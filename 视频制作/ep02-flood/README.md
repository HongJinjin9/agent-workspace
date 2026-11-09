# 第 02 期《内容洪水里，最贵的是「真的」》视频工程

来源：`自媒体稿/第02期-内容洪水里最贵的是真的.md`（v2.2，2026-11-09 评审通过）。
规格：9:16 1080×1920 / 24fps / 3:55；不出镜、不署名、无职业信息；画面/配音含 AI 辅助制作并在片尾声明。

## 结构

- 6 段旁白（S1–S6，edge-tts zh-CN-YunjianNeural），实测 223.27s；加冷开场/转场/片尾留白后成片 235.27s（3:55）
- 24 个分镜：深夜手机（停住→转发→辟谣）→ 数据机房/HUD → AI 魔改蒙太奇 → 编辑台抹水印 → 内容洪水 3D → 供需曲线 → 创作者视角 → 标识办法时间线 → 双屏对比 → 历史蒙太奇（印刷/电视/互联网）→ 3D 筛子与光流 → 来源标记 → 城市 → 滑动/长按 → 条款 → 发布 → 片尾卡
- 视觉母题：白色内容洪水与金属筛子；冷灰 + 暖金

## 流水线

| 文件 | 作用 |
| --- | --- |
| `narration/segments.json` | 从稿件 §4 抽取的 6 段纯口播 |
| `tts_segments.py` | 逐段 edge-tts + 实测时长（含 SRT 句级字幕） |
| `fetch_stock2.py` | Pexels B-roll 下载（手机/机房/编辑台/印刷/老电视/城市等） |
| `build_timeline.py` | 由 TTS 实测时长 + 分镜设计生成 `work/timeline.json` |
| `gen_bg_par.py` | B-roll → 900×1600 冷/暖调色逐帧背景 |
| `scene_flood.py` | 渲染器：内容洪水、3D 筛子、供需曲线、标识时间线、双屏、手机 UI、字幕/花字/片尾卡 |
| `engine3d.py` | 轻量 3D 相机/投影 |
| `subs.py` | SRT → ≤14 字/行、精确起止的字幕时间轴 |
| `build_audio2.py` | 6 段场景化音乐床 + sidechain + 两遍 loudnorm |
| `gen_cover.py` | 9:16 / 3:4 封面 |
| `finalize.py` | 等待渲染 → 1080×1920 编码 + 静帧/封面 |

## 复现

```bash
python3 tts_segments.py && python3 fetch_stock2.py && python3 build_timeline.py
python3 build_audio2.py && python3 gen_bg_par.py
mkdir -p work/frames
for r in "0 941" "941 1882" "1882 2823" "2823 3764" "3764 4705" "4705 5646"; do setsid nohup ./run_render.sh $r & done
python3 finalize.py
```

素材：Pexels License（B-roll）；Mixkit Free License（BGM/SFX）；Noto CJK（OFL）。
成片 mp4、静帧、封面不入库，通过 PR 评论交付。
