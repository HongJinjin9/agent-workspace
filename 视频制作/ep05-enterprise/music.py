#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep05 原创配乐（纯 numpy 合成，无外部曲库 / 无外部采样，版权干净）
====================================================================
主题：一张越织越密的网 —— 时钟滴答 / 齿轮 / 低频脉冲 / 弦乐反复拉起又落下
- **声音记忆点 = 「收网动机」**：一个持续低音 A 上的三音小细胞，音程一次次收窄
  （E5→A4 纯五度 → D5→A4 纯四度 → C5→A4 小三度 → B4→A4 大二度 → A4→A4 同度）。
  它不是 ep01–04 任何一期的动机：第 05 期用「音程收窄」直接对应「网越织越密」。
- **时钟滴答**：72 BPM 的 tick-tock（左右交替、2050/2600Hz 共振窄脉冲），是全片的时间骨。
  S2 的脉冲密度随节点数 3→10→20 逐级加密（2 拍/拍/半拍/八分），对应关系数 n(n−1)/2。
- **齿轮**：S3 的机械下沉段用齿状 click 序列 + 低音级进下行（A→G#→G→F#→F→E），
  循环句加速到八分音符，像越咬越紧的传动。
- **S5 弦乐**：同一条上行+下落的弦乐 swell 重复 4 次，峰值逐次衰减（1.0→0.72→0.50→0.30），
  对应 74%→43% 的变革支持率与「幅度一次比一次小」。
- 调性：A 小调（主调，S1–S3）→ S4 降至 A 弗里几亚（Bb 邻音）几乎抽空 → S5 弦乐在
  F–C–G–Am 上反复拉起又落下 → S6 回 A 小调，片尾落 C 大调（关系大调）收束。
  与第 04 期（E 小调→F 小调→G 大调、64BPM 心跳）不同调、不同速度、不同动机、不同音色。

段落调度（不是全片铺满，关键句前人工停乐/退开）：
  cold open 极稀疏（两次 tick + 低 drone）→ S1 走廊脉冲 + 一句一音稀疏钢琴 →
  S2 时钟脉冲随节点加密 + Am–F–C–G pad → S3 齿轮机械 + 低音级进下行 + 循环加速 →
  S4 几乎抽空（只剩极慢低频结构性搏动 + 一丝网线的张力）→ S5 弦乐反复拉起又落下 →
  S6 收网动机回归、弦乐收束到 C 大调、tick 渐隐。

输出 work/music.wav（48kHz 立体声 24bit，长度 = timeline total，峰值 ≈ -7.5dBFS）
     work/music_meta.json
内存受限（cgroup 4 CPU / 6GB 与其它 Agent 共享）：float32 + 分块 FFT/分块写盘。
用法：python3 music.py [--dry]
"""
import argparse
import json
import math
import os

import numpy as np

ROOT = "/app/vedio/ep05-enterprise"
SR = 48000
TIMELINE_FULL = os.path.join(ROOT, "work", "timeline_audio_full.json")
MUSIC_WAV = os.path.join(ROOT, "work", "music.wav")
MUSIC_META = os.path.join(ROOT, "work", "music_meta.json")
F32 = np.float32

BPM = 72.0                  # 主速度：时钟滴答 72 BPM（1.2 Hz 的「秒针」感）
BEAT = 60.0 / BPM           # 0.8333 s
S4BPM = 50.0                # S4 几乎抽空：更慢的结构性搏动
S4BEAT = 60.0 / S4BPM       # 1.2 s


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
def tick(amp, seed=0, tone=2050.0, dur=0.045):
    """时钟「滴/答」：极短带限噪声 + 一条窄带共振，左右声像由调用方决定。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    click = band_noise(n, 1200, 9000, seed, decay=0.0035) * 0.9
    body = np.sin(2 * np.pi * tone * t) * np.exp(-t / 0.010)
    body += 0.35 * np.sin(2 * np.pi * tone * 1.53 * t + 0.4) * np.exp(-t / 0.006)
    sig = click * env_ar(n, 0.0005, 0.010) + body
    return (sig * amp).astype(F32)


def gear_click(amp, seed=0, f=620.0):
    """齿轮齿 click：金属窄带 + 低次共振，84–120ms，比 tick 更「钝」。"""
    n = int(0.10 * SR)
    t = np.arange(n) / SR
    sig = band_noise(n, 700, 4800, seed, decay=0.010) * 0.8
    sig += 0.7 * np.sin(2 * np.pi * f * t) * np.exp(-t / 0.028)
    sig += 0.4 * np.sin(2 * np.pi * f * 1.48 * t + 0.7) * np.exp(-t / 0.018)
    sig += 0.5 * np.sin(2 * np.pi * f * 0.5 * t) * np.exp(-t / 0.040)
    return (sig * env_ar(n, 0.001, 0.030) * amp).astype(F32)


def ratchet(dur, amp, seed=0, rate=8.0, f=560.0):
    """齿轮组：按 rate 次/秒排一串渐弱齿 click（机械传动感）。"""
    n = int(dur * SR)
    sig = np.zeros(n, dtype=np.float64)
    rng = np.random.default_rng(seed)
    t = 0.0
    k = 0
    while t < dur - 0.02:
        c = gear_click(1.0, seed + k, f * (1.0 + 0.05 * (rng.random() - 0.5)))
        i0 = int(t * SR)
        m = min(len(c), n - i0)
        if m > 0:
            sig[i0:i0 + m] += c[:m] * (0.75 + 0.25 * rng.random())
        t += (1.0 / rate) * (0.85 + 0.30 * rng.random())
        k += 1
    return (sig * amp).astype(F32)


def piano(f0, dur, amp, seed=0, bright=1.0):
    """加法合成钢琴（本期音色：击弦更亮、衰减稍长，与 ep04 的钢琴音色区分）。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    tau0 = float(np.clip(3.9 * (220.0 / f0) ** 0.5, 0.55, 7.5))
    for k, a, tk in [(1.0, 1.0, 1.0), (2.002, 0.36, 0.62), (3.006, 0.16, 0.42),
                     (4.016, 0.075, 0.30), (5.04, 0.034, 0.22), (6.07, 0.016, 0.17),
                     (7.12, 0.008, 0.13), (9.2, 0.004, 0.10)]:
        if f0 * k > 9500:
            break
        det = 1.0 + 0.0005 * (rng.random() - 0.5)
        sig += (a * bright) * np.sin(2 * np.pi * f0 * k * det * t
                                     + rng.random() * 6.28318
                                     + 0.0012 * np.sin(2 * np.pi * 0.5 * t)) \
            * np.exp(-t / (tau0 * tk))
    nn = min(n, int(0.016 * SR))
    if nn > 0:
        sig[:nn] += band_noise(nn, 1100, 6200, seed + 7, decay=0.0030) * 0.13
    sig *= env_ar(n, 0.0035, min(0.5, dur * 0.35))
    return (sig * amp).astype(F32)


def pad(freqs, dur, amp, att=1.2, rel=1.7, cutoff=1500, seed=0, detune=0.0015):
    """暖 pad：有限谐波 + 群失谐 + 慢呼吸（S2/S6 的和声底色）。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    for i, f in enumerate(freqs):
        d = detune * (1 if i % 2 == 0 else -1)
        for k in range(1, max(1, int(cutoff / max(f, 30.0))) + 1):
            sig += (1.0 / k ** 1.75) * np.sin(2 * np.pi * f * k * (1 + d) * t
                                             + rng.random() * 6.28318)
    sig *= 1.0 + 0.07 * np.sin(2 * np.pi * 0.071 * t + rng.random() * 6.28)
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def low_drone(f0, dur, amp, att=1.3, rel=1.5, wob=0.14, seed=0):
    """低频 drone：1/2/3 次谐波 + 极慢幅度起伏（机械底噪/楼层重量感）。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = (np.sin(2 * np.pi * f0 * t) + 0.42 * np.sin(2 * np.pi * 2 * f0 * t + 0.6)
           + 0.16 * np.sin(2 * np.pi * 3 * f0 * t + 1.7)
           + 0.09 * np.sin(2 * np.pi * 4 * f0 * t + 2.4))
    sig *= 1.0 + wob * np.sin(2 * np.pi * (0.19 + 0.03 * rng.random()) * t + 0.4)
    sig += band_noise(n, 25, 260, seed + 1, decay=0, tilt=-0.4) * 0.05
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def sub_thump(amp, seed=0, f_hi=64.0, f_lo=38.0, dur=0.85, tau=0.30):
    """结构性低频搏动（S4「只剩心跳」）：比 ep04 的心跳更慢、更钝、无 dub。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f_hi * np.exp(-t / 0.07) + f_lo * (1.0 - np.exp(-t / 0.07))
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(ph) * np.exp(-t / tau)
    sig += 0.30 * np.sin(2 * ph + 0.4) * np.exp(-t / (tau * 0.5))
    sig += 0.10 * band_noise(n, 120, 900, seed + 2, decay=0.018)
    return (sig * env_ar(n, 0.0015, 0.18) * amp).astype(F32)


def footstep(amp, seed=0):
    """走廊脚步（极轻，S1 的「走廊」空间感）：一次钝低频 + 鞋底摩擦噪声。"""
    n = int(0.30 * SR)
    t = np.arange(n) / SR
    f = 88.0 * np.exp(-t / 0.03) + 52.0 * (1.0 - np.exp(-t / 0.03))
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(ph) * np.exp(-t / 0.075) + 0.25 * band_noise(n, 300, 2600, seed, decay=0.020)
    return (sig * env_ar(n, 0.002, 0.10) * amp).astype(F32)


def strings_swell(freqs, dur, amp, att=1.4, rel=2.2, rise=0.55, seed=0, vib=4.4,
                  gliss_semi=1.0, fall_ratio=0.55):
    """S5 弦乐「被拉起又落下」：音量先涨后落，音高在 rise 段前上滑 gliss_semi 半音再落下。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    u = np.clip(t / dur, 0, 1)
    rng = np.random.default_rng(seed)
    # 音高轮廓：0→rise 上滑到 +gliss，rise→1 落回 0（用半音表示）
    semi = np.where(u < rise,
                    gliss_semi * np.sin(np.pi * 0.5 * (u / rise)),
                    gliss_semi * np.cos(np.pi * 0.5 * np.clip((u - rise) / (1.0 - rise), 0, 1)))
    vib_lfo = 0.0045 * np.sin(2 * np.pi * vib * t)
    sig = np.zeros(n, dtype=np.float64)
    for i, f in enumerate(freqs):
        for k in range(1, 8):
            fr = f * (2.0 ** (semi / 12.0)) * k * (1.0 + 0.0016 * ((k % 3) - 1) + 0.0006 * i)
            ph = 2 * np.pi * np.cumsum(fr) / SR
            sig += (0.85 / k) * np.sin(ph + vib_lfo * k + rng.random() * 6.28318)
    # 拉起-落下的幅度包络：涨到 rise 处，之后指数落下
    rel_u = np.clip((u - rise) / (1.0 - rise), 0.0, 1.0)
    amp_env = np.where(u < rise, (u / max(rise, 1e-6)) ** 1.6,
                       (1.0 - (1.0 - fall_ratio) * rel_u ** 0.9))
    sig *= amp_env
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def net_tension(dur, amp, seed=0):
    """「网线绷紧」的高频持续张力：极窄带高音 + 缓慢起伏，只在 S2/S4 托一层。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    sig = band_noise(n, 2600, 7800, seed, decay=0, tilt=-0.25) * 0.5
    sig += 0.30 * np.sin(2 * np.pi * 3136.0 * t + 0.3 * np.sin(2 * np.pi * 0.13 * t))
    sig += 0.16 * np.sin(2 * np.pi * 4710.0 * t + 0.7 * np.sin(2 * np.pi * 0.09 * t))
    sig *= 1.0 + 0.35 * np.sin(2 * np.pi * 0.11 * t + 1.1)
    return (sig * env_ar(n, 1.2, 1.6) * amp).astype(F32)


def cello_line(freqs, t0_dur, amp, period, seed=0, note_dur=0.55):
    """S3 低音级进（机械下行）：短促低音 + 轻微擦弦噪声。"""
    n = int(t0_dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    sig = np.zeros(n, dtype=np.float64)
    k, pos = 0, 0.0
    rng = np.random.default_rng(seed)
    while pos < t0_dur - 0.02:
        f = freqs[k % len(freqs)]
        m = min(int(note_dur * SR), n - int(pos * SR))
        if m <= 8:
            break
        tt = np.arange(m) / SR
        note = (np.sin(2 * np.pi * f * tt) + 0.34 * np.sin(2 * np.pi * 2 * f * tt + 0.3)
                + 0.14 * np.sin(2 * np.pi * 3 * f * tt + 1.1))
        note += 0.06 * band_noise(m, 180, 1600, seed + k, decay=0.05)
        note *= env_ar(m, 0.010, note_dur * 0.6)
        i0 = int(pos * SR)
        sig[i0:i0 + m] += note
        k += 1
        pos += period
    return (sig * amp).astype(F32)


def make_ir(dur=1.8, seed=11, hp=130.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ir = np.zeros((2, n), dtype=F32)
    for ch in range(2):
        rng = np.random.default_rng(seed + ch * 37)
        X = np.fft.rfft(rng.standard_normal(n).astype(F32))
        f = np.fft.rfftfreq(n, 1.0 / SR)
        lo = np.maximum(f, 1.0)
        y = np.fft.irfft(X * (1.0 / (1.0 + (lo / 3200.0) ** 2)), n).astype(F32)
        y *= np.exp(-t / 0.50).astype(F32)
        for dly, g in ((0.013, 0.55), (0.023, 0.40), (0.037, 0.30), (0.053, 0.22), (0.071, 0.16)):
            i = int(dly * SR)
            if i < n:
                y[i] += g * (1 if ch == 0 else 0.85)
        y = fft_hp_small(y, hp)
        ir[ch] = y / (np.sqrt(np.sum(y.astype(np.float64) ** 2)) + 1e-12)
    return ir


# ---------------------------------------------------------------- 和声 / 动机
# A 小调（主调）—— 与 ep04 的 E 小调不同
CHORDS = {
    "Am":  [45, 52, 57, 60],       # A2 E3 A3 C4
    "F":   [41, 48, 53, 57],       # F2 C3 F3 A3
    "C":   [36, 43, 48, 52],       # C2 G2 C3 E3
    "G":   [43, 50, 55, 59],       # G2 D3 G3 B3
    "Dm":  [38, 45, 50, 53],       # D2 A2 D3 F3
    "E":   [40, 47, 52, 56],       # E2 B2 E3 G#3
    "Bb":  [46, 53, 58, 62],       # Bb2 F3 Bb3 D4（S4 弗里几亚邻音）
    "Cmaj7": [36, 43, 48, 52, 59],
    "Amadd9": [45, 52, 57, 60, 64],
    "Fmaj7": [41, 48, 53, 57, 60],
}

# 「收网动机」：A 持续音上，上方音一次次向 A 收窄（P5→P4→m3→M2→同度）
# 单位：相对起点秒偏移 / MIDI / 时长 / 力度
MOTIF_CLOSE = [
    (0.00, 76, 1.30, 0.072),   # E5
    (1.25, 69, 2.00, 0.078),   # A4（纯五度收）
    (2.50, 74, 1.20, 0.066),   # D5
    (3.75, 69, 2.00, 0.074),   # A4（纯四度收）
    (5.00, 72, 1.10, 0.062),   # C5
    (6.25, 69, 2.00, 0.070),   # A4（小三度收）
    (7.50, 71, 1.10, 0.058),   # B4
    (8.75, 69, 2.60, 0.066),   # A4（大二度收 → 同度）
]
MOTIF_OPEN = [
    (0.00, 69, 1.30, 0.070),   # A4
    (1.25, 72, 1.30, 0.066),   # C5
    (2.50, 76, 1.60, 0.070),   # E5
    (4.10, 74, 1.20, 0.064),   # D5
    (5.35, 72, 1.20, 0.062),   # C5
    (6.60, 71, 2.40, 0.068),   # B4
]

# 低音级进下行（S3 机械下沉）：A2 → G#2 → G2 → F#2 → F2 → E2 → Eb2 → D2
DESCENT = [45, 44, 43, 42, 41, 40, 39, 38]


def load_tl():
    with open(TIMELINE_FULL, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 调度 / 渲染
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
    s1, s2, s3, s4, s5, s6 = (segs[k] for k in ("S1", "S2", "S3", "S4", "S5", "S6"))

    def tick_pair(t0, amp=0.020, gain=1.0, seed=0, dur_gap=BEAT):
        """tick-tock：左右交替，两次之间隔一个 dur_gap×比例。"""
        put("tick_L_%d" % seed, t0, tick(amp, seed=seed, tone=2050.0), pan=-0.35, gain=gain)
        put("tick_R_%d" % seed, t0 + dur_gap * 0.5, tick(amp * 0.86, seed=seed + 1, tone=2600.0),
            pan=0.35, gain=gain)

    # ============================================================ cold open 0–2.5
    put("cold_drone", 0.00, low_drone(hz(33), cold + 0.4, 0.030, att=0.9, rel=0.6, seed=600), pan=0.0)
    tick_pair(0.35, amp=0.030, seed=600, dur_gap=BEAT * 0.9)
    put("cold_tension", 0.50, net_tension(cold - 0.2, 0.006, seed=610), pan=0.0)
    put("cold_piano", 1.45, piano(hz(69), 3.4, 0.062, seed=620), pan=-0.10)
    put("cold_piano2", 1.50, piano(hz(76), 3.0, 0.040, seed=621), pan=0.18)

    # ============================================================ S1 走廊 + 稀疏钢琴 2.5–~
    s1a = s1["start"] + 0.15
    put("S1_drone", s1a, low_drone(hz(45), s1["end"] - s1a, 0.024, att=1.2, rel=1.0, seed=700), pan=0.0)
    put("S1_sub", s1a + 0.1, low_drone(hz(33), s1["end"] - s1a - 0.1, 0.013, att=1.4, rel=1.0, seed=701), pan=0.0)
    # 走廊脚步：每 2 拍一次，很轻
    ft = s1["start"] + 0.9
    k = 0
    while ft < s1["end"] - 0.8:
        put("S1_step%d" % k, ft, footstep(0.016 if k % 2 else 0.020, seed=710 + k), pan=-0.18 if k % 2 else 0.15)
        ft += 2.0 * BEAT
        k += 1
    # 稀疏钢琴：一句一音（收网动机的上方音散落，最后收在 A）
    s1_pno = [("S1_01", 0.20, 76, 3.0, 0.058), ("S1_02", 0.15, 74, 2.8, 0.052),
              ("S1_03", 0.15, 72, 3.0, 0.054), ("S1_04", 0.20, 71, 2.8, 0.050),
              ("S1_05", 0.10, 69, 2.6, 0.048), ("S1_06", 0.15, 69, 3.6, 0.058)]
    for i, (sid, off, m, dur, amp) in enumerate(s1_pno):
        put("S1_piano%d" % (i + 1), S(sid) + off, piano(hz(m), dur, amp, seed=730 + i), pan=0.08 if i % 2 else -0.08)
    # 最后一句「这只是大本身带的病」：低音到 A1 + 一次 tick
    put("S1_lastlow", S("S1_06") + 0.20, low_drone(hz(33), 3.2, 0.022, att=0.5, rel=1.2, seed=740), pan=0.0)
    put("S1_lasttick", S("S1_06") + 0.55, tick(0.020, seed=741, tone=2050.0), pan=-0.2)

    # ============================================================ S2 时钟脉冲加密 + pad
    # 和声：Am F C G | Am F Dm E（每 ~5s 一次，与句子锚点对齐）
    s2_prog = [("S2_01", "Am", 5.0), ("S2_02", "F", 4.6), ("S2_03", "C", 4.6),
               ("S2_04", "G", 4.6), ("S2_05", "Am", 4.8), ("S2_06", "F", 4.4),
               ("S2_07", "Dm", 4.4), ("S2_08", "E", 4.4), ("S2_09", "Am", 5.0),
               ("S2_10", "F", 4.0)]
    for j, (sid, name, d) in enumerate(s2_prog):
        t0 = S(sid) - 0.15 if j else s2["start"] + 0.2
        d = min(d, s2["end"] - t0)
        if d <= 0.4:
            continue
        put("S2_padL_%s" % name, t0, pad(ch(name)[1:], d, 0.0105, att=1.4, rel=1.8,
                                          cutoff=1250, seed=800 + j), pan=-0.36)
        put("S2_padR_%s" % name, t0 + 0.04, pad(ch(name)[1:], d, 0.0092, att=1.6, rel=1.8,
                                                 cutoff=1150, seed=830 + j), pan=0.36)
        put("S2_root_%s" % name, t0, low_drone(hz(CHORDS[name][0]), min(d, 4.6), 0.020,
                                               att=0.7, rel=0.9, seed=860 + j), pan=0.0)
    put("S2_tension", S("S2_01") + 0.4, net_tension(min(26.0, s2["end"] - S("S2_01") - 0.8),
                                                    0.0065, seed=880), pan=0.0)
    # ---- 脉冲密度：随节点数 3→10→20 逐级加密（n(n-1)/2 的听觉映射）
    def pulses(t0, t1, step, amp, seed0, tag):
        t = t0
        i = 0
        while t < t1 - 0.05:
            put("S2_pulse_%s_%d" % (tag, i), t, sub_thump(amp, seed=seed0 + i, f_hi=70.0,
                                                         f_lo=42.0, dur=0.55, tau=0.16),
                pan=0.0)
            i += 1
            t += step
        return i

    # n=3：2 拍一次；n=10：1 拍；n=20：半拍；「关系数按乘法涨」：八分音符（最密）
    pulses(S("S2_02") + 0.15, S("S2_03") - 0.15, 2.0 * BEAT, 0.042, 900, "n3")
    pulses(S("S2_03") + 0.15, S("S2_04") - 0.15, 1.0 * BEAT, 0.046, 930, "n10")
    pulses(S("S2_04") + 0.15, S("S2_05") - 0.15, 0.5 * BEAT, 0.049, 960, "n20")
    pulses(S("S2_05") + 0.10, S("S2_08") - 0.20, 0.5 * BEAT, 0.040, 1000, "explode")
    # tick 网格：n=20 起加入秒针，密度最高时 tick 与 pulse 交错
    tt = S("S2_04") + 0.15
    k = 0
    while tt < S("S2_08") - 0.15:
        put("S2_tick%d" % k, tt, tick(0.013 if k % 2 else 0.016, seed=1100 + k,
                                      tone=2050.0 if k % 2 else 2600.0), pan=-0.30 if k % 2 else 0.30)
        tt += 0.5 * BEAT
        k += 1
    # 后半：分析性段落，脉冲退回半拍/拍
    pulses(S("S2_08") + 0.10, S("S2_09") - 0.15, 2.0 * BEAT, 0.034, 1150, "analysis")
    pulses(S("S2_09") + 0.10, S("S2_10") - 0.30, 1.0 * BEAT, 0.030, 1170, "slow")
    # 收网动机第一次完整出现：「下属人数按加法涨，关系数按乘法涨」一句一音
    for i, (off, m, dur, amp) in enumerate(MOTIF_CLOSE):
        put("S2_motif%d" % (i + 1), S("S2_05") + 0.30 + off * 0.55, piano(hz(m), dur, amp * 0.92,
                                                                          seed=1200 + i), pan=-0.05)
    # 出厂设置：一记低音 + 停
    put("S2_setting", S("S2_10") + 0.20, low_drone(hz(41), 2.6, 0.024, att=0.4, rel=1.2, seed=1250), pan=0.0)
    put("S2_setting_tick", S("S2_10") + 0.55, tick(0.018, seed=1251, tone=2050.0), pan=0.0)

    # ============================================================ S3 齿轮机械 + 低音级进下行
    s3a = s3["start"] + 0.25
    put("S3_drone", s3a, low_drone(hz(41), s3["end"] - s3a, 0.020, att=1.0, rel=1.2, seed=1300), pan=0.0)
    put("S3_sub", s3a, low_drone(hz(29), s3["end"] - s3a, 0.012, att=1.2, rel=1.2, seed=1301), pan=0.0)
    # 低音级进下行（每句下降一个半音），tag 锚在句首
    desc_anchor = ["S3_03", "S3_05", "S3_07", "S3_08", "S3_09", "S3_10", "S3_11", "S3_12"]
    for j, sid in enumerate(desc_anchor):
        m = DESCENT[j]
        d = min(max(2.2, E(sid) - S(sid) + 0.6), 5.0)
        put("S3_desc%d" % j, S(sid) + 0.10, cello_line([hz(m)], d, 0.030, 1.0 * BEAT,
                                                       seed=1350 + j, note_dur=0.62), pan=-0.10)
        put("S3_desc_oct%d" % j, S(sid) + 0.10, low_drone(hz(m - 12), d, 0.014, att=0.4,
                                                          rel=0.8, seed=1380 + j), pan=0.0)
    # 齿轮：前半每拍一齿（左右交替），S3_10 起加速到半拍（越咬越紧）
    def gears(t0, t1, step, amp, seed0, tag):
        t = t0
        i = 0
        while t < t1 - 0.05:
            put("S3_gear_%s_%d" % (tag, i), t, gear_click(amp, seed=seed0 + i,
                                                          f=560.0 + 40.0 * (i % 3)),
                pan=-0.28 if i % 2 else 0.28)
            i += 1
            t += step
        return i

    gears(S("S3_02") + 0.10, S("S3_10") - 0.15, 1.0 * BEAT, 0.024, 1400, "slow")
    gears(S("S3_10") - 0.05, s3["end"] - 0.45, 0.5 * BEAT, 0.019, 1500, "fast")
    put("S3_ratchet", S("S3_09") + 0.10, ratchet(2.6, 0.020, seed=1550, rate=9.0, f=520.0), pan=-0.15)
    put("S3_ratchet2", S("S3_12") + 0.05, ratchet(3.4, 0.026, seed=1551, rate=13.0, f=480.0), pan=0.15)
    # 弦乐底：前半铺，后半（S3_09 唐斯）压低
    s3_prog = [("S3_01", "Am", 6.5), ("S3_05", "Dm", 6.0), ("S3_09", "Bb", 6.0),
               ("S3_10", "Am", 5.0), ("S3_12", "E", 4.6)]
    for j, (sid, name, d) in enumerate(s3_prog):
        t0 = S(sid) - 0.15
        d = min(d, s3["end"] - t0)
        if d <= 0.4:
            continue
        put("S3_strL_%s" % name, t0, pad(ch(name)[1:], d, 0.0085, att=1.6, rel=1.8,
                                          cutoff=1100, seed=1580 + j), pan=-0.40)
        put("S3_strR_%s" % name, t0 + 0.04, pad(ch(name)[1:], d, 0.0074, att=1.8, rel=1.8,
                                                 cutoff=1000, seed=1600 + j), pan=0.40)
    # 循环三句「复杂，就加层」：每句一记低音 + 齿轮密一档
    for j, sid in enumerate(["S3_11", "S3_12", "S3_13"]):
        put("S3_loop%d" % j, S(sid) + 0.05, sub_thump(0.030 - 0.004 * j, seed=1650 + j,
                                                     f_hi=66.0, f_lo=40.0, dur=0.7, tau=0.20), pan=0.0)

    # ============================================================ S4 几乎抽空：只剩慢搏动 + 一丝张力
    s4a = s4["start"] + 0.2
    put("S4_drone", s4a, low_drone(hz(41), s4["end"] - s4a, 0.016, att=1.5, rel=1.6, seed=1700), pan=0.0)
    put("S4_tension", s4a + 0.2, net_tension(min(20.0, s4["end"] - s4a - 0.8), 0.0045, seed=1710), pan=0.0)
    # 结构性搏动：50 BPM，一次一记，无 dub —— 比 ep04 的心跳更慢、更钝
    tb = S("S4_01") + 0.30
    k = 0
    while tb < E("S4_09") - 0.30:
        put("S4_pulse%d" % k, tb, sub_thump(0.030 if k % 3 else 0.038, seed=1750 + k,
                                            f_hi=60.0, f_lo=37.0, dur=1.05, tau=0.42), pan=0.0)
        tb += 2.4
        k += 1
    # 极稀疏钢琴：只在关键句给一个音（不是每句）
    s4_pno = [("S4_01", 0.35, 69, 3.6, 0.052), ("S4_03", 0.30, 72, 3.2, 0.048),
              ("S4_05", 0.30, 71, 3.0, 0.044), ("S4_07", 0.30, 69, 3.4, 0.050)]
    for i, (sid, off, m, dur, amp) in enumerate(s4_pno):
        put("S4_piano%d" % (i + 1), S(sid) + off, piano(hz(m), dur, amp, seed=1800 + i), pan=0.06 if i % 2 else -0.06)
    # 全片最重一锤：S4_08「这不是谁偷懒」/ S4_09「整体不理性」低频下沉
    put("S4_heavy", S("S4_08") + 0.15, low_drone(hz(31), 3.4, 0.026, att=0.35, rel=1.4, seed=1850), pan=0.0)
    put("S4_heavy2", S("S4_09") + 0.15, sub_thump(0.038, seed=1851, f_hi=54.0, f_lo=33.0,
                                                  dur=1.8, tau=0.75), pan=0.0)
    put("S4_lastlow", E("S4_09") - 0.4, low_drone(hz(29), 2.2, 0.018, att=0.4, rel=1.0, seed=1852), pan=0.0)

    # ============================================================ S5 弦乐反复拉起又落下
    s5_prog = [("S5_01", "F", 7.0), ("S5_03", "C", 6.0), ("S5_05", "G", 5.6),
               ("S5_06", "Am", 5.2), ("S5_08", "F", 5.0), ("S5_09", "G", 5.0),
               ("S5_10", "C", 6.0), ("S5_11", "Am", 5.0)]
    for j, (sid, name, d) in enumerate(s5_prog):
        t0 = S(sid) - 0.15
        d = min(d, s5["end"] - t0)
        if d <= 0.4:
            continue
        put("S5_padL_%s" % name, t0, pad(ch(name)[1:], d, 0.0110, att=1.2, rel=1.6,
                                          cutoff=1400, seed=1900 + j), pan=-0.38)
        put("S5_padR_%s" % name, t0 + 0.04, pad(ch(name)[1:], d, 0.0098, att=1.4, rel=1.6,
                                                 cutoff=1300, seed=1930 + j), pan=0.38)
        put("S5_cello_%s" % name, t0, low_drone(hz(CHORDS[name][0] - 12), min(d, 5.5), 0.017,
                                                att=0.8, rel=1.2, seed=1960 + j), pan=0.0)
    # 4 次「拉起又落下」：峰值逐次衰减 1.0 → 0.72 → 0.50 → 0.30
    SWELL_SIDS = ["S5_01", "S5_03", "S5_06", "S5_09"]
    SWELL_AMP = [1.00, 0.72, 0.50, 0.30]
    SWELL_TOP = [76, 74, 72, 71]     # E5 D5 C5 B4（收窄，收网动机的上方音）
    for j, (sid, amp_f, top) in enumerate(zip(SWELL_SIDS, SWELL_AMP, SWELL_TOP)):
        t0 = S(sid) + 0.25
        dur = min(E(sid) - S(sid) + 2.2, 5.2)
        put("S5_swellL%d" % j, t0, strings_swell([hz(57), hz(60), hz(top)], dur,
                                                0.020 * amp_f, att=0.9, rel=1.8,
                                                rise=0.5, seed=2000 + j, gliss_semi=1.0,
                                                fall_ratio=0.55), pan=-0.42)
        put("S5_swellR%d" % j, t0 + 0.03, strings_swell([hz(57), hz(60), hz(top)], dur,
                                                       0.017 * amp_f, att=1.0, rel=1.8,
                                                       rise=0.5, seed=2020 + j, gliss_semi=1.0,
                                                       fall_ratio=0.55), pan=0.42)
        # 每次拉起时给一记低频「托」，强化「拉不动」的重量
        put("S5_lift%d" % j, t0, sub_thump(0.024 * amp_f, seed=2040 + j, f_hi=58.0,
                                           f_lo=36.0, dur=0.9, tau=0.30), pan=0.0)
    # 74%→43%：两个音高台阶（G5→E5）落在数字上
    put("S5_74", S("S5_06") + 0.55, piano(hz(79), 2.2, 0.052, seed=2060), pan=0.10)
    put("S5_43", S("S5_06") + 1.65, piano(hz(76), 2.6, 0.046, seed=2061), pan=-0.10)
    # 最后一次拉起最轻：S5_11「被装备好、被支持、被看见」只留弦乐一点尾巴
    put("S5_laststrL", S("S5_11") + 0.10, strings_swell([hz(57), hz(64)], 4.4, 0.0105,
                                                       att=1.2, rel=2.0, rise=0.45,
                                                       seed=2080, gliss_semi=0.5,
                                                       fall_ratio=0.35), pan=-0.30)
    put("S5_laststrR", S("S5_11") + 0.14, strings_swell([hz(57), hz(64)], 4.4, 0.0092,
                                                       att=1.3, rel=2.0, rise=0.45,
                                                       seed=2081, gliss_semi=0.5,
                                                       fall_ratio=0.35), pan=0.30)
    put("S5_lasttick", S("S5_11") + 1.10, tick(0.014, seed=2090, tone=2050.0), pan=0.0)

    # ============================================================ S6 收网动机回归 / C 大调收束
    s6_prog = [("S6_01", "Am", 7.0), ("S6_03", "F", 5.6), ("S6_04", "C", 5.4),
               ("S6_06", "G", 5.0), ("S6_07", "Am", 5.0), ("S6_08", "F", 5.0),
               ("S6_10", "C", 5.0), ("S6_12", "G", 4.6), ("S6_13", "F", 4.6),
               ("S6_14", "G", 4.2), ("S6_15", "Cmaj7", 9.0)]
    for j, (sid, name, d) in enumerate(s6_prog):
        t0 = S(sid) - 0.20
        d = min(d, total - t0 - 1.2)
        if d <= 0.4:
            continue
        put("S6_strL_%s" % name, t0, pad(ch(name)[1:], d, 0.0095, att=1.3, rel=2.0,
                                          cutoff=1500, seed=2100 + j), pan=-0.40)
        put("S6_strR_%s" % name, t0 + 0.04, pad(ch(name)[1:], d, 0.0084, att=1.5, rel=2.0,
                                                 cutoff=1400, seed=2130 + j), pan=0.40)
        put("S6_root_%s" % name, t0, low_drone(hz(CHORDS[name][0] - 12), min(d, 6.0), 0.016,
                                               att=0.7, rel=1.2, seed=2160 + j), pan=0.0)
    # 收网动机回归：S6_01 / S6_04 / S6_07 / S6_10 各一次（A→C 大调色彩逐步变亮）
    MOTIF_S6 = [
        ("S6_01", MOTIF_CLOSE, 0.25, 2200, -0.06),
        ("S6_04", MOTIF_OPEN, 0.20, 2240, 0.06),
        ("S6_07", MOTIF_CLOSE, 0.20, 2280, -0.06),
        ("S6_10", MOTIF_OPEN, 0.20, 2320, 0.06),
    ]
    for tag, (sid, motif, off0, seed0, pan) in enumerate(MOTIF_S6):
        for i, (off, m, dur, amp) in enumerate(motif):
            put("S6_motif%d_%d" % (tag + 1, i + 1), S(sid) + off0 + off,
                piano(hz(m), dur, amp * 1.05, seed=seed0 + i), pan=pan)
    # 第二方向「少加层，多加桥」：加入一条明亮的对位（C5–E5–G5）
    for i, (off, m) in enumerate([(0.0, 72), (0.9, 76), (1.8, 79), (2.8, 76)]):
        put("S6_bridge%d" % i, S("S6_08") + 0.25 + off, piano(hz(m), 2.6, 0.050 - 0.004 * i,
                                                               seed=2380 + i), pan=0.0)
    # 78→43 之后 / 收束：tick 放慢，最后两次
    for i, off in enumerate([0.6, 1.9]):
        put("S6_tick%d" % i, S("S6_13") + off, tick(0.014, seed=2400 + i, tone=2050.0 if i else 2600.0),
            pan=-0.25 if i else 0.25)
    # 片尾：C 大调主和弦 + 收网动机最后落在 A4→C5→E5→C5→A4，tick 渐隐
    tail_t = E("S6_15") + 0.35
    put("tail_padL", tail_t, pad([hz(48), hz(55), hz(60), hz(64), hz(67)], total - tail_t - 0.2,
                                 0.0150, att=0.5, rel=2.6, cutoff=2100, seed=2500), pan=-0.35)
    put("tail_padR", tail_t + 0.02, pad([hz(48), hz(55), hz(60), hz(64), hz(67)], total - tail_t - 0.2,
                                        0.0132, att=0.6, rel=2.6, cutoff=1900, seed=2501), pan=0.35)
    for i, (off, m, dur, amp) in enumerate([(0.0, 69, 3.0, 0.056), (0.75, 72, 2.6, 0.050),
                                            (1.55, 76, 2.8, 0.048), (2.45, 72, 2.6, 0.044),
                                            (3.35, 69, 4.2, 0.050)]):
        put("tail_piano%d" % (i + 1), tail_t + off, piano(hz(m), dur, amp, seed=2510 + i),
            pan=0.10 if i % 2 else -0.10)
    put("tail_tick1", total - 3.4, tick(0.012, seed=2520, tone=2050.0), pan=-0.2)
    put("tail_tick2", total - 2.4, tick(0.009, seed=2521, tone=2600.0), pan=0.2)
    # 片尾口播（outro_voice）之下保持安静：只留 pad 与极轻低音
    put("tail_sub", total - 5.0, low_drone(hz(36), 4.6, 0.008, att=0.6, rel=1.6, seed=2530), pan=0.0)

    # 底噪（分块 pink，交叉淡化）：不做全片铺满，只在有音乐的段落托一层空气
    air_t = [0.0, 0.35, 1.32, 2.5, cold, cold + 0.5, total]
    air_v = [0.0013, 0.0022, 0.0018, 0.0017, 0.0016, 0.0015, 0.0012]
    bs, ov = SR * 2, SR // 4
    for chn in range(2):
        pos, k = 0, 0
        while pos < N:
            L = min(bs + ov, N - pos)
            x = band_noise(L, 30, 5200, seed=3500 + chn * 97 + k, decay=0, tilt=-0.5)
            w = np.ones(L, dtype=F32)
            na = min(ov, L)
            w[:na] = np.linspace(0.0, 1.0, na, endpoint=False, dtype=F32)
            if pos + L < N:
                w[-ov:] = np.linspace(1.0, 0.0, ov, endpoint=False, dtype=F32)
            amp = np.interp(np.arange(pos, pos + L) / SR, air_t, air_v).astype(F32)
            mix[chn, pos:pos + L] += x * w * amp
            pos += bs
            k += 1

    # 混响（分块卷积 + 低切 IR，能量归一 IR，wet 0.24）
    ir = make_ir(1.8)
    for chn in range(2):
        send = mix[chn].copy()
        fft_conv_add(mix[chn], send, ir[chn], gain=0.24, block=1 << 17)
        del send
    del ir

    # ---------------------------------------------------------- 人工调度曲线
    # 从 timeline 句级锚点推导（不是写死秒数）：关键句前退开/停乐、段落进出的真静默
    def _win(t0, t1, level, ramp=0.35):
        return (max(0.0, t0), min(total, t1), level, ramp)

    gates = [
        # S1 末「大本身带的病」之后停乐，让 whoosh 落地
        _win(E("S1_06") + 0.55, S("S2_01") + 0.05, 0.0, 0.25),
        # S2 后半「周雪光/组织规模负效率」退开；「出厂设置」停
        _win(S("S2_08") - 0.10, S("S2_09") - 0.10, 0.55),
        _win(S("S2_10") - 0.10, S("S3_01") - 0.10, 0.0),
        # S3「威尔逊」引语与「唐斯」长句退开，循环三句重新收紧
        _win(S("S3_05") + 0.15, E("S3_05"), 0.62),
        _win(S("S3_09") + 0.10, E("S3_09"), 0.60),
        _win(S("S3_11") - 0.05, E("S3_13"), 1.05),
        # 段间停乐进 S4
        _win(E("S3_13") + 0.30, S("S4_01") - 0.10, 0.0),
        # S4 几乎抽空；最重一锤处略抬
        _win(S("S4_01") - 0.05, E("S4_07"), 0.78),
        _win(S("S4_08") - 0.05, E("S4_09"), 1.00),
        _win(E("S4_09") + 0.40, S("S5_01") - 0.15, 0.0),
        # S5：数字句退开，最后一次拉起放轻；段尾交给 outro
        _win(S("S5_06") - 0.10, E("S5_06"), 0.72),
        _win(S("S5_10") - 0.05, E("S5_11"), 0.66),
        _win(E("S6_15") + 2.2, total - 0.5, 0.55, 0.8),
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
        theme="网越织越密 / 时钟滴答 / 齿轮 / 低频脉冲 / 弦乐拉起又落下",
        key="A minor (main) -> A Phrygian (S4, Bb neighbor) -> C major (tail resolution)",
        tempo_bpm=BPM, tick_period_s=round(BEAT, 4), tick_hz=round(1.0 / BEAT, 4),
        s4_bpm=S4BPM,
        motif=("收网动机（原创）：A 持续音上三音细胞，音程逐次收窄 "
               "E5->A4(P5) -> D5->A4(P4) -> C5->A4(m3) -> B4->A4(M2)；"
               "S2 首次出现、S6 四次回归；S5 上方音 E5->D5->C5->B4 逐次放矮"),
        pulse_density=dict(node_n3="2 拍/次", node_n10="1 拍/次", node_n20="半拍/次",
                           multiplication_explosion="半拍脉冲 + 秒针 tick 交错"),
        swell_peaks=[1.0, 0.72, 0.50, 0.30],
        sections={}, gate_windows=[], events=events)
    for name, a, b in [("cold_open", 0.0, cold), ("S1", s1["start"], s1["end"]),
                       ("S2", s2["start"], s2["end"]), ("S3", s3["start"], s3["end"]),
                       ("S4", s4["start"], s4["end"]), ("S5", s5["start"], s5["end"]),
                       ("S6", s6["start"], s6["end"]),
                       ("tail", E("S6_15") + 0.35, total)]:
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
        print("[music] 72BPM tick = %.4f Hz; S4 = %.1f BPM slow structural pulse" % (
            meta["tick_hz"], S4BPM))
        for k, v in meta["sections"].items():
            print("    %-12s %7.1f dBFS" % (k, v))
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
