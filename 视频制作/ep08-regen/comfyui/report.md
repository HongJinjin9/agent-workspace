# 第 08 期 · ComfyUI H3 生成与验收报告

> 生成入口：`https://wp08.unicorn.org.cn:22418`（WyfGate 门禁；凭据只走环境变量，未写入任何文件/消息/仓库）。
> 窗口日志覆盖：2026-11-16T10:57:26Z → 2026-11-16T23:55:34Z；批量生成耗时 227.3s。

## 1. 结果总览

- 镜头：23 条；raw 23 / 本地 1080p 23 / 生成成功 20
- 模式：FL2VA/i2v 15 条；T2V 8 条（其中 FL2VA 失败后降级 0 条）
- 失败/顺延：0 / 0
- 校验：raw PASS 23/23；1080p PASS 23/23
- 能力探测：ComfyUI 0.42.5 / cuda:0 NVIDIA GeForce RTX 5090 : cudaMallocAsync；FL2VA=fl2va；降级=False

## 2. 逐镜清单

| 镜头 | 镜号 | 段落 | 内容 | 模式 | 生成 | 时长 | seed | 耗时(s) | job id | raw 校验 | 1080p 校验 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H02 | S02 | S1 | 车内侧窗：长下坡，护栏后退，光斑流动 | fl2va | 864×480 | 5.0s | 202611160103 | 92.0 | 2f8f807e-109e-4530-841d-6eb223f1394d | PASS | PASS | downloaded |
| H03 | S05 | S2 | 长下坡全景：山路连续下坡，远处谷底 | fl2va | 864×480 | 5.0s | 202611160104 | 38.4 | 1047ef23-dfb2-478c-b34a-e408d1b495d7 | PASS | PASS | downloaded |
| H04 | S07 | S2 | 轮毂与底盘：车轮旋转、悬挂轻微起伏 | fl2va | 864×480 | 5.0s | 202611160105 | 38.3 | 5ba29cc2-033b-40b6-aaf0-857ff568af90 | PASS | PASS | downloaded |
| H05 | S10 | S2 | 刹车盘红热：盘面由暗转红，热浪微微扭曲 | fl2va | 864×480 | 5.0s | 202611160106 | 37.6 | baa5bc5b-e466-40f7-8527-78f9dedabdee | PASS | PASS | downloaded |
| H06 | S20 | S3 | 电池包外观与 BMS 屏：冷光、线束、指示灯 | fl2va | 864×480 | 5.0s | 202611160107 | 42.8 | 27b3eb08-fa82-4609-8617-08fc38f2cea0 | PASS | PASS | downloaded |
| H07 | S25 | S4 | 刹车踏板：脚掌下压、踏板行程 | t2v | 864×480 | 5.0s | 202611160108 | 1.0 | 875a4101-0f94-4f06-9f2e-75608037f0f1 | PASS | PASS | downloaded |
| H08 | S30 | S4 | 刹车盘热浪：红热区域扩大、颗粒逸出 | t2v | 864×480 | 5.0s | 202611160109 | 35.7 | 6c031af8-cc67-47f5-9e52-b286dbae2be8 | PASS | PASS | downloaded |
| H09 | S35 | S4 | 城市道路底图：车流稀疏，路面反光 | fl2va | 864×480 | 5.0s | 202611160110 | 37.8 | 470fc700-56ae-47e8-857c-aacdb07c0d57 | PASS | PASS | downloaded |
| H10 | S39 | S4 | 城市车流横移：走走停停，刹车灯明灭 | fl2va | 864×480 | 5.0s | 202611160111 | 40.4 | fc16762b-3cc5-4d46-9e8b-c40216f379ab | PASS | PASS | downloaded |
| H11 | S40 | S4 | 山路俯拍下坡：连续弯道，谷底可见（hero 候选，可选尾帧） | fl2va | 864×480 | 5.0s | 202611160112 | 38.2 | b216f911-b084-4b88-8e6d-3539a2f0f725 | PASS | PASS | downloaded |
| H12 | S44 | S5 | 低温霜冻路面/车窗：白霜、冷光 | fl2va | 864×480 | 5.0s | 202611160113 | 37.3 | ffb5c5d1-e68b-4392-9659-b7fdfb252b45 | PASS | PASS | downloaded |
| H13 | S48 | S5 | 高速低机位跟拍：车头切风、路面高速流动（纯 H3） | fl2va | 864×480 | 5.0s | 202611160114 | 38.1 | cbc652ae-8648-45b4-8a0d-706e902f3adc | PASS | PASS | downloaded |
| H14 | S49 | S5 | 雨雪路面与轮胎：胎面碾过水膜，抓地环反光 | fl2va | 864×480 | 5.0s | 202611160115 | 39.9 | d86edd57-1af8-4def-9679-d5bbc30e6486 | PASS | PASS | redline_fallback |
| H15 | S50 | S5 | 湿滑路面急刹：轮速抖动、车身微沉 | fl2va | 864×480 | 5.0s | 202611160116 | 41.4 | 2d84fcd8-0784-471a-8912-ca2394d48cb8 | PASS | PASS | downloaded |
| H16 | S53 | S6 | 踏板机构：加速踏板回弹、刹车踏板待命（hero 候选，可选尾帧） | t2v | 864×480 | 5.0s | 202611160117 | 36.1 | aed5456d-f3fe-4343-8c83-d9b1a6f4e03d | PASS | PASS | downloaded |
| H17 | S55 | S6 | 车内水杯水面：液面随减速轻晃 | t2v | 864×480 | 5.0s | 202611160118 | 35.2 | 7fd388c3-e1f3-43df-bb21-83b09462cee0 | PASS | PASS | downloaded |
| H18 | S56 | S6 | 城市车流（续航段）：路口多车减速 | t2v | 864×480 | 5.0s | 202611160119 | 35.8 | a47b6fe1-6010-4fcc-baf4-c8b3acd726cf | PASS | PASS | redline_fallback |
| H19 | S57 | S6 | 高速行驶（续航段）：匀速巡航，前景模糊 | t2v | 864×480 | 5.0s | 202611160120 | 35.7 | ae5e18f2-2c6c-4ba5-85c8-99b73c2df8cd | PASS | PASS | downloaded |
| H20 | S58 | S6 | 刹车片/卡钳微距：摩擦片厚度、金属光泽 | t2v | 864×480 | 5.0s | 202611160121 | 38.0 | 95fd91a8-bb95-48ca-a0a3-fd8bfb654f5f | PASS | PASS | downloaded |
| H21 | S59 | S6 | 刹车盘锈蚀：盘面锈斑、边缘氧化物（纯 H3） | fl2va | 864×480 | 5.0s | 202611160122 | 39.8 | 5aa65314-7491-40af-b3df-5ab8c1cea0e9 | PASS | PASS | downloaded |
| H22 | S60 | S6 | 车流跟拍（驾驶习惯段）：前车减速、距离变化（可选尾帧） | t2v | 864×480 | 5.0s | 202611160123 | 35.5 | f239d464-2398-4339-8fd8-6a0d5be8f9ff | PASS | PASS | redline_fallback |
| H23 | S66 | S7 | 城市黄昏远景：长焦压缩车流，暖光（纯 H3） | fl2va | 864×480 | 5.0s | 202611160124 | 38.1 | 96116bbc-0aca-494d-8c6f-09c3e6858137 | PASS | PASS | downloaded |
| H24 | SPARE | SPARE | 备用：充电口/插枪，充电枪插入、指示灯亮（片尾空镜/顶替） | fl2va | 864×480 | 5.0s | 202611161100 | 38.1 | f512ed5f-8a7c-445e-be42-8089f5d1b76f | PASS | PASS | downloaded |

## 3. 失败 / 降级 / 待处理

- **H14** status=redline_fallback raw=assets/h3/raw/H14_raw.mp4 final=assets/h3/H14.mp4 problems=[]；红线：重生成 1 次后轮毂中心盖仍出现 Mercedes 三叉星品牌标（红线：logo）
- **H18** status=redline_fallback raw=assets/h3/raw/H18_raw.mp4 final=assets/h3/H18.mp4 problems=[]；红线：重生成 1 次后仍有可读车牌/店招文字/行人（红线：文字+人物）
- **H22** status=redline_fallback raw=assets/h3/raw/H22_raw.mp4 final=assets/h3/H22.mp4 problems=[]；红线：重生成 1 次后前车车牌可读（红线：文字）

### 3.1 红线重生成后通过（已替换为新文件）

- **H06**：红线重生成 1 次后通过（文字/logo 已消除）（`assets/h3/H06.mp4`）
- **H08**：红线重生成 1 次后通过（文字/logo 已消除）（`assets/h3/H08.mp4`）
- **H19**：红线重生成 1 次后通过（文字/logo 已消除）（`assets/h3/H19.mp4`）

## 4. T2V 降级镜头（无关键帧 / FL2VA 失败）

- H07：刹车踏板：脚掌下压、踏板行程（864×480）
- H08：刹车盘热浪：红热区域扩大、颗粒逸出（864×480）
- H16：踏板机构：加速踏板回弹、刹车踏板待命（hero 候选，可选尾帧）（864×480）
- H17：车内水杯水面：液面随减速轻晃（864×480）
- H18：城市车流（续航段）：路口多车减速（864×480）
- H19：高速行驶（续航段）：匀速巡航，前景模糊（864×480）
- H20：刹车片/卡钳微距：摩擦片厚度、金属光泽（864×480）
- H22：车流跟拍（驾驶习惯段）：前车减速、距离变化（可选尾帧）（864×480）

## 5. 文件与复现

- 1080p 成片：`assets/h3/H01.mp4` … `assets/h3/H24.mp4`（1920×1080 / 24fps / H.264 + AAC）；同时硬链接 `assets/h3/S01.mp4` …（engine `shot` 命名），manifest 两个路径都记。
- 原始：`assets/h3/raw/{ID}_raw.mp4`（864×480 或 hero 1280×736，H3 原生音轨）
- 清单：`assets/h3/manifest.json`；能力探测：`assets/h3/capability.json`；逐帧校验：`assets/h3/verify-raw.json` / `verify-final.json`；抽帧：`assets/h3/frames/`
- 提示词：`comfyui/prompts-ep08.md`（机器可读 `comfyui/shots-ep08-run.json`）

```bash
export H3_USER=… H3_PASS=… H3_BASE=…   # 只走环境变量
cd /app/vedio/ep08-regen/comfyui
python3 check_pack.py                     # 开机前静态校验
python3 resolve_base.py 1800              # 入口探测
python3 capability_probe.py               # 节点/模型/FL2VA 探测
python3 batch_run.py --retries 1          # 生成（FL2VA 优先，失败降级 T2V）
python3 local_conform.py --fill-missing  # 本地 lanczos 1080p
python3 verify_clip.py ../assets/h3/raw/H*_raw.mp4 --frames-dir ../assets/h3/frames
python3 verify_clip.py ../assets/h3/H??.mp4 --frames-dir ../assets/h3/frames --expect 1920x1080
python3 make_report_ep08.py               # 本报告 + manifest 定稿
```
