#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 07 期收尾：生成 work/final-report.md + assets-manifest.json。

数据来源（存在即用，缺失如实标注 null）：
  work/final-check.json              verify_ep07.py 的实测结果
  delivery/delivery-manifest.json    prepare_delivery.py 的交付清单
  assets/h3/manifest.json            comfyui-operator 的 H3 素材 provenance
  audio/work/audio-report.md         audio-narration 的混音报告
  audio/work/timeline_audio.json     句级时间轴
  src/data/shots.json / timeline.json  MH 工程分镜与时间轴
  work/mh-render.json                本次最终导出的命令/耗时/输出
  work/notes.md                      人工备注（可选，整段追加进报告）

用法：python3 scripts/write_report.py [--notes work/notes.md]
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")
FILM = os.path.join(ROOT, "out", "ep07-mh.mp4")


def jload(*cands, default=None):
    for c in cands:
        if c and os.path.isfile(c):
            try:
                return json.load(open(c, encoding="utf-8"))
            except Exception:
                pass
    return default


def summary(text, pat):
    for line in (text or "").splitlines():
        if re.search(pat, line):
            return line.strip()
    return None


def sha256(path):
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", default=os.path.join(WORK, "notes.md"))
    args = ap.parse_args()

    check = jload(os.path.join(WORK, "final-check.json"), default={}) or {}
    deliv = jload(os.path.join(ROOT, "delivery", "delivery-manifest.json"), default={}) or {}
    h3 = jload(os.path.join(ROOT, "assets", "h3", "manifest.json"),
               os.path.join(ROOT, "assets", "h3", "h3-manifest.json"), default={}) or {}
    shots = jload(os.path.join(ROOT, "src", "data", "shots.json"),
                  os.path.join(ROOT, "src", "data", "timeline.json"), default={}) or {}
    tla = jload(os.path.join(ROOT, "audio", "work", "timeline_audio.json"),
                os.path.join(ROOT, "audio", "audio-timeline.json"), default={}) or {}
    render = jload(os.path.join(WORK, "mh-render.json"), default={}) or {}
    audio_report = ""
    for c in (os.path.join(ROOT, "audio", "work", "audio-report.md"),
              os.path.join(ROOT, "audio", "audio-report.md")):
        if os.path.isfile(c):
            audio_report = open(c, encoding="utf-8", errors="ignore").read()
            break
    notes = ""
    if args.notes and os.path.isfile(args.notes):
        notes = open(args.notes, encoding="utf-8").read()

    lw = check.get("loudness") or {}
    dur = check.get("duration")
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    ok = not check.get("problems")
    n_shots = None
    if isinstance(shots, dict):
        for k in ("shots", "beats"):
            if isinstance(shots.get(k), list):
                n_shots = len(shots[k])
                break
    elif isinstance(shots, list):
        n_shots = len(shots)
    n_hnar = None
    if isinstance(tla, dict):
        for k in ("segments", "sentences", "cues"):
            if isinstance(tla.get(k), list):
                n_hnar = len(tla[k])
                break
    h3_count = None
    h3_clips = []
    if isinstance(h3, dict):
        for k in ("clips", "shots", "files", "items"):
            v = h3.get(k)
            if isinstance(v, dict):
                h3_clips = [dict(path=kk, **(vv if isinstance(vv, dict) else {}))
                            for kk, vv in v.items()]
                break
            if isinstance(v, list):
                h3_clips = v
                break
        h3_count = len(h3_clips) or h3.get("count") or h3.get("generated")

    lines = []
    A = lines.append
    A("# 第 07 期《三年之后，你的车还值多少钱》成片自检报告\n")
    A("> 由 `scripts/write_report.py` 依据实测数据生成（%s UTC）；MotionHarness Pro 工程导出。\n"
      % now.isoformat())
    A("## 1. 技术规格\n")
    A("| 项目 | 实测 | 目标 | 结论 |")
    A("| --- | --- | --- | --- |")
    A("| 成片 | `%s` | — | — |" % check.get("film", "out/ep07-mh.mp4"))
    A("| 时长 | %s s | %s s（设计 3:17，按 TTS 实测） | %s |" % (
        "%.3f" % dur if dur else "—",
        "%.3f" % (check.get("expected_duration") or 197.0),
        "✅" if dur and abs(dur - (check.get("expected_duration") or 0)) <= 0.5 else "❌"))
    A("| 帧数 | %s | %s | %s |" % (
        check.get("frames", "—"), check.get("expected_frames", "—"),
        "✅" if abs((check.get("frames") or 0) - (check.get("expected_frames") or 0)) <= 2 else "❌"))
    A("| 分辨率 | %sx%s | 1920x1080 | %s |" % (
        check.get("width"), check.get("height"),
        "✅" if (check.get("width"), check.get("height")) == (1920, 1080) else "❌"))
    A("| 帧率 | %s | 24 | %s |" % (check.get("fps"), "✅" if check.get("fps") == 24.0 else "❌"))
    A("| 体积 | %s MB | — | — |" % check.get("size_mb", "—"))
    A("| 视频/音频 | %s / %s | H.264 + AAC | %s |" % (
        check.get("video_codec", "—"),
        ", ".join("%s %sHz %sch" % (a.get("codec"), a.get("sr"), a.get("ch"))
                  for a in (check.get("audio") or [])) or "—",
        "✅" if check.get("audio") else "❌"))
    A("| 全片解码 | %s | 无错误 | %s |" % (
        "无错误" if not check.get("decode_errors") else check.get("decode_errors")[:80],
        "✅" if not check.get("decode_errors") else "❌"))
    A("")
    A("## 2. 响度与音频\n")
    A("| 指标 | 实测 | 目标 | 结论 |")
    A("| --- | --- | --- | --- |")
    A("| 整体响度 I | %s LUFS | -14 ±0.5 | %s |" % (
        lw.get("I", "—"),
        "✅" if lw.get("I") and -14.81 <= lw["I"] <= -13.81 else "❌"))
    A("| 真峰值 TP | %s dBTP | ≤ -1.0 | %s |" % (
        lw.get("TP", "—"), "✅" if lw.get("TP") and lw["TP"] <= -1.0 else "❌"))
    A("| 响度范围 LRA | %s LU | — | — |" % lw.get("LRA", "—"))
    loud_line = summary(audio_report, r"loudnorm|LUFS|TP")
    if loud_line:
        A("| 混音报告 | %s | — | — |" % loud_line[:160].replace("|", "/"))
    A("")
    A("## 3. 画面与字幕\n")
    A("| 检查项 | 实测 | 结论 |")
    A("| --- | --- | --- |")
    names = {c["name"]: c for c in (check.get("checks") or [])}
    for k, label in (("letterbox_2.35", "2.35:1 遮幅（上下 132px 黑边）"),
                     ("content_present", "画面内容"),
                     ("subtitles_present", "字幕带文字存在"),
                     ("subtitles_band_black", "字幕落在下黑边内"),
                     ("endcard_text_density", "片尾双声明卡文字密度"),
                     ("fade_out_black", "尾部淡出/黑场")):
        c = names.get(k)
        if c:
            A("| %s | %s | %s |" % (label, c.get("detail", ""), "✅" if c.get("pass") else "❌"))
    A("")
    A("- 片尾双声明（画面）：「本片人物/画面由 AI 生成或含 AI 辅助制作」类声明由工程 `end_card` 保证；"
      "片尾静帧见 `delivery/stills/still-10-end-card.jpg`，供人工复核可读性（本机无 OCR，"
      "脚本以中心区文字像素密度 + 静帧目检判定）。")
    A("- 字幕：`work/srt/all.srt`（或 `src/data/srt.json`）驱动；脚本按下黑边文字像素抽检覆盖。")
    A("")
    A("## 4. 素材使用（H3 / 3D / 声音）\n")
    A("- MotionHarness Pro 3D 程序化场景：本片空间、相机、3D 图表、排版、遮幅、颗粒、字幕与最终合成。")
    A("- ComfyUI H3 证据影像：%s 条（provenance 见 `assets-manifest.json`）"
      % (h3_count if h3_count is not None else "见 assets/h3/manifest.json"))
    if h3_clips:
        for c in h3_clips[:20]:
            A("  - `%s` %s %s" % (c.get("path") or c.get("id") or c,
                                  c.get("duration_s") or "", c.get("method") or ""))
    A("- 声音：旁白 + BGM + 音效（%s 段/句级时间轴见 `audio/work/timeline_audio.json`）；"
      "混音目标 I=-14 LUFS / TP≤-1.0。" % (n_hnar if n_hnar else "见"))
    A("")
    A("## 5. 交付物\n")
    A("- 成片：`out/ep07-mh.mp4`（sha256 `%s`）" % (deliv.get("film_sha256") or sha256(FILM) or "—"))
    if deliv:
        A("- 静帧：`delivery/stills/` %s 张（%s）" % (
            len(deliv.get("beats") or []),
            ", ".join(b.get("name", "") for b in deliv.get("beats") or [])))
        A("- 联系表：`delivery/contact-sheet.jpg`")
        A("- 封面：%s" % ", ".join(deliv.get("covers") or []))
    A("- 工程：`/app/vedio/ep07-mh`（MotionHarness Pro）；仓库同步目录 `视频制作/ep07-motionharness/`（仅源码，素材不入库）")
    if render:
        A("- 导出：`%s`（quality=%s, fps=%s, 耗时 %s s）" % (
            render.get("command", "mh render out/ep07-mh.mp4"),
            render.get("quality", "master"), render.get("fps", 24),
            render.get("elapsed_s", "—")))
    if check.get("contact_sheet"):
        A("- 校验抽帧联系表：`%s`" % check["contact_sheet"])
    A("")
    A("## 6. 结论\n")
    A("**%s**" % ("全部硬指标通过，可交付。" if ok else
                  "存在未通过项：%s（需处理）。" % ", ".join(check.get("problems") or [])))
    if notes.strip():
        A("\n## 7. 制作备注 / 已知限制\n")
        A(notes.strip())
    A("")
    report = "\n".join(lines) + "\n"
    out_md = os.path.join(WORK, "final-report.md")
    os.makedirs(WORK, exist_ok=True)
    open(out_md, "w", encoding="utf-8").write(report)
    print("report ->", out_md)

    manifest = {
        "episode": "第07期《三年之后，你的车还值多少钱》",
        "generated_by": "MotionHarness Pro (3D + DOM 合成) + ComfyUI H3 证据影像",
        "generated_at_utc": now.isoformat(),
        "spec": {
            "film": {"path": "out/ep07-mh.mp4", "duration_s": dur,
                     "frames": check.get("frames"), "width": check.get("width"),
                     "height": check.get("height"), "fps": check.get("fps"),
                     "size_mb": check.get("size_mb"),
                     "sha256": (deliv.get("film_sha256") or sha256(FILM))},
            "expected_duration_s": check.get("expected_duration"),
            "expected_duration_source": check.get("expected_duration_source"),
            "loudness": lw,
            "checks": {c["name"]: c["pass"] for c in (check.get("checks") or [])},
            "problems": check.get("problems") or [],
        },
        "program": {
            "project_dir": "/app/vedio/ep07-mh",
            "project_type": "motionharness-pro",
            "entry": "src/project.ts",
            "shots": n_shots,
            "files": sorted(os.path.relpath(os.path.join(dp, f), ROOT)
                            for dp, dns, fns in os.walk(os.path.join(ROOT, "src"))
                            for f in fns) if os.path.isdir(os.path.join(ROOT, "src")) else [],
        },
        "h3": {
            "manifest": "assets/h3/manifest.json",
            "count": h3_count,
            "clips": h3_clips,
            "note": "H3 素材为大文件，不入库；仓库只保留 provenance 清单。",
        },
        "audio": {
            "timeline_audio": "audio/work/timeline_audio.json",
            "master": "audio/ep07-master.m4a",
            "report": "audio/work/audio-report.md",
            "segments_or_lines": n_hnar,
            "loudness": lw,
        },
        "delivery": {
            "manifest": "delivery/delivery-manifest.json",
            "stills": [b.get("name") for b in deliv.get("beats") or []],
            "contact_sheet": "delivery/contact-sheet.jpg",
            "covers": deliv.get("covers") or [],
        },
        "notes": notes.strip() or None,
    }
    out_json = os.path.join(ROOT, "assets-manifest.json")
    json.dump(manifest, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("manifest ->", out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
