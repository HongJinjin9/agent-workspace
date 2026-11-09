import os, math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT='/app/vedio/ep02-flood'
F_SERIF='/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
F_SANS='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
F_SANS_R='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def ft(p,s): return ImageFont.truetype(p,s)
def draw_cover(w,h,title_lines,sub,path):
    im=Image.new('RGB',(w,h),(6,8,12)); d=ImageDraw.Draw(im)
    # 顶部光源
    for yy in range(0,int(h*0.42),3):
        a=int(70*(1-yy/(h*0.42))); d.line((0,yy,w,yy),fill=(10+a//3,16+a//2,24+a))
    # 内容卡片瀑布
    rnd=random.Random(3); glyphs=['AI','10万+','标题','揭秘','转发','震惊','专家','独家']
    for i in range(70):
        x=rnd.uniform(-20,w-60); y=rnd.uniform(0,h*0.95); cw,ch=rnd.uniform(40,90),rnd.uniform(34,70)
        a=rnd.randint(40,150)
        d.rounded_rectangle((x,y,x+cw,y+ch),radius=5,fill=(200+a//3,215+a//4,230+a//6),outline=(255,255,255))
    # 筛子光流
    cx,cy=w*0.62,h*0.62; rr=int(w*0.28)
    for k in range(4):
        d.ellipse((cx-rr+k*10,cy-rr+k*10,cx+rr-k*10,cy+rr-k*10),outline=(225,235,245),width=3)
    for k in range(12):
        a=k/12*2*math.pi
        d.line((cx,cy,cx+rr*math.cos(a),cy+rr*math.sin(a)),fill=(190,204,218),width=2)
    d.line((cx,cy+rr*0.2,cx+18,cy+rr*1.9),fill=(245,205,115),width=10,joint='curve')
    # 压暗
    ov=Image.new('RGBA',(w,h),(2,4,8,70)); im=Image.alpha_composite(im.convert('RGBA'),ov); d=ImageDraw.Draw(im)
    # 标题
    ty=int(h*0.16)
    for i,line in enumerate(title_lines):
        f=ft(F_SERIF,int(w*0.115)); tw=d.textlength(line,font=f)
        d.text(((w-tw)/2,ty+i*int(w*0.135)),line,font=f,fill=(240,244,248),stroke_width=3,stroke_fill=(0,0,0))
    f=ft(F_SANS_R,int(w*0.035)); tw=d.textlength(sub,font=f)
    d.text(((w-tw)/2,ty+len(title_lines)*int(w*0.135)+int(h*0.02)),sub,font=f,fill=(240,195,106))
    im.convert('RGB').save(path,quality=94)
def main():
    draw_cover(1080,1920,['内容洪水里','最贵的是「真的」'],'从 6 亿 AI 用户到内容疲劳',f'{ROOT}/delivery/cover-9x16.jpg')
    draw_cover(1200,1600,['内容洪水里','最贵的是「真的」'],'从 6 亿 AI 用户到内容疲劳',f'{ROOT}/delivery/cover-3x4.jpg')
    print('covers done')
if __name__=='__main__': main()
