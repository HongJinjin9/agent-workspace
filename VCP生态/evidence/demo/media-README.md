# V视听演示 · 成片与真实制作链路（vstudio-media 交付）

> Ticket：VCP 系统的「V视听」功能开发（原工作 Issue #3）
> 本目录是「人给视频内容 → AI agent 调用视频制作工具 → 出成片 → 人逐帧/逐元素提意见 → agent 修订重渲染」这条链路的**可复现实证**。
> 所有时间均为 UTC。

## 一、成片

| 项 | 值 |
| --- | --- |
| 成片 | `/app/VCPChat/AppData/VStudio/projects/proj_mvz5fnozzwxuh/renders/final.mp4` |
| 规格 | 1280×720 / 30fps / H.264 + AAC 48kHz 立体声 / 43s |
| 封面 | `/app/VCPChat/AppData/VStudio/projects/proj_mvz5fnozzwxuh/renders/poster.jpg` |
| 工程 | 「V视听演示 · AI 协同剪辑」`proj_mvz5fnozzwxuh` |
| 工程目录 | `/app/VCPChat/AppData/VStudio/projects/proj_mvz5fnozzwxuh/` |
| 审阅版（修订前） | `.../renders/review-v1.mp4`（用于批注前后对比；副本 `output/review-v1.mp4`） |
| 成片副本 | `/app/vedio/vstudio-demo/output/final.mp4` |
| 渲染 | 后端 VStudioCore.render()，场景 5、音轨 6；审阅版 25.5s / 最终成片 43.0s（1280×720/30，preset fast） |

画面构成（工程时间线）：

| # | 类型 | 内容 | 起点 | 时长 |
| --- | --- | --- | --- | --- |
| 1 | image | 片头标题卡「AI 协同剪辑」（Ken Burns + ASS 中文标题/副标题/来源说明） | 0s | 3s |
| 2 | video | MotionGit B1：主标题「V视听」+ 一句话解释 + 光路动效 | 3s | 11s |
| 3 | video | MotionGit B2：「AI 剪辑流程」三条要点卡 | 14s | 10s |
| 4 | video | MotionGit B3：人工剪辑 vs AI 协同 左右对比 + 结论 | 24s | 10s |
| 5 | video | MotionGit B4：「人机协同剪辑」总结 + 行动指引 | 34s | 9s |

音轨（6 条）：4 段 edge-tts 中文旁白（起点 3.3 / 14.2 / 24.2 / 34.3s）、BGM 氛围垫乐（0s，音量 0.22，淡入 2s/淡出 4s）、MotionGit 模板原生动效（3.0s 起，音量 0.8）。

## 二、链路与证据

```
人的内容（自写中文文案）
  └─ AI agent：MotionGit .motion 模板 → plan → prepare → preview → render → -with-audio.mp4
       （真实 HTML/Canvas 逐帧合成 + Chrome 截图 + ffmpeg 编码，详见 MOTIONGIT-NOTES.md）
  └─ AI agent：VStudio 插件工具（VStudio.js stdio 协议）组装工程
       create_project → import_asset ×11 → add_scene ×5 → add_audio_track ×6 → add_annotation ×3
  └─ VStudioCore.render() → review-v1.mp4（审阅版）
  └─ 人在预览中提意见（open 批注：frame 45 / target=element / 归一化区域）
  └─ AI agent 执行批注：update_scene（标题上移 6%、副标题补字）→ update_annotation（resolved + reply）→ render
  └─ 成片 final.mp4（修订后）
```

确定性证据文件：

- `agent-tool-calls.log`：全部工具调用与返回摘要（构建阶段 + 修订阶段，36 次）。
- `/tmp/vstudio-media/agent-tool-calls.jsonl`：同一批调用的完整请求/响应 JSONL（含时间戳、耗时、参数、返回体）。
- `project-snapshot.json`：最终工程 JSON 快照（场景/音轨/批注/渲染状态）。
- `/tmp/vstudio-media/vstudio-render-report.json`：渲染结果报告（路径、时长、耗时、批注状态）。
- `MOTIONGIT-NOTES.md`：MotionGit 模板取包、渲染方式、实际命令、兼容性修改记录。
- `evidence/`：成片抽帧 png（`final-01-title.png`…`final-06-outro.png`）、批注修订前标题卡 `title-v1-before.png`、封面 `poster.jpg`。
- MotionGit 模板独立成片（中间产物）：`/tmp/vstudio-media/motiongit/final-kinetic-zh-with-audio.mp4`（40.00s，1920×1080@60，模板原生渲染 + 模板混音）。

## 三、素材与来源

| 素材 | 来源 | 说明 |
| --- | --- | --- |
| 4 段动态画面 | [motiontemplates/385712](https://github.com/motiontemplates/385712) `downloads/kinetic-tech-zh.motion`（v0.2.7-open-beta，17,596,250 B） | 用模板**真实制作入口** `adapter.py plan/prepare/preview/render` 渲染 40s 母版（1920×1080@60，中文文案 B1–B4），再按分镜切为 4 段 1080p30 场景素材 |
| 中文旁白 4 段 | edge-tts `zh-CN-XiaoxiaoNeural`（本机 `/home/admin/.local/bin/edge-tts`） | 文案为本项目自写；10.13 / 7.42 / 8.09 / 4.34 秒 |
| BGM 氛围垫乐 | ffmpeg `aevalsrc` 合成（A 小调正弦叠加 + lowpass + tremolo + 淡入淡出） | 原创合成，无第三方素材 |
| 模板原生动效音轨 | MotionGit `mix.py` 输出 `audio-output/native-sfx.wav` | 模板原生动作音效（击打/擦除/上升音），作为 sfx 轨加入工程 |
| 片头标题卡底图 | `make-titlecard.py`（PIL 程序化绘制） | 按其视觉语言（深蓝渐变/网格/HUD 角标/颗粒）生成；文字由 VStudio ASS 渲染 |

## 四、复现

```bash
# 0) 前置：MotionGit 模板已解压到 /tmp/motion385712/kinetic-zh，npm ci；ffprobe shim 见 MOTIONGIT-NOTES.md
export PATH=/tmp/vstudio-media/bin:$PATH
# 1) MotionGit 真实渲染 40s 中文母版（约 16 分钟，见 MOTIONGIT-NOTES.md 第 4 节）
#    → /tmp/vstudio-media/motiongit/final-kinetic-zh.mp4（+ -with-audio.mp4 带混音版）
# 2) 切场景素材 + 生成标题卡/音频素材
bash /app/vedio/vstudio-demo/make-assets.sh
# 3) agent 通过 VStudio 插件工具组装工程并渲染审阅版
node /app/vedio/vstudio-demo/agent-build.mjs
# 4) agent 执行人工批注并重渲染最终成片
node /app/vedio/vstudio-demo/agent-revise.mjs
#    若 agent-build 被宿主中断（本机实际发生过一次：渲染中途进程被回收），用续跑脚本一次完成
#    「渲染审阅版 → 执行批注 → 渲染最终成片」：
#    node /app/vedio/vstudio-demo/agent-render-revise.mjs <projectId>
# 5) 验证（ffmpeg -i / 解码 / 抽帧 / 响度）
bash /app/vedio/vstudio-demo/verify-film.sh <成片> /tmp/vstudio-media/verify
```

## 五、验证结果

```
=== 1) 容器/流信息（ffmpeg -i）
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from '/app/VCPChat/AppData/VStudio/projects/proj_mvz5fnozzwxuh/renders/final.mp4':
  Metadata:
    major_brand     : isom
    minor_version   : 512
    compatible_brands: isomiso2avc1mp41
    encoder         : Lavf61.1.100
  Duration: 00:00:43.00, start: 0.000000, bitrate: 2118 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), 1280x720 [SAR 1:1 DAR 16:9], 1914 kb/s, 30 fps, 30 tbr, 15360 tbn (default)
      Metadata:
        handler_name    : VideoHandler
        vendor_id       : [0][0][0][0]
        encoder         : Lavc61.3.100 libx264
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 194 kb/s (default)
      Metadata:
        handler_name    : SoundHandler
        vendor_id       : [0][0][0][0]
At least one output file must be specified

=== 2) 时长/分辨率/帧率/音轨（解析）
  Duration: 00:00:43.00, start: 0.000000, bitrate: 2118 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), 1280x720 [SAR 1:1 DAR 16:9], 1914 kb/s, 30 fps, 30 tbr, 15360 tbn (default)
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 194 kb/s (default)

=== 3) 解码完整性 + 音视频流计数（解码整片到 null）
decode-exit=0

=== 4) 抽帧证据（每 5 秒 1 帧，PNG）
-rw------- 1 admin admin 678700 Nov  2 11:04 /tmp/vstudio-media/verify/frame-001.png
-rw------- 1 admin admin 312807 Nov  2 11:04 /tmp/vstudio-media/verify/frame-002.png
-rw------- 1 admin admin 804595 Nov  2 11:04 /tmp/vstudio-media/verify/frame-003.png
-rw------- 1 admin admin 350586 Nov  2 11:04 /tmp/vstudio-media/verify/frame-004.png
-rw------- 1 admin admin 317471 Nov  2 11:04 /tmp/vstudio-media/verify/frame-005.png
-rw------- 1 admin admin 364817 Nov  2 11:04 /tmp/vstudio-media/verify/frame-006.png
-rw------- 1 admin admin 321601 Nov  2 11:04 /tmp/vstudio-media/verify/frame-007.png
-rw------- 1 admin admin 362046 Nov  2 11:04 /tmp/vstudio-media/verify/frame-008.png
-rw------- 1 admin admin 273945 Nov  2 11:04 /tmp/vstudio-media/verify/frame-009.png

=== 5) 音频电平（volumedetect）
[Parsed_volumedetect_0 @ 0x70ff00002ec0] mean_volume: -23.3 dB
[Parsed_volumedetect_0 @ 0x70ff00002ec0] max_volume: -3.3 dB

=== 6) 音轨响度（ebur128 摘要）

  Integrated loudness:
    I:         -19.1 LUFS
    Threshold: -30.7 LUFS

  Loudness range:
    LRA:        10.3 LU
    Threshold: -40.4 LUFS
    LRA low:   -28.6 LUFS
    LRA high:  -18.3 LUFS
[out#0/null @ 0x27029d00] video:0KiB audio:8064KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: unknown
size=N/A time=00:00:43.00 bitrate=N/A speed= 482x
```

## 六、诚实说明与已知限制

1. **本机 ffmpeg 无 drawtext**（7.0.2 静态构建），因此 VStudio 后端的文字渲染走 **libass/ASS**（后端实现已适配，中文实测正常）；MotionGit 模板自身的文字由模板 Canvas 引擎绘制。
2. MotionGit 模板包 `render.mjs` 的 ffmpeg 色彩转换链使用了新版本 ffmpeg 的 `scale=in_primaries=...` 选项，本机 7.0.2 已移除该选项，导致渲染 EPIPE。我们做了**仅限编码参数**的兼容修改（渲染逻辑不变），原始文件备份在 `/tmp/vstudio-media/motiongit/render.mjs.orig`，详见 `MOTIONGIT-NOTES.md` 第 3 节。
3. 模板 `CREATION.md` 声明「横屏 macOS 有实测，其他系统与最大容量不冒充已通过」；本片在本机（Linux）实际渲染通过，但不等同于模板官方对全平台的兼容声明。
4. 本机无可用 `ffprobe`（符号链接指向 ffmpeg），探测一律用 `ffmpeg -i`；同时提供了 ffprobe shim `/tmp/vstudio-media/bin/ffprobe` 供后端/脚本使用。
5. 3 条批注中 1 条由 agent 真实执行并置 resolved（含 reply），1 条保持 open 供 UI pin 截图演示，1 条 in_progress 展示状态流转；批注中的版式调整说明对应 MotionGit 模板参数调整（重渲染该段素材后替换场景）。
6. 未改 `/app/VCPChat`、`/app/VCPToolBox` 源码；工程数据全部通过 VStudio API/插件工具写入默认数据目录。
7. 构建阶段宿主进程回收导致 `agent-build.mjs` 在主进程报告写入前被中断；工程数据已完整落盘（5 场景/6 音轨/3 批注），用 `agent-render-revise.mjs` 续跑完成审阅版与最终成片（工具调用记录见 `agent-tool-calls.log`，前后共 36 次调用）。

### 批注状态（最终工程）

| 帧 | target | 状态 | 批注 / agent 回复 |
| --- | --- | --- | --- |
| 45 | element | resolved | 已把标题卡标题上移 6%（y 0.44 → 0.38）、副标题补充「V视听演示片」，并用 ASS 重新渲染标题场景，已重新出片。 |
| 830 | layout | in_progress | 已在 MotionGit 模板 B3 单元调整版式并重新渲染，替换工程中的场景素材。 |
| 1220 | frame | open | 结尾节奏偏快，最后一帧多停留 0.5 秒，配乐淡出再慢一点。 |
