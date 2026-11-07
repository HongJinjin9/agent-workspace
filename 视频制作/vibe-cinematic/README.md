# 《当「感觉」比「技术」更重要：Vibe 时代的生活革命》— 电影感重制版

针对反馈「画面像播放 PPT、粗糙；要动画效果和电影的高级感」重制的版本。
素材来源与工具链：**本机 china-aigc skill**（AI 文生图，Agnes）+ **Pexels**（实拍电影感 B-roll）
+ **Mixkit**（电影配乐/音效，免费授权）+ edge-tts（中文旁白）+ ffmpeg（剪辑/调色/动效/混音）。

## 成片

- `out/vibe-cinematic.mp4` —— 76.29s / 1920×1080 / 24fps / H.264 High + AAC 192k（36.9MB）
- 校验：全片解码无错误；响度 mean -17.7dB / max -1.0dB
- 关键帧：`frames/f*.jpg`
- 工程报告：`out/report.json`（逐镜头素材、旁白时间轴、音乐）
- 上一版（字卡版）保留在 `/app/vedio/vibe-speech-video/` 供对比

## 与上一版的差别（回应反馈）

| 上一版（PPT 感） | 本版（电影感） |
| --- | --- |
| 静态字卡 + 缓慢缩放，全片字卡 | **实拍/AI 电影感画面**：夜色城市延时、手机屏幕微光、咖啡、摄影、人群、黎明等 B-roll 与 AI 电影感剧照混剪 |
| 平面文字直接压在画面上 | **动态排版**：标题分层入场（位移+缩放+淡入），章节标签、强调色、闪光/光扫转场 |
| 无调色 | **电影调色**：青橙色调、对比/饱和曲线、暗角、胶片颗粒、2.35:1 遮幅 |
| 只有 BGM 垫乐 | **声音设计**：电影配乐（The Journey）+ whoosh/riser/impact 音效点缀 + 旁白 |
| 80 秒 27 张字卡 | 76 秒 17 个镜头，**按旁白节拍硬切**，节奏更快 |

## 制作链路

```
Nova 发言稿（群聊「自媒体」话题原文 → 12 个旁白节拍）
  ├─ 旁白：edge-tts zh-CN-YunxiNeural（男声，+8%），12 段，逐段对齐镜头
  ├─ 画面（17 镜）：
  │    ├─ Pexels 实拍 B-roll 14 条（1080p，夜色城市/手机微光/咖啡馆/摄影/人群/黎明/独行…）
  │    └─ china-aigc · Agnes t2i AI 电影感剧照 8 张（神经元/光墙/眼睛/创作者/伸手向 AI/光柱/门缝光/未来城市）
  ├─ 运动：实拍原生运动 + 剧照缓慢推近/横移（Ken Burns），24fps 电影帧率
  ├─ 包装：ASS/libass 动态标题（SimHei 中文大字）+ 闪光/光扫转场 + 青橙调色 + 暗角 + 胶片颗粒 + 2.35:1 遮幅
  ├─ 配乐：Mixkit《The Journey》（Film Score，免费授权）
  ├─ 音效：Mixkit whoosh / riser / impact
  └─ 合成：ffmpeg（分段归一化 → 硬切拼剪 → 调色/遮幅/字幕 → 旁白+BGM+音效混音 → loudnorm）
```

交付：PR #4 评论（历史记录未随公开版本迁移）（视频 + 3 张静帧）；成片 `out/vibe-cinematic.mp4`，全片解码无错误，响度 mean -17.9dB / max -1.1dB。

## 复现

```bash
cd /app/vedio/vibe-cinematic
python3 fetch_stock.py        # Pexels B-roll（需 keys.env 的 PEXELS_API_KEY）
python3 gen_stills.py         # china-aigc Agnes t2i（需 keys.env 的 AGNES_API_KEY）
python3 build.py --fresh      # TTS（缓存）+ 逐镜生成 + 拼剪 + 调色 + 混音 + 导出
```

## 素材授权

- Pexels：免费商用（Pexels License）
- Mixkit：免费商用（Mixkit Stock Music Free License）
- AI 剧照：本机 china-aigc(Agnes) 生成
- 旁白文本：群聊「自媒体」话题中 Nova 的发言稿原文

## v3 自查优化（人类要求「自查一下有没有要优化或者调整的」）

逐项自查发现并修复 9 处（`build.py` 已同步）：

1. **片尾署名/账号信息未渲染**（ASS `credit` 类型未处理，真 bug）→ 补上「《Vibe 时代的生活革命》· 发言稿 Nova · 视频 VCP 视听 出品」与关注 CTA；
2. 章节标签（01 / VIBE CODING 等）落在 2.35:1 遮幅黑边里 → 移入画面内容区（y=166）；
3. 眼睛镜头「最大的风险」文字压在亮部、对比不足 → 该镜文字下移（hero_base=760），全片字幕加大描边/阴影；
4. 高潮处 impact 音效与旁白同时起、压住第一句 → impact 移到旁白前 0.35s、降音量；BGM 由 0.16 降到 0.125；
5. 「技术可以外包」长句叠在 AI 光形上 → 拆成三行短句（技术可以外包 / 「什么是对的」/ 外包不了）；
6. 「消费者 / 创作者」只有单个街景镜头 → 拆成两镜：人群（消费者永远被收割）+ 窗边独行剪影（创作者才有定价权）；
7. 静帧镜头只有推拉、偏静态 → 每个静帧加缓慢光扫（light sweep）；
8. 切点缺声音动感 → 每个镜头切换加轻 whoosh，高潮前加 riser + impact；
9. 节奏：在「但这不是乌托邦」前加 0.9s 停顿、结尾金句前加 0.6s；片尾由 7.75s 缩短到 6.75s，成片总长 75.98s。

v3 成片 `out/vibe-cinematic.mp4`（75.96s / 1920×1080 / 24fps / 34.3MB），v2 保留为 `out/vibe-cinematic-v2.mp4` 便于对比。
