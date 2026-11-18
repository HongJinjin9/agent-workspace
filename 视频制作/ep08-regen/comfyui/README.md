# 第 08 期 ComfyUI H3 交接包（h3-operator）

> 把「代码关键帧 → 生成运动 → 本地 1080p → 逐条验收」这条链固定下来，计费窗口内只跑必要步骤。
> 规范：`PLAN.md` §4 窗口纪律 + `refs/comfyui.txt` PDF §4（交接接口/提示词写法）。
> 凭据只走环境变量（`/home/admin/.h3.env` 或 Lead 下发），仓库内与日志中**无凭据**。

## 目录

| 文件 | 用途 |
| --- | --- |
| `RUNBOOK.md` | **窗口操作手册**（开机前门禁、6 步执行、降级预案、验收口径、hero 升级） |
| `shots-ep08.json` | engine-dev 的 H3 工单（只读消费；24 镜：17 FL2VA + 7 T2V） |
| `shots-ep08-run.json` | 可执行工单（本目录生成：提示词终版 + 关键帧路径 + seed/分辨率/mode 就绪） |
| `prompt-overrides-ep08.json` | 人工润色的 24 条提示词（机器源，`shots-ep08-run.json` 由它 + engine 工单生成） |
| `prompts-ep08.md` | 提示词人读表（由 `shots-ep08-run.json` 生成，勿手改） |
| `workflows/t2v_api.json` | 实测 API 工作流（23 节点，`/prompt` 直提） |
| `workflows/fl2va_api.json` | FL2VA 参考图（27 节点：LoadImage→ImageScale→first_frame/last_frame） |
| `batch_run.py` | 批量执行：login→上传关键帧→生成（FL2VA 优先/T2V 降级/重试/deadline）→下载 |
| `capability_probe.py` | 窗口首步能力探测（FL2VA optional 口/模型/上传口/system_stats） |
| `resolve_base.py` | 入口解析（env `H3_BASE` → ep05/ep07 已知端口 → `--base`，15s 轮询） |
| `local_conform.py` / `conform_watch_ep08.py` | 本地 lanczos 1080p（cover 缩放+中心裁切，保留原生音轨） |
| `verify_clip.py` / `frame_sheet.py` / `keyframe_adherence.py` | 逐条硬校验/抽帧三联图/首帧一致性 |
| `check_pack.py` / `selftest_local.py` | 开机前静态门禁 + 本地链路自测（无网络） |
| `build_run_orders.py` | 从 engine 工单 + 提示词终版生成可执行工单并跑门禁 |
| `make_report_ep08.py` | 窗口后报告 + `assets/h3/manifest.json` 定稿 |
| `window_run.sh` | `preflight`（无网络全检）/ `run`（真实窗口 6 步） |

## 快速命令

```bash
cd /app/vedio/ep08-regen/comfyui
./window_run.sh preflight        # 开机前：全绿才允许用户开机
./window_run.sh run              # Lead 说「窗口开启」后
```

产物：`assets/h3/H01.mp4…`（1920×1080 / 24fps / H.264+AAC）、`assets/h3/raw/`、`assets/h3/manifest.json`、
`comfyui/report.md`。素材与成片**不入库**；本目录只同步脚本/文档/提示词/报告。
