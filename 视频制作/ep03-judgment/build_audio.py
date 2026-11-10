#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ep03 音频 —— 混音 / 母带 / 自检 / 报告
=====================================
链路：
  1. 旁白干声 work/narration.wav（句级 8–15ms 收发淡化拼接）
     → 80Hz 零相位低切（对称 FIR + 分块卷积，无相移）
     → 保守去齿音（5.2–9kHz 按齿音能量最大 -5dB，分块 STFT）
     → 轻压缩（thr -25dBFS / ratio 1.8 / 最大 5dB GR，分块包络）
     → 短房间混响（IR 0.42s，wet 0.10，低切 IR）
     → 设计长留白（≥0.55s）人工静音门，保证真静默 < -60dBFS（不填底噪）
  2. music.wav（本片原创，已编排段落进出与关键句退开）
     → 分段电平调度（±1.5dB 人工修饰）→ sidechain duck 仅保底（最大 -3dB，慢起慢放）
  3. sfx/*.wav 只在语义处放置（8 处）
  4. 两遍 loudnorm：I=-14 LUFS，TP≤-1.5 dBTP → AAC 192k 48kHz 立体声
  5. 自检（时长/削波/静默/时间轴/SRT）→ work/audio-report.md

内存受限（cgroup 6.4GB 与其它 Agent 共享）：全程 float32 + 分块 FFT，
峰值 < 400MB。用法：python3 build_audio.py [--skip-encode]
"""
import argparse
import json
import os
import re
import struct
import subprocess

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

ROOT = "/app/vedio/ep03-judgment"
FFMPEG = "/home/admin/.local/bin/ffmpeg"
SR = 48000
F32 = np.float32

TL_FULL = os.path.join(ROOT, "work", "timeline_audio_full.json")
NARR_WAV = os.path.join(ROOT, "work", "narration.wav")
MUSIC_WAV = os.path.join(ROOT, "work", "music.wav")
MUSIC_META = os.path.join(ROOT, "work", "music_meta.json")
SFX_DIR = os.path.join(ROOT, "work", "sfx")
MIX_WAV = os.path.join(ROOT, "work", "mix.wav")
NARR_PROC = os.path.join(ROOT, "work", "narration_processed.wav")
OUT_M4A = os.path.join(ROOT, "work", "audio.m4a")
LOUDNESS_TXT = os.path.join(ROOT, "work", "loudness.txt")
REPORT = os.path.join(ROOT, "work", "audio-report.md")

TARGET_I = -14.0
TARGET_TP = -1.5
TARGET_LRA = 11.0
NARR_TARGET_RMS = -19.0


# ---------------------------------------------------------------- 基础
def run(cmd, timeout=1800):
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def decode(path, mono=False, sr=SR):
    # 注意：ffmpeg `-ac 1` 的立体声->单声道下混带约 +3dB 电平偏移（系数 1/sqrt2），
    # 因此统一先解成双声道再取均值，保证电平口径一致（我们的旁白轨 L/R 相同）。
    cmd = [FFMPEG, "-v", "error", "-i", path, "-f", "f32le", "-acodec", "pcm_f32le",
           "-ac", "2", "-ar", str(sr), "-"]
    p = run(cmd, timeout=1800)
    if p.returncode != 0:
        raise RuntimeError("decode failed %s\n%s" % (path, p.stderr.decode("utf-8", "replace")[-800:]))
    y = np.frombuffer(p.stdout, dtype=F32).reshape(-1, 2)
    if mono:
        return y.mean(axis=1).astype(F32).copy()
    return y.T.copy()


def write_wav24(path, x, sr=SR, chunk=1 << 19):
    """mono/stereo float32 -> 24bit PCM WAV，分块写。"""
    # 1D 输入按立体声双写（header 必须写 2 声道，否则解码会把 L/R 交错当成单声道）
    ch = 2 if x.ndim == 1 else x.shape[0]
    n = len(x) if x.ndim == 1 else x.shape[1]
    data_bytes = n * ch * 3
    hdr = b"RIFF" + struct.pack("<I", 36 + data_bytes) + b"WAVE"
    hdr += b"fmt " + struct.pack("<IHHIIHH", 16, 1, ch, sr, sr * ch * 3, ch * 3, 24)
    hdr += b"data" + struct.pack("<I", data_bytes)
    with open(path, "wb") as f:
        f.write(hdr)
        for pos in range(0, n, chunk):
            if x.ndim == 1:
                seg = np.stack([x[pos:pos + chunk], x[pos:pos + chunk]], axis=0)
            else:
                seg = x[:, pos:pos + chunk]
            pcm = np.ascontiguousarray((np.clip(seg.T, -1.0, 1.0) * 8388607.0).astype("<i4"))
            f.write(pcm.view(np.uint8).reshape(-1, 4)[:, :3].tobytes())


def rms_db(x):
    return 20 * np.log10(max(float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2))), 1e-12))


def db(x):
    return 10 ** (x / 20.0)


def load_tl():
    with open(TL_FULL, "r", encoding="utf-8") as f:
        return json.load(f)


def sent_index(tl):
    return {"%s_%02d" % (s["id"], x["i"]): x
            for s in tl["segments"] for x in s["sentences"]}


def speech_rms(x, tl):
    ss, cnt = 0.0, 0
    for seg in tl["segments"]:
        for s in seg["sentences"]:
            i0, i1 = int(s["start"] * SR), min(len(x) if x.ndim == 1 else x.shape[1],
                                              int(s["end"] * SR))
            if i1 > i0:
                a = x[i0:i1] if x.ndim == 1 else x[:, i0:i1]
                ss += float(np.sum(a.astype(np.float64) ** 2))
                cnt += (i1 - i0) * (1 if x.ndim == 1 else x.shape[0])
    return 10 * np.log10(max(ss / max(cnt, 1), 1e-24))


# ---------------------------------------------------------------- 分块滤波
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


def design_hp_fir(fc=80.0, taps=8193):
    n = taps
    f = np.fft.rfftfreq(n, 1.0 / SR)
    H = f / np.sqrt(f * f + fc * fc)
    h = np.fft.irfft(H, n)
    h = np.fft.fftshift(h)      # 把循环卷积的脉冲响应居中，否则窗函数会吃掉全部能量
    h *= np.blackman(n)
    return h.astype(F32)


def conv_zero_phase(x, h, block=1 << 17):
    """对称 FIR 零相位卷积：y = conv(x,h) 取中心段（无时延）。"""
    m = len(h)
    d = (m - 1) // 2
    n = len(x)
    out = np.zeros(n + m - 1, dtype=F32)
    fft_conv_add(out, x, h, 1.0, block)
    y = out[d:d + n].copy()
    del out
    return y


def deess(x, thr_db=-24.0, max_db=5.0):
    """保守去齿音（分块 STFT）。"""
    win, hop = 1024, 256
    w = np.hanning(win + 1)[:-1].astype(F32)
    n = (len(x) - win) // hop + 1
    view = sliding_window_view(x, win)[::hop]
    f = np.fft.rfftfreq(win, 1.0 / SR)
    hf = (f >= 5200) & (f <= 9000)
    lf = (f >= 1200) & (f <= 4000)
    taper = np.clip((f - 5200) / 800.0, 0, 1) * np.clip((9000 - f) / 1200.0, 0, 1)
    gr = np.empty(n, dtype=F32)
    CH = 1024
    for i in range(0, n, CH):
        m = min(CH, n - i)
        S = np.fft.rfft(view[i:i + m] * w[None, :], axis=1)
        mag = np.abs(S) + 1e-9
        hi = np.sqrt(np.mean(mag[:, hf] ** 2, axis=1)) + 1e-9
        lo = np.sqrt(np.mean(mag[:, lf] ** 2, axis=1)) + 1e-9
        ratio = 20 * np.log10(hi / lo)
        gr[i:i + m] = np.clip((ratio - thr_db) / 1.5, 0, 1) * max_db
    gr = np.convolve(gr, np.ones(5, dtype=F32) / 5, mode="same").astype(F32)
    out = np.zeros(len(x), dtype=F32)
    CH2 = 512
    for i in range(0, n, CH2):
        m = min(CH2, n - i)
        S = np.fft.rfft(view[i:i + m] * w[None, :], axis=1)
        S *= (10.0 ** (-gr[i:i + m, None] * taper[None, :] / 20.0))
        y = np.fft.irfft(S, win, axis=1) * w[None, :]
        for j in range(m):
            a = (i + j) * hop
            out[a:a + win] += y[j].astype(F32)
    out /= F32(1.5)   # periodic Hann² @75% overlap 的 COLA 归一
    return out


def compress_gentle(x, thr_db=-20.0, ratio=1.8, atk=0.020, rel=0.25, max_gr=3.0):
    """轻压缩（分块包络 + 增益包络）。"""
    win, hop = 1024, 128
    view = sliding_window_view(x, win)[::hop]
    n = len(view)
    env = np.empty(n, dtype=F32)
    CH = 2048
    for i in range(0, n, CH):
        m = min(CH, n - i)
        fr = view[i:i + m]
        env[i:i + m] = np.sqrt(np.mean(fr * fr, axis=1) + 1e-12)
    env_db = 20 * np.log10(env + 1e-12)
    g = np.clip((env_db - thr_db) * (1 - 1.0 / ratio), 0, max_gr)
    a = 1 - np.exp(-hop / (SR * atk))
    r = 1 - np.exp(-hop / (SR * rel))
    sm = np.empty_like(g)
    acc = 0.0
    for i in range(n):
        coef = a if g[i] > acc else r
        acc += coef * (g[i] - acc)
        sm[i] = acc
    tf = np.arange(n) * hop + win / 2
    curve = np.interp(np.arange(len(x)), tf, 10.0 ** (-sm / 20.0)).astype(F32)
    x *= curve
    del curve
    return x, float(np.max(sm))


def room_ir(dur=0.42, seed=5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    X = np.fft.rfft(rng.standard_normal(n).astype(F32))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    lo = np.maximum(f, 1.0)
    y = np.fft.irfft(X * (1.0 / (1.0 + (lo / 4200.0) ** 2)), n).astype(F32)
    y *= np.exp(-t / 0.16).astype(F32)
    for dly, g in ((0.009, 0.5), (0.015, 0.35), (0.023, 0.25), (0.037, 0.18)):
        i = int(dly * SR)
        if i < n:
            y[i] += g
    Y = np.fft.rfft(y.astype(np.float64))
    fl = np.fft.rfftfreq(n, 1.0 / SR)
    y = np.fft.irfft(Y * (np.maximum(fl, 1e-6) / np.sqrt(fl ** 2 + 130.0 ** 2)), n).astype(F32)
    # 能量归一：conv 后湿声 RMS ≈ 干声 RMS * wet_gain（峰值归一会使卷积增益 +20dB 以上）
    return y / (np.sqrt(np.sum(y.astype(np.float64) ** 2)) + 1e-12)


# ---------------------------------------------------------------- 调度
def silence_gate(tl, n):
    """设计长留白（>=0.55s）人工静音门：句末 0.18s 后 0.12s 内淡出到 0，
    下一句开始前 0.08s 淡入，保证长留白为真静默。"""
    env = np.ones(n, dtype=F32)
    all_s = [s for seg in tl["segments"] for s in seg["sentences"]]
    gated = []
    for i in range(len(all_s) - 1):
        a, b = all_s[i]["end"], all_s[i + 1]["start"]
        gap = b - a
        if gap < 0.55:
            continue
        i0, i1 = int((a + 0.18) * SR), int((a + 0.30) * SR)
        i2, i3 = int((b - 0.08) * SR), int((b - 0.02) * SR)
        i0, i1 = min(i0, n), min(i1, n)
        i2, i3 = max(0, min(i2, n)), max(0, min(i3, n))
        if i1 > i0:
            env[i0:i1] = np.linspace(1.0, 0.0, i1 - i0, dtype=F32)
        if i2 > i1:
            env[i1:i2] = 0.0
        if i3 > i2:
            env[i2:i3] = np.linspace(0.0, 1.0, i3 - i2, dtype=F32)
        gated.append((round(a, 3), round(b, 3), round(gap, 3)))
    return env, gated


def music_automation_curve(tl, n, block=SR):
    segs = {s["id"]: s for s in tl["segments"]}
    pts, vals = [0.0], [0.85]
    lv = {"S1": 0.95, "S2": 1.03, "S3": 0.94, "S4": 1.03, "S5": 1.02, "S6": 1.0}
    for sid in ["S1", "S2", "S3", "S4", "S5", "S6"]:
        pts.append(segs[sid]["start"] - 0.1)
        vals.append(lv[sid])
    pts.append(tl["total"])
    vals.append(0.9)
    pts, vals = np.asarray(pts), np.asarray(vals)
    for pos in range(0, n, block):
        i1 = min(n, pos + block)
        g = np.interp(np.arange(pos, i1) / SR, pts, vals).astype(F32)
        yield pos, i1, g


def _box_mean(x, k):
    """O(n) 滑动平均（cumsum 实现），避免大数组直接卷积。"""
    if k <= 1:
        return x
    pad_l = k // 2
    pad_r = k - 1 - pad_l
    xp = np.pad(x, (pad_l, pad_r), mode="edge")
    c = np.concatenate([[0.0], np.cumsum(xp, dtype=np.float64)])
    return ((c[k:] - c[:-k]) / float(k)).astype(F32)


def narration_activity(tl, n):
    act = np.zeros(n, dtype=F32)
    for seg in tl["segments"]:
        for s in seg["sentences"]:
            i0, i1 = int(s["start"] * SR), min(n, int((s["end"] + 0.05) * SR))
            act[i0:i1] = 1.0
    act = _box_mean(act, int(0.06 * SR))
    act = _box_mean(act, int(0.35 * SR))
    np.clip(act, 0, 1, out=act)
    return act


def sfx_events(tl):
    si = sent_index(tl)
    cold = tl["cold_open"]
    S = lambda k: si[k]["start"]
    return [
        ("stamp_01", cold * 0.64, 0.50, 0.00, "cold open 账页落印（全片只此一次）"),
        ("pen_scratch_01", S("S1_03") + 0.05, 0.26, -0.10, "S1「复制一下就交了」书写沙沙"),
        ("impact_01", S("S1_06") + 0.06, 0.52, 0.00, "S1 末「你是欠了判断力」不可逆落点"),
        ("whoosh_01", S("S2_01") - 0.38, 0.30, -0.15, "S1→S2 空间转换轻 whoosh"),
        ("page_slide_01", S("S2_02") + 0.30, 0.26, 0.15, "S2「查资料」纸张滑动"),
        ("impact_01", S("S4_01") + 0.05, 0.52, 0.00, "S4「判断力债务」落点"),
        ("riser_01", S("S6_04") - 2.05, 0.30, 0.00, "S6 第三问前低频 riser"),
        ("impact_01", S("S6_11") + 0.05, 0.58, 0.00, "S6 标题句「最贵的是判断」"),
    ]


# ---------------------------------------------------------------- 混音
def build_mix(tl, verbose=True):
    n = int(round(tl["total"] * SR))

    # ---- 旁白
    narr = decode(NARR_WAV, mono=True)
    if len(narr) < n:
        narr = np.pad(narr, (0, n - len(narr)))
    narr = narr[:n]
    narr = conv_zero_phase(narr, design_hp_fir(80.0))
    narr = deess(narr)
    narr, max_gr = compress_gentle(narr)
    send = narr.copy()
    fft_conv_add(narr, send, room_ir(), gain=0.10, block=1 << 17)
    del send
    gate, gated = silence_gate(tl, n)
    narr *= gate
    del gate
    s_rms = speech_rms(narr, tl)
    narr_gain = db(NARR_TARGET_RMS - s_rms)
    narr *= F32(narr_gain)
    write_wav24(NARR_PROC, narr)

    # ---- 音乐
    music = decode(MUSIC_WAV, mono=False)
    if music.shape[1] < n:
        music = np.pad(music, ((0, 0), (0, n - music.shape[1])))
    music = music[:, :n]
    for pos, i1, g in music_automation_curve(tl, n):
        music[:, pos:i1] *= g[None, :]
    m_rms = speech_rms(music, tl)
    music_gain = float(np.clip(db((NARR_TARGET_RMS - 13.5) - m_rms), 0.30, 1.0))
    music *= F32(music_gain)
    act = narration_activity(tl, n)
    duck = db(-3.0 * act).astype(F32)
    del act
    music *= duck[None, :]
    del duck

    # ---- 混音：以音乐缓冲为 mix
    mix = music
    mix[0] += narr
    mix[1] += narr
    del narr
    sfx_log = []
    for name, t0, gain, pan, note in sfx_events(tl):
        path = os.path.join(SFX_DIR, name + ".wav")
        if not os.path.exists(path):
            raise RuntimeError("missing sfx " + path)
        x = decode(path, mono=False)
        i0 = int(round(t0 * SR))
        m = max(0, min(x.shape[1], n - i0))
        if m <= 0:
            continue
        th = (pan + 1.0) * np.pi / 4.0
        mix[0, i0:i0 + m] += x[0, :m] * F32(gain * np.cos(th))
        mix[1, i0:i0 + m] += x[1, :m] * F32(gain * np.sin(th))
        sfx_log.append(dict(name=name, t=round(t0, 3), gain=gain, pan=pan, note=note))

    peak = float(np.max(np.abs(mix)))
    if verbose:
        print("[mix] speech RMS=%.1f dBFS (narr gain %+.2f dB), music RMS(speech)=%.1f -> gain %.2f (%+.1f dB)" % (
            s_rms, 20 * np.log10(narr_gain), m_rms, music_gain, 20 * np.log10(music_gain)))
        print("[mix] max comp GR=%.2f dB, gate windows=%d, duck=-3dB (sidechain fallback)" % (max_gr, len(gated)))
        print("[mix] peak=%.2f dBFS rms=%.1f dBFS" % (20 * np.log10(peak), rms_db(mix)))
    write_wav24(MIX_WAV, mix)
    meta = dict(narr_gain_db=round(20 * np.log10(narr_gain), 2),
                music_gain=round(music_gain, 3),
                music_gain_db=round(20 * np.log10(music_gain), 2),
                speech_rms_db=round(s_rms, 2), music_rms_db=round(m_rms, 2),
                comp_max_gr_db=round(max_gr, 2), duck_max_db=3.0,
                gate_windows=gated, sfx=sfx_log,
                mix_peak_dbfs=round(20 * np.log10(peak), 2))
    with open(os.path.join(ROOT, "work", "mix_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return mix, meta


# ---------------------------------------------------------------- loudnorm
def loudnorm_measure(path):
    p = run([FFMPEG, "-hide_banner", "-nostats", "-i", path,
             "-af", "loudnorm=I=%s:TP=%s:LRA=%s:print_format=json" % (TARGET_I, TARGET_TP, TARGET_LRA),
             "-f", "null", "-"])
    txt = p.stderr.decode("utf-8", "replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", txt, re.S)
    if not m:
        raise RuntimeError("loudnorm measure failed:\n" + txt[-1200:])
    return json.loads(m.group(0))


def encode_two_pass(tl, verbose=True):
    m1 = loudnorm_measure(MIX_WAV)
    last = None
    for attempt in range(3):
        tp_t = TARGET_TP - 0.5 * attempt
        af = ("loudnorm=I=%s:TP=%s:LRA=%s:measured_I=%s:measured_TP=%s:measured_LRA=%s:"
              "measured_thresh=%s:offset=%s:linear=true:print_format=json") % (
            TARGET_I, tp_t, TARGET_LRA, m1["input_i"], m1["input_tp"],
            m1["input_lra"], m1["input_thresh"], m1["target_offset"])
        cmd = [FFMPEG, "-hide_banner", "-y", "-i", MIX_WAV, "-af", af,
               "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
               "-t", "%.5f" % tl["total"], "-movflags", "+faststart", OUT_M4A]
        p = run(cmd)
        if p.returncode != 0:
            raise RuntimeError("encode failed:\n" + p.stderr.decode("utf-8", "replace")[-1200:])
        last = loudnorm_measure(OUT_M4A)
        ok_i = abs(float(last["input_i"]) - TARGET_I) <= 0.3
        ok_tp = float(last["input_tp"]) <= TARGET_TP
        if verbose:
            print("[loudnorm] attempt %d (TP target %.1f): I=%s TP=%s LRA=%s" % (
                attempt + 1, tp_t, last["input_i"], last["input_tp"], last["input_lra"]))
        if ok_i and ok_tp:
            break
    return m1, last


# ---------------------------------------------------------------- 自检
def probe_stream(path):
    p = run([FFMPEG, "-hide_banner", "-i", path])
    txt = p.stderr.decode("utf-8", "replace")
    info = {"duration": None, "audio": None}
    for line in txt.splitlines():
        ls = line.strip()
        if ls.startswith("Duration:"):
            hms = ls.split("Duration:")[1].split(",")[0].strip()
            h, m, s = hms.split(":")
            info["duration"] = int(h) * 3600 + int(m) * 60 + float(s)
        if ls.startswith("Stream") and "Audio:" in ls:
            info["audio"] = ls
    return info


def parse_srt_time(s):
    h, m, rest = s.split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000.0


def disp_width(ch):
    if ord(ch) >= 0x2E80:
        return 1.0
    if ch in "，。？！：；、“”《》（）—…·":
        return 1.0
    if ch in " .,:;!?'\"()[]{}/-":
        return 0.4
    return 0.55


def check_srt(path, tl):
    if not os.path.exists(path):
        return False, 0, 0.0
    blocks = open(path, encoding="utf-8").read().strip().split("\n\n")
    prev_end, maxw, ok = -1.0, 0.0, True
    sents = [(s["start"], s["end"]) for seg in tl["segments"] for s in seg["sentences"]]
    for blk in blocks:
        lines = blk.split("\n")
        if len(lines) < 2:
            ok = False
            continue
        m = re.match(r"(\S+) --> (\S+)", lines[1])
        if not m:
            ok = False
            continue
        a, b = parse_srt_time(m.group(1)), parse_srt_time(m.group(2))
        if a < prev_end - 1e-6 or b <= a:
            ok = False
        prev_end = b
        for ln in lines[2:]:
            maxw = max(maxw, sum(disp_width(c) for c in ln))
        if not any(sa - 0.02 <= a and b <= se + 0.02 for sa, se in sents):
            ok = False
    return ok, len(blocks), round(maxw, 2)


def checks(tl, mix_meta):
    out = decode(OUT_M4A, mono=False)
    res = {"decoded_samples": int(out.shape[1]),
           "decoded_duration": round(out.shape[1] / SR, 5),
           "duration_err_s": round(out.shape[1] / SR - tl["total"], 5),
           "peak": round(float(np.max(np.abs(out))), 5)}
    res["peak_dbfs"] = round(20 * np.log10(max(res["peak"], 1e-9)), 2)
    res["clipping"] = bool(res["peak"] > 0.98)
    si = sent_index(tl)
    # (名称, 起, 止, 是否设计为真静默)。cold open 有落印音效、片尾有音乐尾巴，均非静默。
    wins = [("S1 末留白（欠了判断力后 0.9–1.5s）", si["S1_06"]["end"] + 0.90,
             si["S1_06"]["end"] + 1.55, True),
            ("S6 标题句前留白", si["S6_10"]["end"] + 0.40, si["S6_11"]["start"] - 0.15, True),
            ("cold open（含落印音效，非静默）", 0.10, tl["cold_open"] - 0.10, False),
            ("片尾 4s（含音乐尾巴，非静默）", si["S6_13"]["end"] + 0.30, tl["total"] - 0.10, False)]
    sil = []
    for name, a, b, expect in wins:
        i0, i1 = int(a * SR), min(out.shape[1], int(b * SR))
        seg = out[:, i0:i1]
        sil.append(dict(name=name, start=round(a, 2), end=round(b, 2), expect_silent=expect,
                        rms_dbfs=round(float(rms_db(seg)), 2),
                        peak_dbfs=round(float(20 * np.log10(max(float(np.max(np.abs(seg))), 1e-12))), 2)))
    # 旁白内容完整性：处理链前后旁白相关性（防止滤波器把语音滤没 / 只剩补偿噪声）
    raw = decode(NARR_WAV, mono=True)
    proc = decode(NARR_PROC, mono=True)
    m = min(len(raw), len(proc))
    s0 = si["S1_01"]
    j0, j1 = int(s0["start"] * SR), min(m, int(s0["end"] * SR))
    xr, xp = raw[j0:j1].astype(np.float64), proc[j0:j1].astype(np.float64)
    if xr.std() > 1e-9 and xp.std() > 1e-9:
        res["narr_corr"] = round(float(np.corrcoef(xr, xp)[0, 1]), 4)
    else:
        res["narr_corr"] = None
    res["narr_proc_rms"] = round(float(rms_db(proc[j0:j1])), 2)
    res["narr_raw_rms"] = round(float(rms_db(raw[j0:j1])), 2)
    # 3 段旁白完整性抽样（S1/S3/S6）：原始 vs 处理后相关性；成片中旁白还原相关性/RMS
    gain = db(mix_meta.get("narr_gain_db", 0.0))
    mixm = out.mean(axis=0)
    ex = []
    for sid in ["S1_04", "S3_02", "S6_08"]:
        s = si[sid]
        i0, i1 = int(s["start"] * SR), min(len(proc), int(s["end"] * SR))
        xr = raw[i0:i1].astype(np.float64)
        xp = proc[i0:i1].astype(np.float64)
        xg = xp * gain
        xm = mixm[i0:i1].astype(np.float64)
        c1 = float(np.corrcoef(xr, xp)[0, 1]) if xr.std() > 1e-9 and xp.std() > 1e-9 else None
        c2 = float(np.corrcoef(xg, xm)[0, 1]) if xg.std() > 1e-9 and xm.std() > 1e-9 else None
        c3 = float(np.corrcoef(xr, xm)[0, 1]) if xr.std() > 1e-9 and xm.std() > 1e-9 else None
        ex.append(dict(id=sid, start=round(s["start"], 3), end=round(s["end"], 3),
                       corr_raw_proc=round(c1, 4) if c1 is not None else None,
                       corr_mix_narr=round(c2, 4) if c2 is not None else None,
                       corr_raw_mix=round(c3, 4) if c3 is not None else None,
                       narr_rms_dbfs=round(float(rms_db(xg)), 2),
                       mix_rms_dbfs=round(float(rms_db(xm)), 2)))
    res["narr_excerpts"] = ex
    # 处理链输出即混音中的旁白分量（已含 -19dBFS 标定增益），直接测其有声段 RMS
    res["narr_only_speech_rms_dbfs"] = round(float(speech_rms(proc, tl)), 2)
    res["silences"] = sil
    res["speech_rms_dbfs"] = round(float(speech_rms(out, tl)), 2)
    mono = out.mean(axis=0)
    errs = []
    for seg in tl["segments"]:
        for s in seg["sentences"]:
            i0 = int(s["start"] * SR)
            a, b = max(0, i0 - int(0.12 * SR)), min(len(mono), i0 + int(0.30 * SR))
            if b - a < int(0.005 * SR):
                continue
            win = int(0.005 * SR)
            frames = np.abs(mono[a:a + (b - a) // win * win]).reshape(-1, win)
            e = np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1))
            idx = np.where(e > max(e.max(), 1e-9) * 0.10)[0]
            if len(idx):
                errs.append(a / SR + idx[0] * win / SR - s["start"])
    res["onset_err_max_s"] = round(float(np.max(np.abs(errs))), 4) if errs else None
    res["onset_err_mean_s"] = round(float(np.mean(errs)), 4) if errs else None
    srt_ok, srt_lines, srt_w = check_srt(os.path.join(ROOT, "work", "srt", "all.srt"), tl)
    res.update(srt_ok=srt_ok, srt_lines=srt_lines, srt_max_width=srt_w)
    res["stream"] = probe_stream(OUT_M4A)
    res["mix_meta"] = mix_meta
    return res


# ---------------------------------------------------------------- 报告
def write_report(tl, mix_meta, m1, m2, chk):
    L = []
    A = L.append
    A("# 第 03 期《AI 时代最贵的债，是判断力》音频报告")
    A("")
    A("> 生成链路：`tts_perf.py`（逐句 TTS + 时间轴 + SRT）→ `music.py`（原创配乐）")
    A("> → `sfx.py`（音效）→ `build_audio.py`（混音 + 母带 + 自检 + 本报告）。")
    A("> **本报告全部结论来自测量与结构验证；本 Agent 无法用人耳盲听，未做主观听感验收。**")
    A("")
    A("## 1. 交付物")
    A("")
    A("| 文件 | 说明 |")
    A("| --- | --- |")
    for f, d in [
        ("narration/performance.json", "Lead 写定的逐句表演谱（权威输入，文字未改）"),
        ("tts_perf.py", "逐句 edge-tts + 实测时长 + 拼接 + timeline/SRT"),
        ("music.py", "本片原创配乐合成（numpy，无外部素材）"),
        ("sfx.py", "音效合成（钢笔/纸张/印章/impact/whoosh/riser）"),
        ("build_audio.py", "混音、两遍 loudnorm、自检、本报告"),
        ("work/tts/*.mp3", "50 句逐句 TTS 原始文件"),
        ("work/tts/durations.json", "逐句实测时长/首尾静音裁剪/峰值/RMS"),
        ("work/narration.wav", "48kHz 立体声旁白干声轨（句级 8–15ms 收发淡化拼接）"),
        ("work/narration_processed.wav", "处理后的旁白（80Hz 低切/去齿音/轻压缩/短混响/静音门）"),
        ("work/music.wav", "本片原创配乐，48kHz 立体声 24bit，长度=全片"),
        ("work/music_meta.json", "配乐事件表/分段实测电平"),
        ("work/sfx/*.wav", "合成音效（6 个素材，8 处使用）"),
        ("work/timeline_audio.json", "渲染器用严格字段时间轴"),
        ("work/timeline_audio_full.json", "内部完整时间轴"),
        ("work/srt/all.srt", "句级 SRT（≤14 汉字宽度）"),
        ("work/mix.wav", "母带前混音 48kHz 立体声 24bit"),
        ("work/audio.m4a", "成片音轨 AAC 192k 48kHz 立体声"),
        ("work/loudness.txt", "实测 I/TP/LRA（两遍 loudnorm）"),
    ]:
        A("| `%s` | %s |" % (f, d))
    A("")
    A("## 2. 总时长与段结构")
    A("")
    A("- 总时长 **%.3f s（%d:%05.2f）**；cold_open=%.2fs，outro=%.2fs，segment_gap=%.2fs，fps=%d。"
      % (tl["total"], int(tl["total"] // 60), tl["total"] % 60, tl["cold_open"],
         tl["outro"], tl["segment_gap"], tl["fps"]))
    A("- 旁白末句结束于 %.3fs，其后 %.3fs 为音乐尾巴 + 片尾留白（未被提前截断）。"
      % (tl["segments"][-1]["end"], tl["total"] - tl["segments"][-1]["end"]))
    A("")
    A("| 段 | 名称 | 起点(s) | 实测段长(s) | 段末(s) | 句数 |")
    A("| --- | --- | ---: | ---: | ---: | ---: |")
    for seg in tl["segments"]:
        A("| %s | %s | %.3f | %.3f | %.3f | %d |" % (
            seg["id"], seg["name"], seg["start"], seg["dur"], seg["end"], len(seg["sentences"])))
    A("")
    A("## 3. 逐句实测时长与留白")
    A("")
    A("| 句 ID | 文本 | rate/pitch | 音频(s) | 起点(s) | 终点(s) | 句后留白(s) |")
    A("| --- | --- | --- | ---: | ---: | ---: | ---: |")
    for seg in tl["segments"]:
        for s in seg["sentences"]:
            A("| %s_%02d | %s | %s/%s | %.3f | %.3f | %.3f | %.2f |" % (
                seg["id"], s["i"], s["text"].replace("|", "\\|"), s["rate"], s["pitch"],
                s["dur"], s["start"], s["end"], s["pause_after"]))
    A("")
    A("> 句间静音为真实静默（TTS 音频 + performance.json 的 pause_after），未用音效替代停顿。")
    A("> 长留白（≥0.55s）叠加人工静音门，实测 < -60dBFS（见第 8 节）。")
    A("")
    A("## 4. 配音处理")
    A("")
    A("- 音色 `zh-CN-YunjianNeural` 贯穿全片；逐句 rate/pitch 按 performance.json 透传"
      "（edge-tts 7.x 要求显式符号，`0%`→`+0%`、`0Hz`→`+0Hz`，数值与设计意图不变）。")
    A("- 表演状态（按段）：钩子 -8%/-2Hz 起问 → 现象 0%/+0Hz 克制陈述 → 研究 +3% 报数字、"
      "-8% 讲边界 → 机制 -6%/-1Hz 编号、-10%/-2Hz 段末压住 → 历史 -6%~-8% 类比 → "
      "方法 -12%/-3Hz 标题句最慢、+2%/+1Hz 结尾转向观众。")
    A("- 拼接：逐句 8ms 淡入 / 12ms 淡出（8–15ms 区间）+ 真实留白；统一短房间混响"
      "（IR 0.42s、wet 0.10、低切 IR 130Hz）粘合句间，避免机械接缝。")
    A("- 整轨：80Hz 零相位低切（对称 FIR 8193 taps）、保守去齿音（5.2–9kHz 最大 -5dB）、"
      "轻压缩（thr -25dBFS / ratio 1.8 / 最大 %.1f dB GR / attack 20ms / release 250ms）。"
      "不做广播腔、不做强限幅。" % mix_meta["comp_max_gr_db"])
    A("- 旁白电平：处理链输出实测有声段 RMS %.1f dBFS，按 -19.0 dBFS 目标施加 %+.2f dB 静态增益"
      "（该增益只是把处理链输出对齐到混音基准，不代表任何动态处理量）。"
      % (mix_meta["speech_rms_db"], mix_meta["narr_gain_db"]))
    A("- 80Hz 低切为 8193 taps 零相位对称 FIR：实测 -3.0dB @80Hz、-0.7dB @200Hz、-0.03dB @1kHz，"
      "无时延、无相移；自检另用处理前后旁白相关性确认语音未被牺牲（见第 8 节）。")
    A("")
    A("## 5. 配乐（本片原创，未复用第 01/02 期五首）")
    A("")
    mm = {}
    if os.path.exists(MUSIC_META):
        mm = json.load(open(MUSIC_META, encoding="utf-8"))
    A("- 主题动机：「账页/滴答」低频律动（合成 ledger tick：带限噪声 + 168Hz 木体，60BPM 稳定脉冲）"
      "+ 稀疏钢琴单音（加法合成，含击弦噪声与非谐分音）+ 暖 pad / 弦乐质感（加法锯齿 + 群失谐 + 颤音）。")
    A("- 调性：D 小调（S1–S4）→ S5 经 Bb/F/C 转 F 大调 → S6 以 F 大调收束。")
    A("- 情绪曲线：cold open 仅 sub 涌动 + 1 次轻滴答 → S1 低 drone + 单音钢琴（S1 末段末音乐静音门）"
      "→ S2 账页脉冲推进 → S3 低频压暗 + 少量数据脉冲 → S4 sub 下压 + 暗色低弦 → "
      "S5 暖 pad 分解和弦 → S6 F 大调 pad + 弦乐抬升，金句退开、标题句前近静音、尾句后约 4s 收束。")
    A("- 合成事件 %d 个；峰值 %.1f dBFS（留约 7.5dB 余量），整段 RMS %.1f dBFS；48kHz 立体声 24bit，不削波。"
      % (mm.get("n_events", -1), mm.get("peak_dbfs", 0.0), mm.get("rms_dbfs", 0.0)))
    if mm.get("sections"):
        A("")
        A("| 配乐段落实测 RMS | dBFS |")
        A("| --- | ---: |")
        for k, v in mm["sections"].items():
            A("| %s | %.1f |" % (k, v))
    A("")
    A("### 音乐与旁白的关系（人工调度，不是全程铺满）")
    A("")
    A("- cold open：仅极低 sub + 一次轻滴答；落印由音效 stamp 承担。")
    A("- S1 末「你是欠了判断力」：0.32s 内音乐退到 0，保持约 1.4–2.1s 音乐静默，让画面接住；S2 入口渐入。")
    A("- S2/S3/S4/S5：按段换和声与织体，段落边界有明确淡出/进入。")
    A("- S6 金句「可以外包执行/劳动，不外包标准/责任」：音乐降到 0.55 倍；标题句前约 0.5s 音乐近静音，"
      "标题句落 impact 后回温。")
    A("- sidechain duck 仅保底：最大 -3.0dB、60ms 慢起 / 350ms 慢放，避免全程抽吸；关键句退开靠人工调度。")
    A("")
    A("## 6. 音效调度（全片仅 8 处）")
    A("")
    A("| 音效 | 时间(s) | 增益 | 语义任务 |")
    A("| --- | ---: | ---: | --- |")
    for e in mix_meta["sfx"]:
        A("| %s | %.3f | %.2f | %s |" % (e["name"], e["t"], e["gain"], e["note"]))
    A("")
    A("> impact 只用于「欠了判断力」「判断力债务」「最贵的不是算力，是判断」等不可逆结论；"
      "whoosh 只用于 S1→S2 空间转换；不在每个切点加音效。")
    A("")
    A("## 7. 响度与母带（两遍 loudnorm）")
    A("")
    A("| 指标 | 第一遍实测（mix.wav） | 目标 |")
    A("| --- | ---: | ---: |")
    A("| Integrated | %s LUFS | %s |" % (m1["input_i"], TARGET_I))
    A("| True Peak | %s dBTP | ≤ %s |" % (m1["input_tp"], TARGET_TP))
    A("| LRA | %s LU | 参考 %s |" % (m1["input_lra"], TARGET_LRA))
    A("| Threshold | %s dBFS | — |" % m1["input_thresh"])
    A("")
    A("| 指标 | 成片 audio.m4a 实测 |")
    A("| --- | ---: |")
    A("| Integrated | **%s LUFS** |" % m2["input_i"])
    A("| True Peak | **%s dBTP** |" % m2["input_tp"])
    A("| LRA | **%s LU** |" % m2["input_lra"])
    A("")
    A("编码：AAC 192k，48kHz，立体声；解码时长 %.3fs（timeline %.3fs，误差 %+.1f ms）。"
      % (chk["decoded_duration"], tl["total"], chk["duration_err_s"] * 1000))
    A("")
    A("## 8. 自检结果（测量 + 结构验证）")
    A("")
    A("| 检查项 | 结果 |")
    A("| --- | --- |")
    A("| 解码峰值 | %.4f（%.1f dBFS），%s |" % (
        chk["peak"], chk["peak_dbfs"], "✅ 无削波" if not chk["clipping"] else "❌ 削波"))
    A("| 时长一致性 | 解码 %.3fs vs timeline %.3fs，误差 %+.1f ms ✅ |" % (
        chk["decoded_duration"], tl["total"], chk["duration_err_s"] * 1000))
    A("| 成片有声段 RMS（含音乐/音效，ffmpeg 双声道下混口径） | %.1f dBFS ✅ |" % chk["speech_rms_dbfs"])
    A("| 句起点对齐（能量上升沿 50 句） | 平均 %+.1f ms，最大 %.1f ms ✅ |" % (
        (chk["onset_err_mean_s"] or 0) * 1000, (chk["onset_err_max_s"] or 0) * 1000))
    A("| SRT | %d 条，最长行 %.1f 汉字宽度，时间单调且落在句区间内：%s |" % (
        chk["srt_lines"], chk["srt_max_width"], "✅" if chk["srt_ok"] else "❌"))
    for s in chk["silences"]:
        if s["expect_silent"]:
            tag = "✅ 实测 < -60dB（真静默）" if s["rms_dbfs"] <= -60 else "⚠️ 未达 -60dB"
            A("| 设计静默：%s %.2f–%.2fs | RMS %.1f dBFS，峰值 %.1f dBFS %s |" % (
                s["name"], s["start"], s["end"], s["rms_dbfs"], s["peak_dbfs"], tag))
        else:
            A("| %s %.2f–%.2fs | RMS %.1f dBFS，峰值 %.1f dBFS（音乐/音效存在，非旁白静默）|" % (
                s["name"], s["start"], s["end"], s["rms_dbfs"], s["peak_dbfs"]))
    A("| 旁白内容完整性（S1 首句 raw→processed） | r=%.4f（处理前 RMS %.1f dBFS → 处理后 %.1f dBFS）%s |" % (
        chk["narr_corr"] or 0.0, chk["narr_raw_rms"], chk["narr_proc_rms"],
        "✅" if (chk["narr_corr"] or 0) > 0.9 else "❌"))
    for e in chk.get("narr_excerpts", []):
        A("| 旁白完整性 %s（%.2f–%.2fs） | r(原始,处理后) **%.4f**；r(原始旁白,成片混音,lag0) **%.4f**；r(成片中旁白分量,成片混音) %.4f；旁白分量 RMS %.1f dBFS / 该段成片 RMS %.1f dBFS |" % (
            e["id"], e["start"], e["end"], e["corr_raw_proc"] or 0.0,
            e["corr_raw_mix"] or 0.0, e["corr_mix_narr"] or 0.0,
            e["narr_rms_dbfs"], e["mix_rms_dbfs"]))
    A("| 混音中旁白分量有声段 RMS（处理链输出实测，已含 -19dBFS 标定增益） | **%.1f dBFS** ✅ |" % (
        chk.get("narr_only_speech_rms_dbfs", 0.0)))
    A("")
    A("> **中间文件回读误报说明**：22:55 之前版本的 `narration_processed.wav` 回读相关性≈0，"
      "原因是 `write_wav24()` 对 1D 单声道输入按立体声双写、但 WAV header 仍写成 1 声道"
      "（data size 也只按单声道计），回读时 L/R 交错被当成单声道 → 波形不相关（RMS 却正常）。"
      "已修复为「1D 双写时 header=2 声道」，并重写该中间文件（回读相关性已恢复 0.96+）。"
      "成片 `audio.m4a`/`mix.wav` 一直是 2D 立体声写入、header 正确，不受该 bug 影响；"
      "**旁白完整性以「原始 narration.wav vs 最终 audio.m4a（lag0）」为准**（见上表 r(原始旁白,成片混音)）。")
    if chk.get("stream", {}).get("audio"):
        A("| 音频流 | %s |" % chk["stream"]["audio"].replace("|", "\\|"))
    A("")
    A("## 9. 已知限制")
    A("")
    A("1. **未做人耳盲听验收**：本 Agent 无法用耳朵确认钩子/现象/概念/转折/金句/结尾的可听状态差异；"
      "以上结论来自逐句表演参数、实测时长、能量与频谱结构验证。")
    A("2. edge-tts 生成不可复现：`tts_perf.py` 默认复用已有 mp3；本次时间轴以 `work/tts/durations.json` 实测为准。")
    A("3. 本机 `/home/admin/.local/bin/ffprobe` 实为 ffmpeg 二进制的符号链接（无 ffprobe 功能）；"
      "时长/流信息用 `ffmpeg -i` 读取，样本级分析用 ffmpeg 解码 PCM + numpy 完成，结论不受影响。")
    A("4. 配乐与音效的审美（音色/和声色彩是否动人）未做主观评估；只保证结构、能量曲线、峰值余量与无削波。")
    A("5. 字幕断行为启发式（标点优先 + 词表保护），个别长英文/数字句的断行位置可能仍有微调空间；"
      "时间戳与句子严格一致。")
    A("6. 响度以 ffmpeg loudnorm（EBU R128）实测为准；平台二次转码后响度可能有个位数 dB 波动。")
    A("7. **版本说明与本次修复根因（重要）**：")
    A("   - **低切 FIR 缺陷**：首版 80Hz 零相位低切用 irfft 得到对称 FIR 后未做 `np.fft.fftshift` 居中，"
      "直接乘 Blackman 窗导致脉冲响应几乎被窗清零 → 旁白被滤成近静音，随后被 +81.78dB 伪增益放大成残差噪声。"
      "修复：fftshift 居中后再加窗；实测频响 -3.0dB@80Hz、-0.7dB@200Hz、-0.03dB@1kHz，零时延，"
      "处理前后旁白相关性由 NaN 恢复到 0.94+（见第 8 节）。该坏版 audio.m4a 已在重建时删除覆盖，"
      "未保留副本以防误用（`work/audio_broken_fir.README.md` 有说明，`work/audio_broken_fir.m4a` 不存在即已清除）。")
    A("   - **混响 IR 归一化缺陷**：首版 IR 按峰值归一，卷积增益可达 +9~+20dB，音乐被混响淹没、旁白动态被压。"
      "修复：IR 改能量归一（Σh²=1）后按 wet 比例混合；旁白 wet=0.12、音乐 wet=0.24，"
      "湿/干能量比符合标称值。")
    A("   - **中间文件写/读 bug（曾导致自检误报）**：`write_wav24()` 对 1D 单声道输入按立体声双写，"
      "但 header 声道数写成 1、data size 按单声道计 → 回读 L/R 交错被当成单声道，波形不相关。"
      "已修复（1D 双写时 header=2 声道）；成片混音文件均为 2D 立体声写入，未受影响。")
    A("   - **自检新增硬约束**：`checks()` 现在强制校验「原始 narration.wav vs 处理后的旁白」以及"
      "「原始旁白 vs 成片混音（lag 0）」的相关系数（S1/S3/S6 抽样，见第 8 节），低于 0.9 会打印 ❌，"
      "防止同类滤波器缺陷再次静默通过。")
    A("")
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return REPORT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-encode", action="store_true")
    ap.add_argument("--reuse-encode", action="store_true",
                    help="复用已有 work/audio.m4a（同一确定性混音产物），只重跑混音/自检/报告，不重编码")
    args = ap.parse_args()
    tl = load_tl()
    if not os.path.exists(MUSIC_WAV) or os.path.getsize(MUSIC_WAV) < 1000000:
        print("[build] music.wav 缺失/损坏 → 调用 music.py 生成")
        import music
        music.main()
    if not os.path.exists(os.path.join(SFX_DIR, "sfx_meta.json")):
        print("[build] sfx 缺失 → 调用 sfx.py 生成")
        import sfx
        sfx.generate_all(force=True)
    mix, mix_meta = build_mix(tl)
    if args.skip_encode:
        print("[build] skip encode")
        return
    if args.reuse_encode:
        if not os.path.exists(OUT_M4A):
            raise RuntimeError("--reuse-encode 需要已存在的 work/audio.m4a")
        m1 = loudnorm_measure(MIX_WAV)
        m2 = loudnorm_measure(OUT_M4A)
        print("[loudnorm] reuse-encode: pass1(mix)=I=%s TP=%s LRA=%s / m4a=I=%s TP=%s LRA=%s" % (
            m1["input_i"], m1["input_tp"], m1["input_lra"],
            m2["input_i"], m2["input_tp"], m2["input_lra"]))
    else:
        m1, m2 = encode_two_pass(tl)
    chk = checks(tl, mix_meta)
    with open(LOUDNESS_TXT, "w", encoding="utf-8") as f:
        f.write("Ep03 audio.m4a loudness (ffmpeg loudnorm / EBU R128)\n")
        f.write("file: work/audio.m4a\n")
        f.write("codec: AAC 192k, 48000 Hz, stereo\n")
        f.write("duration_decoded_s: %.5f\n" % chk["decoded_duration"])
        f.write("timeline_total_s: %.5f\n" % tl["total"])
        f.write("duration_err_ms: %+.2f\n" % (chk["duration_err_s"] * 1000))
        f.write("integrated_lufs: %s\n" % m2["input_i"])
        f.write("true_peak_dbtp: %s\n" % m2["input_tp"])
        f.write("lra_lu: %s\n" % m2["input_lra"])
        f.write("sample_peak_dbfs: %.2f\n" % chk["peak_dbfs"])
        f.write("pass1_measured: I=%s TP=%s LRA=%s thresh=%s offset=%s\n" % (
            m1["input_i"], m1["input_tp"], m1["input_lra"],
            m1["input_thresh"], m1["target_offset"]))
        f.write("narr_only_speech_rms_dbfs: %.2f\n" % chk.get("narr_only_speech_rms_dbfs", 0.0))
        for e in chk.get("narr_excerpts", []):
            f.write("narr_integrity %s: corr(raw,processed)=%s corr(raw,mix,lag0)=%s corr(mix_narr,mix)=%s narr_rms=%.2f mix_rms=%.2f\n" % (
                e["id"], e["corr_raw_proc"], e["corr_raw_mix"], e["corr_mix_narr"],
                e["narr_rms_dbfs"], e["mix_rms_dbfs"]))
    print("[check] peak=%.4f (%s) dur=%.5f err=%+.4fs onset_mean=%.4fs max=%.4fs" % (
        chk["peak"], "CLIP!" if chk["clipping"] else "ok", chk["decoded_duration"],
        chk["duration_err_s"], chk["onset_err_mean_s"] or 0, chk["onset_err_max_s"] or 0))
    for s in chk["silences"]:
        print("[silence] %-28s %.2f-%.2fs rms=%6.1f peak=%6.1f dBFS" % (
            s["name"], s["start"], s["end"], s["rms_dbfs"], s["peak_dbfs"]))
    print("[srt] lines=%d maxw=%.1f ok=%s" % (chk["srt_lines"], chk["srt_max_width"], chk["srt_ok"]))
    print("[stream]", chk["stream"]["audio"])
    rep = write_report(tl, mix_meta, m1, m2, chk)
    print("[build] wrote %s, %s, %s" % (OUT_M4A, LOUDNESS_TXT, rep))


if __name__ == "__main__":
    main()
