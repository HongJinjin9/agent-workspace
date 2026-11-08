#!/usr/bin/env python3
"""第 01 期混音 v2：按场景分层的连续音乐床 + sidechain 自动压低 + 两遍 loudnorm。

参考实践（见 PR 说明 / 音频方案文档）：
- 音乐床在旁白下自动 duck（侧链压缩）：threshold≈0.012、ratio 12、attack 20ms、release 500ms
- 音乐是"一条连续床"，不在场景切换处硬切；段落间用 1.5s 交叉淡化
- 旁白合成音容易被音乐掩蔽：床在旁白下再低约 16dB
- 目标响度 -14 LUFS / TP -1.5dBTP / LRA≤11，两遍 loudnorm（第二遍 linear）
"""
import json, os, re, subprocess

ROOT = '/app/vedio/ep01-hybrid'
FF = '/home/admin/.local/bin/ffmpeg'
TL = json.load(open(f'{ROOT}/work/timeline.json', encoding='utf-8'))
TOTAL = TL['total']
segs = TL['segments']

MUSIC = {k: f'{ROOT}/assets/music/{k}.mp3' for k in
         ['the-journey', 'silent-descent', 'cyberpunk-city', 'epical-drums-01', 'vastness']}

# 每段的音乐床：轨道、起点（秒）、床音量（相对）
PLAN = {
    'S1': ('the-journey',   0.0,  0.42),
    'S2': ('silent-descent', 2.0, 0.36),
    'S3': ('cyberpunk-city', 1.0, 0.34),
    'S4': ('cyberpunk-city', 12.0, 0.40),
    'S5': ('silent-descent', 26.0, 0.32),
    'S6': ('the-journey',   30.0, 0.55),
}
INPUTS = []
FILTERS = []
idx = 0


def add_input(args):
    global idx
    INPUTS.extend(args)
    i = idx
    idx += 1
    return i


def fmt(t):
    return f'{max(0.0, t):.3f}'


# ---------- 旁白轨 ----------
nar_inputs = []
for s in segs:
    i = add_input(['-i', os.path.join(ROOT, s['file'])])
    delay = int(round(s['vo_start'] * 1000))
    FILTERS.append(f'[{i}:a]aresample=48000,adelay={delay}|{delay}[n{i}]')
    nar_inputs.append(f'[n{i}]')
FILTERS.append(''.join(nar_inputs) + f'amix=inputs={len(nar_inputs)}:normalize=0:duration=longest[namix]')
FILTERS.append('[namix]highpass=f=80,acompressor=threshold=-18dB:ratio=2.5:attack=20:release=200[narr]')
FILTERS.append('[narr]asplit=2[narr_mix][narr_key]')

# ---------- 音乐床：按段落切片 → 交叉淡化拼接 ----------
bed_parts = []
for s in segs:
    track, off, vol = PLAN[s['id']]
    i = add_input(['-stream_loop', '-1', '-i', MUSIC[track]])
    d = s['dur']
    FILTERS.append(
        f'[{i}:a]aresample=48000,atrim=start={fmt(off)}:end={fmt(off + d + 2)},asetpts=PTS-STARTPTS,'
        f'volume={vol},afade=t=in:st=0:d=0.9,afade=t=out:st={fmt(max(0, d - 0.9))}:d=1.8[b{len(bed_parts)}]'
    )
    bed_parts.append(f'[b{len(bed_parts)}]')
# 连续拼接（相邻片段重叠 1.5s 交叉淡化）
prev = bed_parts[0]
for k in range(1, len(bed_parts)):
    lbl = f'[xf{k}]'
    FILTERS.append(f'{prev}{bed_parts[k]}acrossfade=d=1.5:c1=tri:c2=tri{lbl}')
    prev = lbl
FILTERS.append(f'{prev}highpass=f=120,equalizer=f=300:width_type=o:width=1.2:g=-2,'
               f'equalizer=f=3000:width_type=o:width=1.5:g=-1.5,volume=0.55[bed]')
# 侧链：旁白压音乐
FILTERS.append('[bed][narr_key]sidechaincompress=threshold=0.012:ratio=12:attack=20:release=500:makeup=1[bed_duck]')

# ---------- 音效：转场轻 whoosh / 关键点 impact ----------
sfx_parts = []
def sfx(name, t, vol, fade=0.12):
    i = add_input(['-i', f'{ROOT}/assets/sfx/{name}'])
    FILTERS.append(f'[{i}:a]aresample=48000,volume={vol},afade=t=in:st=0:d={fade},'
                   f'afade=t=out:st=0.65:d=0.35,adelay={int(round(t*1000))}|{int(round(t*1000))}[x{i}]')
    sfx_parts.append(f'[x{i}]')

for k, s in enumerate(segs[1:], 1):
    # 段落转场：更安静，避免抢旁白
    sfx('whoosh-2.mp3', max(0, s['start'] - 0.35), 0.10)
sfx('whoosh-1.mp3', 0.25, 0.16)
sfx('impact-1.mp3', 0.45, 0.22)
sfx('riser-1.mp3', max(0, segs[2]['start'] - 1.6), 0.14)   # S3 拆概念前
sfx('impact-2.mp3', max(0, segs[5]['start'] - 0.25), 0.18)  # S6 升华入点
sfx('riser-1.mp3', max(0, segs[5]['start'] - 2.2), 0.12)
if sfx_parts:
    FILTERS.append(''.join(sfx_parts) + f'amix=inputs={len(sfx_parts)}:normalize=0:duration=longest[sfx]')
    mix_inputs = '[narr_mix][bed_duck][sfx]'
    n_mix = 3
else:
    mix_inputs = '[narr_mix][bed_duck]'
    n_mix = 2
FILTERS.append(mix_inputs + f'amix=inputs={n_mix}:normalize=0:duration=longest,alimiter=limit=0.95,apad=whole_dur={TOTAL}[mix]')

pre = f'{ROOT}/work/mix_pre.wav'
fc = ';'.join(FILTERS)
cmd = [FF, '-hide_banner', '-loglevel', 'error', '-y'] + INPUTS + \
      ['-filter_complex', fc, '-map', '[mix]', '-t', str(TOTAL), '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', pre]
subprocess.run(cmd, check=True)
print('mix_pre ok', os.path.getsize(pre), flush=True)

# ---------- 两遍 loudnorm ----------
meas = subprocess.run([FF, '-hide_banner', '-i', pre, '-af',
                       'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json',
                       '-f', 'null', '-'], capture_output=True, text=True).stderr
m = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', meas, re.S)
data = json.loads(m[-1]) if m else {}
vals = {k: data[k] for k in ['input_i', 'input_tp', 'input_lra', 'input_thresh', 'output_i', 'target_offset'] if k in data}
print('measured', vals, flush=True)
out = f'{ROOT}/work/audio.m4a'
if vals:
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={vals['input_i']}:measured_TP={vals['input_tp']}:"
          f"measured_LRA={vals['input_lra']}:measured_thresh={vals['input_thresh']}:offset={vals['target_offset']}:linear=true")
else:
    ln = 'loudnorm=I=-14:TP=-1.5:LRA=11'
subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-y', '-i', pre, '-af', ln,
                '-ar', '48000', '-ac', '2', '-c:a', 'aac', '-b:a', '192k', out], check=True)

# ---------- 校验 ----------
probe = subprocess.run([FF, '-hide_banner', '-i', out, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json',
                        '-f', 'null', '-'], capture_output=True, text=True).stderr
mm = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', probe, re.S)
res = json.loads(mm[-1]) if mm else {}
print('final loudness', {k: res.get(k) for k in ['input_i', 'input_tp', 'input_lra']}, flush=True)
vd = subprocess.run([FF, '-hide_banner', '-i', out, '-af', 'volumedetect', '-f', 'null', '-'],
                    capture_output=True, text=True).stderr
for line in vd.splitlines():
    if 'mean_volume' in line or 'max_volume' in line:
        print(line.strip(), flush=True)
print('audio size', os.path.getsize(out), flush=True)
