import os, math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT='/app/vedio/ep02-flood'
F_SERIF='/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
F_SANS='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
F_SANS_R='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def ft(p,s): return ImageFont.truetype(p,s)
def draw_cover(w,h,path):
    im=Image.new('RGB',(w,h),(6,8,12)); d=ImageDraw.Draw(im)
    for yy in range(0,int(h*0.5),3):
        a=int(90*(1-yy/(h*0.5))); d.line((0,yy,w,yy),fill=(10+a//2,18+a,28+a))
    rnd=random.Random(3); glyphs=['AI','10万+','标题','揭秘','转发','震惊','专家','独家']
    for i in range(90):
        x=rnd.uniform(-20,w-60); y=rnd.uniform(0,h*0.98); cw,ch=rnd.uniform(36,96),rnd.uniform(30,74)
        a=rnd.randint(60,190)
        d.rounded_rectangle((x,y,x+cw,y+ch),radius=6,fill=(200+a//3,215+a//4,230+a//6),outline=(255,255,255))
    # 筛子
    cx,cy=w*0.66,h*0.63; rr=int(w*0.26)
    for k in range(4): d.ellipse((cx-rr+k*10,cy-rr+k*10,cx+rr-k*10,cy+rr-k*10),outline=(240,195,106),width=4)
    for k in range(12):
        a=k/12*2*math.pi; d.line((cx,cy,cx+rr*math.cos(a),cy+rr*math.sin(a)),fill=(205,218,232),width=2)
    d.line((cx,cy+rr*0.2,cx+18,cy+rr*1.9),fill=(245,205,115),width=12,joint='curve')
    ov=Image.new('RGBA',(w,h),(2,4,8,80)); im=Image.alpha_composite(im.convert('RGBA'),ov); d=ImageDraw.Draw(im)
    # 顶部爆款大字
    ty=int(h*0.07)
    f1=ft(F_SANS,int(w*0.165))
    d.text((int(w*0.05),ty),'6.02亿',font=f1,fill=(240,195,106),stroke_width=4,stroke_fill=(0,0,0))
    f2=ft(F_SANS_R,int(w*0.055))
    d.text((int(w*0.05),ty+int(w*0.17)),'人在用 AI 生成内容',font=f2,fill=(240,244,248),stroke_width=3,stroke_fill=(0,0,0))
    # 标题块（色块）
    bx,by,bw,bh=int(w*0.05),int(h*0.55),int(w*0.9),int(h*0.12)
    d.rounded_rectangle((bx,by,bx+bw,by+bh),radius=14,fill=(240,195,106))
    f3=ft(F_SANS,int(w*0.095))
    title='最贵的是「真的」'
    tw=d.textlength(title,font=f3)
    d.text((bx+(bw-tw)//2,by+int(bh*0.14)),title,font=f3,fill=(10,12,16))
    f4=ft(F_SERIF,int(w*0.07))
    sub='内容洪水里'
    tw2=d.textlength(sub,font=f4)
    d.text((int(w*0.05),by-int(w*0.085)),sub,font=f4,fill=(240,244,248),stroke_width=3,stroke_fill=(0,0,0))
    f5=ft(F_SANS_R,int(w*0.04))
    d.text((int(w*0.05),by+bh+int(h*0.02)),'从 6 亿 AI 用户到内容疲劳',font=f5,fill=(205,215,225),stroke_width=2,stroke_fill=(0,0,0))
    im.convert('RGB').save(path,quality=94)
def main():
    draw_cover(1080,1920,f'{ROOT}/delivery/cover-9x16.jpg')
    draw_cover(1200,1600,f'{ROOT}/delivery/cover-3x4.jpg')
    print('covers v3 done')
if __name__=='__main__': main()
