#!/usr/bin/env python3
"""第 03 期时间轴生成器。

输入：
  work/timeline_audio.json   —— 音频组的句级实测时间轴（若缺失或 --provisional，则用
                                narration/performance.json 估算一个临时时间轴用于渲染联调）
  shots.json                 —— 分镜锚点：每镜以「段落+句号+偏移」锚定，避免逐字稿改速后错位

输出：
  work/timeline.json         —— 渲染器唯一时间基准：{total, fps, segments, sentences, shots}

用法：
  python3 build_timeline.py                 # 优先用实测时间轴
  python3 build_timeline.py --provisional   # 用估算时间轴（仅用于渲染器联调）
  python3 build_timeline.py --check         # 只做一致性校验
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FPS = 24
PROVISIONAL_SENT_RATE = 3.9  # 字/秒（≈233 字/分，edge-tts 默认语速实测口径）


def load_perf():
    return json.load(open(os.path.join(ROOT, "narration", "performance.json"), encoding="utf-8"))


def provisional_timeline():
    """按 performance.json 的 rate 与字数估算，供渲染器先行联调。"""
    perf = load_perf()
    cold = float(perf.get("cold_open", 4.0))
    gap = float(perf.get("segment_gap", 0.8))
    outro = float(perf.get("outro", 4.0))
    t = cold
    segs = []
    for seg in perf["segments"]:
        sents = []
        st = t
        for s in seg["sentences"]:
            rate = int(str(s.get("rate", "0%")).replace("%", "")) if str(s.get("rate", "0%")).replace("%", "").lstrip("-").isdigit() else 0
            factor = 1.0 + rate / 100.0
            chars = len(re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", s["text"]))
            dur = round(chars / PROVISIONAL_SENT_RATE / max(0.6, factor), 3)
            sents.append({"i": s["i"], "text": s["text"], "start": round(st, 3), "end": round(st + dur, 3)})
            st = round(st + dur + float(s.get("pause_after", 0.45)), 3)
        seg_dur = round(st - t, 3)
        segs.append({"id": seg["id"], "name": seg.get("name", ""), "start": round(t, 3), "dur": seg_dur,
                     "sentences": sents})
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
    seg = seg_map[anchor["seg"]]
    sents = {s["i"]: s for s in seg["sentences"]}
    s = sents[int(anchor["sent"])]
    base = float(s["end"]) if anchor.get("from_end") else float(s["start"])
    return base + float(anchor.get("off", 0.0))


def main():
    provisional = "--provisional" in sys.argv or not os.path.exists(os.path.join(ROOT, "work", "timeline_audio.json"))
    audio = provisional_timeline() if provisional else load_audio_timeline()
    seg_map = {s["id"]: s for s in audio["segments"]}
    total = round(float(audio["total"]), 3)
    shots = json.load(open(os.path.join(ROOT, "shots.json"), encoding="utf-8"))
    out = []
    for sh in shots:
        start = round(anchor_time(audio, seg_map, sh["at"]), 3)
        out.append(dict(sh, start=start))
    out.sort(key=lambda s: s["start"])
    # 去重/夹紧：任何后一镜不得早于前一镜 +0.5s
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
        if sh["dur"] <= 0.3:
            raise SystemExit(f"分镜 {sh['id']} 时长为 {sh['dur']}")
    sentences = []
    for seg in audio["segments"]:
        for s in seg["sentences"]:
            sentences.append({"seg": seg["id"], "i": s["i"], "start": s["start"], "end": s["end"], "text": s["text"]})
    sentences.sort(key=lambda s: s["start"])
    tl = {"total": total, "fps": FPS, "provisional": provisional,
          "cold_open": audio.get("cold_open"), "outro": audio.get("outro"),
          "segments": audio["segments"], "sentences": sentences, "shots": out}
    os.makedirs(os.path.join(ROOT, "work"), exist_ok=True)
    with open(os.path.join(ROOT, "work", "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(tl, f, ensure_ascii=False, indent=1)
    print(f"timeline: {'PROVISIONAL' if provisional else 'measured'} total={total}s frames={round(total*FPS)} shots={len(out)}")
    for seg in audio["segments"]:
        print(f"  {seg['id']} start={seg['start']:8.2f} dur={seg['dur']:7.2f} end={seg['start']+seg['dur']:8.2f}")
    print("  shots:", " ".join(f"{s['id']}@{s['start']:.1f}({s['dur']:.1f})" for s in out))
    # 一致性校验
    assert out[0]["start"] >= 0
    assert abs(out[-1]["start"] + out[-1]["dur"] - total) < 0.01
    for s in out:
        assert s["start"] + s["dur"] <= total + 0.01


if __name__ == "__main__":
    main()
