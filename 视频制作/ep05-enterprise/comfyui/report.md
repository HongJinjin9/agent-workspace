# 第 05 期 · ComfyUI H3 出片报告（C1–C8）

> 名义时间窗（租用）：2026-11-12 13:50–14:50 UTC（北京 21:50–22:50，按分钟计费）。**实际生成窗口：2026-11-12T14:28:08Z/14:33:13Z**（入口在 13:50–14:27Z 期间不可达，14:27:12Z 门禁上线、14:28:08Z 后端就绪）。本次日志覆盖 2026-11-12T14:28:08Z → 2026-11-12T14:49:54Z（UTC）。
> 机器：优云智算 ComfyUI H3 视频版 / RTX 5090 32GB / ComfyUI 0.36.0；MiniMax H3 int8（`minimax_h3_fl2va_pruned_int8_convrot`）+ 8 步 turbo LoRA。
> 入口 `https://wp08.unicorn.org.cn:24909`（WyfGate 门禁）。凭据只走环境变量，未写入任何仓库文件。

## 1. 结果总览

- 交付：`assets/comfy/c1.mp4` … `c8.mp4`（1920×1080 / 24fps / H.264 yuv420p / AAC 48k，约 5.17s）
- 原始产物：`assets/comfy/raw/cN_raw.mp4`（c1 864×480; c2 864×480; c3 864×480; c4 864×480; c5 864×480; c6 864×480; c7 864×480; c8 864×480）
- app 4x-UltraSharp 超分：c1, c2, c3, c4, c5, c6, c7, c8
- 本地 ffmpeg/原生回退：无（详见 §2 表）
- 生成采样累计耗时（各片 elapsed 之和）：332s；日志事件 106 条

## 2. 逐镜清单

| 镜头 | 内容 | 生成分辨率 | 时长 | 生成耗时 | job id | 1080p 方法 | 最终分辨率 | 原始校验 | 成片校验 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c1 | Corridor slow push-in, folder handed along | 864×480 | 5.0s | 97.0 | 0fe514bf-092e-46e2-ad6e-c688e8e535bb | app:4x-UltraSharp+lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c2 | Hands passing a document folder, close-up | 864×480 | 5.0s | 31.7 | fe9d24bf-a3b7-4cf8-983b-fff62d5a6540 | app:4x-UltraSharp+lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c3 | Rubber stamp pressing onto paper, red mark lands | 864×480 | 5.0s | 35.5 | fe64a914-a476-46fe-81a0-5dbd613fdc9a | app:4x-UltraSharp+lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c4 | Elevator doors slide open, floor buttons light up | 864×480 | 5.0s | 37.6 | f3816933-39ef-487a-b0c3-530bb02f620a | app:4x-UltraSharp+lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c5 | Looking up through a high-rise atrium, stacked floors | 864×480 | 5.0s | 33.6 | 5f99558d-b879-463e-8506-9169b9342511 | app:4x-UltraSharp+lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c6 | Top-down meeting table, papers and hands, no faces | 864×480 | 5.0s | 33.5 | 120836c5-775b-48c8-af33-fd938e381cd4 | app:4x-UltraSharp+lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c7 | Empty office corridor, lights switch on row by row | 864×480 | 5.0s | 31.4 | d2b9d49b-14b7-4933-87f5-cb14bfae1c33 | app:4x-UltraSharp+lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c8 | Venetian-blind grid of dusk light on wall and papers | 864×480 | 5.0s | 31.4 | 57c1b058-e6ff-4028-90a5-fc0047ade3aa | app:4x-UltraSharp+lanczos 1920x1080 | 1920×1080 | PASS | PASS |

## 3. 窗口时间线（自动提取自 comfyui/run.log）

```text
2026-11-12T14:28:08Z  login OK (wyfgate cookie obtained)
2026-11-12T14:28:10Z  login OK (wyfgate cookie obtained)
2026-11-12T14:28:10Z  c1: submit attempt 1/2 (864x480, 5.0s, seed=202611120501)
2026-11-12T14:28:10Z  c1: prompt_id=0fe514bf-092e-46e2-ad6e-c688e8e535bb
2026-11-12T14:29:47Z  c1: saved c1_raw.mp4 (0.54 MB) in 97.0s
2026-11-12T14:29:47Z  c2: submit attempt 1/2 (864x480, 5.0s, seed=202611120502)
2026-11-12T14:29:47Z  c2: prompt_id=fe9d24bf-a3b7-4cf8-983b-fff62d5a6540
2026-11-12T14:30:19Z  c2: saved c2_raw.mp4 (0.38 MB) in 31.7s
2026-11-12T14:30:19Z  c3: submit attempt 1/2 (864x480, 5.0s, seed=202611120503)
2026-11-12T14:30:19Z  c3: prompt_id=fe64a914-a476-46fe-81a0-5dbd613fdc9a
2026-11-12T14:30:55Z  c3: saved c3_raw.mp4 (0.39 MB) in 35.5s
2026-11-12T14:30:55Z  c4: submit attempt 1/2 (864x480, 5.0s, seed=202611120504)
2026-11-12T14:30:55Z  c4: prompt_id=f3816933-39ef-487a-b0c3-530bb02f620a
2026-11-12T14:31:33Z  c4: saved c4_raw.mp4 (0.27 MB) in 37.6s
2026-11-12T14:31:33Z  c5: submit attempt 1/2 (864x480, 5.0s, seed=202611120505)
2026-11-12T14:31:33Z  c5: prompt_id=5f99558d-b879-463e-8506-9169b9342511
2026-11-12T14:32:07Z  c5: saved c5_raw.mp4 (0.61 MB) in 33.6s
2026-11-12T14:32:07Z  c6: submit attempt 1/2 (864x480, 5.0s, seed=202611120506)
2026-11-12T14:32:07Z  c6: prompt_id=120836c5-775b-48c8-af33-fd938e381cd4
2026-11-12T14:32:40Z  c6: saved c6_raw.mp4 (0.53 MB) in 33.5s
2026-11-12T14:32:40Z  batch done in 270.3s: 6/6 ok
2026-11-12T14:32:41Z  login OK (wyfgate cookie obtained)
2026-11-12T14:32:41Z  c7: submit attempt 1/2 (864x480, 5.0s, seed=202611120507)
2026-11-12T14:32:41Z  c7: prompt_id=d2b9d49b-14b7-4933-87f5-cb14bfae1c33
2026-11-12T14:33:13Z  c7: saved c7_raw.mp4 (0.38 MB) in 31.4s
2026-11-12T14:33:13Z  c8: submit attempt 1/2 (864x480, 5.0s, seed=202611120508)
2026-11-12T14:33:13Z  c8: prompt_id=57c1b058-e6ff-4028-90a5-fc0047ade3aa
2026-11-12T14:33:44Z  c8: saved c8_raw.mp4 (0.36 MB) in 31.4s
2026-11-12T14:33:44Z  batch done in 63.2s: 2/2 ok
2026-11-12T14:34:19Z  c8: LOCAL hero conform FAILED in 34.5s -> c8.mp4 (NonexNone)
2026-11-12T14:36:00Z  c1: upscale submitted (0.5 MB -> 1920x1080, model=4x-UltraSharp.pth) prompt_id=2cba238b-00d9-4c99-a876-4fdfdc1cdee1
2026-11-12T14:37:48Z  c1: upsale done in 105.9s -> c1.mp4 (1.76 MB, 1920x1080, 5.17s)
2026-11-12T14:37:48Z  c4: upscale submitted (0.3 MB -> 1920x1080, model=4x-UltraSharp.pth) prompt_id=564fe258-5fc6-431c-b2e1-e7a14f05ab06
2026-11-12T14:39:31Z  c4: upsale done in 103.0s -> c4.mp4 (0.89 MB, 1920x1080, 5.17s)
2026-11-12T14:39:31Z  c5: upscale submitted (0.6 MB -> 1920x1080, model=4x-UltraSharp.pth) prompt_id=18d551ba-a2f0-4007-a68f-c9a7063b8a50
2026-11-12T14:41:14Z  c5: upsale done in 102.8s -> c5.mp4 (2.53 MB, 1920x1080, 5.17s)
2026-11-12T14:41:14Z  c3: upscale submitted (0.4 MB -> 1920x1080, model=4x-UltraSharp.pth) prompt_id=73315eb4-3f41-436e-ace0-50ec37bf9261
2026-11-12T14:42:57Z  c3: upsale done in 102.8s -> c3.mp4 (1.49 MB, 1920x1080, 5.17s)
2026-11-12T14:42:58Z  c2: upscale submitted (0.4 MB -> 1920x1080, model=4x-UltraSharp.pth) prompt_id=f7b74d39-c114-4a9a-8ec3-660e6790e023
2026-11-12T14:44:41Z  c2: upsale done in 103.3s -> c2.mp4 (1.16 MB, 1920x1080, 5.17s)
2026-11-12T14:44:42Z  c6: upscale submitted (0.5 MB -> 1920x1080, model=4x-UltraSharp.pth) prompt_id=b328844d-7c97-439c-a980-25607c0da458
2026-11-12T14:46:25Z  c6: upsale done in 103.3s -> c6.mp4 (2.05 MB, 1920x1080, 5.17s)
2026-11-12T14:46:25Z  c7: upscale submitted (0.4 MB -> 1920x1080, model=4x-UltraSharp.pth) prompt_id=c1e29433-0f05-4296-9ec1-3026d11ac52e
2026-11-12T14:48:08Z  c7: upsale done in 102.9s -> c7.mp4 (1.50 MB, 1920x1080, 5.17s)
2026-11-12T14:48:08Z  c8: upscale submitted (0.4 MB -> 1920x1080, model=4x-UltraSharp.pth) prompt_id=a1bb9f3e-575c-47e0-8ec9-5c9d5ea8e68c
2026-11-12T14:49:54Z  c8: upsale done in 106.0s -> c8.mp4 (1.20 MB, 1920x1080, 5.17s)
```

> 注：时间线中 14:34:19Z 的 “c8 LOCAL hero conform FAILED” 是 emergency 脚本的重复本地转码与 conform_watch 并发写同一 tmp 文件造成的无害竞争；c8 已由 conform_watch 正确生成并通过校验，随后在 14:49:54Z 被 app 4x-UltraSharp 版替换，不影响交付。

## 4. 提示词与工作流

- 提示词全文：`comfyui/prompts-ep05.md`（机器可读 `comfyui/shots-ep05.json`）；写法 = `integrated_multimodal_description` + `overall_soundscape` + `non_diegetic_music`。
- 工作流：`comfyui/workflows/t2v_api.json`；改 prompt/宽高 `140:131`、时长 `140:133`、seed `140:129`、8 步 turbo 开关 `140:139`、输出前缀 `92`。
- 超分工作流：`comfyui/upscale_all.py` 内联图（LoadVideo→4x-UltraSharp→lanczos 1920×1080→CreateVideo 带音轨）。
- 审片：`comfyui/verify_clip.py`（ffmpeg 探针 + 10/50/90% 抽帧 + 帧差运动量），抽帧在 `assets/comfy/frames/`。

## 5. 失败与处理

**窗口状态**：窗口异常/延迟开机：租用实例在 21:50（13:50Z）窗口开启时仍未开机——13:14Z 起对 https://wp08.unicorn.org.cn:24909 的探测持续为 TLS EOF（TCP 24909 可连、TLS ClientHello 后即断，无任何 HTTP 响应），持续到 14:27Z（约 45 次 login 轮询，每 15–45s 一次；期间从未出现 302→/login?err=1，证明不是账号密码问题）。14:27:12Z 门禁上线并接受登录（credentials OK），但后端 ComfyUI 仍在启动（/system_stats 返回 502）；14:28:08Z 后端就绪（ComfyUI 0.36.0 / RTX 5090 33.7GB）。随后在压缩后的窗口内完成 C1–C8 全部 8 条生成（14:28:10–14:33:44Z）与本地 1080p 初版交付，并在 14:36:00–14:49:54Z 将 8/8 成片全部替换为 app 4x-UltraSharp 超分版；所有 raws 均在 14:33:44Z 完成下载。机器按分钟计费，本次实际生成+超分占用约 23 分钟机器时间；最后一条任务 14:49:54Z 完成后即保持 idle，未再提交任务。

- 采样：无 job 级失败。
- 超分：无失败。

## 6. 环境与已知限制

- 本机没有真 ffprobe（`/home/admin/.local/bin/ffprobe` 实为 ffmpeg 的软链），校验用 `ffmpeg -i` stderr + OpenCV 交叉核对（分辨率/帧率/时长/编码/音轨/帧数），等效于 ffprobe 必查项；`verify_clip.py` 的 3 帧目检由 operator 人工完成。
- H3 原生输出 24fps、约 5.167s（124 帧）；成片按 5s 左右 in/out 使用。
- 提示词已避开文字/公司标识/人脸；抽帧核查后如有残留文字，需后期遮挡（见 §5）。
- MiniMax H3 商用需确认 Comfy 商业许可（README §六）；成片需 AI 声明（SPEC §4）。

## 7. 目检与验收（人工抽帧，2026-11-12T14:50Z 完成）

每条片抽 10%/50%/90% 三帧（`assets/comfy/frames/cN_p10/p50/p90.png`），拼成三帧对照图
（`assets/comfy/frames/sheets/cN_sheet.png`）逐条目检：

| 镜头 | 目检结论 | 备注 |
| --- | --- | --- |
| c1 走廊递文件 | ✅ 内容正确：走廊纵深 + 前景手递文件夹 + 缓慢推进，背景职员浅景深虚化 | 无清晰正脸/工牌/文字；人物仅作空间纵深 |
| c2 递文件特写 | ✅ 双手交递文件夹，暖台灯 + 冷窗光 | 无脸、无字 |
| c3 盖章 | ✅ 印章压下 → 抬起 → 纸面留下红色椭圆印迹 | 印迹内无可读字符；macro 质感符合 |
| c4 电梯 | ✅ 双门滑开、轿厢亮起、按钮橙色依次点亮 | 按钮上有极小楼层数字（成片 2.35 遮幅+景深下不可读）；如需绝对干净可后期遮挡 |
| c5 中庭仰拍 | ✅ 楼层层叠、缓慢仰摇，光比与 teal-orange 符合 | 无人物 |
| c6 桌面俯拍 | ✅ 顶视会议桌、纸张与手、投影阴影 | 纸面细纹不可读；无脸 |
| c7 空走廊 | ✅ 顶灯一格格亮起、无人、一点透视 | 与 s5a「人走空」语义相符 |
| c8 百叶窗光 | ✅ 网格暖光在墙面/纸张上移动，黄昏色温准确 | 无字 |

- 机器校验 **8/8 PASS**：1920×1080 / 24fps / 5.17s / H.264 yuv420p + AAC；非冻结；详情见
  `assets/comfy/verify-raw.json`、`assets/comfy/verify-final.json`。
- 合规：无公司名/logo/工牌/车牌，无清晰人脸；成片仍需按 SPEC §4 做 AI 声明，商用许可按 README §六 确认。

## 8. 复现 / 下次窗口重跑步骤（实测总计约 23 分钟机器时间）

```bash
export H3_USER=…  H3_PASS=…            # 凭据只走环境变量，绝不入库
cd /app/vedio/ep05-enterprise/comfyui
python3 batch_run.py --stats                              # 登录 + /system_stats + 节点检查（内置 APP DOWN / LOGIN REJECTED 分类）
python3 batch_run.py --only c1 --retries 1                # 冷启动 97.0s（含模型加载）
python3 batch_run.py --only c2,c3,c4,c5,c6 --retries 1    # 热采样 31.4–37.6s/条
python3 batch_run.py --only c7,c8 --retries 1
python3 upscale_all.py --local-ids "" --force --deadline 15:00   # app 4x-UltraSharp→1080p，102.8–106.0s/条
python3 verify_clip.py ../assets/comfy/c?.mp4 --frames-dir ../assets/comfy/frames --expect 1920x1080 \
    > ../assets/comfy/verify-final.json
python3 finalize_manifest.py && python3 make_report.py
```

实测耗时（2026-11-12 本实例）：冷启动 97.0s；热采样 31.4–37.6s/条；4x-UltraSharp 超分 102.8–106.0s/条；
1280×736 hero 预估 ~220s/条（本次因窗口被压缩未启用，C1/C3 亦按 864×480 生成）。8 条生成 ≈ 9 分钟（含冷启动），
8 条超分 ≈ 14 分钟，合计 ≈ 23 分钟。若下次窗口正常，可把 hero 提到 1280×736 并用 `--res c1=1280x736 --res c3=1280x736`。

## 9. 交付与物料

- 成片（进时间轴）：`assets/comfy/c1.mp4` … `c8.mp4`（1920×1080/24fps/≈5.17s/H.264+AAC）
- 原始 768p 级母版：`assets/comfy/raw/cN_raw.mp4`（864×480）
- 清单：`assets/comfy/manifest.json`（逐镜：prompt/seed/job id/耗时/超分方法/校验）
- 提示词：`comfyui/prompts-ep05.md`（机器可读 `comfyui/shots-ep05.json`）
- 抽帧与对照图：`assets/comfy/frames/`（`sheets/` 为每镜三帧对照）
- **App 使用结束**：最后一条任务 14:49:54Z 完成；此后保持 idle，未再提交任何任务，避免继续计费。
