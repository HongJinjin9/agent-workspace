import json, os, shutil, subprocess
from PIL import Image
ROOT='/app/vedio/ep01-hybrid'; FF='/home/admin/.local/bin/ffmpeg'; FPS=24
TL=json.load(open(f'{ROOT}/work/timeline.json'))
PARTS=f'{ROOT}/work/bgparts'; OUT=f'{ROOT}/work/bg'
os.makedirs(PARTS,exist_ok=True)
if os.path.isdir(OUT): shutil.rmtree(OUT)
os.makedirs(OUT)
FB={'piano_hands':'reading','woodworking':'keyboard_typing','empty_chair':'desk_notebook','crumpled_paper':'desk_notebook',
 'running':'city_day','tea':'rain_window','reading':'desk_notebook','city_night_aerial':'city_day',
 'car_interior_night':'steering_night','pen_writing':'desk_notebook','phone_desk':'desk_lamp','rain_window':'desk_lamp',
 'keyboard_typing':'laptop_night','brake_pedal':'car_dash','metro_window':'city_day'}
def src(name):
    p=f'{ROOT}/assets/stock/{name}.mp4'
    if os.path.exists(p) and os.path.getsize(p)>50000: return p
    alt=FB.get(name); p2=f'{ROOT}/assets/stock/{alt}.mp4' if alt else None
    if p2 and os.path.exists(p2): return p2
    for f in sorted(os.listdir(f'{ROOT}/assets/stock')):
        if f.endswith('.mp4'): return f'{ROOT}/assets/stock/{f}'
def jpgs(d): return sorted(f for f in os.listdir(d) if f.endswith('.jpg'))
def lowseq(sp,t,n,outdir,scale='450:800'):
    os.makedirs(outdir,exist_ok=True)
    subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-ss',str(max(0,t)),'-t',str(n/FPS+2),'-i',sp,
        '-vf',f'crop=ih*9/16:ih,scale={scale},fps=24','-frames:v',str(n),'-q:v','4',f'{outdir}/f%05d.jpg'],check=True)
    return jpgs(outdir)
for sh in TL['shots']:
    n=sh['n']; d=f'{PARTS}/{n}'; os.makedirs(d,exist_ok=True)
    want=int(round(sh['dur']*FPS))
    if sh['type']=='dark': continue
    have=jpgs(d)
    if len(have)<want:
        if sh['type']=='single' and len(have)==0:
            sp=src(sh['src']); tmp=f'{d}_tmp'
            if os.path.isdir(tmp): shutil.rmtree(tmp)
            fs=lowseq(sp, sh['src_t'], want, tmp)
            for i,f in enumerate(fs[:want],1): shutil.move(f'{tmp}/{f}', f'{d}/f{i:05d}.jpg')
        elif sh['type']=='montage' and len(have)==0:
            names=sh['src']; k=len(names); part=max(1,want//k)
            idx=0
            for j,name in enumerate(names):
                sp=src(name); tmp=f'{d}_m{j}'
                if os.path.isdir(tmp): shutil.rmtree(tmp)
                fs=lowseq(sp, 1.0+j*0.3, part, tmp)
                for f in fs[:part]:
                    idx+=1; shutil.move(f'{tmp}/{f}', f'{d}/f{idx:05d}.jpg')
        # pad with last frame
        have=jpgs(d)
        if have:
            i=len(have)
            while i<want:
                i+=1; shutil.copy(f'{d}/{have[-1]}', f'{d}/f{i:05d}.jpg')
    print('shot',n,'->',len(jpgs(d)),'/',want, flush=True)
# stitch
counter=0
for sh in TL['shots']:
    d=f'{PARTS}/{sh["n"]}'
    for f in jpgs(d):
        counter+=1; shutil.copy(f'{d}/{f}', f'{OUT}/f{counter:05d}.jpg')
print('TOTAL',counter)
