#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep03 音频 —— 自合成音效（纯 numpy，版权干净）
=============================================
只在语义发生作用时使用，不做「每个切点一个音效」：
  pen_scratch  钢笔书写沙沙（S1「复制一下就交了」/ S4 分析处）
  page_slide   纸张滑动（S2「查资料」）
  stamp        印章落下 / 低频 thud（cold open 账页落印）
  impact       不可逆结论的 impact（S1 末「欠了判断力」/ S4「判断力债务」/ S6 标题句）
  whoosh       段落/空间转换的轻 whoosh（仅 S2 入口）
  riser        低频 riser（S6 第三问前）

输出 work/sfx/*.wav（48kHz 立体声 24bit）+ work/sfx/sfx_meta.json

用法：python3 sfx.py
"""
import json
import os

import numpy as np

ROOT = "/app/vedio/ep03-judgment"
SR = 48000
SFX_DIR = os.path.join(ROOT, "work", "sfx")


def band_noise(n, flo, fhi, seed, decay=0.0, tilt=0.0):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    lo = np.maximum(f, 1.0)
    mask = 1.0 / (1.0 + (lo / max(fhi, 1e-6)) ** 4)
    mask *= 1.0 / (1.0 + (max(flo, 1e-6) / lo) ** 4)
    if tilt:
        mask *= (lo / 1000.0) ** tilt
    y = np.fft.irfft(X * mask, n)
    y /= (np.max(np.abs(y)) + 1e-12)
    if decay > 0:
        t = np.arange(n) / SR
        y *= np.exp(-t / decay)
    return y


def env_ar(n, att, rel):
    e = np.ones(n, dtype=np.float64)
    na = min(n, int(att * SR))
    nr = min(n - na, int(rel * SR))
    if na > 0:
        e[:na] = 0.5 - 0.5 * np.cos(np.pi * np.arange(na) / na)
    if nr > 0:
        e[n - nr:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(nr) / nr)
    return e


def pen_scratch(seed=0):
    """钢笔书写：随机笔画起落的带限噪声 + 纸面摩擦底。"""
    dur = 2.0
    n = int(dur * SR)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    env = np.zeros(n)
    # 笔画：每 60–120ms 一笔，幅度随机，略带回钩
    pos = 0.02
    while pos < dur - 0.05:
        L = rng.uniform(0.045, 0.11)
        a = rng.uniform(0.35, 1.0)
        i0 = int(pos * SR)
        i1 = min(n, int((pos + L) * SR))
        seg = env_ar(i1 - i0, 0.012, L * 0.8) * a
        env[i0:i1] = np.maximum(env[i0:i1], seg)
        pos += L + rng.uniform(0.012, 0.05)
    hi = band_noise(n, 1700, 6800, seed + 1, tilt=0.3)
    mid = band_noise(n, 600, 2200, seed + 2)
    low = band_noise(n, 120, 700, seed + 3)
    sig = env * (0.75 * hi + 0.35 * mid) + 0.10 * low
    # 极轻的纸面底噪，避免数字静音感
    sig += 0.02 * band_noise(n, 200, 1200, seed + 4)
    sig *= env_ar(n, 0.03, 0.10)
    return sig


def page_slide(seed=0):
    """纸张滑动：低频驱动的气流噪声 + 轻微沙沙。"""
    dur = 0.75
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = band_noise(n, 350, 3200, seed, tilt=0.15)
    x += 0.4 * band_noise(n, 2000, 6500, seed + 1)
    e = np.exp(-((t - 0.22) ** 2) / (2 * 0.16 ** 2)) * env_ar(n, 0.02, 0.28)
    body = np.sin(2 * np.pi * 95 * t) * np.exp(-t / 0.16) * 0.15
    return x * e + body * e


def stamp(seed=0):
    """印章落下：低频 thud（音高下坠）+ 纸面撞击瞬态 + 短尾。"""
    dur = 1.0
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 82.0 * np.exp(-t / 0.10) + 44.0 * (1 - np.exp(-t / 0.10))
    phase = 2 * np.pi * np.cumsum(f) / SR
    thud = np.sin(phase) * np.exp(-t / 0.20)
    thud += 0.35 * np.sin(2 * phase) * np.exp(-t / 0.10)
    click = band_noise(n, 300, 3800, seed + 1, decay=0.020) * 0.55
    click += band_noise(n, 1200, 7000, seed + 2, decay=0.006) * 0.35
    sig = thud + click * env_ar(n, 0.001, 0.02)
    return sig * env_ar(n, 0.0015, 0.30)


def impact(seed=0):
    """不可逆结论 impact：比 stamp 更深、更长，带 sub 尾巴。"""
    dur = 2.2
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 70.0 * np.exp(-t / 0.14) + 33.0 * (1 - np.exp(-t / 0.14))
    phase = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(phase) * np.exp(-t / 0.55)
    body += 0.30 * np.sin(2 * phase + 0.4) * np.exp(-t / 0.30)
    body += 0.18 * np.sin(2 * np.pi * 41.2 * t) * np.exp(-t / 0.9)
    click = band_noise(n, 250, 5000, seed + 1, decay=0.028) * 0.45
    sig = body + click * env_ar(n, 0.001, 0.03)
    return sig * env_ar(n, 0.002, 0.9)


def whoosh(seed=0):
    """轻 whoosh：频带从低到高再回落，音量正弦包络（用于段落/空间转换）。"""
    dur = 0.95
    n = int(dur * SR)
    t = np.arange(n) / SR
    # 三段带限噪声交叉淡化模拟扫频
    a = band_noise(n, 220, 900, seed)
    b = band_noise(n, 700, 2600, seed + 1)
    c = band_noise(n, 2200, 7000, seed + 2)
    w1 = np.clip(1 - t / 0.45, 0, 1)
    w2 = np.exp(-((t - 0.42) ** 2) / (2 * 0.20 ** 2))
    w3 = np.clip((t - 0.35) / 0.6, 0, 1)
    sig = a * w1 + 0.8 * b * w2 + 0.45 * c * w3
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.4
    return sig * e


def riser(seed=0):
    """低频 riser：噪声带 + 上行的低频音，2.4s，结尾自然收（留给后面 impact/落点）。"""
    dur = 2.4
    n = int(dur * SR)
    t = np.arange(n) / SR
    a = band_noise(n, 120, 600, seed)
    b = band_noise(n, 500, 2600, seed + 1)
    c = band_noise(n, 2000, 8000, seed + 2)
    x = 0.9 * a * (1 - t / dur) + 0.5 * b * (t / dur) + 0.25 * c * (t / dur) ** 2
    f = 85.0 * (1 + 2.6 * (t / dur) ** 1.5)
    tone = 0.35 * np.sin(2 * np.pi * np.cumsum(f) / SR)
    e = (t / dur) ** 1.8
    sig = (x + tone) * e
    return sig * env_ar(n, 0.5, 0.18)


def to_stereo(x, pan=0.0):
    th = (pan + 1.0) * np.pi / 4.0
    return np.stack([x * np.cos(th), x * np.sin(th)], axis=0)


def write_wav24(path, x, sr=SR):
    if x.ndim == 1:
        x = np.stack([x, x], axis=0)
    pcm = np.ascontiguousarray((np.clip(x.T, -1.0, 1.0) * 8388607.0).astype("<i4"))
    b = pcm.view(np.uint8).reshape(-1, 4)[:, :3]
    data = b.tobytes()
    ch = x.shape[0]
    import struct
    hdr = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    hdr += b"fmt " + struct.pack("<IHHIIHH", 16, 1, ch, sr, sr * ch * 3, ch * 3, 24)
    hdr += b"data" + struct.pack("<I", len(data))
    with open(path, "wb") as f:
        f.write(hdr)
        f.write(data)


def normalize(x, target_peak=0.85):
    p = float(np.max(np.abs(x)))
    return x * (target_peak / p) if p > 0 else x


SFX = [
    ("pen_scratch_01", pen_scratch, -2),
    ("page_slide_01", page_slide, -3),
    ("stamp_01", stamp, -1),
    ("impact_01", impact, 0),
    ("whoosh_01", whoosh, 1),
    ("riser_01", riser, 2),
]


def generate_all(force=False):
    os.makedirs(SFX_DIR, exist_ok=True)
    meta = {}
    for name, fn, seed in SFX:
        path = os.path.join(SFX_DIR, name + ".wav")
        sig = fn(seed=abs(seed) + 17)
        sig = normalize(np.asarray(sig, dtype=np.float64), 0.80)
        if not force and os.path.exists(path):
            pass
        write_wav24(path, to_stereo(sig, pan=0.0))
        rms = float(np.sqrt(np.mean(sig ** 2)))
        meta[name] = dict(file=os.path.relpath(path, ROOT),
                          duration=round(len(sig) / SR, 4),
                          peak_dbfs=round(20 * np.log10(max(np.max(np.abs(sig)), 1e-9)), 2),
                          rms_dbfs=round(20 * np.log10(max(rms, 1e-12)), 2),
                          note=fn.__doc__.split("：")[0])
    with open(os.path.join(SFX_DIR, "sfx_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta


if __name__ == "__main__":
    m = generate_all(force=True)
    for k, v in m.items():
        print("[sfx] %-16s %.2fs peak=%6.1f dBFS rms=%6.1f dBFS" % (
            k, v["duration"], v["peak_dbfs"], v["rms_dbfs"]))
    print("[sfx] wrote", SFX_DIR)
