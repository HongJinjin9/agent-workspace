import subprocess, os, time
ROOT='/app/vedio/ep01-hybrid'
FF='/home/admin/.local/bin/ffmpeg'
N=6234
def count():
    d=f'{ROOT}/work/frames'
    return len([f for f in os.listdir(d) if f.endswith('.jpg')]) if os.path.isdir(d) else 0
log=open('/tmp/ep01-finalize.log','w')
for i in range(2400):
    c=count(); p=subprocess.run(['pgrep','-fc','scene_hybrid.py'],capture_output=True,text=True).stdout.strip() or '0'
    if c>=N and p=='0': break
    time.sleep(5)
if count()<N:
    log.write('ERR frames %d\n'%count()); raise SystemExit(1)
out=f'{ROOT}/out/ep01-hybrid.mp4'
cmd=[FF,'-hide_banner','-loglevel','error','-y','-framerate','24','-i',f'{ROOT}/work/frames/f%05d.jpg','-i',f'{ROOT}/work/audio.m4a',
     '-vf','scale=1080:1920:flags=lanczos,unsharp=5:5:0.4:5:5:0.0','-c:v','libx264','-preset','veryfast','-crf','24',
     '-pix_fmt','yuv420p','-profile:v','high','-c:a','aac','-b:a','192k','-movflags','+faststart','-shortest',out]
subprocess.run(cmd,check=True)
log.write('size=%d\n'%os.path.getsize(out)); log.flush()
os.makedirs(f'{ROOT}/delivery',exist_ok=True)
for t,name in ((1.6,'still-01-dash'),(27,'still-02-split'),(80,'still-03-diagram'),(98,'still-04-fourgrid'),
               (121,'still-05-ai'),(165,'still-06-regen'),(200,'still-07-paper'),(235,'still-08-city'),
               (255,'still-09-outro'),(258.5,'still-10-endcard')):
    subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-ss',str(t),'-i',out,'-frames:v','1','-q:v','2',f'{ROOT}/delivery/{name}.jpg'])
subprocess.run(['python3',f'{ROOT}/gen_cover.py'],check=True)
open('/tmp/ep01-video.done','w').write('OK %d\n'%os.path.getsize(out))
log.write('DONE\n')
