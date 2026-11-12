#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep04 音频 —— 逐句表演 TTS + 时间轴拼装
=====================================
读取 narration/performance.json（Lead 写定的权威表演谱），对每一句调用 edge-tts
生成独立音频，实测时长（解码后去除首尾数字静音），再按 pause_after / segment_gap /
cold_open / outro 拼出整条旁白轨与时间轴。

产出：
  work/tts/{Sx}_{NN}.mp3        逐句原始 TTS
  work/tts/{Sx}_{NN}.wav        逐句 48kHz 单声道 float32（已裁静音、已加收发淡入淡出）
  work/tts/durations.json       逐句实测时长/峰值/RMS/句间留白
  work/narration.wav            48kHz 立体声（双单声道）干声旁白轨，长度 = 全片总时长
  work/timeline_audio.json      段/句级时间轴（供 Lead 渲染器使用）
  work/srt/all.srt              句级 SRT（每行 ≤18 汉字宽度，时间单调）

注意：TTS 不可复现（同一 request 每次结果可能有细微差异）。默认复用已存在的 mp3，
      --force 才重新生成；时间轴永远由实测时长驱动。

用法：
  python3 tts_perf.py                 # 生成缺失句 + 拼装时间轴
  python3 tts_perf.py --force         # 全部重新生成
  python3 tts_perf.py --only S1       # 只重生成某段
  python3 tts_perf.py --assemble-only # 只拼装（用已有 tts）
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

ROOT = "/app/vedio/ep04-body"
EDGE_TTS = "/home/admin/.local/bin/edge-tts"
FFMPEG = "/home/admin/.local/bin/ffmpeg"
SR = 48000
FPS = 24

PERF = os.path.join(ROOT, "narration", "performance.json")
TTS_DIR = os.path.join(ROOT, "work", "tts")
DUR_JSON = os.path.join(TTS_DIR, "durations.json")
NARR_WAV = os.path.join(ROOT, "work", "narration.wav")
TIMELINE = os.path.join(ROOT, "work", "timeline_audio.json")
TIMELINE_FULL = os.path.join(ROOT, "work", "timeline_audio_full.json")
SRT = os.path.join(ROOT, "work", "srt", "all.srt")

# 拼接参数
FADE_IN = 0.008   # 8ms 句首淡入
FADE_OUT = 0.012  # 12ms 句尾淡出（8–15ms 交叉淡化区间）
XFADE_MIN = 0.020 # 相邻句间隔小于此值时做等功率交叠交叉淡化


def norm_param(v, unit):
    """performance.json 里的 rate/pitch 写作 0% / 2% / 0Hz / 1Hz，
    edge-tts 7.x 校验正则要求显式符号 ^[+-]\\d+%$ / ^[+-]\\d+Hz$。
    这里只补符号，不改变数值与设计意图（0 仍是 0）。"""
    s = str(v).strip()
    if s and s[0] not in "+-":
        s = "+" + s
    return s


def log(*a):
    print(*a, flush=True)


def run(cmd, timeout=180, **kw):
    return subprocess.run(cmd, capture_output=True, timeout=timeout, **kw)


def decode(path, sr=SR, mono=True):
    """用 ffmpeg 解码任意音频为 float32 numpy。"""
    cmd = [FFMPEG, "-v", "error", "-i", path, "-f", "f32le", "-acodec", "pcm_f32le"]
    if mono:
        cmd += ["-ac", "1"]
    cmd += ["-ar", str(sr), "-"]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg decode failed: %s\n%s" % (path, p.stderr.decode("utf-8", "replace")))
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def probe_duration(path):
    """ffmpeg(本机 ffprobe 符号链接到 ffmpeg) 读取容器/流时长。"""
    p = run([FFMPEG, "-hide_banner", "-i", path])
    txt = p.stderr.decode("utf-8", "replace")
    dur = None
    for line in txt.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            hms = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = hms.split(":")
            dur = int(h) * 3600 + int(m) * 60 + float(s)
    return dur, txt


def write_wav(path, x, sr=SR, channels=1):
    """float32 -> 16bit PCM WAV（numpy 直接写，避免临时文件）。"""
    x = np.asarray(x, dtype=np.float32)
    if channels == 2 and x.ndim == 1:
        x = np.stack([x, x], axis=1)
    inter = np.clip(x, -1.0, 1.0)
    pcm = (inter * 32767.0).astype("<i2")
    if pcm.ndim == 1:
        ch, n = 1, pcm.shape[0]
    else:
        n, ch = pcm.shape
    data = pcm.tobytes()
    import struct
    hdr = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    hdr += b"fmt " + struct.pack("<IHHIIHH", 16, 1, ch, sr, sr * ch * 2, ch * 2, 16)
    hdr += b"data" + struct.pack("<I", len(data))
    with open(path, "wb") as f:
        f.write(hdr)
        f.write(data)


def trim_silence(x, sr=SR):
    """去除首尾数字静音，保留极短自然吸气/尾音。返回 (裁剪后音频, 前裁秒, 后裁秒)。"""
    if len(x) == 0:
        return x, 0.0, 0.0
    win = max(1, int(0.010 * sr))  # 10ms 能量窗
    a = np.abs(x).astype(np.float64)
    c = np.concatenate([[0.0], np.cumsum(a * a)])
    n = len(x)
    idx = np.arange(win, n + 1)
    env = np.sqrt((c[idx] - c[idx - win]) / win)
    peak = env.max()
    if peak <= 1e-9:
        return x, 0.0, 0.0
    thr = max(2e-4, peak * 0.008)  # 约 -42dB rel. 峰值 / 绝对 -74dBFS
    above = np.where(env > thr)[0]
    if len(above) == 0:
        return x, 0.0, 0.0
    first = above[0]
    last = above[-1] + win
    lead = max(0, first - int(0.015 * sr))
    tail = min(n, last + int(0.060 * sr))
    return x[lead:tail], lead / sr, (n - tail) / sr


def tts_one(job, voice, force):
    """生成/复用一句 TTS，返回实测信息。"""
    sid, text, rate, pitch = job
    rate = norm_param(rate, "%")
    pitch = norm_param(pitch, "Hz")
    mp3 = os.path.join(TTS_DIR, sid + ".mp3")
    ok = os.path.exists(mp3) and os.path.getsize(mp3) > 2000 and not force
    if not ok:
        err = None
        for attempt in range(1, 6):
            if os.path.exists(mp3):
                os.remove(mp3)
            cmd = [EDGE_TTS, "--voice", voice, "--rate=" + rate, "--pitch=" + pitch,
                   "--text", text, "--write-media", mp3]
            p = run(cmd, timeout=120)
            good = os.path.exists(mp3) and os.path.getsize(mp3) > 2000
            if p.returncode == 0 and good:
                err = None
                break
            err = (p.returncode, p.stderr.decode("utf-8", "replace")[-400:])
            log("[tts] retry %d %s: %s" % (attempt, sid, err[1][:160]))
            time.sleep(1.5 * attempt)
        if err is not None or not os.path.exists(mp3):
            raise RuntimeError("TTS failed for %s: %s" % (sid, err))
    raw = decode(mp3, mono=True)
    if len(raw) == 0:
        raise RuntimeError("decoded empty audio for " + sid)
    clip, lead, tail = trim_silence(raw)
    # 8–15ms 收发淡化（防拼接爆音；不与静音段重叠，故不改变语义）
    fi = min(len(clip), int(FADE_IN * SR))
    fo = min(len(clip), int(FADE_OUT * SR))
    if fi > 0:
        clip[:fi] *= np.linspace(0.0, 1.0, fi, dtype=np.float32)
    if fo > 0:
        clip[-fo:] *= np.linspace(1.0, 0.0, fo, dtype=np.float32)
    wav = os.path.join(TTS_DIR, sid + ".wav")
    write_wav(wav, clip)
    dur = len(clip) / SR
    peak = float(np.max(np.abs(clip))) if len(clip) else 0.0
    rms = float(np.sqrt(np.mean(clip.astype(np.float64) ** 2))) if len(clip) else 0.0
    return sid, dict(
        sid=sid, text=text, rate=rate, pitch=pitch,
        mp3=os.path.relpath(mp3, ROOT), wav=os.path.relpath(wav, ROOT),
        mp3_dur=round(len(raw) / SR, 4),
        lead_trim=round(lead, 4), tail_trim=round(tail, 4),
        dur=round(dur, 4),
        peaks=round(peak, 4),
        rms_db=round(20 * np.log10(max(rms, 1e-9)), 2),
        peak_db=round(20 * np.log10(max(peak, 1e-9)), 2),
    )


def load_perf():
    with open(PERF, "r", encoding="utf-8") as f:
        return json.load(f)


def jobs_from_perf(perf, only=None):
    js = []
    for seg in perf["segments"]:
        if only and seg["id"] not in only:
            continue
        for s in seg["sentences"]:
            sid = "%s_%02d" % (seg["id"], s["i"])
            js.append((sid, s["text"], s["rate"], s["pitch"]))
    return js


def build_narration(perf, durations):
    """按表演谱计算时间轴并拼出整轨旁白。"""
    sr = SR
    cold = float(perf["cold_open"])
    outro = float(perf["outro"])
    gap = float(perf["segment_gap"])

    # 先算总长
    cursor = cold
    seg_meta = []
    for seg in perf["segments"]:
        start = cursor
        sent_meta = []
        for s in seg["sentences"]:
            sid = "%s_%02d" % (seg["id"], s["i"])
            d = durations[sid]["dur"]
            sent_meta.append(dict(i=s["i"], text=s["text"], sid=sid,
                                  start=round(cursor, 5), end=round(cursor + d, 5),
                                  dur=round(d, 5), pause_after=float(s["pause_after"]),
                                  rate=s["rate"], pitch=s["pitch"]))
            cursor += d + float(s["pause_after"])
        seg_end = cursor
        seg_meta.append(dict(id=seg["id"], name=seg["name"], start=round(start, 5),
                             end=round(seg_end, 5), dur=round(seg_end - start, 5),
                             pause_before=float(seg.get("pause_before", gap)),
                             sentences=sent_meta))
        cursor += gap
    total = cursor - gap + outro  # 最后一段之后是 outro，不再加 segment_gap
    total = round(total, 5)
    n = int(round(total * sr))

    buf = np.zeros(n, dtype=np.float32)
    placed = 0
    for seg in seg_meta:
        for s in seg["sentences"]:
            clip = decode(os.path.join(ROOT, durations[s["sid"]]["wav"]), mono=True)
            i0 = int(round(s["start"] * sr))
            i1 = i0 + len(clip)
            if i1 > n:
                raise RuntimeError("clip overruns total: " + s["sid"])
            # 若与前一 clip 交叠（理论上不会，留白均 >0.4s），做等功率交叉淡化
            seg_prev_end = None
            buf[i0:i1] += clip
            placed += 1

    # 双单声道立体声
    st = np.stack([buf, buf], axis=1)
    write_wav(NARR_WAV, st, sr=sr, channels=2)

    # 完整内部数据（含 pause_after/rate/pitch/dur，供混音与报告使用）
    tl_full = dict(
        source="narration/performance.json",
        voice=perf["voice"],
        fps=FPS,
        sample_rate=sr,
        cold_open=round(cold, 4),
        outro=round(outro, 4),
        segment_gap=round(gap, 4),
        total=round(total, 5),
        total_samples=n,
        narration_end=round(seg_meta[-1]["end"], 5),
        segments=seg_meta,
    )
    with open(TIMELINE_FULL, "w", encoding="utf-8") as f:
        json.dump(tl_full, f, ensure_ascii=False, indent=2)
    # 交付给渲染器的严格字段版
    tl = dict(
        cold_open=round(cold, 4),
        outro=round(outro, 4),
        segment_gap=round(gap, 4),
        fps=FPS,
        total=round(total, 5),
        segments=[dict(
            id=s["id"], name=s["name"], start=round(s["start"], 4),
            dur=round(s["dur"], 4),
            sentences=[dict(i=x["i"], text=x["text"],
                            start=round(x["start"], 4), end=round(x["end"], 4))
                       for x in s["sentences"]],
        ) for s in seg_meta],
    )
    with open(TIMELINE, "w", encoding="utf-8") as f:
        json.dump(tl, f, ensure_ascii=False, indent=2)

    # 一致性自检
    for seg in seg_meta:
        d = sum(s["dur"] + s["pause_after"] for s in seg["sentences"])
        assert abs(d - seg["dur"]) < 1e-3, (seg["id"], d, seg["dur"])
    return tl, tl_full, buf


# ---------------- SRT ----------------
def disp_width(ch):
    o = ord(ch)
    if o >= 0x2E80:  # CJK 及全角
        return 1.0
    if ch in "，。？！：；、“”《》（）—…·":
        return 1.0
    if ch in " .,:;!?'\"()[]{}/-":
        return 0.4
    return 0.55


SAFE_NEXT = set("为是真让你我他她它而但却就还也都不要能可会把被在有这那便才又再从对向于给跟和与或如因所使令叫请替帮")
# 这些字后面不宜断行（功能字/词头），否则会把词拆开
BAD_AFTER = set("的了着过就都也还才又再却但而和与或在不没很太最更便替帮使令叫请给把被让向从到于以及所因为如若其且则之你 我 他 她 它 这 那 个 些 有 是 会 要 能 可 想 该 将 已 曾 正 刚 时 后 前 中 上 下 里 外 第 每 各 名 位 件 种 次 分 秒 年 月 日 号 岁 元 个 得")
NO_BREAK_BEFORE = set("，。；：？！、,.;:?!")
OPEN_Q = set("\u201c\u2018\u300a\uff08\u3010\u300c\u300e")
CLOSE_Q = set("\u201d\u2019\u300b\uff09\u3011\u300d\u300f")

# 常见词/专有名词表：断行位置落在词内部时加罚，避免「卡内/基梅隆」「交/给」这类拆词
WORDS = """为什么 什么 怎么 这个 那个 这些 那些 我们 你们 他们 自己 判断 标准 责任
执行 问题 能力 验证 风险 工具 模型 研究 结果 数据 案例 论文 记忆 归属 时间 版本
答案 逻辑 解释 框架 方法 过程 结论 特别 真的 不是 就是 而是 还是 也是 都是 就会
就能 会有 交给 以后 之前 之后 已经 因为 所以 如果 但是 然而 而且 并且 或者 甚至
反而 其实 只是 只要 只有 没有 可以 可能 应该 必须 需要 觉得 认为 发现 知道 理解
决定 选择 相信 怀疑 承担 外包 加速 积累 熟练 复杂 简单 完整 重要 危险 安全 普遍
规模 有限 同行 评审 预印本 知识 工作者 研究者 调查 收到 真实 使用 生成 核验 内容
信息 时代 算力 体力 劳动 历史 通用 分配 计算器 导航 口算 敌人 恰好 足够 时候 容易
不再 哪里 不对 三句话 第一 第二 第三 可逆 放心 留在 手里 更好 反例 后果 解释
框架 现成 大脑 连接 活动 作品 归属感 批判性 思考 相关 信心 推测 证据 结论 边界
提示 提醒 省下 不一定 未必 长期 依赖 大模型 参与者 分组 写论文 执行框架 判断力
债务 成本 便宜 版本 方案 资料 框架 改几遍 复制 解释 时刻 答案 逻辑 顺 全
卡内基梅隆 卡内基 梅隆 大学 微软 苹果 时代 最贵 算力 判断 评论 评论区 说说 后悔
Microsoft Research MIT Media Lab 微软 研究 媒体 实验室 预印本 同行评审 大模型
调查了 收到了 自己的 简单问题 复杂问题 卡内基梅隆大学 三年 两件事 三件事 一部分 复杂问题 长期依赖
越有信心 批判性思考 连接活动 归属感 作品记忆 知识工作者 使用案例 真实 AI 案例 算力 判断力 债务
写得像 很难发现 不是让 让你的 给了你 你自己 我们没有 没有人 是怎么 哪里可能 一起交 得像
""".split()



def wrap_sentence(text, maxw=18.0):
    """按 ≤14 汉字宽度断行。动态规划：优先标点断行，其次短语边界，
    避免拆词（如「为什么」「就能」「之前」）和在 ASCII 词内部断开。"""
    n = len(text)
    if n == 0:
        return [""]
    W = [disp_width(c) for c in text]
    bad_break = set()
    for w in WORDS:
        k = text.find(w)
        while k >= 0:
            for p in range(k + 1, k + len(w)):
                bad_break.add(p)
            k = text.find(w, k + 1)

    def break_cost(j):
        """在 text[j-1] 与 text[j] 之间断行的代价（越小越自然）。"""
        if j <= 0 or j >= n:
            return 0.0
        prev, nxt = text[j - 1], text[j]
        if prev in NO_BREAK_BEFORE:
            return 0.0                       # 标点后断行：最自然
        if nxt in NO_BREAK_BEFORE:
            return 8.0                       # 标点不能出现在行首
        if prev in OPEN_Q:
            return 9.0                       # 左引号后不能断
        if nxt in CLOSE_Q:
            return 9.0                       # 右引号不能出现在行首
        if j in bad_break:
            return 7.0                       # 断在词/专名内部
        if prev in BAD_AFTER:
            return 6.0                       # 拆词/拆短语
        if prev.isascii() and nxt.isascii() and prev.isalnum() and nxt.isalnum():
            return 8.0                       # 拆开 ASCII 单词
        if prev.isspace() or nxt.isspace():
            return 2.5                       # 英文词之间断行（可接受）
        if prev.isascii() or nxt.isascii():
            return 1.5                       # 中英之间
        if nxt in SAFE_NEXT:
            return 1.2                       # 在功能字/词头前断：短语边界
        return 3.0

    INF = 1e18
    dp = [INF] * (n + 1)
    prev_idx = [-1] * (n + 1)
    dp[0] = 0.0
    for j in range(1, n + 1):
        w = 0.0
        for i in range(j - 1, -1, -1):
            w += W[i]
            if w > maxw + 1e-9:
                break
            bc = break_cost(j)
            c = dp[i] + 2.2 + bc
            if w < maxw * 0.45:             # 行太短（比如只剩「2025 年，」）
                c += 1.2 * (maxw * 0.45 - w)
            if w < 6.5 and j < n and text[j - 1] in NO_BREAK_BEFORE:
                c += 2.5                    # 标点后只剩很短一行：尽量并到下一行
            if c < dp[j]:
                dp[j] = c
                prev_idx[j] = i
    cuts, j = [], n
    while j > 0:
        i = prev_idx[j]
        if i < 0:
            i = 0
        cuts.append((i, j))
        j = i
    cuts.reverse()
    return [text[a:b].strip() for a, b in cuts if text[a:b].strip()]


def time_to_srt(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def build_srt(tl, maxw=18.0):
    entries = []
    for seg in tl["segments"]:
        for s in seg["sentences"]:
            lines = wrap_sentence(s["text"], maxw)
            # 按显示宽度分配句内时间（单调、不重叠）
            ws = [max(0.2, sum(disp_width(c) for c in ln)) for ln in lines]
            tot = sum(ws)
            t = s["start"]
            span = max(0.05, s["end"] - s["start"])
            for ln, w in zip(lines, ws):
                d = span * w / tot
                entries.append((t, min(s["end"], t + d), ln))
                t += d
    # 保证单调且不越界
    out = []
    for idx, (a, b, txt) in enumerate(entries):
        a = max(0.0, a)
        b = max(a + 0.05, b)
        if idx + 1 < len(entries):
            b = min(b, entries[idx + 1][0])
        out.append((a, b, txt))
    os.makedirs(os.path.dirname(SRT), exist_ok=True)
    with open(SRT, "w", encoding="utf-8") as f:
        for i, (a, b, txt) in enumerate(out, 1):
            f.write("%d\n%s --> %s\n%s\n\n" % (i, time_to_srt(a), time_to_srt(b), txt))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default=None, help="逗号分隔段 ID，如 S1,S6")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--assemble-only", action="store_true")
    args = ap.parse_args()

    os.makedirs(TTS_DIR, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "work", "srt"), exist_ok=True)
    perf = load_perf()
    durations = {}
    if os.path.exists(DUR_JSON):
        with open(DUR_JSON, "r", encoding="utf-8") as f:
            durations = json.load(f)

    if not args.assemble_only:
        only = set(args.only.split(",")) if args.only else None
        js = jobs_from_perf(perf, only)
        log("[tts] %d sentences, voice=%s, workers=%d" % (len(js), perf["voice"], args.workers))
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(tts_one, j, perf["voice"], args.force): j[0] for j in js}
            for k, fut in enumerate(as_completed(futs), 1):
                sid, info = fut.result()
                durations[sid] = info
                log("  [%2d/%2d] %s dur=%.3fs peak=%.1fdBFS speech=%.1fdB" % (
                    k, len(js), sid, info["dur"], info["peak_db"], info["rms_db"]))
        log("[tts] done in %.1fs" % (time.time() - t0))
        # 保留旧记录（--only 时），但只写本 perf 里出现的句子
        all_sids = [sid for sid, _, _, _ in jobs_from_perf(perf)]
        durations = {sid: durations[sid] for sid in all_sids if sid in durations}
        missing = [sid for sid in all_sids if sid not in durations]
        if missing:
            raise RuntimeError("missing durations: %s" % missing)
        with open(DUR_JSON, "w", encoding="utf-8") as f:
            json.dump(durations, f, ensure_ascii=False, indent=2)
        log("[tts] wrote " + DUR_JSON)

    # 拼装
    missing = [sid for sid in [ "%s_%02d" % (g["id"], s["i"]) for g in perf["segments"] for s in g["sentences"]] if sid not in durations]
    if missing:
        raise RuntimeError("durations missing, run tts first: %s" % missing)
    tl, tl_full, buf = build_narration(perf, durations)
    srt = build_srt(tl_full)
    log("[assemble] total=%.3fs  narration_end=%.3fs  srt_lines=%d" % (tl_full["total"], tl_full["narration_end"], len(srt)))
    for seg in tl_full["segments"]:
        log("  %s %-4s start=%7.3f dur=%7.3f end=%7.3f  sentences=%d" % (
            seg["id"], seg["name"], seg["start"], seg["dur"], seg["end"], len(seg["sentences"])))
    log("[assemble] wrote %s, %s, %s" % (NARR_WAV, TIMELINE, SRT))

    # 打印关键留白自检
    key = {"S1_05": 1.15, "S2_09": 0.82, "S5_05": 1.00, "S5_08": 1.45, "S5_11": 0.60}
    for seg in tl_full["segments"]:
        for s in seg["sentences"]:
            if s["sid"] in key:
                log("  [gap] %s pause_after=%.2fs (design %.2fs)" % (s["sid"], s["pause_after"], key[s["sid"]]))


if __name__ == "__main__":
    main()
