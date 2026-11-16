#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep08 原创配乐（纯 numpy 合成，无外部曲库 / 无外部采样，版权干净）
====================================================================
主题：一条可逆的能量通道 —— 电流脉冲 / 能量回流 / 电机上扫 / 回收提示
- **声音记忆点 = 「能量脉冲动机」**（原创，与第 04/05 期不同）：
  三个快速上行的电流脉冲（D4→A4→D5，像电流被推上去），接一记**下落长脉冲**
  （D5→D2 的指数下滑，像动能从轮端落进电池）。上行=回收开始，下落=能量存进去；
  片尾把同一动机改成 D 大调（F#）落在 D 上，等于「能量回来了」。
  第 04 期记忆点是 64BPM 心跳 lub-dub；第 05 期是音程收窄的「收网动机」；
  本期是「上行三连 + 下落长滑」，动机方向相反，独一无二。
- **电流脉冲**：90 BPM、八分/十六分音符网格上的短颗粒（有限谐波 + 极短衰减），
  是「电流在母线里走」的听觉化；越接近能量账/损耗，脉冲越密。
- **继电器 click**：机械吸合的两段金属瞬态，充当节拍里的「开关声」，
  只在能量路径切换（逆变器/电池接上）的段落出现。
- **电机上扫**：滤波噪声 + 谐波正弦的上扫层，只在「拆解」段托底，
  与 sfx.py 的 motor_sweep 是不同音色/不同用途（这里只是音乐织体）。
- 调性：D 小调（主调）→ S4 能量账转 D 多利亚（E 自然、变亮）→
  S5 限制退回 D 小调 + Bb 暗色 → S6 再判转 F 大调色彩 → S7 收束 D 大调（皮卡第三度）。
  速度 90 BPM，与第 04 期 64BPM、第 05 期 72BPM 均不同。

段落调度（不全片铺满；4 段人工停乐的真静默窗）：
  cold open 极稀疏（低 drone + 两记电流脉冲 + 动机碎片 + 一记继电器）→
  S1 钩子：一句一音稀疏动机 + 低频 drone → S2 立判：八分电流脉冲 + 低频「轮转」+ pad →
  S3 拆解：电机上扫层 + 电流脉冲加密 + 低音级进下行 + 继电器开关 →
  S4 能量账：十六分脉冲 + 琶音「记账」+ 动机完整陈述 + 效率损耗处退开 →
  S5 限制：几乎抽空（慢继电器 + 四条下落脉冲，一条限制一记）→
  S6 再判：脉冲回归 + 动机两次 + 上行充能 → S7 收束：D 大调动机 + 充能上扫 + 片尾 pad。

输出（全部在 audio/work/ 下，长度 = timeline_audio_full.json 的 total）：
  audio/work/music.wav       48kHz 立体声 24bit
  audio/work/music_meta.json 事件表/逐段电平/调性/动机/停乐窗

用法：python3 music.py [--dry]
"""
import argparse
import json
import math
import os

import numpy as np

ROOT = "/app/vedio/ep08-regen"
AUDIO = os.path.join(ROOT, "audio", "work")
SR = 48000
TIMELINE_FULL = os.path.join(AUDIO, "timeline_audio_full.json")
MUSIC_WAV = os.path.join(AUDIO, "music.wav")
MUSIC_META = os.path.join(AUDIO, "music_meta.json")
F32 = np.float32

BPM = 90.0                  # 主速度：电流脉冲 90 BPM（与 ep04 64 / ep05 72 区分）
BEAT = 60.0 / BPM           # 0.6667 s
E8 = BEAT / 2.0             # 八分音符 0.3333 s
S16 = BEAT / 4.0            # 十六分音符 0.1667 s


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


# ---------------------------------------------------------------- 音色（本期专属）
def energy_pulse(f0, f1, dur, amp, seed=0, bright=1.0):
    """能量脉冲（本期记忆点音色）：FM 快速起振 + 指数滑音 + 指数衰减。

    f0→f1 的下滑 = 能量回灌（D5→D2）；f0==f1 时是一记「电流脉冲」。
    """
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / 0.11)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = (np.sin(ph)
            + 0.44 * bright * np.sin(2.02 * ph + 0.4)
            + 0.17 * bright * np.sin(3.05 * ph + 1.1)
            + 0.07 * bright * np.sin(4.10 * ph + 2.0))
    mod = 1.0 + 0.16 * np.sin(2 * np.pi * 3.35 * f0 * t) * np.exp(-t / 0.055)
    tau = min(1.5, max(0.12, dur * 0.36))
    sig = body * mod * np.exp(-t / tau)
    nn = min(n, int(0.006 * SR))
    if nn > 0:
        sig[:nn] += band_noise(nn, 2000, 12000, seed, decay=0.0020) * 0.45
    sig *= env_ar(n, 0.002, min(0.55, dur * 0.30))
    return (sig * amp).astype(F32)


def current_pulse(amp, seed=0, f=73.4, dur=0.16):
    """电流脉冲：八分/十六分网格上的短颗粒，有限谐波 + 极短衰减。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float64)
    for k in range(1, 9):
        if f * k > 6000:
            break
        sig += (1.0 / k ** 1.30) * np.sin(2 * np.pi * f * k * t + 0.37 * k)
    sig *= np.exp(-t / 0.040)
    sig += 0.42 * band_noise(n, 350, 3200, seed, decay=0.008)
    sig *= env_ar(n, 0.0015, 0.030)
    return (sig * amp).astype(F32)


def relay_click(amp, seed=0, f=2600.0, gap=0.026):
    """继电器吸合：两段金属瞬态（衔铁先撞一下、再吸实）+ 一记低频 thunk。"""
    n = int(0.26 * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float64)
    for j, (off, g) in enumerate([(0.0, 1.0), (gap, 0.72)]):
        i0 = int(off * SR)
        nn = n - i0
        if nn <= 8:
            break
        tt = np.arange(nn) / SR
        c = band_noise(nn, 1800, 12000, seed + j, decay=0.0032) * 0.85
        c += 0.85 * np.sin(2 * np.pi * f * (1.0 + 0.03 * j) * tt) * np.exp(-tt / 0.011)
        c += 0.32 * np.sin(2 * np.pi * f * 1.51 * tt + 0.5) * np.exp(-tt / 0.007)
        sig[i0:] += c * g
    ff = 150.0 * np.exp(-t / 0.020) + 68.0 * (1.0 - np.exp(-t / 0.020))
    ph = 2 * np.pi * np.cumsum(ff) / SR
    sig += 0.55 * np.sin(ph) * np.exp(-t / 0.045)
    sig *= env_ar(n, 0.0008, 0.060)
    return (sig * amp).astype(F32)


def motor_up(f0, f1, dur, amp, seed=0):
    """电机上扫层（音乐织体）：谐波正弦随转速上扫 + 齿槽脉动 + 随速噪声。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    u = np.clip(t / dur, 0, 1)
    f = f0 * (f1 / f0) ** u
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(ph) + 0.30 * np.sin(2 * ph + 0.3) + 0.12 * np.sin(3 * ph + 1.0)
    sig *= 0.62 + 0.38 * np.sin(2 * np.pi * 3.1 * t) ** 2
    wh = band_noise(n, max(120.0, f0 * 1.4), min(11000.0, f1 * 4.0), seed, decay=0.0)
    sig += 0.24 * wh * u
    sig *= env_ar(n, 0.10, min(0.55, dur * 0.30))
    return (sig * amp).astype(F32)


def charge_rise(f0, f1, dur, amp, seed=0):
    """充能上扫（收束用）：低音向上收拢 + 一层极轻的高频微光（不尖）。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    u = np.clip(t / dur, 0, 1)
    f = f0 * (f1 / f0) ** (u ** 1.25)
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(ph) * (u ** 1.55)
    sig += 0.30 * np.sin(2 * ph + 0.4) * (u ** 1.8)
    sig += 0.14 * np.sin(3 * ph + 1.2) * (u ** 2.0)
    shimmer = band_noise(n, 3200, 9000, seed, decay=0.0, tilt=0.35) * 0.15 * (u ** 2.2)
    sig += shimmer
    sig *= env_ar(n, 0.20, 0.45)
    return (sig * amp).astype(F32)


def pluck(f0, dur, amp, seed=0):
    """「记账」拨弦：比能量脉冲更短、更干的木/金属感颗粒（S4 能量账用）。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = np.zeros(n, dtype=np.float64)
    tau0 = float(np.clip(2.6 * (220.0 / f0) ** 0.5, 0.35, 4.5))
    for k, a in [(1.0, 1.0), (2.004, 0.30), (3.01, 0.12), (4.02, 0.05)]:
        if f0 * k > 9000:
            break
        sig += a * np.sin(2 * np.pi * f0 * k * (1 + 0.0004 * (rng.random() - 0.5)) * t
                          + rng.random() * 6.28318) * np.exp(-t / (tau0 / k ** 0.6))
    nn = min(n, int(0.012 * SR))
    if nn > 0:
        sig[:nn] += band_noise(nn, 1200, 7000, seed + 3, decay=0.0025) * 0.12
    sig *= env_ar(n, 0.0025, min(0.4, dur * 0.3))
    return (sig * amp).astype(F32)


def pad(freqs, dur, amp, att=1.2, rel=1.7, cutoff=1500, seed=0, detune=0.0015):
    """暖 pad：有限谐波 + 群失谐 + 慢呼吸（和声底色）。"""
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
    sig *= 1.0 + 0.07 * np.sin(2 * np.pi * 0.083 * t + rng.random() * 6.28)
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def low_drone(f0, dur, amp, att=1.3, rel=1.5, wob=0.14, seed=0):
    """低频 drone：1/2/3/4 次谐波 + 极慢幅度起伏（车辆底盘的重量感）。"""
    n = int(dur * SR)
    if n <= 8:
        return np.zeros(max(n, 0), dtype=F32)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    sig = (np.sin(2 * np.pi * f0 * t) + 0.42 * np.sin(2 * np.pi * 2 * f0 * t + 0.6)
           + 0.16 * np.sin(2 * np.pi * 3 * f0 * t + 1.7)
           + 0.09 * np.sin(2 * np.pi * 4 * f0 * t + 2.4))
    sig *= 1.0 + wob * np.sin(2 * np.pi * (0.21 + 0.03 * rng.random()) * t + 0.4)
    sig += band_noise(n, 25, 260, seed + 1, decay=0, tilt=-0.4) * 0.05
    sig *= env_ar(n, att, rel)
    return (sig * amp).astype(F32)


def sub_thump(amp, seed=0, f_hi=62.0, f_lo=36.0, dur=0.70, tau=0.24):
    """低频「轮转/落点」：一记钝的低频搏动（不是 ep04 的心跳、也不是 ep05 的慢搏动）。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f_hi * np.exp(-t / 0.07) + f_lo * (1.0 - np.exp(-t / 0.07))
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(ph) * np.exp(-t / tau)
    sig += 0.28 * np.sin(2 * ph + 0.4) * np.exp(-t / (tau * 0.5))
    sig += 0.09 * band_noise(n, 110, 820, seed + 2, decay=0.016)
    return (sig * env_ar(n, 0.0015, 0.16) * amp).astype(F32)


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
# D 小调（主调）—— 与 ep04 的 E 小调、ep05 的 A 小调不同
CHORDS = {
    "Dm":    [38, 45, 50, 53],     # D2 A2 D3 F3
    "Bb":    [46, 53, 58, 62],     # Bb2 F3 Bb3 D4
    "F":     [41, 48, 53, 57],     # F2 C3 F3 A3
    "C":     [36, 43, 48, 52],     # C2 G2 C3 E3
    "Gm":    [43, 50, 55, 58],     # G2 D3 G3 Bb3
    "A":     [45, 52, 57, 61],     # A2 E3 A3 C#4（限制段的和声张力）
    "Em":    [40, 47, 52, 55],     # E2 B2 E3 G3（S4 多利亚变亮）
    "G":     [43, 50, 55, 59],     # G2 D3 G3 B3
    "Dmaj":  [38, 45, 50, 54],     # D2 A2 D3 F#3（片尾皮卡第三度）
    "Dmaj7": [38, 45, 50, 54, 57], # D2 A2 D3 F#3 A3
}

# 「能量脉冲动机」：三个上行电流脉冲（D4→A4→D5），接一记下落长脉冲（D5→D2）。
# 单位：相对起点秒偏移 / 起始 MIDI / 结束 MIDI / 时长 / 力度
MOTIF_REGEN = [
    (0.00, 62, 62, 0.50, 0.056),   # D4 电流脉冲（回收开始）
    (0.34, 69, 69, 0.50, 0.064),   # A4（被推上去）
    (0.68, 74, 74, 0.56, 0.060),   # D5（到峰值）
    (1.16, 74, 38, 2.30, 0.080),   # D5→D2：下落长脉冲（能量落进电池）
]

# 片尾：改写成 D 大调的上行四音，再收在同一条下落脉冲上（「能量回来了」）
MOTIF_MAJOR = [
    (0.00, 62, 62, 0.52, 0.054),   # D4
    (0.36, 66, 66, 0.52, 0.060),   # F#4（皮卡第三度）
    (0.72, 69, 69, 0.56, 0.058),   # A4
    (1.10, 74, 74, 0.60, 0.062),   # D5
    (1.62, 74, 38, 2.40, 0.078),   # 下落长脉冲
]

# 拆解段「电流经过三件套」的上行琶音（轮端→电机→逆变器→电池）
ARP_UP = [62, 65, 69, 74, 77]

ROLE_ORDER = ["hook", "judge", "teardown", "account", "limits", "rejudge", "close"]


def roles_for(nseg):
    """7 段标准结构；若发言稿分段数不同则合并/拆分，保证每段都有音乐任务。"""
    if nseg == 7:
        return list(ROLE_ORDER)
    if nseg == 6:
        return ["hook", "judge", "teardown", "account", "limits", "close"]
    if nseg == 5:
        return ["hook", "judge", "teardown", "limits", "close"]
    if nseg == 8:
        return ["hook", "judge", "teardown", "account", "account2", "limits", "rejudge", "close"]
    return ["hook"] + ["judge"] * max(0, nseg - 2) + ["close"]


def load_tl():
    with open(TIMELINE_FULL, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 调度 / 渲染
def render(tl, verbose=True):
    total = float(tl["total"])
    N = int(round(total * SR))
    mix = np.zeros((2, N), dtype=F32)
    events = []
    segs = sorted(tl["segments"], key=lambda s: s["start"])
    roles = roles_for(len(segs))
    cold = float(tl["cold_open"])

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

    def st(seg, f):
        """段内按句序号比例取句起点。"""
        ss = seg["sentences"]
        idx = min(len(ss) - 1, max(0, int(round(f * (len(ss) - 1)))))
        return ss[idx]["start"]

    def en(seg, f):
        ss = seg["sentences"]
        idx = min(len(ss) - 1, max(0, int(round(f * (len(ss) - 1)))))
        return ss[idx]["end"]

    def chord_pads(seg, prog, amp=0.0100, cutoff=1300, root_amp=0.017, att=1.3, rel=1.7):
        for j, (f, name, d) in enumerate(prog):
            t0 = st(seg, f) - 0.15
            d = min(d, seg["end"] - t0)
            if d <= 0.4:
                continue
            put("padL_%s_%s" % (seg["id"], name), t0,
                pad([hz(m) for m in CHORDS[name][1:]], d, amp, att=att, rel=rel,
                    cutoff=cutoff, seed=1100 + 40 * j + 7), pan=-0.38)
            put("padR_%s_%s" % (seg["id"], name), t0 + 0.04,
                pad([hz(m) for m in CHORDS[name][1:]], d, amp * 0.86, att=att + 0.1,
                    rel=rel, cutoff=cutoff * 0.92, seed=1120 + 40 * j + 7), pan=0.38)
            put("root_%s_%s" % (seg["id"], name), t0,
                low_drone(hz(CHORDS[name][0] - 12), min(d, 5.5), root_amp,
                          att=0.8, rel=1.1, seed=1140 + 40 * j + 7), pan=0.0)

    def pulse_grid(seg, t0, t1, step, amp, seed0, tag, f=73.4, pan_alt=True):
        t, i = t0, 0
        while t < t1 - 0.03:
            pan = (-0.24 if i % 2 else 0.24) if pan_alt else 0.0
            put("pulse_%s_%s_%d" % (seg["id"], tag, i), t,
                current_pulse(amp * (0.9 + 0.2 * ((i * 7) % 3) / 2.0), seed=seed0 + i, f=f),
                pan=pan)
            i += 1
            t += step
        return i

    def wheel(seg, t0, t1, step, amp, seed0):
        t, i = t0, 0
        while t < t1 - 0.03:
            put("wheel_%s_%d" % (seg["id"], i), t,
                sub_thump(amp * (1.0 if i % 2 == 0 else 0.78), seed=seed0 + i,
                          f_hi=60.0, f_lo=35.0, dur=0.62, tau=0.20), pan=0.0)
            i += 1
            t += step
        return i

    def relay_ticks(seg, t0, t1, step, amp, seed0):
        t, i = t0, 0
        while t < t1 - 0.03:
            put("relay_%s_%d" % (seg["id"], i), t,
                relay_click(amp * (1.0 if i % 2 == 0 else 0.74), seed=seed0 + i),
                pan=0.30 if i % 2 else -0.30)
            i += 1
            t += step
        return i

    def motif(seg, f, table, seed0, gain=1.0, pan=0.0):
        t0 = st(seg, f) + 0.18
        for i, (off, m0, m1, dur, amp) in enumerate(table):
            note = energy_pulse(hz(m0), hz(m1), dur, amp * gain, seed=seed0 + i)
            put("motif_%s_%d" % (seg["id"], i), t0 + off, note,
                pan=pan + (0.06 if i % 2 else -0.06), gain=1.0)

    # ============================================================ cold open 0–cold
    put("cold_drone", 0.0, low_drone(hz(26), cold + 0.50, 0.030, att=1.0, rel=0.8, seed=600), pan=0.0)
    put("cold_sub", 0.0, low_drone(hz(33), cold + 0.40, 0.012, att=1.2, rel=1.0, seed=601), pan=0.0)
    # 片头极短（本期冷开场设计仅 ~0.6s，第一句就进钩子）：一记电流脉冲 + 一记继电器
    put("cold_pulse1", max(0.03, cold * 0.30), current_pulse(0.050, seed=610, f=hz(38)), pan=-0.15)
    if cold >= 1.2:
        put("cold_motif_a", cold * 0.45, energy_pulse(hz(62), hz(62), 0.50, 0.052, seed=620), pan=-0.10)
        put("cold_relay", max(0.05, cold - 0.40), relay_click(0.026, seed=630), pan=0.0)
    else:
        put("cold_relay", max(0.05, cold - 0.15), relay_click(0.026, seed=630), pan=0.0)

    # ============================================================ 逐段
    for seg, role in zip(segs, roles):
        s0, s1 = seg["start"], seg["end"]
        dur = max(0.5, s1 - s0)

        if role == "hook":
            # S1 钩子：极稀疏 —— 低 drone + 稀疏动机碎片 + 两拍一记电流脉冲
            put("hook_drone", s0 + 0.10, low_drone(hz(26), dur - 0.10, 0.021, att=1.2, rel=1.2, seed=700), pan=0.0)
            put("hook_drone2", s0 + 0.30, low_drone(hz(33), dur - 0.20, 0.010, att=1.4, rel=1.2, seed=701), pan=0.0)
            pulse_grid(seg, s0 + 0.60, s1 - 0.35, 2.0 * BEAT, 0.030, 710, "hook", f=hz(38))
            relay_ticks(seg, s0 + 0.90, s1 - 0.40, 4.0 * BEAT, 0.014, 730)
            ss = seg["sentences"]
            if len(ss) >= 2:
                put("hook_note1", ss[1]["start"] + 0.30,
                    energy_pulse(hz(69), hz(69), 0.55, 0.046, seed=740), pan=0.08)
            if len(ss) >= 4:
                put("hook_note2", ss[-2]["start"] + 0.30,
                    energy_pulse(hz(74), hz(74), 0.60, 0.050, seed=741), pan=-0.08)
            put("hook_fall", en(seg, 0.0) - 1.35,
                energy_pulse(hz(74), hz(38), 1.60, 0.056, seed=742), pan=0.0)

        elif role == "judge":
            # S2 立判：八分电流脉冲 + 低频「轮转」+ 继电器 + Dm–Bb–F–C pad
            chord_pads(seg, [(0.0, "Dm", 4.6), (0.30, "Bb", 4.2), (0.58, "F", 4.2), (0.80, "C", 4.8)],
                       amp=0.0096, cutoff=1250, root_amp=0.017)
            pulse_grid(seg, s0 + 0.45, s1 - 0.50, E8, 0.030, 800, "e8", f=hz(38))
            wheel(seg, s0 + 0.30, s1 - 0.40, 2.0 * BEAT, 0.033, 840)
            relay_ticks(seg, s0 + 0.70, s1 - 0.45, 4.0 * BEAT, 0.019, 870)
            motif(seg, 0.62, MOTIF_REGEN, 900, gain=1.0)
            put("judge_fall", en(seg, 0.0) - 1.50,
                energy_pulse(hz(74), hz(38), 1.80, 0.062, seed=920), pan=0.0)

        elif role == "teardown":
            # S3 拆解：电机上扫层 + 电流脉冲加密 + 低音级进下行 + 继电器开关
            chord_pads(seg, [(0.0, "Dm", 4.4), (0.26, "Gm", 4.2), (0.52, "Bb", 4.0), (0.76, "A", 4.4)],
                       amp=0.0094, cutoff=1350, root_amp=0.016)
            m0 = s0 + 0.25
            for j in range(3):
                t0 = m0 + j * (dur / 3.4)
                if t0 + 2.0 < s1:
                    put("tear_motor%d" % j, t0, motor_up(hz(36), hz(48), min(2.6, s1 - t0 - 0.2),
                                                         0.016, seed=1000 + j), pan=-0.30 + 0.30 * j)
            pulse_grid(seg, s0 + 0.35, s1 - 0.45, E8, 0.032, 1040, "e8", f=hz(38))
            wheel(seg, s0 + 0.30, s1 - 0.40, 2.0 * BEAT, 0.030, 1080)
            relay_ticks(seg, s0 + 0.50, s1 - 0.40, 2.0 * BEAT, 0.017, 1120)
            # 低音级进下行：D2 → C2 → Bb1 → A1（能量沿通道往下走）
            for j, (f, m) in enumerate([(0.10, 38), (0.36, 36), (0.62, 34), (0.84, 33)]):
                t0 = st(seg, f) + 0.10
                put("tear_bass%d" % j, t0, low_drone(hz(m), min(3.6, s1 - t0 - 0.1), 0.028,
                                                     att=0.25, rel=0.8, seed=1150 + j), pan=0.0)
            # 「电流经过三件套」：上行琶音 4 个音
            arp_t = st(seg, 0.42) + 0.20
            for i, m in enumerate(ARP_UP):
                put("tear_arp%d" % i, arp_t + i * S16 * 2,
                    energy_pulse(hz(m), hz(m), 0.34, 0.036 - 0.003 * i, seed=1180 + i),
                    pan=(-0.20 if i % 2 else 0.20))
            put("tear_fall", en(seg, 0.0) - 1.40,
                energy_pulse(hz(74), hz(38), 1.70, 0.060, seed=1200), pan=0.0)

        elif role == "account":
            # S4 能量账：十六分电流脉冲 + 「记账」琶音 + 动机完整陈述 + 损耗处退开
            chord_pads(seg, [(0.0, "Dm", 4.2), (0.20, "Em", 3.8), (0.40, "F", 3.8),
                             (0.60, "G", 3.8), (0.80, "Dm", 4.2)],
                       amp=0.0098, cutoff=1900, root_amp=0.015)
            pulse_grid(seg, s0 + 0.30, s1 - 0.55, S16, 0.021, 1300, "s16", f=hz(38), pan_alt=False)
            wheel(seg, s0 + 0.25, s1 - 0.45, 2.0 * BEAT, 0.028, 1340)
            relay_ticks(seg, s0 + 0.60, s1 - 0.45, 4.0 * BEAT, 0.014, 1370)
            # 「记账」拨弦：D F A D 循环，每八分一个音（像在算账）
            ledger = [62, 65, 69, 74, 69, 65]
            t, i = s0 + 0.40, 0
            while t < s1 - 0.70 and i < 180:
                m = ledger[i % len(ledger)]
                put("acct_pluck%d" % i, t, pluck(hz(m + 12), 0.55, 0.026 - 0.002 * (i % 3),
                                                 seed=1400 + i), pan=(-0.26 if i % 2 else 0.26))
                i += 1
                t += E8 * (2 if i % 6 == 0 else 1)
            motif(seg, 0.44, MOTIF_REGEN, 1500, gain=1.05)
            # 效率/损耗处：一记低频 + 音乐退开（gate 由人工调度曲线做）
            put("acct_loss", en(seg, 0.78), sub_thump(0.038, seed=1560, f_hi=58.0, f_lo=34.0,
                                                      dur=1.0, tau=0.38), pan=0.0)
            put("acct_fall", en(seg, 0.0) - 1.30,
                energy_pulse(hz(74), hz(38), 1.60, 0.058, seed=1580), pan=0.0)

        elif role in ("limits", "account2"):
            # S5 限制：几乎抽空 —— 慢继电器 + 四条下落脉冲（一条限制一记）
            put("lim_drone", s0 + 0.15, low_drone(hz(26), dur - 0.20, 0.020, att=1.4, rel=1.4, seed=1700), pan=0.0)
            chord_pads(seg, [(0.0, "Bb", 5.0), (0.34, "Gm", 4.6), (0.68, "Dm", 5.2)],
                       amp=0.0074, cutoff=900, root_amp=0.014, att=1.8, rel=2.0)
            relay_ticks(seg, s0 + 0.55, s1 - 0.50, 2.0 * BEAT, 0.015, 1740)
            ss = seg["sentences"]
            nlimit = min(4, len(ss))
            for j in range(nlimit):
                frac = 0.10 + 0.72 * (j / max(1, nlimit - 1)) if nlimit > 1 else 0.4
                t0 = st(seg, frac) + 0.20
                put("lim_pulse%d" % j, t0,
                    energy_pulse(hz(69), hz(38), 2.10, 0.052 - 0.006 * j, seed=1780 + j),
                    pan=-0.10 + 0.20 * (j % 2))
                put("lim_thud%d" % j, t0 + 0.05,
                    sub_thump(0.026, seed=1800 + j, f_hi=56.0, f_lo=33.0, dur=0.85, tau=0.30), pan=0.0)
            put("lim_fall", en(seg, 0.0) - 1.30,
                energy_pulse(hz(62), hz(38), 1.50, 0.046, seed=1820), pan=0.0)

        elif role == "rejudge":
            # S6 再判：脉冲回归 + 动机两次 + 上行充能
            chord_pads(seg, [(0.0, "F", 4.6), (0.26, "C", 4.2), (0.52, "Dm", 4.2), (0.76, "Bb", 4.6)],
                       amp=0.0100, cutoff=1500, root_amp=0.016)
            pulse_grid(seg, s0 + 0.40, s1 - 0.55, E8, 0.024, 1900, "e8", f=hz(38))
            wheel(seg, s0 + 0.30, s1 - 0.45, 2.0 * BEAT, 0.026, 1940)
            relay_ticks(seg, s0 + 0.70, s1 - 0.50, 4.0 * BEAT, 0.014, 1970)
            motif(seg, 0.28, MOTIF_REGEN, 2000, gain=0.95)
            motif(seg, 0.70, MOTIF_REGEN, 2020, gain=0.85)
            # 明亮对位：F A C F
            for i, (off, m) in enumerate([(0.0, 65), (0.9, 69), (1.8, 72), (2.7, 69)]):
                put("rej_counter%d" % i, st(seg, 0.45) + 0.25 + off,
                    pluck(hz(m + 12), 1.20, 0.024 - 0.002 * i, seed=2060 + i), pan=0.0)
            put("rej_rise", en(seg, 0.0) - 3.0, charge_rise(hz(38), hz(62), 3.0, 0.020, seed=2090), pan=0.0)

        elif role == "close":
            # S7 收束：D 小调 → D 大调（皮卡第三度）+ 动机大调版 + 充能上扫 + 片尾 pad
            ss = seg["sentences"]
            last_t = ss[-1]["start"]
            chord_pads(seg, [(0.0, "Dm", 4.6), (0.36, "Bb", 4.2)], amp=0.0100, cutoff=1350, root_amp=0.016)
            t_maj = max(s0 + 1.0, last_t - 1.6)
            put("close_padL_maj", t_maj, pad([hz(m) for m in CHORDS["Dmaj7"][1:]],
                                             max(2.0, s1 - t_maj + 1.2), 0.0110,
                                             att=0.5, rel=2.4, cutoff=1900, seed=2100), pan=-0.38)
            put("close_padR_maj", t_maj + 0.04, pad([hz(m) for m in CHORDS["Dmaj7"][1:]],
                                                    max(2.0, s1 - t_maj + 1.2), 0.0096,
                                                    att=0.6, rel=2.4, cutoff=1750, seed=2101), pan=0.38)
            put("close_root_maj", t_maj, low_drone(hz(26), max(2.5, s1 - t_maj + 1.8), 0.020,
                                                   att=0.5, rel=1.8, seed=2102), pan=0.0)
            # 末句前的电流脉冲逐渐拉开（八分 → 拍 → 两拍）
            t, step, i = s0 + 0.40, E8, 0
            while t < last_t - 0.30 and i < 90:
                put("close_pulse%d" % i, t, current_pulse(0.026 - 0.004 * min(2, i // 24),
                                                          seed=2120 + i, f=hz(38)),
                    pan=(-0.20 if i % 2 else 0.20))
                i += 1
                step = E8 if t < last_t - 8 else (BEAT if t < last_t - 4 else 2.0 * BEAT)
                t += step
            # 片尾动机（D 大调）+ 充能上扫
            for i, (off, m0, m1, dd, amp) in enumerate(MOTIF_MAJOR):
                put("close_motif%d" % i, last_t + 0.35 + off,
                    energy_pulse(hz(m0), hz(m1), dd, amp, seed=2140 + i), pan=0.0)
            put("close_charge", last_t + 0.10, charge_rise(hz(38), hz(74), 4.2, 0.022, seed=2160), pan=0.0)
            put("close_hit", last_t + 0.06, sub_thump(0.034, seed=2161, f_hi=58.0, f_lo=32.0,
                                                      dur=1.4, tau=0.50), pan=0.0)

    # ============================================================ 片尾（outro 口播之下）
    tail_t = max(segs[-1]["end"] - 0.6, total - 9.0)
    put("tail_padL", tail_t, pad([hz(m) for m in CHORDS["Dmaj7"]], max(2.0, total - tail_t - 0.2),
                                 0.0125, att=0.8, rel=2.8, cutoff=2000, seed=2500), pan=-0.35)
    put("tail_padR", tail_t + 0.03, pad([hz(m) for m in CHORDS["Dmaj7"]], max(2.0, total - tail_t - 0.2),
                                        0.0105, att=0.9, rel=2.8, cutoff=1800, seed=2501), pan=0.35)
    put("tail_root", tail_t, low_drone(hz(26), max(2.0, total - tail_t - 0.1), 0.012,
                                       att=0.8, rel=2.2, seed=2502), pan=0.0)
    if total - 3.4 > tail_t:
        put("tail_fall", total - 3.4, energy_pulse(hz(74), hz(38), 2.6, 0.045, seed=2510), pan=0.0)

    # ============================================================ 空气底噪（分块 pink，交叉淡化）
    # 只在整体有音乐的织体下托一层极轻的空气；人工停乐窗会被 gate 归零（真静默）
    air_amp = 0.0016
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
            mix[chn, pos:pos + L] += x * w * F32(air_amp)
            pos += bs
            k += 1

    # ============================================================ 混响（分块卷积 + 低切 IR）
    ir = make_ir(1.8)
    for chn in range(2):
        send = mix[chn].copy()
        fft_conv_add(mix[chn], send, ir[chn], gain=0.24, block=1 << 17)
        del send
    del ir

    # ============================================================ 人工调度曲线（4 段真静默 + 退开）
    def _win(t0, t1, level, ramp=0.35):
        return (max(0.0, t0), min(total - 0.01, t1), level, ramp)

    def boundary(prev_role, next_role, level=0.0):
        """段落交界的人工停乐窗：用「上一段末句结束 → 下一段首句开始」的旁白留白，
        与 segment_gap 大小无关（ep08 设计上段间只留 0.2s，停乐窗靠末句后的气口）。"""
        idx = roles.index(prev_role)
        prev_seg = segs[idx]
        nxt_seg = segs[idx + 1]
        a = prev_seg["sentences"][-1]["end"] + 0.15
        b = nxt_seg["sentences"][0]["start"] - 0.10
        if b - a < 0.55:
            return None
        return _win(a, b, level, 0.30)

    gates = []
    for pr, nr in [("judge", "teardown"), ("account", "limits"), ("limits", "rejudge"), ("rejudge", "close")]:
        if pr in roles and nr in roles and roles.index(nr) == roles.index(pr) + 1:
            g = boundary(pr, nr)
            if g:
                gates.append(g)
    # 能量账内：效率/损耗句前退开（不让音乐盖住「损耗」）
    if "account" in roles:
        acc = segs[roles.index("account")]
        anchor = st(acc, 0.72)
        gates.append(_win(anchor - 0.55, anchor + 2.6, 0.48, 0.40))
    # 四条限制总览前音乐退开 0.6s（稿件 §3.5）；整段压暗交给 build_audio 的分段电平
    if "limits" in roles:
        lim = segs[roles.index("limits")]
        gates.append(_win(lim["start"] - 0.20, lim["start"] + 0.80, 0.42, 0.35))
    # 金句后 0.5s 静默再上片尾声明（稿件 §3.5；取收束段末句前的旁白留白）
    if "close" in roles:
        cls = segs[roles.index("close")]
        ss = cls["sentences"]
        if len(ss) >= 2:
            a = ss[-2]["end"] + 0.10
            b = ss[-1]["start"] - 0.10
            if b - a >= 0.45:
                gates.append(_win(a, b, 0.0, 0.25))

    # 按时间排序（不同来源的 gate 可能交错），保证 apply_curve 的时间点单调
    gates.sort(key=lambda g: g[0])
    GATE_T, GATE_V = [0.0], [1.0]
    last_gate = 0.0
    for t0, t1, lv, ramp in gates:
        t1 = max(t0 + 0.05, min(total - 0.02, t1))
        start = max(last_gate + 0.01, t0 - ramp)
        end = min(total - 0.02, t1 + ramp)
        if end <= start:
            continue
        GATE_T += [start, t0, t1, end]
        GATE_V += [1.0, lv, lv, 1.0]
        last_gate = end
    # 片尾淡出
    fade_start = max(last_gate + 0.01, total - 2.2)
    GATE_T += [fade_start, total]
    GATE_V += [1.0, 0.0]
    assert len(GATE_T) == len(GATE_V), "gate points mismatch"
    apply_curve(mix, GATE_T, GATE_V)

    # 峰值归一（留约 8dB 余量；build_audio 再做音乐床电平调度）
    peak = 0.0
    for pos in range(0, N, SR):
        peak = max(peak, float(np.max(np.abs(mix[:, pos:pos + SR]))))
    target_peak = 0.40
    scale = F32(target_peak / max(peak, 1e-9))
    for pos in range(0, N, SR):
        mix[:, pos:pos + SR] *= scale
    rms = float(np.sqrt(np.mean(mix.astype(np.float64) ** 2)))

    # ---- 逐段实测电平 / 事件密度
    sections, densities = {}, {}
    for seg in segs:
        i0, i1 = int(seg["start"] * SR), min(N, int(seg["end"] * SR))
        if i1 > i0:
            r = float(np.sqrt(np.mean(mix[:, i0:i1].astype(np.float64) ** 2)))
            sections[seg["id"]] = round(20 * np.log10(max(r, 1e-12)), 2)
            cnt = sum(1 for e in events if seg["start"] <= e["t"] < seg["end"])
            densities[seg["id"]] = dict(events=cnt, per_s=round(cnt / max(seg["dur"], 1e-9), 3))
    i0, i1 = 0, min(N, int(cold * SR))
    if i1 > i0:
        r = float(np.sqrt(np.mean(mix[:, i0:i1].astype(np.float64) ** 2)))
        sections["cold_open"] = round(20 * np.log10(max(r, 1e-12)), 2)
    else:
        sections["cold_open"] = -240.0
    i0 = int(tail_t * SR)
    r = float(np.sqrt(np.mean(mix[:, i0:N].astype(np.float64) ** 2)))
    sections["tail"] = round(20 * np.log10(max(r, 1e-12)), 2)

    # ---- 静默窗（设计值，实测见 build_audio 报告）
    gate_windows = []
    for i in range(len(GATE_T) - 1):
        if GATE_V[i] < 0.15 and GATE_V[i + 1] < 0.15:
            gate_windows.append([round(GATE_T[i], 3), round(GATE_T[i + 1], 3)])

    meta = dict(
        total=total, sample_rate=SR, n_events=len(events),
        peak_dbfs=round(20 * np.log10(max(target_peak, 1e-9)), 2),
        rms_dbfs=round(20 * np.log10(max(rms, 1e-9)), 2),
        theme="可逆的能量通道 —— 电流脉冲 / 能量回流 / 电机上扫 / 回收提示",
        key=("D minor (main) -> D dorian (S4 energy ledger, E natural brightens) -> "
             "D minor + Bb (S5 limits, darkest) -> F major colour (S6 re-judge) -> "
             "D major Picardy third (S7 close: energy comes back)"),
        tempo_bpm=BPM, beat_s=round(BEAT, 4), beat_hz=round(1.0 / BEAT, 4),
        pulse_grid=dict(eighth_s=round(E8, 4), sixteenth_s=round(S16, 4),
                        eighth_hz=round(1.0 / E8, 3), sixteenth_hz=round(1.0 / S16, 3)),
        motif=("能量脉冲动机（原创）：三个快速上行电流脉冲 D4->A4->D5，接一记下落长脉冲 "
               "D5->D2（能量从轮端落进电池）；片尾改成 D 大调 D4->F#4->A4->D5 再下落收束。"
               "方向与 ep04 心跳、ep05 收网动机均不同"),
        motif_notes=dict(regen=["D4", "A4", "D5", "D5->D2"], major=["D4", "F#4", "A4", "D5", "D5->D2"]),
        roles=dict(zip([s["id"] for s in segs], roles)),
        sections=sections, densities=densities,
        gate_windows=gate_windows,
        events=events)
    if verbose:
        print("[music] peak=%.2f dBFS rms=%.2f dBFS events=%d" % (
            meta["peak_dbfs"], meta["rms_dbfs"], len(events)))
        print("[music] 90BPM / beat %.4fs; 八分脉冲 %.3f Hz；动机=D4-A4-D5 + D5->D2" % (
            BEAT, 1.0 / E8))
        for k, v in sections.items():
            print("    %-12s %7.1f dBFS   %s" % (k, v, densities.get(k, "")))
        print("[music] 人工停乐窗:", gate_windows)
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
    os.makedirs(AUDIO, exist_ok=True)
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
