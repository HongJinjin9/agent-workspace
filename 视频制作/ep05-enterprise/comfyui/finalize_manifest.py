#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild the authoritative assets/comfy/manifest.json from what actually exists on disk.

Merges: shots-ep05.json (prompts/specs), batch_run manifest (job ids / elapsed), raw files,
final cN.mp4 files, conform-status.json, verify-raw.json / verify-final.json.

Also used for the blocked case (no raws at all -> zero-record manifest per Lead spec).
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from probe_util import probe_video  # noqa: E402

A = ROOT / "assets" / "comfy"
SHOTS = ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"]


def load(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def save(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(p)


def parse_log_upscales(log_path):
    """Recover the *last* app 4x-UltraSharp job per shot from run.log (authoritative after clobbers)."""
    out = {}
    p = Path(log_path)
    if not p.exists():
        return out
    sub_re = re.compile(r"^\[(\S+)\] (c\d): upscale submitted .* prompt_id=(\S+)")
    done_re = re.compile(r"^\[(\S+)\] (c\d): upsale done in ([\d.]+)s -> .*? \(([\d.]+) MB, "
                         r"(\d+)x(\d+), ([\d.]+)s\)")
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = sub_re.match(ln)
        if m:
            out.setdefault(m.group(2), {})["upscale_job_id"] = m.group(3)
            continue
        m = done_re.match(ln)
        if m:
            sid = m.group(2)
            out.setdefault(sid, {}).update({
                "upscale_method": "app:4x-UltraSharp+lanczos 1920x1080",
                "upscale_elapsed_s": float(m.group(3)),
                "upscale_done_utc": m.group(1),
                "upscale_output_mb": float(m.group(4)),
                "final_res": [int(m.group(5)), int(m.group(6))],
            })
    # drop half-entries that never completed
    return {k: v for k, v in out.items() if "upscale_method" in v}


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


NOTE_OK = (
    "窗口异常/延迟开机：租用实例在 21:50（13:50Z）窗口开启时仍未开机——13:14Z 起对 "
    "https://wp08.unicorn.org.cn:24909 的探测持续为 TLS EOF（TCP 24909 可连、TLS ClientHello 后即断，"
    "无任何 HTTP 响应），持续到 14:27Z（约 45 次 login 轮询，每 15–45s 一次；期间从未出现 "
    "302→/login?err=1，证明不是账号密码问题）。14:27:12Z 门禁上线并接受登录（credentials OK），"
    "但后端 ComfyUI 仍在启动（/system_stats 返回 502）；14:28:08Z 后端就绪（ComfyUI 0.36.0 / "
    "RTX 5090 33.7GB）。随后在压缩后的窗口内完成 C1–C8 全部 8 条生成（14:28:10–14:33:44Z）与本地 1080p 初版交付，"
    "并在 14:36:00–14:49:54Z 将 8/8 成片全部替换为 app 4x-UltraSharp 超分版；所有 raws 均在 14:33:44Z 完成下载。"
    "机器按分钟计费，本次实际生成+超分占用约 23 分钟机器时间；最后一条任务 14:49:54Z 完成后即保持 idle，未再提交任务。"
)

NOTE_BLOCKED = (
    "窗口阻塞：2026-11-12 13:50–14:50 UTC（北京 21:50–22:50）租用实例始终未开机。"
    "从 13:14Z 起对 https://wp08.unicorn.org.cn:24909 的探测全部为 TLS EOF（TCP 24909 可连、"
    "TLS ClientHello 后连接被断，无任何 HTTP 响应），从未出现 302→/login?err=1，因此不是账号密码问题。"
    "窗口内累计 login 轮询 45+ 次全部失败，未提交任何生成任务，未产生生成费用（仅租用费用）。"
    "按 SPEC §0 退路：C1–C4 用 ep03 签字/桌面 B-roll + 程序化数据层，C5–C8 用 ep02 城市/空椅/雨窗 + 程序化光效。"
)


def main():
    doc = load(HERE / "shots-ep05.json")
    old = load(A / "manifest.json", default=None) or {}
    old_shots = old.get("shots", {}) or {}
    conf = load(A / "conform-status.json", default=None) or {}
    conf_shots = conf.get("shots", {}) or {}
    vr = {Path(x["path"]).stem.split("_")[0]: x for x in (load(A / "verify-raw.json", []) or [])}
    vf = {Path(x["path"]).stem.split("_")[0]: x for x in (load(A / "verify-final.json", []) or [])}
    up_log = parse_log_upscales(HERE / "run.log")

    shots_out = {}
    any_raw = False
    for s in doc["shots"]:
        sid = s["id"]
        raw = A / "raw" / f"{sid}_raw.mp4"
        fin = A / f"{sid}.mp4"
        prev = old_shots.get(sid, {}) or {}
        cs = conf_shots.get(sid, {}) or {}
        entry = {
            "id": sid, "label": s.get("title", ""), "segments": s.get("seg", ""),
            "spec": s.get("md", ""), "prompt": s["prompt"], "seed": s["seed"],
            "req_res": [s["width"], s["height"]], "req_duration_s": s["duration"],
        }
        for k in ("job_id", "elapsed_s", "downloaded_utc", "source_filename"):
            if prev.get(k) is not None:
                entry[k] = prev[k]
        if raw.exists():
            any_raw = True
            pr = probe_video(raw)
            entry.update({"raw": str(raw.relative_to(ROOT)), "raw_res": [pr.get("width"), pr.get("height")],
                          "raw_duration_s": pr.get("duration_s"), "raw_fps": pr.get("fps"),
                          "raw_audio": pr.get("audio"), "status": "downloaded"})
        if fin.exists():
            fp = probe_video(fin)
            log_up = up_log.get(sid) or {}
            prev_m = prev.get("upscale_method") or ""
            cs_m = cs.get("method") or ""
            if log_up.get("upscale_method"):
                method = log_up["upscale_method"]
            elif "UltraSharp" in prev_m:
                method = prev_m
            elif cs_m:
                method = cs_m
            else:
                method = prev_m or "local-ffmpeg"
            entry.update({
                "final": str(fin.relative_to(ROOT)),
                "final_res": [fp.get("width"), fp.get("height")],
                "final_duration_s": fp.get("duration_s"), "final_fps": fp.get("fps"),
                "upscaled": True, "upscale_method": method, "status": "ok",
            })
            if log_up:
                for k in ("upscale_job_id", "upscale_elapsed_s", "upscale_done_utc",
                          "upscale_output_mb"):
                    if log_up.get(k) is not None:
                        entry[k] = log_up[k]
            elif cs.get("elapsed_s"):
                entry["upscale_elapsed_s"] = cs["elapsed_s"]
        elif prev.get("status") == "failed":
            entry.update({"status": "failed", "error": prev.get("error")})
        if sid in vr:
            entry["verified_raw"] = {"pass": bool(vr[sid].get("pass")),
                                     "problems": vr[sid].get("problems", [])}
        if sid in vf:
            entry["verified_final"] = {"pass": bool(vf[sid].get("pass")),
                                       "problems": vf[sid].get("problems", [])}
        shots_out[sid] = entry

    final_count = sum(1 for v in shots_out.values() if v.get("final"))
    raw_count = sum(1 for v in shots_out.values() if v.get("raw"))

    if raw_count == 0:
        man = {
            "series": "ep05-enterprise",
            "generated": False,
            "reason": ("App unreachable for the whole 13:50–14:50Z window: gate TLS EOF, no HTTP response; "
                       "no generation job was ever submitted (not a credentials failure; no 302 /login?err=1)."),
            "shots": {},
        }
        print("BLOCKED: no raw clips -> zero-record manifest per Lead spec")
    else:
        man = {
            "series": "ep05-enterprise",
            "generated": final_count == 8,
            "generated_utc": now(),
            "window_utc": "2026-11-12T14:28:08Z/14:33:13Z",
            "window_nominal_utc": "2026-11-12T13:50:00Z/14:50:00Z (entry unreachable until 14:27:12Z)",
            "app_entry": "https://wp08.unicorn.org.cn:24909",
            "generator": "ComfyUI H3 video app — MiniMax H3 int8 + 8-step turbo LoRA, RTX 5090 32GB (ComfyUI 0.36.0)",
            "app_ready_utc": "2026-11-12T14:28:08Z",
            "window_note": NOTE_OK,
            "evidence": {
                "failure_mode_before_14:27Z": "TLS EOF after ClientHello (TCP connect OK), no HTTP response",
                "login_rejected": False,
                "gate_backend_502_at": "2026-11-12T14:27:12Z",
                "backend_ready_at": "2026-11-12T14:28:08Z",
                "first_generation_submit_utc": "2026-11-12T14:28:10Z",
            },
            "counts": {"raw": raw_count, "final_1080p": final_count, "total": 8},
            "shots": shots_out,
        }
    save(A / "manifest.json", man)
    print(f"manifest: generated={man['generated']} raw={raw_count} final={final_count} "
          f"-> {A / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
