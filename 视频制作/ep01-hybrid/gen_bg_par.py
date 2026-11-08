import json, os, subprocess, shutil
from concurrent.futures import ThreadPoolExecutor
ROOT='/app/vedio/ep01-hybrid'
FF='/home/admin/.local/bin/ffmpeg'
TL=json.load(open(f'{ROOT}/work/timeline.json'))
FPS=24
OUT=f'{ROOT}/work/bg'
PARTS=f'{ROOT}/work/bgparts'
for d in (OUT,PARTS):
    os.makedirs(d, exist_ok=True)
import fcntl
_lock=open(f'{PARTS}.lock','w')
try:
    fcntl.flock(_lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:
    print('another generator running'); raise SystemExit(0)
FALLBACK={'piano_hands':'reading','woodworking':'keyboard_typing','empty_chair':'desk_notebook',
 'crumpled_paper':'desk_notebook','running':'city_day','tea':'rain_window','reading':'desk_notebook',
 'city_night_aerial':'city_day','car_interior_night':'steering_night','pen_writing':'desk_notebook',
 'phone_desk':'desk_lamp','rain_window':'desk_lamp','keyboard_typing':'laptop_night','brake_pedal':'car_dash',
 'metro_window':'city_day','desk_notebook':'desk_lamp','steering_night':'car_dash','car_dash':'steering_night'}
def src(name):
    p=f'{ROOT}/assets/stock/{name}.mp4'
    if os.path.exists(p) and os.path.getsize(p)>50000: return p
    alt=FALLBACK.get(name); p2=f'{ROOT}/assets/stock/{alt}.mp4' if alt else None
    if p2 and os.path.exists(p2) and os.path.getsize(p2)>50000: return p2
    for f in sorted(os.listdir(f'{ROOT}/assets/stock')):
        if f.endswith('.mp4'): return f'{ROOT}/assets/stock/{f}'
    return None
GRADE=("eq=contrast=1.07:saturation=0.86:brightness=-0.02,"
       "colorbalance=rs=0.02:bs=-0.01:rm=0.03:gm=0.01:bm=-0.02")
def gen_shot(sh):
    n=sh['n']; d=f'{PARTS}/{n}'
    os.makedirs(d, exist_ok=True)
    want=int(round(sh['dur']*FPS)) if sh['type']!='dark' else 0
    have=len([f for f in os.listdir(d) if f.endswith('.jpg')])
    if have>=want and want>0:
        return (n, have)
    for attempt in range(3):
        try:
            return _gen_shot(sh)
        except Exception as e:
            print('retry', n, attempt, str(e)[:120], flush=True)
    return (n, len([f for f in os.listdir(d) if f.endswith('.jpg')]))

def _gen_shot(sh):
    n=sh['n']; d=f'{PARTS}/{n}'
    os.makedirs(d, exist_ok=True)
    if sh['type']=='dark':
        return (n, 0)
    if sh['type']=='single':
        sp=src(sh['src']); nf=int(round(sh['dur']*FPS))
        vf=f'crop=ih*9/16:ih,scale=900:1600,fps=24,{GRADE}'
        subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-threads','1','-ss',str(max(0,sh['src_t'])),'-t',str(sh['dur']+3),'-i',sp,
            '-threads','1','-vf',vf,'-frames:v',str(nf),'-q:v','3',f'{d}/f%05d.jpg'],check=True)
        return (n, nf)
    if sh['type']=='split':
        a,b=src(sh['src'][0]),src(sh['src'][1]); nf=int(round(sh['dur']*FPS))
        for tag,sp in (('a',a),('b',b)):
            os.makedirs(f'{d}/{tag}',exist_ok=True)
            subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-threads','1','-ss','1.0','-t',str(sh['dur']+3),'-i',sp,
                '-threads','1','-vf',f'crop=303:1080,scale=450:1600,fps=24,{GRADE}','-frames:v',str(nf),'-q:v','3',f'{d}/{tag}/f%05d.jpg'],check=True)
        from PIL import Image
        for i in range(1,nf+1):
            im1=Image.open(f'{d}/a/f{i:05d}.jpg'); im2=Image.open(f'{d}/b/f{i:05d}.jpg')
            c=Image.new('RGB',(900,1600)); c.paste(im1,(0,0)); c.paste(im2,(450,0))
            c.save(f'{d}/f{i:05d}.jpg',quality=88)
        return (n,nf)
    if sh['type']=='montage':
        names=sh['src']; k=len(names); part=sh['dur']/k; nf=int(round(part*FPS))
        for j,name in enumerate(names):
            sp=src(name); os.makedirs(f'{d}/{j}',exist_ok=True)
            subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-threads','1','-ss',str(0.5+j*0.3),'-t',str(part+2),'-i',sp,
                '-threads','1','-vf',f'crop=ih*9/16:ih,scale=900:1600,fps=24,{GRADE}','-frames:v',str(nf),'-q:v','3',f'{d}/{j}/f%05d.jpg'],check=True)
        idx=0
        for j in range(k):
            for i in range(1,nf+1):
                idx+=1
                shutil.copy(f'{d}/{j}/f{i:05d}.jpg', f'{d}/f{idx:05d}.jpg')
        return (n,idx)
    return (n,0)
with ThreadPoolExecutor(max_workers=2) as ex:
    res=list(ex.map(gen_shot, TL['shots']))
print('parts', res, flush=True)
# stitch
counter=0
for sh in TL['shots']:
    n=sh['n']; d=f'{PARTS}/{n}'
    fs=sorted(f for f in os.listdir(d) if f.endswith('.jpg'))
    for f in fs:
        counter+=1
        shutil.copy(f'{d}/{f}', f'{OUT}/f{counter:05d}.jpg')
print('TOTAL BG FRAMES', counter, flush=True)
