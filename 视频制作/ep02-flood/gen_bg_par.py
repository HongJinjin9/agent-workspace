#!/usr/bin/env python3
import json, os, subprocess, hashlib, shutil, sys
from concurrent.futures import ThreadPoolExecutor
ROOT=os.path.dirname(os.path.abspath(__file__))
TL=json.load(open(f'{ROOT}/work/timeline.json',encoding='utf-8'))
FPS=24
GRADE={
 'cool':'eq=contrast=1.08:saturation=0.72:brightness=-0.03,colorbalance=rs=0.015:bs=-0.012:rm=0.02:gm=0.0:bm=-0.02',
 'warm':'eq=contrast=1.05:saturation=0.86:brightness=-0.02,colorbalance=rs=0.03:bs=-0.03:rm=0.03:gm=0.01:bm=-0.03',
 'neutral':'eq=contrast=1.06:saturation=0.8:brightness=-0.03,colorbalance=rs=0.01:bs=-0.01:rm=0.02:gm=0.0:bm=-0.02',
}
SHOT_GRADE={'data':'cool','glitch':'warm','erase':'warm','creator':'cool','hist_print':'warm','hist_tv':'warm','hist_phone':'cool','source':'warm','city':'cool','scroll':'cool','clause':'cool','publish':'cool','lamp':'warm'}
FF='/home/admin/.local/bin/ffmpeg'
os.makedirs(f'{ROOT}/work/bg',exist_ok=True); os.makedirs(f'{ROOT}/work/bgparts',exist_ok=True)

def dur_of(p):
    r=subprocess.run([FF,'-hide_banner','-i',p],capture_output=True,text=True)
    import re; m=re.search(r'Duration: (\d+):(\d+):([\d.]+)',r.stderr)
    return int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3)) if m else 0

def work(shot):
    src=f"{ROOT}/assets/stock/{shot['src']}.mp4"
    if not os.path.exists(src): print('MISS clip',shot['src']); return
    f0=round(shot['start']*FPS); f1=round(shot['end']*FPS); n=max(1,f1-f0)
    outdir=f"{ROOT}/work/bgparts/{shot['i']:02d}_{shot['label']}"; os.makedirs(outdir,exist_ok=True)
    for f in os.listdir(outdir):
        if f.startswith('f') and f.endswith('.jpg'): os.remove(os.path.join(outdir,f))
    cd=dur_of(src)
    need=n/FPS
    h=int(hashlib.md5(shot['label'].encode()).hexdigest()[:8],16)
    off=0.0 if cd<=need+1 else (h % int((cd-need-1)*10))/10.0
    grade=GRADE[SHOT_GRADE.get(shot['label'],'neutral')]
    vf=f"scale=900:1600:force_original_aspect_ratio=increase,crop=900:1600,fps={FPS},{grade}"
    cmd=[FF,'-hide_banner','-loglevel','error','-y','-stream_loop','-1','-ss',f'{off:.2f}','-i',src,'-t',f'{need+0.1:.2f}','-vf',vf,'-q:v','3',f'{outdir}/f%05d.jpg']
    subprocess.run(cmd,check=True)
    # rename to global index
    for idx in range(1,n+1):
        srcf=f'{outdir}/f{idx:05d}.jpg'; dst=f"{ROOT}/work/bg/f{f0+idx-1:05d}.jpg"
        if os.path.exists(srcf): os.replace(srcf,dst)
    print('done',shot['i'],shot['label'],n,flush=True)

shots=[s for s in TL['shots'] if s['kind']=='stock']
with ThreadPoolExecutor(max_workers=1) as ex:
    list(ex.map(work,shots))
# verify
have=sum(1 for s in TL['shots'] if s['kind']=='stock' for _ in range(round(s['start']*FPS),round(s['end']*FPS)) if os.path.exists(f"{ROOT}/work/bg/f{_:05d}.jpg"))
print('bg frames present',have)
