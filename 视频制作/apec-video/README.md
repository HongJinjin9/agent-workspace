# 《一张盘，看懂一场峰会》短视频工程

来源：VCPChat「自媒体」群聊，稽疑 2026-11-04 22:23 发布的视频发言稿
《一张盘，看懂一场峰会 · 奇门遁甲起盘，全流程实拆》（OneRing DB `稽疑.db` id=45，
另见 `beats.json` 中按口播稿拆出的 23 条旁白）。

## 成片

> 成片**不随仓库分发**，通过 Issue #3 评论附件交付；本工程目录只保留脚本、时间轴、字幕与复现说明，按下方流水线可重新产出。

- 规格：9:16 竖屏 1080×1920 / 24fps / H.264 + AAC，时长 5 分 22 秒（322.2s）
- 结构：钩子 → 定局（阴阳遁/节气三元/符头）→ 布地盘（逆布六仪三奇）→ 值符值使 → 完整盘面 → 断（核心/主办方/经贸/安保/变数/应期）→ 可检验四条 → 学理与免责 → CTA

## 制作方式（两条参考都用上了）

1. **Blender 4.5.15（headless, Cycles）**：`build_board.py`
   - 建 3×3 奇门九宫盘：暗色圆角瓦片、发光边框、天干/九星/八门/八神、空亡红框、洛书环形光轨；
   - 输出 `assets/blender/board_ortho.png`（1440×2560，正交，透明背景）与
     `board_hero.png`（1080×1920，斜视角 hero）；
   - 无头渲染：`blender -b --factory-startup --python build_board.py -- ortho|hero`
2. **程序化动效（PIL + numpy，1080×1920@24fps）**：`render_video.py`
   - 正交盘面按宫格切片成 9 个瓦片精灵，布地盘时按阴遁逆布顺序（5→4→3→2→1→9→8→7→6）
     逐宫出现、缩放淡入 + 光环；
   - 值符移宫 坎一→坤二 动线、值使逆数七宫 坎一→艮八 动点；
   - 坤二/兑七「空」脉冲高亮、应期时间轴（11/4→11/6→11/17-18）、四条检验卡片；
   - 章节标签、宋体标题、发光字、颗粒/暗角/淡入淡出等电影化收尾。
3. 参考 **wisewong6/wise-motion**：按其 SKILL 的动效方法（文字动效、卡片 reveal、
   转场与节奏组合）设计本片动效；未引入其 Remotion 运行时，若后续要复用现成组件，
   按 REMOTION.md 接 shared 组件包即可。

## 音频

- 旁白：edge-tts `zh-CN-YunjianNeural` +6%；23 段，逐段对齐 beat（`work/narration.json`）
- 配乐：Mixkit「Vastness」（免费许可）；音效：Mixkit whoosh/riser/impact
- `build_audio.py`：旁白按 beat 起点 adelay、BGM 0.11 音量淡入淡出、SFX 按镜头切换布置、
  loudnorm I=-15 TP=-1.5

## 复现

```bash
cd /app/vedio/apec-video
/home/admin/apps/blender-4.5.15-linux-x64/blender -b --factory-startup --python build_board.py -- ortho
/home/admin/apps/blender-4.5.15-linux-x64/blender -b --factory-startup --python build_board.py -- hero
python3 tts.py           # 生成旁白
python3 build_audio.py   # 混音
python3 render_video.py 0 7733   # 帧渲染（可分段并行）
./encode.sh              # 编码成片
```

## 事实边界

- 会期：APEC CEO Summit 2026 深圳 11/17-18（中国日报/CGTN/深圳市政府英文站三源一致）；
  领导人会议另有 18-19 之说，标为待核；成片保留「应期断事态节奏、不绑死单日」。
- 片尾声明：术数练习与教学演示，不构成任何现实决策依据。
- 素材许可：Blender 场景与程序化图形自制；音乐/音效 Mixkit 免费许可；字体 Noto Serif/Sans CJK（OFL）。

## v2 电影感重做（回应「3D 场景、动态排盘特效偏弱 / PPT 感」）

- 自研轻量 3D 引擎 `engine3d.py` + `scene3d.py`：九宫瓦片是带厚度与透视的真实 3D 四边形，
  相机 dolly / orbit / 俯冲，逐宫飞入落位带涟漪与光环；值符/值使光球沿 3D 弧线移动，
  空宫红环脉冲与粒子；布地盘按 5→4→3→2→1→9→8→7→6 顺序动态排盘。
- 沿用上一版成熟经验（按主人 2026-11-05 补充要求）：
  - 真实 B-roll / AI 静帧做电影感背景层（`assets/backdrops/`：城市夜景、星云、晨光、抽象光），
    缓慢漂移视差；
  - 统一 teal-orange 调色、辉光（bloom）、胶片颗粒、暗角、光漏（light leak）；
  - 配乐 Mixkit「Vastness」循环铺满 + whoosh/riser/impact 音效；loudnorm I=-15；
  - 旁白 edge-tts 同一稿 23 段；交付静帧与附件流程不变。
- 渲染 900×1600@24fps（CPU 8 进程并行）→ 成片 1080×1920（lanczos 放大 + 轻锐化）。
- 产物：成片 `out/apec-qimen-v2f.mp4`（crf25，1080×1920，约 45MB）由 `finalize-v2.sh` 生成，**不随仓库分发**，通过 Issue #3 评论附件交付；crf21 高码率版（131MB）超出 GitHub 附件上限，仅本地留存。帧输出：`work/frames2/`；脚本：`engine3d.py`、`scene3d.py`、`gen_backdrops.py`、`encode2.sh`、`finalize-v2.sh`。
