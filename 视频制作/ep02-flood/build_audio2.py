#!/usr/bin/env python3
"""第 02 期混音：场景化连续音乐床 + sidechain 自动压低 + 两遍 loudnorm。"""
import json, os, re, subprocess
ROOT='/app/vedio/ep02-flood'
FF='/home/admin/.local/bin/ffmpeg'
TL=json.load(open(f'{ROOT}/work/timeline.json',encoding='utf-8'))
TOTAL=TL['total']; segs=TL['segments']
MUSIC={k:f'{ROOT}/assets/music/{k}.mp3' for k in ['the-journey','silent-descent','cyberpunk-city','epical-drums-01','vastness']}
PLAN={
 'S1':('silent-descent', 6.0, 0.42),
 'S2':('cyberpunk-city', 2.0, 0.38),
 'S3':('cyberpunk-city', 16.0, 0.44),
 'S4':('vastness', 4.0, 0.40),
 'S5':('the-journey', 8.0, 0.40),
 'S6':('the-journey', 26.0, 0.55),
}
INPUTS=[]; FILTERS=[]; idx=[0]
def add_input(args):
    INPUTS.extend(args); i=idx[0]; idx[0]+=1; return i
def fmt(t): return f'{max(0.0,t):.3f}'
nar=[]
for s in segs:
    i=add_input(['-i',os.path.join(ROOT,s['file'])]); delay=int(round(s['vo_start']*1000))
    FILTERS.append(f'[{i}:a]aresample=48000,adelay={delay}|{delay}[n{i}]'); nar.append(f'[n{i}]')
FILTERS.append(''.join(nar)+f'amix=inputs={len(nar)}:normalize=0:duration=longest[namix]')
FILTERS.append('[namix]highpass=f=80,acompressor=threshold=-18dB:ratio=2.5:attack=20:release=200[narr]')
FILTERS.append('[narr]asplit=2[narr_mix][narr_key]')
bed=[]
for s in segs:
    track,off,vol=PLAN[s['id']]
    i=add_input(['-stream_loop','-1','-i',MUSIC[track]])
    d=s['dur']
    FILTERS.append(f'[{i}:a]aresample=48000,atrim=start={fmt(off)}:end={fmt(off+d+2)},asetpts=PTS-STARTPTS,volume={vol},'
                   f'afade=t=in:st=0:d=0.9,afade=t=out:st={fmt(max(0,d-0.9))}:d=1.8[b{len(bed)}]')
    bed.append(f'[b{len(bed)}]')
prev=bed[0]
for k in range(1,len(bed)):
    FILTERS.append(f'{prev}{bed[k]}acrossfade=d=1.5:c1=tri:c2=tri[xf{k}]'); prev=f'[xf{k}]'
FILTERS.append(f'{prev}highpass=f=120,equalizer=f=300:width_type=o:width=1.2:g=-2,equalizer=f=3000:width_type=o:width=1.5:g=-1.5,volume=0.55[bed]')
FILTERS.append('[bed][narr_key]sidechaincompress=threshold=0.012:ratio=12:attack=20:release=500:makeup=1[bed_duck]')
sfx=[]
def add_sfx(name,t,vol,fade=0.12):
    i=add_input(['-i',f'{ROOT}/assets/sfx/{name}'])
    FILTERS.append(f'[{i}:a]aresample=48000,volume={vol},afade=t=in:st=0:d={fade},afade=t=out:st=0.65:d=0.35,'
                   f'adelay={int(round(t*1000))}|{int(round(t*1000))}[x{i}]'); sfx.append(f'[x{i}]')
add_sfx('whoosh-1.mp3',0.3,0.16); add_sfx('impact-1.mp3',0.5,0.20)
for s in segs[1:]:
    add_sfx('whoosh-2.mp3',max(0,s['start']-0.35),0.09)
add_sfx('riser-1.mp3',max(0,segs[2]['start']-1.6),0.13)
add_sfx('impact-2.mp3',max(0,segs[5]['start']-0.25),0.18)
add_sfx('riser-1.mp3',max(0,segs[5]['start']-2.4),0.12)
FILTERS.append(''.join(sfx)+f'amix=inputs={len(sfx)}:normalize=0:duration=longest[sfx]')
FILTERS.append('[narr_mix][bed_duck][sfx]amix=inputs=3:normalize=0:duration=longest,alimiter=limit=0.95,apad=whole_dur='+str(TOTAL)+'[mix]')
pre=f'{ROOT}/work/mix_pre.wav'
subprocess.run([FF,'-hide_banner','-loglevel','error','-y']+INPUTS+['-filter_complex',';'.join(FILTERS),'-map','[mix]','-t',str(TOTAL),'-ar','48000','-ac','2','-c:a','pcm_s16le',pre],check=True)
print('mix_pre ok',os.path.getsize(pre),flush=True)
meas=subprocess.run([FF,'-hide_banner','-i',pre,'-af','loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True).stderr
m=re.findall(r'\{[^{}]*"input_i"[^{}]*\}',meas,re.S); data=json.loads(m[-1]) if m else {}
vals={k:data[k] for k in ['input_i','input_tp','input_lra','input_thresh','target_offset'] if k in data}
print('measured',vals,flush=True)
ln=('loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={input_i}:measured_TP={input_tp}:measured_LRA={input_lra}:measured_thresh={input_thresh}:offset={target_offset}:linear=true').format(**vals) if vals else 'loudnorm=I=-14:TP=-1.5:LRA=11'
out=f'{ROOT}/work/audio.m4a'
subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-i',pre,'-af',ln,'-ar','48000','-ac','2','-c:a','aac','-b:a','192k',out],check=True)
probe=subprocess.run([FF,'-hide_banner','-i',out,'-af','loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True).stderr
mm=re.findall(r'\{[^{}]*"input_i"[^{}]*\}',probe,re.S); res=json.loads(mm[-1]) if mm else {}
print('final',{k:res.get(k) for k in ['input_i','input_tp','input_lra']},flush=True)
vd=subprocess.run([FF,'-hide_banner','-i',out,'-af','volumedetect','-f','null','-'],capture_output=True,text=True).stderr
for line in vd.splitlines():
    if 'mean_volume' in line or 'max_volume' in line: print(line.strip())
print('audio size',os.path.getsize(out))
