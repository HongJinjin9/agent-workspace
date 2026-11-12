#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 05 期时间轴生成器。

输入：
  work/timeline_audio.json   —— 音频组的句级实测时间轴（权威；若缺失或 --provisional，
                                则用 narration/performance.json 或稿件 §4 估算临时时间轴联调）
  shots.json                 —— 分镜锚点：每镜以「段落+句号+偏移」锚定，避免逐字稿改速后错位；
                                `{"abs": t}` 绝对秒；`{"from_end": 6.5}` / `{"from_end": "outro"}`
                                从片尾回退（用于对齐 audio 的 outro 尾巴）。

输出：
  work/timeline.json         —— 渲染器唯一时间基准：{total, fps, segments, sentences, shots}

用法：
  python3 build_timeline.py                 # 优先用实测时间轴
  python3 build_timeline.py --provisional   # 用估算时间轴（仅用于渲染器联调）
  python3 build_timeline.py --check         # 只做一致性校验（不写文件）
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FPS = 24
PROVISIONAL_SENT_RATE = 3.9  # 字/秒（≈234 字/分，edge-tts 默认语速实测口径）
SCRIPT_EPISODE = "第05期-为什么公司越大越容易自己绊自己.md"


def log(*a):
    print("[timeline] " + " ".join(str(x) for x in a), flush=True)


# ------------------------------------------------------------------ 稿件解析（provisional）
def find_script():
    cands = [
        os.path.join(ROOT, "script.md"),
        os.path.join(ROOT, "..", "..", "自媒体稿", SCRIPT_EPISODE),
        os.path.join(ROOT, "..", "自媒体稿", SCRIPT_EPISODE),
    ]
    cands += glob.glob("/home/admin/.dsh/state/superagent/work/*/自媒体稿/" + SCRIPT_EPISODE)
    cands += glob.glob("/app/vedio/*/自媒体稿/" + SCRIPT_EPISODE)
    for c in cands:
        c = os.path.abspath(c)
        if os.path.isfile(c) and os.path.getsize(c) > 5000:
            return c
    return None


def parse_script_sentences(path):
    """解析 §4 逐字稿 → {seg_id: [text, ...]}（括号内的口播提示不读）。"""
    raw = open(path, encoding="utf-8").read()
    m = re.search(r"^## 4\. 逐字稿\s*$(.*?)^## ", raw, re.S | re.M)
    if not m:
        raise SystemExit("稿件缺少 §4 逐字稿")
    body = m.group(1)
    segments = []
    cur = None
    for line in body.splitlines():
        hm = re.match(r"^### (S\d+)｜", line.strip())
        if hm:
            cur = {"id": hm.group(1), "sentences": []}
            segments.append(cur)
            continue
        s = line.strip()
        if not s:
            continue
        if s.startswith(">") or s.startswith("（") or s.startswith("("):
            continue
        if cur is not None:
            cur["sentences"].append(s)
    for seg in segments:
        if not seg["sentences"]:
            raise SystemExit("稿件解析失败：%s 无句子" % seg["id"])
    return segments


def load_perf():
    p = os.path.join(ROOT, "narration", "performance.json")
    if not os.path.isfile(p):
        return None
    try:
        perf = json.load(open(p, encoding="utf-8"))
    except Exception:
        return None
    segs = [s.get("id") for s in perf.get("segments", [])]
    nsent = sum(len(s.get("sentences", [])) for s in perf.get("segments", []))
    # 只接受「看着像第 05 期」的 performance.json（ep04 的旧文件会被拒绝）
    txt = json.dumps(perf, ensure_ascii=False)
    if segs != ["S1", "S2", "S3", "S4", "S5", "S6"] or nsent < 60 or "公司" not in txt:
        return None
    return perf


def provisional_timeline():
    """按 performance.json 的 rate/字数估算；缺失时直接解析稿件 §4 估算。"""
    perf = load_perf()
    cold = float(perf.get("cold_open", 3.5)) if perf else 3.5
    gap = float(perf.get("segment_gap", 1.2)) if perf else 1.2
    outro = float(perf.get("outro", 6.0)) if perf else 6.0
    if perf:
        seg_src = [{"id": s["id"], "name": s.get("name", ""), "sentences": [
            {"i": i + 1, "text": x["text"], "rate": x.get("rate", "0%"),
             "pause_after": float(x.get("pause_after", 0.45))}
            for i, x in enumerate(s["sentences"])]} for s in perf["segments"]]
        log("provisional 源 = narration/performance.json（audio-narration 施工中版本）")
    else:
        script = find_script()
        if not script:
            raise SystemExit("缺少 narration/performance.json 且找不到稿件 §4，无法生成 provisional 时间轴")
        log("provisional 源 = 稿件 §4：" + script)
        seg_src = [{"id": s["id"], "name": "", "sentences": [
            {"i": i + 1, "text": t, "rate": "0%", "pause_after": 0.45}
            for i, t in enumerate(s["sentences"])]} for s in parse_script_sentences(script)]
    t = cold
    segs = []
    for seg in seg_src:
        sents = []
        st = t
        for s in seg["sentences"]:
            r = str(s.get("rate", "0%")).replace("%", "")
            rate = int(r) if r.lstrip("-").isdigit() else 0
            factor = 1.0 + rate / 100.0
            chars = len(re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", s["text"]))
            dur = round(chars / PROVISIONAL_SENT_RATE / max(0.6, factor), 3)
            sents.append({"i": s["i"], "text": s["text"], "start": round(st, 3),
                          "end": round(st + dur, 3)})
            st = round(st + dur + float(s.get("pause_after", 0.45)), 3)
        segs.append({"id": seg["id"], "name": seg["name"], "start": round(t, 3),
                     "dur": round(st - t, 3), "sentences": sents})
        t = round(st + gap, 3)
    total = round(t - gap + outro, 3)
    return {"provisional": True, "cold_open": cold, "outro": outro, "segment_gap": gap,
            "fps": FPS, "total": total, "segments": segs}


def load_audio_timeline():
    path = os.path.join(ROOT, "work", "timeline_audio.json")
    if not os.path.exists(path):
        return None
    data = json.load(open(path, encoding="utf-8"))
    need = ("total", "segments")
    if any(k not in data for k in need):
        raise SystemExit(f"work/timeline_audio.json 缺少字段 {need}")
    return data


def anchor_time(audio, seg_map, anchor):
    if "abs" in anchor:
        return float(anchor["abs"])
    if "from_end" in anchor:
        k = anchor["from_end"]
        val = float(audio.get("outro", 6.0)) if k == "outro" else float(k)
        return round(float(audio["total"]) - val, 3)
    seg = seg_map[anchor["seg"]]
    sents = {s["i"]: s for s in seg["sentences"]}
    s = sents[int(anchor["sent"])]
    base = float(s["end"]) if anchor.get("from_end") else float(s["start"])
    return base + float(anchor.get("off", 0.0))


def shots_source():
    return json.load(open(os.path.join(ROOT, "shots.json"), encoding="utf-8"))


def build(provisional=False):
    audio = load_audio_timeline() if not provisional else None
    if audio is None:
        audio = provisional_timeline()
        provisional = True
    seg_map = {s["id"]: s for s in audio["segments"]}
    total = round(float(audio["total"]), 3)
    shots = shots_source()
    out = []
    for sh in shots:
        start = round(anchor_time(audio, seg_map, sh["at"]), 3)
        out.append(dict(sh, start=start))
    out.sort(key=lambda s: s["start"])
    prev = -1e9
    for sh in out:
        if sh["start"] < prev + 0.5:
            raise SystemExit(f"分镜过密或时间锚点重叠: {sh['id']} @ {sh['start']} (前一镜 {prev})")
        prev = sh["start"]
    if out[0]["start"] < 0:
        raise SystemExit("首镜早于 0")
    for i, sh in enumerate(out):
        end = out[i + 1]["start"] if i + 1 < len(out) else total
        sh["dur"] = round(end - sh["start"], 3)
        sh["end"] = round(end, 3)
        if sh["dur"] <= 0.3:
            raise SystemExit(f"分镜 {sh['id']} 时长为 {sh['dur']}")
    sentences = []
    for seg in audio["segments"]:
        for s in seg["sentences"]:
            sentences.append({"seg": seg["id"], "i": s["i"], "start": s["start"],
                              "end": s["end"], "text": s["text"]})
    sentences.sort(key=lambda s: s["start"])
    tl = {"total": total, "fps": FPS, "provisional": provisional,
          "cold_open": audio.get("cold_open"), "outro": audio.get("outro"),
          "segment_gap": audio.get("segment_gap"),
          "outro_voice": audio.get("outro_voice"),
          "segments": audio["segments"], "sentences": sentences, "shots": out}
    return tl


def validate(tl):
    """一致性校验 + 施工风险提示。"""
    total = tl["total"]
    shots = tl["shots"]
    assert shots[0]["start"] >= 0, "首镜早于 0"
    assert abs(shots[-1]["start"] + shots[-1]["dur"] - total) < 0.01, "末镜未对齐片尾"
    seg_map = {s["id"]: s for s in tl["segments"]}
    for s in shots:
        assert s["start"] + s["dur"] <= total + 0.01, "镜头越界 %s" % s["id"]
        if s.get("seg") in seg_map:
            seg = seg_map[s["seg"]]
            if s is not shots[0] and s["start"] < seg["start"] - 0.02:
                print("[timeline] 警告: %s 早于 %s 起点" % (s["id"], s["seg"]))
    ids = [s["id"] for s in shots]
    assert len(ids) == len(set(ids)), "shot id 重复"
    # 句号连续性：每段句子 i 从 1 连续
    for seg in tl["segments"]:
        ii = [s["i"] for s in seg["sentences"]]
        if ii != list(range(1, len(ii) + 1)):
            raise SystemExit("%s 句号不连续: %s" % (seg["id"], ii))
    return True


def summary(tl):
    print(f"timeline: {'PROVISIONAL' if tl['provisional'] else 'MEASURED'} "
          f"total={tl['total']}s frames={round(tl['total'] * FPS)} shots={len(tl['shots'])} "
          f"sentences={len(tl['sentences'])}")
    for seg in tl["segments"]:
        print("  %-3s start=%8.2f dur=%7.2f end=%8.2f sents=%d" % (
            seg["id"], seg["start"], seg["dur"], seg["start"] + seg["dur"],
            len(seg["sentences"])))
    last_seg = None
    for s in tl["shots"]:
        flag = ""
        if s.get("asset", "").startswith("comfy_"):
            p = os.path.join(ROOT, "assets", "comfy", s["asset"].replace("comfy_", "") + ".mp4")
            flag = "  [comfy]" if os.path.isfile(p) else "  [comfy-MISSING→fallback]"
            if s["dur"] > 6.4:
                flag += " (dur>6.4s: 需慢放/循环)"
        print("  %-6s %-5s %7.2f +%6.2f  %-18s %-22s%s" % (
            s["id"], s["kind"], s["start"], s["dur"],
            s.get("scene") or s.get("asset", ""), s.get("overlay", ""), flag))


def main():
    provisional = "--provisional" in sys.argv
    check_only = "--check" in sys.argv
    if not provisional and not os.path.exists(os.path.join(ROOT, "work", "timeline_audio.json")):
        log("work/timeline_audio.json 未就绪 → 自动使用 provisional 时间轴（联调用）")
    tl = build(provisional=provisional)
    validate(tl)
    summary(tl)
    if check_only:
        return
    os.makedirs(os.path.join(ROOT, "work"), exist_ok=True)
    with open(os.path.join(ROOT, "work", "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(tl, f, ensure_ascii=False, indent=1)
    log("→ work/timeline.json")


if __name__ == "__main__":
    main()
