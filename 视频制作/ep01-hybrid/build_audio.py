import json, subprocess, os
ROOT='/app/vedio/ep01-hybrid'
FF='/home/admin/.local/bin/ffmpeg'
TL=json.load(open(f'{ROOT}/work/timeline.json'))
TOTAL=TL['total']
segs=TL['segments']
inputs=[]
filters=[]
idx=0
# narration inputs
for s in segs:
    inputs += ['-i', os.path.join(ROOT, s['file'])]
    delay=int(round(s['vo_start']*1000))
    filters.append(f'[{idx}:a]adelay={delay}|{delay},volume=1.0[n{idx}]')
    idx+=1
narr_mix=''.join(f'[n{i}]' for i in range(idx))+'amix=inputs=%d:normalize=0:duration=longest[narr]'%idx
filters.append(narr_mix)
# bgm
bgm=os.path.join(ROOT,'assets','music','the-journey.mp3')
amb=os.path.join(ROOT,'assets','music','silent-descent.mp3')
inputs += ['-stream_loop','-1','-i',bgm]
b=idx; idx+=1
filters.append(f'[{b}:a]atrim=0:{TOTAL},volume=0.14,afade=t=in:st=0:d=3,afade=t=out:st={max(0,TOTAL-4):.2f}:d=4[bgm]')
inputs += ['-stream_loop','-1','-i',amb]
a=idx; idx+=1
filters.append(f'[{a}:a]atrim=0:{TOTAL},volume=0.10,afade=t=in:st=0:d=4,afade=t=out:st={max(0,TOTAL-5):.2f}:d=5[amb]')
# sfx
def sfx(name, t, vol):
    global idx
    p=os.path.join(ROOT,'assets','sfx',name)
    if not os.path.exists(p): return None
    inputs.extend(['-i',p])
    delay=int(round(max(0,t)*1000))
    filters.append(f'[{idx}:a]adelay={delay}|{delay},volume={vol}[s{idx}]')
    idx+=1
    return f'[s{idx-1}]'
parts=[]
parts.append(sfx('whoosh-1.mp3', 0.2, 0.6))
parts.append(sfx('impact-1.mp3', 0.4, 0.7))
parts.append(sfx('riser-1.mp3', 0.3, 0.5))
for s in segs[1:]:
    parts.append(sfx('whoosh-2.mp3', s['start']-0.25, 0.4))
for t in (66.8, 173.8, 241.8):
    parts.append(sfx('impact-2.mp3', t, 0.55))
parts=[p for p in parts if p]
mixin=''.join(parts)+'[narr][bgm][amb]'
filters.append(mixin+f'amix=inputs={len(parts)+3}:normalize=0:duration=longest,alimiter=limit=0.95,loudnorm=I=-14:TP=-1.5:LRA=11[aout]')
fc=';'.join(filters)
out=os.path.join(ROOT,'work','audio.m4a')
cmd=[FF,'-hide_banner','-loglevel','error','-y']+inputs+['-filter_complex',fc,'-map','[aout]','-t',str(TOTAL),'-c:a','aac','-b:a','192k',out]
subprocess.run(cmd,check=True)
r=subprocess.run([FF,'-hide_banner','-i',out],capture_output=True,text=True)
import re
m=re.search(r'Duration: (\d+):(\d+):([\d.]+)',r.stderr)
print('audio', out, m.group(0) if m else '?', os.path.getsize(out))
