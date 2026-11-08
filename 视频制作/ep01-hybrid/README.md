# 第 01 期《人生，也是一台混动车》视频工程

来源：`自媒体稿/第01期-人生也是一台混动车.md`（Issue #1 / PR #3，2026-11-07 定稿）。
按稿件 §2–§7 的视听设定制作：9:16 1080×1920 / 24fps / 4:20，不出镜、不署名、无职业信息。

## 结构

- 6 段旁白（S1–S6，edge-tts zh-CN-YunjianNeural），实测 243.18s，加设计留白后成片 259.78s（4:19.8）
- 25 个分镜：车内仪表/刹车 → 夜工位 → 白天/夜晚分屏 → 3D 混动剖面（五节点能量光带）→ 四种模式 → 挫败与回收 → 城市夜景 → 片尾卡
- 核心视觉母题：青绿能量光带 #3DF5C8；teal–orange 影调 + 35mm 颗粒 + 暗角；8 处花字；逐句字幕（≤14 字/行，距底 260px 安全区）

## 流水线

| 文件 | 作用 |
| --- | --- |
| `narration/segments.json` | 从稿件 §4 抽取的 6 段纯口播（剥离提示与引用块；稿件原文见 `自媒体稿/`） |
| `tts_segments.py` | 逐段 edge-tts + 实测时长 → `work/tts/` |
| `fetch_stock.py` | Pexels B-roll 下载（23 支：仪表/刹车/工位/地铁/键盘/手机/纸笔/雨窗/城市夜景/车内等） |
| `build_timeline.py` | 由 TTS 实测时长 + 分镜设计表生成 `work/timeline.json`（25 镜、总时长） |
| `gen_bg_par.py` | 并行把 B-roll 裁成 900×1600、teal-orange 调色、24fps，输出逐帧背景（分屏/蒙太奇镜头单独合成） |
| `scene_hybrid.py` | 渲染器：背景帧 + 能量光带（2D 贝塞尔 / 3D 流动）+ 混动 3D 剖面（5 节点、四种模式）+ 仪表 HUD + 四宫格 + 字幕 + 8 处花字 + 片尾卡 |
| `subs.py` | 解析 edge-tts 句级 SRT，生成 ≤14 字/行、精确起止的字幕时间轴（`work/srt/*.srt`） |
| `build_audio2.py` | v2 混音：6 段场景化连续音乐床 + sidechain 自动压低 + 音效 + 两遍 loudnorm（-14 LUFS / TP -1.5） |
| `gen_cover.py` | 9:16 与 3:4 视频号封面（成片封面见 PR 评论，不入库） |
| `finalize.py` | 等待渲染 → 1080×1920 编码（crf24）+ 静帧/封面抽取 |

## v2 修订（2026-11-08 反馈）

- 配乐：6 段场景化连续音乐床（the-journey / silent-descent / cyberpunk-city 按段落切换，1.5s 交叉淡化）+ sidechain 自动压低 + 两遍 loudnorm（-14 LUFS / TP -1.5 / LRA≤11），见 `build_audio2.py` 与 `音频混音与字幕同步方案.md`。
- 字幕：改用 edge-tts `--write-subtitles` 的句级 SRT 时间戳（`subs.py`），按 ≤14 字切行并在句内按字数分配，替代原「整段字数比例」估算。

## 复现

```bash
python3 tts_segments.py && python3 fetch_stock.py && python3 build_timeline.py
python3 build_audio2.py && python3 gen_bg_par.py
mkdir -p work/frames
for r in "0 1040" "1040 2080" ... "5200 6234"; do setsid nohup python3 scene_hybrid.py $r & done
python3 finalize.py
```

素材：Pexels License（B-roll）；Mixkit Free License（BGM/SFX）；Noto Sans/Serif CJK（OFL）；旁白 edge-tts。
合规：不出镜、不署名、不提及职业背景；AI 生成内容声明见片尾卡与发布文案。

> 文件最小化：成片 mp4、静帧、封面与交付评论不随仓库入库（通过 PR 评论/群聊交付），仓库只保留可复现的脚本、文档、时间轴与 SRT。
