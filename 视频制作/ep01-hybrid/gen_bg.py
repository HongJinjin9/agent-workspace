import json, os, subprocess, shutil
ROOT='/app/vedio/ep01-hybrid'
FF='/home/admin/.local/bin/ffmpeg'
TL=json.load(open(f'{ROOT}/work/timeline.json'))
FPS=24
OUT=f'{ROOT}/work/bg'
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT): os.remove(os.path.join(OUT,f))
FALLBACK={'piano_hands':'reading','woodworking':'keyboard_typing','empty_chair':'desk_notebook',
 'crumpled_paper':'desk_notebook','running':'city_day','tea':'rain_window','reading':'desk_notebook',
 'city_night_aerial':'city_day','car_interior_night':'steering_night','pen_writing':'desk_notebook',
 'phone_desk':'desk_lamp','rain_window':'desk_lamp','keyboard_typing':'laptop_night','brake_pedal':'car_dash',
 'metro_window':'city_day','desk_notebook':'desk_lamp','steering_night':'car_dash','car_dash':'steering_night'}
def src(name):
    p=f'{ROOT}/assets/stock/{name}.mp4'
    if os.path.exists(p) and os.path.getsize(p)>50000: return p
    alt=FALLBACK.get(name)
    p2=f'{ROOT}/assets/stock/{alt}.mp4' if alt else None
    if p2 and os.path.exists(p2) and os.path.getsize(p2)>50000:
        print('fallback',name,'->',alt, flush=True); return p2
    for f in os.listdir(f'{ROOT}/assets/stock'):
        if f.endswith('.mp4'):
            print('fallback',name,'->',f, flush=True); return f'{ROOT}/assets/stock/{f}'
    return None
GRADE=("eq=contrast=1.07:saturation=0.86:brightness=-0.02,"
       "colorbalance=rs=0.02:bs=-0.01:rm=0.03:gm=0.01:bm=-0.02,"
       "vignette=PI/5,noise=alls=6:allf=t+u")
def frames_for(outdir, srcpath, src_t, dur, extra=None):
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir): os.remove(os.path.join(outdir,f))
    n=int(round(dur*FPS))
    if extra=='split_side':
        vf=f'crop=303:1080,scale=450:1600,fps=24,{GRADE}'
    else:
        vf=f'crop=ih*9/16:ih,scale=900:1600,fps=24,{GRADE}'
    cmd=[FF,'-hide_banner','-loglevel','error','-y','-ss',str(max(0,src_t)),'-t',str(dur+3),'-i',srcpath,
         '-vf',vf,'-frames:v',str(n),'-q:v','3',f'{outdir}/f%05d.jpg']
    subprocess.run(cmd,check=True)
    got=len([f for f in os.listdir(outdir) if f.endswith('.jpg')])
    if got<n and got>0:
        last=sorted(os.listdir(outdir))[-1]
        for i in range(got+1,n+1):
            shutil.copy(f'{outdir}/{last}', f'{outdir}/f{i:05d}.jpg')
    return outdir
counter=0
def emit(src_frame):
    global counter
    counter+=1
    dst=f'{OUT}/f{counter:05d}.jpg'
    shutil.copy(src_frame, dst)
tmp=f'{ROOT}/work/tmp_bg'
for sh in TL['shots']:
    n=sh['n']
    if sh['type']=='single':
        sp=src(sh['src'])
        d=frames_for(f'{tmp}/s{n}', sp, sh['src_t'], sh['dur'])
        for f in sorted(os.listdir(d)): emit(f'{d}/{f}')
    elif sh['type']=='split':
        a=src(sh['src'][0]); b=src(sh['src'][1])
        os.makedirs(f'{tmp}/a{n}',exist_ok=True); os.makedirs(f'{tmp}/b{n}',exist_ok=True)
        da=frames_for(f'{tmp}/a{n}', a, 1.0, sh['dur'], extra='split_side')
        db=frames_for(f'{tmp}/b{n}', b, 1.0, sh['dur'], extra='split_side')
        from PIL import Image
        fa=sorted(os.listdir(da)); fb=sorted(os.listdir(db))
        for x,y in zip(fa,fb):
            im1=Image.open(f'{da}/{x}'); im2=Image.open(f'{db}/{y}')
            canvas=Image.new('RGB',(900,1600)); canvas.paste(im1,(0,0)); canvas.paste(im2,(450,0))
            p=f'{tmp}/c{n}_{x}'; canvas.save(p,quality=88); emit(p)
    elif sh['type']=='montage':
        names=sh['src']; k=len(names); part=sh['dur']/k
        for i,name in enumerate(names):
            sp=src(name)
            d=frames_for(f'{tmp}/m{n}_{i}', sp, 0.5+i*0.3, part)
            for f in sorted(os.listdir(d)): emit(f'{d}/{f}')
    print('shot',n,sh['kind'],'done total frames',counter, flush=True)
print('TOTAL BG FRAMES', counter)
