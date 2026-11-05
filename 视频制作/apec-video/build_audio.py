import json, os, subprocess
ROOT=os.path.dirname(os.path.abspath(__file__))
FFMPEG='/home/admin/.local/bin/ffmpeg'
tl=json.load(open('work/timeline.json',encoding='utf-8'))
beats=tl['beats']; total=tl['total']
def A(*p): return os.path.join(ROOT,*p)
narr=[b['file'] for b in beats]
inputs=[]
for f in narr: inputs += ['-i', f]
bgm=A('assets','music','vastness.mp3')
inputs += ['-stream_loop','-1','-i',bgm]; bgm_i=len(narr)
plan=[]
# whoosh at every beat start except first, softer on minor beats
wh=[A('assets','sfx',f'whoosh-{i}.mp3') for i in (1,2,3)]
for i,b in enumerate(beats[1:],start=1):
    plan.append((wh[i%3], max(0,b['start']-0.05), 0.16 if i%2 else 0.22))
# riser + impacts at section transitions
riser=A('assets','sfx','riser-1.mp3'); impact=A('assets','sfx','impact-1.mp3')
def start_of(bid): return next(b['start'] for b in beats if b['id']==bid)
plan.append((riser, max(0,start_of('b06')-0.9), 0.26))
plan.append((impact, max(0,start_of('b06')-0.25), 0.34))
plan.append((impact, max(0,start_of('b13')-0.15), 0.40))
plan.append((riser, max(0,start_of('b14')-0.9), 0.26))
plan.append((impact, max(0,start_of('b19')-0.2), 0.30))
plan.append((impact, max(0,start_of('b20')-0.15), 0.28))
sfx_i=bgm_i+1
for f,at,vol in plan: inputs += ['-i',f]
fc=[]
for i,b in enumerate(beats):
    d=int(round(b['start']*1000))
    fc.append(f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,adelay={d}|{d},volume=1.0[n{i}]")
fc.append(''.join(f'[n{i}]' for i in range(len(beats)))+f"amix=inputs={len(beats)}:normalize=0:dropout_transition=0[narr]")
fc.append(f"[{bgm_i}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,atrim=0:{total:.3f},volume=0.11,afade=t=in:st=0:d=2.5,afade=t=out:st={max(0,total-4):.3f}:d=4[bgm]")
for i,(f,at,vol) in enumerate(plan):
    d=int(round(max(0,at)*1000))
    fc.append(f"[{sfx_i+i}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,adelay={d}|{d},volume={vol}[x{i}]")
fc.append(f"[narr][bgm]"+''.join(f'[x{i}]' for i in range(len(plan)))+f"amix=inputs={2+len(plan)}:normalize=0:dropout_transition=0,apad=whole_dur={total:.3f},alimiter=limit=0.95:level=false,loudnorm=I=-15:TP=-1.5:LRA=11[aout]")
cmd=[FFMPEG,'-hide_banner','-loglevel','error','-y']+inputs+['-filter_complex',';'.join(fc),'-map','[aout]','-t',f'{total:.3f}','-c:a','aac','-b:a','192k','-ar','48000','work/audio.m4a']
subprocess.run(cmd,check=True)
print('audio done', total)
