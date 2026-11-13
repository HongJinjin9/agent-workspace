#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep06 三声部音频 —— 逐句表演 TTS + 分轨拼装 + 时间轴 + SRT
==========================================================
读取 narration/performance.json（三声部表演谱：N 旁白 / M 老规矩 / L 小账本），
对每一句按其 speaker 调用对应 edge-tts 音色生成独立音频，实测时长（解码后去除首尾
数字静音），再按 pause_after / act_gap / cold_open / outro 拼出整条旁白轨与时间轴。

产出：
  work/tts/{SID}.mp3 / .wav            逐句原始 TTS + 已裁静音/收发淡化的 48kHz 单声道
  work/tts/durations.json              逐句实测时长/峰值/RMS/voice/speaker
  work/narration.wav                   三声部合轨干声（48k 立体声，长度=全片）
  work/narration_N.wav / _M.wav / _L.wav   按 speaker 分轨干声（同长度，供混音分别处理）
  work/timeline_audio.json             段（幕）/句级时间轴（含 speaker 字段，供渲染器使用）
  work/timeline_audio_full.json        同上 + rate/pitch/pause_after/outro_voice
  work/srt/all.srt                     句级 SRT（每行 ≤18 汉字显示宽度；每句不跨 speaker）
  work/srt/speakers.json               SRT 条目 -> speaker 映射（speaker-aware 旁挂）

用法：
  python3 tts_perf.py                 # 生成缺失句 + 拼装
  python3 tts_perf.py --force         # 全部重新生成
  python3 tts_perf.py --assemble-only # 只拼装
"""
import argparse
import json
import os
import struct
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

ROOT = "/app/vedio/ep06-dialogue"
EDGE_TTS = "/home/admin/.local/bin/edge-tts"
FFMPEG = "/home/admin/.local/bin/ffmpeg"
SR = 48000
FPS = 24

PERF = os.path.join(ROOT, "narration", "performance.json")
TTS_DIR = os.path.join(ROOT, "work", "tts")
DUR_JSON = os.path.join(TTS_DIR, "durations.json")
NARR_WAV = os.path.join(ROOT, "work", "narration.wav")
STEMS = {s: os.path.join(ROOT, "work", "narration_%s.wav" % s) for s in ("N", "M", "L")}
TIMELINE = os.path.join(ROOT, "work", "timeline_audio.json")
TIMELINE_FULL = os.path.join(ROOT, "work", "timeline_audio_full.json")
SRT = os.path.join(ROOT, "work", "srt", "all.srt")
SRT_SPK = os.path.join(ROOT, "work", "srt", "speakers.json")

FADE_IN = 0.008
FADE_OUT = 0.012
OUTRO_SID = "OUTRO_01"


def norm_param(v):
    s = str(v).strip()
    if s and s[0] not in "+-":
        s = "+" + s
    return s


def log(*a):
    print(*a, flush=True)


def run(cmd, timeout=180, **kw):
    return subprocess.run(cmd, capture_output=True, timeout=timeout, **kw)


def decode(path, sr=SR, mono=True):
    cmd = [FFMPEG, "-v", "error", "-threads", "2", "-i", path,
           "-f", "f32le", "-acodec", "pcm_f32le"]
    if mono:
        cmd += ["-ac", "1"]
    cmd += ["-ar", str(sr), "-"]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg decode failed: %s\n%s" % (path, p.stderr.decode("utf-8", "replace")))
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def write_wav(path, x, sr=SR, channels=1):
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
    hdr = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    hdr += b"fmt " + struct.pack("<IHHIIHH", 16, 1, ch, sr, sr * ch * 2, ch * 2, 16)
    hdr += b"data" + struct.pack("<I", len(data))
    with open(path, "wb") as f:
        f.write(hdr)
        f.write(data)


def trim_silence(x, sr=SR):
    if len(x) == 0:
        return x, 0.0, 0.0
    win = max(1, int(0.010 * sr))
    a = np.abs(x).astype(np.float64)
    c = np.concatenate([[0.0], np.cumsum(a * a)])
    n = len(x)
    idx = np.arange(win, n + 1)
    env = np.sqrt((c[idx] - c[idx - win]) / win)
    peak = env.max()
    if peak <= 1e-9:
        return x, 0.0, 0.0
    thr = max(2e-4, peak * 0.008)
    above = np.where(env > thr)[0]
    if len(above) == 0:
        return x, 0.0, 0.0
    first = above[0]
    last = above[-1] + win
    lead = max(0, first - int(0.015 * sr))
    tail = min(n, last + int(0.060 * sr))
    return x[lead:tail], lead / sr, (n - tail) / sr


def tts_one(job, voice, force):
    """生成/复用一句 TTS，返回实测信息。job=(sid, text, rate, pitch, speaker)。"""
    sid, text, rate, pitch, spk = job
    rate = norm_param(rate)
    pitch = norm_param(pitch)
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
    fi = min(len(clip), int(FADE_IN * SR))
    fo = min(len(clip), int(FADE_OUT * SR))
    if fi > 0:
        clip[:fi] *= np.linspace(0.0, 1.0, fi, dtype=np.float32)
    if fo > 0:
        clip[-fo:] *= np.linspace(1.0, 0.0, fo, dtype=np.float32)
    write_wav(os.path.join(TTS_DIR, sid + ".wav"), clip)
    dur = len(clip) / SR
    peak = float(np.max(np.abs(clip))) if len(clip) else 0.0
    rms = float(np.sqrt(np.mean(clip.astype(np.float64) ** 2))) if len(clip) else 0.0
    return sid, dict(
        sid=sid, text=text, speaker=spk, voice=voice, rate=rate, pitch=pitch,
        mp3=os.path.relpath(mp3, ROOT), wav=os.path.relpath(os.path.join(TTS_DIR, sid + ".wav"), ROOT),
        mp3_dur=round(len(raw) / SR, 4), lead_trim=round(lead, 4), tail_trim=round(tail, 4),
        dur=round(dur, 4), peaks=round(peak, 4),
        rms_db=round(20 * np.log10(max(rms, 1e-9)), 2),
        peak_db=round(20 * np.log10(max(peak, 1e-9)), 2),
    )


def load_perf():
    with open(PERF, "r", encoding="utf-8") as f:
        return json.load(f)


def jid(seg_id, i):
    return "%s_%02d" % (seg_id, i)


def jobs_from_perf(perf):
    js = []
    for seg in perf["segments"]:
        for s in seg["sentences"]:
            js.append((jid(seg["id"], s["i"]), s["text"], s["rate"], s["pitch"], s["speaker"]))
    ov = perf.get("outro_voice")
    if ov:
        js.append((OUTRO_SID, ov["text"], ov["rate"], ov["pitch"], ov.get("speaker", "N")))
    return js


def build_narration(perf, durations):
    sr = SR
    cold = float(perf["cold_open"])
    outro = float(perf["outro"])
    gap = float(perf.get("act_gap", perf.get("segment_gap", 1.5)))
    voices = perf["voices"]

    cursor = cold
    seg_meta = []
    for seg in perf["segments"]:
        start = cursor
        sent_meta = []
        for s in seg["sentences"]:
            sid = jid(seg["id"], s["i"])
            d = durations[sid]["dur"]
            sent_meta.append(dict(i=s["i"], speaker=s["speaker"], text=s["text"], sid=sid,
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
    seg_end = cursor - gap

    ov = perf.get("outro_voice")
    ov_meta = None
    if ov:
        ov_start = seg_end + float(ov.get("pause_before", 0.8))
        ov_dur = durations[OUTRO_SID]["dur"]
        ov_meta = dict(sid=OUTRO_SID, speaker=ov.get("speaker", "N"), voice=voices[ov.get("speaker", "N")]["voice"],
                       text=ov["text"], start=round(ov_start, 5), end=round(ov_start + ov_dur, 5),
                       dur=round(ov_dur, 5), rate=ov["rate"], pitch=ov["pitch"],
                       pause_before=float(ov.get("pause_before", 0.8)))
        total = max(seg_end + outro, ov_meta["end"] + 1.0)
    else:
        total = seg_end + outro
    total = round(total, 5)
    n = int(round(total * sr))

    buf = np.zeros(n, dtype=np.float32)
    stems = {s: np.zeros(n, dtype=np.float32) for s in ("N", "M", "L")}
    for seg in seg_meta:
        for s in seg["sentences"]:
            clip = decode(os.path.join(ROOT, durations[s["sid"]]["wav"]), mono=True)
            i0 = int(round(s["start"] * sr))
            i1 = i0 + len(clip)
            if i1 > n:
                raise RuntimeError("clip overruns total: " + s["sid"])
            buf[i0:i1] += clip
            stems.setdefault(s["speaker"], np.zeros(n, dtype=np.float32))[i0:i1] += clip
    if ov_meta:
        clip = decode(os.path.join(ROOT, durations[OUTRO_SID]["wav"]), mono=True)
        i0 = int(round(ov_meta["start"] * sr))
        if i0 + len(clip) > n:
            raise RuntimeError("outro voice overruns total")
        buf[i0:i0 + len(clip)] += clip
        stems.setdefault(ov_meta["speaker"], np.zeros(n, dtype=np.float32))[i0:i0 + len(clip)] += clip

    write_wav(NARR_WAV, np.stack([buf, buf], axis=1), sr=sr, channels=2)
    for spk, x in stems.items():
        if spk in STEMS:
            write_wav(STEMS[spk], np.stack([x, x], axis=1), sr=sr, channels=2)

    tl_full = dict(
        source="narration/performance.json",
        voices={k: dict(voice=v["voice"], role=v["role"], label=v["label"]) for k, v in voices.items()},
        fps=FPS, sample_rate=sr,
        cold_open=round(cold, 4), outro=round(outro, 4), act_gap=round(gap, 4),
        segment_gap=round(gap, 4),
        total=round(total, 5), total_samples=n,
        narration_end=round(seg_meta[-1]["end"], 5),
        narration_end_with_outro=round(ov_meta["end"], 5) if ov_meta else round(seg_meta[-1]["end"], 5),
        outro_voice=ov_meta,
        stems={k: os.path.relpath(v, ROOT) for k, v in STEMS.items()},
        segments=seg_meta,
    )
    with open(TIMELINE_FULL, "w", encoding="utf-8") as f:
        json.dump(tl_full, f, ensure_ascii=False, indent=2)

    tl = dict(
        cold_open=round(cold, 4), outro=round(outro, 4),
        act_gap=round(gap, 4), segment_gap=round(gap, 4), fps=FPS,
        total=round(total, 5),
        voices={k: dict(voice=v["voice"], role=v["role"], label=v["label"]) for k, v in voices.items()},
        outro_voice=dict(speaker=ov_meta["speaker"], text=ov_meta["text"],
                         start=round(ov_meta["start"], 4), end=round(ov_meta["end"], 4)) if ov_meta else None,
        segments=[dict(
            id=s["id"], name=s["name"], start=round(s["start"], 4), dur=round(s["dur"], 4),
            sentences=[dict(i=x["i"], speaker=x["speaker"], text=x["text"],
                            start=round(x["start"], 4), end=round(x["end"], 4))
                       for x in s["sentences"]],
        ) for s in seg_meta],
    )
    with open(TIMELINE, "w", encoding="utf-8") as f:
        json.dump(tl, f, ensure_ascii=False, indent=2)

    for seg in seg_meta:
        d = sum(s["dur"] + s["pause_after"] for s in seg["sentences"])
        assert abs(d - seg["dur"]) < 1e-3, (seg["id"], d, seg["dur"])
    return tl, tl_full, buf


# ---------------- SRT ----------------
def disp_width(ch):
    o = ord(ch)
    if o >= 0x2E80:
        return 1.0
    if ch in "，。？！：；、“”《》（）—…·":
        return 1.0
    if ch in " .,:;!?'\"()[]{}/-":
        return 0.4
    return 0.55


SAFE_NEXT = set("为是真让你我他她它而但却就还也都不要能可会把被在有这那便才又再从对向于给跟和与或如因所使令叫请替帮")
BAD_AFTER = set("的了着过就都也还才又再却但而和与或在不没很太最更便替帮使令叫请给把被让向从到于以及所因为如若其且则之你 我 他 她 它 这 那 个 些 有 是 会 要 能 可 想 该 将 已 曾 正 刚 时 后 前 中 上 下 里 外 第 每 各 名 位 件 种 次 分 秒 年 月 日 号 岁 元 个 得")
NO_BREAK_BEFORE = set("，。；：？！、,.;:?!")
OPEN_Q = set("\u201c\u2018\u300a\uff08\u3010\u300c\u300e")
CLOSE_Q = set("\u201d\u2019\u300b\uff09\u3011\u300d\u300f")

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
增程 增程式 电动车 内燃机 热力学 上险 单月 销量 同比 下滑 概念车 车展 高压平台
充电 超车 高速 用户 市场 份额 判决 改判 再判 立判 手册 账本 空白 虚拟 声明
一万三千四百三十八 一万二千四百四十五 九百九十三 二十四点九 复合 转换 能量
大众集团 中国区 媒体沟通会 冯思翰 李想 微博 理想 ONE 上汽大众 ID.ERA 途昂 途锐
揽境 ID.6 Crozz SUV 成都 上海 一年后 四年 前五个月 百分之 继续努力 感谢鞭策
就这么算 这不是观点 是热力学 不算账 算别的账 不看你 他看我 多丢一次 多一道
说得很实 过时 潜力不大 发动机 发电 用电 驱动 车轮 整个国家 地球 角度 简直
胡说八道 最糟糕 方案 单车 角度 具备 一定 价值
""".split()


def wrap_sentence(text, maxw=18.0):
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
        if j <= 0 or j >= n:
            return 0.0
        prev, nxt = text[j - 1], text[j]
        if prev in NO_BREAK_BEFORE:
            return 0.0
        if nxt in NO_BREAK_BEFORE:
            return 8.0
        if prev in OPEN_Q:
            return 9.0
        if nxt in CLOSE_Q:
            return 9.0
        if j in bad_break:
            return 7.0
        if prev in BAD_AFTER:
            return 6.0
        if prev.isascii() and nxt.isascii() and prev.isalnum() and nxt.isalnum():
            return 8.0
        if prev.isspace() or nxt.isspace():
            return 2.5
        if prev.isascii() or nxt.isascii():
            return 1.5
        if nxt in SAFE_NEXT:
            return 1.2
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
            c = dp[i] + 2.2 + break_cost(j)
            if w < maxw * 0.45:
                c += 1.2 * (maxw * 0.45 - w)
            if w < 6.5 and j < n and text[j - 1] in NO_BREAK_BEFORE:
                c += 2.5
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


def build_srt(tl):
    entries = []
    for seg in tl["segments"]:
        for s in seg["sentences"]:
            lines = wrap_sentence(s["text"], 18.0)
            ws = [max(0.2, sum(disp_width(c) for c in ln)) for ln in lines]
            tot = sum(ws)
            t = s["start"]
            span = max(0.05, s["end"] - s["start"])
            for ln, w in zip(lines, ws):
                d = span * w / tot
                entries.append((t, min(s["end"], t + d), ln, s["speaker"], s["i"], seg["id"]))
                t += d
    ov = tl.get("outro_voice")
    if ov:
        lines = wrap_sentence(ov["text"], 18.0)
        ws = [max(0.2, sum(disp_width(c) for c in ln)) for ln in lines]
        tot = sum(ws)
        t = ov["start"]
        span = max(0.05, ov["end"] - ov["start"])
        for ln, w in zip(lines, ws):
            d = span * w / tot
            entries.append((t, min(ov["end"], t + d), ln, ov["speaker"], 0, "OUTRO"))
            t += d
    out = []
    for idx, (a, b, txt, spk, si, segid) in enumerate(entries):
        a = max(0.0, a)
        b = max(a + 0.05, b)
        if idx + 1 < len(entries):
            b = min(b, entries[idx + 1][0])
        out.append((a, b, txt, spk, si, segid))
    os.makedirs(os.path.dirname(SRT), exist_ok=True)
    with open(SRT, "w", encoding="utf-8") as f:
        for i, (a, b, txt, spk, si, segid) in enumerate(out, 1):
            f.write("%d\n%s --> %s\n%s\n\n" % (i, time_to_srt(a), time_to_srt(b), txt))
    with open(SRT_SPK, "w", encoding="utf-8") as f:
        json.dump([dict(idx=i, start=round(a, 4), end=round(b, 4), speaker=spk,
                        sent=i0, seg=segid, text=txt)
                   for i, (a, b, txt, spk, i0, segid) in enumerate(out, 1)],
                  f, ensure_ascii=False, indent=1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--assemble-only", action="store_true")
    args = ap.parse_args()

    os.makedirs(TTS_DIR, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "work", "srt"), exist_ok=True)
    perf = load_perf()
    voices = perf["voices"]
    durations = {}
    if os.path.exists(DUR_JSON):
        with open(DUR_JSON, "r", encoding="utf-8") as f:
            durations = json.load(f)

    if not args.assemble_only:
        js = jobs_from_perf(perf)
        log("[tts] %d sentences (N/M/L=%d/%d/%d), workers=%d" % (
            len(js),
            sum(1 for j in js if j[4] == "N"), sum(1 for j in js if j[4] == "M"),
            sum(1 for j in js if j[4] == "L"), args.workers))
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {}
            for j in js:
                futs[ex.submit(tts_one, j, voices[j[4]]["voice"], args.force)] = j[0]
            for k, fut in enumerate(as_completed(futs), 1):
                sid, info = fut.result()
                durations[sid] = info
                log("  [%2d/%2d] %-8s %s dur=%.3fs peak=%.1fdBFS" % (
                    k, len(js), info["speaker"], sid, info["dur"], info["peak_db"]))
        log("[tts] done in %.1fs" % (time.time() - t0))
        all_sids = [sid for sid, _, _, _, _ in jobs_from_perf(perf)]
        durations = {sid: durations[sid] for sid in all_sids if sid in durations}
        missing = [sid for sid in all_sids if sid not in durations]
        if missing:
            raise RuntimeError("missing durations: %s" % missing)
        with open(DUR_JSON, "w", encoding="utf-8") as f:
            json.dump(durations, f, ensure_ascii=False, indent=1)
        log("[tts] wrote " + DUR_JSON)

    tl, tl_full, buf = build_narration(perf, durations)
    srt = build_srt(tl_full)
    log("[assemble] total=%.3fs  narration_end=%.3fs  srt_lines=%d" % (
        tl_full["total"], tl_full["narration_end"], len(srt)))
    for seg in tl_full["segments"]:
        log("  %-6s %-12s start=%7.3f dur=%7.3f end=%7.3f  sentences=%d" % (
            seg["id"], seg["name"], seg["start"], seg["dur"], seg["end"], len(seg["sentences"])))
    log("[assemble] wrote %s, %s, %s, stems=%s" % (NARR_WAV, TIMELINE, SRT, list(STEMS.values())))


if __name__ == "__main__":
    main()
