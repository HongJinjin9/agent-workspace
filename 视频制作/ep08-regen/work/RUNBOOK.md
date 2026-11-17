# EP08 成片导出/验收 Runbook（交付 owner: delivery-engineer）

前置（缺一不可）：
1. engine-dev 报「渲染入口就绪 + 时间轴冻结」；`work/timeline.json`、`work/shots.json` 可读。
2. `audio/work/audio.m4a` 母带有效（I=-14±0.5 LUFS / TP≤-1.0），`work/srt/all.srt` 句级字幕到位。
3. `assets/h3/H01..H24.mp4` 到位（或 Lead 明确接受降级），`comfyui/report.md` 已写。
4. Lead 通知「可以全片渲染」（H3 窗口内不做 CPU 重活）。

资源纪律（Lead 2026-11-16 裁决，实测校准）：
- 本机 `nproc=128` 是**宿主核数**；本容器 cgroup 实际 **cpu.max=4 核 / memory.max=6GB**
  （`cat /sys/fs/cgroup/cpu.max` = `400000 100000`，`memory.max` = 6442450944）。
  已有 OOM kill 记录，`-threads 0` 必被 kill。
- 所有 ffmpeg 统一 `-threads 2`（解码/滤镜），x264 最多 `-threads 4`；Python 侧
  `OMP_NUM_THREADS=2` / `OPENBLAS_NUM_THREADS=2` / `MKL_NUM_THREADS=2`，不开多进程 >2。
- 实测 finalize 滤镜链约 8–12 fps（4 分钟成片 master 编码约 10–15 分钟）；H3 窗口内
  **不做全片渲染/编码**（只做轻量准备），窗口结束且 Lead 通知后再跑。
- **同一时刻只允许一个全片渲染/编码**：逐镜渲染 `scripts/render_all.sh` 持
  `flock /tmp/ep08-render.lock`；finalize 持 `flock /tmp/ep08-finalize.lock`；
  两侧启动前互查对方锁并等待（finalize 最多等 30 分钟，可用 `EP08_WAIT_RENDER_LOCK` 调）。

```bash
cd /app/vedio/ep08-regen
export PATH=/home/admin/.local/bin:$PATH

# 0) 环境自检
ffprobe-real -version | head -1
ls -la work/timeline.json work/shots.json audio/work/audio.m4a work/srt/all.srt 2>&1

# 1) 全片渲染编排（engine 渲染器；flock 单实例；记录耗时/rc 到 work/render.json）
scripts/render_all.sh --cmd "python3 scene_body.py --all --jobs 8"
#   若 engine 提供整合渲染入口，则：
#   scripts/render_all.sh --cmd "python3 render_film.py --all"
#   产物应在 work/clips/<shot-id>.mp4（或 raw 全片，见 2b）

# 1.5) 输入自检（timeline/clips/母带/SRT/H3 一次看清；有 FAIL 不开工）
python3 scripts/check_inputs.py --wait 900    # -> work/input-check.json

# 2a) finalize（clips 模式：拼接 + 调色/遮幅/颗粒/ASS 字幕/淡入淡出 + 母带 remux + web 版）
python3 scripts/finalize.py --wait 300 --verify
#   产物：out/ep08-regen.mp4（master）、out/ep08-regen-web.mp4（web）
#   清单：work/finalize.json

# 2a-draft) code-only 内部验证版（H3 未到货时先跑通链路；不进 Release）
#   python3 scripts/finalize.py --draft --out out/ep08-draft.mp4 --web-out out/ep08-draft-web.mp4
#   python3 scripts/verify_ep08.py out/ep08-draft.mp4 --web out/ep08-draft-web.mp4 --allow-missing-h3
#   -> work/finalize-draft.json / work/final-check-draft.json

# 2b) 备选：engine 整合渲染出全片（raw 模式）
#   python3 scripts/finalize.py --input work/film-raw.mp4          # 未烘焙遮幅/字幕 → 套滤镜链
#   python3 scripts/finalize.py --input work/film-raw.mp4 --baked  # 已烘焙 → 视频流 copy + 母带 remux

# 3) 硬校验（30+ 项，含 QA 静帧 + 16 帧联系表；全 PASS 才交付）
python3 scripts/verify_ep08.py
#   人工复核：work/qa/human-check.md（逐帧目检清单，含镜号/时间/帧文件）、
#            work/qa/endcard-check.png（片尾双声明卡可读）、
#            work/qa/principle-*.png（能量流方向/电机-逆变器-电池路径）、
#            work/qa/h3-H*.png（H3 物理细节/无乱码/无 logo/无正脸）、
#            work/qa/verify-contact-sheet.jpg（16 帧全片）

# 4) 交付物：10 静帧 + 联系表 + 三版封面 + delivery-manifest.json
python3 scripts/prepare_delivery.py

# 5) 报告/清单：work/final-report.md + work/assets-manifest.json
python3 scripts/write_report.py --notes work/notes.md

# 5.5) code-only 备选交付（H3 未到货、Lead 批准时）：H3 相关项降级为 WARN
#   setsid nohup bash scripts/deliver_all.sh --allow-missing-h3 > work/deliver-all.log 2>&1 < /dev/null &
#   输出：out/ep08-regen.mp4（master）+ web + delivery/ + work/final-report.md + 工程包

# 6) 仓库同步（不 commit，Lead 统一提交）
#    Lead 裁决：仓库 视频制作/ep08-regen/scripts/ 与 README.md 归 delivery-engineer
scripts/sync_repo.sh            # delivery/ + work 报告/清单/SRT + scripts/
# scripts/sync_repo.sh --no-scripts   # 只同步交付物/报告
```

## 降级方案

| 风险 | 降级 |
| --- | --- |
| 逐镜渲染失败/缺镜 | `scripts/render_all.sh` 记 rc+日志；只重渲缺失镜号（`--only id1,id2`）；仍失败→程序化占位 + 记录（不得黑屏） |
| engine 整合渲染全片失败 | 退回逐镜 clips + finalize 拼接（默认路径）；或分段渲染 + ffmpeg concat |
| raw 全片已烘焙字幕/遮幅 | `finalize.py --input raw --baked`：视频流 copy + 母带 remux（不再套滤镜链） |
| 母带迟到 | 先用 engine 临时音轨出 draft（`finalize.py --draft`），母带到后重跑 finalize+verify |
| 响度不达标 | 由 audio-engineer 重做 loudnorm；finalize 不二次处理母带（保持交付一致性） |
| 字幕缺失/越界 | 从 `work/srt/all.srt` 修；finalize 的 ASS 字号 48 / MarginV 50 落在下黑边内 |
| H3 缺条 | engine footage 层自动隐藏（不黑屏）；verify 的 `h3_assets_present`/`h3_ratio` 记录问题并写入报告 |

## 验收阈值（Lead 逐项核）

- 1920×1080 / 24fps / 2.35:1（上下 132px 黑边）/ 时长 3:40–4:20 / 帧数 ±2 / 解码 0 错。
- I=-14±0.5 LUFS / TP≤-1.0 dBTP / LRA 0–20。
- 字幕句覆盖、无重叠、单行 ≤18 汉字、落在下黑边内；片尾双声明（画面卡 + 旁白口播）。
- 全片 36 点无黑段、8 对帧间差中位数 >0.8（不是「会动的静图」）。
- H3 24/24 到位、成片 H3 时长占比 20–35%。
- 10 静帧 + 联系表 + 16:9/1:1/3:4 封面 + web 版 + `delivery/delivery-manifest.json`。
- **人工逐帧目检**（脚本查不出）：能量流方向/电机-逆变器-电池路径/制动混合方向、
  H3 物理细节、无乱码文字/无品牌 logo/无真人正脸、片尾声明卡可读。
