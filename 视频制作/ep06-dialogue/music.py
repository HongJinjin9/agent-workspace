#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep06 原创配乐（纯 numpy 合成，无外部曲库 / 无外部采样，版权干净）
====================================================================
主题：**单一主题变奏** —— 「判决主题」：一个 16 拍（60 BPM）的 D 小调旋律，
由低音提琴（arco，慢起音、揉弦）陈述；每一幕只变配器、节奏与调式，不做第二主题。

「判决主题」（单位：拍，60 BPM → 1 拍 = 1 秒）：
  D4 F4 A4 | C5 A4 F4 | E4 G4 Bb4 | A4 D4     （D 小调，落回主音 A4 → D4）
第三幕同一主题转 **D 大调**（F→F#、C→C#、Bb→B），是同一句话换了判决。

段落性格（严格按稿件 §2.6）：
  冷开场  —— 低音提琴长弓 + 极低 drone；主题只露前四个音，几乎不解释
  第一幕  —— 低音提琴陈述完整主题 + D 小调低音持续；压迫感，无脉冲；判决处大留白
  第二幕  —— 同一主题 + 加入 muted pulse（60 BPM 的软底鼓）+ 钢琴八分音符分解；节奏推进
  第三幕  —— 同一主题转 D 大调：弦乐群铺亮，脉冲退到二分音符（「改判」的色彩）
  第四幕  —— 主题回落：只剩单音钢琴（一句一音）+ 低 drone；冷，几乎抽空
  收束    —— 主题完整再现一次（低音提琴 + 弦乐 + 钢琴），最后一个 Dm(add9) 长音后 **停**
              （之后是片尾声明口播，音乐保持真静默，形成「说完就走」的留白）

调性：D 小调（主调）→ 第二幕 D 小调（Dm–Bb–F–C）→ 第三幕 D 大调（D–Bm–G–A）
      → 第四幕 D 小调 → 收束 D 小调完满终止（Dm add9）。与 ep04（E 小调/64BPM 心跳）、
      ep05（A 小调/72BPM 时钟）不同调、不同速度、不同动机、不同主奏乐器（低音提琴 arco）。

输出 work/music.wav（48kHz 立体声 24bit，长度 = timeline total，峰值 ≈ -7.5dBFS）
     work/music_meta.json
用法：python3 music.py [--dry]
"""
import argparse
import json
import math
import os

import numpy as np

ROOT = "/app/vedio/ep06-dialogue"
SR = 48000
TIMELINE_FULL = os.path.join(ROOT, "work", "timeline_audio_full.json")
MUSIC_WAV = os.path.join(ROOT, "work", "music.wav")
MUSIC_META = os.path.join(ROOT, "work", "music_meta.json")
F32 = np.float32

BPM = 60.0                  # 主速度：1 拍 = 1 秒，慢而稳（审判的节奏）
BEAT = 60.0 / BPM


# ---------------------------------------------------------------- 基础工具
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


def hz(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


# ---------------------------------------------------------------- 音色
def bowed(f0, dur, amp, att=0.22, rel=0.45, vib_hz=4.6, seed=0, brightness=0.55):
    """低音提琴（arco）：慢起音 + 揉弦 + 弓噪；低次谐波厚、高次谐波按亮度衰减。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    vib = 0.0032 * np.sin(2 * np.pi * vib_hz * t + rng.random() * 6.28)
    for k in range(1, 11):
        if f0 * k > 7000:
            break
        a = (1.0 / k ** 1.15) * (brightness ** (k - 1))
        det = 1.0 + 0.0011 * ((k % 3) - 1)
        sig += a * np.sin(2 * np.pi * f0 * k * det * t + vib * k + rng.random() * 6.28318)
    # 弓噪：低频为主，一点点 2–5kHz 的「毛边」
    sig += 0.010 * band_noise(n, 120, 2400, seed + 1, decay=0) * (1.0 + 0.3 * np.sin(2 * np.pi * 0.7 * t))
    sig += 0.0035 * band_noise(n, 2400, 6000, seed + 2, decay=0)
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def cello_phrase(notes, amp, seed=0, bpm=BPM, att=0.20, rel=0.40, brightness=0.55):
    """低音提琴陈述一条旋律：notes=[(beat_off, midi, dur_beats), ...]，60BPM 下 1 拍=1s。"""
    if not notes:
        return np.zeros(0, dtype=F32)
    beat = 60.0 / bpm
    total = max(off * beat + d * beat for off, m, d in notes) + 1.2
    n = int(total * SR)
    sig = np.zeros(n, dtype=np.float64)
    for k, (off, m, d) in enumerate(notes):
        c = bowed(hz(m), d * beat + rel, 1.0, att=att, rel=rel,
                  seed=seed + k, brightness=brightness)
        i0 = int(off * beat * SR)
        m2 = min(len(c), n - i0)
        if m2 > 0:
            sig[i0:i0 + m2] += c[:m2]
    return (sig * amp).astype(F32)


def piano(f0, dur, amp, seed=0, bright=0.80):
    """软钢琴（比 ep05 更暗更圆）：1–4 次分音为主，中速衰减。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    tau0 = float(np.clip(3.2 * (220.0 / f0) ** 0.45, 0.5, 6.0))
    for k, a, tk in [(1.0, 1.0, 1.0), (2.001, 0.30, 0.55), (3.004, 0.12, 0.34),
                     (4.009, 0.05, 0.24), (5.02, 0.02, 0.16)]:
        if f0 * k > 8000:
            break
        sig += (a * bright) * np.sin(2 * np.pi * f0 * k * t + rng.random() * 6.28318) \
            * np.exp(-t / (tau0 * tk))
    nn = min(n, int(0.012 * SR))
    if nn > 0:
        sig[:nn] += band_noise(nn, 800, 4200, seed + 3, decay=0.0035) * 0.07
    sig *= env_ar(n, 0.004, min(0.5, dur * 0.30))
    return (sig * amp).astype(F32)


def strings(freqs, dur, amp, att=1.4, rel=1.8, seed=0, vib_hz=4.2, cutoff=9):
    """弦乐群：慢起音、群失谐、轻颤音（第三幕转大调时铺亮）。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    vib = 0.0035 * np.sin(2 * np.pi * vib_hz * t)
    for i, f in enumerate(freqs):
        for k in range(1, cutoff + 1):
            if f * k > 8000:
                break
            d = 1.0 + 0.0016 * ((k % 3) - 1) + 0.0006 * i
            sig += (0.85 / k) * np.sin(2 * np.pi * f * k * d * t + vib * k + rng.random() * 6.28318)
    sig *= 1.0 + 0.05 * np.sin(2 * np.pi * 0.09 * t + 1.3)
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def low_drone(f0, dur, amp, att=1.6, rel=1.6, wob=0.12, seed=0):
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = (np.sin(2 * np.pi * f0 * t) + 0.40 * np.sin(2 * np.pi * 2 * f0 * t + 0.6)
           + 0.14 * np.sin(2 * np.pi * 3 * f0 * t + 1.7)
           + 0.07 * np.sin(2 * np.pi * 4 * f0 * t + 2.4))
    sig *= 1.0 + wob * np.sin(2 * np.pi * (0.11 + 0.03 * rng.random()) * t + 0.3)
    sig += band_noise(n, 22, 220, seed + 1, decay=0, tilt=-0.4) * 0.05
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def muted_pulse(amp, seed=0, f_hi=66.0, f_lo=44.0, tau=0.14):
    """muted pulse（软底鼓）：音高 66→44Hz、极短，像隔着桌布敲一下；第二幕的推进。"""
    n = int(0.42 * SR)
    t = np.arange(n) / SR
    f = f_hi * np.exp(-t / 0.035) + f_lo * (1.0 - np.exp(-t / 0.035))
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(ph) * np.exp(-t / tau)
    sig += 0.20 * np.sin(2 * ph + 0.4) * np.exp(-t / (tau * 0.5))
    sig += 0.05 * band_noise(n, 150, 1500, seed + 1, decay=0.012)
    return (sig * env_ar(n, 0.0015, 0.10) * amp).astype(F32)


def make_ir(dur=2.0, seed=11, hp=120.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ir = np.zeros((2, n), dtype=F32)
    for ch in range(2):
        rng = np.random.default_rng(seed + ch * 41)
        X = np.fft.rfft(rng.standard_normal(n).astype(F32))
        f = np.fft.rfftfreq(n, 1.0 / SR)
        lo = np.maximum(f, 1.0)
        y = np.fft.irfft(X * (1.0 / (1.0 + (lo / 3000.0) ** 2)), n).astype(F32)
        y *= np.exp(-t / 0.62).astype(F32)
        for dly, g in ((0.017, 0.5), (0.029, 0.36), (0.047, 0.26), (0.068, 0.18), (0.091, 0.12)):
            i = int(dly * SR)
            if i < n:
                y[i] += g * (1 if ch == 0 else 0.85)
        y = fft_hp_small(y, hp)
        ir[ch] = y / (np.sqrt(np.sum(y.astype(np.float64) ** 2)) + 1e-12)
    return ir


# ---------------------------------------------------------------- 和声 / 主题
CHORDS = {
    # D 小调
    "Dm":    [38, 45, 50, 53],     # D2 A2 D3 F3
    "Bb":    [34, 41, 46, 50],     # Bb1 F2 Bb2 D3
    "F":     [41, 48, 53, 57],     # F2 C3 F3 A3
    "C":     [36, 43, 48, 52],     # C2 G2 C3 E3
    "Gm":    [31, 38, 43, 46],     # G1 D2 G2 Bb2
    "A":     [33, 40, 45, 49],     # A1 E2 A2 C#3
    "Dmadd9": [38, 45, 50, 53, 64],
    # D 大调（第三幕）
    "D":     [38, 45, 50, 54],     # D2 A2 D3 F#3
    "Bm":    [35, 42, 47, 50],     # B1 F#2 B2 D3
    "G":     [31, 38, 43, 47],     # G1 D2 G2 B2
    "A_maj": [33, 40, 45, 49],     # A1 E2 A2 C#3
}
# 「判决主题」：D 小调（beat_off, midi, dur_beats）
THEME_MIN = [(0, 62, 2), (2, 65, 1), (3, 69, 1), (4, 72, 2), (6, 69, 1),
             (7, 65, 1), (8, 64, 2), (10, 67, 1), (11, 70, 1), (12, 69, 3), (15, 62, 1)]
# 同一主题转 D 大调（第三幕）：F→F#、C→C#、Bb→B
THEME_MAJ = [(0, 62, 2), (2, 66, 1), (3, 69, 1), (4, 73, 2), (6, 69, 1),
             (7, 66, 1), (8, 64, 2), (10, 67, 1), (11, 71, 1), (12, 69, 3), (15, 62, 1)]


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

    def ch(name):
        return [hz(m) for m in CHORDS[name]]

    cold = float(tl["cold_open"])
    c, a1, a2, a3, a4, cl = (segs[k] for k in ("COLD", "ACT1", "ACT2", "ACT3", "ACT4", "CLOSE"))

    # ============================================================ 冷开场 0–16.1
    put("cold_drone", 0.0, low_drone(hz(26), cold - 0.1, 0.024, att=1.0, rel=0.8, seed=600), pan=0.0)
    put("cold_cello_low", 0.15, low_drone(hz(38), 5.0, 0.014, att=0.8, rel=1.2, seed=601), pan=0.0)
    # 主题只露前四个音（D4 F4 A4），慢
    put("cold_cello1", S("COLD_01") + 1.0, cello_phrase([(0, 62, 2.4), (2.4, 65, 1.2), (3.6, 69, 2.0)],
                                                       0.020, seed=610, brightness=0.42), pan=-0.12)
    put("cold_cello2", S("COLD_03") + 0.6, cello_phrase([(0, 64, 2.0), (2.0, 62, 3.0)], 0.016,
                                                       seed=613, brightness=0.40), pan=0.10)
    put("cold_piano", S("COLD_02") + 0.4, piano(hz(74), 3.6, 0.020, seed=615), pan=0.06)

    # ============================================================ 第一幕 17.7–55.7（低音提琴 + Dm 持续，压迫）
    a1a = a1["start"]
    put("ACT1_drone", a1a, low_drone(hz(26), a1["end"] - a1a, 0.016, att=1.6, rel=1.4, seed=700), pan=0.0)
    # Dm 低音持续（每句换气一次，避免长音死板）
    for j, sid in enumerate(["ACT1_01", "ACT1_04", "ACT1_07", "ACT1_10"]):
        t0 = S(sid)
        d = min(a1["end"] - t0 - 0.3, 11.0)
        if d <= 0.5:
            continue
        put("ACT1_pad%d" % j, t0, low_drone(hz(38), d, 0.011, att=1.2, rel=1.6, seed=720 + j), pan=0.0)
    # 主题完整陈述一次：低音提琴（第一幕核心）
    put("ACT1_theme", S("ACT1_04") - 0.4, cello_phrase(THEME_MIN, 0.028, seed=740, brightness=0.50), pan=-0.10)
    # 判决句前：低音提琴只剩长音；判决后主题前半再现（低八度）
    put("ACT1_theme2", S("ACT1_09") + 0.4,
        cello_phrase([(0, 50, 2.0), (2, 53, 1.5), (3.5, 57, 1.5), (5, 60, 2.5)], 0.020,
                     seed=750, brightness=0.44), pan=0.10)
    # 小账本开口时：极轻的钢琴点（B3/A3）
    put("ACT1_piano1", S("ACT1_06") + 0.2, piano(hz(59), 2.4, 0.016, seed=760), pan=0.10)
    put("ACT1_piano2", S("ACT1_08") + 0.2, piano(hz(57), 2.4, 0.014, seed=761), pan=-0.10)
    put("ACT1_piano3", S("ACT1_11") + 0.1, piano(hz(62), 2.8, 0.016, seed=762), pan=0.0)
    # 老规矩「这叫不算账」：一记低音提琴短弓
    put("ACT1_bow", S("ACT1_10") + 0.1, bowed(hz(38), 1.6, 0.024, att=0.06, rel=0.8, seed=770), pan=0.0)

    # ============================================================ 第二幕 57.3–97.0（主题 + muted pulse + 钢琴分解）
    a2a = a2["start"]
    put("ACT2_drone", a2a, low_drone(hz(26), a2["end"] - a2a, 0.013, att=1.4, rel=1.4, seed=800), pan=0.0)
    # Dm Bb F C（每个和弦约 9.5s，与句子锚点对齐）
    a2_prog = [("ACT2_01", "Dm", 9.6), ("ACT2_03", "Bb", 9.0), ("ACT2_06", "F", 9.0),
               ("ACT2_08", "C", 8.0), ("ACT2_10", "Dm", 6.0)]
    for j, (sid, name, d) in enumerate(a2_prog):
        t0 = S(sid) - 0.10
        d = min(d, a2["end"] - t0 - 0.2)
        if d <= 0.5:
            continue
        put("ACT2_pad_%s" % name, t0, strings(ch(name)[1:], d, 0.0075, att=1.2, rel=1.6,
                                               seed=820 + j, cutoff=5), pan=0.0)
        put("ACT2_root_%s" % name, t0, low_drone(hz(CHORDS[name][0]), min(d, 7.0), 0.012,
                                                 att=0.8, rel=1.2, seed=850 + j), pan=0.0)
    # muted pulse：60 BPM 每拍一下，第二幕推进；AC T2_05 后加密到每半拍（数字逼近）
    tp = a2["start"] + 0.4
    k = 0
    while tp < S("ACT2_05") - 0.2:
        put("ACT2_pulse%d" % k, tp, muted_pulse(0.024 if k % 4 else 0.030, seed=900 + k), pan=0.0)
        tp += BEAT
        k += 1
    while tp < a2["end"] - 0.8:
        put("ACT2_pulse%d" % k, tp, muted_pulse(0.018 if k % 2 else 0.024, seed=900 + k), pan=0.0)
        tp += BEAT * 0.5
        k += 1
    # 钢琴八分音符分解：从「管十个人」式的数字段开始，密度递增
    arp_sets = {"Dm": [62, 65, 69, 74], "Bb": [58, 62, 65, 70], "F": [57, 60, 65, 69],
                "C": [60, 64, 67, 72]}
    prog_by_t = [(S("ACT2_01"), "Dm"), (S("ACT2_03"), "Bb"), (S("ACT2_06"), "F"),
                 (S("ACT2_08"), "C"), (S("ACT2_10"), "Dm")]
    for (t0, name) in prog_by_t:
        t1 = min(t0 + 9.2, a2["end"] - 0.5)
        notes = arp_sets[name]
        t = t0 + 0.2
        i = 0
        while t < t1:
            m = notes[[0, 1, 2, 3, 2, 1][i % 6]] + (12 if i % 6 in (3, 4) else 0)
            g = 0.013 if t < S("ACT2_05") else (0.016 if t < S("ACT2_09") else 0.011)
            put("ACT2_arp_%d_%d" % (int(t0), i), t, piano(hz(m), 1.4, g, seed=950 + i), pan=0.16 if i % 2 else -0.16)
            t += BEAT * 0.5
            i += 1
    # 还差九百九十三台：脉冲停、留一条低音，让数字自己站住
    put("ACT2_stop_low", S("ACT2_09") + 0.10, low_drone(hz(38), 3.4, 0.016, att=0.5, rel=1.4, seed=980), pan=0.0)
    put("ACT2_bow", S("ACT2_11") + 0.20, bowed(hz(50), 2.6, 0.018, att=0.08, rel=1.0, seed=981), pan=0.0)

    # ============================================================ 第三幕 98.6–133.5（同一主题转 D 大调）
    a3a = a3["start"]
    put("ACT3_drone", a3a, low_drone(hz(38), a3["end"] - a3a, 0.010, att=1.6, rel=1.6, seed=1000), pan=0.0)
    a3_prog = [("ACT3_01", "D", 8.0), ("ACT3_03", "Bm", 9.0), ("ACT3_05", "G", 9.0),
               ("ACT3_07", "A_maj", 8.0), ("ACT3_09", "D", 9.0)]
    for j, (sid, name, d) in enumerate(a3_prog):
        t0 = S(sid) - 0.10
        d = min(d, a3["end"] - t0 - 0.2)
        if d <= 0.5:
            continue
        put("ACT3_strL_%s" % name, t0, strings(ch(name), d, 0.0095, att=1.2, rel=1.8,
                                                seed=1020 + j, cutoff=6), pan=-0.34)
        put("ACT3_strR_%s" % name, t0 + 0.04, strings(ch(name), d, 0.0082, att=1.4, rel=1.8,
                                                       seed=1050 + j, cutoff=6), pan=0.34)
        put("ACT3_root_%s" % name, t0, low_drone(hz(CHORDS[name][0]), min(d, 6.0), 0.011,
                                                 att=0.8, rel=1.2, seed=1080 + j), pan=0.0)
    # 同一主题转大调：大提琴 + 钢琴同时陈述（「改判」的色彩）
    put("ACT3_theme_cello", S("ACT3_03") - 0.3,
        cello_phrase(THEME_MAJ, 0.022, seed=1100, brightness=0.62), pan=-0.14)
    for i, (off, m, d) in enumerate(THEME_MAJ[:6]):
        put("ACT3_theme_pno%d" % i, S("ACT3_03") - 0.3 + off * BEAT,
            piano(hz(m + 12), d * BEAT + 1.2, 0.014, seed=1120 + i), pan=0.18)
    # 第三幕脉冲退到二分音符（更稳，不再推进）
    tp = a3["start"] + 0.5
    k = 0
    while tp < a3["end"] - 0.8:
        put("ACT3_pulse%d" % k, tp, muted_pulse(0.014, seed=1150 + k), pan=0.0)
        tp += BEAT * 2.0
        k += 1
    # 「这局，平」：一记低音提琴长音 + 钢琴高音，落平
    put("ACT3_flat_bow", S("ACT3_11") + 0.1, bowed(hz(38), 3.2, 0.020, att=0.15, rel=1.6, seed=1170), pan=0.0)
    put("ACT3_flat_pno", S("ACT3_11") + 0.2, piano(hz(74), 3.4, 0.014, seed=1171), pan=0.10)

    # ============================================================ 第四幕 135.1–184.4（主题回落：只剩单音钢琴）
    a4a = a4["start"]
    put("ACT4_drone", a4a, low_drone(hz(26), a4["end"] - a4a, 0.011, att=2.0, rel=1.8, seed=1200), pan=0.0)
    put("ACT4_drone2", a4a + 0.5, low_drone(hz(38), a4["end"] - a4a - 0.5, 0.007, att=2.2, rel=1.8, seed=1201), pan=0.0)
    # 单音钢琴：一句一音（主题音高的零散回声），越到后面越稀
    a4_pno = [("ACT4_02", 0.4, 74, 3.0), ("ACT4_03", 0.5, 72, 2.8), ("ACT4_04", 0.5, 69, 2.8),
              ("ACT4_05", 0.3, 65, 2.6), ("ACT4_07", 0.4, 64, 2.8), ("ACT4_09", 0.4, 62, 3.0),
              ("ACT4_10", 0.5, 69, 2.6), ("ACT4_12", 0.5, 62, 3.6)]
    for i, (sid, off, m, dur) in enumerate(a4_pno):
        put("ACT4_piano%d" % i, S(sid) + off, piano(hz(m), dur, 0.016 - 0.0008 * i, seed=1220 + i),
            pan=0.12 if i % 2 else -0.12)
    # 全片最重一句：「是账本背后的东西，变了」——低音提琴只拉一个音，不铺和声
    put("ACT4_heavy", S("ACT4_11") + 0.2, bowed(hz(38), 3.4, 0.020, att=0.30, rel=1.6, seed=1240), pan=0.0)
    put("ACT4_heavy_low", S("ACT4_12") + 0.3, low_drone(hz(26), 4.2, 0.014, att=0.6, rel=1.8, seed=1241), pan=0.0)

    # ============================================================ 收束 186.0–219.7（主题完整再现一次，然后停）
    cla = cl["start"]
    put("CLOSE_drone", cla, low_drone(hz(26), min(22.0, cl["end"] - cla), 0.012, att=1.2, rel=2.0, seed=1300), pan=0.0)
    cl_prog = [("CLOSE_01", "Dm", 6.0), ("CLOSE_03", "Bb", 5.5), ("CLOSE_04", "F", 5.0),
               ("CLOSE_05", "C", 5.0), ("CLOSE_06", "Dm", 6.0), ("CLOSE_08", "Dmadd9", 6.0)]
    for j, (sid, name, d) in enumerate(cl_prog):
        t0 = S(sid) - 0.10
        d = min(d, cl["end"] - t0 - 0.2)
        if d <= 0.5:
            continue
        put("CLOSE_strL_%s" % name, t0, strings(ch(name)[1:], d, 0.0105, att=1.3, rel=2.0,
                                                 seed=1320 + j, cutoff=6), pan=-0.36)
        put("CLOSE_strR_%s" % name, t0 + 0.04, strings(ch(name)[1:], d, 0.0092, att=1.5, rel=2.0,
                                                        seed=1350 + j, cutoff=6), pan=0.36)
        put("CLOSE_root_%s" % name, t0, low_drone(hz(CHORDS[name][0]), min(d, 5.0), 0.012,
                                                  att=0.8, rel=1.4, seed=1380 + j), pan=0.0)
    # 完整再现：低音提琴陈述主题一次（从收束第一句开始）
    put("CLOSE_theme_cello", S("CLOSE_01") + 0.15,
        cello_phrase(THEME_MIN, 0.026, seed=1400, brightness=0.55), pan=-0.10)
    # 弦乐在高位衬主题的长音（八度 + 五度）
    for i, (off, midi, d) in enumerate([(0, 74, 6), (6, 77, 4), (10, 81, 4), (14, 74, 6)]):
        put("CLOSE_str_top%d" % i, S("CLOSE_01") + 0.20 + off * BEAT,
            strings([hz(midi)], d * BEAT, 0.0075, att=1.2, rel=1.8, seed=1420 + i), pan=0.0)
    # 钢琴逐句点亮主题（收束的「完整再现」由三种音色叠成）
    for i, (sid, off, m) in enumerate([("CLOSE_02", 0.3, 65), ("CLOSE_04", 0.3, 69),
                                       ("CLOSE_06", 0.3, 72), ("CLOSE_08", 0.4, 70)]):
        put("CLOSE_piano%d" % i, S(sid) + off, piano(hz(m), 3.2, 0.016, seed=1440 + i), pan=0.10)
    # 最后一个长音：Dm(add9)，到「只有不断被重新判决的技术」后停
    tail = S("CLOSE_09") - 0.2
    put("CLOSE_final", tail, strings([hz(50), hz(53), hz(57), hz(62), hz(64)], 16.0,
                                     0.0105, att=1.0, rel=6.0, seed=1460), pan=0.0)
    put("CLOSE_final_cello", tail, bowed(hz(38), 15.0, 0.016, att=0.6, rel=6.0, seed=1461), pan=0.0)
    put("CLOSE_final_piano", S("CLOSE_10") + 0.3, piano(hz(62), 6.0, 0.014, seed=1462), pan=0.0)

    # 底噪（分块 pink）：只在有音乐的段落托一层空气
    air_t = [0.0, 0.35, 2.0, total]
    air_v = [0.0010, 0.0015, 0.0013, 0.0009]
    bs, ov = SR * 2, SR // 4
    for chn in range(2):
        pos, k = 0, 0
        while pos < N:
            L = min(bs + ov, N - pos)
            x = band_noise(L, 30, 5000, seed=3500 + chn * 97 + k, decay=0, tilt=-0.5)
            w = np.ones(L, dtype=F32)
            na = min(ov, L)
            w[:na] = np.linspace(0.0, 1.0, na, endpoint=False, dtype=F32)
            if pos + L < N:
                w[-ov:] = np.linspace(1.0, 0.0, ov, endpoint=False, dtype=F32)
            amp = np.interp(np.arange(pos, pos + L) / SR, air_t, air_v).astype(F32)
            mix[chn, pos:pos + L] += x * w * amp
            pos += bs
            k += 1

    # 混响（分块卷积 + 低切 IR，能量归一，wet 0.26；比 ep05 稍湿，配合「房间/判决」）
    ir = make_ir(2.0)
    for chn in range(2):
        send = mix[chn].copy()
        fft_conv_add(mix[chn], send, ir[chn], gain=0.26, block=1 << 17)
        del send
    del ir

    # ---------------------------------------------------------- 人工调度曲线
    def _win(t0, t1, level, ramp=0.40):
        return (max(0.0, t0), min(total, t1), level, ramp)

    gates = [
        # 第一幕判决句前退开，让「这不是观点」干出来
        _win(S("ACT1_05") - 0.6, E("ACT1_05") + 0.35, 0.45),
        # 第二幕「还差九百九十三台」：脉冲已停，音乐再退一层
        _win(S("ACT2_09") - 0.3, E("ACT2_09") + 0.4, 0.55),
        _win(S("ACT2_11") - 0.2, E("ACT2_11"), 0.72),
        # 第三幕「这局，平」留白
        _win(S("ACT3_11") - 0.2, E("ACT3_11") + 0.5, 0.60),
        # 第四幕：整体抽空；最重一句再退
        _win(S("ACT4_01"), E("ACT4_10"), 0.72),
        _win(S("ACT4_11") - 0.2, E("ACT4_12") + 0.6, 0.55),
        # 收束主题再现后 **停**：最后一句结束 → 真静默（片尾声明口播在干声上）
        _win(E("CLOSE_10") + 1.4, total - 0.05, 0.0, 1.2),
    ]
    GATE_T, GATE_V = [0.0], [1.0]
    for t0, t1, lv, ramp in gates:
        if t1 <= t0:
            continue
        GATE_T += [max(0.0, t0 - ramp), t0, t1, min(total, t1 + ramp)]
        GATE_V += [1.0, lv, lv, 1.0]
    GATE_T.append(total)
    GATE_V.append(0.0)
    assert len(GATE_T) == len(GATE_V), "gate points mismatch"
    apply_curve(mix, GATE_T, GATE_V)

    # 峰值归一（留 ~7.5dB 余量）
    peak = 0.0
    for pos in range(0, N, SR):
        peak = max(peak, float(np.max(np.abs(mix[:, pos:pos + SR]))))
    target_peak = 0.42
    scale = F32(target_peak / max(peak, 1e-9))
    for pos in range(0, N, SR):
        mix[:, pos:pos + SR] *= scale
    rms = float(np.sqrt(np.mean(mix.astype(np.float64) ** 2)))

    meta = dict(
        total=total, sample_rate=SR, n_events=len(events),
        peak_dbfs=round(20 * np.log10(max(target_peak, 1e-9)), 2),
        rms_dbfs=round(20 * np.log10(max(rms, 1e-9)), 2),
        theme="单一主题变奏「判决主题」——一场持续六年的技术判决，和它自己的判决",
        key=("D minor (main) -> D minor Dm-Bb-F-C (ACT2) -> D major D-Bm-G-A (ACT3) "
             "-> D minor (ACT4) -> D minor Dm(add9) final (CLOSE)"),
        tempo_bpm=BPM,
        motif=("判决主题（原创，16 拍 @60BPM）：D4 F4 A4 | C5 A4 F4 | E4 G4 Bb4 | A4 D4；"
               "第三幕同一主题转 D 大调（F#/C#/B）；主奏：低音提琴 arco + 软钢琴 + 弦乐群 + muted pulse"),
        sections={}, gate_windows=[], events=events)
    for name, a, b in [("cold_open", 0.0, cold), ("COLD", c["start"], c["end"]),
                       ("ACT1", a1["start"], a1["end"]), ("ACT2", a2["start"], a2["end"]),
                       ("ACT3", a3["start"], a3["end"]), ("ACT4", a4["start"], a4["end"]),
                       ("CLOSE", cl["start"], cl["end"]),
                       ("outro_silence", E("CLOSE_10") + 1.6, total)]:
        i0, i1 = int(a * SR), min(N, int(b * SR))
        if i1 > i0:
            r = float(np.sqrt(np.mean(mix[:, i0:i1].astype(np.float64) ** 2)))
            meta["sections"][name] = round(20 * np.log10(max(r, 1e-12)), 2)
    for i in range(0, len(GATE_T) - 1):
        if GATE_V[i] < 0.15 and GATE_V[i + 1] < 0.15:
            meta["gate_windows"].append([round(GATE_T[i], 3), round(GATE_T[i + 1], 3)])
    if verbose:
        print("[music] peak=%.2f dBFS rms=%.2f dBFS events=%d" % (
            meta["peak_dbfs"], meta["rms_dbfs"], len(events)))
        for k, v in meta["sections"].items():
            print("    %-14s %7.1f dBFS" % (k, v))
        print("[music] music-silence windows:", meta["gate_windows"])
    return mix, meta


def write_wav24(path, x, sr=SR, chunk=1 << 19):
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
