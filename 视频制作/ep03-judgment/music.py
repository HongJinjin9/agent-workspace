#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep03 原创配乐（纯 numpy，版权干净）。主题：低频「账页/滴答」+ 稀疏钢琴 + 暖 pad/弦乐。
调性：D 小调（S1–S4）→ S5 转 F 大调 → S6 收束。
情绪：cold open 极稀疏 → S1 悬置（S1 末真静默）→ S2 脉冲推进 → S3 克制 →
S4 下压 → S5 历史温度 → S6 抬升/金句退开/标题句前静默/尾句后 3–4s 收束。
内存受限（cgroup 6.4GB 共享）：全程 float32 + 分块 FFT，峰值 < 400MB。
输出 work/music.wav（48k 立体声 24bit，长度=timeline total，峰值≈-7.5dBFS）。
用法：python3 music.py [--dry]
"""
import argparse
import json
import math
import os

import numpy as np

ROOT = "/app/vedio/ep03-judgment"
SR = 48000
TIMELINE_FULL = os.path.join(ROOT, "work", "timeline_audio_full.json")
MUSIC_WAV = os.path.join(ROOT, "work", "music.wav")
MUSIC_META = os.path.join(ROOT, "work", "music_meta.json")
F32 = np.float32


# ---------------------------------------------------------------- 工具
def env_ar(n, att, rel, sr=SR):
    e = np.ones(n, dtype=F32)
    na = min(n, max(0, int(att * sr)))
    nr = min(n - na, max(0, int(rel * sr)))
    if na > 0:
        e[:na] = 0.5 - 0.5 * np.cos(np.pi * np.arange(na) / na)
    if nr > 0:
        e[n - nr:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(nr) / nr)
    return e


def band_noise(n, flo, fhi, seed, decay=0.03, tilt=0.0):
    rng = np.random.default_rng(seed)
    X = np.fft.rfft(rng.standard_normal(n).astype(F32))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    lo = np.maximum(f, 1.0)
    mask = 1.0 / (1.0 + (lo / max(fhi, 1e-6)) ** 4) / (1.0 + (max(flo, 1e-6) / lo) ** 4)
    if tilt:
        mask *= (lo / 1000.0) ** tilt
    y = np.fft.irfft(X * mask, n).astype(F32)
    y /= (np.max(np.abs(y)) + F32(1e-12))
    if decay > 0:
        y *= np.exp(-np.arange(n) / SR / decay).astype(F32)
    return y


def fft_conv_add(dst, src, h, gain=1.0, block=1 << 17):
    """dst += gain*conv(src,h)，分块 FFT；src 与 dst 需分离。"""
    m, n = len(h), len(src)
    nfft = 1 << (block + m - 1).bit_length()
    H = np.fft.rfft(h.astype(np.float64), nfft)
    for pos in range(0, n, block):
        seg = src[pos:pos + block]
        y = np.fft.irfft(np.fft.rfft(seg.astype(np.float64), nfft) * H, nfft)
        y = y[:len(seg) + m - 1]
        i0 = pos
        n1 = min(len(y), len(dst) - i0)
        if n1 > 0:
            dst[i0:i0 + n1] += (gain * y[:n1]).astype(F32)


def fft_hp_small(x, fc):
    n = len(x)
    X = np.fft.rfft(x.astype(np.float64))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    lo = np.maximum(f, 1e-6)
    return np.fft.irfft(X * (lo / np.sqrt(lo * lo + fc * fc)), n).astype(F32)


def apply_curve(mix, times, vals, block=SR):
    n = mix.shape[1]
    T = np.asarray(times, dtype=np.float64)
    V = np.asarray(vals, dtype=np.float64)
    for pos in range(0, n, block):
        i1 = min(n, pos + block)
        g = np.interp(np.arange(pos, i1) / SR, T, V).astype(F32)
        mix[:, pos:i1] *= g[None, :]


# ---------------------------------------------------------------- 乐器
def piano(f0, dur, amp, seed=0, bright=1.0):
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    tau0 = float(np.clip(3.4 * (220.0 / f0) ** 0.5, 0.45, 6.0))
    for k, a, tk in [(1.0, 1.0, 1.0), (2.001, 0.42, 0.66), (3.004, 0.20, 0.46),
                     (4.012, 0.10, 0.35), (5.03, 0.05, 0.27), (6.05, 0.025, 0.21),
                     (7.08, 0.012, 0.17), (8.11, 0.006, 0.14)]:
        if f0 * k > 9000:
            break
        det = 1.0 + 0.0004 * (rng.random() - 0.5)
        sig += (a * bright) * np.sin(2 * np.pi * f0 * k * det * t
                                     + rng.random() * 6.28318
                                     + 0.0009 * np.sin(2 * np.pi * 0.6 * t)) \
               * np.exp(-t / (tau0 * tk))
    nn = min(n, int(0.014 * SR))
    if nn > 0:
        sig[:nn] += band_noise(nn, 900, 5200, seed + 7, decay=0.0032) * 0.10
    sig *= env_ar(n, 0.004, min(0.4, dur * 0.35))
    return (sig * amp).astype(F32)


def pad(freqs, dur, amp, att=1.2, rel=1.6, cutoff=1400, seed=0, detune=0.0014):
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    for i, f in enumerate(freqs):
        d = detune * (1 if i % 2 == 0 else -1)
        for k in range(1, max(1, int(cutoff / f)) + 1):
            sig += (1.0 / k ** 1.7) * np.sin(2 * np.pi * f * k * (1 + d) * t
                                            + rng.random() * 6.28318)
    sig *= 1.0 + 0.06 * np.sin(2 * np.pi * 0.083 * t + rng.random() * 6.28)
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def strings(freqs, dur, amp, att=2.2, rel=2.4, seed=0):
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    vib = 0.0035 * np.sin(2 * np.pi * 4.7 * t)
    for i, f in enumerate(freqs):
        for k in range(1, 9):
            d = 1.0 + 0.0018 * ((k % 3) - 1) + 0.0007 * (i - 1)
            sig += (0.8 / k) * np.sin(2 * np.pi * f * k * d * t + vib * k
                                      + rng.random() * 6.28318)
    sig *= 1.0 + 0.04 * np.sin(2 * np.pi * 0.11 * t + 1.3)
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def drone(f0, dur, amp, att=1.4, rel=1.6):
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    sig = (np.sin(2 * np.pi * f0 * t) + 0.45 * np.sin(2 * np.pi * 2 * f0 * t + 0.7)
           + 0.18 * np.sin(2 * np.pi * 3 * f0 * t + 1.9)
           + 0.10 * np.sin(2 * np.pi * 4 * f0 * t + 2.7))
    sig *= 1.0 + 0.16 * np.sin(2 * np.pi * 0.07 * t + 0.4)
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def sub_pulse(f0, dur, amp, att=0.006):
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * f0 * t) + 0.35 * np.sin(2 * np.pi * 2 * f0 * t + 0.5)
    return (sig * np.exp(-t / 0.55) * (1.0 - np.exp(-t / max(att, 1e-4))) * amp).astype(F32)


def ledger_tick(amp, bright=2600, seed=0):
    n = int(0.085 * SR)
    t = np.arange(n) / SR
    click = band_noise(n, bright - 1200, bright + 1400, seed, decay=0.011)
    body = (np.sin(2 * np.pi * 168 * t) * np.exp(-t / 0.030)).astype(F32)
    return (click * F32(0.9) + body * F32(0.35)) * F32(amp)


def data_blip(f0, amp, seed=0):
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * f0 * t) + 0.3 * np.sin(2 * np.pi * 2 * f0 * t)
    return (sig * (1 - np.exp(-t / 0.002)) * np.exp(-t / 0.014) * amp).astype(F32)


def make_ir(dur=1.5, seed=11, hp=120.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ir = np.zeros((2, n), dtype=F32)
    for ch in range(2):
        rng = np.random.default_rng(seed + ch * 31)
        X = np.fft.rfft(rng.standard_normal(n).astype(F32))
        f = np.fft.rfftfreq(n, 1.0 / SR)
        lo = np.maximum(f, 1.0)
        y = np.fft.irfft(X * (1.0 / (1.0 + (lo / 3600.0) ** 2)), n).astype(F32)
        y *= np.exp(-t / 0.42).astype(F32)
        for dly, g in ((0.011, 0.55), (0.019, 0.42), (0.027, 0.34),
                       (0.041, 0.26), (0.058, 0.20), (0.079, 0.15)):
            i = int(dly * SR)
            if i < n:
                y[i] += g * (1 if ch == 0 else 0.85)
        y = fft_hp_small(y, hp)
        # 能量归一：湿声 RMS ≈ 干声 RMS * wet_gain（峰值归一会让卷积增益高达 +25dB）
        ir[ch] = y / (np.sqrt(np.sum(y.astype(np.float64) ** 2)) + 1e-12)
    return ir


# ---------------------------------------------------------------- 和声
D2, D3, D4 = 73.42, 146.83, 293.66
A2, A3, A4 = 110.00, 220.00, 440.00
F2, F3, F4 = 87.31, 174.61, 349.23
C2, C3, C4, C5 = 65.41, 130.81, 261.63, 523.25
G2, G3, G4 = 98.00, 196.00, 392.00
E3, Bb1, Bb2, D5 = 164.81, 58.27, 116.54, 587.33

CHORDS = {
    "Dm": [D2, A2, D3, F3], "Bb": [Bb1, F2, Bb2, D3], "F": [F2, C3, F3, A3],
    "C": [C2, G2, C3, E3], "Gm": [G2, Bb2, D3, G3], "A": [A2, E3, A3, C4],
    "Fadd9": [F2, C3, F3, G3], "Fwarm": [F2, A2, C3, F3, A3],
}


def load_tl():
    with open(TIMELINE_FULL, "r", encoding="utf-8") as f:
        return json.load(f)


def render(tl, verbose=True):
    total = float(tl["total"])
    N = int(round(total * SR))
    mix = np.zeros((2, N), dtype=F32)
    events = []
    segs = {s["id"]: s for s in tl["segments"]}
    sent = {}
    for s in tl["segments"]:
        for x in s["sentences"]:
            sent["%s_%02d" % (s["id"], x["i"])] = x

    def S(sid):
        return sent[sid]["start"]

    def E(sid):
        return sent[sid]["end"]

    def put(name, t0, sig, pan=0.0, gain=1.0):
        if sig is None or len(sig) == 0:
            return
        i0 = int(round(t0 * SR))
        if i0 < 0:
            sig, i0 = sig[-i0:], 0
        if i0 >= N:
            return
        n = min(len(sig), N - i0)
        th = (pan + 1.0) * math.pi / 4.0
        chunk = sig[:n].astype(F32) * F32(gain)
        mix[0, i0:i0 + n] += chunk * F32(math.cos(th))
        mix[1, i0:i0 + n] += chunk * F32(math.sin(th))
        events.append(dict(name=name, t=round(t0, 3), dur=round(len(sig) / SR, 3),
                           pan=round(pan, 2), gain=round(gain, 3)))

    s1, s2, s3, s4, s5, s6 = (segs[k] for k in ("S1", "S2", "S3", "S4", "S5", "S6"))
    cold, gap = float(tl["cold_open"]), float(tl["segment_gap"])

    # cold open：sub 涌动 + 1 次轻滴答（落印交给 sfx）
    put("cold_sub", 0.35, drone(36.71, cold - 0.35, 0.012, att=1.6, rel=1.0), pan=0.0)
    put("cold_tick", 1.35, ledger_tick(0.020, bright=2400, seed=101), pan=0.10)

    # S1 悬置
    s1_end = E("S1_06") - 0.10
    put("S1_drone", S("S1_01") + 0.15, drone(D2, max(1.0, s1_end - S("S1_01") - 0.15),
                                              0.050, att=1.3, rel=0.55), pan=0.0)
    put("S1_sub", S("S1_01") + 0.15, drone(36.71, max(1.0, s1_end - S("S1_01") - 0.15),
                                          0.022, att=1.6, rel=0.55), pan=0.0)
    for k, (t0, f, d, a, p) in enumerate([
            (S("S1_01") + 0.35, D4, 3.6, 0.105, -0.15),
            (E("S1_02") + 0.10, A3, 3.2, 0.085, 0.20),
            (S("S1_03") + 0.15, F4, 3.0, 0.070, 0.10),
            (S("S1_04") + 0.10, C4, 3.2, 0.080, -0.10),
            (S("S1_05") + 0.10, D4, 3.0, 0.095, 0.05),
            (S("S1_06") + 0.02, D3, 4.0, 0.120, 0.0)]):
        put("S1_piano%d" % (k + 1), t0, piano(f, d, a, seed=200 + k), pan=p)

    # S2 脉冲推进
    t, k = s2["start"] + 0.45, 0
    while t < s2["end"] - 0.9:
        put("S2_tick%d" % k, t, ledger_tick(0.024 * (1.0 if k % 4 == 0 else 0.62),
                                            bright=2500, seed=300 + k), pan=0.08)
        k += 1
        t += 1.0
    put("S2_tick_end", s2["end"] - 0.55, ledger_tick(0.016, bright=2200, seed=399), pan=0.05)
    for j, name in enumerate(["Dm", "Bb", "F", "C"]):
        t0 = s2["start"] + j * (s2["dur"] / 4.0)
        put("S2_bass_%s" % name, t0, sub_pulse(CHORDS[name][0] / 2, 4.2, 0.032), pan=0.0)
        put("S2_padL_%s" % name, t0, pad(CHORDS[name][1:], s2["dur"] / 4.0 + 0.8, 0.0140,
                                         att=1.1, rel=1.6, cutoff=1100, seed=400 + j), pan=-0.35)
        put("S2_padR_%s" % name, t0 + 0.02, pad(CHORDS[name][1:], s2["dur"] / 4.0 + 0.8, 0.0125,
                                                 att=1.3, rel=1.6, cutoff=1000, seed=430 + j), pan=0.35)
    for k, (t0, f, a) in enumerate([
            (S("S2_02") + 0.05, A3, 0.075), (S("S2_03") + 0.05, F4, 0.070),
            (S("S2_04") + 0.05, C4, 0.075), (S("S2_05") + 0.05, D4, 0.085),
            (S("S2_06") + 0.05, A3, 0.065), (S("S2_07") + 0.05, C4, 0.070),
            (E("S2_08") + 0.05, F4, 0.080)]):
        put("S2_piano%d" % (k + 1), t0, piano(f, 3.0, a, seed=500 + k), pan=0.05)

    # S3 克制
    put("S3_drone", s3["start"] + 0.2, drone(D2, s3["dur"] - 0.9, 0.032, att=1.4, rel=0.8), pan=0.0)
    for j, name in enumerate(["Dm", "Bb", "Gm", "Dm", "Bb", "Dm"]):
        put("S3_pad_%s" % name, s3["start"] + j * (s3["dur"] / 6.0),
            pad(CHORDS[name][1:], s3["dur"] / 6.0 + 0.6, 0.0105,
                att=1.4, rel=1.8, cutoff=900, seed=600 + j), pan=-0.30)
    t, k = s3["start"] + 0.7, 0
    while t < s3["end"] - 0.9:
        put("S3_tick%d" % k, t, ledger_tick(0.016, bright=2100, seed=650 + k), pan=-0.05)
        k += 1
        t += 1.6
    for j, (sid, f) in enumerate([("S3_02", 1500), ("S3_02", 1780), ("S3_05", 1420)]):
        t0 = S(sid) + 1.1 + j * 1.9
        if t0 < s3["end"] - 0.5:
            put("S3_blip%d" % j, t0, data_blip(f, 0.016, seed=680 + j), pan=0.25)
    for k, (t0, f, a) in enumerate([
            (S("S3_01") + 0.10, D4, 0.080), (S("S3_02") + 0.10, A3, 0.070),
            (S("S3_03") + 0.10, F4, 0.060), (S("S3_04") + 0.10, C4, 0.068),
            (S("S3_05") + 0.10, A3, 0.058), (S("S3_06") + 0.10, D3, 0.085),
            (S("S3_07") + 0.10, F3, 0.075)]):
        put("S3_piano%d" % (k + 1), t0, piano(f, 3.4, a, seed=700 + k), pan=-0.05)

    # S4 下压
    put("S4_drone", s4["start"] + 0.15, drone(36.71, s4["dur"] - 0.8, 0.055,
                                              att=1.2, rel=0.7), pan=0.0)
    t, k = s4["start"] + 0.35, 0
    while t < s4["end"] - 0.95:
        put("S4_sub%d" % k, t, sub_pulse(D2 if k % 2 == 0 else F2, 1.8, 0.050), pan=0.0)
        if k % 2 == 1:
            put("S4_tick%d" % k, t, ledger_tick(0.012, bright=1900, seed=800 + k), pan=0.10)
        k += 1
        t += 2.0
    put("S4_darkpadL", s4["start"] + 0.3, pad([D2, A2, D3, F3], s4["dur"] - 1.0, 0.020,
                                             att=2.0, rel=2.2, cutoff=620, seed=810), pan=-0.25)
    put("S4_darkpadR", s4["start"] + 0.35, pad([D2, A2, D3, F3], s4["dur"] - 1.0, 0.017,
                                              att=2.2, rel=2.2, cutoff=580, seed=811), pan=0.25)
    for k, (t0, f, d, a) in enumerate([
            (S("S4_01") + 0.05, D3, 4.0, 0.125), (S("S4_02") + 0.05, D3, 2.6, 0.090),
            (S("S4_03") + 0.05, A3, 3.4, 0.070), (S("S4_04") + 0.05, F3, 2.8, 0.095),
            (S("S4_05") + 0.05, D3, 3.2, 0.080), (S("S4_06") + 0.05, A2, 3.2, 0.105),
            (S("S4_07") + 0.05, D3, 3.0, 0.075), (S("S4_08") + 0.05, C4, 2.6, 0.075),
            (S("S4_09") + 0.05, F4, 2.6, 0.075), (S("S4_10") + 0.05, D3, 4.2, 0.130)]):
        put("S4_piano%d" % (k + 1), t0, piano(f, d, a, seed=850 + k), pan=-0.05)

    # S5 历史温度
    put("S5_drone", s5["start"] + 0.2, drone(F2, s5["dur"] - 0.7, 0.020, att=1.6, rel=0.9), pan=0.0)
    for j, name in enumerate(["Bb", "F", "C", "Dm"]):
        t0 = s5["start"] + j * (s5["dur"] / 4.0)
        put("S5_padL_%s" % name, t0, pad(CHORDS[name][1:], s5["dur"] / 4.0 + 1.0, 0.0175,
                                         att=1.5, rel=2.0, cutoff=1900, seed=900 + j), pan=-0.42)
        put("S5_padR_%s" % name, t0 + 0.03, pad(CHORDS[name][1:], s5["dur"] / 4.0 + 1.0, 0.0155,
                                                att=1.7, rel=2.0, cutoff=1700, seed=930 + j), pan=0.42)
    put("S5_sub", s5["start"] + 0.2, drone(F2 / 2, s5["dur"] - 0.7, 0.012, att=1.8, rel=0.9), pan=0.0)
    for k, (t0, f, d, a) in enumerate([
            (S("S5_01") + 0.10, F4, 3.6, 0.080), (S("S5_02") + 0.10, A4, 3.2, 0.070),
            (S("S5_02") + 2.1, C5, 2.8, 0.058), (S("S5_03") + 0.10, G4, 2.8, 0.062),
            (S("S5_04") + 0.10, A4, 3.4, 0.070), (S("S5_05") + 0.05, F4, 3.6, 0.085),
            (E("S5_06") + 0.10, A4, 3.0, 0.062)]):
        put("S5_piano%d" % (k + 1), t0, piano(f, d, a, seed=960 + k), pan=0.12)

    # S6 抬升→回落
    for j, name in enumerate(["F", "C", "Dm", "Bb", "Fadd9"]):
        t0 = s6["start"] + j * (s6["dur"] / 5.0)
        d = s6["dur"] / 5.0 + 1.2
        put("S6_padL_%s" % name, t0, pad(CHORDS[name][1:], d, 0.0175, att=1.6, rel=2.2,
                                         cutoff=1900, seed=1000 + j), pan=-0.40)
        put("S6_padR_%s" % name, t0 + 0.03, pad(CHORDS[name][1:], d, 0.0150, att=1.8, rel=2.2,
                                                cutoff=1700, seed=1030 + j), pan=0.40)
    put("S6_drone", s6["start"] + 0.15, drone(F2, s6["dur"] - 0.8, 0.024, att=1.8, rel=1.2), pan=0.0)
    str_d = S("S6_05") - S("S6_02") + 1.2
    put("S6_strings1", S("S6_02") - 0.2, strings([F3, A3, C4], str_d, 0.0125,
                                                 att=2.0, rel=2.2, seed=1100), pan=-0.30)
    put("S6_strings1R", S("S6_02") - 0.2, strings([F3, A3, C4], str_d, 0.0105,
                                                  att=2.2, rel=2.2, seed=1101), pan=0.30)
    str_d2 = S("S6_07") - S("S6_04") + 0.8
    put("S6_strings2", S("S6_04") + 0.4, strings([A3, C4, F4], str_d2, 0.0135,
                                                 att=1.6, rel=2.0, seed=1110), pan=-0.25)
    put("S6_strings2R", S("S6_04") + 0.4, strings([A3, C4, F4], str_d2, 0.0115,
                                                  att=1.8, rel=2.0, seed=1111), pan=0.25)
    t, k = s6["start"] + 0.9, 0
    while t < E("S6_08") - 0.2:
        put("S6_tick%d" % k, t, ledger_tick(0.017 * (1.0 if k % 4 == 0 else 0.60),
                                            bright=2400, seed=1200 + k), pan=0.06)
        k += 1
        t += 1.0
    for j, sid in enumerate(["S6_02", "S6_03", "S6_04"]):
        put("S6_qsub%d" % j, S(sid) - 0.12, sub_pulse(C2 if j < 2 else D2, 1.5,
                                                      0.030 if j < 2 else 0.040), pan=0.0)
    for k, (t0, f, a) in enumerate([
            (S("S6_01") + 0.10, F4, 0.085), (S("S6_02") + 0.10, A4, 0.075),
            (S("S6_03") + 0.10, C5, 0.065), (S("S6_04") + 0.05, F4, 0.095),
            (S("S6_05") + 0.05, A4, 0.075), (S("S6_06") + 0.05, G4, 0.080),
            (S("S6_07") + 0.05, C5, 0.065), (S("S6_08") + 0.05, D5, 0.060),
            (S("S6_09") + 0.10, A4, 0.058), (E("S6_10") + 0.30, F4, 0.045),
            (S("S6_12") + 0.20, C5, 0.060), (S("S6_13") + 0.10, F4, 0.070)]):
        put("S6_piano%d" % (k + 1), t0, piano(f, 3.6, a, seed=1300 + k), pan=0.10)
    tail_t = E("S6_13") + 0.08
    tail_d = max(0.8, total - tail_t - 0.15)
    put("tail_chordL", tail_t, pad(CHORDS["Fwarm"][1:], tail_d, 0.022,
                                   att=0.5, rel=2.6, cutoff=1700, seed=1400), pan=-0.35)
    put("tail_chordR", tail_t + 0.02, pad(CHORDS["Fwarm"][1:], tail_d, 0.019,
                                          att=0.6, rel=2.6, cutoff=1500, seed=1401), pan=0.35)
    put("tail_piano1", tail_t, piano(F4, 3.4, 0.075, seed=1410), pan=0.10)
    put("tail_piano2", tail_t + 1.05, piano(C5, 2.8, 0.050, seed=1411), pan=-0.10)
    put("tail_piano3", tail_t + 2.05, piano(A4, 2.6, 0.042, seed=1412), pan=0.12)
    put("tail_sub", tail_t, sub_pulse(F2, 3.4, 0.030, att=0.02), pan=0.0)

    # 底噪（分块 pink，交叉淡化）
    air_t = [0.0, 0.35, 1.32, 3.6, cold, cold + 0.5, total]
    air_v = [0.0016, 0.0028, 0.0022, 0.0020, 0.0019, 0.0018, 0.0016]
    bs, ov = SR * 2, SR // 4
    for ch in range(2):
        pos, k = 0, 0
        while pos < N:
            L = min(bs + ov, N - pos)
            x = band_noise(L, 30, 5200, seed=1500 + ch * 97 + k, decay=0, tilt=-0.5)
            w = np.ones(L, dtype=F32)
            na = min(ov, L)
            w[:na] = np.linspace(0.0, 1.0, na, endpoint=False, dtype=F32)
            if pos + L < N:
                w[-ov:] = np.linspace(1.0, 0.0, ov, endpoint=False, dtype=F32)
            amp = np.interp(np.arange(pos, pos + L) / SR, air_t, air_v).astype(F32)
            mix[ch, pos:pos + L] += x * w * amp
            pos += bs
            k += 1

    # 混响（分块卷积 + 低切 IR）
    ir = make_ir(1.5)
    for ch in range(2):
        send = mix[ch].copy()
        fft_conv_add(mix[ch], send, ir[ch], gain=0.24, block=1 << 17)
        del send
    del ir

    # 音乐 auto（人工调度：关键句前退开 / 段末真静默）
    gate_t = [0.0, S("S1_05") - 0.2, S("S1_05"), S("S1_06") - 0.15, E("S1_06"),
              E("S1_06") + 0.32, s1["end"] - 0.02, s2["start"] - 0.15,
              s2["start"] + 0.55, s2["start"] + 1.15, s2["end"] - 0.4,
              s3["start"] - 0.1, s3["start"] + 0.6, s3["end"] - 0.5,
              s4["start"] - 0.1, s4["start"] + 0.5, s4["end"] - 0.6,
              s5["start"] - 0.1, s5["start"] + 0.6, s5["end"] - 0.5,
              s6["start"] - 0.1, s6["start"] + 0.5, E("S6_08"), E("S6_08") + 0.30,
              E("S6_10"), E("S6_10") + 0.30, S("S6_11") + 0.12, S("S6_11") + 0.9,
              S("S6_12") + 0.3, S("S6_13"), total - 0.15]
    gate_v = [1.0, 1.0, 0.92, 0.88, 0.88, 0.0, 0.0, 0.0, 0.70, 1.0, 1.0,
              1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
              0.55, 0.55, 0.0, 0.0, 0.82, 0.88, 0.92, 0.0]
    apply_curve(mix, gate_t, gate_v)

    # 峰值归一（留余量）
    peak = 0.0
    for pos in range(0, N, SR):
        peak = max(peak, float(np.max(np.abs(mix[:, pos:pos + SR]))))
    target_peak = 0.42
    scale = F32(target_peak / max(peak, 1e-9))
    for pos in range(0, N, SR):
        mix[:, pos:pos + SR] *= scale
    rms = float(np.sqrt(np.mean(mix.astype(np.float64) ** 2)))

    meta = dict(total=total, sample_rate=SR, n_events=len(events),
                peak_dbfs=round(20 * np.log10(max(target_peak, 1e-9)), 2),
                rms_dbfs=round(20 * np.log10(max(rms, 1e-9)), 2),
                sections={}, events=events)
    for name, a, b in [("cold_open", 0.0, cold), ("S1", s1["start"], s1["end"]),
                       ("S1_silence", E("S1_06") + 0.4, s1["end"] + gap),
                       ("S2", s2["start"], s2["end"]), ("S3", s3["start"], s3["end"]),
                       ("S4", s4["start"], s4["end"]), ("S5", s5["start"], s5["end"]),
                       ("S6", s6["start"], s6["end"]), ("tail", E("S6_13") + 0.2, total)]:
        i0, i1 = int(a * SR), min(N, int(b * SR))
        if i1 > i0:
            r = float(np.sqrt(np.mean(mix[:, i0:i1].astype(np.float64) ** 2)))
            meta["sections"][name] = round(20 * np.log10(max(r, 1e-12)), 2)
    if verbose:
        print("[music] peak=%.2f dBFS rms=%.2f dBFS events=%d" % (
            meta["peak_dbfs"], meta["rms_dbfs"], len(events)))
        for k, v in meta["sections"].items():
            print("    %-12s %7.1f dBFS" % (k, v))
    return mix, meta


def write_wav24(path, x, sr=SR, chunk=1 << 19):
    """stereo float32 -> 24bit PCM WAV，分块写（低内存）。"""
    n = x.shape[1]
    data_bytes = n * 2 * 3
    import struct
    hdr = b"RIFF" + struct.pack("<I", 36 + data_bytes) + b"WAVE"
    hdr += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 2, sr, sr * 2 * 3, 2 * 3, 24)
    hdr += b"data" + struct.pack("<I", data_bytes)
    with open(path, "wb") as f:
        f.write(hdr)
        for pos in range(0, n, chunk):
            seg = x[:, pos:pos + chunk].T
            pcm = np.ascontiguousarray((np.clip(seg, -1.0, 1.0) * 8388607.0).astype("<i4"))
            f.write(pcm.view(np.uint8).reshape(-1, 4)[:, :3].tobytes())
            del pcm, seg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    tl = load_tl()
    mix, meta = render(tl)
    if args.dry:
        print("[music] dry run")
        return
    write_wav24(MUSIC_WAV, mix)
    meta["file"] = os.path.relpath(MUSIC_WAV, ROOT)
    meta["samples"] = int(mix.shape[1])
    meta["duration"] = round(mix.shape[1] / SR, 5)
    with open(MUSIC_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("[music] wrote %s (%.3fs, %d samples)" % (MUSIC_WAV, meta["duration"], meta["samples"]))


if __name__ == "__main__":
    main()
