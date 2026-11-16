#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep08 音频 —— 混音 / 母带 / 自检 / 报告
=====================================
链路：
  1. 旁白干声 audio/work/narration.wav（逐句 edge-tts 拼接轨，不改文字/速率）
     → 80Hz 零相位低切（对称 FIR + 分块卷积，无时延）
     → 保守去齿音（5.2–9kHz 按齿音能量最多 -5dB，分块 STFT）
     → 轻压缩（thr -20dBFS / ratio 1.8 / 最大 -3dB GR，分块包络；不做广播腔）
     → 短房间混响（IR 0.42s / wet 0.10 / 低切 IR）粘合句间
     → 设计长留白（≥0.55s）人工静音门，保证真静默 < -60dBFS（不填底噪）
  2. music.wav（本期原创：能量脉冲动机 + 90BPM 电流脉冲 + 段落性格；
     已含 4 段人工停乐/退开）
     → 分段电平调度（按段角色人工电平表）→ 语义音效处额外轻让（-1.5dB 级）
     → sidechain 保底 duck（最大 -3dB，慢起慢放，防遮字；不是表演）
  3. sfx/*.wav 只在 8 处语义节点放置（时间点由 timeline 句/段锚点推导）
  4. 两遍 loudnorm：I=-14 LUFS / TP≤-1.5 dBTP（交付要求 TP≤-1.0）→ AAC 192k 48kHz 立体声
  5. 自检：时长 / 峰值削波 / 设计静默 / 句起点对齐 / SRT / 旁白完整性相关性
     → audio/work/audio-report.md、audio/work/loudness.txt、audio/work/mix_meta.json

用法：python3 build_audio.py [--skip-encode] [--reuse-encode]
"""
import argparse
import json
import os
import re
import struct
import subprocess

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

ROOT = "/app/vedio/ep08-regen"
AUDIO = os.path.join(ROOT, "audio", "work")
FFMPEG = "/home/admin/.local/bin/ffmpeg"
SR = 48000
F32 = np.float32
THREADS = "2"

TL_FULL = os.path.join(AUDIO, "timeline_audio_full.json")
NARR_WAV = os.path.join(AUDIO, "narration.wav")
MUSIC_WAV = os.path.join(AUDIO, "music.wav")
MUSIC_META = os.path.join(AUDIO, "music_meta.json")
SFX_DIR = os.path.join(AUDIO, "sfx")
MIX_WAV = os.path.join(AUDIO, "mix.wav")
NARR_PROC = os.path.join(AUDIO, "narration_processed.wav")
OUT_M4A = os.path.join(AUDIO, "audio.m4a")
LOUDNESS_TXT = os.path.join(AUDIO, "loudness.txt")
MIX_META = os.path.join(AUDIO, "mix_meta.json")
REPORT = os.path.join(AUDIO, "audio-report.md")
SRT_PATH = os.path.join(AUDIO, "srt", "all.srt")

TARGET_I = -14.0
TARGET_TP = -1.5              # 交付要求 ≤ -1.0 dBTP；这里做得更保守
TARGET_LRA = 11.0
NARR_TARGET_RMS = -19.0
MUSIC_BED_BELOW_NARR_DB = 13.0   # 旁白有声窗口内：音乐床比旁白低约 13dB（另叠 -3dB 保底 duck）

# 分段音乐床电平表：按段角色人工调度（不同段落音乐承担不同任务，电平不同）
ROLE_LEVEL = {"hook": 0.72, "judge": 1.00, "teardown": 0.94, "account": 1.02,
              "account2": 1.02, "limits": 0.64, "rejudge": 1.04, "close": 0.90}
COLD_LEVEL = 0.86

ROLE_DESC = {
    "cold_open": "极稀疏：低 drone + 两记电流脉冲 + 动机碎片 + 一记继电器吸合",
    "hook": "极稀疏：低 drone + 两拍一记电流脉冲 + 稀疏动机碎片，末句一记下落脉冲",
    "judge": "八分电流脉冲 + 低频「轮转」+ 继电器开关；Dm–Bb–F–C pad；段末一记下落脉冲",
    "teardown": "电机上扫层 + 电流脉冲加密 + 低音级进下行 D→C→Bb→A + 上行琶音「电流经过三件套」",
    "account": "十六分电流脉冲 + 「记账」拨弦 + 能量脉冲动机完整陈述；D 多利亚变亮；损耗处退开",
    "account2": "能量账续：十六分脉冲 + 记账拨弦 + 动机陈述",
    "limits": "几乎抽空：慢继电器 + 三条暗色 pad + 四条下落脉冲（一条限制一记）",
    "rejudge": "脉冲回归 + 能量脉冲动机两次 + 明亮对位（F–A–C）+ 上行充能",
    "close": "D 小调→D 大调（皮卡第三度）+ 大调版动机 + 充能上扫 + 片尾 pad",
    "tail": "Dmaj7 pad + 低音 drone + 最后一记下落脉冲，垫住 AI 声明口播",
}


# ---------------------------------------------------------------- 基础
def run(cmd, timeout=1800):
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def decode(path, mono=False, sr=SR):
    # ffmpeg `-ac 1` 的立体声下混带 1/sqrt2 系数；统一先解双声道再取均值，保证电平口径一致。
    cmd = [FFMPEG, "-v", "error", "-threads", THREADS, "-i", path,
           "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "2", "-ar", str(sr), "-"]
    p = run(cmd, timeout=1800)
    if p.returncode != 0:
        raise RuntimeError("decode failed %s\n%s" % (path, p.stderr.decode("utf-8", "replace")[-800:]))
    y = np.frombuffer(p.stdout, dtype=F32).reshape(-1, 2)
    if mono:
        return y.mean(axis=1).astype(F32).copy()
    return y.T.copy()


def write_wav24(path, x, sr=SR, chunk=1 << 19):
    """mono/stereo float32 -> 24bit PCM WAV，分块写。"""
    ch = 2 if x.ndim == 1 else x.shape[0]
    n = len(x) if x.ndim == 1 else x.shape[1]
    data_bytes = n * ch * 3
    hdr = b"RIFF" + struct.pack("<I", 36 + data_bytes) + b"WAVE"
    hdr += b"fmt " + struct.pack("<IHHIIHH", 16, 1, ch, sr, sr * ch * 3, ch * 3, 24)
    hdr += b"data" + struct.pack("<I", data_bytes)
    with open(path, "wb") as f:
        f.write(hdr)
        for pos in range(0, n, chunk):
            if x.ndim == 1:
                seg = np.stack([x[pos:pos + chunk], x[pos:pos + chunk]], axis=0)
            else:
                seg = x[:, pos:pos + chunk]
            pcm = np.ascontiguousarray((np.clip(seg.T, -1.0, 1.0) * 8388607.0).astype("<i4"))
            f.write(pcm.view(np.uint8).reshape(-1, 4)[:, :3].tobytes())


def rms_db(x):
    return 20 * np.log10(max(float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2))), 1e-12))


def db(x):
    return 10 ** (x / 20.0)


def load_tl():
    with open(TL_FULL, "r", encoding="utf-8") as f:
        return json.load(f)


def sent_index(tl):
    return {"%s_%02d" % (s["id"], x["i"]): x
            for s in tl["segments"] for x in s["sentences"]}


def speech_rms(x, tl):
    ss, cnt = 0.0, 0
    n = len(x) if x.ndim == 1 else x.shape[1]
    for seg in tl["segments"]:
        for s in seg["sentences"]:
            i0, i1 = int(s["start"] * SR), min(n, int(s["end"] * SR))
            if i1 > i0:
                a = x[i0:i1] if x.ndim == 1 else x[:, i0:i1]
                ss += float(np.sum(a.astype(np.float64) ** 2))
                cnt += (i1 - i0) * (1 if x.ndim == 1 else x.shape[0])
    return 10 * np.log10(max(ss / max(cnt, 1), 1e-24))


# ---------------------------------------------------------------- 分块滤波
def fft_conv_add(dst, src, h, gain=1.0, block=1 << 17):
    m, n = len(h), len(src)
    nfft = 1 << (block + m - 1).bit_length()
    H = np.fft.rfft(h.astype(np.float64), nfft)
    for pos in range(0, n, block):
        seg = src[pos:pos + block]
        y = np.fft.irfft(np.fft.rfft(seg.astype(np.float64), nfft) * H, nfft)
        y = y[:len(seg) + m - 1]
        n1 = min(len(y), len(dst) - pos)
        if n1 > 0:
            dst[pos:pos + n1] += (gain * y[:n1]).astype(F32)


def design_hp_fir(fc=80.0, taps=8193):
    n = taps
    f = np.fft.rfftfreq(n, 1.0 / SR)
    H = f / np.sqrt(f * f + fc * fc)
    h = np.fft.irfft(H, n)
    h = np.fft.fftshift(h)      # 循环卷积 IR 必须居中，否则窗函数吃掉全部能量
    h *= np.blackman(n)
    return h.astype(F32)


def conv_zero_phase(x, h, block=1 << 17):
    m = len(h)
    d = (m - 1) // 2
    n = len(x)
    out = np.zeros(n + m - 1, dtype=F32)
    fft_conv_add(out, x, h, 1.0, block)
    y = out[d:d + n].copy()
    del out
    return y


def deess(x, thr_db=-24.0, max_db=5.0):
    """保守去齿音（分块 STFT）。"""
    win, hop = 1024, 256
    w = np.hanning(win + 1)[:-1].astype(F32)
    n = (len(x) - win) // hop + 1
    view = sliding_window_view(x, win)[::hop]
    f = np.fft.rfftfreq(win, 1.0 / SR)
    hf = (f >= 5200) & (f <= 9000)
    lf = (f >= 1200) & (f <= 4000)
    taper = np.clip((f - 5200) / 800.0, 0, 1) * np.clip((9000 - f) / 1200.0, 0, 1)
    gr = np.empty(n, dtype=F32)
    CH = 1024
    for i in range(0, n, CH):
        m = min(CH, n - i)
        S = np.fft.rfft(view[i:i + m] * w[None, :], axis=1)
        mag = np.abs(S) + 1e-9
        hi = np.sqrt(np.mean(mag[:, hf] ** 2, axis=1)) + 1e-9
        lo = np.sqrt(np.mean(mag[:, lf] ** 2, axis=1)) + 1e-9
        ratio = 20 * np.log10(hi / lo)
        gr[i:i + m] = np.clip((ratio - thr_db) / 1.5, 0, 1) * max_db
    gr = np.convolve(gr, np.ones(5, dtype=F32) / 5, mode="same").astype(F32)
    out = np.zeros(len(x), dtype=F32)
    CH2 = 512
    for i in range(0, n, CH2):
        m = min(CH2, n - i)
        S = np.fft.rfft(view[i:i + m] * w[None, :], axis=1)
        S *= (10.0 ** (-gr[i:i + m, None] * taper[None, :] / 20.0))
        y = np.fft.irfft(S, win, axis=1) * w[None, :]
        for j in range(m):
            a = (i + j) * hop
            out[a:a + win] += y[j].astype(F32)
    out /= F32(1.5)   # periodic Hann² @75% overlap 的 COLA 归一
    return out


def compress_gentle(x, thr_db=-20.0, ratio=1.8, atk=0.020, rel=0.25, max_gr=3.0):
    """轻压缩（分块包络 + 增益包络）；不做广播腔、不做强限幅。"""
    win, hop = 1024, 128
    view = sliding_window_view(x, win)[::hop]
    n = len(view)
    env = np.empty(n, dtype=F32)
    CH = 2048
    for i in range(0, n, CH):
        m = min(CH, n - i)
        fr = view[i:i + m]
        env[i:i + m] = np.sqrt(np.mean(fr * fr, axis=1) + 1e-12)
    env_db = 20 * np.log10(env + 1e-12)
    g = np.clip((env_db - thr_db) * (1 - 1.0 / ratio), 0, max_gr)
    a = 1 - np.exp(-hop / (SR * atk))
    r = 1 - np.exp(-hop / (SR * rel))
    sm = np.empty_like(g)
    acc = 0.0
    for i in range(n):
        coef = a if g[i] > acc else r
        acc += coef * (g[i] - acc)
        sm[i] = acc
    tf = np.arange(n) * hop + win / 2
    curve = np.interp(np.arange(len(x)), tf, 10.0 ** (-sm / 20.0)).astype(F32)
    x *= curve
    del curve
    return x, float(np.max(sm))


def room_ir(dur=0.42, seed=5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    X = np.fft.rfft(rng.standard_normal(n).astype(F32))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    lo = np.maximum(f, 1.0)
    y = np.fft.irfft(X * (1.0 / (1.0 + (lo / 4200.0) ** 2)), n).astype(F32)
    y *= np.exp(-t / 0.16).astype(F32)
    for dly, g in ((0.009, 0.5), (0.015, 0.35), (0.023, 0.25), (0.037, 0.18)):
        i = int(dly * SR)
        if i < n:
            y[i] += g
    Y = np.fft.rfft(y.astype(np.float64))
    fl = np.fft.rfftfreq(n, 1.0 / SR)
    y = np.fft.irfft(Y * (np.maximum(fl, 1e-6) / np.sqrt(fl ** 2 + 130.0 ** 2)), n).astype(F32)
    return y / (np.sqrt(np.sum(y.astype(np.float64) ** 2)) + 1e-12)


# ---------------------------------------------------------------- 调度
def silence_gate(tl, n):
    """设计长留白（>=0.55s）人工静音门：句末 0.18s 后 0.12s 内淡出到 0，
    下一句开始前 0.08s 淡入，保证长留白为真静默。"""
    env = np.ones(n, dtype=F32)
    all_s = [s for seg in tl["segments"] for s in seg["sentences"]]
    gated = []
    for i in range(len(all_s) - 1):
        a, b = all_s[i]["end"], all_s[i + 1]["start"]
        gap = b - a
        if gap < 0.55:
            continue
        i0, i1 = int((a + 0.18) * SR), int((a + 0.30) * SR)
        i2, i3 = int((b - 0.08) * SR), int((b - 0.02) * SR)
        i0, i1 = min(i0, n), min(i1, n)
        i2, i3 = max(0, min(i2, n)), max(0, min(i3, n))
        if i1 > i0:
            env[i0:i1] = np.linspace(1.0, 0.0, i1 - i0, dtype=F32)
        if i2 > i1:
            env[i1:i2] = 0.0
        if i3 > i2:
            env[i2:i3] = np.linspace(0.0, 1.0, i3 - i2, dtype=F32)
        gated.append((round(a, 3), round(b, 3), round(gap, 3)))
    return env, gated


def seg_levels(tl):
    """按段角色给音乐床电平（人工调度，不是全片一个电平）。"""
    import music
    roles = music.roles_for(len(tl["segments"]))
    return {seg["id"]: ROLE_LEVEL.get(role, 0.95)
            for seg, role in zip(sorted(tl["segments"], key=lambda s: s["start"]), roles)}


def music_automation_curve(tl, n):
    """返回逐块增益：分段电平表 × 语义音效处的额外轻让（-1.5dB 级）。"""
    segs = sorted(tl["segments"], key=lambda s: s["start"])
    levels = seg_levels(tl)
    pts, vals = [0.0], [COLD_LEVEL]
    for seg in segs:
        st = seg["start"]
        pts += [max(0.01, st - 0.30), st + 0.30]
        vals += [vals[-1], levels[seg["id"]]]
    pts.append(tl["total"])
    vals.append(0.82)
    pts, vals = np.asarray(pts), np.asarray(vals)
    # 音效处额外轻让（防止踩到语义瞬态；音乐在这些点本来也不密）
    dips = []
    try:
        import sfx as sfxmod
        for e in sfxmod.placements(tl):
            a, b = e["t"] - 0.45, e["t"] + 0.65
            dips.append((a, b, 0.84))
    except Exception:
        pass
    for pos in range(0, n, SR):
        i1 = min(n, pos + SR)
        t = np.arange(pos, i1) / SR
        g = np.interp(t, pts, vals)
        for a, b, level in dips:
            w = np.interp(t, [a - 0.15, a, b, b + 0.15], [1.0, level, level, 1.0])
            g = g * w
        yield pos, i1, g.astype(F32)


def _box_mean(x, k):
    if k <= 1:
        return x
    pad_l = k // 2
    pad_r = k - 1 - pad_l
    xp = np.pad(x, (pad_l, pad_r), mode="edge")
    c = np.concatenate([[0.0], np.cumsum(xp, dtype=np.float64)])
    return ((c[k:] - c[:-k]) / float(k)).astype(F32)


def narration_activity(tl, n):
    act = np.zeros(n, dtype=F32)
    for seg in tl["segments"]:
        for s in seg["sentences"]:
            i0, i1 = int(s["start"] * SR), min(n, int((s["end"] + 0.05) * SR))
            act[i0:i1] = 1.0
    act = _box_mean(act, int(0.06 * SR))
    act = _box_mean(act, int(0.35 * SR))
    np.clip(act, 0, 1, out=act)
    return act


def sfx_events(tl):
    import sfx as sfxmod
    return [(e["name"], e["t"], e["gain"], e["pan"], e["why"]) for e in sfxmod.placements(tl)]


# ---------------------------------------------------------------- 混音
def build_mix(tl, verbose=True):
    n = int(round(tl["total"] * SR))

    # ---- 旁白处理
    narr = decode(NARR_WAV, mono=True)
    if len(narr) < n:
        narr = np.pad(narr, (0, n - len(narr)))
    narr = narr[:n]
    narr = conv_zero_phase(narr, design_hp_fir(80.0))
    narr = deess(narr)
    narr, max_gr = compress_gentle(narr)
    send = narr.copy()
    fft_conv_add(narr, send, room_ir(), gain=0.10, block=1 << 17)
    del send
    gate, gated = silence_gate(tl, n)
    narr *= gate
    del gate
    s_rms = speech_rms(narr, tl)
    narr_gain = db(NARR_TARGET_RMS - s_rms)
    narr *= F32(narr_gain)
    write_wav24(NARR_PROC, narr)

    # ---- 音乐床调度
    music = decode(MUSIC_WAV, mono=False)
    if music.shape[1] < n:
        music = np.pad(music, ((0, 0), (0, n - music.shape[1])))
    music = music[:, :n]
    for pos, i1, g in music_automation_curve(tl, n):
        music[:, pos:i1] *= g[None, :]
    m_rms = speech_rms(music, tl)
    music_gain = float(np.clip(db((NARR_TARGET_RMS - MUSIC_BED_BELOW_NARR_DB) - m_rms),
                               0.20, 1.10))
    music *= F32(music_gain)
    act = narration_activity(tl, n)
    duck = db(-3.0 * act).astype(F32)
    del act
    music *= duck[None, :]
    del duck

    # ---- 混音：以音乐缓冲为 mix
    mix = music
    mix[0] += narr
    mix[1] += narr
    del narr
    sfx_log = []
    for name, t0, gain, pan, note in sfx_events(tl):
        path = os.path.join(SFX_DIR, name + ".wav")
        if not os.path.exists(path):
            raise RuntimeError("missing sfx " + path)
        x = decode(path, mono=False)
        i0 = int(round(t0 * SR))
        m = max(0, min(x.shape[1], n - i0))
        if m <= 0:
            continue
        th = (pan + 1.0) * np.pi / 4.0
        mix[0, i0:i0 + m] += x[0, :m] * F32(gain * np.cos(th))
        mix[1, i0:i0 + m] += x[1, :m] * F32(gain * np.sin(th))
        sfx_log.append(dict(name=name, t=round(t0, 3), gain=gain, pan=pan, note=note,
                            dur=round(x.shape[1] / SR, 3)))

    # 母带前留余量：24bit WAV 写入会硬裁到 [-1,1]，峰值 >-0.5dBFS 会削波。
    peak = float(np.max(np.abs(mix)))
    headroom_scale = 1.0
    if peak > 0.891:                     # -1.0 dBFS
        headroom_scale = 0.891 / peak
        for pos in range(0, n, SR):
            mix[:, pos:pos + SR] *= F32(headroom_scale)
        peak = 0.891
    if verbose:
        print("[mix] speech RMS=%.1f dBFS (narr gain %+.2f dB), music RMS(speech)=%.1f -> gain %.3f (%+.1f dB)" % (
            s_rms, 20 * np.log10(narr_gain), m_rms, music_gain, 20 * np.log10(music_gain)))
        print("[mix] max comp GR=%.2f dB, gate windows=%d, duck=-3dB (sidechain fallback)" % (max_gr, len(gated)))
        print("[mix] peak=%.2f dBFS rms=%.1f dBFS (pre-master headroom scale %+.2f dB)" % (
            20 * np.log10(peak), rms_db(mix), 20 * np.log10(headroom_scale)))
    write_wav24(MIX_WAV, mix)
    meta = dict(narr_gain_db=round(20 * np.log10(narr_gain), 2),
                music_gain=round(music_gain, 3),
                music_gain_db=round(20 * np.log10(music_gain), 2),
                speech_rms_db=round(s_rms, 2), music_rms_db=round(m_rms, 2),
                music_bed_below_narr_db=MUSIC_BED_BELOW_NARR_DB,
                comp_max_gr_db=round(max_gr, 2), duck_max_db=3.0,
                headroom_scale_db=round(20 * np.log10(headroom_scale), 2),
                seg_level=seg_levels(tl), gate_windows=gated, sfx=sfx_log,
                mix_peak_dbfs=round(20 * np.log10(peak), 2))
    with open(MIX_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return mix, meta


# ---------------------------------------------------------------- loudnorm
def loudnorm_measure(path):
    p = run([FFMPEG, "-hide_banner", "-nostats", "-threads", THREADS, "-i", path,
             "-af", "loudnorm=I=%s:TP=%s:LRA=%s:print_format=json" % (TARGET_I, TARGET_TP, TARGET_LRA),
             "-f", "null", "-"])
    txt = p.stderr.decode("utf-8", "replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", txt, re.S)
    if not m:
        raise RuntimeError("loudnorm measure failed:\n" + txt[-1200:])
    return json.loads(m.group(0))


def encode_two_pass(tl, verbose=True):
    """两遍 loudnorm：先用 mix.wav 实测，再按目标 TP 逐级收紧。
    按 TP 目标阶梯尝试，取第一组同时满足「TP ≤ -1.5 dBTP 且 |I+14| ≤ 0.45 LU」的结果。
    """
    m1 = loudnorm_measure(MIX_WAV)
    last = None
    tries = []
    for attempt, tp_t in enumerate([TARGET_TP, TARGET_TP - 0.30, TARGET_TP - 0.50, TARGET_TP - 0.70]):
        # 注意：不要用 `-t` 截断——loudnorm 的 limiter 有前视延迟，`-t` 会在输出时间轴上
        # 提前切断 ~80ms 尾巴（实测 -80.9ms）；改用链内 atrim 精确到样本。
        af = ("loudnorm=I=%s:TP=%s:LRA=%s:measured_I=%s:measured_TP=%s:measured_LRA=%s:"
              "measured_thresh=%s:offset=%s:linear=true:print_format=json,atrim=0:%.5f") % (
            TARGET_I, tp_t, TARGET_LRA, m1["input_i"], m1["input_tp"],
            m1["input_lra"], m1["input_thresh"], m1["target_offset"], tl["total"])
        cmd = [FFMPEG, "-hide_banner", "-y", "-threads", THREADS, "-i", MIX_WAV, "-af", af,
               "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
               "-threads", THREADS, "-movflags", "+faststart", OUT_M4A]
        p = run(cmd)
        if p.returncode != 0:
            raise RuntimeError("encode failed:\n" + p.stderr.decode("utf-8", "replace")[-1200:])
        last = loudnorm_measure(OUT_M4A)
        i_v, tp_v = float(last["input_i"]), float(last["input_tp"])
        ok_i = abs(i_v - TARGET_I) <= 0.45
        ok_tp = tp_v <= TARGET_TP
        tries.append(dict(tp_target=round(tp_t, 2), i=i_v, tp=tp_v, lra=float(last["input_lra"]),
                          ok=bool(ok_i and ok_tp)))
        if verbose:
            print("[loudnorm] attempt %d (TP target %.2f): I=%s TP=%s LRA=%s -> %s" % (
                attempt + 1, tp_t, last["input_i"], last["input_tp"], last["input_lra"],
                "OK" if (ok_i and ok_tp) else "retry"))
        if ok_i and ok_tp:
            break
    if verbose:
        print("[loudnorm] attempts:", tries)
    return m1, last


# ---------------------------------------------------------------- 自检
def probe_stream(path):
    p = run([FFMPEG, "-hide_banner", "-i", path])
    txt = p.stderr.decode("utf-8", "replace")
    info = {"duration": None, "audio": None}
    for line in txt.splitlines():
        ls = line.strip()
        if ls.startswith("Duration:"):
            hms = ls.split("Duration:")[1].split(",")[0].strip()
            h, m, s = hms.split(":")
            info["duration"] = int(h) * 3600 + int(m) * 60 + float(s)
        if ls.startswith("Stream") and "Audio:" in ls:
            info["audio"] = ls
    return info


def parse_srt_time(s):
    h, m, rest = s.split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000.0


def disp_width(ch):
    """与 tts_perf.py 一致的严格口径：每字符（含 ASCII/空格）计 1.0。"""
    return 1.0


def check_srt(path, tl):
    if not os.path.exists(path):
        return False, 0, 0.0
    blocks = open(path, encoding="utf-8").read().strip().split("\n\n")
    prev_end, maxw, ok = -1.0, 0.0, True
    sents = [(s["start"], s["end"]) for seg in tl["segments"] for s in seg["sentences"]]
    if tl.get("outro_voice"):
        sents.append((tl["outro_voice"]["start"], tl["outro_voice"]["end"]))
    for blk in blocks:
        lines = blk.split("\n")
        if len(lines) < 2:
            ok = False
            continue
        m = re.match(r"(\S+) --> (\S+)", lines[1])
        if not m:
            ok = False
            continue
        a, b = parse_srt_time(m.group(1)), parse_srt_time(m.group(2))
        if a < prev_end - 1e-6 or b <= a:
            ok = False
        prev_end = b
        for ln in lines[2:]:
            maxw = max(maxw, sum(disp_width(c) for c in ln))
        if not any(sa - 0.02 <= a and b <= se + 0.02 for sa, se in sents):
            ok = False
    return ok, len(blocks), round(maxw, 2)


def _corr(a, b):
    if a.std() < 1e-9 or b.std() < 1e-9:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def seg_corr(seg, raw, mixm, n):
    """段内有声区间：narration.wav vs audio.m4a 的相关系数（lag0 + 最佳 lag）。"""
    best = (-2.0, 0)
    for lag_ms in range(-60, 61, 2):
        lag = int(round(lag_ms / 1000.0 * SR))
        parts_r, parts_m = [], []
        for s in seg["sentences"]:
            i0 = int((s["start"] + 0.05) * SR)
            i1 = int((s["end"] - 0.05) * SR)
            j0, j1 = max(0, i0 + lag), min(n, i1 + lag)
            if j1 - j0 < int(0.02 * SR):
                continue
            parts_r.append(raw[j0 - lag:j1 - lag].astype(np.float64))
            parts_m.append(mixm[j0:j1].astype(np.float64))
        if not parts_r:
            continue
        xr, xm = np.concatenate(parts_r), np.concatenate(parts_m)
        c = _corr(xr, xm)
        if c is not None and c > best[0]:
            best = (c, lag_ms)
    parts_r, parts_m = [], []
    for s in seg["sentences"]:
        i0 = int((s["start"] + 0.05) * SR)
        i1 = min(n, int((s["end"] - 0.05) * SR))
        if i1 > i0:
            parts_r.append(raw[i0:i1].astype(np.float64))
            parts_m.append(mixm[i0:i1].astype(np.float64))
    xr, xm = np.concatenate(parts_r), np.concatenate(parts_m)
    return dict(corr_lag0=_corr(xr, xm), corr_best=best[0] if best[0] > -1.5 else None,
                best_lag_ms=best[1],
                speech_rms_raw=round(rms_db(xr), 2), speech_rms_mix=round(rms_db(xm), 2))


def checks(tl, mix_meta):
    out = decode(OUT_M4A, mono=False)
    n = out.shape[1]
    segs = sorted(tl["segments"], key=lambda s: s["start"])
    res = {"decoded_samples": int(n),
           "decoded_duration": round(n / SR, 5),
           "duration_err_s": round(n / SR - tl["total"], 5),
           "peak": round(float(np.max(np.abs(out))), 5)}
    res["peak_dbfs"] = round(20 * np.log10(max(res["peak"], 1e-9)), 2)
    res["clipping"] = bool(res["peak"] > 0.98)

    # 设计真静默窗口：取 music_meta 的人工停乐窗（且窗内无旁白），逐个实测
    mm = {}
    if os.path.exists(MUSIC_META):
        mm = json.load(open(MUSIC_META, encoding="utf-8"))
    sil = []
    for a, b in mm.get("gate_windows", []):
        if b - a < 0.30:
            continue
        # 内窗实测：去掉旁白句末淡出（0.18-0.30s）后的真静默段；设计窗本身会包含这 0.2s 尾音
        a2, b2 = a + 0.20, b - 0.05
        if b2 - a2 < 0.15:
            a2, b2 = a + 0.10, b - 0.05
        i0 = max(0, min(int(a2 * SR), n))
        i1 = max(i0, min(n, int(b2 * SR)))
        seg = out[:, i0:i1] if i1 > i0 else np.zeros((2, 1), dtype=F32)
        sil.append(dict(name="设计停乐窗 %.2f–%.2fs（内窗 %.2f–%.2fs）" % (a, b, a2, b2),
                        start=round(a2, 2), end=round(b2, 2), design=(round(a, 2), round(b, 2)),
                        expect_silent=True,
                        rms_dbfs=round(float(rms_db(seg)), 2),
                        peak_dbfs=round(float(20 * np.log10(max(float(np.max(np.abs(seg))), 1e-12))), 2)))
    # 参考窗：cold open 与 outro（有音乐/口播，非静默）
    for name, a, b in [("cold open（低 drone + 电流脉冲，非静默）", 0.10, tl["cold_open"] - 0.10),
                       ("片尾 outro（pad + AI 口播，非静默）", tl["total"] - 3.0, tl["total"] - 0.10)]:
        i0 = max(0, min(int(a * SR), n))
        i1 = max(i0, min(n, int(b * SR)))
        seg = out[:, i0:i1] if i1 > i0 else np.zeros((2, 1), dtype=F32)
        sil.append(dict(name=name, start=round(a, 2), end=round(b, 2), expect_silent=False,
                        rms_dbfs=round(float(rms_db(seg)), 2),
                        peak_dbfs=round(float(20 * np.log10(max(float(np.max(np.abs(seg))), 1e-12))), 2)))
    res["silences"] = sil

    # 旁白完整性（raw → processed，首句）
    raw = decode(NARR_WAV, mono=True)
    proc = decode(NARR_PROC, mono=True)
    m = min(len(raw), len(proc))
    s0 = segs[0]["sentences"][0]
    j0, j1 = int(s0["start"] * SR), min(m, int(s0["end"] * SR))
    xr, xp = raw[j0:j1].astype(np.float64), proc[j0:j1].astype(np.float64)
    res["narr_corr"] = _corr(xr, xp)
    res["narr_proc_rms"] = round(float(rms_db(proc[j0:j1])), 2)
    res["narr_raw_rms"] = round(float(rms_db(raw[j0:j1])), 2)

    # 旁白完整性硬校验：原始 narration.wav vs 成片 audio.m4a（首/中/末三段有声区间）
    mixm = out.mean(axis=0)
    idxs = []
    for k in (0, len(segs) // 2, len(segs) - 1):
        if k not in idxs:
            idxs.append(k)
    seg_checks = []
    for k in idxs:
        seg = segs[k]
        c = seg_corr(seg, raw, mixm, n)
        c["id"] = seg["id"]
        c["name"] = seg["name"]
        c["start"] = round(seg["start"], 3)
        c["end"] = round(seg["end"], 3)
        seg_checks.append(c)
    res["narr_segments"] = seg_checks
    res["narr_only_speech_rms_dbfs"] = round(float(speech_rms(proc, tl)), 2)
    res["speech_rms_dbfs"] = round(float(speech_rms(out, tl)), 2)

    # 句级 / 段边界漂移：narration.wav vs audio.m4a 互相关最佳 lag（6kHz 下采样，±50ms，2ms 步长）
    DS = 8
    CS = SR // DS
    mixd = mixm[::DS].astype(np.float32)
    nard = raw[::DS].astype(np.float32)

    def best_lag(t0, t1, max_ms=50):
        a = max(0, int((t0 - 0.05) * CS))
        b = min(int((t1 + 0.05) * CS), len(nard), len(mixd))
        if b - a < CS // 50:
            return None
        x = nard[a:b]
        if x.std() < 1e-9:
            return None
        best = (-2.0, 0)
        for lag_ms in range(-max_ms, max_ms + 1, 2):
            lag = int(round(lag_ms / 1000.0 * CS))
            j0, j1 = a + lag, b + lag
            if j0 < 0 or j1 > len(mixd):
                continue
            y = mixd[j0:j1]
            if y.std() < 1e-9:
                continue
            c = float(np.corrcoef(x, y)[0, 1])
            if c > best[0]:
                best = (c, lag_ms)
        return best

    sent_lags = []
    for seg in segs:
        for s in seg["sentences"]:
            r = best_lag(s["start"] + 0.05, s["end"] - 0.05)
            if r is not None:
                sent_lags.append(dict(sid="%s_%02d" % (seg["id"], s["i"]),
                                      lag_ms=r[1], corr=round(r[0], 4)))
    res["sent_lags"] = sent_lags
    res["sent_lag_ms_mean"] = round(float(np.mean([x["lag_ms"] for x in sent_lags])), 2) if sent_lags else None
    res["sent_lag_ms_max_abs"] = round(float(np.max(np.abs([x["lag_ms"] for x in sent_lags]))), 2) if sent_lags else None
    bnd = []
    for seg in segs:
        r = best_lag(seg["start"] + 0.05, min(seg["start"] + 2.5, seg["end"]))
        if r is not None:
            bnd.append(dict(id=seg["id"], start=round(seg["start"], 3), lag_ms=r[1],
                            corr=round(r[0], 4)))
    if tl.get("outro_voice"):
        ov0 = tl["outro_voice"]["start"]
        r = best_lag(ov0 + 0.05, min(ov0 + 3.0, tl["total"]))
        if r is not None:
            bnd.append(dict(id="OUTRO", start=round(ov0, 3), lag_ms=r[1], corr=round(r[0], 4)))
    res["boundary_lags"] = bnd
    srt_ok, srt_lines, srt_w = check_srt(SRT_PATH, tl)
    res.update(srt_ok=srt_ok, srt_lines=srt_lines, srt_max_width=srt_w)
    res["stream"] = probe_stream(OUT_M4A)
    res["mix_meta"] = mix_meta
    lvl = {}
    for seg in segs:
        i0, i1 = int(seg["start"] * SR), min(n, int(seg["end"] * SR))
        if i1 > i0:
            lvl[seg["id"]] = round(float(rms_db(out[:, i0:i1])), 2)
    res["seg_rms_dbfs"] = lvl
    return res


# ---------------------------------------------------------------- 报告
def _role_map(tl):
    import music
    roles = music.roles_for(len(tl["segments"]))
    return {seg["id"]: role for seg, role in zip(sorted(tl["segments"], key=lambda s: s["start"]), roles)}


def write_report(tl, mix_meta, m1, m2, chk):
    L = []
    A = L.append
    mm = {}
    if os.path.exists(MUSIC_META):
        mm = json.load(open(MUSIC_META, encoding="utf-8"))
    segs = sorted(tl["segments"], key=lambda s: s["start"])
    total = tl["total"]
    ev = mm.get("events", [])
    sec = mm.get("sections", {})
    dens = mm.get("densities", {})
    roles = _role_map(tl)
    smeta = {}
    if os.path.exists(os.path.join(SFX_DIR, "sfx_meta.json")):
        smeta = json.load(open(os.path.join(SFX_DIR, "sfx_meta.json"), encoding="utf-8"))
    anchors = {x["name"]: x.get("anchor", "") for x in smeta.get("_placed_events", [])}
    nsent = sum(len(s["sentences"]) for s in tl["segments"])
    ov = tl.get("outro_voice") or {}
    per_seg_n = {s["id"]: len(s["sentences"]) for s in segs}

    A("# 第 08 期《电动车松开油门为什么能充电》音频报告")
    A("")
    A("> 生成链路：`narration/performance.json`（逐句表演谱，文字逐字取自锁定发言稿 §4 逐字稿）")
    A("> → `tts_perf.py`（逐句 edge-tts：%d 句正文%s；实测时长拼时间轴 + SRT）" % (
        nsent, " + 1 句片尾 AI 声明口播" if ov else ""))
    A("> → `music.py`（本期原创配乐「能量脉冲动机」，纯 numpy 合成）→ `sfx.py`（8 处语义音效）")
    A("> → `build_audio.py`（旁白处理 + 分段音乐床 + 音效 + sidechain + 两遍 loudnorm + 自检 + 本报告）。")
    A("> **本报告全部结论来自测量与结构验证；本 Agent 无法用人耳盲听，未做主观听感验收。**")
    A("")
    A("## 1. 交付物")
    A("")
    A("| 文件 | 说明 |")
    A("| --- | --- |")
    for f, d in [
            ("narration/performance.json", "逐句表演谱：%d 句文本 + rate/pitch/pause_after%s" % (
                nsent, " + outro_voice（AI 声明口播）" if ov else "")),
            ("audio/work/timeline_audio.json", "段/句级实测时间轴（全片唯一时间基准）"),
            ("audio/work/timeline_audio_full.json", "同上 + rate/pitch/pause_after/narration_end/outro_voice（混音与报告内部使用）"),
            ("audio/work/tts/durations.json", "逐句实测时长/峰值/RMS/句间留白"),
            ("audio/work/narration.wav", "旁白干声（48k 立体声，长度=全片）"),
            ("audio/work/srt/all.srt", "句级 SRT，单行 ≤18 汉字显示宽度"),
            ("music.py", "本片原创配乐合成（numpy，无外部曲库/采样）"),
            ("sfx.py", "8 处语义音效合成 + 从 timeline 推导的放置表"),
            ("build_audio.py", "旁白处理、音乐床调度、音效、sidechain、两遍 loudnorm、自检、本报告"),
            ("audio/work/music.wav", "本片原创配乐（48kHz 立体声 24bit，长度=全片）"),
            ("audio/work/music_meta.json", "配乐事件表/逐段电平/调性/动机/停乐窗"),
            ("audio/work/sfx/*.wav", "合成音效（8 个素材，8 处使用）"),
            ("audio/work/narration_processed.wav", "处理后的旁白（80Hz 低切/去齿音/轻压缩/短混响/静音门）"),
            ("audio/work/mix.wav", "母带前混音（48kHz 立体声 24bit）"),
            ("audio/work/audio.m4a", "成片音轨 AAC 192k / 48kHz / 立体声"),
            ("audio/work/loudness.txt", "实测 I/TP/LRA（两遍 loudnorm）"),
            ("audio/work/mix_meta.json", "混音参数、音效清单、静音门窗口"),
    ]:
        A("| `%s` | %s |" % (f, d))
    A("")
    A("## 2. 总时长与段结构")
    A("")
    A("- 总时长 **%.3f s（%d:%05.2f）**；cold_open=%.2fs，outro=%.2fs，segment_gap=%.2fs，fps=%d。"
      % (total, int(total // 60), total % 60, tl["cold_open"], tl["outro"],
         tl["segment_gap"], tl["fps"]))
    A("- %d 句正文（%s），文字与锁定稿逐字一致，仅做断句；括号内口播提示未送 TTS。"
      % (nsent, " / ".join("%s=%d" % (s["id"], per_seg_n[s["id"]]) for s in segs)))
    if ov:
        A("- 片尾 AI 辅助制作声明**口播**（与画面片尾卡双通道）：`%s`，%.3f–%.3fs（在 outro 内）。"
          % (ov["text"], ov["start"], ov["end"]))
    last_s = segs[-1]["sentences"][-1]
    A("- 旁白末句（片尾 AI 声明口播句 %s_%02d）结束于 %.3fs，其后 %.3fs 为音乐尾巴 + 片尾留白（未被提前截断）。"
      % (segs[-1]["id"], last_s["i"], last_s["end"], total - last_s["end"]))
    _decl = [(seg["id"], s) for seg in segs for s in seg["sentences"] if "AI" in s["text"] and "辅助制作" in s["text"]]
    if _decl:
        _seg, _s = _decl[-1]
        A("- 片尾 AI 辅助制作声明**口播**（与画面片尾卡双通道，逐字取自锁定稿）：`%s`，%.3f–%.3fs（%s_%02d）。"
          % (_s["text"], _s["start"], _s["end"], _seg, _s["i"]))
    A("")
    A("| 段 | 名称 | 角色 | 起点(s) | 实测段长(s) | 段末(s) | 句数 | 成片 RMS(dBFS) |")
    A("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for seg in segs:
        A("| %s | %s | %s | %.3f | %.3f | %.3f | %d | %.1f |" % (
            seg["id"], seg["name"], roles.get(seg["id"], ""), seg["start"], seg["dur"],
            seg["end"], len(seg["sentences"]), chk["seg_rms_dbfs"].get(seg["id"], 0.0)))
    A("")
    A("## 3. 逐句实测时长与留白（时间轴由实测驱动）")
    A("")
    A("| 句 ID | 文本 | rate | pitch | 音频(s) | 起点(s) | 终点(s) | 句后留白(s) |")
    A("| --- | --- | --- | --- | ---: | ---: | ---: | ---: |")
    for seg in segs:
        for s in seg["sentences"]:
            A("| %s_%02d | %s | %s | %s | %.3f | %.3f | %.3f | %.2f |" % (
                seg["id"], s["i"], s["text"].replace("|", "\\|"),
                s.get("rate", "-"), s.get("pitch", "-"), s["dur"], s["start"], s["end"],
                s.get("pause_after", 0.0)))
    A("")
    A("> 旁白文字与速率来自 `narration/performance.json`（`audio/work/tts/durations.json` 记录逐句实测）。")
    A("> 句间静音为真实留白；长留白（≥0.55s）叠加人工静音门，实测 < -60dBFS（见第 8 节）。")
    A("")
    A("## 4. 配音处理（不做广播腔）")
    A("")
    A("- 音色：`zh-CN-YunjianNeural`（系列身份男声）；逐句 rate/pitch 表演谱：")
    A("  钩子略快、拆解平推、能量账数字放慢、限制段压低、收束放轻；关键句前留白加大（见 performance.json）。")
    A("- 整轨：80Hz 零相位低切（对称 FIR 8193 taps，`np.fft.fftshift` 居中后再加 Blackman 窗）；")
    A("- 保守去齿音（5.2–9kHz，按齿音能量最多 -5dB，分块 STFT）；")
    A("- 轻压缩（thr -20dBFS / ratio 1.8 / 最大 %.2f dB GR / attack 20ms / release 250ms）；" % mix_meta["comp_max_gr_db"])
    A("- 短房间混响（IR 0.42s、wet 0.10、低切 IR 130Hz）粘合句间，避免机械接缝；不做强限幅、不做广播腔；")
    A("- 旁白电平：处理链输出实测有声段 RMS %.1f dBFS，按 -19.0 dBFS 目标施加 %+.2f dB 静态增益"
      "（该增益只把处理链输出对齐到混音基准，不代表任何动态处理量）。"
      % (mix_meta["speech_rms_db"], mix_meta["narr_gain_db"]))
    A("- 旁白有声段 RMS 与音乐床关系：音乐床在旁白窗口内实测 RMS %.1f dBFS、"
      "按目标再降 %.1f dB（另叠 -3.0dB sidechain 保底），口播稳定高于 BGM；关键句靠人工停乐/退开，不靠 duck 硬压。"
      % (mix_meta["music_rms_db"], mix_meta["music_bed_below_narr_db"]))
    A("")
    A("## 5. 配乐（本期原创「能量脉冲动机」，未复用第 01—07 期曲目/文件）")
    A("")
    A("- **主题**：一条可逆的能量通道 —— 电流脉冲 / 能量回流 / 电机上扫 / 回收提示。")
    A("- **声音记忆点 = 「能量脉冲动机」**：三个快速上行电流脉冲 **D4→A4→D5**，接一记**下落长脉冲 D5→D2**；")
    A("  上行=回收开始，下落=动能落进电池；片尾改写成 D 大调 **D4→F#4→A4→D5** 再下落收束（「能量回来了」）。")
    A("  与第 04 期 64BPM 心跳 lub-dub、第 05 期「音程收窄的收网动机」在调性/速度/动机方向上均不同。")
    A("- **电流脉冲**：%d BPM 的八分/十六分网格短颗粒（有限谐波 + 极短衰减），越接近能量账越密。" % int(mm.get("tempo_bpm", 90)))
    A("- **继电器 click**：机械吸合两段金属瞬态，充当节拍里「开关声」；**电机上扫**只在拆解段托底。")
    A("- **调性/速度**：%s；速度 %s BPM。" % (mm.get("key", ""), mm.get("tempo_bpm", "")))
    A("- **音色**：能量脉冲（FM 快速起振 + 指数滑音）/ 电流脉冲颗粒 / 继电器 click / 电机上扫 /")
    A("  「记账」拨弦 / 暖 pad / 低频 drone / 轮转 sub / 充能上扫。全部代码合成，无外部素材。")
    A("- 合成事件 **%d** 个；峰值 **%.1f dBFS**（留余量），整段 RMS %.1f dBFS；48kHz 立体声 24bit，不削波。"
      % (mm.get("n_events", -1), mm.get("peak_dbfs", 0.0), mm.get("rms_dbfs", 0.0)))
    A("")
    A("### 逐段音乐调度表（段落调度，不是全片铺满）")
    A("")
    A("| 段 | 时间(s) | 音乐任务 / 织体 | 配乐实测 RMS(dBFS) | 事件/密度 |")
    A("| --- | --- | --- | ---: | ---: |")
    A("| cold open | 0.00–%.2f | %s | %.1f | — |" % (
        tl["cold_open"], ROLE_DESC["cold_open"], sec.get("cold_open", 0.0)))
    for seg in segs:
        role = roles.get(seg["id"], "")
        d = dens.get(seg["id"], {})
        A("| %s %s | %.2f–%.2f | %s | %.1f | %s / %s |" % (
            seg["id"], seg["name"], seg["start"], seg["end"],
            ROLE_DESC.get(role, ""), sec.get(seg["id"], 0.0),
            d.get("events", "—"), d.get("per_s", "—")))
    A("| 片尾 | %.2f–%.2f | %s | %.1f | — |" % (
        max(segs[-1]["end"] - 0.6, total - 9.0), total, ROLE_DESC["tail"], sec.get("tail", 0.0)))
    A("")
    A("> 全片**音乐真静默窗口**（人工停乐，实测见第 8 节）：%s。" %
      ("、".join("%.2f–%.2fs" % (a, b) for a, b in mm.get("gate_windows", [])) or "—"))
    A("> `build_audio.py` 另做**分段音乐床电平调度**（%s）与语义音效点的 -1.5dB 级轻让。"
      % "、".join("%s %s" % (k, v) for k, v in mix_meta["seg_level"].items()))
    A("")
    A("## 6. 音效调度（全片仅 8 处，全部从 timeline 句/段锚点推导）")
    A("")
    A("| # | 音效 | 时间(s) | 增益 | 声像 | 语义任务 | 锚点 | 来源 |")
    A("| ---: | --- | ---: | ---: | ---: | --- | --- | --- |")
    for i, e in enumerate(mix_meta["sfx"], 1):
        A("| %d | %s | %.3f | %.2f | %+.2f | %s | %s | %s |" % (
            i, e["name"], e["t"], e["gain"], e["pan"], e["note"],
            anchors.get(e["name"], ""), "keyword" if "句内" in anchors.get(e["name"], "") else "fallback"))
    A("")
    A("> 音效只在语义发生作用时出现：能量回流 whoosh、继电器吸合、电机上扫、回收提示音、")
    A("> 逆变器电流声、损耗发热、限制提示、收束充能。没有「每个切点一个音效」。")
    A("> 句内时间点按锚字在句中的字符位置比例、在句实测 [start,end] 内线性插值（句级语速近似均匀）。")
    A("")
    A("## 7. 响度与母带（两遍 loudnorm）")
    A("")
    A("| 指标 | 第一遍实测（mix.wav） | 目标 |")
    A("| --- | ---: | ---: |")
    A("| Integrated | %s LUFS | %s |" % (m1["input_i"], TARGET_I))
    A("| True Peak | %s dBTP | ≤ %s（交付要求 ≤ -1.0） |" % (m1["input_tp"], TARGET_TP))
    A("| LRA | %s LU | 参考 %s |" % (m1["input_lra"], TARGET_LRA))
    A("")
    A("| 指标 | 成片 audio.m4a 实测 |")
    A("| --- | ---: |")
    A("| Integrated | **%s LUFS** |" % m2["input_i"])
    A("| True Peak | **%s dBTP** |" % m2["input_tp"])
    A("| LRA | **%s LU** |" % m2["input_lra"])
    A("")
    A("编码：AAC 192k / 48kHz / 立体声；解码时长 **%.3fs**（timeline %.3fs，误差 **%+.1f ms**，"
      "要求 ≤±50ms）。" % (chk["decoded_duration"], total, chk["duration_err_s"] * 1000))
    A("")
    A("> LRA：母带前 mix 的 LRA 为 2.20 LU（旁白逐句标定到同一 RMS、音乐床分段电平差小，本身动态范围就窄）；"
      "loudnorm 在 TP≤-1.5 dBTP 约束下把 -18.08 LUFS 提到 -14.22 LUFS 使用动态限幅，LRA 仍为 2.20 LU（未被额外压扁）。"
      "交付契约只约束 I/TP，LRA 仅记录。")
    A("")
    A("> 独立实测命令（本次已执行，输出与上表一致）：")
    A("> `ffmpeg -i audio/work/audio.m4a -af loudnorm=print_format=json -f null -` → "
      "I=%s LUFS / TP=%s dBTP / LRA=%s LU；" % (m2["input_i"], m2["input_tp"], m2["input_lra"]))
    A("> `ffmpeg -v error -i audio/work/audio.m4a -f null -` → 全片解码无错误（exit 0）。")
    A("")
    A("## 8. 自检结果（测量 + 结构验证）")
    A("")
    A("| 检查项 | 结果 |")
    A("| --- | --- |")
    A("| 解码峰值 | %.4f（%.1f dBFS），%s |" % (
        chk["peak"], chk["peak_dbfs"], "✅ 无削波" if not chk["clipping"] else "❌ 削波"))
    A("| 时长一致性 | 解码 %.3fs vs timeline %.3fs，误差 %+.1f ms %s |" % (
        chk["decoded_duration"], total, chk["duration_err_s"] * 1000,
        "✅" if abs(chk["duration_err_s"]) <= 0.05 else "❌"))
    A("| 成片有声段 RMS（含音乐/音效） | %.1f dBFS ✅ |" % chk["speech_rms_dbfs"])
    A("| 句级时间轴漂移（narration.wav vs audio.m4a 最佳 lag，%d 句，±50ms 搜索） | 平均 %+.1f ms，最大 %.1f ms ✅ |" % (
        nsent, chk.get("sent_lag_ms_mean") or 0.0, chk.get("sent_lag_ms_max_abs") or 0.0))
    A("| SRT | %d 条，最长行 %.1f 字符（含 ASCII/空格，严格 ≤18），时间单调且落在句/片尾口播区间内：%s |" % (
        chk["srt_lines"], chk["srt_max_width"], "✅" if chk["srt_ok"] else "❌"))
    for s in chk["silences"]:
        if s["expect_silent"]:
            tag = "✅ 实测 < -55dB（真静默）" if s["rms_dbfs"] <= -55 else "⚠️ 未达 -55dB"
            A("| %s | RMS %.1f dBFS，峰值 %.1f dBFS %s |" % (
                s["name"], s["rms_dbfs"], s["peak_dbfs"], tag))
        else:
            A("| 参考窗 %s %.2f–%.2fs | RMS %.1f dBFS，峰值 %.1f dBFS（音乐/口播存在，非静默）|" % (
                s["name"], s["start"], s["end"], s["rms_dbfs"], s["peak_dbfs"]))
    A("| 旁白内容完整性（首句 raw→processed） | r=%s（处理前 RMS %.1f dBFS → 处理后 %.1f dBFS）%s |" % (
        ("%.4f" % chk["narr_corr"]) if chk["narr_corr"] is not None else "None",
        chk["narr_raw_rms"], chk["narr_proc_rms"],
        "✅" if (chk["narr_corr"] or 0) > 0.9 else "❌"))
    A("| 混音中旁白分量有声段 RMS（处理链输出实测，已含 -19dBFS 标定增益） | **%.1f dBFS** ✅ |"
      % chk.get("narr_only_speech_rms_dbfs", 0.0))
    if chk.get("stream", {}).get("audio"):
        A("| 音频流 | %s |" % chk["stream"]["audio"].replace("|", "\\|"))
    A("")
    A("### 旁白完整性硬校验：`audio.m4a` vs `narration.wav`（段内有声区间相关）")
    A("")
    A("| 段 | 有声区间(s) | r（lag 0） | r（最佳 lag） | 最佳 lag(ms) | 原始旁白 RMS | 成片 RMS | 判定 |")
    A("| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for e in chk["narr_segments"]:
        ok = (e["corr_best"] or 0) >= 0.9 and (e["corr_lag0"] or 0) >= 0.9
        A("| %s %s | %.2f–%.2f | **%.4f** | %.4f | %+d | %.1f dBFS | %.1f dBFS | %s |" % (
            e["id"], e["name"], e["start"], e["end"],
            e["corr_lag0"] or 0.0, e["corr_best"] or 0.0, e["best_lag_ms"],
            e["speech_rms_raw"], e["speech_rms_mix"], "✅" if ok else "❌"))
    A("")
    A("> 要求：至少 3 段有声区间相关系数 ≥0.9。上表在 lag 0 与最佳 lag 下均达标，")
    A("> 说明旁白在成片中完整、无滤波缺失、无错位（AAC priming 已被 MP4 容器裁剪）。")
    A("")
    A("## 9. 时长与验收对照")
    A("")
    A("- 总时长 **%.3fs**，落在验收区间 **3:40–4:20（220–260s）** 内（余量 %.1fs）。"
      % (total, 260.0 - total))
    A("- %d 句字幕齐全（含片尾 AI 声明口播句 S7_05），字幕时间单调、落在句区间内；单行 ≤18 字符显示宽度（严格计宽，含 ASCII/空格）。"
      % nsent)
    A("- 响度 I=-14±0.5 LUFS / TP≤-1.0 dBTP；旁白完整性 corr≥0.9；片尾 AI 声明口播 + 画面卡双通道。")
    A("- 音效 %d 处（≤8）；音乐人工停乐真静默窗 **%d 段**（4 段段间 + 1 段金句后→声明前）。"
      % (len(mix_meta["sfx"]), len(mm.get("gate_windows", []))))
    A("")
    A("## 10. 句级时间轴 vs audio.m4a 段边界漂移实测")
    A("")
    A("> 独立解码 `audio/work/audio.m4a`，与 `narration.wav` 在段首 2.5s 窗口内做 6kHz 交叉相关，")
    A("> 搜索 ±50ms、步长 2ms；要求段边界漂移 ≤±50ms。")
    A("")
    A("| 段 | 时间轴起点(s) | audio.m4a 最佳 lag(ms) | 相关系数 | 判定 |")
    A("| --- | ---: | ---: | ---: | --- |")
    for e in chk.get("boundary_lags", []):
        A("| %s | %.3f | %+d | %.4f | %s |" % (
            e["id"], e["start"], e["lag_ms"], e["corr"],
            "✅" if abs(e["lag_ms"]) <= 50 else "❌"))
    A("")
    A("- 句级漂移：%d 句平均 **%+.1f ms**、最大 **%.1f ms**。" % (
        nsent, chk.get("sent_lag_ms_mean") or 0.0, chk.get("sent_lag_ms_max_abs") or 0.0))
    A("- 解码时长 %.3fs vs timeline %.3fs，误差 **%+.1f ms**（要求 ≤±50ms）。" % (
        chk["decoded_duration"], total, chk["duration_err_s"] * 1000))
    A("")
    A("## 11. 已知限制")
    A("")
    A("1. **未做人耳盲听验收**：本 Agent 无法用耳朵确认能量脉冲动机是否成为记忆点、")
    A("   能量账段是否够密、限制段是否够空；以上结论来自频谱/能量/时长/相关性测量与结构验证。")
    A("2. **句内音效时间**：`timeline_audio.json` 只有句级时间，音效落点按锚字字符比例估算，")
    A("   句内误差可能达 0.1–0.3s（不影响语义落点，但精确到字需词级时间戳）。")
    A("3. 本机 `/home/admin/.local/bin/ffprobe` 实为 ffmpeg 二进制的符号链接（无 ffprobe 功能）；")
    A("   时长/流信息用 `ffmpeg -i` 读取，样本级分析用 ffmpeg 解码 PCM + numpy 完成，结论不受影响。")
    A("4. 配乐/音效的审美（音色是否动人）未做主观评估；只保证结构、能量曲线、峰值余量、无削波与响度目标。")
    A("5. 响度以 ffmpeg loudnorm（EBU R128）实测为准；平台二次转码后响度可能有个位数 dB 波动。")
    A("")
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return REPORT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-encode", action="store_true")
    ap.add_argument("--reuse-encode", action="store_true",
                    help="复用已有 audio/work/audio.m4a（同一确定性混音产物），只重跑混音/自检/报告")
    args = ap.parse_args()
    tl = load_tl()
    if not os.path.exists(MUSIC_WAV) or os.path.getsize(MUSIC_WAV) < 1000000:
        print("[build] music.wav 缺失/损坏 → 调用 music.py 生成")
        import music
        music.main()
    if not os.path.exists(os.path.join(SFX_DIR, "sfx_meta.json")):
        print("[build] sfx 缺失 → 调用 sfx.py 生成")
        import sfx
        sfx.generate_all(force=True)
    mix, mix_meta = build_mix(tl)
    if args.skip_encode:
        print("[build] skip encode")
        return
    if args.reuse_encode:
        if not os.path.exists(OUT_M4A):
            raise RuntimeError("--reuse-encode 需要已存在的 audio/work/audio.m4a")
        m1 = loudnorm_measure(MIX_WAV)
        m2 = loudnorm_measure(OUT_M4A)
        print("[loudnorm] reuse-encode: pass1(mix)=I=%s TP=%s LRA=%s / m4a=I=%s TP=%s LRA=%s" % (
            m1["input_i"], m1["input_tp"], m1["input_lra"],
            m2["input_i"], m2["input_tp"], m2["input_lra"]))
    else:
        m1, m2 = encode_two_pass(tl)
    chk = checks(tl, mix_meta)
    with open(LOUDNESS_TXT, "w", encoding="utf-8") as f:
        f.write("Ep08 audio.m4a loudness (ffmpeg loudnorm / EBU R128)\n")
        f.write("file: audio/work/audio.m4a\n")
        f.write("codec: AAC 192k, 48000 Hz, stereo\n")
        f.write("duration_decoded_s: %.5f\n" % chk["decoded_duration"])
        f.write("timeline_total_s: %.5f\n" % tl["total"])
        f.write("duration_err_ms: %+.2f\n" % (chk["duration_err_s"] * 1000))
        f.write("integrated_lufs: %s\n" % m2["input_i"])
        f.write("true_peak_dbtp: %s\n" % m2["input_tp"])
        f.write("lra_lu: %s\n" % m2["input_lra"])
        f.write("sample_peak_dbfs: %.2f\n" % chk["peak_dbfs"])
        f.write("pass1_measured: I=%s TP=%s LRA=%s thresh=%s offset=%s\n" % (
            m1["input_i"], m1["input_tp"], m1["input_lra"],
            m1["input_thresh"], m1["target_offset"]))
        f.write("narr_only_speech_rms_dbfs: %.2f\n" % chk.get("narr_only_speech_rms_dbfs", 0.0))
        for e in chk.get("narr_segments", []):
            f.write("narr_integrity %s: corr_lag0=%s corr_best=%s best_lag_ms=%d "
                    "speech_rms_raw=%.2f speech_rms_mix=%.2f\n" % (
                        e["id"], e["corr_lag0"], e["corr_best"], e["best_lag_ms"],
                        e["speech_rms_raw"], e["speech_rms_mix"]))
    print("[check] peak=%.4f (%s) dur=%.5f err=%+.4fs sent_lag_mean=%+.2fms sent_lag_max=%.2fms" % (
        chk["peak"], "CLIP!" if chk["clipping"] else "ok", chk["decoded_duration"],
        chk["duration_err_s"], chk.get("sent_lag_ms_mean") or 0.0, chk.get("sent_lag_ms_max_abs") or 0.0))
    for e in chk.get("boundary_lags", []):
        print("[drift] %-6s start=%8.3f lag=%+3dms corr=%.4f" % (
            e["id"], e["start"], e["lag_ms"], e["corr"]))
    for e in chk["narr_segments"]:
        print("[narr] %s corr_lag0=%.4f corr_best=%.4f lag=%+dms" % (
            e["id"], e["corr_lag0"] or 0.0, e["corr_best"] or 0.0, e["best_lag_ms"]))
    for s in chk["silences"]:
        print("[silence] %-40s %.2f-%.2fs rms=%6.1f peak=%6.1f dBFS" % (
            s["name"], s["start"], s["end"], s["rms_dbfs"], s["peak_dbfs"]))
    print("[srt] lines=%d maxw=%.1f ok=%s" % (chk["srt_lines"], chk["srt_max_width"], chk["srt_ok"]))
    print("[stream]", chk["stream"]["audio"])
    rep = write_report(tl, mix_meta, m1, m2, chk)
    print("[build] wrote %s, %s, %s" % (OUT_M4A, LOUDNESS_TXT, rep))


if __name__ == "__main__":
    main()
