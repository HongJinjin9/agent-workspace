# 第 06 期 · ComfyUI H3 出片报告（C1–C14）

> 名义时间窗（租用）：2026-11-13T04:40:00Z/05:40:00Z。**实际生成窗口：2026-11-13T05:04:27Z/05:13:42Z**。本次日志覆盖 2026-11-13T05:04:28Z → 2026-11-13T05:13:42Z（UTC）。
> 机器：优云智算 ComfyUI H3 视频版 / RTX 5090 32GB / ComfyUI 0.36.0；MiniMax H3 int8（`minimax_h3_fl2va_pruned_int8_convrot`）+ 8 步 turbo LoRA。
> 入口 `https://wp08.unicorn.org.cn:22815`（WyfGate 门禁）。凭据只走环境变量，未写入任何仓库文件。

## 1. 结果总览

- 交付：`assets/comfy/c1.mp4` … `c14.mp4`（1920×1080 / 24fps / H.264 yuv420p + AAC 音轨，约 5.18s）
- 原始产物：`assets/comfy/raw/cN_raw.mp4`（c1 864×480; c2 864×480; c3 864×480; c4 864×480; c5 864×480; c6 864×480; c7 864×480; c8 864×480; c9 864×480; c10 864×480; c11 864×480; c12 864×480; c13 864×480; c14 864×480）
- app 4x-UltraSharp 超分：无
- 本地 ffmpeg lanczos 1080p：c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11, c12, c13, c14（详见 §2 表）
- 生成采样累计耗时（各片 elapsed 之和）：549s；日志事件 108 条

## 2. 逐镜清单

| 镜头 | 内容 | 生成分辨率 | 时长 | 生成耗时 | job id | 1080p 方法 | 最终分辨率 | 原始校验 | 成片校验 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c1 | Wide symmetric two silhouettes at long conference table | 864×480 | 5.0s | 111.8 | b069a7b3-2424-46a2-ac98-cff7b8c17590 | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c2 | Middle-aged man side silhouette flipping old manual | 864×480 | 5.0s | 32.1 | 780d9cad-c687-43c9-bd73-cb4903907780 | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c3 | Man's hands stamping a document, red mark lands | 864×480 | 5.0s | 33.8 | 74671da1-ba69-47a6-b39c-e9999856400f | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c4 | Young woman looking down at tablet/ledger, screen glow | 864×480 | 5.0s | 33.8 | 0f65f288-36db-4f21-b616-c3ea25ac0c74 | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c5 | Woman's hands pushing ledger across the table | 864×480 | 5.0s | 33.8 | 85650daf-4eb4-4945-b5c8-478d9265018e | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c6 | Macro thick manual pages flipping and bending | 864×480 | 5.0s | 33.9 | 34922280-1f8c-4242-baeb-a12fa23fdbf4 | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c7 | Over-shoulder two-shot at table, distance closer | 864×480 | 5.0s | 32.0 | 74106880-fad5-42f8-89cf-76817d3cabec | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c8 | Woman's finger tapping tablet, abstract numbers glow | 864×480 | 5.0s | 33.8 | 41362fed-9871-4d6f-9d7f-afbcaf68cae3 | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c9 | Man's hand underlining a line in manual with pen | 864×480 | 5.0s | 33.8 | 0869ff00-1b91-4e7c-ab9d-7ebe41e5f370 | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c10 | Red round stamp mark on paper, macro | 864×480 | 5.0s | 33.9 | 10ed5b2c-518c-442e-a845-0834cb647db2 | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c11 | New blank manual/notebook on dark table, side light, dust | 864×480 | 5.0s | 33.8 | 3e92aa27-c427-40fc-ba61-76c4ec5921d0 | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c12 | Old ledger close-up with column rules and pen | 864×480 | 5.0s | 33.8 | 71fc2407-2010-4aac-b475-9bdeaad00265 | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c13 | Empty conference room at dusk, city window, cold light | 864×480 | 5.0s | 33.8 | fc16535d-c485-4946-b8e3-faa29b5722f5 | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |
| c14 | Man's back view closing manual, leaning back, backlit | 864×480 | 5.0s | 35.2 | 0f0f7510-29d1-4c42-be0c-b2ed7ba90d04 | local-ffmpeg-lanczos 1920x1080 | 1920×1080 | PASS | PASS |

## 3. 窗口时间线（自动提取自 comfyui/run.log）

```text
2026-11-13T05:04:28Z  login OK (wyfgate cookie obtained)
2026-11-13T05:04:30Z  login OK (wyfgate cookie obtained)
2026-11-13T05:04:30Z  c1: submit attempt 1/2 (864x480, 5.0s, seed=202611130101)
2026-11-13T05:04:30Z  c1: prompt_id=b069a7b3-2424-46a2-ac98-cff7b8c17590
2026-11-13T05:06:22Z  c1: saved c1_raw.mp4 (0.26 MB) in 111.8s
2026-11-13T05:06:22Z  c2: submit attempt 1/2 (864x480, 5.0s, seed=202611130102)
2026-11-13T05:06:22Z  c2: prompt_id=780d9cad-c687-43c9-bd73-cb4903907780
2026-11-13T05:06:54Z  c2: saved c2_raw.mp4 (0.34 MB) in 32.1s
2026-11-13T05:06:54Z  c3: submit attempt 1/2 (864x480, 5.0s, seed=202611130103)
2026-11-13T05:06:55Z  c3: prompt_id=74671da1-ba69-47a6-b39c-e9999856400f
2026-11-13T05:07:28Z  c3: saved c3_raw.mp4 (0.38 MB) in 33.8s
2026-11-13T05:07:28Z  c4: submit attempt 1/2 (864x480, 5.0s, seed=202611130104)
2026-11-13T05:07:29Z  c4: prompt_id=0f65f288-36db-4f21-b616-c3ea25ac0c74
2026-11-13T05:08:02Z  c4: saved c4_raw.mp4 (0.51 MB) in 33.8s
2026-11-13T05:08:02Z  c5: submit attempt 1/2 (864x480, 5.0s, seed=202611130105)
2026-11-13T05:08:03Z  c5: prompt_id=85650daf-4eb4-4945-b5c8-478d9265018e
2026-11-13T05:08:36Z  c5: saved c5_raw.mp4 (0.35 MB) in 33.8s
2026-11-13T05:08:36Z  c6: submit attempt 1/2 (864x480, 5.0s, seed=202611130106)
2026-11-13T05:08:37Z  c6: prompt_id=34922280-1f8c-4242-baeb-a12fa23fdbf4
2026-11-13T05:09:11Z  c6: saved c6_raw.mp4 (0.44 MB) in 33.9s
2026-11-13T05:09:11Z  c7: submit attempt 1/2 (864x480, 5.0s, seed=202611130107)
2026-11-13T05:09:11Z  c7: prompt_id=74106880-fad5-42f8-89cf-76817d3cabec
2026-11-13T05:09:43Z  c7: saved c7_raw.mp4 (0.27 MB) in 32.0s
2026-11-13T05:09:43Z  c8: submit attempt 1/2 (864x480, 5.0s, seed=202611130108)
2026-11-13T05:09:43Z  c8: prompt_id=41362fed-9871-4d6f-9d7f-afbcaf68cae3
2026-11-13T05:10:17Z  c8: saved c8_raw.mp4 (0.35 MB) in 33.8s
2026-11-13T05:10:17Z  c9: submit attempt 1/2 (864x480, 5.0s, seed=202611130109)
2026-11-13T05:10:17Z  c9: prompt_id=0869ff00-1b91-4e7c-ab9d-7ebe41e5f370
2026-11-13T05:10:51Z  c9: saved c9_raw.mp4 (0.40 MB) in 33.8s
2026-11-13T05:10:51Z  c10: submit attempt 1/2 (864x480, 5.0s, seed=202611130110)
2026-11-13T05:10:51Z  c10: prompt_id=10ed5b2c-518c-442e-a845-0834cb647db2
2026-11-13T05:11:25Z  c10: saved c10_raw.mp4 (0.34 MB) in 33.9s
2026-11-13T05:11:25Z  c11: submit attempt 1/2 (864x480, 5.0s, seed=202611130111)
2026-11-13T05:11:25Z  c11: prompt_id=3e92aa27-c427-40fc-ba61-76c4ec5921d0
2026-11-13T05:11:59Z  c11: saved c11_raw.mp4 (0.27 MB) in 33.8s
2026-11-13T05:11:59Z  c12: submit attempt 1/2 (864x480, 5.0s, seed=202611130112)
2026-11-13T05:11:59Z  c12: prompt_id=71fc2407-2010-4aac-b475-9bdeaad00265
2026-11-13T05:12:33Z  c12: saved c12_raw.mp4 (0.35 MB) in 33.8s
2026-11-13T05:12:33Z  c13: submit attempt 1/2 (864x480, 5.0s, seed=202611130113)
2026-11-13T05:12:33Z  c13: prompt_id=fc16535d-c485-4946-b8e3-faa29b5722f5
2026-11-13T05:13:07Z  c13: saved c13_raw.mp4 (0.33 MB) in 33.8s
2026-11-13T05:13:07Z  c14: submit attempt 1/2 (864x480, 5.0s, seed=202611130114)
2026-11-13T05:13:07Z  c14: prompt_id=0f0f7510-29d1-4c42-be0c-b2ed7ba90d04
2026-11-13T05:13:42Z  c14: saved c14_raw.mp4 (0.36 MB) in 35.2s
2026-11-13T05:13:42Z  batch done in 552.3s: 14/14 ok
```

## 4. 提示词与工作流

- 提示词全文：`comfyui/prompts-ep06.md`（机器可读 `comfyui/shots-ep06.json`）；写法 = `integrated_multimodal_description` + `overall_soundscape` + `non_diegetic_music`。
- 工作流：`comfyui/workflows/t2v_api.json`；改 prompt/宽高 `140:131`、时长 `140:133`、seed `140:129`、8 步 turbo 开关 `140:139`、输出前缀 `92`。
- 超分工作流：`comfyui/upscale_all.py` 内联图（LoadVideo→4x-UltraSharp→lanczos 1920×1080→CreateVideo 带音轨）。
- 审片：`comfyui/verify_clip.py`（ffmpeg 探针 + 10/50/90% 抽帧 + 帧差运动量），抽帧在 `assets/comfy/frames/`。

## 5. 失败与处理

**窗口状态**：窗口异常但最终完成：名义窗口 2026-11-13 04:40–05:40 UTC（北京 12:40–13:40，计时收费 1 小时）。04:40:00–05:03Z 旧入口 https://wp08.unicorn.org.cn:24909 不可达（ConnectionError / 60s ConnectTimeout 交替，TLS 从未完成、零 HTTP 响应；始终无 302→/login?err=1，非账号密码问题）；机器于 12:48 北京重启并更换入口，新入口 https://wp08.unicorn.org.cn:22815 于 05:04:28Z 登录成功（ComfyUI 0.36.0 / RTX 5090 33.7GB），05:04:30Z 开始生成，05:13:42Z 完成 C1–C14 全部 14 条（C1 冷启动 111.8s，C2–C14 热采样 32.0–35.2s/条），05:15:24Z 前全部本地 ffmpeg lanczos 升到 1920×1080（保留 H3 原生音轨）。实际占用约 9 分钟机器时间；此后未再提交任务。角色均为 AI 虚构形象：镜头仅侧影/过肩/手部/背影，无清晰正脸、无真实人物相似性、无 logo、无可读文字。

- 采样：无 job 级失败。
- 超分：无失败。

## 6. 环境与已知限制

- 本机没有真 ffprobe（`/home/admin/.local/bin/ffprobe` 实为 ffmpeg 的软链），校验用 `ffmpeg -i` stderr + OpenCV 交叉核对（分辨率/帧率/时长/编码/音轨/帧数），等效于 ffprobe 必查项；`verify_clip.py` 的 3 帧目检由 operator 人工完成。
- H3 原生输出 24fps、约 5.167s（124 帧）；成片按 5s 左右 in/out 使用。
- 提示词已避开文字/公司标识/人脸；抽帧核查后如有残留文字，需后期遮挡（见 §5）。
- MiniMax H3 商用需确认 Comfy 商业许可（README §六）；成片需 AI 声明（SPEC §4）。


## 7. 目检与验收（人工抽帧，2026-11-13T05:19Z 完成）

每条片抽 10%/50%/90% 三帧（`assets/comfy/frames/cN_p10/p50/p90.png`），并生成 14 宫中景联系表
`assets/comfy/frames/contact-sheet-14.jpg` 逐条目检（顺序 c1→c14，4×4）：

| 镜头 | 目检结论 |
| --- | --- |
| C1 长桌两端剪影 | ✅ 对称构图、两剪影对坐、逆光冷灰+暖金台灯，桌面手册/账本可见，符合冷开场 |
| C2 男性侧影翻手册 | ✅ 深灰西装、卷袖、侧影低头翻旧手册，台灯暖光，无正脸 |
| C3 男性双手盖章 | ✅ 手部微距、木印章压下，暖光侧逆、浅景深 |
| C4 女性低头看平板/账本 | ✅ 浅色便装、头发松散、侧脸朝向屏幕、屏幕微光，侧影非正脸（见备注） |
| C5 女性双手推账本 | ✅ 手部微距、账本在桌面推移，浅景深 |
| C6 厚手册翻页微距 | ✅ 厚纸页翻动弯曲、暖光、尘埃，书页文字虚化不可读 |
| C7 过肩两人中景 | ✅ 侧后双人、过肩构图、间距更近，桌灯 |
| C8 手指点平板 | ✅ 指尖微距、屏幕冷光、抽象光斑（不可读），符合后期叠数字的底 |
| C9 笔划线微距 | ✅ 金属笔尖划出细线、暖光、浅景深 |
| C10 红印特写 | ✅ 圆形红印落在纸面、纸纤维与侧光，印内无文字（见备注） |
| C11 空白新手册 | ✅ 深色封面上桌、侧光、尘埃，无标题无 logo |
| C12 旧账本+钢笔 | ✅ 泛黄账页、栏格、钢笔搁页，浅景深 |
| C13 黄昏空会议室 | ✅ 长桌空椅、落地窗外城市、冷光+单盏台灯、无人 |
| C14 男性背影合手册 | ✅ 背影中景、逆光肩线、合上手册靠回椅背，无脸 |

- 机器校验 **14/14 PASS**：1920×1080 / 24fps / 5.18s / H.264 yuv420p + AAC；非冻结（运动量最低 c7=0.31、c1=0.39、c11=0.47，均为刻意的静场/慢镜，非死帧）；详情 `assets/comfy/verify-final.json`、`verify-raw.json`。
- 备注（合规复核）：C4 为女性侧脸朝向屏幕（非正脸，符合“侧影”约定；如成片镜头更近可再加虚化）；C10 纸面有虚化排版文字但不可读；所有镜头无 logo/公司名/工牌/车牌、无清晰正脸、不指向真实人物。成片仍需按 SPEC §4 双声明（虚构人物 + AI 辅助制作）。

## 8. 复现 / 重跑步骤（实测总计约 9 分钟机器时间）

```bash
export H3_USER=…  H3_PASS=…  H3_BASE=https://…   # 凭据/入口只走环境变量，绝不入库
cd /app/vedio/ep06-dialogue/comfyui
python3 batch_run.py --stats --shots shots-ep06.json       # 登录 + /system_stats + 节点检查
python3 conform_watch.py 1800 &                            # 并行：每条 raw 落地即本地 1080p
python3 batch_run.py --only c1,c2,c3,c4,c5,c6,c7,c8,c9,c10,c11,c12,c13,c14         --shots shots-ep06.json --prefix video/ep06_ --retries 1
python3 upscale_all.py --shots shots-ep06.json --local-ids c1,…,c14 --deadline 23:59   # 兜底全量本地 conform
python3 verify_clip.py ../assets/comfy/c*.mp4 --frames-dir ../assets/comfy/frames --expect 1920x1080 \
        > ../assets/comfy/verify-final.json
python3 finalize_manifest.py && python3 make_report.py
```

实测（2026-11-13 本实例，864×480 / 5s / 8 步 turbo）：冷启动 C1 111.8s（含模型加载），热采样 C2–C14 32.0–35.2s/条，14 条批量 552.3s；本地 ffmpeg lanczos 1080p 单条约 9–25s（与 GPU 采样并行时 15–25s）。若要更高质量且窗口宽裕：生成后跑 `python3 upscale_all.py --local-ids "" --force --deadline …`（app 4x-UltraSharp，约 103–106s/条）。

## 9. 交付与物料

- 成片（进时间轴）：`assets/comfy/c1.mp4` … `c14.mp4`（1920×1080 / 24fps / 5.18s / H.264+AAC）
- 原始母版：`assets/comfy/raw/cN_raw.mp4`（864×480，H3 原生音轨）
- 清单：`assets/comfy/manifest.json`（generated:true，14/14；逐镜 prompt/seed/job id/耗时/upscale_method/engine/verify）
- 提示词：`comfyui/prompts-ep06.md`（机器可读 `comfyui/shots-ep06.json`）
- 抽帧/联系表：`assets/comfy/frames/`（`contact-sheet-14.jpg` 为 14 宫中景）
- **App 使用结束**：最后一条任务 05:13:42Z 完成，05:15:24Z 全部本地转码结束；此后未再提交任何任务，实例可关闭以停止计费。
