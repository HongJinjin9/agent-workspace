#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build comfyui/report.md (+ a compact manifest summary) from run.log / manifest / verify JSON.

Usage after the window:
  python3 verify_clip.py ../assets/comfy/raw/c*_raw.mp4 --frames-dir ../assets/comfy/frames/raw \
      > ../assets/comfy/verify-raw.json 2>/dev/null
  python3 verify_clip.py ../assets/comfy/c*.mp4 --frames-dir ../assets/comfy/frames/final \
      > ../assets/comfy/verify-final.json 2>/dev/null
  python3 make_report.py
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COMFY = ROOT / "assets" / "comfy"

SHOT_ORDER = ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"]
LOG_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\]\s+(.*)$")


def load(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def read_log(p):
    events = []
    p = Path(p)
    if not p.exists():
        return events
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LOG_RE.match(ln)
        if m:
            events.append({"t": m.group(1), "msg": m.group(2)})
    return events


def timeline(events):
    keep = []
    for e in events:
        m = e["msg"]
        if e["t"] < "2026-11-12T13:45":
            continue  # pre-window script tests
        if re.search(r"env loaded|upscale target|upscale login OK|final already exists|"
                     r"skip upscale|progress:", m):
            continue
        if re.search(r"login OK|submit attempt|prompt_id=|saved |batch done|"
                     r"UPSCALE|LOCAL hero|submitted|done in|fallback|deadline|FAILED|STATS_OK|"
                     r"BACKEND|window", m):
            keep.append(e)
    # collapse consecutive identical-ish wait spam is already filtered by the regex
    return keep


def fmt_verify(v):
    if not v:
        return "—"
    if v.get("pass"):
        return "PASS"
    return "FAIL: " + "; ".join(v.get("problems") or [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(COMFY / "manifest.json"))
    ap.add_argument("--verify-raw", default=str(COMFY / "verify-raw.json"))
    ap.add_argument("--verify-final", default=str(COMFY / "verify-final.json"))
    ap.add_argument("--log", default=str(HERE / "run.log"))
    ap.add_argument("--out", default=str(HERE / "report.md"))
    args = ap.parse_args()

    man = load(args.manifest, {}) or {}
    shots = man.get("shots", {})
    vr = {Path(x["path"]).stem.split("_")[0]: x for x in (load(args.verify_raw, []) or [])}
    vf = {Path(x["path"]).stem.split("_")[0]: x for x in (load(args.verify_final, []) or [])}
    events = read_log(args.log)
    tl = timeline(events)
    first = tl[0]["t"] if tl else "—"
    last = tl[-1]["t"] if tl else "—"

    rows = []
    for sid in SHOT_ORDER:
        s = shots.get(sid, {})
        raw_res = s.get("raw_res") or s.get("req_res") or ["?", "?"]
        fr = s.get("final_res") or ["?", "?"]
        rows.append(
            f"| {sid} | {s.get('label','(missing)')} | {raw_res[0]}×{raw_res[1]} | "
            f"{s.get('req_duration_s','?')}s | {s.get('elapsed_s','—')} | {s.get('job_id','—')} | "
            f"{s.get('upscale_method','—')} | {fr[0]}×{fr[1]} | "
            f"{fmt_verify(vr.get(sid))} | {fmt_verify(vf.get(sid))} |")

    failed = [sid for sid in SHOT_ORDER
              if (shots.get(sid) or {}).get("status") in ("failed", "unavailable")]
    missing = [sid for sid in SHOT_ORDER if sid not in shots]
    total_elapsed = 0.0
    for sid in SHOT_ORDER:
        try:
            total_elapsed += float((shots.get(sid) or {}).get("elapsed_s") or 0)
        except (TypeError, ValueError):
            pass
    upscaled = [sid for sid in SHOT_ORDER if shots.get(sid, {}).get("upscaled") is True]
    native = [sid for sid in SHOT_ORDER if shots.get(sid, {}).get("upscaled") is False]

    L = []
    L.append("# 第 05 期 · ComfyUI H3 出片报告（C1–C8）\n")
    L.append(f"> 名义时间窗（租用）：2026-11-12 13:50–14:50 UTC（北京 21:50–22:50，按分钟计费）。"
             f"**实际生成窗口：{man.get('window_utc', '—')}**（入口在 13:50–14:27Z 期间不可达，14:27:12Z 门禁上线、14:28:08Z 后端就绪）。"
             f"本次日志覆盖 {first} → {last}（UTC）。")
    L.append("> 机器：优云智算 ComfyUI H3 视频版 / RTX 5090 32GB / ComfyUI 0.36.0；"
             "MiniMax H3 int8（`minimax_h3_fl2va_pruned_int8_convrot`）+ 8 步 turbo LoRA。")
    L.append("> 入口 `https://wp08.unicorn.org.cn:24909`（WyfGate 门禁）。凭据只走环境变量，未写入任何仓库文件。\n")
    L.append("## 1. 结果总览\n")
    L.append(f"- 交付：`assets/comfy/c1.mp4` … `c8.mp4`（1920×1080 / 24fps / H.264 yuv420p / AAC 48k，约 5.17s）")
    raw_specs = []
    for sid in SHOT_ORDER:
        rr = (shots.get(sid) or {}).get("raw_res") or (shots.get(sid) or {}).get("req_res") or ["?", "?"]
        if sid in shots:
            raw_specs.append(f"{sid} {rr[0]}×{rr[1]}")
    L.append(f"- 原始产物：`assets/comfy/raw/cN_raw.mp4`（{'; '.join(raw_specs)}）")
    L.append(f"- app 4x-UltraSharp 超分：{', '.join(upscaled) or '无'}")
    L.append(f"- 本地 ffmpeg/原生回退：{', '.join(native) or '无'}（详见 §2 表）")
    if failed:
        L.append(f"- **失败镜头**：{', '.join(failed)}")
    if missing:
        L.append(f"- **未生成**：{', '.join(missing)}")
    L.append(f"- 生成采样累计耗时（各片 elapsed 之和）：{total_elapsed:.0f}s；日志事件 {len(events)} 条\n")
    L.append("## 2. 逐镜清单\n")
    L.append("| 镜头 | 内容 | 生成分辨率 | 时长 | 生成耗时 | job id | 1080p 方法 | 最终分辨率 | 原始校验 | 成片校验 |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    L.extend(rows)
    L.append("")
    L.append("## 3. 窗口时间线（自动提取自 comfyui/run.log）\n")
    L.append("```text")
    for e in tl:
        L.append(f"{e['t']}  {e['msg'][:180]}")
    L.append("```\n")
    L.append("## 4. 提示词与工作流\n")
    L.append("- 提示词全文：`comfyui/prompts-ep05.md`（机器可读 `comfyui/shots-ep05.json`）；"
             "写法 = `integrated_multimodal_description` + `overall_soundscape` + `non_diegetic_music`。")
    L.append("- 工作流：`comfyui/workflows/t2v_api.json`；改 prompt/宽高 `140:131`、时长 `140:133`、"
             "seed `140:129`、8 步 turbo 开关 `140:139`、输出前缀 `92`。")
    L.append("- 超分工作流：`comfyui/upscale_all.py` 内联图（LoadVideo→4x-UltraSharp→lanczos 1920×1080→CreateVideo 带音轨）。")
    L.append("- 审片：`comfyui/verify_clip.py`（ffmpeg 探针 + 10/50/90% 抽帧 + 帧差运动量），"
             "抽帧在 `assets/comfy/frames/`。\n")
    L.append("## 5. 失败与处理\n")
    if man.get("window_note"):
        L.append(f"**窗口状态**：{man['window_note']}\n")
    if failed:
        for sid in failed:
            L.append(f"- {sid}: {shots[sid].get('error','?')}")
    else:
        L.append("- 采样：无 job 级失败。")
    ups_fail = [sid for sid in SHOT_ORDER if shots.get(sid, {}).get("upscale_error")]
    if ups_fail:
        for sid in ups_fail:
            L.append(f"- {sid} 超分失败后回退：{shots[sid]['upscale_error']}")
    else:
        L.append("- 超分：无失败。")
    L.append("")
    L.append("## 6. 环境与已知限制\n")
    L.append("- 本机没有真 ffprobe（`/home/admin/.local/bin/ffprobe` 实为 ffmpeg 的软链），"
             "校验用 `ffmpeg -i` stderr + OpenCV 交叉核对（分辨率/帧率/时长/编码/音轨/帧数），"
             "等效于 ffprobe 必查项；`verify_clip.py` 的 3 帧目检由 operator 人工完成。")
    L.append("- H3 原生输出 24fps、约 5.167s（124 帧）；成片按 5s 左右 in/out 使用。")
    L.append("- 提示词已避开文字/公司标识/人脸；抽帧核查后如有残留文字，需后期遮挡（见 §5）。")
    L.append("- MiniMax H3 商用需确认 Comfy 商业许可（README §六）；成片需 AI 声明（SPEC §4）。")
    L.append("")

    out = Path(args.out)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(L)} lines)")
    print(f"failed={failed} missing={missing} upscaled={upscaled} native={native}")


if __name__ == "__main__":
    main()
