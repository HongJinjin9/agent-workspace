from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np, subprocess
ROOT='/app/vedio/ep01-hybrid'
FF='/home/admin/.local/bin/ffmpeg'
SERIF='/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
SANS='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
SANS_R='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
W,H=1080,1920
# background from desk lamp b-roll (dark warm workshop)
def frame(src,t):
    subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-ss',str(t),'-i',src,'-frames:v','1','/tmp/cv.jpg'],check=True)
    return Image.open('/tmp/cv.jpg').convert('RGB')
src=f'{ROOT}/assets/stock/desk_lamp.mp4'
im=frame(src,3.0)
s=max(W/im.width,H/im.height); im=im.resize((int(im.width*s),int(im.height*s)),Image.LANCZOS)
x=(im.width-W)//2; y=(im.height-H)//2; im=im.crop((x,y,x+W,y+H))
arr=np.asarray(im,dtype=np.float32)*0.62
yy=np.arange(H)[:,None,None]/H
arr=arr*(1-0.55*np.clip((yy-0.35)/0.65,0,1)**1.3)
arr=arr*(1-0.35*np.clip((0.35-yy)/0.35,0,1)**1.2)
im=Image.fromarray(np.clip(arr,0,255).astype(np.uint8)).convert('RGBA')
d=ImageDraw.Draw(im)
def ft(p,s): return ImageFont.truetype(p,s)
# energy band
band=Image.new('RGBA',(W,H),(0,0,0,0)); bd=ImageDraw.Draw(band)
pts=[(80,H*0.72),(W*0.45,H*0.66),(W-80,H*0.74)]
for w,a in ((26,60),(12,140),(5,255)):
    bd.line(pts,fill=(61,245,200,a),width=w,joint='curve')
band=band.filter(ImageFilter.GaussianBlur(6)); im.alpha_composite(band)
# title vertical typography
title='人生，也是一台混动车'
sub='从一台混动车，看人的能量管理'
f1=ft(SERIF,86); f2=ft(SANS,34); f3=ft(SANS_R,24)
y0=250
for i,ch in enumerate(title):
    d.text((W//2, y0+i*105), ch, font=f1, fill=(240,244,248,255), anchor='mm', stroke_width=3, stroke_fill=(0,0,0,180))
d.line([(W//2-90,y0+len(title)*105+20),(W//2+90,y0+len(title)*105+20)],fill=(61,245,200,220),width=3)
d.text((W//2, y0+len(title)*105+80), sub, font=f2, fill=(210,218,222,240), anchor='mm', stroke_width=2, stroke_fill=(0,0,0,160))
d.text((W//2, H-150), 'EP.01 · VCP 视听', font=f3, fill=(140,150,156,220), anchor='mm')
im.convert('RGB').save(f'{ROOT}/delivery/cover-9x16.jpg',quality=92)
# 3:4 version
c34=im.crop((0,int(H*0.14),W,int(H*0.14)+int(W*4/3))).resize((1080,1440),Image.LANCZOS)
c34.convert('RGB').save(f'{ROOT}/delivery/cover-3x4.jpg',quality=92)
print('covers saved')
