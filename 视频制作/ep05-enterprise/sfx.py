#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep05 音频 —— 自合成音效（纯 numpy，无外部素材 / 无曲库）
=========================================================
原则（稿件 §2.7 + 制作优化意见 §5.2 D）：全片不超过 8 处，只在语义节点出现，
不做「每个镜头切点一个音效」。本期 8 处，语义母题是「网 / 层级 / 齿轮 / 审批」：

  1. stamp_thud      盖章：一枚章压下去，纸面闷响 + 低频落点     （S1_02「签七个字」）
  2. paper_flip      翻纸：文件一路递过去、翻页的沙沙声           （S1_03「等批下来」）
  3. network_connect 连线：数字线「啪」地接通 + 高频 chirp        （S2_04「管二十个人」关系数暴涨）
  4. gear_clunk      齿轮咬合：加一层时的机械落锁 + 齿状余响      （S3_04「但加层有个副作用」）
  5. elevator_ding   电梯叮：每加一层多停一次的金属铃             （S3_07「多一道审批」）
  6. riser           上行 riser：从 S5 的疲劳里抬起，进入 S6 收束 （S6 段首前 1.30s）
  7. impact_heavy    全片最重一锤的低频落点                       （S4_09「所有人的理性」）
  8. impact_soft     最后一句「远了一点」的轻落点（克制，不轰）   （S6_15「远了一点」）

时间点全部从 work/timeline_audio.json 的段/句锚点推导：句内锚字按「字符位置比例」
在句实测 [start,end] 内线性插值（句级 TTS 语速近似均匀，误差小于半句），
推导结果写死进 work/sfx/sfx_meta.json，并供 build_audio.py 读取。

输出：work/sfx/*.wav（48kHz 立体声 24bit，峰值 0.80）+ work/sfx/sfx_meta.json
用法：python3 sfx.py
"""
import json
import os

import numpy as np

ROOT = "/app/vedio/ep05-enterprise"
SR = 48000
TIMELINE = os.path.join(ROOT, "work", "timeline_audio.json")
SFX_DIR = os.path.join(ROOT, "work", "sfx")


# ---------------------------------------------------------------- 基础
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


# ---------------------------------------------------------------- 8 个语义音效
def stamp_thud(seed=0):
    """盖章：手起章落——纸面闷响（宽带瞬态）+ 低频落点 + 台面回弹。"""
    dur = 0.52
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 105.0 * np.exp(-t / 0.035) + 58.0 * (1.0 - np.exp(-t / 0.035))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.13)
    body += 0.35 * np.sin(2 * ph + 0.4) * np.exp(-t / 0.07)
    slap = band_noise(n, 250, 3200, seed + 1, decay=0.020) * 0.85
    slap += band_noise(n, 1600, 7000, seed + 2, decay=0.008) * 0.30
    sig = body + slap * env_ar(n, 0.001, 0.030)
    return sig * env_ar(n, 0.0015, 0.24)


def paper_flip(seed=0):
    """翻纸：纸张被递过去、翻页的沙沙声；两段噪声，中间有一次轻顿。"""
    dur = 0.62
    n = int(dur * SR)
    t = np.arange(n) / SR
    a = band_noise(n, 900, 7000, seed + 1, decay=0.16)
    b = band_noise(n, 500, 4200, seed + 2, decay=0.12)
    # 纸张的「抖动」幅度：不规则颤音
    flutter = 0.45 + 0.55 * np.abs(np.sin(2 * np.pi * 11.0 * t + 0.7 * np.sin(2 * np.pi * 3.1 * t)))
    sig = a * flutter * np.clip(1 - t / 0.42, 0, 1)
    sig += 0.55 * b * np.exp(-((t - 0.36) ** 2) / (2 * 0.055 ** 2))
    return sig * env_ar(n, 0.004, 0.10)


def network_connect(seed=0):
    """连线：一根线「啪」地接通——短促 click + 900→1600Hz 的电流 chirp + 尾音。"""
    dur = 0.40
    n = int(dur * SR)
    t = np.arange(n) / SR
    u = np.clip(t / 0.16, 0, 1)
    f = 900.0 * (1600.0 / 900.0) ** u
    ph = 2 * np.pi * np.cumsum(f) / SR
    chirp = np.sin(ph) * (1 - np.exp(-t / 0.004)) * np.exp(-np.maximum(t - 0.10, 0) / 0.06)
    chirp += 0.30 * np.sin(2 * ph + 0.3) * np.exp(-t / 0.10)
    click = band_noise(n, 1800, 11000, seed + 1, decay=0.006) * 0.9
    click += band_noise(n, 300, 1600, seed + 2, decay=0.012) * 0.4
    sig = chirp + click * env_ar(n, 0.0008, 0.02)
    return sig * env_ar(n, 0.001, 0.14)


def gear_clunk(seed=0):
    """齿轮咬合：加一层时机械落锁——金属冲击 + 4 齿余响，越收越紧。"""
    dur = 0.85
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 120.0 * np.exp(-t / 0.04) + 62.0 * (1.0 - np.exp(-t / 0.04))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.16)
    body += 0.4 * np.sin(2 * ph + 0.5) * np.exp(-t / 0.09)
    metal = band_noise(n, 1200, 6200, seed + 1, decay=0.014) * 0.55
    sig = body + metal * env_ar(n, 0.001, 0.02)
    # 齿状余响：0.30/0.44/0.56/0.66s 四次渐弱金属 click（齿一个接一个咬上）
    rng = np.random.default_rng(seed + 3)
    for j, (t0, g) in enumerate([(0.30, 0.42), (0.44, 0.30), (0.56, 0.20), (0.66, 0.13)]):
        n0 = int(t0 * SR)
        if n0 >= n:
            break
        tt = t[:n - n0]
        c = (band_noise(len(tt), 900, 5200, seed + 10 + j, decay=0.012) * 0.7
             + 0.6 * np.sin(2 * np.pi * (640.0 - 40 * j) * tt) * np.exp(-tt / 0.020))
        sig[n0:] += c * g * (0.8 + 0.4 * rng.random())
    return sig * env_ar(n, 0.0015, 0.30)


def elevator_ding(seed=0):
    """电梯叮：金属铃——两个非谐分音 + 长衰减，像电梯到层的提示。"""
    dur = 1.15
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float64)
    for fm, a, tau in [(1318.5, 1.0, 0.55), (1977.8, 0.45, 0.42),
                       (2637.0, 0.22, 0.30), (659.3, 0.35, 0.70)]:
        det = 1.0 + 0.0004 * (np.random.default_rng(seed + int(fm)).random() - 0.5)
        sig += a * np.sin(2 * np.pi * fm * det * t) * np.exp(-t / tau)
    strike = band_noise(n, 2000, 12000, seed + 1, decay=0.007) * 0.55
    sig += strike * env_ar(n, 0.0005, 0.02)
    return sig * env_ar(n, 0.001, 0.55)


def riser(seed=0):
    """上行 riser：1.6s，从低频向上收窄的噪声 + 上行低音，收在 S6 段首（从疲劳里抬起）。"""
    dur = 1.6
    n = int(dur * SR)
    t = np.arange(n) / SR
    a = band_noise(n, 120, 700, seed)
    b = band_noise(n, 600, 3400, seed + 1)
    c = band_noise(n, 2200, 9000, seed + 2)
    u = t / dur
    x = 0.9 * a * (1 - u) + 0.5 * b * u + 0.24 * c * u ** 2
    f = 72.0 * (1 + 2.6 * u ** 1.6)
    tone = 0.30 * np.sin(2 * np.pi * np.cumsum(f) / SR)
    return (x + tone) * (u ** 1.7) * env_ar(n, 0.35, 0.09)


def impact_heavy(seed=0):
    """全片最重一锤：深低频下沉 + 一次短促冲击 + 极轻的网线微光（不轰头）。"""
    dur = 2.4
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 62.0 * np.exp(-t / 0.13) + 29.0 * (1.0 - np.exp(-t / 0.13))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.62)
    body += 0.30 * np.sin(2 * ph + 0.3) * np.exp(-t / 0.30)
    body += 0.14 * np.sin(2 * np.pi * 34.0 * t) * np.exp(-t / 0.95)
    click = band_noise(n, 260, 4200, seed + 1, decay=0.026) * 0.40
    sig = body + click * env_ar(n, 0.001, 0.03)
    # 轻的「网线」泛音：A5/E6 各一点，短促
    for k, (fm, a) in enumerate([(880.0, 0.045), (1318.5, 0.026)]):
        sig += a * np.sin(2 * np.pi * fm * t + k) * np.exp(-t / 0.40)
    return sig * env_ar(n, 0.002, 0.95)


def impact_soft(seed=0):
    """最后一句的轻落点：只留一层很浅的低频「碰」，不轰、不煽。"""
    dur = 1.3
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 72.0 * np.exp(-t / 0.09) + 41.0 * (1.0 - np.exp(-t / 0.09))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.42)
    body += 0.22 * np.sin(2 * ph + 0.4) * np.exp(-t / 0.24)
    soft = band_noise(n, 180, 2400, seed + 1, decay=0.030) * 0.18
    sig = body + soft * env_ar(n, 0.001, 0.04)
    return sig * env_ar(n, 0.002, 0.55)


SFX = [
    ("stamp_thud", stamp_thud, 1, 0.02),
    ("paper_flip", paper_flip, 2, -0.12),
    ("network_connect", network_connect, 3, 0.18),
    ("gear_clunk", gear_clunk, 4, -0.05),
    ("elevator_ding", elevator_ding, 5, 0.22),
    ("riser", riser, 6, 0.0),
    ("impact_heavy", impact_heavy, 7, 0.0),
    ("impact_soft", impact_soft, 8, 0.0),
]


# ---------------------------------------------------------------- 定时（从 timeline 推导）
def load_tl():
    with open(TIMELINE, "r", encoding="utf-8") as f:
        return json.load(f)


def _sent(tl, sid):
    for seg in tl["segments"]:
        for s in seg["sentences"]:
            key = "%s_%02d" % (seg["id"], s["i"])
            if key == sid:
                return s
    raise KeyError(sid)


def at_char(sid, needle, tl, fallback=0.5):
    """句内锚字 -> 绝对时间：按字符位置比例在句实测 [start,end] 内线性插值。"""
    s = _sent(tl, sid)
    text = s["text"]
    idx = text.find(needle)
    rel = ((idx + 0.5 * len(needle)) / max(len(text), 1)) if idx >= 0 else fallback
    return s["start"] + rel * (s["end"] - s["start"]), rel


def placements(tl):
    """8 处语义音效的放置表（时间由段/句锚点推导，推导逻辑在本函数里）。"""
    seg = {s["id"]: s for s in tl["segments"]}
    t_stamp, r1 = at_char("S1_02", "签七个字", tl)
    t_paper, r2 = at_char("S1_03", "等批下来", tl)
    t_net, r3 = at_char("S2_04", "管二十个人", tl)
    t_gear, r4 = at_char("S3_04", "加层", tl)
    t_ding, r5 = at_char("S3_07", "多一道审批", tl)
    t_rise = seg["S6"]["start"] - 1.30
    t_imp, r6 = at_char("S4_09", "所有人的理性", tl)
    t_soft, r7 = at_char("S6_15", "远了一点", tl)
    return [
        dict(name="stamp_thud", t=round(t_stamp, 3), gain=0.50, pan=0.02,
             anchor="S1_02 句内「签七个字」(char %.2f)" % r1,
             why="盖章：一枚章压下去，纸面闷响 + 低频落点（「每递一次盖一个章」）"),
        dict(name="paper_flip", t=round(t_paper, 3), gain=0.30, pan=-0.12,
             anchor="S1_03 句内「等批下来」(char %.2f)" % r2,
             why="文件一路递过去的翻纸沙沙声（过五关的物理感）"),
        dict(name="network_connect", t=round(t_net, 3), gain=0.36, pan=0.18,
             anchor="S2_04 句内「管二十个人」(char %.2f)" % r3,
             why="关系数按乘法暴涨：一根根线「啪」地接通"),
        dict(name="gear_clunk", t=round(t_gear, 3), gain=0.40, pan=-0.05,
             anchor="S3_04 句内「加层」(char %.2f)" % r4,
             why="加一层：机械落锁 + 齿状余响，越收越紧"),
        dict(name="elevator_ding", t=round(t_ding, 3), gain=0.28, pan=0.22,
             anchor="S3_07 句内「多一道审批」(char %.2f)" % r5,
             why="每加一层，电梯要多停一次的金属铃"),
        dict(name="riser", t=round(t_rise, 3), gain=0.30, pan=0.0,
             anchor="S6 段首前 1.30s", why="从 S5 的疲劳里抬起，进入 S6 收束"),
        dict(name="impact_heavy", t=round(t_imp, 3), gain=0.50, pan=0.0,
             anchor="S4_09 句内「所有人的理性」(char %.2f)" % r6,
             why="全片最重一锤：所有人的理性加在一起，成了整体的不理性"),
        dict(name="impact_soft", t=round(t_soft, 3), gain=0.30, pan=0.0,
             anchor="S6_15 句内「远了一点」(char %.2f)" % r7,
             why="最后一句「离那个最初想解决的问题远了一点」的轻落点（克制）"),
    ]


# ---------------------------------------------------------------- 生成
def generate_all(force=False):
    os.makedirs(SFX_DIR, exist_ok=True)
    meta = {}
    for name, fn, seed, pan in SFX:
        path = os.path.join(SFX_DIR, name + ".wav")
        x = fn(seed=abs(seed) + 17)
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
                             outro=tl["outro"], segment_gap=tl["segment_gap"])
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
