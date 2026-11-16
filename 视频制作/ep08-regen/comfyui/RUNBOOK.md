# 第 08 期 H3 窗口 Runbook（ComfyUI · 计费 1 小时 · 人工开机）

> 权威源：`/app/vedio/ep08-regen/PLAN.md`（尤其 §4 窗口纪律）+ `refs/comfyui.txt`（PDF §4 交接接口）
> 分工：只有 H3 负责「像真的」——真实道路/车内/踏板/刹车灯/底盘/充电口实拍质感 + 环境声。
> H3 **永不**承载文字、数字、原理示意、字幕、配音；声音只允许环境音/音效，禁止人声台词与配乐。
> 凭据只从 `/home/admin/.h3.env` 或环境变量读取；**任何情况下不打印/写入文件/消息/日志/仓库**。

---

## 0. 交接包清单（开机前必须全部 ✅）

| # | 项 | 位置 | 状态 |
| --- | --- | --- | --- |
| 1 | H3 工单（引擎侧，只读消费） | `comfyui/shots-ep08.json` | 等 engine-dev |
| 2 | 首帧关键帧（+可选尾帧） | `comfyui/keyframes/<ID>_first.png` | 等 engine-dev |
| 3 | 可执行工单（提示词已按 PDF §4 润色） | `comfyui/shots-ep08-run.json` | 由 1/2 生成 |
| 4 | 提示词表（人读） | `comfyui/prompts-ep08.md` | 由 3 生成 |
| 5 | 工作流模板 | `comfyui/workflows/t2v_api.json` / `fl2va_api.json` | ✅ |
| 6 | 批量执行器（FL2VA 优先 / T2V 降级 / 重试 / deadline） | `comfyui/batch_run.py` | ✅ |
| 7 | 本地 1080p + 逐条校验 + 报告 | `local_conform.py`、`conform_watch_ep08.py`、`verify_clip.py`、`make_report_ep08.py` | ✅ |
| 8 | 静态校验 + 本地链路自测 | `check_pack.py`、`selftest_local.py`、`window_run.sh preflight` | ✅ |
| 9 | 入口/凭据读取 | `/home/admin/.h3.env`（`H3_USER`/`H3_PASS`/`H3_BASE`）；新入口由 Lead 走 env | ✅（不落盘） |

**开机前门禁（Lead 只在下面全绿后才提示用户开机）**

```bash
cd /app/vedio/ep08-regen/comfyui
./window_run.sh preflight        # → 必须 RESULT: PREFLIGHT_OK
```

preflight 覆盖：python 语法、shell 语法、workflow 变量节点、工单 schema/提示词规范、
关键帧存在性/可解码/16:9/非空白、本地 1080p→verify 全链路自测、dry-run 工作流构建、
单条 gen 耗时预算。**它不是网络测试**；网络只在窗口内由 `resolve_base.py` 做。

---

## 0.5 资源纪律（本机真实上限 cgroup 4 核 / 6 GB，nproc 不可信）

- 全链路 Python 设 `OMP_NUM_THREADS=2 / OPENBLAS_NUM_THREADS=2 / MKL_NUM_THREADS=2 / NUMEXPR_NUM_THREADS=2`（脚本内已 `setdefault`，`window_run.sh` 已 export）。
- 本地 lanczos 1080p / verify / 抽帧的 ffmpeg 一律 `-threads 2 -filter_threads 2`（`local_conform.py`、`verify_clip.py`、`frame_sheet.py` 已内置）；本地 CPU 任务**串行、最多 2 路**。
- 窗口内**不做**全片渲染、大编译、全分辨率大数组常驻；`conform_watch` 单进程串行追生成进度（H3 在远端 GPU，不抢本地 GPU）。
- 内存紧张时先停 `conform_watch`（生成更重要），窗口结束后再 `local_conform.py --fill-missing` 补 1080p。

## 1. 工作流变量节点（以实际 `workflows/t2v_api.json` 为准，勿凭记忆）

| 节点 id | class_type | 变量 | 运行时写入 |
| --- | --- | --- | --- |
| `140:131` | MiniMaxH3ImageToVideo | `prompt` / `width` / `height` / `length`（+ 可选 `first_frame`/`last_frame`） | 每镜 prompt、字面量 864×480（hero 1280×736） |
| `140:132` | ComfyMathExpression | `length = max(5, round(a*24)) + (5 - (…%17))%17` | 5.0s → 124 帧（17k+5 网格） |
| `140:133` | PrimitiveFloat | `value` = 时长秒 | 5.0 |
| `140:129` | RandomNoise | `noise_seed` | 每镜 seed |
| `140:139` | PrimitiveBoolean | turbo LoRA 开关 | **true** → 走 `140:135` LoRA + `140:138`=8 步 |
| `140:138` | PrimitiveInt | 8 步 | 固定 8 |
| `140:127` | UNETLoader | `unet_name` | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` |
| `140:128` | CLIPLoader | `clip_name` / `type=minimax` | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` |
| `140:119` / `140:120` | VAELoader ×2 | 视频 VAE / 音频 VAE | 两个都必须加载 |
| `140:130` | CreateVideo | images + audio（H3 原生声） | 124 帧 @24fps |
| `92` | SaveVideo | `filename_prefix` | `video/ep08_H01` … |
| `115` | ResolutionSelector | 被字面量 width/height 覆盖 | 绕过，保证像素精确 |
| `900`/`901`（运行时注入） | LoadImage → ImageScale | FL2VA 首帧 | 上传后文件名 → lanczos 到生成分辨率 |
| `910`/`911`（运行时注入） | LoadImage → ImageScale | 尾帧（可选） | 同上 |

`batch_run.py` 不修改模板结构，只做 deepcopy + 变量字段替换；FL2VA 节点仅在每镜需要时注入。

---

## 2. 窗口执行（Lead 说「窗口开启」后；全程 ≤60 分钟）

```bash
cd /app/vedio/ep08-regen/comfyui
./window_run.sh run            # 或 ./window_run.sh run HH:MM 定时等窗口
```

脚本内部 6 步（每步时间戳写 `comfyui/run.log`）：

1. **入口解析**：`resolve_base.py`（候选 = `H3_BASE` 环境变量 → ep05/ep07 已知端口 → `--base` 追加；每 15s 重试）。
   - 新入口：`export H3_BASE=https://host:port`（凭据仍只走 env），或 `resolve_base.py 600 --base URL`。
2. **能力探测**（`capability_probe.py`，只读 + 一次 64×36 PNG upload smoke）：
   - 节点齐全性、`MiniMaxH3ImageToVideo` 的 `first_frame/last_frame` optional 口 → **FL2VA 可用性**；
   - 5 个模型文件是否在 loader enum（UNET/turbo LoRA/CLIP/视频+音频 VAE）；
   - `/upload/image` 是否接受关键帧上传。
   - 结果写 `assets/h3/capability.json`；**FL2VA 不可用 → 自动 `--mode t2v`，不阻塞窗口**。
3. **批量生成**：`batch_run.py --retries 1 --deadline <now+30min>`；同时后台 `conform_watch_ep08.py` 逐条本地 1080p。
   - 每镜：`[0-2s]/[2-5s]` 分阶段提示词 + seed；FL2VA 优先，失败 1 次后自动 T2V 重试并记录降级；
   - 单任务串行（H3 5s/864×480 显存贴顶，绝不并发两个采样）；
   - 下载后原子写入 `assets/h3/raw/<ID>_raw.mp4`；`deadline` 后的镜头标 `deferred`。
4. **补 1080p**：`local_conform.py --fill-missing`（lanczos + 中心裁切到 1920×1080，保留 H3 原生音轨）。
   - H3 原生 864×480=9:5、1280×736≈1.74，均非严格 16:9 → 统一「cover 缩放 + 中心裁切」（≤2.3%），**不拉伸**。
5. **逐条硬校验**：`verify_clip.py` raw（时长/帧率/解码/非冻结）+ final（1920×1080）；抽 10%/50%/90% 三帧 + 三联图。
   再用 `keyframe_adherence.py` 比对「生成首帧 vs 代码关键帧」灰度相关（FL2VA 是否真从首帧长出来；
   T2V 降级镜相关性低属预期，记录不阻塞）。
6. **报告/清单**：`make_report_ep08.py` → `comfyui/report.md`、`comfyui/report.json`、
   `assets/h3/manifest.json`（逐镜 mode/seed/job/耗时/降级/校验）。
7. **立刻 send_message 给 lead**：逐镜状态、总耗时、降级项、文件路径（不等窗口关闭）。

### 预计耗时（按 ep05/ep07 实测冷/热启动）

| 阶段 | 估计 |
| --- | --- |
| 入口解析 + 登录 + stats + 能力探测 + keyframe 上传 | 2–4 min |
| 24 条 × 5s/864×480/8 步（首条冷启 ~90–110s，其余 T2V ~35–50s / FL2VA ~55–75s） | 15–30 min |
| hero 1280×736（0–2 条） | +2–6 min |
| 本地 1080p（与生成并行，24 条 ~3–6 min CPU） | 0（重叠） |
| 逐条 verify + frames + report | 1–2 min |
| **合计（预算 35 min，硬上限 60 min）** | **约 20–32 min** |

> 时间不够时优先保证 24 条全部有 raw；`--deadline` 兜底顺延（deferred 记录在报告，engine 层自动降级不黑屏）。

### 2.1 主生成完成后的「初版上报」与可选 hero 升级（Lead 已批准）

主生成 + 1080p + verify 完成后 **先** `make_report_ep08.py` 并把「N/24 可用、降级项、路径」发 Lead，
**不要等 hero**。发完初版后，若窗口余量 ≥8 分钟才做 hero 升级（Lead 指定 2-3 条，
优先“真实道路下坡 / 踏板释放 / 仪表负功率”），否则直接收尾：

```bash
IDS="H01,H05,H12"                       # 只用 2-3 条，且已经被 864x480 覆盖过的
python3 batch_run.py --only "$IDS" --force --retries 1 \
    --res H01=1280x736 --res H05=1280x736 --res H12=1280x736
python3 local_conform.py --only "$IDS" --force
python3 verify_clip.py ../assets/h3/H01.mp4 ../assets/h3/H05.mp4 ../assets/h3/H12.mp4 \
    --frames-dir ../assets/h3/frames --expect 1920x1080
python3 make_report_ep08.py             # 更新 hero 行后把终版 report 发 Lead
```

hero 升级失败/超时 → 保留原 864×480 版本（已在 manifest 里），报告标注 hero=fallback-864，不重试第二次。
**任何情况下 24/24 覆盖优先于 hero 清晰度。**

---

## 3. 降级预案（窗口内不纠结，先记录再继续）

| 现象 | 判定 | 动作 |
| --- | --- | --- |
| `resolve_base` 全候选 502/超时 | 例未开机/后端没起 | 报告 Lead，等 boot；脚本每 15s 重试，不重复扣费 |
| 登录 302 → `err=1` | 账号/新凭据未生效 | 报 Lead 要新凭据（走 env/issue），**不猜密码** |
| `first_frame/last_frame` optional 口缺失 | FL2VA 不可用 | 自动 T2V（提示词已含完整场景描述兜底），`capability.json` 记录原因 |
| `LoadImage` 上传失败 | 关键帧不可达 | 该镜自动 T2V 降级；其余照常 |
| 单镜 submit 400（节点参数/模型名不符） | workflow 与实例镜像漂移 | 记录错误 JSON→该镜 T2V 重试 1 次；仍失败标 failed/fallback code |
| 单镜 timeout/无 outputs | 采样异常 | 重试 1 次（同 mode）→ 再失败 T2V → 仍失败标 failed |
| 显存 OOM（日志报 CUDA out of memory） | 分辨率/并发问题 | 确认没有并发第二任务；hero 1280×736 可降 960×544（`--res Hxx=960x544` 重跑该镜） |
| 时间将尽（deadline） | 预算耗尽 | 剩余镜头 deferred；先保证已生成的 1080p+verify+report |
| 1080p 本地转码失败 | ffmpeg 异常 | `local_conform` 会报错；该镜保留 raw，报告标注（engine 层可原生 864×480 兜底） |

**窗口内禁止**：全片渲染、大编译、批量 CPU 重活（会与本地 1080p/verify 抢占）；修改引擎侧文件；git commit/push。

---

### 3.1 窗口内红线画面处置（Lead 指令）

生成后逐条看 `assets/h3/frames/sheets/<ID>_sheet.png`（10%/50%/90% 三帧）与首帧对照：
- **红线**：出现可读文字/数字/UI、品牌 LOGO/徽标、真人正脸或人物剪影 → 该镜 `redline`。
- 处置：`redline` 镜先 `batch_run.py --only <ID> --force --seed <ID>=新seed --retries 0` 重生成 **1 次**；
  仍命中 → 该镜降级为代码层（manifest `status=redline_fallback`，`fallback=code`），**不带病进片**。
- 记录：`report.md` 的「失败/降级」节逐条写镜号、命中项、处置结果；manifest 同步。
- hero 候选镜（H01/H11/H16）红线优先重生成，其余镜以 24/24 覆盖优先。

## 4. 逐条验收口径（H3 层）

- 时长 5s 级（±1s；`verify_clip` 默认 [4.0,6.6]s 硬门槛）、24fps、可完整解码、非冻结（motion 启发式）。
- raw 分辨率 = 请求分辨率（864×480 / hero 1280×736）；final = 1920×1080 / 24fps / H.264 + AAC。
- 抽帧目检（脚本查不出，必须人看）：无乱码文字/数字、无品牌 LOGO、无真人正脸、无穿模；
  能量流/踏板/刹车灯/表针等**物理方向**是否正确（PDF §六：H3 最可能出错处，必须逐帧目检）。
- 不满意 → 改提示词/关键帧后**重开窗口**再生成；不在剪辑上补救（PDF §4.2 回传约定）。
- 声音：只允许环境音/音效；H3 原生音轨进成片时压低到旁白 −12~−18 dB（engine/audio 混音层决定）。

---

## 5. 交接产物（窗口后立即同步）

| 产物 | 路径 |
| --- | --- |
| 1080p 素材 | `assets/h3/H01.mp4 …`（1920×1080/24fps/H.264+AAC） |
| 原始素材 | `assets/h3/raw/<ID>_raw.mp4` |
| 清单 | `assets/h3/manifest.json`（逐镜 mode/seed/job/耗时/降级/final_res/verify） |
| 能力探测 | `assets/h3/capability.json`、`node_probe_raw.json` |
| 校验 | `assets/h3/verify-raw.json`、`verify-final.json`、`frames/`、`frames/sheets/` |
| 报告 | `comfyui/report.md`、`comfyui/report.json` |
| 复现 | `comfyui/run.log` + 本 runbook + `prompts-ep08.md` |

仓库同步范围（**不 commit**，Lead 统一提交）：`视频制作/ep08-regen/comfyui/`（脚本/文档/提示词/报告；
素材与大产物不入库）。`assets/h3/` 只在生产目录。

---

## 6. 故障排查速查

```bash
# 登录（不打印凭据）
set -a; . /home/admin/.h3.env; set +a
python3 tools/comfy_client.py login          # 仅验证门禁
python3 tools/comfy_client.py stats          # 显卡/版本
python3 tools/comfy_client.py nodes --grep MiniMax | head
python3 tools/comfy_client.py queue          # 是否还有排队任务
# 单镜重跑（改 seed / 重试 / 换分辨率）
python3 batch_run.py --only H07 --force --seed H07=202611160907 --retries 1
python3 batch_run.py --only H07 --res H07=960x544 --force
# 单独重做 1080p / 校验
python3 local_conform.py --only H07 --force
python3 verify_clip.py ../assets/h3/H07.mp4 --frames-dir ../assets/h3/frames --expect 1920x1080
```

> 任何新入口/凭据只经 Lead 通过 env/issue 下发；本 runbook 与仓库内不出现任何口令。
