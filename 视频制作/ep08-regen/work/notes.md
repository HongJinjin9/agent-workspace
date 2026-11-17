# EP08 交付备注 / 已知限制（write_report.py 会整段并入 final-report.md §8）

> 交付 owner 在成片验收后补充；只写实测结论与人工目检结果，不写「应该没问题」。

## 1. 交付形态：H3 正式版

- ComfyUI MiniMax H3 窗口 2026-11-16T23:28Z–2026-11-17T00:28Z：`assets/h3/` 45 个 mp4（23 Hxx + 22 Sxx），
  manifest counts **total 23 / ok 20 / redline_fallback 3 / failed 0 / fl2va 15 / t2v 8**；H24 备用未使用。
- **红线降级 3 镜**：H14→S49（重生成后仍有品牌 logo）、H18→S56（可读车牌/店招/行人）、H22→S60（前车车牌可读），
  按 Lead 规则走**代码层降级**（clips 中 S49/S56/S60 必须为代码版，不得用 H3 画面）；manifest `redline` 字段与
  `comfyui/report.md §3` 记录原因。
- 成片 H3 时长占比：**实测 27.2%**（19 个 H3 镜 / 67 镜时长口径；时间轴已更新 `h3=true` 19 镜）；
  engine 初算 30.2% 是 23 条全可用口径，h3-operator 估算 ~24%；实测 27.2% 在 20–35% 内。
- 之前 code-only 兜底版（12:10）已归档 `out/fallback-codeonly/`（master sha256 4f06f803…），H3 版不可用时可直接回退；
  归档时 verify 的 `content_present` FAIL 是误判（t=246.38s 片尾暗底声明卡），已修判据。

## 2. 渲染/编码实测

- 逐镜渲染：code-only 67 镜（QA4 后）+ H3 整合 23 镜（22 混合 + S67，`--force`，约 7 分钟/2 进程）；
  `verify_clips.py` 67/67 bad=0、全部 1920×1080/24fps/解码 0 错、时长误差 ≤0.04s。
- 拼接：67 镜合计 252.25s（H3 镜重渲后比时间轴短 0.13s）→ finalize 用 `tpad=clone` 补齐到时间轴 252.380s，
  成片帧数应为 6057（=round(252.380×24)）。
- 长进程纪律：finalize/交付链必须 `setsid nohup ... < /dev/null &` 脱离会话，否则随 agent 回合结束被回收；
  `flock /tmp/ep08-finalize.lock` 与 engine 的 `/tmp/ep08-render.lock` 互斥（finalize 启动会等 render 锁释放）。

## 3. 人工目检（Lead 逐帧，待填结果）

- [ ] 能量流方向：回收=轮端→电机→逆变器→电池；驱动=电池→逆变器→电机→轮端；不得混向。
- [ ] 电机-逆变器-电池剖面路径、转子/定子/三相/DC 母线标注正确。
- [ ] 制动混合方向（液压制动 + 电机回收的力矩分配）。
- [ ] H3 画面：无乱码文字/可读数字/原理箭头、无品牌 logo、无真人正脸；车轮转向/踏板行程/刹车盘热态/雨雪抓地/ABS 轮速等物理细节合理（PDF §六 要求逐帧目检）。
- [ ] 片尾双声明卡可读（`work/qa/endcard-check.png`）+ 旁白口播可闻。
- [ ] 低运动抽帧（`work/qa/motion-probe/`）：H3 到货后应由实拍运动提升；若仍有 fallback 静置卡需记录。

## 4. 已知限制

- **H3 商用许可**：MiniMax H3 生成内容的商用发布需按平台许可确认（发布前复核，凭据未落仓库）。
- **H3 物理细节需人工逐帧目检**：脚本只能验证画面存在与运动量，不能判断电流方向/能量流箭头语义与 H3 物理合理性。
- **运动量指标裕度**：`motion_present` 含胶片颗粒贡献，人检时仍需确认「不是会动的静图」；补充指标 `motion_content`（强变化像素占比）自动记录。
- **本机无 OCR**：片尾声明卡/花字可读性以「文字像素密度 + 静帧」判定，交付前人工目检。
- **平台转码**：响度/真峰值以 ffmpeg loudnorm 实测为准，平台转码后可能有 ±0.3 LU 偏差；字幕字号在手机端需预览一次。
- **本机 ffprobe 是假的**（符号链接到 ffmpeg）：校验脚本统一用 `ffprobe-real` / `ffmpeg -i` 解析。
- **H3 素材授权**：H3 素材大文件不入库，仓库只保留 `comfyui/` 工单/报告与 `assets/h3/manifest.json` provenance。

## 5. 合规

- 片尾画面卡 + 旁白口播双声明（AI 辅助制作 / 选题核实判断由人完成）。
- 全片不出镜、不署名、无职业/公司/证件/车牌信息；不点评具体车型/品牌好坏。
- AI 素材：H3 23 条（22 使用 + H24 备用）；BGM/音效 numpy 原创合成；旁白 edge-tts `zh-CN-YunjianNeural`；
  Pexels B-roll（如有）按 `delivery/delivery-manifest.json` 的 `assets_provenance` 记录；字体 Noto CJK（OFL）。
