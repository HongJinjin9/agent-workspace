#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep04 原创配乐（纯 numpy 合成，无外部曲库 / 无外部采样，版权干净）
====================================================================
主题：身体 / 心跳 / 发动机
- **声音记忆点**：64 BPM 的「lub-dub」心跳动机（周期 0.9375 s ≈ 1.07 Hz）。
  稿件 S2 讲「车身压在弹簧上，1 到 2 赫兹」——心跳动机的重复频率刻意落在同一条
  1–2 Hz 频带里，让「音乐的晃」和「车身的晃」是同一个频率概念。
- 调性：E 小调（主调，S1–S3）→ S4 上移半音转 **F 小调**（节奏突变 + 电子音色，
  对应电车 jerk）→ S5 回到 E 小调，尾段落到关系大调 **G 大调**收束。
- 配器：心跳低频脉冲、发动机 drone、加法合成钢琴、暖 pad / 弦乐群、S4 电子
  kick / hat / 滤波锯齿 arp / 电源下坠。全部由代码合成，无外部素材。
- 段落调度（不是全片铺满）：cold open 极稀疏 → S1 悬置（S1 末 3 s 停乐）→
  S2 心跳脉冲 + 稀疏钢琴 → S3 弦乐铺底、S3_09 起中段收紧 → S4 半音转调 + 电子
  节奏；S4_10 退开 → S5 回主调、弦乐收束、片尾心跳渐隐。
- 关键句前人工停乐/退开见 `GATE_T/GATE_V`。

输出 work/music.wav（48kHz 立体声 24bit，长度 = timeline total，峰值 ≈ -7.5dBFS）
     work/music_meta.json
内存受限（cgroup 4 CPU / 6GB 与其它 Agent 共享）：全程 float32 + 分块 FFT/分块写盘。
用法：python3 music.py [--dry]
"""
import argparse
import json
import math
import os

import numpy as np

ROOT = "/app/vedio/ep04-body"
SR = 48000
TIMELINE_FULL = os.path.join(ROOT, "work", "timeline_audio_full.json")
MUSIC_WAV = os.path.join(ROOT, "work", "music.wav")
MUSIC_META = os.path.join(ROOT, "work", "music_meta.json")
F32 = np.float32
BPM = 64.0                 # 主速度：心跳动机 64 BPM（1.0667 Hz，落在 1–2 Hz 带）
BEAT = 60.0 / BPM          # 0.9375 s
EBPM = 96.0                # S4 电子段速度：节奏突变
EBEAT = 60.0 / EBPM        # 0.625 s


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
    """dst += gain*conv(src,h)，分块 FFT；src 与 dst 需分离。"""
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
    """MIDI 音高 → 频率。"""
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


# ---------------------------------------------------------------- 乐器 / 音色
def piano(f0, dur, amp, seed=0, bright=1.0):
    """加法合成钢琴：非谐分音 + 击弦噪声。"""
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
    """暖 pad：有限谐波 + 群失谐 + 呼吸幅度。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    for i, f in enumerate(freqs):
        d = detune * (1 if i % 2 == 0 else -1)
        for k in range(1, max(1, int(cutoff / max(f, 30.0))) + 1):
            sig += (1.0 / k ** 1.7) * np.sin(2 * np.pi * f * k * (1 + d) * t
                                            + rng.random() * 6.28318)
    sig *= 1.0 + 0.06 * np.sin(2 * np.pi * 0.083 * t + rng.random() * 6.28)
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def strings(freqs, dur, amp, att=2.2, rel=2.4, seed=0, vib_hz=4.7):
    """弦乐群：8 次谐波 + 群失谐 + 颤音。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    vib = 0.0035 * np.sin(2 * np.pi * vib_hz * t)
    for i, f in enumerate(freqs):
        for k in range(1, 9):
            d = 1.0 + 0.0018 * ((k % 3) - 1) + 0.0007 * i
            sig += (0.8 / k) * np.sin(2 * np.pi * f * k * d * t + vib * k
                                      + rng.random() * 6.28318)
    sig *= 1.0 + 0.04 * np.sin(2 * np.pi * 0.11 * t + 1.3)
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def tremolo_strings(freqs, dur, amp, rate=7.5, att=1.2, rel=1.8, seed=0):
    """紧缩段的高位弦乐：持续 + 颤音（tremolo）幅度调制，制造「收紧」。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    for i, f in enumerate(freqs):
        for k in range(1, 6):
            sig += (0.7 / k) * np.sin(2 * np.pi * f * k * (1 + 0.0012 * (i - 1)) * t
                                   + rng.random() * 6.28318)
    trem = 1.0 - 0.55 * (0.5 + 0.5 * np.sin(2 * np.pi * rate * t))
    sig *= trem
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def drone(f0, dur, amp, att=1.4, rel=1.6, wob=0.16):
    """发动机 drone：低次谐波 + 慢速幅度起伏（怠速感）。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    sig = (np.sin(2 * np.pi * f0 * t) + 0.45 * np.sin(2 * np.pi * 2 * f0 * t + 0.7)
           + 0.18 * np.sin(2 * np.pi * 3 * f0 * t + 1.9)
           + 0.10 * np.sin(2 * np.pi * 4 * f0 * t + 2.7))
    sig *= 1.0 + wob * np.sin(2 * np.pi * 0.23 * t + 0.4)
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def sub_pulse(f0, dur, amp, att=0.006, dec=0.55):
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * f0 * t) + 0.35 * np.sin(2 * np.pi * 2 * f0 * t + 0.5)
    return (sig * np.exp(-t / dec) * (1.0 - np.exp(-t / max(att, 1e-4))) * amp).astype(F32)


def heartbeat(amp, seed=0, dub=0.58):
    """心跳动机「lub-dub」：一次完整搏动 ~0.9s。

    lub：音高从 ~64Hz 下坠到 ~44Hz 的膜性低频 + 轻微瞬态；
    dub：0.24s 后以 0.58 倍力度再收一下。
    周期 0.9375s（64BPM）≈ 1.07Hz，与稿件 S2「车身 1–2 赫兹」同一频带。
    """
    n = int(0.95 * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float64)

    def _thump(t0, gain, f_hi, f_lo, tau, click_amp):
        n0 = int(t0 * SR)
        if n0 >= n:
            return
        tt = t[:n - n0]
        f = f_hi * np.exp(-tt / 0.055) + f_lo * (1.0 - np.exp(-tt / 0.055))
        ph = 2 * np.pi * np.cumsum(f) / SR
        body = np.sin(ph) * np.exp(-tt / tau)
        body += 0.32 * np.sin(2 * ph + 0.5) * np.exp(-tt / (tau * 0.55))
        body += 0.12 * np.sin(2 * np.pi * 118.0 * tt) * np.exp(-tt / 0.055)
        click = band_noise(len(tt), 180, 1400, seed + 3, decay=0.012) * click_amp
        sig[n0:] += (body + click * env_ar(len(tt), 0.001, 0.01)) * gain

    _thump(0.00, 1.00, 66.0, 43.0, 0.165, 0.22)
    _thump(0.235, dub, 58.0, 41.0, 0.140, 0.14)
    return (sig * amp).astype(F32)


def sub_sweep(f0, f1, dur, amp, att=0.05, kind="exp"):
    """低频下坠/上扫（S3→S4 的「动力切换」、S4 转场）。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    u = np.clip(t / dur, 0, 1)
    if kind == "exp":
        f = f0 * (f1 / f0) ** u
    else:
        f = f0 + (f1 - f0) * u
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(ph) + 0.30 * np.sin(2 * ph + 0.4)
    sig *= env_ar(n, att, 0.25)
    return (sig * amp).astype(F32)


def cello_ostinato(freqs, t0_dur, amp, period, seed=0, note_dur=0.42):
    """紧缩段的低音固定音型（按 period 重复的和弦根音，短音）。"""
    n = int(t0_dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    sig = np.zeros(n, dtype=np.float64)
    k = 0
    pos = 0.0
    while pos < t0_dur - 0.02:
        f = freqs[k % len(freqs)]
        m = min(int(note_dur * SR), n - int(pos * SR))
        if m <= 8:
            break
        tt = np.arange(m) / SR
        note = (np.sin(2 * np.pi * f * tt) + 0.30 * np.sin(2 * np.pi * 2 * f * tt + 0.3)
                + 0.12 * np.sin(2 * np.pi * 3 * f * tt + 1.1))
        note *= env_ar(m, 0.008, note_dur * 0.55)
        i0 = int(pos * SR)
        sig[i0:i0 + m] += note
        k += 1
        pos += period
    return (sig * amp).astype(F32)


# ---- S4 电子音色
def elec_kick(amp, seed=0):
    """电子 kick：音高 130→44Hz 快速下坠 + 瞬态 click。"""
    n = int(0.34 * SR)
    t = np.arange(n) / SR
    f = 132.0 * np.exp(-t / 0.030) + 44.0 * (1.0 - np.exp(-t / 0.030))
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(ph) * np.exp(-t / 0.115)
    sig += 0.25 * np.sin(2 * ph) * np.exp(-t / 0.055)
    click = band_noise(n, 900, 6000, seed + 1, decay=0.006) * 0.30
    sig += click
    return (sig * amp).astype(F32)


def elec_hat(amp, seed=0, open_=False):
    """电子 hi-hat：高频带限噪声，短。"""
    n = int((0.16 if open_ else 0.055) * SR)
    x = band_noise(n, 5500, 13000, seed, decay=(0.075 if open_ else 0.020), tilt=0.2)
    x *= env_ar(n, 0.001, n / SR * 0.7)
    return (x * amp).astype(F32)


def saw_arp(f0, dur, amp, cutoff=900, seed=0):
    """滤波锯齿 arp 音：手写 saw 谐波 + 一阶低通近似（在谐波幅度上加 cutoff 衰减）。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    kmax = int(min(24, max(2, 15000.0 / max(f0, 30.0))))
    for k in range(1, kmax + 1):
        a = 1.0 / k * (1.0 / (1.0 + (f0 * k / max(cutoff, 80.0)) ** 2))
        sig += a * np.sin(2 * np.pi * f0 * k * t + rng.random() * 6.28318)
    # 轻微滤波包络（每个音自带下行 cutoff 感）
    sig *= 1.0 + 0.35 * np.exp(-t / 0.05)
    sig *= env_ar(n, 0.004, min(0.10, dur * 0.6))
    return (sig * amp).astype(F32)


def elec_pad(freqs, dur, amp, cutoff=700, seed=0, att=1.4, rel=1.6):
    """S4 电子 pad：失谐锯齿 + 低通，比弦乐更冷。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    for i, f in enumerate(freqs):
        for k in range(1, 12):
            a = 1.0 / k * (1.0 / (1.0 + (f * k / max(cutoff, 80.0)) ** 2))
            det = 1.0 + 0.0028 * (1 if i % 2 == 0 else -1)
            sig += a * np.sin(2 * np.pi * f * k * det * t + rng.random() * 6.28318)
    sig *= 1.0 + 0.05 * np.sin(2 * np.pi * 0.19 * t + rng.random() * 6.28)
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def power_down(amp, seed=0):
    """S3→S4 的「动力切断/切换」：滤波噪声下扫 + 低频下坠 + 电流嗡声收尾。"""
    dur = 1.5
    n = int(dur * SR)
    t = np.arange(n) / SR
    sweep = band_noise(n, 200, 5200, seed)
    # 用时间相关的频带能量近似下扫：高频先退、低频后收
    hi = band_noise(n, 2200, 12000, seed + 1)
    lo = band_noise(n, 90, 700, seed + 2)
    w_hi = np.clip(1.0 - t / 0.55, 0, 1) ** 1.5
    w_lo = np.clip((t - 0.25) / 0.75, 0, 1)
    sub = sub_sweep(110.0, 38.0, dur, 0.6, att=0.02)
    sig = 0.55 * sweep * np.clip(1.0 - t / dur, 0, 1) + 0.6 * hi * w_hi + 0.5 * lo * w_lo
    sig = sig * np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.7
    sig += sub
    return (sig * amp).astype(F32)


def glitch_blip(f0, amp, seed=0):
    """S4 数据/电流小脉冲（很短）。"""
    n = int(0.055 * SR)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * f0 * t) + 0.4 * np.sin(2 * np.pi * f0 * 2.01 * t)
    sig *= (1.0 - np.exp(-t / 0.0015)) * np.exp(-t / 0.012)
    return (sig * amp).astype(F32)


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
        # 能量归一：湿声 RMS ≈ 干声 RMS * wet_gain（峰值归一会让卷积增益过大）
        ir[ch] = y / (np.sqrt(np.sum(y.astype(np.float64) ** 2)) + 1e-12)
    return ir


# ---------------------------------------------------------------- 和声 / 动机
CHORDS = {
    # 主调 E 小调
    "Em":     [40, 47, 52, 55],       # E2 B2 E3 G3
    "C":      [36, 43, 48, 52],       # C2 G2 C3 E3
    "G":      [43, 50, 55, 59],       # G2 D3 G3 B3
    "D":      [38, 45, 50, 54],       # D2 A2 D3 F#3
    "Am":     [45, 52, 57, 60],       # A2 E3 A3 C4
    "B":      [47, 54, 59, 62],       # B2 F#3 B3 D4
    "Cmaj7":  [36, 43, 48, 52, 59],
    "Emadd9": [40, 47, 52, 55, 66],
    "Gmaj7":  [43, 50, 55, 59, 66],
    # S4 F 小调（上移半音）
    "Fm":     [41, 48, 53, 56],       # F2 C3 F3 Ab3
    "Db":     [37, 44, 49, 53],       # Db2 Ab2 Db3 F3
    "Bbm":    [46, 53, 58, 61],       # Bb2 F3 Bb3 Db4
    "Csus":   [48, 55, 60, 63],       # C3 G3 C4 Eb4（S4 末悬置）
}

# 主主题动机（原创，E 自然小调；单位：秒偏移 / MIDI / 时长 / 力度）
MOTIF_A = [
    (0.00, 64, 1.7, 0.085),   # E4
    (0.94, 67, 1.5, 0.075),   # G4
    (1.88, 71, 2.2, 0.070),   # B4
    (4.22, 69, 1.6, 0.072),   # A4
    (5.16, 67, 1.4, 0.066),   # G4
    (6.10, 66, 2.4, 0.068),   # F#4
    (8.44, 64, 3.0, 0.078),   # E4
]
MOTIF_B = [
    (0.00, 67, 1.7, 0.084),   # G4
    (0.94, 69, 1.5, 0.074),   # A4
    (1.88, 74, 2.2, 0.070),   # D5
    (4.22, 71, 1.6, 0.072),   # B4
    (5.16, 69, 1.4, 0.064),   # A4
    (6.10, 67, 2.4, 0.066),   # G4
    (8.44, 64, 3.0, 0.076),   # E4
]


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

    def chord(sid):
        return [hz(m) for m in CHORDS[sid]]

    s1, s2, s3, s4, s5 = (segs[k] for k in ("S1", "S2", "S3", "S4", "S5"))
    cold, gap = float(tl["cold_open"]), float(tl["segment_gap"])

    # ============================================================ cold open 0–3.0
    # 极稀疏：一次心跳 + 发动机怠速 drone + 一记钢琴；把「声音记忆点」先亮出来
    put("cold_heart", 0.55, heartbeat(0.050, seed=1001), pan=0.0)
    put("cold_engine", 0.20, drone(hz(28), cold - 0.20, 0.028, att=1.7, rel=1.1), pan=0.0)
    put("cold_engine2", 0.35, drone(hz(40), cold - 0.35, 0.016, att=1.8, rel=1.0), pan=0.0)
    put("cold_piano", 1.55, piano(hz(64), 3.8, 0.070, seed=1010), pan=-0.12)

    # ============================================================ S1 悬置 3.0–23.21
    s1_a, s1_b = s1["start"] + 0.20, E("S1_05") + 0.50
    put("S1_engine", s1_a, drone(hz(40), s1_b - s1_a, 0.030, att=1.3, rel=0.9), pan=0.0)
    put("S1_sub", s1_a + 0.15, drone(hz(28), s1_b - s1_a - 0.15, 0.014, att=1.6, rel=0.9), pan=0.0)
    # S1 两次心跳：不只是音效，是主题在「困惑」段落的第一次呼吸
    put("S1_heart1", 4.55, heartbeat(0.030, seed=1020, dub=0.52), pan=0.0)
    put("S1_heart2", 15.65, heartbeat(0.034, seed=1021, dub=0.55), pan=0.0)
    for k, (sid, m, dur, amp, pan) in enumerate([
            ("S1_01", 64, 3.6, 0.078, -0.15),   # E4
            ("S1_02", 71, 3.4, 0.070, 0.18),    # B4
            ("S1_03", 67, 3.2, 0.068, 0.10),    # G4
            ("S1_04", 66, 3.2, 0.062, -0.10),   # F#4
            ("S1_05", 69, 3.4, 0.074, 0.05)]):  # A4
        put("S1_piano%d" % (k + 1), S(sid) + 0.12, piano(hz(m), dur, amp, seed=1030 + k), pan=pan)
    put("S1_high2", S("S1_05") + 0.55, pad([hz(76), hz(83)], 2.6, 0.010,
                                           att=0.9, rel=1.2, cutoff=2600, seed=1040), pan=0.30)
    put("S1_high2R", S("S1_05") + 0.60, pad([hz(76), hz(83)], 2.6, 0.009,
                                            att=1.0, rel=1.2, cutoff=2400, seed=1041), pan=-0.30)

    # ============================================================ S2 心跳脉冲 + 稀疏钢琴 24.66–78.93
    s2_a, s2_b = s2["start"] + 0.62, s2["end"] - 0.55
    # 和声：Em C G D | Em C G Em（每 7.5s 一次，两声道分层 pad）
    s2_chords = ["Em", "C", "G", "D", "Em", "C", "G", "Em"]
    for j, name in enumerate(s2_chords):
        t0 = s2["start"] + 0.60 + j * 7.5
        d = min(7.5 + 1.1, s2["end"] - t0)
        if d <= 0.3:
            continue
        put("S2_padL_%s" % name, t0, pad(chord(name)[1:], d, 0.0115,
                                        att=1.5, rel=1.8, cutoff=1200, seed=1100 + j), pan=-0.36)
        put("S2_padR_%s" % name, t0 + 0.03, pad(chord(name)[1:], d, 0.0100,
                                               att=1.7, rel=1.8, cutoff=1100, seed=1130 + j), pan=0.36)
        put("S2_root_%s" % name, t0, drone(hz(CHORDS[name][0]), min(d, 6.0), 0.020,
                                           att=0.8, rel=1.0), pan=0.0)
    put("S2_sub", s2_a, drone(hz(28), s2_b - s2_a, 0.013, att=1.8, rel=1.2), pan=0.0)
    # 心跳动机：每拍一组 lub-dub（0.9375s ≈ 64BPM 静息心率，也 ≈1.07Hz 车身/弹簧频带），S2 核心记忆点
    t = s2_a + 0.10
    k = 0
    while t < s2_b - 0.4:
        amp = 0.036 if k % 4 else 0.046
        put("S2_heart%d" % k, t, heartbeat(amp, seed=1200 + k, dub=0.55), pan=0.0)
        k += 1
        t += BEAT
    # 稀疏钢琴：一句一音，句尾落回主音
    s2_pno = [
        ("S2_01", 0.55, 64, 3.2, 0.070),   # E4
        ("S2_02", 0.10, 67, 3.0, 0.062),   # G4（「咚」句，下面会人工退开）
        ("S2_03", 0.10, 66, 3.0, 0.060),   # F#4（「咣当」）
        ("S2_04", 0.10, 62, 2.8, 0.060),   # D4（问句）
        ("S2_05", 0.20, 59, 3.4, 0.066),   # B3（1–2Hz 解释）
        ("S2_06", 0.10, 69, 3.2, 0.062),   # A4（10–15Hz）
        ("S2_07", 0.10, 64, 3.2, 0.066),   # E4（4–8Hz 身体）
        ("S2_08", 0.10, 67, 3.0, 0.062),   # G4（软硬）
        ("S2_09", 0.10, 66, 3.2, 0.066),   # F#4（阻尼）
        ("S2_10", 0.10, 64, 3.2, 0.064),   # E4（咚）
        ("S2_11", 0.10, 59, 3.6, 0.068),   # B3（咣当/晃）
    ]
    for k, (sid, off, m, dur, amp) in enumerate(s2_pno):
        put("S2_piano%d" % (k + 1), S(sid) + off, piano(hz(m), dur, amp, seed=1300 + k), pan=0.06)
    put("S2_piano_extra", S("S2_05") + 2.60, piano(hz(71), 3.0, 0.052, seed=1320), pan=-0.05)

    # ============================================================ S3 弦乐铺底 / 中段收紧 80.38–128.35
    s3_a = s3["start"] + 0.55
    # 弦乐和声：Em Am C | B Em C B（前半铺底，后半收紧）
    s3_prog = [(81.0, "Em", 9.6), (90.6, "Am", 9.6), (100.2, "C", 8.4),
               (108.6, "B", 6.4), (115.0, "Em", 6.4), (121.4, "C", 5.6), (127.0, "B", 1.3)]
    for j, (t0, name, d) in enumerate(s3_prog):
        put("S3_strL_%s" % name, t0, strings(chord(name), d, 0.0125,
                                             att=2.0, rel=2.2, seed=1400 + j), pan=-0.40)
        put("S3_strR_%s" % name, t0 + 0.03, strings(chord(name), d, 0.0105,
                                                    att=2.2, rel=2.2, seed=1430 + j), pan=0.40)
        put("S3_cello_%s" % name, t0, drone(hz(CHORDS[name][0] - 12), min(d, 7.0), 0.016,
                                            att=1.2, rel=1.4), pan=0.0)
    # 中段收紧：S3_09（差的车这条线是断的）起加高位 tremolo 弦乐 + 低音固定音型
    tight_a = S("S3_09") - 0.15
    put("S3_tight_strL", tight_a, tremolo_strings([hz(76), hz(79)], 13.5, 0.0105,
                                                  rate=7.5, att=1.0, rel=1.6, seed=1500), pan=-0.42)
    put("S3_tight_strR", tight_a + 0.03, tremolo_strings([hz(76), hz(79)], 13.5, 0.0090,
                                                         rate=7.7, att=1.1, rel=1.6, seed=1501), pan=0.42)
    put("S3_ostinato", S("S3_09") - 0.10, cello_ostinato([hz(40), hz(47), hz(45), hz(47)],
                                                         16.6, 0.022, 2.0 * BEAT / 2,
                                                         seed=1510, note_dur=0.40), pan=-0.10)
    put("S3_tight_sub", S("S3_11") - 0.10, sub_pulse(hz(28), 4.0, 0.026, att=0.02), pan=0.0)
    for k, (sid, m, amp, pan) in enumerate([
            ("S3_02", 62, 0.060, 0.10),    # D4
            ("S3_06", 67, 0.058, -0.08),   # G4
            ("S3_13", 64, 0.064, 0.05)]):  # E4
        put("S3_piano%d" % (k + 1), S(sid) + 0.20, piano(hz(m), 3.4, amp, seed=1520 + k), pan=pan)
    put("S3_highL", S("S3_12") + 0.10, strings([hz(76), hz(79)], 3.6, 0.0085,
                                              att=0.9, rel=1.8, seed=1530), pan=-0.30)
    put("S3_highR", S("S3_12") + 0.13, strings([hz(76), hz(79)], 3.6, 0.0075,
                                              att=1.0, rel=1.8, seed=1531), pan=0.30)

    # ============================================================ S4 半音转调 + 电子音色 129.80–178.13
    # 动力切换（S3 末已停乐）：低频下坠 + 噪声下扫，落点在「第三个。电动车。」
    put("S4_powerdown", 129.50, power_down(0.055, seed=1600), pan=0.0)
    put("S4_enter_sub", S("S4_01") + 0.10, sub_sweep(hz(38), hz(26), 1.8, 0.030, att=0.10), pan=0.0)
    # 电子和声 Fm Db Bbm C | Fm Db Csus（i–VI–iv–V，与主调不同的调式色彩）
    s4_prog = [(132.35, "Fm", 8.0), (140.35, "Db", 7.0), (147.35, "Bbm", 7.0),
               (154.35, "C", 6.0), (160.35, "Fm", 6.0), (166.35, "Db", 6.0),
               (172.35, "Csus", 5.4)]
    for j, (t0, name, d) in enumerate(s4_prog):
        put("S4_epadL_%s" % name, t0, elec_pad(chord(name)[1:], d, 0.0125,
                                               cutoff=800, seed=1700 + j, att=0.35, rel=0.8), pan=-0.35)
        put("S4_epadR_%s" % name, t0 + 0.02, elec_pad(chord(name)[1:], d, 0.0110,
                                                      cutoff=700, seed=1730 + j, att=0.40, rel=0.8), pan=0.35)
        put("S4_bassroot_%s" % name, t0, drone(hz(CHORDS[name][0] - 12), min(d, 3.5), 0.020,
                                               att=0.3, rel=0.4, wob=0.05), pan=0.0)
    # 电子 groove：分段性格（thin / pulse / full / half / sparse）
    ARP = [53, 56, 60, 63, 65, 63, 60, 56]   # F3 Ab3 C4 Eb4 F4 Eb4 C4 Ab3
    ARP_DB = [49, 53, 56, 60, 61, 60, 56, 53]

    def groove(t0, t1, mode, seed0=1800):
        """在 [t0,t1) 内铺电子节奏。mode: thin/pulse/full/sparse。"""
        pos = t0
        bi = 0
        while pos < t1 - 0.05:
            bar = (pos - t0) / (4.0 * EBEAT)
            # kick
            if mode in ("pulse", "full") and bi % 4 in (0, 2):
                put("S4_kick_%d_%d" % (int(t0), bi), pos, elec_kick(0.075, seed=seed0 + bi), pan=0.0)
            if mode == "half" and bi % 8 == 0:
                put("S4_kick_%d_%d" % (int(t0), bi), pos, elec_kick(0.060, seed=seed0 + bi), pan=0.0)
            # hat
            if mode in ("pulse", "full", "half") and bi % 2 == 0:
                put("S4_hat_%d_%d" % (int(t0), bi), pos + 0 * EBEAT,
                    elec_hat(0.020 if mode != "full" else 0.026, seed=seed0 + 100 + bi), pan=0.22)
            if mode == "full" and bi % 2 == 1:
                put("S4_hat2_%d_%d" % (int(t0), bi), pos,
                    elec_hat(0.013, seed=seed0 + 200 + bi), pan=-0.18)
            if mode == "thin" and bi % 4 == 0:
                put("S4_hat_%d_%d" % (int(t0), bi), pos,
                    elec_hat(0.014, seed=seed0 + 300 + bi, open_=True), pan=0.10)
            # 16 分 arp
            if mode in ("full", "pulse", "half") and (mode != "half" or bi % 2 == 0):
                if mode == "full":
                    notes = ARP
                elif bi < 8:
                    notes = ARP
                else:
                    notes = ARP_DB
                m = notes[bi % 8]
                put("S4_arp_%d_%d" % (int(t0), bi), pos, saw_arp(hz(m), 0.22,
                                                                 0.0165 if mode == "full" else 0.0130,
                                                                 cutoff=950 if mode == "full" else 720,
                                                                 seed=seed0 + 400 + bi), pan=0.28 if bi % 2 else -0.28)
            bi += 1
            pos += EBEAT / 2.0   # 8 分音符网格
    # S4 段落性格
    groove(132.35, 139.45, "pulse", seed0=1800)   # 节奏突变：先 kick+hat（jerk 未揭示）
    groove(139.45, 146.80, "thin", seed0=1900)    # 定义 jerk：退开、只留 hat 与 pad
    groove(146.80, 155.15, "half", seed0=2000)    # 燃油车扭矩「慢慢爬」
    groove(155.15, 159.55, "full", seed0=2100)    # 「突然出现」→ 全开
    groove(159.55, 163.43, "full", seed0=2200)    # 推背/晕车
    groove(163.43, 171.95, "thin", seed0=2300)    # 密歇根研究：长句信息段，退开
    put("S4_glitch1", S("S4_04") + 1.10, glitch_blip(1680.0, 0.014, seed=2401), pan=0.30)
    put("S4_glitch2", S("S4_05") + 0.80, glitch_blip(1240.0, 0.012, seed=2402), pan=-0.25)
    put("S4_glitch3", S("S4_09") + 2.20, glitch_blip(2100.0, 0.010, seed=2403), pan=0.22)
    # S4_10 收束：只留一条低音与一个 sub，随后交给 S5 riser
    put("S4_last_sub", S("S4_10") + 0.10, sub_pulse(hz(26), 3.2, 0.034, att=0.02), pan=0.0)
    put("S4_last_pad", S("S4_10") + 0.15, elec_pad([hz(48), hz(55), hz(60)], 4.2, 0.010,
                                                  cutoff=520, seed=2410, att=0.7, rel=1.8), pan=-0.20)

    # ============================================================ S5 回主调 / 弦乐收束 180.68–230.38
    # 三线合流：低弦进入 + 主题动机回归
    s5_prog = [(180.80, "Em", 8.6), (189.40, "C", 8.6), (198.00, "G", 8.6),
               (206.60, "B", 4.0), (210.60, "G", 3.6), (214.20, "C", 5.2),
               (219.40, "G", 6.4), (225.80, "C", 4.5), (230.30, "G", 6.4)]
    for j, (t0, name, d) in enumerate(s5_prog):
        put("S5_strL_%s" % name, t0, strings(chord(name), d, 0.0125,
                                             att=1.8, rel=2.2, seed=2500 + j), pan=-0.40)
        put("S5_strR_%s" % name, t0 + 0.03, strings(chord(name), d, 0.0105,
                                                    att=2.0, rel=2.2, seed=2530 + j), pan=0.40)
        put("S5_cello_%s" % name, t0, drone(hz(CHORDS[name][0] - 12), min(d, 6.5), 0.016,
                                            att=1.0, rel=1.4), pan=0.0)
        put("S5_epiano_%s" % name, t0 + 0.05, pad(chord(name)[1:], min(d, 5.0), 0.0065,
                                                  att=0.5, rel=1.4, cutoff=2400, seed=2560 + j), pan=0.0)
    # 弦乐收束的高位长音（S5_08 情绪峰值）
    put("S5_peak_strL", S("S5_08") - 2.0, strings([hz(76), hz(79), hz(83)], 8.5, 0.0105,
                                                  att=1.8, rel=2.6, seed=2600), pan=-0.45)
    put("S5_peak_strR", S("S5_08") - 1.9, strings([hz(76), hz(79), hz(83)], 8.5, 0.0090,
                                                  att=2.0, rel=2.6, seed=2601), pan=0.45)
    # 主题动机：A → B → A，分别落在 S5_01 / S5_05 / S5_08
    for tag, (base_motif, t_base, seed0, pan) in enumerate([
            (MOTIF_A, S("S5_01") + 0.30, 2700, -0.05),
            (MOTIF_B, S("S5_05") + 0.25, 2750, 0.10),
            (MOTIF_A, S("S5_08") + 0.05, 2800, -0.08)]):
        for k, (off, m, dur, amp) in enumerate(base_motif):
            put("S5_motif%d_%d" % (tag + 1, k + 1), t_base + off,
                piano(hz(m), dur, amp, seed=seed0 + k), pan=pan)
    put("S5_heart_a", S("S5_01") + 0.60, heartbeat(0.030, seed=2900, dub=0.55), pan=0.0)
    put("S5_heart_b", S("S5_08") + 0.20, heartbeat(0.038, seed=2901, dub=0.58), pan=0.0)
    # 片尾：主调收束 + 心跳渐隐
    tail_t = E("S5_11") + 0.30      # 229.78 + 0.30
    put("tail_padL", tail_t, pad([hz(43), hz(50), hz(55), hz(59), hz(66)], 6.6, 0.0165,
                                 att=0.6, rel=3.0, cutoff=2000, seed=3000), pan=-0.35)
    put("tail_padR", tail_t + 0.02, pad([hz(43), hz(50), hz(55), hz(59), hz(66)], 6.6, 0.0145,
                                        att=0.7, rel=3.0, cutoff=1800, seed=3001), pan=0.35)
    put("tail_heart1", tail_t + 1.10, heartbeat(0.034, seed=3010, dub=0.55), pan=0.0)
    put("tail_heart2", tail_t + 2.90, heartbeat(0.026, seed=3011, dub=0.50), pan=0.0)
    for k, (off, m) in enumerate([(0.00, 64), (0.55, 67), (1.10, 71), (1.75, 76)]):
        put("tail_piano%d" % (k + 1), tail_t + off, piano(hz(m), 3.4, 0.060 - 0.006 * k,
                                                          seed=3020 + k), pan=0.10 if k % 2 else -0.10)

    # 底噪（分块 pink，交叉淡化）：不做全片「铺满」，只在有音乐的段落托一层空气
    air_t = [0.0, 0.35, 1.32, 3.6, cold, cold + 0.5, total]
    air_v = [0.0014, 0.0024, 0.0019, 0.0018, 0.0017, 0.0016, 0.0014]
    bs, ov = SR * 2, SR // 4
    for ch in range(2):
        pos, k = 0, 0
        while pos < N:
            L = min(bs + ov, N - pos)
            x = band_noise(L, 30, 5200, seed=3500 + ch * 97 + k, decay=0, tilt=-0.5)
            w = np.ones(L, dtype=F32)
            na = min(ov, L)
            w[:na] = np.linspace(0.0, 1.0, na, endpoint=False, dtype=F32)
            if pos + L < N:
                w[-ov:] = np.linspace(1.0, 0.0, ov, endpoint=False, dtype=F32)
            amp = np.interp(np.arange(pos, pos + L) / SR, air_t, air_v).astype(F32)
            mix[ch, pos:pos + L] += x * w * amp
            pos += bs
            k += 1

    # 混响（分块卷积 + 低切 IR，能量归一 IR，wet 0.22）
    ir = make_ir(1.5)
    for ch in range(2):
        send = mix[ch].copy()
        fft_conv_add(mix[ch], send, ir[ch], gain=0.22, block=1 << 17)
        del send
    del ir

    # ---------------------------------------------------------- 人工调度曲线
    # （关键句前退开/停乐、段落进出的真静默；对应稿件 §3.7 与优化意见 §5.2 C）
    GATE_T = [
        0.00, 3.00,
        21.80, 22.50, 25.55, 26.45, 27.05,
        29.40, 30.00, 31.20, 32.00,
        33.60, 34.00, 35.20, 36.00,
        37.40, 37.65, 38.90, 39.50,
        62.20, 62.60, 64.80, 65.60, 66.20,
        77.70, 78.30, 80.80, 81.60, 82.40,
        102.60, 103.00, 105.00, 105.80,
        109.80, 110.20, 112.50, 113.20,
        127.20, 128.00, 129.45,
        129.50, 130.70, 130.90, 132.35, 132.45,
        139.30, 139.50, 145.90, 146.60,
        154.90, 155.20, 159.00, 159.40,
        163.20, 163.60, 171.80, 172.40, 177.70, 178.20,
        180.68, 181.20, 196.30, 196.80,
        201.30, 203.90, 204.40, 209.90, 210.50,
        214.50, 216.30, 221.40, 222.00, 229.60, 230.20, 235.40, 236.60,
    ]
    GATE_V = [
        1.0, 1.0,
        1.0, 0.0, 0.0, 0.9, 1.0,
        1.0, 0.55, 0.55, 0.95,
        1.0, 0.50, 0.55, 1.0,
        1.0, 0.45, 0.45, 0.95,
        1.0, 0.22, 0.25, 0.85, 1.0,
        0.95, 0.0, 0.0, 0.85, 1.0,
        1.0, 0.72, 0.72, 1.0,
        1.0, 0.85, 0.90, 1.0,
        0.95, 0.0, 0.0,
        0.60, 0.60, 0.0, 0.0, 1.0,
        1.0, 0.55, 0.55, 0.95,
        1.0, 1.05, 1.05, 1.0,
        1.0, 0.55, 0.60, 0.45, 0.40, 0.0,
        0.90, 1.0, 1.0, 0.90,
        0.65, 0.65, 0.40, 0.40, 1.0,
        0.95, 0.90, 0.90, 0.55, 0.55, 0.70, 0.70, 0.0,
    ]
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
        theme="身体 / 心跳 / 发动机",
        key="E minor (main) -> F minor (S4, +1 semitone) -> G major (tail resolution)",
        tempo_bpm=BPM, heartbeat_period_s=round(BEAT, 4),
        heartbeat_hz=round(1.0 / BEAT, 4),
        s4_bpm=EBPM,
        motif="lub-dub heartbeat 64BPM + original E-minor piano motif (A: E4-G4-B4-A4-G4-F#4-E4)",
        sections={}, gate_windows=[], events=events)
    for name, a, b in [("cold_open", 0.0, cold), ("S1", s1["start"], s1["end"]),
                       ("S1_silence", E("S1_05") + 0.6, s2["start"]),
                       ("S2", s2["start"], s2["end"]), ("S3", s3["start"], s3["end"]),
                       ("S4", s4["start"], s4["end"]), ("S5", s5["start"], s5["end"]),
                       ("tail", E("S5_11") + 0.3, total)]:
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
        print("[music] 64BPM heartbeat = %.4f Hz (1-2Hz body band)" % meta["heartbeat_hz"])
        for k, v in meta["sections"].items():
            print("    %-12s %7.1f dBFS" % (k, v))
        print("[music] music-silence windows:", meta["gate_windows"])
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
