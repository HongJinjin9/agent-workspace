#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 06 期时间轴生成器（三幕对话剧 / 三声部 N-M-L）。

输入：
  work/timeline_audio.json  —— 音频组句级实测时间轴（权威；含 COLD/ACT1..ACT4/CLOSE 六段、
                               cold_open/act_gap/outro/outro_voice）；缺失时用 narration/performance.json
                               或稿件 §4 估算 provisional 时间轴联调。
  shots.json                —— 分镜锚点。seg 可用真实段 id（COLD/ACT1/…），也可用**角色名**
                               `cold,a1,a2,a3,a4,outro`（按段顺序映射，解耦音频组的命名）；
                               `{"abs": t}` 绝对秒；`{"from_end": 1.0}` / `{"from_end": "outro"}` 片尾回退。

输出：
  work/timeline.json        —— {total, fps, segments, sentences, shots}

用法：
  python3 build_timeline.py                 # 优先实测
  python3 build_timeline.py --provisional   # 估算（联调用）
  python3 build_timeline.py --check         # 只校验不写
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FPS = 24
PROVISIONAL_SENT_RATE = 4.15  # 字/秒（三声部对话剧实测口径 ≈249 字/分）
SCRIPT_EPISODE = "第06期-他们说这是最糟糕的方案.md"
ROLE_ORDER = ["cold", "a1", "a2", "a3", "a4", "outro"]
SECTION_ROLES = [("冷开场", "cold"), ("第一幕", "a1"), ("第二幕", "a2"),
                 ("第三幕", "a3"), ("第四幕", "a4"), ("收束", "outro")]
SKIP_LINE_PREFIX = (">", "【", "——", "（", "(", "|")


def log(*a):
    print("[timeline] " + " ".join(str(x) for x in a), flush=True)


# ------------------------------------------------------------------ 稿件解析
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
    """解析 §4 逐字稿 → [{role, name, sentences:[text]}]（括号提示/引述卡/尾声明不读）。"""
    raw = open(path, encoding="utf-8").read()
    m = re.search(r"^## 4\. 逐字稿[^\n]*\n(.*?)^## ", raw, re.S | re.M)
    if not m:
        raise SystemExit("稿件缺少 §4 逐字稿")
    body = m.group(1)
    body = re.split(r"^### 4\.1", body, flags=re.M)[0]
    segs = []
    cur = None
    skip_tail = False
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("### "):
            name = s[4:].strip()
            role = None
            for kw, r in SECTION_ROLES:
                if kw in name:
                    role = r
                    break
            if role is None:
                cur = None
                continue
            cur = {"role": role, "name": name, "sentences": []}
            segs.append(cur)
            skip_tail = False
            continue
        if not s:
            continue
        if s.startswith("（尾声明"):
            skip_tail = True
            continue
        if skip_tail or cur is None:
            continue
        if s.startswith(SKIP_LINE_PREFIX):
            continue
        cur["sentences"].append(s)
    roles = [s["role"] for s in segs]
    if roles != ROLE_ORDER:
        raise SystemExit("稿件段序不符合预期: %s" % roles)
    for seg in segs:
        if not seg["sentences"]:
            raise SystemExit("稿件解析失败：%s 无句子" % seg["name"])
    return segs


# ------------------------------------------------------------------ performance.json
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
    txt = json.dumps(perf, ensure_ascii=False)
    # 只接受「看着像第 06 期」的 performance.json（ep05 的旧文件会被拒绝）
    ok_ids = segs == ["COLD", "ACT1", "ACT2", "ACT3", "ACT4", "CLOSE"]
    if not ok_ids or nsent < 50 or "增程" not in txt:
        return None
    return perf


def provisional_timeline():
    perf = load_perf()
    cold = float(perf.get("cold_open", 2.6)) if perf else 2.6
    gap = float(perf.get("act_gap", perf.get("segment_gap", 1.5))) if perf else 1.5
    outro = float(perf.get("outro", 10.5)) if perf else 10.5
    if perf:
        log("provisional 源 = narration/performance.json（三声部表演谱，施工中版本）")
        seg_src = []
        for s in perf["segments"]:
            seg_src.append({
                "role": ROLE_ORDER[len(seg_src)],
                "name": s.get("name", ""),
                "sentences": [{"text": x["text"], "rate": x.get("rate", "0%"),
                               "pause_after": float(x.get("pause_after", 0.45)),
                               "speaker": x.get("speaker", "N")}
                              for x in s["sentences"]],
            })
    else:
        script = find_script()
        if not script:
            raise SystemExit("缺少 narration/performance.json 且找不到稿件 §4，无法生成 provisional 时间轴")
        log("provisional 源 = 稿件 §4：" + script)
        seg_src = [{"role": s["role"], "name": s["name"], "sentences": [
            {"text": t, "rate": "0%", "pause_after": 0.75, "speaker": "N"}
            for t in s["sentences"]]} for s in parse_script_sentences(script)]
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
            sents.append({"i": len(sents) + 1, "text": s["text"], "start": round(st, 3),
                          "end": round(st + dur, 3), "speaker": s.get("speaker", "N")})
            st = round(st + dur + float(s.get("pause_after", 0.45)), 3)
        segs.append({"id": seg["role"].upper() if seg["role"] != "cold" else "COLD",
                     "name": seg["name"], "start": round(t, 3),
                     "dur": round(st - t, 3), "sentences": sents})
        t = round(st + gap, 3)
    total = round(t - gap + outro, 3)
    return {"provisional": True, "cold_open": cold, "outro": outro, "segment_gap": gap,
            "act_gap": gap, "fps": FPS, "total": total, "segments": segs}


# ------------------------------------------------------------------ timeline
def load_audio_timeline():
    path = os.path.join(ROOT, "work", "timeline_audio.json")
    if not os.path.exists(path):
        return None
    data = json.load(open(path, encoding="utf-8"))
    need = ("total", "segments")
    if any(k not in data for k in need):
        raise SystemExit(f"work/timeline_audio.json 缺少字段 {need}")
    return data


def role_segments(audio):
    """返回 {role: segment}（按顺序），以及原始 id 映射。"""
    segs = audio["segments"]
    if len(segs) != len(ROLE_ORDER):
        raise SystemExit("段数不符：期望 %d 段（COLD/ACT1..ACT4/CLOSE），实际 %d"
                         % (len(ROLE_ORDER), len(segs)))
    by_id = {s["id"]: s for s in segs}
    by_role = dict(zip(ROLE_ORDER, segs))
    return by_id, by_role


def anchor_time(audio, by_id, by_role, anchor):
    if "abs" in anchor:
        return float(anchor["abs"])
    if "from_end" in anchor:
        k = anchor["from_end"]
        val = float(audio.get("outro", 10.5)) if k == "outro" else float(k)
        return round(float(audio["total"]) - val, 3)
    seg = None
    if anchor["seg"] in by_id:
        seg = by_id[anchor["seg"]]
    elif str(anchor["seg"]).lower() in by_role:
        seg = by_role[str(anchor["seg"]).lower()]
    else:
        raise SystemExit("未知 seg 锚点: %r（可用 id: %s / 角色: %s）"
                         % (anchor["seg"], list(by_id), ROLE_ORDER))
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
    by_id, by_role = role_segments(audio)
    total = round(float(audio["total"]), 3)
    out = []
    for sh in shots_source():
        start = round(anchor_time(audio, by_id, by_role, sh["at"]), 3)
        out.append(dict(sh, start=start))
    out.sort(key=lambda s: s["start"])
    prev = -1e9
    for sh in out:
        if sh["start"] < prev + 0.4:
            raise SystemExit(f"分镜过密或锚点重叠: {sh['id']} @ {sh['start']} (前一镜 {prev})")
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
            item = {"seg": seg["id"], "i": s["i"], "start": s["start"], "end": s["end"],
                    "text": s["text"]}
            if "speaker" in s:
                item["speaker"] = s["speaker"]
            sentences.append(item)
    sentences.sort(key=lambda s: s["start"])
    tl = {"total": total, "fps": FPS, "provisional": provisional,
          "cold_open": audio.get("cold_open"), "outro": audio.get("outro"),
          "segment_gap": audio.get("segment_gap"), "act_gap": audio.get("act_gap"),
          "outro_voice": audio.get("outro_voice"), "voices": audio.get("voices"),
          "segments": audio["segments"], "sentences": sentences, "shots": out}
    return tl


def validate(tl):
    total = tl["total"]
    shots = tl["shots"]
    assert shots[0]["start"] >= 0, "首镜早于 0"
    assert abs(shots[-1]["start"] + shots[-1]["dur"] - total) < 0.01, "末镜未对齐片尾"
    by_id = {s["id"]: s for s in tl["segments"]}
    for s in shots:
        assert s["start"] + s["dur"] <= total + 0.01, "镜头越界 %s" % s["id"]
    ids = [s["id"] for s in shots]
    assert len(ids) == len(set(ids)), "shot id 重复"
    for seg in tl["segments"]:
        ii = [x["i"] for x in seg["sentences"]]
        if ii != list(range(1, len(ii) + 1)):
            raise SystemExit("%s 句号不连续: %s" % (seg["id"], ii))
    # 每镜必须落在时间轴内且起点可解释
    for s in shots:
        assert "at" in s
    return True


def summary(tl):
    print(f"timeline: {'PROVISIONAL' if tl['provisional'] else 'MEASURED'} "
          f"total={tl['total']}s frames={round(tl['total'] * FPS)} shots={len(tl['shots'])} "
          f"sentences={len(tl['sentences'])}")
    for seg in tl["segments"]:
        print("  %-5s %-8s start=%8.2f dur=%7.2f end=%8.2f sents=%d" % (
            seg["id"], seg.get("name", ""), seg["start"], seg["dur"],
            seg["start"] + seg["dur"], len(seg["sentences"])))
    for s in tl["shots"]:
        flag = ""
        if s.get("asset", "").startswith("comfy_"):
            p = os.path.join(ROOT, "assets", "comfy",
                             s["asset"].replace("comfy_", "") + ".mp4")
            flag = "  [comfy]" if os.path.isfile(p) else "  [comfy-MISSING→fallback]"
            if s["dur"] > 6.4:
                flag += " (dur>6.4s: 慢放/凝结)"
        ov = s.get("overlays") or s.get("overlay") or ""
        if isinstance(ov, list):
            ov = "+".join(ov)
        print("  %-6s %-5s %7.2f +%6.2f  %-16s %-26s%s" % (
            s["id"], s["kind"], s["start"], s["dur"],
            s.get("scene") or s.get("asset", ""), ov, flag))


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
