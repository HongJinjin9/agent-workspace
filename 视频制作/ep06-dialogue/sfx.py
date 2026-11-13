#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep06 音频 —— 自合成语义音效（纯 numpy，无外部素材 / 无曲库）
=============================================================
原则（稿件 §2.6）：全片 **不超过 6 处**，只在判决落下的瞬间，不做逐镜音效。本期 6 处：

  1. page_turn       翻页：老规矩翻开厚手册（沉重纸页 + 一次压实）   （ACT1_07「那怎么算？」前 0.45s，M：翻开手册）
  2. stamp_thud      盖章：判决落下的一枚红印——纸面闷响 + 低频落点 （ACT1_05「这是热力学」句后 0.20s）
  3. tablet_tap      点击：小账本手指点在数字上（玻璃/平板轻响）     （ACT2_03「一万三千四百三十八台」前 0.35s，L：手指点在数字上）
  4. verdict_impact  判决落点：还差九百九十三台的深低频冲击          （ACT2_09「还差九百九十三台」+0.10s）
  5. pen_scratch     笔尖划线：钢笔在手册上划出一条线                （ACT3_05「当年我划的这条线」+0.25s）
  6. verdict_soft    最重一句的轻落点：账没错，是账本背后的东西变了  （ACT4_12 +0.30s，克制，不轰）

时间点全部从 work/timeline_audio.json 的幕/句锚点推导，推导结果写死进
work/sfx/sfx_meta.json，并供 build_audio.py 读取。

输出：work/sfx/*.wav（48kHz 立体声 24bit，峰值 0.80）+ work/sfx/sfx_meta.json
用法：python3 sfx.py
"""
import json
import os

import numpy as np

ROOT = "/app/vedio/ep06-dialogue"
SR = 48000
TIMELINE = os.path.join(ROOT, "work", "timeline_audio.json")
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


def normalize(x, target_peak=0.80):
    p = float(np.max(np.abs(x)))
    return x * (target_peak / p) if p > 0 else x


# ---------------------------------------------------------------- 6 个语义音效
def page_turn(seed=0):
    """翻页：厚手册的一页被掀起、翻过去、压实——两段纸声 + 一次低频「扑」。
    比普通翻页更沉：册子厚，纸页有重量。"""
    dur = 0.95
    n = int(dur * SR)
    t = np.arange(n) / SR
    lift = band_noise(n, 700, 6500, seed + 1, decay=0.22)
    land = band_noise(n, 350, 3800, seed + 2, decay=0.10)
    flutter = 0.40 + 0.60 * np.abs(np.sin(2 * np.pi * 9.0 * t + 0.6 * np.sin(2 * np.pi * 2.3 * t)))
    sig = lift * flutter * np.clip(1 - t / 0.42, 0, 1)
    sig += 0.75 * land * np.exp(-((t - 0.52) ** 2) / (2 * 0.070 ** 2))
    f = 120.0 * np.exp(-np.maximum(t - 0.45, 0) / 0.020) + 68.0
    thump = np.sin(2 * np.pi * f * np.maximum(t - 0.45, 0)) * np.exp(-np.maximum(t - 0.45, 0) / 0.09)
    sig += 0.55 * thump * (t >= 0.45)
    return sig * env_ar(n, 0.004, 0.18)


def stamp_thud(seed=0):
    """盖章：手起章落——纸面瞬态 + 低频落点 + 桌面回弹；一记就收住（判决不容置疑）。"""
    dur = 0.60
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 108.0 * np.exp(-t / 0.032) + 56.0 * (1.0 - np.exp(-t / 0.032))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.145)
    body += 0.35 * np.sin(2 * ph + 0.4) * np.exp(-t / 0.075)
    slap = band_noise(n, 260, 3400, seed + 1, decay=0.018) * 0.85
    slap += band_noise(n, 1600, 7500, seed + 2, decay=0.007) * 0.32
    sig = body + slap * env_ar(n, 0.001, 0.030)
    return sig * env_ar(n, 0.0015, 0.26)


def tablet_tap(seed=0):
    """平板点击：指尖敲在玻璃上的短促「哒」+ 一点点数字屏的电流尾音。"""
    dur = 0.30
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 320.0 * np.exp(-t / 0.012) + 210.0 * (1.0 - np.exp(-t / 0.012))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.045)
    body += 0.45 * np.sin(2 * np.pi * 1860.0 * t + 0.3) * np.exp(-t / 0.020)
    click = band_noise(n, 1200, 9000, seed + 1, decay=0.005) * 0.6
    sig = body + click * env_ar(n, 0.0008, 0.010)
    sig += 0.05 * np.sin(2 * np.pi * 880.0 * t) * np.exp(-t / 0.06)
    return sig * env_ar(n, 0.001, 0.10)


def verdict_impact(seed=0):
    """判决落点：深低频下沉 + 一层短促纸张/金属泛音；为「还差九百九十三台」的落点。"""
    dur = 2.2
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 64.0 * np.exp(-t / 0.12) + 30.0 * (1.0 - np.exp(-t / 0.12))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.60)
    body += 0.30 * np.sin(2 * ph + 0.3) * np.exp(-t / 0.28)
    body += 0.13 * np.sin(2 * np.pi * 35.0 * t) * np.exp(-t / 0.9)
    click = band_noise(n, 240, 4600, seed + 1, decay=0.024) * 0.38
    sig = body + click * env_ar(n, 0.001, 0.03)
    # 一条很轻的「纸页被震起」的高频尾（判决落在纸上）
    sig += 0.05 * band_noise(n, 2500, 8000, seed + 2, decay=0.18) * env_ar(n, 0.02, 0.4)
    return sig * env_ar(n, 0.002, 0.9)


def pen_scratch(seed=0):
    """笔尖划线：钢笔尖在纸上快速划出一条线——带限摩擦 + 不规则高频颗粒。"""
    dur = 0.85
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    base = band_noise(n, 1800, 9000, seed + 1, tilt=-0.1)
    grain = band_noise(n, 3200, 12000, seed + 2)
    # 划线速度略不均：用低频随机包络做「沙沙」的起伏
    lfo = 0.55 + 0.45 * np.abs(np.sin(2 * np.pi * 6.0 * t + 0.8 * np.sin(2 * np.pi * 1.3 * t)))
    sig = base * lfo * 0.8 + 0.35 * grain * (0.4 + 0.6 * lfo)
    e = np.clip(t / 0.06, 0, 1) * np.clip((dur - t) / 0.22, 0, 1)
    # 收笔的一下轻顿
    sig += 0.25 * band_noise(n, 1200, 5000, seed + 3) * np.exp(-((t - 0.68) ** 2) / (2 * 0.05 ** 2))
    return sig * e


def verdict_soft(seed=0):
    """最重一句的轻落点：只留一层很浅的低频「碰」，不轰、不煽。"""
    dur = 1.4
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 70.0 * np.exp(-t / 0.10) + 40.0 * (1.0 - np.exp(-t / 0.10))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.46)
    body += 0.22 * np.sin(2 * ph + 0.4) * np.exp(-t / 0.26)
    soft = band_noise(n, 200, 2200, seed + 1, decay=0.035) * 0.16
    sig = body + soft * env_ar(n, 0.001, 0.05)
    return sig * env_ar(n, 0.002, 0.60)


SFX = [
    ("page_turn", page_turn, 1, -0.10),
    ("stamp_thud", stamp_thud, 2, 0.04),
    ("tablet_tap", tablet_tap, 3, 0.20),
    ("verdict_impact", verdict_impact, 4, 0.0),
    ("pen_scratch", pen_scratch, 5, -0.06),
    ("verdict_soft", verdict_soft, 6, 0.0),
]


# ---------------------------------------------------------------- 定时（从 timeline 推导）
def load_tl():
    with open(TIMELINE, "r", encoding="utf-8") as f:
        return json.load(f)


def _sent(tl, sid):
    for seg in tl["segments"]:
        for s in seg["sentences"]:
            if "%s_%02d" % (seg["id"], s["i"]) == sid:
                return s
    raise KeyError(sid)


def placements(tl):
    seg = {s["id"]: s for s in tl["segments"]}

    def s0(sid):
        return _sent(tl, sid)["start"]

    def e0(sid):
        return _sent(tl, sid)["end"]

    return [
        dict(name="page_turn", t=round(s0("ACT1_07") - 0.45, 3), gain=0.34, pan=-0.10,
             anchor="ACT1_07「那怎么算？」前 0.45s（M：翻开手册）",
             why="老规矩翻开厚手册：纸页掀起、翻过去、压实"),
        dict(name="stamp_thud", t=round(e0("ACT1_05") + 0.20, 3), gain=0.46, pan=0.04,
             anchor="ACT1_05「这是热力学」句后 0.20s",
             why="判决落下：一枚红印压下去（盖章声）"),
        dict(name="tablet_tap", t=round(s0("ACT2_03") - 0.35, 3), gain=0.30, pan=0.20,
             anchor="ACT2_03「一万三千四百三十八台」前 0.35s（L：手指点在数字上）",
             why="小账本手指点在平板的数字上"),
        dict(name="verdict_impact", t=round(s0("ACT2_09") + 0.10, 3), gain=0.48, pan=0.0,
             anchor="ACT2_09「还差九百九十三台」+0.10s",
             why="判决落点：数字反超的深低频冲击"),
        dict(name="pen_scratch", t=round(s0("ACT3_05") + 0.25, 3), gain=0.26, pan=-0.06,
             anchor="ACT3_05「当年我划的这条线」+0.25s",
             why="笔尖在手册上划出一条线（M 划线）"),
        dict(name="verdict_soft", t=round(s0("ACT4_12") + 0.30, 3), gain=0.30, pan=0.0,
             anchor="ACT4_12「是账本背后的东西，变了」+0.30s",
             why="全片最重一句的轻落点：不轰，只留一层低频"),
    ]


def generate_all(force=False):
    os.makedirs(SFX_DIR, exist_ok=True)
    meta = {}
    for name, fn, seed, pan in SFX:
        path = os.path.join(SFX_DIR, name + ".wav")
        x = fn(seed=abs(seed) + 23)
        if x.ndim == 1:
            x = to_stereo(x, pan=pan)
        x = normalize(np.asarray(x, dtype=np.float64), 0.80)
        write_wav24(path, x)
        m = x.mean(axis=0)
        rms = float(np.sqrt(np.mean(m ** 2)))
        meta[name] = dict(file=os.path.relpath(path, ROOT),
                          duration=round(x.shape[1] / SR, 4),
                          peak_dbfs=round(20 * np.log10(max(np.max(np.abs(x)), 1e-9)), 2),
                          rms_dbfs=round(20 * np.log10(max(rms, 1e-12)), 2),
                          note=(fn.__doc__ or "").split("：")[0])
    tl = load_tl()
    meta["_placed_events"] = placements(tl)
    meta["_timeline"] = dict(total=tl["total"], cold_open=tl["cold_open"],
                             outro=tl["outro"], act_gap=tl["act_gap"])
    with open(os.path.join(SFX_DIR, "sfx_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta


if __name__ == "__main__":
    m = generate_all(force=True)
    for k, v in m.items():
        if k.startswith("_"):
            continue
        print("[sfx] %-16s %.2fs peak=%6.1f dBFS rms=%6.1f dBFS" % (
            k, v["duration"], v["peak_dbfs"], v["rms_dbfs"]))
    print("[sfx] placements (from timeline):")
    for e in m["_placed_events"]:
        print("    %-16s t=%8.3fs gain=%.2f pan=%+.2f  %s" % (
            e["name"], e["t"], e["gain"], e["pan"], e["why"]))
    print("[sfx] wrote", SFX_DIR)
