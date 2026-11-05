import subprocess, os
from PIL import Image, ImageFilter, ImageEnhance
import numpy as np
ROOT='/app/vedio/apec-video'
FF='/home/admin/.local/bin/ffmpeg'
VB='/app/vedio/vibe-cinematic/assets'
W,H=900,1600
def from_video(path, t, blur, dark, tint):
    tmp='/tmp/bd.jpg'
    subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-ss',str(t),'-i',path,'-frames:v','1','-q:v','2',tmp],check=True)
    im=Image.open(tmp).convert('RGB')
    # cover crop
    s=max(W/im.width,H/im.height); im=im.resize((int(im.width*s),int(im.height*s)),Image.LANCZOS)
    x=(im.width-W)//2; y=(im.height-H)//2
    im=im.crop((x,y,x+W,y+H)).filter(ImageFilter.GaussianBlur(blur))
    arr=np.asarray(im,dtype=np.float32)
    arr*=dark
    arr[...,0]*=tint[0]; arr[...,1]*=tint[1]; arr[...,2]*=tint[2]
    return Image.fromarray(np.clip(arr,0,255).astype(np.uint8))
def from_image(path, blur, dark, tint):
    im=Image.open(path).convert('RGB')
    s=max(W/im.width,H/im.height); im=im.resize((int(im.width*s),int(im.height*s)),Image.LANCZOS)
    x=(im.width-W)//2; y=(im.height-H)//2
    im=im.crop((x,y,x+W,y+H)).filter(ImageFilter.GaussianBlur(blur))
    arr=np.asarray(im,dtype=np.float32)*dark
    arr[...,0]*=tint[0]; arr[...,1]*=tint[1]; arr[...,2]*=tint[2]
    return Image.fromarray(np.clip(arr,0,255).astype(np.uint8))
jobs={
 'city':   lambda: from_video(f'{VB}/stock/city-night.mp4', 3.0, 3, 0.42, (0.82,1.0,1.15)),
 'cosmos': lambda: from_image(f'{VB}/ai/city-future.png', 6, 0.40, (0.85,0.95,1.2)),
 'dawn':   lambda: from_video(f'{VB}/stock/sunrise.mp4', 2.0, 5, 0.45, (1.1,1.0,0.92)),
 'light':  lambda: from_video(f'{VB}/stock/light-abstract.mp4', 2.0, 6, 0.45, (0.9,1.0,1.12)),
}
for name,fn in jobs.items():
    out=f'{ROOT}/assets/backdrops/{name}.jpg'
    fn().save(out, quality=92)
    print('saved', out)
