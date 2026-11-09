import json, os, subprocess, time
ROOT='/app/vedio/ep02-flood'
FF='/home/admin/.local/bin/ffmpeg'
TL=json.load(open(f'{ROOT}/work/timeline.json',encoding='utf-8')); TOTAL=TL['total']; N=round(TOTAL*24)
os.makedirs(f'{ROOT}/out',exist_ok=True)
def count():
    try: return len([f for f in os.listdir(f'{ROOT}/work/frames') if f.endswith('.jpg')])
    except FileNotFoundError: return 0
last=-1; stable=0
while True:
    c=count()
    if c>=N and c==last: stable+=1
    else: stable=0
    if c>=N and stable>=3: break
    last=c; print('waiting',c,N,flush=True); time.sleep(3)
out=f'{ROOT}/out/ep02-flood.mp4'
subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-framerate','24','-i',f'{ROOT}/work/frames/f%05d.jpg','-i',f'{ROOT}/work/audio.m4a',
  '-vf','scale=1080:1920:flags=lanczos,unsharp=5:5:0.4:5:5:0.0','-c:v','libx264','-preset','veryfast','-crf','24','-pix_fmt','yuv420p','-profile:v','high',
  '-c:a','aac','-b:a','192k','-movflags','+faststart','-t',str(TOTAL),out],check=True)
print('size='+str(os.path.getsize(out)),flush=True)
stills=[('1.8','still-01-phone'),('8.0','still-02-forward'),('27.0','still-03-data'),('40.0','still-04-glitch'),('60.0','still-05-erase'),('72.0','still-06-flood'),('88.0','still-07-curve'),('120.0','still-08-law'),('160.0','still-09-sieve'),('210.0','still-10-clause')]
os.makedirs(f'{ROOT}/delivery',exist_ok=True)
for t,name in stills:
    subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-ss',t,'-i',out,'-frames:v','1','-q:v','2',f'{ROOT}/delivery/{name}.jpg'])
subprocess.run(['python3',f'{ROOT}/gen_cover.py'],check=True)
open('/tmp/ep02-video.done','w').write('OK '+str(os.path.getsize(out)))
print('DONE',flush=True)
