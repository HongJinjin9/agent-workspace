#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep04 音频 —— 自合成音效（纯 numpy，无外部素材 / 无曲库）
=========================================================
原则（稿件 §3.7 + 制作优化意见 §5.2 D）：全片不超过 8 处，只在语义节点出现，
不做「每个镜头切点一个音效」。本期 8 处：

  1. bump_thud    减速带「咚」——干净利落的一次收敛      （S2_02 句内「咚」字锚点）
  2. bump_rattle  减速带「咣当」——一次冲击 + 余振三晃    （S2_03 句内「咣当」字锚点）
  3. steer_friction 转向摩擦——方向盘变重/胎面侧滑的摩擦声（S3_06「方向盘」字锚点）
  4. motor_whine  电机上扫——零转速满扭矩的电流/电机音     （S4_06「电机」字锚点）
  5. jerk_impact  jerk 低频冲击——加速度突然出现            （S4_07「突然出现」字锚点）
  6. whoosh       空间转换 whoosh——S1→S2                    （S2_01 前 0.38s）
  7. riser        S5 合流前 riser——三线合流进段            （S5 段首前 1.55s）
  8. impact_merge S5 合流 impact——合流落点                  （S5_01 后 0.10s）

时间点全部从 work/timeline_audio.json 的段/句锚点推导：句内锚字按「字符位置比例」
在句实测 [start,end] 内线性插值（句级 TTS 语速近似均匀，误差小于半句），
推导结果写死进 work/sfx/sfx_meta.json，并供 build_audio.py 读取。

输出：work/sfx/*.wav（48kHz 立体声 24bit，峰值 0.80）+ work/sfx/sfx_meta.json
用法：python3 sfx.py
"""
import json
import os

import numpy as np

ROOT = "/app/vedio/ep04-body"
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


# ---------------------------------------------------------------- 8 个音效
def bump_thud(seed=0):
    """减速带「咚」：一次干净收敛的低频冲击——阻尼够，一次就结束。

    音高 95→48Hz 快速下坠 + 一次瞬态 + 极短尾（0.55s 内收住）。
    """
    dur = 0.55
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 95.0 * np.exp(-t / 0.045) + 47.0 * (1.0 - np.exp(-t / 0.045))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.145)
    body += 0.35 * np.sin(2 * ph + 0.4) * np.exp(-t / 0.075)
    body += 0.12 * np.sin(2 * np.pi * 135.0 * t) * np.exp(-t / 0.045)
    click = band_noise(n, 900, 5200, seed + 1, decay=0.010) * 0.55
    click += band_noise(n, 200, 1200, seed + 2, decay=0.020) * 0.35
    sig = body + click * env_ar(n, 0.001, 0.012)
    return sig * env_ar(n, 0.0015, 0.28)


def bump_rattle(seed=0):
    """减速带「咣当」：一次冲击后能量没吃完，接着晃三晃（0.45/0.85/1.25s 三次余振）。"""
    dur = 1.7
    n = int(dur * SR)
    t = np.arange(n) / SR
    # 主冲击（比 thud 更低、更拖）
    f = 88.0 * np.exp(-t / 0.06) + 42.0 * (1.0 - np.exp(-t / 0.06))
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(ph) * np.exp(-t / 0.26)
    sig += 0.40 * np.sin(2 * ph + 0.3) * np.exp(-t / 0.13)
    # 三次余振：金属/车身二次撞击，逐次衰减、音高略变
    for j, (t0, g, ft) in enumerate([(0.42, 0.55, 82.0), (0.80, 0.36, 74.0), (1.16, 0.22, 66.0)]):
        n0 = int(t0 * SR)
        tt = t[:n - n0]
        f2 = ft * np.exp(-tt / 0.035) + 52.0 * (1.0 - np.exp(-tt / 0.035))
        ph2 = 2 * np.pi * np.cumsum(f2) / SR
        knock = np.sin(ph2) * np.exp(-tt / 0.11)
        knock += 0.35 * np.sin(2 * np.pi * (400 + 90 * j) * tt) * np.exp(-tt / 0.05)
        knock += band_noise(len(tt), 600, 3800, seed + 10 + j, decay=0.012) * 0.30
        sig[n0:] += knock * g
    return sig * env_ar(n, 0.0015, 0.55)


def steer_friction(seed=0):
    """转向摩擦：方向盘变重、胎面侧滑的带限摩擦声；中间有轻微「粘滑」脉冲。"""
    dur = 1.05
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    base = band_noise(n, 700, 4200, seed + 1, tilt=-0.15)
    low = band_noise(n, 180, 800, seed + 2)
    # 粘滑：以 ~18Hz 的不规则幅度调制
    mod = 0.55 + 0.45 * np.abs(np.sin(2 * np.pi * 18.0 * t + 0.8 * np.sin(2 * np.pi * 1.7 * t)))
    sig = base * mod + 0.55 * low * (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 9.0 * t)))
    # 极轻的转向机「吱」——窄带 900–1400Hz 短脉冲
    sig += 0.25 * band_noise(n, 900, 1400, seed + 3) * np.exp(-((t - 0.35) ** 2) / (2 * 0.10 ** 2))
    e = np.clip(t / 0.10, 0, 1) * np.clip((dur - t) / 0.35, 0, 1)
    return sig * e


def motor_whine(seed=0):
    """电机音：零转速满扭矩——电流基频从 160Hz 上扫到 520Hz + 高次谐波 + 逆变器噪声。"""
    dur = 1.25
    n = int(dur * SR)
    t = np.arange(n) / SR
    u = np.clip(t / dur, 0, 1)
    f = 160.0 * (520.0 / 160.0) ** (u ** 1.4)
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(ph) * 0.55 + 0.28 * np.sin(2 * ph + 0.4) + 0.16 * np.sin(3 * ph + 1.2)
    sig += 0.10 * np.sin(4 * ph + 2.0)
    # 逆变器开关噪声（高频窄带「电流嘶」）
    sig += 0.22 * band_noise(n, 5200, 12000, seed + 1) * (0.4 + 0.6 * u)
    sig += 0.10 * band_noise(n, 1800, 4200, seed + 2)
    sig *= np.clip(t / 0.06, 0, 1) * np.clip((dur - t) / 0.30, 0, 1)
    return sig


def jerk_impact(seed=0):
    """jerk 低频冲击：加速度突然出现——比普通 impact 更「陡」，40→26Hz，快起慢收。"""
    dur = 1.9
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 72.0 * np.exp(-t / 0.09) + 27.0 * (1.0 - np.exp(-t / 0.09))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.50)
    body += 0.45 * np.sin(2 * ph + 0.5) * np.exp(-t / 0.22)
    body += 0.20 * np.sin(2 * np.pi * 38.0 * t) * np.exp(-t / 0.75)
    click = band_noise(n, 300, 6000, seed + 1, decay=0.024) * 0.55
    click += band_noise(n, 1600, 9000, seed + 2, decay=0.008) * 0.30
    sig = body + click * env_ar(n, 0.001, 0.02)
    return sig * env_ar(n, 0.002, 0.7)


def whoosh(seed=0):
    """空间转换 whoosh（S1→S2）：频带由低到高再回落，声像由左到右轻移。"""
    dur = 0.95
    n = int(dur * SR)
    t = np.arange(n) / SR
    a = band_noise(n, 180, 800, seed)
    b = band_noise(n, 650, 2600, seed + 1)
    c = band_noise(n, 2100, 7500, seed + 2)
    w1 = np.clip(1 - t / 0.45, 0, 1)
    w2 = np.exp(-((t - 0.42) ** 2) / (2 * 0.20 ** 2))
    w3 = np.clip((t - 0.35) / 0.6, 0, 1)
    sig = a * w1 + 0.8 * b * w2 + 0.45 * c * w3
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.4
    return sig * e


def riser(seed=0):
    """S5 合流 riser：三线合流前 1.6s 上行噪声 + 上行低音，收在段首。"""
    dur = 1.6
    n = int(dur * SR)
    t = np.arange(n) / SR
    a = band_noise(n, 110, 620, seed)
    b = band_noise(n, 500, 3000, seed + 1)
    c = band_noise(n, 2000, 9000, seed + 2)
    u = t / dur
    x = 0.9 * a * (1 - u) + 0.5 * b * u + 0.28 * c * u ** 2
    f = 78.0 * (1 + 2.4 * u ** 1.5)
    tone = 0.34 * np.sin(2 * np.pi * np.cumsum(f) / SR)
    e = u ** 1.7
    sig = (x + tone) * e
    return sig * env_ar(n, 0.35, 0.10)


def impact_merge(seed=0):
    """S5 合流 impact：深低频落点 + 一层明亮泛音「合流」闪光。"""
    dur = 2.6
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 64.0 * np.exp(-t / 0.16) + 30.0 * (1.0 - np.exp(-t / 0.16))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.70)
    body += 0.32 * np.sin(2 * ph + 0.3) * np.exp(-t / 0.35)
    body += 0.16 * np.sin(2 * np.pi * 36.0 * t) * np.exp(-t / 1.0)
    # 合流闪光：一组高音泛音（E5/B5/E6）短促起音
    shimmer = np.zeros(n, dtype=np.float64)
    for k, (fm, a) in enumerate([(659.26, 0.10), (987.77, 0.07), (1318.5, 0.045)]):
        shimmer += a * np.sin(2 * np.pi * fm * t + k) * np.exp(-t / 0.55)
    click = band_noise(n, 250, 5200, seed + 1, decay=0.030) * 0.42
    sig = body + shimmer * env_ar(n, 0.004, 0.8) + click * env_ar(n, 0.001, 0.03)
    return sig * env_ar(n, 0.002, 1.1)


SFX = [
    ("bump_thud", bump_thud, 1, 0.0),
    ("bump_rattle", bump_rattle, 2, 0.0),
    ("steer_friction", steer_friction, 3, -0.10),
    ("motor_whine", motor_whine, 4, 0.15),
    ("jerk_impact", jerk_impact, 5, 0.0),
    ("whoosh", whoosh, 6, -0.12),
    ("riser", riser, 7, 0.0),
    ("impact_merge", impact_merge, 8, 0.0),
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
    """8 处语义音效的放置表（时间由段/句锚点推导，写死推导逻辑在本函数里）。"""
    seg = {s["id"]: s for s in tl["segments"]}
    t_thud, r1 = at_char("S2_02", "咚", tl)
    t_rattle, r2 = at_char("S2_03", "咣当", tl)
    t_steer, r3 = at_char("S3_06", "方向盘", tl)
    t_motor, r4 = at_char("S4_06", "电机", tl)
    t_jerk, r5 = at_char("S4_07", "突然出现", tl)
    whoosh_t = seg["S2"]["start"] - 0.38
    riser_t = seg["S5"]["start"] - 1.55
    merge_t = seg["S5"]["sentences"][0]["start"] + 0.10
    return [
        dict(name="whoosh", t=round(whoosh_t, 3), gain=0.30, pan=-0.12,
             anchor="S2 段首前 0.38s", why="S1→S2 空间转换（全片唯一 whoosh）"),
        dict(name="bump_thud", t=round(t_thud, 3), gain=0.52, pan=0.06,
             anchor="S2_02 句内「咚」(char %.2f)" % r1,
             why="好车过减速带：阻尼够，一次收敛的「咚」"),
        dict(name="bump_rattle", t=round(t_rattle, 3), gain=0.44, pan=-0.06,
             anchor="S2_03 句内「咣当」(char %.2f)" % r2,
             why="阻尼不够：一次冲击 + 余振三晃的「咣当」"),
        dict(name="steer_friction", t=round(t_steer, 3), gain=0.26, pan=-0.10,
             anchor="S3_06 句内「方向盘」", why="过弯信息：方向盘变重/胎面摩擦"),
        dict(name="motor_whine", t=round(t_motor, 3), gain=0.24, pan=0.15,
             anchor="S4_06 句内「电机」", why="电机零转速满扭矩（电子音色上扫）"),
        dict(name="jerk_impact", t=round(t_jerk, 3), gain=0.50, pan=0.0,
             anchor="S4_07 句内「突然出现」", why="jerk：加速度突然出现，低频冲击"),
        dict(name="riser", t=round(riser_t, 3), gain=0.34, pan=0.0,
             anchor="S5 段首前 1.55s", why="三线合流前的上行 riser"),
        dict(name="impact_merge", t=round(merge_t, 3), gain=0.46, pan=0.0,
             anchor="S5_01 后 0.10s", why="S5 合流落点（心电图/发动机/身体合成一条线）"),
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
