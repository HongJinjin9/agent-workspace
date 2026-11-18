#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os as _os
# 4-core / 6GB cgroup: keep BLAS/torch/ffmpeg thread counts low (Lead resource rule)
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    _os.environ.setdefault(_k, "2")
"""EP08 window report + manifest finalize (run right after generation/verify).

Inputs:
  assets/h3/manifest.json          per-shot authoring state written by batch_run.py
  assets/h3/conform-status.json    local 1080p conform state (conform_watch_ep08.py)
  assets/h3/verify-raw.json        verify_clip.py on raw clips
  assets/h3/verify-final.json      verify_clip.py on 1920x1080 finals
  assets/h3/capability.json        window capability probe
  comfyui/run.log                  timestamped submit/finish lines
Outputs:
  comfyui/report.md                human report (per-shot table, timings, degradations)
  comfyui/report.json              machine summary
  assets/h3/manifest.json          finalized counts / window / generated_utc
"""
import argparse
import datetime as _dt
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
A = ROOT / "assets" / "h3"
MANIFEST = A / "manifest.json"
REPORT_MD = HERE / "report.md"
REPORT_JSON = HERE / "report.json"


def now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def save_json(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(p)


def verify_index(path):
    doc = load_json(path, default=None)
    if not doc:
        return {}
    if isinstance(doc, dict):
        doc = [doc]
    out = {}
    for r in doc:
        if not isinstance(r, dict):
            continue
        stem = Path(r.get("path", "")).stem
        sid = stem.split("_")[0]
        out[sid] = r
    return out


def parse_log(path):
    """Extract per-shot submit/finish/saved lines and window bounds from run.log."""
    events = []
    if not path.exists():
        return events, {}
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\[(\d{4}-\d\d-\d\dT[\d:]+Z)\]\s+(.*)", ln)
        if not m:
            continue
        ts, msg = m.group(1), m.group(2)
        events.append((ts, msg))
    bounds = {}
    if events:
        bounds["first"] = events[0][0]
        bounds["last"] = events[-1][0]
    batch = [msg for _, msg in events if msg.startswith("batch done in ")]
    if batch:
        m = re.search(r"batch done in ([\d.]+)s: (\d+)/(\d+) ok", batch[-1])
        if m:
            bounds["batch_elapsed_s"] = float(m.group(1))
            bounds["batch_ok"] = int(m.group(2))
            bounds["batch_total"] = int(m.group(3))
    return events, bounds


def rel(p):
    try:
        return str(Path(p).relative_to(ROOT))
    except ValueError:
        return str(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=str(HERE / "shots-ep08-run.json"))
    args = ap.parse_args()

    run = load_json(args.shots, default=None) or {}
    shots = run.get("shots", [])
    man = load_json(MANIFEST, default=None) or {"series": "ep08-regen", "shots": {}}
    mshots = man.setdefault("shots", {})
    raw_verify = verify_index(A / "verify-raw.json")
    fin_verify = verify_index(A / "verify-final.json")
    caps = load_json(A / "capability.json", default=None) or {}
    events, bounds = parse_log(HERE / "run.log")

    rows, counts = [], {"total": len(shots), "raw": 0, "final": 0, "ok": 0,
                        "fl2va": 0, "t2v": 0, "t2v_fallback": 0, "failed": 0,
                        "deferred": 0, "verify_raw_pass": 0, "verify_final_pass": 0}
    for s in shots:
        sid = s["id"]
        m = mshots.get(sid, {})
        raw = A / "raw" / f"{sid}_raw.mp4"
        fin = A / f"{sid}.mp4"
        raw_has = raw.exists()
        fin_has = fin.exists()
        if raw_has:
            counts["raw"] += 1
        if fin_has:
            counts["final"] += 1
        mode = m.get("mode") or ("fl2va" if s.get("first_frame") else "t2v")
        if mode == "fl2va":
            counts["fl2va"] += 1
        elif m.get("status") == "ok" and s.get("first_frame"):
            counts["t2v_fallback"] += 1
        else:
            counts["t2v"] += 1
        status = m.get("status", "pending")
        if status in ("downloaded", "ok") and raw_has:
            counts["ok"] += 1
        elif status == "redline_fallback":
            counts.setdefault("redline_fallback", 0)
            counts["redline_fallback"] += 1
        elif status == "failed":
            counts["failed"] += 1
        elif status == "deferred":
            counts["deferred"] += 1
        rv = raw_verify.get(sid, {})
        fv = fin_verify.get(sid, {})
        if rv.get("pass"):
            counts["verify_raw_pass"] += 1
        if fv.get("pass"):
            counts["verify_final_pass"] += 1
        rows.append({
            "id": sid, "shot": s.get("shot"), "seg": s.get("seg", ""),
            "title": s.get("title", ""),
            "mode": mode, "width": s.get("width"), "height": s.get("height"),
            "duration": s.get("duration"), "seed": s.get("seed"),
            "job_id": m.get("job_id"), "elapsed_s": m.get("elapsed_s"),
            "status": status, "raw": rel(raw) if raw_has else "",
            "final": rel(fin) if fin_has else "",
            "final_alias": m.get("final_alias"),
            "final_res": m.get("final_res"),
            "verify_raw": "PASS" if rv.get("pass") else ("FAIL" if rv else "—"),
            "verify_final": "PASS" if fv.get("pass") else ("FAIL" if fv else "—"),
            "raw_problems": rv.get("problems"),
            "final_problems": fv.get("problems"),
            "redline_reason": (m.get("redline") or {}).get("reason"),
            "regen_note": m.get("regen_note"),
        })

    man.update({
        "series": "ep08-regen",
        "generated_utc": now(),
        "generator": "ComfyUI H3 (MiniMax H3 FL2VA int8 + 8-step turbo LoRA, RTX5090)",
        "app_entry": (caps.get("base") or "env H3_BASE"),
        "window": {"first_log": bounds.get("first"), "last_log": bounds.get("last"),
                   "batch_elapsed_s": bounds.get("batch_elapsed_s")},
        "capability": caps.get("decision") or {},
        "counts": counts,
        "shots": mshots,
    })
    save_json(MANIFEST, man)

    report = {"generated_utc": now(), "counts": counts, "shots": rows,
              "window": bounds, "capability": caps.get("decision") or {}}
    save_json(REPORT_JSON, report)

    md = []
    md.append("# 第 08 期 · ComfyUI H3 生成与验收报告")
    md.append("")
    md.append(f"> 生成入口：`{caps.get('base', 'env H3_BASE')}`（WyfGate 门禁；"
              f"凭据只走环境变量，未写入任何文件/消息/仓库）。")
    md.append(f"> 窗口日志覆盖：{bounds.get('first', '—')} → {bounds.get('last', '—')}；"
              f"批量生成耗时 {bounds.get('batch_elapsed_s', '—')}s。")
    md.append("")
    md.append("## 1. 结果总览")
    md.append("")
    md.append(f"- 镜头：{counts['total']} 条；raw {counts['raw']} / 本地 1080p {counts['final']} / "
              f"生成成功 {counts['ok']}")
    md.append(f"- 模式：FL2VA/i2v {counts['fl2va']} 条；T2V {counts['t2v']} 条"
              f"（其中 FL2VA 失败后降级 {counts['t2v_fallback']} 条）")
    md.append(f"- 失败/顺延：{counts['failed']} / {counts['deferred']}")
    md.append(f"- 校验：raw PASS {counts['verify_raw_pass']}/{counts['raw']}；"
              f"1080p PASS {counts['verify_final_pass']}/{counts['final']}")
    if caps:
        d = caps.get("decision") or {}
        md.append(f"- 能力探测：ComfyUI {caps.get('comfyui_version')} / {caps.get('gpu')}；"
                  f"FL2VA={d.get('fl2va_mode')}；降级={d.get('degraded')}"
                  f"{'（' + '; '.join(d.get('degrade_reasons') or []) + '）' if d.get('degraded') else ''}")
    md.append("")
    md.append("## 2. 逐镜清单")
    md.append("")
    md.append("| 镜头 | 镜号 | 段落 | 内容 | 模式 | 生成 | 时长 | seed | 耗时(s) | job id | "
              "raw 校验 | 1080p 校验 | 状态 |")
    md.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        md.append(f"| {r['id']} | {r.get('shot') or '—'} | {r['seg']} | {r['title']} | {r['mode']} | "
                  f"{r['width']}×{r['height']} | {r['duration']}s | {r['seed']} | "
                  f"{r['elapsed_s'] if r['elapsed_s'] is not None else '—'} | "
                  f"{r['job_id'] or '—'} | {r['verify_raw']} | {r['verify_final']} | {r['status']} |")
    md.append("")
    bad = [r for r in rows if r["status"] in ("failed", "deferred", "pending", "app_down",
                                             "redline_fallback")
           or r["verify_raw"] == "FAIL" or r["verify_final"] == "FAIL"]
    md.append("## 3. 失败 / 降级 / 待处理")
    md.append("")
    if bad:
        for r in bad:
            extra = f"；红线：{r['redline_reason']}" if r.get("redline_reason") else ""
            md.append(f"- **{r['id']}** status={r['status']} "
                      f"raw={r['raw'] or 'missing'} final={r['final'] or 'missing'} "
                      f"problems={r['raw_problems'] or r['final_problems']}{extra}")
        reok = [r for r in rows if r.get("regen_note")]
        if reok:
            md.append("")
            md.append("### 3.1 红线重生成后通过（已替换为新文件）")
            md.append("")
            for r in reok:
                md.append(f"- **{r['id']}**：{r['regen_note']}（`{r['final']}`）")
    else:
        md.append("- 无：全部镜头生成成功、raw 与 1080p 均通过硬校验。")
    t2v_fb = [r for r in rows if r["mode"] == "t2v" and r["width"]]
    if t2v_fb:
        md.append("")
        md.append("## 4. T2V 降级镜头（无关键帧 / FL2VA 失败）")
        md.append("")
        for r in t2v_fb:
            md.append(f"- {r['id']}：{r['title']}（{r['width']}×{r['height']}）")
    md.append("")
    md.append("## 5. 文件与复现")
    md.append("")
    md.append("- 1080p 成片：`assets/h3/H01.mp4` … `assets/h3/H24.mp4`（1920×1080 / 24fps / H.264 + AAC）；"
              "同时硬链接 `assets/h3/S01.mp4` …（engine `shot` 命名），manifest 两个路径都记。")
    md.append("- 原始：`assets/h3/raw/{ID}_raw.mp4`（864×480 或 hero 1280×736，H3 原生音轨）")
    md.append("- 清单：`assets/h3/manifest.json`；能力探测：`assets/h3/capability.json`；"
              "逐帧校验：`assets/h3/verify-raw.json` / `verify-final.json`；抽帧：`assets/h3/frames/`")
    md.append("- 提示词：`comfyui/prompts-ep08.md`（机器可读 `comfyui/shots-ep08-run.json`）")
    md.append("")
    md.append("```bash")
    md.append("export H3_USER=… H3_PASS=… H3_BASE=…   # 只走环境变量")
    md.append("cd /app/vedio/ep08-regen/comfyui")
    md.append("python3 check_pack.py                     # 开机前静态校验")
    md.append("python3 resolve_base.py 1800              # 入口探测")
    md.append("python3 capability_probe.py               # 节点/模型/FL2VA 探测")
    md.append("python3 batch_run.py --retries 1          # 生成（FL2VA 优先，失败降级 T2V）")
    md.append("python3 local_conform.py --fill-missing  # 本地 lanczos 1080p")
    md.append("python3 verify_clip.py ../assets/h3/raw/H*_raw.mp4 --frames-dir ../assets/h3/frames")
    md.append("python3 verify_clip.py ../assets/h3/H??.mp4 --frames-dir ../assets/h3/frames --expect 1920x1080")
    md.append("python3 make_report_ep08.py               # 本报告 + manifest 定稿")
    md.append("```")
    REPORT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {REPORT_MD}")
    print(f"wrote {REPORT_JSON}")
    print(f"counts: {json.dumps(counts, ensure_ascii=False)}")
    print("RESULT: REPORT_OK")


if __name__ == "__main__":
    main()
