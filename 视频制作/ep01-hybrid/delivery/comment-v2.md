This is by an automated agent, not a human.

你反馈的两点已修复，附 v2 成片供复查（**仍未发布视频号**）。

## 1. 配乐：改为「按场景分层的连续音乐床 + 自动避让」

调研参考（已写入 `音频混音与字幕同步方案.md`）：
- 行业做法：音乐床应是「一条连续床」，旁白出现时用 sidechain 自动压低 15–16 LU；合成旁白易被音乐掩蔽，用 threshold≈0.012 / ratio 12–14 / release 500ms；两遍 loudnorm（第二遍 linear）到 -14 LUFS / TP -1.5。
- 参考实现：ffmpeg `sidechaincompress`（[音频参考](https://github.com/0xDarkMatter/claude-mods/blob/main/skills/ffmpeg-ops/references/audio.md)、[混音与响度指南](https://github.com/shafthq/shaft_engine/blob/main/chaos-engine/addons/design-skills/references/audio-mix-loudness.md)）。

v2 实际改动：
- 6 段场景化音乐床：S1 钩子 the-journey → S2 共鸣 silent-descent → S3/S4 拆概念与四种模式 cyberpunk-city → S5 故事 silent-descent → S6 升华 the-journey；段间 1.5s 交叉淡化，不再硬切/常驻两轨。
- 音乐床 EQ 给旁白让频段（HPF 120Hz、-2dB@300Hz、-1.5dB@3kHz）；旁白 highpass 80Hz + 2.5:1 轻压缩。
- sidechain 自动 duck（threshold=0.012 / ratio=12 / attack=20ms / release=500ms），旁白下音乐自动压低。
- 音效克制（转场 whoosh 0.10、关键点 impact 0.18–0.22）。
- 两遍 loudnorm：实测 -24.02 → **-14.10 LUFS / true peak -1.21 dBTP / LRA 3.6**（目标 -14±1 / TP≤-1 / LRA≤11）。

## 2. 字幕：改用 TTS 句级时间戳精确对齐

- 用 `edge-tts --write-subtitles` 重新取 6 段旁白 SRT（114 条句级时间戳；重新合成音频与现有音轨逐字节一致，时间戳可直接对齐）。
- `subs.py`：每句按标点切成 ≤14 字/行，句内按字数分配时长；全局时间 = 段落起点 + SRT 时间。
- 渲染器直接使用这些时间戳，字幕起止与配音对齐，替代原来「整段字数比例」估算。

## v2 成片

- 1080×1920 / 24fps / 4:19.78（259.78s）/ 40,695,842 字节；音频 48kHz
- 校验：全片解码无错误；混合响度 -14.12 LUFS / true peak -1.21 dBTP / LRA 3.6；volumedetect mean -17.2dB / max -1.2dB；6234 帧
- 附件：v2 成片 + 静帧 + 封面；工程与方案文档已更新到本 PR（`build_audio2.py` / `subs.py` / `音频混音与字幕同步方案.md`）

确认后我再发视频号。
