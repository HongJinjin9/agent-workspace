#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep08 音频 —— 自合成语义音效（纯 numpy，无外部素材 / 无曲库）
=============================================================
原则（制作优化意见 §5.2 D + PLAN §2.3）：全片 **不超过 8 处**，只在语义节点出现，
不做「每个镜头切点一个音效」。本期 8 处，语义母题是「可逆的能量通道 / 电流 / 回收」：

  1. regen_whoosh   能量回流 whoosh：动能从轮子手里被抢回来的那一下     （开场/立判的「松油门」
                                                                        或「动能抢回来」语义）
  2. relay_clunk    继电器吸合：主接触器「咔—哒」两段金属，能量路径接通 （逆变器/电池接上）
  3. motor_sweep    电机上扫：转子被反拖、转速爬升的啸叫上扫             （「电机反过来当发电机」）
  4. regen_chime    回收提示音：仪表上一声轻提示（双音金属铃）          （「仪表多出一个绿色小条」）
  5. inverter_buzz  逆变器电流声：交流/直流来回变的低频嗡鸣             （「交流变直流」）
  6. heat_hiss      损耗/发热：能量没回收的部分变成热的嘶声              （「效率/损耗」落点）
  7. limit_beep     限制提示：两声轻柔的「不回收」提示音                 （满电/低温/高速/ABS 限制）
  8. final_charge   收束充能：上扫微光 + 一记「咔」+ 轻嗡鸣             （收束句「能量回来了」）

时间点全部从 audio/work/timeline_audio.json 的段/句锚点推导：优先用关键词在锁定稿里
定位句子（逐字稿一旦锁定，锚点稳定），找不到时退回「段角色 + 句序比例」；
句内锚字按「字符位置比例」在句实测 [start,end] 内线性插值（句级 TTS 语速近似均匀，
误差小于半句）。推导结果写死进 audio/work/sfx/sfx_meta.json，供 build_audio.py 读取。

输出：audio/work/sfx/*.wav（48kHz 立体声 24bit，峰值 0.80）+ audio/work/sfx/sfx_meta.json
用法：python3 sfx.py
"""
import json
import os

import numpy as np

ROOT = "/app/vedio/ep08-regen"
AUDIO = os.path.join(ROOT, "audio", "work")
SR = 48000
TIMELINE = os.path.join(AUDIO, "timeline_audio.json")
SFX_DIR = os.path.join(AUDIO, "sfx")


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
def regen_whoosh(seed=0):
    """能量回流 whoosh：从轮端被「抽」回来的气流感——三段滤波噪声交叉上移 + 尾部低频到位。"""
    dur = 1.05
    n = int(dur * SR)
    t = np.arange(n) / SR
    u = np.clip(t / dur, 0, 1)
    a = band_noise(n, 120, 900, seed + 1, decay=0.0, tilt=-0.1)
    b = band_noise(n, 500, 2600, seed + 2, decay=0.0, tilt=0.1)
    c = band_noise(n, 1600, 7000, seed + 3, decay=0.0, tilt=0.2)
    w1 = np.clip(1.0 - u / 0.55, 0, 1) ** 1.4
    w2 = np.exp(-((u - 0.45) ** 2) / (2 * 0.20 ** 2))
    w3 = np.clip((u - 0.35) / 0.65, 0, 1) ** 1.8 * np.clip(1.25 - u, 0, 1)
    sig = 0.85 * a * w1 + 0.70 * b * w2 + 0.55 * c * w3
    # 尾部：能量「到位」的一记低频 pull（80→38Hz 下滑）
    tail = np.clip((t - 0.62) / 0.43, 0, 1)
    f = 82.0 * np.exp(-tail / 0.10) + 38.0 * (1 - np.exp(-tail / 0.10))
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig += np.sin(ph) * tail ** 1.5 * np.exp(-np.maximum(tail, 0) / 0.35) * 0.55
    sig *= env_ar(n, 0.10, 0.30)
    return sig


def relay_clunk(seed=0):
    """继电器吸合：衔铁「咔」+ 主触点「哒」两段金属瞬态 + 一记低频 thunk。"""
    dur = 0.42
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float64)
    for j, (off, g, f) in enumerate([(0.0, 1.0, 2900.0), (0.045, 0.85, 2100.0)]):
        i0 = int(off * SR)
        nn = n - i0
        tt = np.arange(nn) / SR
        c = band_noise(nn, 1500, 13000, seed + 1 + j, decay=0.0035) * 0.85
        c += 0.90 * np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.010)
        c += 0.35 * np.sin(2 * np.pi * f * 1.52 * tt + 0.6) * np.exp(-tt / 0.006)
        sig[i0:] += c * g
    # 低频 thunk：金属撞在支架上的钝响
    ff = 170.0 * np.exp(-t / 0.030) + 72.0 * (1.0 - np.exp(-t / 0.030))
    ph = 2 * np.pi * np.cumsum(ff) / SR
    sig += 0.65 * np.sin(ph) * np.exp(-t / 0.075)
    sig += 0.25 * band_noise(n, 200, 1800, seed + 4, decay=0.020)
    sig *= env_ar(n, 0.0008, 0.10)
    return sig


def motor_sweep(seed=0):
    """电机上扫：转子被反拖、转速爬升的啸叫（240→1500Hz 谐波上扫 + 齿槽脉动）。"""
    dur = 1.45
    n = int(dur * SR)
    t = np.arange(n) / SR
    u = np.clip(t / dur, 0, 1)
    f = 240.0 * (1500.0 / 240.0) ** (u ** 1.15)
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(ph) + 0.36 * np.sin(2 * ph + 0.3) + 0.16 * np.sin(3 * ph + 1.1)
    sig *= 0.62 + 0.38 * np.sin(2 * np.pi * 7.0 * u * dur) ** 2
    wh = band_noise(n, 500, 5000, seed + 1, decay=0.0, tilt=0.2)
    sig += 0.22 * wh * u ** 1.4
    sig *= env_ar(n, 0.18, 0.35)
    return sig


def regen_chime(seed=0):
    """回收提示音：仪表上一声轻提示——两个非谐分音的双音铃（短、克制、不刺耳）。"""
    dur = 1.10
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float64)
    for off, f, a in [(0.0, 1318.5, 1.0), (0.10, 1975.5, 0.62)]:
        i0 = int(off * SR)
        nn = n - i0
        tt = np.arange(nn) / SR
        c = (a * np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.60)
             + 0.30 * a * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt / 0.30))
        sig[i0:] += c
    strike = band_noise(n, 2500, 12000, seed + 1, decay=0.0045) * 0.22
    sig += strike * env_ar(n, 0.0005, 0.02)
    sig *= env_ar(n, 0.004, 0.45)
    return sig


def inverter_buzz(seed=0):
    """逆变器电流声：交流/直流来回变的低频嗡鸣（100/200/300Hz + 6Hz 幅度调制 + 轻高频噪声）。"""
    dur = 1.55
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = (np.sin(2 * np.pi * 100.0 * t)
           + 0.42 * np.sin(2 * np.pi * 200.0 * t + 0.5)
           + 0.22 * np.sin(2 * np.pi * 300.0 * t + 1.4)
           + 0.09 * np.sin(2 * np.pi * 400.0 * t + 2.2))
    sig *= 1.0 + 0.28 * np.sin(2 * np.pi * 6.0 * t)
    sig += 0.16 * band_noise(n, 900, 4200, seed + 1, decay=0.0) * (0.6 + 0.4 * np.sin(2 * np.pi * 6.0 * t))
    sig *= env_ar(n, 0.30, 0.45)
    return sig


def heat_hiss(seed=0):
    """损耗/发热：能量没回收的部分变成热——高频嘶声（4–9kHz）+ 一记低频落点。"""
    dur = 1.20
    n = int(dur * SR)
    t = np.arange(n) / SR
    hiss = band_noise(n, 3800, 9500, seed + 1, decay=0.0, tilt=0.3)
    hiss *= (1.0 - np.exp(-t / 0.10)) * np.exp(-np.maximum(t - 0.12, 0) / 0.55)
    ff = 120.0 * np.exp(-t / 0.06) + 58.0 * (1.0 - np.exp(-t / 0.06))
    ph = 2 * np.pi * np.cumsum(ff) / SR
    thud = np.sin(ph) * np.exp(-t / 0.22) * 0.55
    sig = hiss + thud
    sig *= env_ar(n, 0.002, 0.5)
    return sig


def limit_beep(seed=0):
    """限制提示：两声轻柔的「不回收」提示音（740→620Hz，短、圆润，不做报警器）。"""
    dur = 0.80
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float64)
    for j, (off, f, a) in enumerate([(0.0, 740.0, 1.0), (0.26, 620.0, 0.85)]):
        i0 = int(off * SR)
        nn = min(n - i0, int(0.22 * SR))
        tt = np.arange(nn) / SR
        if nn <= 8:
            break
        c = (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(2 * np.pi * 2 * f * tt + 0.4)
             + 0.08 * np.sin(2 * np.pi * 3 * f * tt + 1.0))
        c *= env_ar(nn, 0.012, 0.10)
        sig[i0:i0 + nn] += c * a
    sig *= env_ar(n, 0.006, 0.25)
    return sig


def final_charge(seed=0):
    """收束充能：上扫微光 + 一记「咔」+ 短嗡鸣，表示能量回到车上（不煽情、不炸）。"""
    dur = 1.85
    n = int(dur * SR)
    t = np.arange(n) / SR
    u = np.clip(t / dur, 0, 1)
    f = 90.0 * (360.0 / 90.0) ** (u ** 1.2)
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = (np.sin(ph) + 0.30 * np.sin(2 * ph + 0.4) + 0.12 * np.sin(3 * ph + 1.1)) * (u ** 1.5)
    sig += 0.16 * band_noise(n, 2600, 8000, seed + 1, decay=0.0, tilt=0.3) * (u ** 2.2)
    # 一记轻「咔」：接触器在收束时吸合
    click = np.zeros(n, dtype=np.float64)
    i0 = int(0.30 * SR)
    nn = n - i0
    tt = np.arange(nn) / SR
    click[i0:] = (band_noise(nn, 2000, 12000, seed + 2, decay=0.004) * 0.8
                  + 0.7 * np.sin(2 * np.pi * 2400.0 * tt) * np.exp(-tt / 0.010))
    sig += click * 0.35
    sig *= env_ar(n, 0.20, 0.45)
    return sig


SFX = [
    ("regen_whoosh", regen_whoosh, 1, 0.0),
    ("relay_clunk", relay_clunk, 2, 0.0),
    ("motor_sweep", motor_sweep, 3, -0.10),
    ("regen_chime", regen_chime, 4, 0.16),
    ("inverter_buzz", inverter_buzz, 5, -0.14),
    ("heat_hiss", heat_hiss, 6, 0.10),
    ("limit_beep", limit_beep, 7, 0.0),
    ("final_charge", final_charge, 8, 0.0),
]

# 每处音效的语义放置规格：优先按锁定稿关键词定位，找不到时按「段角色 + 句序比例」退回。
# 关键词只用于定位句子（不进画面/不朗读）；锁定稿即便微调措辞，锚点仍可解释。
SPECS = [
    dict(name="regen_whoosh", gain=0.46, pan=0.0,
         anchors=["松油门，车在充电", "松油门", "捡回来"],
         role="hook", frac=0.10,
         why="能量回流 whoosh：松油门那一下，动能开始往回走（钩子句）"),
    dict(name="regen_chime", gain=0.28, pan=0.16,
         anchors=["仪表上", "能量在往回走", "电量数字往上爬", "仪表"],
         role="hook", frac=0.30,
         why="回收提示音：仪表上能量条往回长的一声轻提示"),
    dict(name="motor_sweep", gain=0.32, pan=-0.10,
         anchors=["轮子反过来推着电机转", "被推着转就发电", "反过来推着电机"],
         role="judge", frac=0.55,
         why="电机上扫：轮子反拖电机、转子转速爬升的啸叫"),
    dict(name="relay_clunk", gain=0.34, pan=-0.06,
         anchors=["双向门", "逆变器"],
         role="teardown", frac=0.20,
         why="继电器吸合：逆变器这道「双向门」接通的咔—哒"),
    dict(name="inverter_buzz", gain=0.26, pan=-0.14,
         anchors=["直流", "交流"],
         role="teardown", frac=0.40,
         why="逆变器电流声：直流/交流来回变的低频嗡鸣"),
    dict(name="heat_hiss", gain=0.28, pan=0.10,
         anchors=["刹车盘上的热", "变成刹车盘", "热"],
         role="account", frac=0.35,
         why="损耗/发热：不回收就全变成刹车盘上的热"),
    dict(name="limit_beep", gain=0.26, pan=0.0,
         anchors=["不是随时都能回收", "随时都能回收", "第一条"],
         role="limits", frac=0.05,
         why="限制提示：两声轻柔的「现在不回收」提示音（进四条限制总览）"),
    dict(name="final_charge", gain=0.30, pan=0.0,
         anchors=["靠的不是魔法", "不是魔法"],
         role="close", frac=0.20,
         why="收束充能：松油门能充电靠的不是魔法——上扫微光 + 一记「咔」"),
]


# ---------------------------------------------------------------- 定时（从 timeline 推导）
def load_tl():
    with open(TIMELINE, "r", encoding="utf-8") as f:
        return json.load(f)


def _sent_list(tl):
    out = []
    for seg in tl["segments"]:
        for s in seg["sentences"]:
            out.append((seg, s))
    return out


def _roles(tl):
    """与 music.py 相同的段角色映射（不 import，避免耦合）。"""
    nseg = len(tl["segments"])
    if nseg == 7:
        return ["hook", "judge", "teardown", "account", "limits", "rejudge", "close"]
    if nseg == 6:
        return ["hook", "judge", "teardown", "account", "limits", "close"]
    if nseg == 5:
        return ["hook", "judge", "teardown", "limits", "close"]
    if nseg == 8:
        return ["hook", "judge", "teardown", "account", "account2", "limits", "rejudge", "close"]
    return ["hook"] + ["judge"] * max(0, nseg - 2) + ["close"]


def at_char(seg, s, needle, text=None):
    """句内锚字 -> 绝对时间：按字符位置比例在句实测 [start,end] 内线性插值。"""
    text = text if text is not None else s["text"]
    idx = text.find(needle)
    rel = ((idx + 0.5 * len(needle)) / max(len(text), 1)) if idx >= 0 else 0.5
    return s["start"] + rel * (s["end"] - s["start"]), rel


def placements(tl):
    """8 处语义音效的放置表（关键词定位优先，段角色+句序比例兜底）。"""
    segs = sorted(tl["segments"], key=lambda x: x["start"])
    roles = _roles(tl)
    role_seg = {r: segs[i] for i, r in enumerate(roles) if i < len(segs)}
    sents = _sent_list(tl)
    used = set()          # 已占用的句子（同一句不放两个音效）
    used_t = []           # 已占用的时间点（间隔 >= 0.9s）
    out = []
    for spec in SPECS:
        hit = None
        # 锚点按「精确 → 宽泛」优先级搜索：先找最具体的锚字，避免泛词提前命中
        for a in spec["anchors"]:
            if not a:
                continue
            for seg, s in sents:
                if id(s) in used:
                    continue
                if a in s["text"]:
                    hit = (seg, s, a)
                    break
            if hit:
                break
        if hit is not None:
            seg, s, a = hit
            t0, rel = at_char(seg, s, a, s["text"])
            anchor = "%s_%02d 句内「%s」(char %.2f)" % (seg["id"], s["i"], a, rel)
            src = "keyword"
        else:
            seg = role_seg.get(spec["role"], segs[-1])
            ss = seg["sentences"]
            idx = min(len(ss) - 1, max(0, int(round(spec["frac"] * (len(ss) - 1)))))
            s = ss[idx]
            t0 = s["start"] + 0.35 * (s["end"] - s["start"])
            anchor = "%s_%02d 段角色[%s] 句序比例 %.2f（未命中关键词，兜底）" % (
                seg["id"], s["i"], spec["role"], spec["frac"])
            src = "fallback"
        # 避免两个音效挤在同一句/同一时刻（保持「只在语义落点」）
        while any(abs(t0 - x) < 0.90 for x in used_t) or id(s) in used:
            t0 += 0.85
            if t0 > seg["end"] - 0.3:
                t0 = seg["end"] - 0.3
                break
        used.add(id(s))
        used_t.append(t0)
        out.append(dict(name=spec["name"], t=round(t0, 3), gain=spec["gain"], pan=spec["pan"],
                        anchor=anchor, why=spec["why"], source=src,
                        sid="%s_%02d" % (seg["id"], s["i"])))
    out.sort(key=lambda e: e["t"])
    return out


# ---------------------------------------------------------------- 生成
def generate_all(force=False):
    os.makedirs(SFX_DIR, exist_ok=True)
    meta = {}
    for name, fn, seed, pan in SFX:
        path = os.path.join(SFX_DIR, name + ".wav")
        if force or not os.path.exists(path):
            x = fn(seed=abs(seed) + 17)
            if x.ndim == 1:
                x = to_stereo(x, pan=pan)
            x = normalize(np.asarray(x, dtype=np.float64), 0.80)
            write_wav24(path, x)
        else:
            # 复用已有素材：按 24bit PCM 读回真实样本（RIFF 44B 头）
            raw = open(path, "rb").read()[44:]
            b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
            i24 = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
            i24 = np.where(i24 & 0x800000, i24 - 0x1000000, i24)
            x = (i24.reshape(-1, 2) / 8388608.0).T
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
        print("    %-16s t=%8.3fs gain=%.2f pan=%+.2f [%s] %s" % (
            e["name"], e["t"], e["gain"], e["pan"], e["source"], e["why"]))
    print("[sfx] wrote", SFX_DIR)
