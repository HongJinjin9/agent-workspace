# MotionGit「酷炫科技风」模板使用记录（原始证据，时间均为 UTC）

> 本文件记录 vstudio-media 在 VCP「V视听」演示片制作中，**真实使用**
> [motiontemplates/385712](https://github.com/motiontemplates/385712) 模板包的过程与命令。
> 成片与工程信息见 `README.md`。

## 0. 环境事实（本机）

| 项 | 值 |
| --- | --- |
| Node | v24.21.0（模板要求 22+ ✅） |
| Python | 3.11（adapter 要求 3.11+ ✅） |
| uv | 0.11.15（`/home/admin/.local/bin/uv`） |
| ffmpeg | 7.0.2-static（imageio_ffmpeg，`/home/admin/.local/bin/ffmpeg`）；**无 drawtext，无可用 ffprobe** |
| Chrome | `chrome-headless-shell` 155.0.8059.39（`/home/admin/.dsh/.browser-kernel/chrome-headless-shell-linux64/chrome-headless-shell`） |
| 中文字体 | `/home/admin/.fonts/NotoSansCJKsc-Regular.otf`（Noto Sans CJK SC） |
| 模板包 | `kinetic-tech-zh.motion`（17,596,250 B，来自 repo `downloads/`，template version 0.2.7-open-beta） |

## 1. 取包

```bash
# 仓库浅克隆（后台进行；同时用 GitHub API 读取文档）
git clone --depth 1 https://github.com/motiontemplates/385712.git /tmp/motion385712
# 直接下载中文版 .motion 包（比整仓库快）
curl -sL -o /tmp/motion-dl/kinetic-tech-zh.motion \
  https://github.com/motiontemplates/385712/raw/main/downloads/kinetic-tech-zh.motion
mkdir -p /tmp/motion385712/kinetic-zh && cd /tmp/motion385712/kinetic-zh
unzip -q /tmp/motion-dl/kinetic-tech-zh.motion
```

模板包结构（解压后 28MB）：`motion.json / guide.json / CREATION.md / adapter.py / render.mjs / mix.py /
chrome.mjs / core/（catalog.json、content.schema.json、engine js、assets、native_audiolib.py）/ examples/text-only.json`。

## 2. 渲染方式（读源码得出）

- `adapter.py`：**真实制作入口**。`plan`（按参数生成分镜计划）→ `prepare`（把用户输入绑定为 instance：
  `settings.json` + `user-input.js` + 复制 core）→ `preview`（Chrome 截图单帧）→ `render`（`render.mjs`
  逐帧截图 + ffmpeg 编码）→ `mix.py`（合成模板原生动效/旁白/BGM，输出 `-with-audio.mp4`）。
- `render.mjs`：启动本地 HTTP server 提供 instance 静态文件，用 `playwright-core` 启动 headless Chrome 打开
  `index.html`，每帧 `page.evaluate(renderAt(t))` 后 `page.screenshot({type:'jpeg'})`，
  把 JPEG 帧通过 stdin 管道喂给 `ffmpeg`（`-f image2pipe -vcodec mjpeg -framerate 60`）编码为 H.264。
  即：**HTML/Canvas 逐帧合成 + Chrome 截图 + ffmpeg 编码**。
- 输出规格：1920×1080、60fps；`mix.py` 用 numpy/scipy/pyloudnorm 生成原生 SFX 并混音（48kHz）。
- 依赖：`npm ci`（playwright-core 1.64.0，3 秒装完）；`uv run`（numpy/scipy/soundfile/pyloudnorm/jsonschema，
  首次自动装 12 个包）。

## 3. 必须做的一处兼容性修改（已记录 diff 备份）

本机 ffmpeg 7.0.2 已移除 `scale` 滤镜的 `in_primaries/...` 选项（这是模板 render.mjs 里为更新版 ffmpeg 写的
色彩转换链），原命令直接报 `Option not found` 并导致 EPIPE。修改仅限编码参数，渲染逻辑不变：

```diff
- const gamma='scale=in_primaries=bt709:in_transfer=iec61966-2-1:in_range=full:out_primaries=bt709,
-   out_transfer=iec61966-2-1:out_color_matrix=bt709:out_range=full,format=yuv444p,
-   colorspace=...,format=yuv420p,sidedata=mode=delete';
+ const gamma='scale=out_color_matrix=bt709:out_range=tv,format=yuv420p,sidedata=mode=delete';
```

原文件备份：`/tmp/vstudio-media/motiongit/render.mjs.orig`。
注意 `integrity.json` 覆盖 render.mjs，所以修改后必须**重新 prepare** 生成新 instance（本记录用 `instance2`）；
adapter 的 `candidateContentDigest` 校验才会一致。

另：adapter 调 `ffprobe` 做媒体探测，而本机 ffprobe 不可用，故提供 shim
`/tmp/vstudio-media/bin/ffprobe`（解析 `ffmpeg -i` 输出，字段名与 ffprobe 对齐）。

## 4. 实际命令

```bash
export PATH=/tmp/vstudio-media/bin:$PATH          # ffprobe shim
export CHROME=/home/admin/.dsh/.browser-kernel/chrome-headless-shell-linux64/chrome-headless-shell

cd /tmp/motion385712/kinetic-zh
npm ci

# 内容输入：/tmp/vstudio-media/motiongit/user.json（中文文案 B1–B4，40s，旁白+BGM 音轨文件）
uv run adapter.py plan   --input /tmp/vstudio-media/motiongit/user.json --out /tmp/vstudio-media/motiongit/plan.json
uv run adapter.py prepare --input /tmp/vstudio-media/motiongit/user.json --out /tmp/vstudio-media/motiongit/instance2
uv run adapter.py preview --instance /tmp/vstudio-media/motiongit/instance2 --out /tmp/vstudio-media/motiongit/preview-t2.png --time 2
uv run adapter.py render  --instance /tmp/vstudio-media/motiongit/instance2 --out /tmp/vstudio-media/motiongit/final-kinetic-zh.mp4
```

`plan.json` 关键输出（真实）：`duration_s=40, frames=2400, width=1920, height=1080, fps=60`，
spans=B1 0–11s / B2 11–21s / B3 21–31s / B4 31–40s，
inputs=voice(`voice-40s.wav`, sha256 09b40412…)、music(`bgm-40s.wav`)。

## 5. 素材与音频（vstudio-media 原创/生成）

- 中文旁白 4 段：`edge-tts --voice zh-CN-XiaoxiaoNeural`，时长 10.13s / 7.42s / 8.09s / 4.34s；
  按场景起点 0.3/11.2/21.2/31.3s 排布，`apad` 补到 40.00s → `audio/voice-40s.wav`（48kHz 立体声）。
- BGM：ffmpeg `aevalsrc` 合成的 A 小调氛围垫乐（110/164.81/220/261.63/329.63Hz 正弦叠加 + lowpass +
  tremolo + 淡入淡出），40.00s → `audio/bgm-40s.wav`。原创，无第三方素材。
- 画面文案（B1–B4）全部为本项目自写中文，由模板的真实文字表达单元（basic.js B1–B4）排版渲染。

## 6. 预览帧（证明模板真实渲染中文）

`/tmp/vstudio-media/motiongit/preview-t2.png`：1920×1080，金属质感主标题「V视听」、
副标题两行中文、HUD 角标/时间码，中文无乱码。
