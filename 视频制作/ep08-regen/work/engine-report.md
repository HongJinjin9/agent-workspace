# 第 08 期 代码层工程报告（engine-dev）

> 状态：v1.0（H3 交接包已冻结；67 镜时间轴已建；代码镜逐镜渲染中/渲染完）
> 权威输入：`自媒体稿/第08期-电动车松开油门为什么能充电.md`（锁定稿，facts §7.2 F01–F18）、
> `视频制作/ep08-scene-design/SCENE-DESIGN.md`（67 镜/23 H3 含镜）、`audio/work/timeline_audio.json`（252.380s）。

## 1. 交付物（生产 `/app/vedio/ep08-regen/`）

| 文件 | 作用 |
| --- | --- |
| `ep08viz.py` | 视觉库：冷灰影调/五色系统、可逆通道/电池/逆变器/电机剖面、Sankey、功率表、版式、颗粒暗角 |
| `scenes_pil.py` | 45 个全画幅程序化场景（44 代码镜 + H3 缺失降级场景） |
| `overlays.py` | 22 个叠加层（压 H3 实拍底的数据/文字层） |
| `build_timeline.py` | 67 镜时间轴生成器（音频实测句首锚定，硬切） |
| `scene_body.py` | 逐镜渲染编排（PIL 直管道 ffmpeg / H3 底+叠加层 / H3 缺失降级） |
| `ep08assets.py` | H3 素材解析（Sxx.mp4 优先、Hxx.mp4 兼容；缺失返回 None） |
| `gen_h3_pack.py` | H3 交接包生成（关键帧 + shots-ep08.json） |
| `keyframe_art.py` | 代码渲染首帧构图（本版未用于 FL2VA，保留供备选） |
| `facts.json` | facts 单一数据源（锁定稿 §7.2 全量字段化；画面全部从此读） |
| `shots.json` | 67 镜 spec（kind/scene/overlay/asset/fallback/start/dur） |
| `work/timeline.json` | 渲染唯一时间基准（total=252.380s / 67 镜 / seg S1–S7 / h3 标记） |
| `work/srt/all.srt` | 句级字幕（来自 audio 侧，99 条，≤18 汉字/行） |
| `work/clips/<shot>.mp4` | 逐镜成片素材（1920×1080/24fps/x264 crf16/无声），交 delivery finalize |
| `comfyui/shots-ep08.json` | H3 工单 23 条（22 含镜 + H24 备用；18 FL2VA / 5 T2V） |
| `comfyui/keyframes/*.png` | H3 首帧 18 张（Sxx_first.png + H24_first.png，864×480） |
| `work/h3-keyframes.json` | 首帧来源/授权/抽帧时间/影调参数 manifest |
| `work/pexels-keyframes.json` | Pexels 静图 manifest（photo id/作者/页面/license） |

## 2. 时间轴（build_timeline.py）

- 唯一基准 `audio/work/timeline_audio.json`：total **252.380s**、7 段、73 句。
- 每镜起点 = 该镜「旁白映射」首句的实测句首；终点 = 下一镜起点（硬切）；末镜终点 = total。
- 同句多镜按设计时长比例插入，最短 1.34s；段号 S1–S7 与音频段一一对应。
- H3 画面时长占比 **30.2%**（76.0s / 251.8s，含混合镜取其整镜时长），在 20–35% 内。
- 字幕 `work/srt/all.srt` 从 audio 侧拷贝；单行 ≤18 汉字由 audio 侧保证。

## 3. 代码镜实现（英雄镜头优先级）

- **C2 可逆能量通道（母题）**：布局固定 `轮端(左) → 电机 → 逆变器 → 电池(右)`；
  **回收/刹车：能量点+箭头 左→右（青）**；**驱动：右→左（琥珀）**（代码注释与 `draw_chain` 参数即契约）。
  复用镜：S04/S06/S21/S22/S23/S24/S31/S63/S64。
- **C1 片头钩子（S01，纯代码）**：功率表从「放电」翻到「回收」、能量倒着走、松油门/车在充电；
  **不出现具体 kW/kWh 数字**（锁定稿口径：功率不写具体数值）。
- **C3 三件套剖面**：电机定子 12 槽三相绕组/8 极转子/气隙（S08/S15），逆变器 DC 母线+三桥臂+三相（S16/S19），
  波形 直流↔交流（S17/S18），电池包+BMS 门禁（S20 混合）。
- **C4 能量账**：½mv²→1.5t/100km/h→0.16 kWh→+44%（S26–S29）；逐站损耗条（S31）；
  效率 70–87% / 驱动 87–89% / 差值（S32–S34）；实车 78%（S35 混合）；Sankey 热/风阻/滚阻（S36）；
  风阻随速度（S37）；高速 <5%（S38）；下坡 1km/50m/0.20/0.14/不到 1km（S41）。
- **C5 四条限制**：四联卡（S42）、满电（S43）、低温（S44 混合）、析锂（S45）、车速（S46）、反电动势（S47）、
  ABS（S50 混合）、三重功率上限（S51）、条件账合上（S52）。
- **C6 单踏板/混合制动**：单踏板逻辑（S53 混合）、串行/并行分配（S54）、平顺 vs 点头（S55 混合）。
- **C7 续航/刹车片**：城市/高速占比环（S56/S57 混合）、刹车片厚度（S58 混合）、刹车盘锈蚀（S59 混合）、
  驾驶习惯（S60 混合）、提前松 vs 重刹曲线/柱状（S61/S62）。
- **C8 收束**：母题回归（S63）、换方向存回（S64）、金句卡（S65）、片尾双声明卡（S67）。

## 4. H3 交接包（冻结版）

- 22 个 H3 含镜 + H24 备用；18 FL2VA（真实 stock/Pexels 首帧）+ 5 T2V（S25/S30/S53/S55/S58）。
- 首帧全部冷灰影调、16:9、无文字/UI/logo/人物；S20/S07 已对可读小字/徽标做区域模糊。
- `shots-ep08.json` 字段：id(H01..H24)/shot(Sxx)/seg/title/md/width/height/duration/seed/
  mode(FL2VA|T2V)/first_frame/last_frame/hero/fallback/spare(H24)。
- 代码示意图首帧仅作备份（`keyframe_art.py`），**不喂 FL2VA**（PDF 分工红线）。

## 5. 渲染与接口

- 入口：`python3 build_timeline.py` → `python3 scene_body.py --all --jobs 2`
- 产物：`work/clips/<shot>.mp4`（1920×1080 / 24fps / x264 crf16 / 无声；**不烘焙**遮幅/字幕/统一调色）。
- H3 缺失：该镜自动降级为 fallback 代码场景（不黑屏、信息不丢），并在渲染日志标注。
- H3 >5.05s 的混合镜：0.80–0.92x 慢放适配（设计稿 §5 方案），不循环硬切。
- 资源纪律：2 进程、每进程 OMP/OPENBLAS=1、ffmpeg `-threads 2`；本地渲染持 `/tmp/ep08-render.lock`。
- finalize/硬校验/交付物由 delivery-engineer 主导（root finalize 副本不作为交付口径）。

## 6. QA 记录（Lead/writer 轮次）

- QA#1：节点效率标签裁切/车轮语义 → 已在正式场景修复；
- QA#2：S01 数值违规（已删数值，改状态符/方向箭头）；四站方向契约（已写死并在各镜显式传参，S04/S21/S24/S63/S64 回收朝右、S06 驱动朝左、S22 双向、S23 翻转）；
- QA#3：S24 副标签重影（已关内置标签仅保留一套）；S46 转速→车速；S34 补回收/驱动标签；S52 补第四项抓地力；
- 预览：`work/previews/pv_<shot>_<t>.png`（全部 67 镜中段帧）。

## 7. 已知限制 / 待办

- H3 素材到货后需 `scene_body.py --force --only <22 镜>` 重渲混合镜；
- H3 环境声混入母带由 audio/finalize 侧处理（本工程 clip 无声）；
- 全片帧数/时长以 delivery finalize 实测为准（本工程 timeline total=252.380s）。

## 8. 渲染实测（2026-11-16）

- 45 个代码镜首轮渲染完成：`work/clips/` 45 个，x264 veryfast crf16，1920×1080/24fps；
  主渲染 2 进程用时约 **486s**（含启动开销）；单镜 9–89s（S24 9.7s 长镜 89s）。
- 随后按「累计帧边界」与 QA#3 修复覆盖重渲 19 镜（S01/S10/S18/S23/S26/S27/S28/S32/S33/
  S36/S37/S41/S42/S43/S47/S51/S61/S62/S65）。
- 22 个 H3 混合镜：H3 素材未到货时先渲染 fallback 代码场景（code-only 全片可审片）；
  H3 到货后 `--force --only <22 镜>` 重渲。
- 逐镜自检 `python3 verify_clips.py`：时长/帧数/分辨率/解码，与 timeline 对照。

## 9. 逐镜 clips 完成情况（code-only 版，2026-11-16）

- `work/clips/`：**67/67 完成**，全部 1920×1080 / 24fps / x264 crf16 / 无声（未烘焙遮幅/字幕/调色）。
- 帧数硬校验：逐镜解码统计 **合计 6057 帧 = round(252.380×24)**，0 镜偏差（按累计帧边界取整）。
- `verify_clips.py`：`clips 67/67 bad=0 missing=0`，时长与 timeline 误差 ≤0.04s，解码 0 错。
- 22 个 H3 混合镜当前为 **fallback 代码场景**（H3 素材未到货）：不黑屏、信息/数字不丢；
  H3 到货后需 `python3 scene_body.py --all --jobs 2 --force --only <22 镜>` 重渲（预计 3–5 分钟），
  之后再次 `verify_clips.py`。
- 参考：主渲染 2 进程 486s；force 重渲 19 镜 + fallback 22 镜合计约 10 分钟。

## 10. QA4 收尾（code-only 最终版，2026-11-16T11:59Z）

- 按 writer/Lead QA P1/P3 修复并重渲 **26 镜**：S02（去 SOC 数字→电量↑/回收中·示意）、
  S42/S52（四卡/条件卡提亮+微光底）、S25 花字「回收功率」、S66 花字「边界」、
  S23（箭头翻转特写放大）、S34（两线叠合+差值斜线高亮）、S57（高速空景+<5%，去占比环）、
  22 个 H3 混合镜 fallback 场景加抽象能量带/漂移斜纹/往返能量点/冷光点。
- 重渲耗时 502.2s（2 进程，含 22 个 fallback 场景 ~0.5s/帧）。
- `verify_clips.py`：**67/67 bad=0 missing=0**；逐镜解码 **合计 6057 帧 = round(252.380×24)，0 偏差**。
- `work/srt/all.srt` 已同步 audio 侧最新版（md5 3dfdc812fd9ec6178fb9d195103d422d，99 条）。
- `/tmp/ep08-render.lock` 已释放；22 个 H3 混合镜仍为 fallback（H3 素材 0/22，窗口未开机），
  到货后跑 `work/h3_integrate.sh` 即可替换。
