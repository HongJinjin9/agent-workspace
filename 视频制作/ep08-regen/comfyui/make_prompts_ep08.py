#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os as _os
# 4-core / 6GB cgroup: keep BLAS/torch/ffmpeg thread counts low (Lead resource rule)
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    _os.environ.setdefault(_k, "2")
"""Render prompts-ep08.md (human-readable prompt sheet) from shots-ep08-run.json.

Machine source of truth is shots-ep08-run.json; this file is generated so the two never
drift.  python3 make_prompts_ep08.py
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "shots-ep08-run.json"
OUT = HERE / "prompts-ep08.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=str(RUN))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    run_path = Path(args.shots)
    doc = json.loads(run_path.read_text(encoding="utf-8"))
    shots = doc["shots"]
    d = doc.get("defaults", {})
    lines = []
    lines.append(f"# 第 08 期 ComfyUI H3 提示词（{len(shots)} 条，"
                 f"{d.get('width', 864)}×{d.get('height', 480)} / "
                 f"{d.get('duration', 5.0)}s / 8 步 turbo LoRA）")
    lines.append("")
    lines.append("> 本文件由 `make_prompts_ep08.py` 从机器可读源 `shots-ep08-run.json` 生成，勿手改。")
    lines.append("> 入口/凭据只走环境变量（`H3_USER`/`H3_PASS`/`H3_BASE` 或 `/home/admin/.h3.env`），"
                 "绝不写入仓库、日志或消息。")
    lines.append("> 工作流 `workflows/t2v_api.json`（API 格式，实测直提）；变量节点：")
    lines.append("> prompt/width/height/length = `140:131`，时长秒 = `140:133`，"
                 "帧数表达式 = `140:132`，seed = `140:129`，")
    lines.append("> 8 步 turbo LoRA 开关 = `140:139`（true→`140:138`=8），SaveVideo = `92`；")
    lines.append("> 首帧/尾帧走 FL2VA：`LoadImage 900/910` → `ImageScale 901/911` → "
                 "`MiniMaxH3ImageToVideo.first_frame/last_frame`。")
    lines.append("> 提示词规范（PDF §4）：分阶段时间轴、一次一种运镜、声音显式描述、"
                 "末尾固定禁止事项；单条 ≤15s（本期 5s）。")
    lines.append("")
    lines.append("## 分镜映射")
    lines.append("")
    lines.append("| 镜头 | 段落/锚点 | 内容 | 生成分辨率 | 时长 | 模式 | seed | 首帧 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for s in shots:
        mode = "FL2VA" if (s.get("first_frame") or s.get("last_frame")) else "T2V"
        kf = Path(s["first_frame"]).name if s.get("first_frame") else "—"
        lines.append(f"| {s['id']} | {s.get('seg', '')} | {s.get('title', '')} | "
                     f"{s['width']}×{s['height']} | {s['duration']}s | {mode} | {s['seed']} | {kf} |")
    lines.append("")
    for s in shots:
        mode = "FL2VA/i2v（首帧锁定构图）" if s.get("first_frame") else "T2V（无关键帧降级）"
        lines.append(f"## {s['id']} · {s.get('title', '')}")
        lines.append("")
        lines.append(f"- 用途：`{s.get('seg', '')}`；{s['width']}×{s['height']} / "
                     f"{s['duration']}s / seed {s['seed']} / {mode}")
        if s.get("first_frame"):
            lines.append(f"- 首帧：`{s['first_frame']}`"
                         + (f"；尾帧：`{s['last_frame']}`" if s.get("last_frame") else ""))
        lines.append("")
        lines.append("```text")
        lines.append(s["prompt"])
        lines.append("```")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 负向/避坑（H3 无独立 negative 输入，只能写在正向描述末尾）")
    lines.append("")
    lines.append("- 文字/数字/LOGO/车牌必乱码：一律写 no readable text / no logos，成片逐条抽帧核查；"
                 "信息一律由代码字幕与叠加层承担。")
    lines.append("- 真人正脸不稳：只出手、背影、侧影或过肩；关键帧已锁构图时提示词只写运动。")
    lines.append("- 声音只允许环境音/音效，禁止人声台词与配乐（配乐由代码合成）；"
                 "否则两条人声打架、与母带冲突。")
    lines.append("- 一个镜头只做一件事；运动写「物理后果」，不堆形容词；运镜一次只写一种。")
    lines.append("- 时长与帧数：5s→124 帧@24fps（17k+5 网格），由 `140:132` 表达式自动取整。")
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out} ({len(shots)} shots, {len(lines)} lines)")


if __name__ == "__main__":
    main()
