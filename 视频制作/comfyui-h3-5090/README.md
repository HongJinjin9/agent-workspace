# ComfyUI H3 视频版（优云智算 · RTX 5090）实测与接入说明

> 状态：**实测记录 + 接入方案**，待主人评审后提交。
> 实测时间：2026-11-12 13:01–14:01（按小时计费的 1 小时窗口）
> 应用：`ComfyUI H3 视频版` ｜ 应用编号 `2120743590090412032` ｜ 入口 `https://wp08.unicorn.org.cn:24909`
> GPU：RTX 5090 ×1（32 GB 显存）｜ 计费：按小时，约 **2840 脑力值/小时（≈ ¥2.84/h）**

本文回答三个问题：**能不能登、能不能跑、对 `agent-workspace` 的视频制作有什么用**。
所有数字都是在这台机器上实测的，不是厂商宣传值；下面每条结论都能用 `tools/comfy_client.py` 复现。

---

## 一、结论速览

| 问题 | 结论 |
| --- | --- |
| 能否登录 | **能**。门禁是自研 `WyfGate`（不是 JupyterHub），账号密码换 `wyfgate` cookie，7 天有效；HTTP API 与浏览器同一套 |
| 能否操作 ComfyUI | **能**。ComfyUI 0.36.0 + 2394 个节点，HTTP API 可读 `/system_stats`、`/object_info`、`/models`、提交 `/prompt`、下载 `/view` |
| 单卡能不能跑 MiniMax H3 | **能，而且是刚好**。int8 量化 + 8 步加速 LoRA，5 秒 768p 实测 **显存占用 31 GB / 32 GB**（空转时只剩 0.34 GB），24 GB 卡跑不动这套配置 |
| 出片速度 | 864×480 / 5 s / 8 步：**108 秒冷启 / 61.5 秒热**；1280×736 / 5 s：**220 秒**；10 s 版：177 秒 |
| 产物规格 | 480×864（竖屏）/ 864×480 / 1280×736，24fps，H.264 + **AAC 立体声音轨（32 kHz）**——H3 一次前向同时出画面和环境声/音效 |
| 对第 04 期的价值 | **直接可用**：S2 积水倒影、S4 雨滴甩出、S3 夜间车内这类「Pexels 找不到、程序化做不出」的镜头，实测 1–4 分钟一条（共 11 次实测见 §五） |
| 主要限制 | 开放权重上限约 768p（**已实测帧级超分补到 1080p**，见 T10）；单次 5–15 秒（**已实测尾帧续接**，见 T11）；车牌/文字会乱码；**商用需 Comfy 的 MiniMax 商业许可**（见 §七） |

> 一句话：**这台机器补的正是「缺口清单」里最难补的那 40% 画面**——它不能替代整条时间轴，但能把「减速带/积水/雨滴」三个视觉母题从「Pexels 凑」升级成「按分镜生成」。

---

## 二、机器与软件（实测）

取自 `GET /system_stats`：

| 项 | 值 |
| --- | --- |
| GPU | `NVIDIA GeForce RTX 5090`，显存 33,671,348,224 B ≈ **31.36 GiB** |
| 内存 | 96 GiB（103,079,215,104 B） |
| ComfyUI | **0.36.0**（前端 1.52.7，模板包 0.11.62） |
| PyTorch | 2.14.0+cu130 ｜ Python 3.12.3 |
| 启动参数 | `main.py --listen 127.0.0.1 --port 8189 --extra-model-paths-config /app/extra_model_paths.yaml` |
| 节点数 | **2394** 个（含 H3 相关 70 个） |
| 显存水位 | 空转 ~0.0 GB 占用；H3 int8 采样时 **31 GB 占满** |

模型库（`/models/*` 实测计数）：

| 目录 | 数量 | 与视频相关的内容 |
| --- | ---: | --- |
| `diffusion_models` | 233 | H3 系 42 个（FL2VA / Ref2VA、官方 + 社区微调、FastH3 8 步、4 步 VSA）、Wan2.1/2.2、LTX-2/2.3、HunyuanVideo 等 |
| `loras` | 607 | H3 加速/风格/运镜 LoRA 约 40 个（4 步、8 步 turbo、camera_motion、realism 等） |
| `checkpoints` | 325 | SD1.5/SDXL/FLUX/ LTX / Hunyuan3D 等 |
| `vae` | 77 | `minimax_h3_video_vae_fp16`、`minimax_h3_audio_vae_fp32`、`fast_h3_vae_noncausal_24l` 等 |
| `text_encoders` | 82 | `qwen3vl_32b_minimax_h3_*`（H3 的文本/多模态编码器，int8/nvfp4/bf16 多版本） |
| `latent_upscale_models` | 11 | `minimax_h3_latent_upscaler_3d_*`（2K 放大链路） |
| `unet_gguf` / `clip_gguf` | 24 / 5 | GGUF 量化版（低显存备用；5090 不必用） |

> 注意：这个应用是**社区整合包**，模型目录里混有大量 NSFW / 换脸 / 动漫微调。做正式内容时建议只认「官方 FL2VA / Ref2VA + 已验证加速 LoRA」这一条线（本文用的就是），别随手换社区底模——风格稳定性比多一个模型更重要。

---

## 三、怎么连（门禁 + API）

### 3.1 门禁是真的门禁，不是 ComfyUI 自带登录

```
GET  /            → 401 {"error":"unauthorized","detail":"login required"}   （服务端 WyfGate/1）
GET  /login       → 200  手绘风登录页（用户名 / 密码两栏）
POST /login  u=…&p=…&next=/  → 302 + Set-Cookie: wyfgate=<token>; HttpOnly; Secure; Max-Age=604800
带上 cookie 后 → 200  ComfyUI 前端
```

> 凭据只走环境变量 `H3_USER` / `H3_PASS`，**不写进仓库**；应用按小时租用，到期即失效。

- 密码错会 302 到 `/login?err=1`；cookie 失效会退回 401。都不需要浏览器，`requests` 足够。
- **应用没开机时**：门禁仍然在线（返回 401），登录也仍然成功，但所有业务路径返回 **502 Bad Gateway（Caddy，空 body）**——这就是 13:00 之前打不开的原因，不是账号问题。`comfy_client.py` 对这种情况会直接抛 `APP DOWN`。

### 3.2 客户端

`tools/comfy_client.py`（依赖 `requests`，本机已装）：

```bash
export H3_USER=... H3_PASS=...
python3 tools/comfy_client.py stats                 # 显卡/版本/内存
python3 tools/comfy_client.py nodes --grep H3       # 节点清单
python3 tools/comfy_client.py models                # 模型目录
python3 tools/comfy_client.py run workflows/t2v_api.json --out out/   # 直接提交 API 工作流
```

`run` 用的是 ComfyUI 的 API 格式（UI 里「导出 (API)」那份 JSON），不是界面工作流；两者转换本文已做完，见 `workflows/t2v_api.json`。

### 3.3 五分钟跑通第一条（最短路径）

```bash
cd 视频制作/comfyui-h3-5090
export H3_USER=<应用登录账号> H3_PASS=<应用登录密码>

python3 tools/comfy_client.py stats          # 1. 确认实例在跑（502 就是没开机）
python3 tools/comfy_client.py run workflows/t2v_api.json --out out/ \
  --set '140:131.prompt=你的提示词'          # 2. 默认 864×480 / 5s / 8 步，约 1–2 分钟
```
产物在 `out/`，自带音轨。换竖屏加 `--set '115.aspect_ratio=9:16 (Portrait Widescreen)'`；换 10 秒加 `--set '140:133.value:num=10'`。

### 3.4 API 工作流里，参数分别在哪（改 prompt 必看）

`workflows/t2v_api.json` 是**子图展开后**的 23 个节点，节点 id 带 `140:` 前缀。常用的几个：

| 想改什么 | 节点 id | inputs 字段名 | 说明 |
| --- | --- | --- | --- |
| 提示词 | `140:131` | `prompt` | MiniMaxH3ImageToVideo 的文本输入 |
| 时长（秒） | `140:133` | `value` | 浮点秒数，经 `140:132` 换算成帧长（5–15 内最稳） |
| 步数 | `140:138` | `value` | 加速 LoRA 模式下为 8 |
| 是否用加速 LoRA | `140:139` | `value` | `true` = LoRA + 8 步（快）；`false` = 底模 + 20 步（慢而稳） |
| 随机种子 | `140:129` | `noise_seed` | 同种子 + 同提示词可复现 |
| 分辨率 | `115` | `megapixels` / `aspect_ratio` | 0.4 MP→864×480；0.9 MP→1280×736（16:9） |
| 帧率 | `140:130` | `fps` | 默认 24 |
| 底模 | `140:127` | `unet_name` | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` |
| 加速 LoRA | `140:134` | `lora_name` | `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` |
| 文本编码器 | `140:128` | `clip_name` | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` |
| 输出文件名前缀 | `92` | `filename_prefix` | 默认 `video/MiniMax_H3` |

示例（把时长改 10 秒、换提示词）：

```bash
python3 tools/comfy_client.py run workflows/t2v_api.json --out out/ \
  --set '140:133.value:num=10' \
  --set '140:131.prompt=Static cinematic night shot: ...'
```

---

## 四、预置工作流（应用自带 27 个，已可读）

应用在 `user/default/workflows/` 下预置了 27 个中文命名的工作流。可直接在 UI 左侧 **Workflows** 面板搜索加载：

| 场景 | 工作流 |
| --- | --- |
| 文生视频 | `文生视频·双加速4步`、`文生视频·FASTVSA4步加Realism`、`文生视频·GGUF量化版` |
| 图生视频 | `单图参考生视频·双加速4步`、`首帧生视频·双加速4步`、`尾帧生视频·双加速4步`、`首尾帧生视频·双加速4步` |
| 多图/参考 | `多图参考生视频·9图3视频3音频`、`多图参考生视频·FASTVSA4步加Realism`、`参考生视频·HybridV1加SLA·不油不崩脸` |
| 长视频 | `长视频·首段生成`、`长视频·自动无缝接续` |
| 画质 | `参考图生视频·2K放大`、`图生视频·FaceRefine加VOSR2面部修复` |
| 控制 | `ControlNet·Canny加Pose`、`ControlNet·Lineart加Pose`、`ControlNet视频参考·GGUF量化版`、`图生视频·视频参考加ControlNet` |
| 编辑/换脸 | `局部重绘·SAM3自动遮罩`、`换脸1/2/3…`、`替换视频中人物·人脸加服装`、`视频换装` |
| 其他 | `场景8视图`、`角色6视图加360度旋转` |

另外 ComfyUI 官方模板库（`/templates/index.json`，22 个 H3 相关模板）也可用，如 `video_minimax_h3_t2v` / `video_minimax_h3_i2v` / `video_minimax_h3_r2v` / `video_fastvideo_fasth3_t2v`，本文把其中 5 个落盘到 `workflows/templates/` 备查。

> 实测提示：官方模板用的是 subgraph（子图）结构，`/prompt` 提交时必须**展开**成 23 个扁平节点；直接在 API 里贴子图会报错。展开后的成品见 `workflows/t2v_api.json`。

---

## 五、实测记录

### 5.1 测试 1：文生视频 864×480 / 5s（对应第 04 期 S2「积水倒影」）

| 项 | 值 |
| --- | --- |
| 工作流 | 官方 `video_minimax_h3_t2v`（双加速 8 步） |
| 底模 | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` |
| 加速 LoRA | `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors`（strength 1.0） |
| 文本编码器 | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` |
| VAE | `minimax_h3_video_vae_fp16` + `minimax_h3_audio_vae_fp32` |
| 分辨率 / 时长 / 步数 | 864×480（0.4 MP，16:9）/ 5 s / 8 步 |
| **耗时** | **108.4 s**（`execution_start` → `execution_success`，服务端时间戳） |
| 产物 | `evidence/t1_t2v_864x480_5s.mp4`，864×480 / 24 fps / 5.17 s / H.264 + AAC 32 kHz 立体声 / 0.51 MB |
| 单条成本 | ≈ 2.84 元/h × 108 s ÷ 3600 ≈ **¥0.085/条** |

画面（`evidence/f1_*.jpg` 为抽帧）：夜间湿路面、车尾灯在积水中倒影、景深与色调接近电影感，**结构完全符合 S2 分镜要求**；已知瑕疵是车牌文字乱码（AI 文字通病，后期遮掉即可）。

### 5.2 测试 2：文生视频 768p / 5s（对应第 04 期 S4「雨滴被甩出」）

| 项 | 值 |
| --- | --- |
| 提示词 | 见 §6.2「S4-1 雨滴 · jerk」 |
| 分辨率 / 时长 / 步数 | 1280×736（0.9 MP，16:9）/ 5 s / 8 步 |
| **耗时** | **220.2 s**（3 分 40 秒） |
| 产物 | `evidence/t2_t2v_720p_5s.mp4`，1280×736 / 24 fps / 5.17 s / H.264 + AAC 32 kHz / 1.37 MB |
| 单条成本 | ≈ **¥0.174/条** |

抽帧（`evidence/f2_*.jpg`）：挡风玻璃雨滴 + 失焦城市灯光 bokeh，雨滴在加速瞬间被拉成斜线，视觉完全符合「jerk 的可见后果」。**0.4 MP → 0.9 MP，耗时从 108 s 涨到 220 s（约 2 倍），显存始终贴顶**——说明瓶颈在显存带宽/换页，不在算力，分辨率要省着用。

### 5.3 测试 3：图生视频（首帧续接，864×480 抽帧当首帧）

| 项 | 值 |
| --- | --- |
| 输入 | T1 的抽帧 `f1_3.0.jpg`（车尾 + 积水倒影） |
| 工作流 | 官方 `video_minimax_h3_i2v` → `LoadImage → ImageScaleToTotalPixels → 子图 → SaveVideo` |
| 提示词 | 「同一机位，车开远、水波平息、尾灯渐隐」的续接描述（英文） |
| **耗时** | **64.2 s**（模型已热加载，显存不需要重新分配） |
| 产物 | `evidence/t3_i2v_640x640_5s.mp4`，640×640 / 24 fps / 5.17 s / 带音轨 |
| 单条成本 | ≈ **¥0.051** |

效果（`evidence/f3_*.jpg`）：首帧的车真的开远了，水面从荡漾变回镜面，机位与色调保持一致——**「抽一帧 → 续 5 秒」这条路是通的**，可以拿现有 Pexels 素材的任意一帧做起点，把「会轻微漂移的静图」变成真运动。

### 5.4 测试 4：中文提示词

| 项 | 值 |
| --- | --- |
| 提示词 | 中文（与 §6.2 S2-1 同义） |
| **耗时** | **61.6 s**（与测试 3 基本一致，说明中文不会变慢） |
| 效果 | `evidence/f4_*.jpg`：车尾灯、积水倒影、雨丝都对，构图与英文版接近 |

结论：**中文提示词可用**，不必强行翻译；但「35mm / 浅景深 / 青橙色调 / 胶片颗粒」这类镜头术语用英文更稳，实践中可以**中文描述内容 + 英文写镜头参数**混排。

### 5.5 测试 5：纯 HTTP 客户端端到端（不碰浏览器）

用 `tools/comfy_client.py run workflows/t2v_api.json` 直接提交（提示词用 S2-2「咣当」对照组）：

```
$ python3 tools/comfy_client.py run workflows/t2v_api.json --out out/ \
    --set '140:131.prompt=Night rain, wet asphalt, a dark sedan hits a speed bump and the body keeps rocking ...'
[run] prompt_id=d939cfd4-1120-4692-8140-b674c4135e44
[run] elapsed=61.5s
[run] saved out/MiniMax_H3_00005_.mp4 (0.48 MB)
```

**结论：整条链路（门禁登录 → 提交 → 轮询 → 下载）纯 Python 可跑，不依赖浏览器**，可用于批量脚本。产物 `evidence/t5_t2v_864x480_clang.mp4`，864×480 / 5.17 s，比 T1 的"咚"版本水花更大、倒影抖得更久——对照组效果成立。

### 5.6 测试 6：10 秒时长（`140:133.value=10`）

| 项 | 值 |
| --- | --- |
| 分辨率 / 时长 / 步数 | 864×480 / **10 s** / 8 步 |
| **耗时** | **177.0 s** |
| 产物 | `evidence/t6_t2v_864x480_10s.mp4`，864×480 / 10.13 s / 带音轨 |
| 单条成本 | ≈ **¥0.140** |

结论：**10 秒能跑**（帧长按 24fps 换算成 240 帧并补齐到 17 的倍数），耗时约为 5 秒的 2.9 倍。画面（`evidence/f6_3.0.jpg`）是雨夜路边停着的车，车身水珠、路灯在湿路面上的长条反光都成立，适合做 S5 收束的静默镜头。

> 实测口径：时长改的是 `140:133`（PrimitiveFloat，秒），不是 `140:131.length`（那是帧数，由 `140:132` 的数学表达式算出）。

### 5.7 测试 7：结构化提示词（官方 `integrated_multimodal_description` 格式）

官方模板里的提示词不是一段话，而是三段式（详见 `prompts.md` §0.1）：

```text
integrated_multimodal_description: [Shot 1] … [Shot 2] At 00:02.400, …
overall_soundscape: …
non_diegetic_music: …
```

实测（FastH3 8 步模板，864×480 / 5 s）：**61.0 s** 出片，`evidence/t7_fasth3_structured_2shots.mp4`——5 秒里真的按 `At 00:02.400` 切了第二个镜头（车开走 + 水波平息），音轨里也有落水声与雨声。

但要记一笔：**结构化写法不等于听话**。这条 prompt 明写 "at night"，成片却是黄昏/白天；H3 对**时间/光线类条件**的服从度明显弱于对**动作/机位**的服从度。所以：

- 想要夜景，别只写在形容词里——**用首帧图锁死影调**（I2V 比纯 T2V 稳）；
- 动作、机位、切镜时点用结构化写法最有效；
- 光线、色调、风格类要求，靠首帧/参考图 + 后期调色，不要指望文字。

### 5.8 测试 8：9:16 竖屏（视频号/抖音母版格式）

| 项 | 值 |
| --- | --- |
| 参数 | `aspect_ratio = 9:16 (Portrait Widescreen)`，0.4 MP → **480×864** |
| 提示词 | 雨夜街道、车迎面驶过积水、车灯水花、霓虹反光（英文） |
| **耗时** | **100.0 s** |
| 产物 | `evidence/t8_t2v_vertical_9x16.mp4`，480×864 / 5.17 s / 24 fps / 带音轨 |
| 单条成本 | ≈ **¥0.079** |

效果（`evidence/f8_2.0.jpg`）：竖屏构图成立，车灯水花、湿地反光、霓虹招牌都到位。**一个副作用要注意**：竖屏街景会自动生成大量招牌文字，而 H3 写不对字（图中日文招牌是乱码）——做 9:16 时要么选无招牌场景，要么后期裁掉/遮掉。

> 竖向出片对 `ep01–ep03` 那条竖屏系列直接可用；第 04 期是 16:9，用上面的横屏参数。

### 5.9 测试 9：首尾帧双控（FLF2V，把镜头运动锁死）

| 项 | 值 |
| --- | --- |
| 做法 | I2V 模板 + 再加一个 `LoadImage` 接 `last_frame`（节点 105 的输入 1） |
| 首帧 | `f1_3.0.jpg`（车正过坎、水波荡漾） |
| 尾帧 | `f3_2.5.jpg`（车已走远、水面平静） |
| **耗时** | **71.4 s** |
| 产物 | `evidence/t9_flf2v_controlled.mp4`，864×480 / 5.17 s / 带音轨 |

验证：首帧 `f9_0.05.jpg` 与输入首帧一致（车在近处、水花大），尾帧 `f9_4.9.jpg` 与输入尾帧一致（车远去、水面基本平静）。

**这条对第 04 期最有价值**：分镜里「车从 A 位置开到 B 位置」「后视镜里地平线转到某个角度」这类**有明确起止状态**的镜头，用首尾帧双控比纯文字描述可靠得多——镜头运动被两头钉住，中间由模型补。

### 5.10 测试 10：768p → 1080p 超分链路（补测）

H3 开放权重上限约 768p，而交付是 1080p。试了两条路，选了一条稳的：

- ❌ **H3 latent 二段放大**（`参考图生视频·2K放大` 工作流）：它的 JSON 被门禁挡着读不到，重建子图风险太高，没敢赌机器时间；
- ✅ **解码后帧级超分**：`LoadVideo → GetVideoComponents → 4x-UltraSharp 超分 → lanczos 缩到 1920×1080 → CreateVideo(带原音轨) → SaveVideo`。

| 项 | 值 |
| --- | --- |
| 输入 | `t1_t2v_864x480_5s.mp4`（864×480 / 5.17 s） |
| 超分模型 | `4x-UltraSharp.pth` → lanczos 缩到 1920×1080 |
| **耗时** | **107.5 s** |
| 产物 | `evidence/t10_upscale_1080p.mp4`，**1920×1080** / 5.17 s / 24 fps / **原音轨保留** |
| 单条成本 | ≈ **¥0.085** |

**效果不是玄学**：局部 1:1 对比（左 lanczos 直放、右 ESRGAN 超分后下采样）——`evidence/t10_compare_lanczos_vs_esrgan.jpg`。同一块路面/水面，右侧纹理与倒影边缘明显更实；拉普拉斯方差 19.1 vs 3.1（**+509%**，同尺寸对比，数值仅供排序参考）。

> 结论：**「生成 768p + 帧级超分」这条路能补上 1080p**，代价是每条片子多 1–2 分钟机器时间（约 ¥0.09）。脚本在 `tools/upscale_video.py`，任何视频都能用。

### 5.11 测试 11：长视频接续（5 s + 5 s 无缝拼接，补测）

H3 单次只给 5–15 秒，超过就要接。做法：**取上一段的最后一帧，当下一段的首帧**（I2V）。

| 项 | 值 |
| --- | --- |
| 输入首帧 | `evidence/lastframe_t1.jpg`（T1 的最后一帧） |
| **耗时** | **125.5 s** |
| 产物 | `evidence/t11_continuation.mp4`，864×480 / 5.17 s |
| **接缝实测** | 续接片段首帧 vs 输入尾帧：**MAE = 2.5/255，相关系数 0.998** |

也就是说，两段拼起来**肉眼基本看不出接缝**（首帧几乎完全复现输入帧），剩下的差异主要来自第二段自己的运动。

**用法**：长镜头按 5 秒切段 → 每段用上一段尾帧续 → 拼接时把重叠帧裁掉 1–2 帧即可。注意每段都要**同提示词、同 seed 策略、同分辨率**，否则色调会漂。

### 5.12 实测汇总

| # | 任务 | 分辨率 | 时长 | 步数 | 耗时 | 折算成本 | 备注 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| T1 | 文生视频（英文） | 864×480 | 5 s | 8 | **108.4 s** | ¥0.085 | 含首次加载模型 |
| T2 | 文生视频（英文） | 1280×736 | 5 s | 8 | **220.2 s** | ¥0.174 | 0.9 MP，显存贴顶 |
| T3 | 图生视频（首帧续接） | 640×640 | 5 s | 8 | **64.2 s** | ¥0.051 | 模型已热 |
| T4 | 图生视频（中文提示词） | 640×640 | 5 s | 8 | **61.6 s** | ¥0.049 | 中文可用 |
| T5 | 纯 HTTP 客户端（英文） | 864×480 | 5 s | 8 | **61.5 s** | ¥0.049 | 验证脚本链路 |
| T6 | 纯 HTTP 客户端（10 秒） | 864×480 | 10 s | 8 | **177.0 s** | ¥0.140 | 时长翻倍≈耗时 2.9 倍 |
| T7 | FastH3 + 结构化提示词 | 864×480 | 5 s | 8 | **61.0 s** | ¥0.049 | 5 秒内两镜头 |
| T8 | 文生视频 **9:16 竖屏** | 480×864 | 5 s | 8 | **100.0 s** | ¥0.079 | 竖屏母版可用 |
| T9 | **首尾帧双控**（FLF2V） | 864×480 | 5 s | 8 | **71.4 s** | ¥0.056 | 起止状态可控 |
| T10 | **768p→1080p 超分** | 1920×1080 | 5 s | — | **107.5 s** | ¥0.085 | 4x-UltraSharp + lanczos |
| T11 | **长视频接续**（尾帧→首帧） | 864×480 | 5 s | 8 | **125.5 s** | ¥0.099 | 接缝 MAE 2.5/255、corr 0.998 |

**规律**：耗时 ≈ 分辨率（像素数）× 帧数 × 步数 × 常数，且**第一次调用要额外 30–40 s 加载模型**；同一进程内连续调用明显更快（T1 108 s → T5 61.5 s，同为 864×480/5 s）。批量生产时把同分辨率、同时长的镜头排在一起，别来回切。

> FastH3（`fastvideo_fasth3_8step_v2`）和普通 H3 + 8 步 turbo LoRA 在这台机器上**速度几乎一样**（61.0 s vs 61.5 s），差别主要在画质取向；选一条固定用就行，不必来回换。

### 5.13 踩过的坑（写下来省下次的事）

| 现象 | 原因 / 处理 |
| --- | --- |
| 门禁能登录、所有页面 502、body 为空 | 应用没开机。门禁是常驻的，应用是按时计费的容器；`comfy_client.py` 会报 `APP DOWN` 而不是让你以为密码错了 |
| 官方模板在 UI 里能跑，API 提交报错 | 模板用 **subgraph**，`/prompt` 只认展开后的扁平节点。先加载模板、`graphToPrompt()` 展开，或在 UI 里导出 API 版 |
| 首帧是 16:9，出来却是正方形 | `ResolutionSelector` 的 `aspect_ratio` 覆盖首帧比例。做 I2V 时把 `aspect_ratio` 设成首帧同比例（或 `megapixels` 与首帧一致） |
| 想从 `/userdata/…json` 读预置工作流，一直 404 | 该接口被门禁挡住。可读的是「目录列表」；单文件内容改用 UI 侧 `graph.configure()` / `graphToPrompt()` 读取，或直接用本文落盘的 `workflows/` |
| 视频里的车牌乱码 | H3 对文字渲染不可控。避开带文字的近景，或后期遮挡；不要指望它写对中文 |
| 显存只剩 0.3 GB，怕它 OOM | 实测能稳定跑完 5 秒 768p；但不要同时开第二个任务，也别在采样时用浏览器重跑工作流 |

---

## 六、对 `agent-workspace` 视频制作的具体用法

### 6.1 现在缺什么、这台机器补哪块

`自媒体稿/第04期-你的身体比参数表更懂车.md` §6.2 的缺口清单，逐条对上：

| 稿件缺口 | 原方案 | 这台机器怎么补 |
| --- | --- | --- |
| 减速带/颠簸路面实拍 | Pexels 补 B-roll | 文生视频：慢速过坎 + 车身起伏，可控频率与阻尼（S2 对比「咚 / 咣当」两版） |
| 积水倒影 | Pexels 补雨夜路面积水 | **已实测**：车尾灯倒影荡开又收敛，正是 S2 曲线的物理载体 |
| 弯道侧倾/后视镜 | Pexels / `car_interior_night` 加倾斜 | 图生视频：拿现有 `car_interior_night.mp4` 抽帧当首帧，加「车身向外倾、地平线转动」 |
| 雨滴打在挡风玻璃 | 复用 `rain_window` | **已实测**（T2）：加速瞬间雨滴被拉成斜线，jerk 的可见证据 |
| 三条曲线动效 | 程序化（PIL/numpy） | 仍建议程序化——曲线要跟数学函数严格对应，生成模型做不准 |

**分工原则**（与《视频制作优化意见》§3.1 一致）：**实拍质感镜头交给生成，数据/文字/精确图形留给程序化**。H3 不擅长数字与文字（实测车牌即乱码），正好和现有证据链互补。

### 6.2 第 04 期可直接粘贴的提示词（含结构化写法见 `prompts.md`）

写法：**镜头语言 + 物理后果 + 声音** 三段式，英文出片更稳（H3 训练语料以英文为主，中文也能跑但术语容易漂）。提示词里不要写「4K/8K」这类空话，写清楚**运动因果**——这正是《优化意见》§3.2 意见 A 要求的「为什么现在动」。

**S2-1 减速带 · 积水倒影（已实测出片）**

```text
Cinematic live-action night shot: a dark grey sedan drives slowly over a speed bump on a wet
suburban road right after rain. Foreground: a shallow puddle on the asphalt reflecting the car
body and red tail lights; the reflection ripples outward in circular waves as the car passes,
then gradually settles. Low camera almost at ground level, 35mm lens, shallow depth of field,
teal-and-orange cinematic grading, subtle film grain, realistic physics, no text, no people
visible. Audio: one low deep thud as the wheel hits the bump, then a soft water splash and tire
hiss on wet asphalt.
```

**S2-2 同一段路的对照组（阻尼不足＝「咣当」）**：把上面 `one low deep thud … then settles` 换成 `a sharp clang, followed by the body continuing to rock back and forth three times`，其余不动，两条并排出对照。

**S3-1 后视镜 · 侧倾**

```text
Cinematic shot from the driver's seat at night: the rear-view mirror fills the frame, showing the
car body and the horizon behind; the car enters a long right-hand bend at speed, the horizon in the
mirror tilts slowly and steadily, the body rolls outward, then settles as the steering unwinds.
Smooth continuous motion, no cuts, 50mm lens, shallow depth of field, dashboard glow, teal-orange
grading, film grain, no faces, no text. Audio: tire roll on asphalt, a faint wind rush rising
through the corner.
```

**S4-1 雨滴 · jerk**

```text
Cinematic macro shot from inside a car at night: rain droplets on the windshield, out-of-focus city
lights bokeh behind. The car accelerates smoothly; the raindrops suddenly slide and streak sideways
across the glass, water beads whipping upward with the acceleration, then settle into a slow drift
as speed becomes constant. Shallow depth of field, 85mm lens, teal-orange grading, film grain,
realistic fluid physics, no people, no text. Audio: muffled rain patter on glass, a low electric
motor whine rising, a subtle water swipe.
```

### 6.3 推荐生产流程（和现有管线拼接，不推翻）

```
分镜（shots.json）→ 挑「需要实拍质感」的镜头 → ComfyUI 生成 5s 素材（768p）
   → 下载 → 本机 ffmpeg：放大到 1080p / 统一调色颗粒遮幅 / 与旁白对齐
   → 进现有 timeline.json → finalize.py 出片
```

- **分辨率**：开放权重上限约 768p，2K 要走 `参考图生视频·2K放大`（latent upscaler）。第 04 期是 1080p 横屏，建议生成 768p 后 lanczos + 轻微锐化放大，和现有 B-roll 的放大策略保持一致。
- **时长**：单条 5–15 s。超过 15 s 用 `长视频·自动无缝接续`（尾帧接首帧）；但接缝仍是风险点，建议**一条只做一个动作**，靠剪辑而不是靠模型拉长。
- **音频**：H3 自带音轨（音效/环境声），可当**音效素材**用；但旁白仍是 edge-tts 那条线，不要把 H3 的人声当旁白。
- **一致性**：同一场景多条用**同一 seed** + 同一提示词前缀；镜头间靠首帧/尾帧衔接，不靠「重新生成一条相似的」。
- **版权/匿名**：生成画面不得出现真人可识别面孔（本期不出镜，天然满足）；车牌照、地名、品牌标要用画面遮挡或后期涂掉。

### 6.4 成本

| 项 | 数字 |
| --- | --- |
| 计费 | 约 2840 脑力值/h ≈ **¥2.84/小时** |
| 一条 5 s / 864×480 / 8 步 | 108 s ≈ **¥0.085** |
| 一条 5 s / 768p / 8 步 | 见 §5.2（按实测秒数折算） |
| 一条 3 分钟片子的 10 个生成镜头 | 约 20–40 分钟机器时间 ≈ **¥1–2** |

结论：**试错成本极低**。真正贵的不是 GPU 费，是「选哪个镜头值得生成」的判断——这和《优化意见》「先做短样、别全片重写」是一个道理。

---

## 七、风险与合规（必须看）

1. **商业许可**：MiniMax H3 是开放权重，但**本地权重的商用输出需通过 Comfy 购买 MiniMax 商业许可**（Comfy 是唯一官方经销商）。本系列是个人自媒体、有广告分成/带货可能，属于商用场景，**发布前必须确认许可状态**；不确定时优先走「AI 辅助画面占比低 + 明确声明」的路径。
2. **AI 声明**：第 03 期 P0 教训——片尾要有**画面 + 旁白双重声明**。用了生成画面后，声明措辞建议升级为「部分画面由 AI 生成」。
3. **模型合规**：应用内置大量社区微调（含 NSFW、换脸）。**不要用换脸/去衣类工作流**；正式产出只用官方 FL2VA/Ref2VA 与已核实来源的加速 LoRA。
4. **数据安全**：这台机器是租用实例，按小时计费、停机 3 天后释放。**不要上传未发布的稿件、真实姓名、联系方式**；生成的提示词也不要夹带个人信息。
5. **稳定性**：门禁 cookie 7 天有效，但实例停机即失效（502）。长任务要写成「提交 → 轮询 → 下载」的可重试脚本，不能假设会话一直在。

---

## 八、复现清单

```
comfyui-h3-5090/
├── README.md                     # 本文
├── tools/comfy_client.py         # 门禁登录 + ComfyUI API 客户端（stats/nodes/models/run/history）
├── tools/upscale_video.py        # 768p → 1080p 帧级超分（LoadVideo→4x-UltraSharp→lanczos→带音轨重封装）
├── workflows/
│   ├── t2v_api.json              # 实测用的 23 节点 API 工作流（可直接 /prompt 提交）
│   ├── t2v_api_from_history.json # 服务端 /history 原始记录（热更新用）
│   ├── i2v_api_from_history.json # 图生视频那次的 /history 记录
│   ├── original/                 # 应用自带 27 个工作流的元数据清单（内容接口被门禁挡住）
│   └── templates/                # ComfyUI 官方 H3 模板原文（t2v / i2v / r2v / fasth3 / multiframe）
└── evidence/
    ├── t1_t2v_864x480_5s.mp4     # 测试 1 产物（车尾灯积水倒影，带音轨）
    ├── t2_t2v_720p_5s.mp4        # 测试 2 产物（雨滴挡风玻璃，1280×736）
    ├── t3_i2v_640x640_5s.mp4     # 测试 3 产物（首帧续接）
    ├── t4_i2v_640x640_zh.mp4     # 测试 4 产物（中文提示词）
    ├── t5_t2v_864x480_clang.mp4  # 测试 5 产物（纯 HTTP 客户端提交，"咣当"对照组）
    ├── t6_t2v_864x480_10s.mp4    # 测试 6 产物（10 秒时长）
    ├── t7_fasth3_structured_2shots.mp4  # 测试 7 产物（结构化提示词，5 秒两镜头）
    ├── t8_t2v_vertical_9x16.mp4  # 测试 8 产物（9:16 竖屏）
    ├── t9_flf2v_controlled.mp4   # 测试 9 产物（首尾帧双控）
    ├── t10_upscale_1080p.mp4     # 测试 10 产物（768p→1080p 超分）
    ├── t10_compare_lanczos_vs_esrgan.jpg  # 超分对比图（左 lanczos / 右 ESRGAN）
    ├── t11_continuation.mp4      # 测试 11 产物（尾帧续接）
    ├── lastframe_t1.jpg          # T11 的输入首帧
    ├── f1_*.jpg … f11_*.jpg      # 各产物抽帧
    ├── ui_graph_i2v_fitted.png   # ComfyUI 里的 I2V 子图 + 出片预览
    └── ui_templates_1920x1080.png# 模板库（H3 T2V / I2V / R2V 等）
```

复现步骤：

```bash
export H3_USER=... H3_PASS=...
python3 tools/comfy_client.py stats
python3 tools/comfy_client.py run workflows/t2v_api.json --out out/ \
  --set '140:131.prompt=<你的提示词>' --set '140:131.width=1280'
```

### 8.1 出片后处理（和现有管线对齐）

生成物是 24 fps / 768p 级，进第 04 期 1080p 时间轴前建议统一走一遍（参数沿用 `视频制作/README.md` 里 vibe 那套）：

```bash
# 768p → 1080p + 统一影调（teal-orange、暗角、颗粒）
ffmpeg -i in.mp4 -vf "\
scale=1920:1080:flags=lanczos,eq=contrast=1.08:saturation=1.12:gamma=0.98,\
vignette=PI/4.6,noise=alls=7:allf=t+u" \
  -c:v libx264 -crf 20 -pix_fmt yuv420p -r 24 -c:a aac -b:a 192k out.mp4
```

> 注意：生成物自带音轨，`-c:a aac` 会重编码保留；如果只用画面，加 `-an`，音效另配。

> 仓库惯例是「成片不入库」。这里保留的 11 条测试片（合计约 9.4 MB）只是**短样证据**，如果要严格守例，提交前删掉 `evidence/*.mp4`、只留抽帧 `f*.jpg` 即可，结论不受影响。

---

## 九、结论：对 v工程 agent-workspace 的增益判断

**增益是实的，但只在「画面质感」这一层，不在「结构」这一层。**

- **能提升的**：第 04 期 §6.2 缺口里的实拍质感镜头（积水、减速带、雨滴、后视镜侧倾），从「Pexels 里碰运气」变成「按分镜定制」；H3 的原生音轨还能顺手补环境声。单条 ¥0.09、2 分钟出片，试错成本比改一次渲染器低两个数量级。
- **还能顺带缓解第 03 期评审的 P1**：教员指出的「研究段/机制段纸质信息卡感」，一部分可以靠插入 1–2 个真实感镜头（雨夜路、车轮、仪表）来打断长镜头节奏，不必重做整段渲染。
- **不能替的**：三条曲线的数学精确性（必须程序化）、1080p 以上分辨率（要放大链路）、时间轴与字幕节奏（仍走现有管线）、以及「选题/核实/判断」——这恰好也是本期稿件的立意。
- **建议的下一步**：先用 §6.2 的三条提示词各出 2 个 seed，和现有 Pexels 素材做 A/B，按《优化意见》§6 的「静音观看 + 闭眼听音」两轮验收，再决定是否进第 04 期正片。
