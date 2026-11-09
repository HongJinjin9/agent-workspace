#!/usr/bin/env python3
"""第 02 期《内容洪水里，最贵的是「真的」》渲染器：B-roll 背景 + 内容洪水 + 筛子 + 数据动效 + 逐句字幕。"""
import os, sys, json, math, random, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import engine3d as E

ROOT=os.path.dirname(os.path.abspath(__file__))
W,H,FPS=900,1600,24
TL=json.load(open(os.path.join(ROOT,'work','timeline.json'),encoding='utf-8'))
TOTAL=TL['total']; SHOTS=TL['shots']; SEGS={s['id']:s for s in TL['segments']}
F_SANS='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
F_SANS_R='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
F_SERIF='/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
F_MONO='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
WHITE=(240,244,248); COOL=(232,244,255); WARM=(240,195,106); RED=(238,96,92); GREY=(150,158,165); DARK=(6,8,10); TEAL=(120,220,235)

def ft(p,s): return ImageFont.truetype(p,s)
_TEX={}
def text_tex(text,size,color,font=F_SANS,glow=0,glow_color=None,glow_strength=0.8,stroke=0,stroke_color=(0,0,0)):
    key=(text,size,color,font,glow,glow_color,stroke,stroke_color)
    if key in _TEX: return _TEX[key]
    f=ft(font,size); tmp=ImageDraw.Draw(Image.new('RGBA',(4,4)))
    bb=tmp.textbbox((0,0),text,font=f,stroke_width=stroke); tw,th=bb[2]-bb[0],bb[3]-bb[1]
    pad=int(max(16,glow*2+stroke*2+8))
    im=Image.new('RGBA',(tw+pad*2,th+pad*2),(0,0,0,0)); d=ImageDraw.Draw(im)
    if glow>0:
        gl=Image.new('RGBA',im.size,(0,0,0,0)); gd=ImageDraw.Draw(gl)
        gd.text((pad-bb[0],pad-bb[1]),text,font=f,fill=(glow_color or color)+(255,),stroke_width=stroke,stroke_fill=stroke_color+(255,))
        gl=gl.filter(ImageFilter.GaussianBlur(glow)); a=gl.getchannel('A').point(lambda v:int(v*glow_strength)); gl.putalpha(a); im.alpha_composite(gl)
    d.text((pad-bb[0],pad-bb[1]),text,font=f,fill=color+(255,),stroke_width=stroke,stroke_fill=stroke_color+(255,))
    _TEX[key]=im; return im

_GLYPH={}
def glyph_tex(txt,color,size,font=F_MONO):
    size=max(10,int(round(size/4.0)*4))
    key=(txt,color,size,font)
    if key in _GLYPH: return _GLYPH[key]
    base=text_tex(txt,28,color,font=font,glow=0,stroke=1,stroke_color=(0,0,0))
    if size==28: im=base
    else: im=base.resize((max(1,int(base.width*size/28)),max(1,int(base.height*size/28))),Image.BILINEAR)
    if len(_GLYPH)>800: _GLYPH.clear()
    _GLYPH[key]=im; return im

def with_alpha(im,a):
    if a>=0.999: return im
    im2=im.copy(); im2.putalpha(im2.getchannel('A').point(lambda v:int(v*a))); return im2

class R:
    def __init__(self, bg=None, cam=None):
        self.img=(bg or Image.new('RGBA',(W,H),DARK+(255,))).convert('RGBA')
        self.items=[]; self.cam=cam or E.Camera((0,-2.8,1.2),(0,0,0.3),fov_deg=40)
    def put(self,tex,x,y,alpha=1.0,anchor='mm',depth=0.5):
        if alpha<=0.004: return
        layer=tex if alpha>=0.999 else with_alpha(tex,alpha)
        if anchor=='mm': bx,by=int(x-layer.width/2),int(y-layer.height/2)
        elif anchor=='lm': bx,by=int(x),int(y-layer.height/2)
        elif anchor=='tl': bx,by=int(x),int(y)
        else: bx,by=int(x-layer.width/2),int(y)
        self.items.append((depth,layer,bx,by))
    def flush(self):
        for depth,layer,bx,by in sorted(self.items,key=lambda it:-it[0]):
            self.img.alpha_composite(layer,(bx,by))
        self.items=[]

def dark_bg(t=0.0,seed=7):
    rnd=random.Random(seed)
    y=np.linspace(0,1,H)[:,None]; x=np.linspace(0,1,W)[None,:]
    base=18+40*np.exp(-((x-0.5)**2/0.10+(y-0.32)**2/0.16))
    a=np.stack([base*0.82,base*0.92,base*1.05],axis=-1)
    n=rnd.uniform(-3,3); a=a+n
    im=Image.fromarray(np.clip(a,0,255).astype(np.uint8),'RGB').convert('RGBA')
    gl=Image.new('RGBA',(W,H),(0,0,0,0)); gd=ImageDraw.Draw(gl)
    for _ in range(5):
        cx=rnd.uniform(100,W-100); cy=rnd.uniform(300,1300); rr=rnd.uniform(200,500)
        gd.ellipse((cx-rr,cy-rr*0.6,cx+rr,cy+rr*0.6),fill=(14,18,26,28))
    gl=gl.filter(ImageFilter.GaussianBlur(120)); im.alpha_composite(gl)
    return im

def hua_tex(text,y,size=52,color=COOL,glow=18,sub=None,sub_size=30):
    t=text_tex(text,size,color,glow=glow,glow_color=color,glow_strength=0.5,stroke=2,stroke_color=(0,0,0))
    if not sub: return t
    s=text_tex(sub,sub_size,(210,216,224),font=F_SANS_R,glow=6,glow_strength=0.4)
    out=Image.new('RGBA',(max(t.width,s.width),t.height+s.height+8),(0,0,0,0))
    out.alpha_composite(t,((out.width-t.width)//2,0)); out.alpha_composite(s,((out.width-s.width)//2,t.height+6)); return out

# 花字：(shot_idx, offset, text, color)
HUA=[
 (6,0.6,'一个月，清理 23000 余条',COOL),
 (8,0.8,'不是内容不够，是「真的」不够',WARM),
 (10,0.8,'内容成本趋零，注意力没变多',COOL),
 (12,0.8,'规则已经写在纸上',COOL),
 (13,0.7,'标识不是技术问题，是利益问题',WARM),
 (18,0.8,'可核、可署名、可负责',WARM),
 (20,0.8,'筛子不该是观众',WARM),
 (21,0.8,'有条款的负责叫兜底',WARM),
]
import subs as SUB
CAPS=[(c['start'],c['end'],c['text']) for c in SUB.build_caps(TL)]

def caption(r,t):
    for (a,b,txt) in CAPS:
        if a<=t<b:
            im=text_tex(txt,44,WHITE,glow=10,glow_color=(0,0,0),glow_strength=0.5,stroke=3,stroke_color=(0,0,0))
            r.put(im,W//2,1400,alpha=0.97); return

def post(im, fi):
    arr=np.asarray(im.convert('RGB')).astype(np.int16)
    rnd=np.random.default_rng(fi)
    arr=arr+rnd.integers(-3,4,arr.shape,dtype=np.int16)
    yy=np.linspace(0,1,H)[:,None]; xx=np.linspace(0,1,W)[None,:]
    mask=1-0.55*(((xx-0.5)*1.25)**2+((yy-0.5)*0.9)**2)
    arr=(arr*np.clip(mask,0.25,1)[...,None])
    return Image.fromarray(np.clip(arr,0,255).astype(np.uint8),'RGB')

# ---------------- 通用
def panel(r,x,y,w,h,fill=(14,18,24,235),outline=(70,86,104),radius=18,width=2):
    lay=Image.new('RGBA',(w,h),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.rounded_rectangle((1,1,w-2,h-2),radius=radius,fill=fill,outline=outline,width=width)
    r.put(lay,x,y,anchor='tl')

def chip(r,text,x,y,size=30,color=WARM,fill=(30,26,18,235),outline=None):
    im=text_tex(text,size,color,font=F_SANS_R,glow=4,glow_strength=0.4)
    w,h=im.width+30,im.height+18
    lay=Image.new('RGBA',(w,h),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.rounded_rectangle((1,1,w-2,h-2),radius=h//2,fill=fill,outline=outline or color+(120,),width=1)
    lay.alpha_composite(im,(15,9)); r.put(lay,x,y,anchor='tl')

def phone_frame(r,cx,cy,w=560,h=980,glow=True):
    lay=Image.new('RGBA',(w+80,h+80),(0,0,0,0)); d=ImageDraw.Draw(lay)
    if glow:
        gl=Image.new('RGBA',lay.size,(0,0,0,0)); ImageDraw.Draw(gl).rounded_rectangle((30,30,w+50,h+50),radius=64,fill=(120,190,255,80))
        lay.alpha_composite(gl.filter(ImageFilter.GaussianBlur(28)))
    d.rounded_rectangle((40,40,w+40,h+40),radius=56,fill=(8,10,14,255),outline=(90,110,130),width=3)
    # screen
    scr=Image.new('RGBA',(w-30,h-60),(12,16,22,255)); sd=ImageDraw.Draw(scr)
    for yy in range(0,scr.height,4): sd.line((0,yy,scr.width,yy),fill=(16,22,30,255))
    lay.alpha_composite(scr,(55,70))
    r.put(lay,cx,cy)

def screen_origin(cx,cy,w=560,h=980): return (cx-w//2+15, cy-h//2+30)  # inner screen top-left

def play_icon(r,x,y,s=40,col=WHITE,alpha=1.0):
    lay=Image.new('RGBA',(s,s),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.polygon([(s*0.28,s*0.2),(s*0.28,s*0.8),(s*0.82,s*0.5)],fill=col+(255,))
    r.put(lay,x,y,alpha=alpha)

# ---------------- 各镜
def sc_cold(r,tg,fi,shot=None):
    if tg<1.2:
        r.put(text_tex('',1,WHITE),W//2,H//2)
        return
    a=min(1,(tg-1.2)/1.6)
    gl=Image.new('RGBA',(W,H),(0,0,0,0)); gd=ImageDraw.Draw(gl)
    gd.ellipse((W//2-200,H//2-330,W//2+200,H//2+330),fill=(120,190,255,int(60*a)))
    gl=gl.filter(ImageFilter.GaussianBlur(90)); r.img.alpha_composite(gl)
    phone_frame(r,W//2,H//2,420,760,glow=False)
    r.put(text_tex('深夜 23:47',30,(150,170,190),font=F_SANS_R,glow=6),W//2,H//2+520,alpha=a)

def feed_card(r,x,y,w=380,h=150,title='',tag='',alpha=1.0,hl=False):
    lay=Image.new('RGBA',(w,h),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.rounded_rectangle((1,1,w-2,h-2),radius=14,fill=(22,28,36,250),outline=(60,74,90) if not hl else (120,170,220),width=2)
    d.rounded_rectangle((16,16,120,h-16),radius=8,fill=(40,52,64))
    r.put(lay,x,y,alpha=alpha,anchor='tl')
    r.put(text_tex(title,24,WHITE,font=F_SANS_R),x+140,y+50,alpha=alpha,anchor='lm')
    r.put(text_tex(tag,18,GREY,font=F_SANS_R),x+140,y+100,alpha=alpha,anchor='lm')

def sc_phone_feed(r,tg,fi,shot):
    cx,cy=W//2,H//2-60
    phone_frame(r,cx,cy,560,980)
    ox,oy=screen_origin(cx,cy,560,980)
    # 状态栏
    r.put(text_tex('23:47',22,GREY,font=F_SANS_R),ox+20,oy+18,anchor='lm')
    scroll=(tg*120)
    items=[('某个你认识的人，去世了？','刚刚 · 4.2 万阅读'),('专家：这件事没那么简单','2 万 · 推荐'),('最新消息：官方回应','热搜 · 1.1 万'),('十年前的今天','回忆 · 3 千')]
    for i,(ti,tg2) in enumerate(items):
        y=oy+70+((i*180-scroll)%720)
        if y<oy+40: continue
        feed_card(r,ox+15,y,500,140,ti,tg2,alpha=max(0,min(1,(y-oy-20)/80)))
    # 光晕
    gl=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(gl).ellipse((W//2-260,H//2-380,W//2+260,H//2+380),fill=(100,170,240,40))
    r.img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(70)))

def sc_phone_forward(r,tg,fi,shot):
    cx,cy=W//2,H//2-60
    phone_frame(r,cx,cy,560,980); ox,oy=screen_origin(cx,cy,560,980)
    panel(r,ox+25,oy+40,510,240,fill=(26,20,20,250),outline=(120,80,80))
    r.put(text_tex('某个你认识的人，去世了？',30,WHITE,font=F_SANS_R),ox+55,oy+100,anchor='lm')
    r.put(text_tex('消息来源：某群聊截图',22,GREY,font=F_SANS_R),ox+55,oy+150,anchor='lm')
    # 转发按钮
    tap=min(1,max(0,(tg-2.2)/0.7)); scale=1-0.08*math.sin(min(1,tap)*math.pi)
    lay=Image.new('RGBA',(300,90),(0,0,0,0)); d=ImageDraw.Draw(lay)
    col=(70,120,210,255) if tap<1 else (40,180,110,255)
    d.rounded_rectangle((2,2,298,88),radius=45,fill=col)
    r.put(lay,ox+255,oy+330)
    txt='转发' if tap<1 else '已转发 ✓'
    r.put(text_tex(txt,34,WHITE,font=F_SANS,glow=8),ox+255,oy+330)
    if tap>=1:
        r.put(text_tex('三个小时后',26,(235,235,235),font=F_SANS_R,glow=6),ox+255,oy+470,alpha=min(1,(tg-3.4)/0.8))

def sc_phone_rumor(r,tg,fi,shot):
    cx,cy=W//2,H//2-60
    phone_frame(r,cx,cy,560,980); ox,oy=screen_origin(cx,cy,560,980)
    panel(r,ox+25,oy+40,510,240,fill=(26,20,20,250),outline=(120,80,80))
    r.put(text_tex('某个你认识的人，去世了？',30,(160,160,160),font=F_SANS_R),ox+55,oy+100,anchor='lm')
    a=min(1,max(0,(tg-1.2)/0.6))
    # 辟谣 stamp
    lay=Image.new('RGBA',(330,130),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.rounded_rectangle((2,2,328,128),radius=10,outline=RED+(255,),width=6)
    d.text((36,26),'辟谣',font=ft(F_SANS,80),fill=RED+(255,))
    lay=lay.rotate(-8,expand=True,resample=Image.BICUBIC)
    r.put(lay,ox+255,oy+430,alpha=a)
    # 冷光/故障条
    if tg>1.6:
        for i in range(4):
            y=oy+120+int((tg*90+i*137)%700); h=random.Random(i*7+int(tg)).randint(2,10)
            lay2=Image.new('RGBA',(510,h),(150,200,255,40)); r.put(lay2,ox+25,y,alpha=0.6)
    r.put(text_tex('那天我在想：我一天要信错多少次，而我自己不知道？',26,(200,210,220),font=F_SANS_R,glow=6),W//2,1400,alpha=0)

def sc_data(r,tg,fi,shot):
    # 背景为机房（stock），叠加暗幕
    ve=Image.new('RGBA',(W,H),(4,6,10,180)); r.img.alpha_composite(ve)
    gl=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(gl).ellipse((W//2-420,H//2-600,W//2+420,H//2+600),fill=(40,110,170,50))
    r.img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(90)))
    nums=[('11.25 亿','中国网民'),('6.02 亿','生成式 AI 用户'),('42.8%','AI 普及率'),('+141.7%','一年增长')]
    t0=0.5; step=2.2
    for i,(num,lab) in enumerate(nums):
        a=max(0,min(1,(tg-t0-i*step)/0.8))
        if a<=0: continue
        y=430+i*230
        anim=1-0.15*(1-a)
        n=text_tex(num,int(96*anim),COOL,glow=28,glow_color=(90,180,255),glow_strength=0.55,stroke=2,stroke_color=(0,0,0))
        r.put(n,W//2-120,y,alpha=a)
        r.put(text_tex(lab,34,(180,196,214),font=F_SANS_R,glow=8),W//2+160,y+10,alpha=a)
        if i==3:
            r.put(text_tex('较 2024 年底',26,(140,156,176),font=F_SANS_R),W//2+160,y+64,alpha=a)
    r.put(text_tex('数据来源：CNNIC 第 57 次《中国互联网络发展状况统计报告》',22,(110,124,140),font=F_SANS_R),W//2,1500,alpha=0.8)

def sc_glitch(r,tg,fi,shot):
    ve=Image.new('RGBA',(W,H),(2,4,6,95)); r.img.alpha_composite(ve)
    rnd=np.random.default_rng(int(tg*30)); noise=(rnd.random((H//3,W//3))*255).astype(np.uint8); nim=Image.fromarray(noise,'L').resize((W,H)).convert('RGBA'); nim.putalpha(28); r.img.alpha_composite(nim)
    t=random.Random(int(tg*8))
    # 故障色块
    for i in range(8):
        y=t.randint(80,1400); h=t.randint(4,40); x=t.randint(-40,400); w=t.randint(200,800)
        lay=Image.new('RGBA',(w,h),(80+t.randint(0,120),40,60,60)); r.put(lay,x,y,alpha=0.5)
    # 标题
    a=min(1,tg/1.0)
    r.put(text_tex('AI 魔改',120,RED,glow=30,glow_color=(255,80,80),glow_strength=0.6,stroke=3,stroke_color=(0,0,0)),W//2,520,alpha=a)
    # 三个平台首周数据
    rows=[('微信','1078'),('抖音','1075'),('快手','1057')]
    for i,(k,v) in enumerate(rows):
        aa=max(0,min(1,(tg-3.0-i*0.9)/0.6))
        if aa<=0: continue
        r.put(text_tex(k,30,(190,200,210),font=F_SANS_R),260,900+i*110,alpha=aa)
        r.put(text_tex(v,44,WHITE,font=F_MONO),560,900+i*110,alpha=aa)
    r.put(text_tex('经典影视 · 批量替换',24,(150,160,170),font=F_SANS_R),W//2,1300,alpha=a)

def sc_expert(r,tg,fi,shot):
    # 批量虚拟专家卡片
    t0=0.4
    for i in range(6):
        a=max(0,min(1,(tg-t0-i*0.35)/0.7))
        if a<=0: continue
        cx=250+(i%2)*420; cy=420+(i//2)*380
        lay=Image.new('RGBA',(360,300),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.rounded_rectangle((1,1,359,299),radius=18,fill=(18,22,30,245),outline=(70,84,100))
        d.ellipse((30,30,120,120),fill=(60,78,96)); d.ellipse((52,52,98,98),fill=(110,130,150))
        r.put(lay,cx,cy,alpha=a)
        r.put(text_tex('专家 '+chr(0x2460+i),32,WHITE,font=F_SANS_R),cx+120,cy-80,alpha=a)
        r.put(text_tex('虚拟大学教授',24,GREY,font=F_SANS_R),cx+120,cy-40,alpha=a)
        r.put(text_tex('AI 生成',22,WARM,font=F_SANS_R,glow=6),cx+120,cy+10,alpha=a)
    if tg>3.0:
        r.put(text_tex('批量上线',64,RED,glow=20,glow_color=(255,90,90),glow_strength=0.5),W//2,1300,alpha=min(1,(tg-3.0)/0.8))

def sc_erase(r,tg,fi,shot):
    ve=Image.new('RGBA',(W,H),(2,4,8,150)); r.img.alpha_composite(ve)
    # 时间线
    y=980
    lay=Image.new('RGBA',(W-120,120),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.rounded_rectangle((1,1,W-122,118),radius=10,fill=(16,20,28,240),outline=(60,74,90))
    for i in range(10):
        d.rectangle((14+i*70,20,14+i*70+56,100),fill=(30,40,52) if i%3 else (44,60,78))
    r.put(lay,60,y,anchor='tl')
    # 水印
    wm=text_tex('AI 生成',44,(220,230,240),font=F_SANS,glow=10)
    r.put(wm,W//2,y-120,alpha=max(0,1-max(0,(tg-1.0)/0.7)))
    # 擦除扫光
    if tg>1.2:
        sx=60+min(1,(tg-1.2)/1.4)*(W-120)
        lay2=Image.new('RGBA',(int(W*1.2),8),(140,220,255,180)); r.put(lay2,sx,y-120+90,alpha=1)
    if tg>3.0:
        r.put(text_tex('已抹除',52,RED,glow=18,glow_color=(255,80,80),glow_strength=0.5),W//2,y-190,alpha=min(1,(tg-3.0)/0.6))

# 3D 洪水
FLOOD_GLYPHS=['AI','10万+','标题','点开','揭秘','转发','震惊','专家','独家','热搜','速看','真的？']
_rnd=random.Random(42)
PARTS=[]
for i in range(220):
    col=i%14; row=i//14
    PARTS.append({'x':-1.30+col*0.20+_rnd.uniform(-0.05,0.05),'z':_rnd.uniform(0.55,1.55),
                  'y0':row*0.42+_rnd.uniform(-0.2,0.2),'sp':_rnd.uniform(0.85,1.35),
                  'g':_rnd.choice(FLOOD_GLYPHS),'s':_rnd.uniform(0.9,1.7),'ph':_rnd.uniform(0,6.28)})

FLOOD_THUMBS=[]
_rnd2=random.Random(7)
for i in range(26):
    FLOOD_THUMBS.append((_rnd2.uniform(-1.4,1.4), _rnd2.uniform(-2.0,2.2), _rnd2.uniform(0.2,1.6), _rnd2.uniform(0.6,1.3)))

def sc_flood(r,tg,fi,shot):
    # 顶部源头光
    top=Image.new('RGBA',(W,380),(0,0,0,0)); td=ImageDraw.Draw(top)
    for yy in range(0,380,2):
        a=int(120*(1-yy/380)); td.line((0,yy,W,yy),fill=(230,242,255,a))
    r.put(top.filter(ImageFilter.GaussianBlur(10)),0,0,anchor='tl',depth=0.1)
    # 光束
    beams=Image.new('RGBA',(W,H),(0,0,0,0)); bd=ImageDraw.Draw(beams)
    for i in range(4):
        xx=140+i*190
        bd.polygon([(xx,0),(xx+90,0),(xx+190,H),(xx+40,H)],fill=(210,232,255,16))
    r.put(beams,0,0,anchor='tl',depth=0.2)
    # 卡片瀑布（4 列）
    glyphs=['AI','10万+','标题','点开','揭秘','转发','震惊','专家','独家','热搜','速看','真的？']
    for col in range(4):
        cx=150+col*200
        speed=520+col*70
        for k in range(9):
            y=((k*230+tg*speed+col*90) % 1500)-120
            if y<-60 or y>1500: continue
            w,h=150,116
            a=0.30+0.6*max(0,min(1,(1-abs(y-700)/700)))
            lay=Image.new('RGBA',(w,h),(0,0,0,0)); d=ImageDraw.Draw(lay)
            d.rounded_rectangle((1,1,w-2,h-2),radius=10,fill=(225,235,246,int(235*a)),outline=(255,255,255,255))
            d.rectangle((10,10,w-10,h//2),fill=(120,150,180,int(200*a)))
            r.put(lay,cx-w//2,y,anchor='tl',alpha=min(1,a*1.2),depth=1.0+col*0.1)
            g=glyphs[(k+col*3)%len(glyphs)]
            r.put(glyph_tex(g,(20,30,45),30),cx,y+h-24,alpha=min(1,a),depth=0.9)
            # 拖影
            streak=Image.new('RGBA',(2,110),(220,238,255,int(70*a))); r.put(streak,cx-2,y-108,anchor='tl',alpha=0.5,depth=1.1)
    # 底部堆积
    rnd=random.Random(11)
    for i in range(34):
        x=rnd.uniform(-20,W-140); y=1400-rnd.uniform(0,240)
        lay=Image.new('RGBA',(150,116),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.rounded_rectangle((1,1,148,114),radius=10,fill=(210,222,236,int(140+80*rnd.random())),outline=(255,255,255,220))
        r.put(lay,x,y,anchor='tl',alpha=0.32,depth=5)
    # 服务器组
    for i in range(7):
        xx=W//2-280+i*80
        lay=Image.new('RGBA',(70,180),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.rounded_rectangle((1,1,68,178),radius=6,fill=(10,14,20,255),outline=(50,90,110))
        for kk in range(5): d.ellipse((16,20+kk*30,28,32+kk*30),fill=(80,220,190))
        r.put(lay,xx,1010,anchor='tl',depth=9)
    # 光晕
    gl=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(gl).ellipse((W//2-380,H//2-520,W//2+380,H//2+520),fill=(80,160,230,40))
    r.img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(100)))

def sc_curve(r,tg,fi,shot):
    x0,y0=170,1240; x1,y1=760,560
    ax=text_tex('内容供给',30,COOL,font=F_SANS_R); r.put(ax,420,470)
    # 坐标与网格
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    for gy in range(y1-80,y0,110):
        d.line((x0,gy,x1,gy),fill=(90,104,120,60),width=1)
    d.line((x0,y0,x1,y0),fill=(170,184,200,235),width=4)
    d.line((x0,y0,x0,y1-120),fill=(170,184,200,235),width=4)
    r.put(lay,0,0,anchor='tl')
    # 供给曲线（指数上升）
    prog=min(1,tg/4.0); pts=[]
    for k in range(40):
        u=k/39*prog; xx=x0+u*(x1-x0); yy=y0-(u**2.2)*(y0-y1)
        pts.append((xx,yy))
    if len(pts)>1:
        lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.polygon(pts+[(pts[-1][0],y0),(x0,y0)],fill=(120,220,235,38))
        d.line(pts,fill=(120,220,235,245),width=6,joint='curve')
        r.put(lay,0,0,anchor='tl')
        r.put(text_tex('趋近于零',30,COOL,font=F_SANS_R,glow=8),pts[-1][0]+40,pts[-1][1]-20)
    # 注意力平线
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.line((x0,900,x1,900),fill=(240,195,106,200),width=4)
    r.put(lay,0,0,anchor='tl')
    r.put(text_tex('注意力',30,WARM,font=F_SANS_R,glow=8),x1-40,850)
    if tg>3.2:
        a=min(1,(tg-3.2)/0.7); pulse=1+0.15*math.sin(tg*6)
        r.put(text_tex('交叉',26,RED,font=F_SANS_R),580,900,alpha=a)
        lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.ellipse((600-10*pulse,900-10*pulse,600+10*pulse,900+10*pulse),outline=RED+(255,),width=4)
        r.put(lay,0,0,anchor='tl',alpha=a)

def sc_creator(r,tg,fi,shot):
    ve=Image.new('RGBA',(W,H),(2,4,8,160)); r.img.alpha_composite(ve)
    titles=['震惊！99% 的人不知道','三天涨粉十万的秘密','再不看她你就亏了','专家不会告诉你的真相']
    for i,ti in enumerate(titles):
        a=max(0,min(1,(tg-0.5-i*0.5)/0.6))
        if a<=0: continue
        lay=Image.new('RGBA',(620,110),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.rounded_rectangle((1,1,618,108),radius=12,fill=(24,20,28,245),outline=(120,90,110))
        r.put(lay,140,380+i*170,alpha=a)
        r.put(text_tex(ti,30,WHITE,font=F_SANS_R),450,435+i*170,alpha=a)
        r.put(text_tex('封面 · 第 %d 版'%(i+1),20,GREY,font=F_SANS_R),620,500+i*170,alpha=a)
    r.put(text_tex('改到第 37 版 还是没人点',30,(200,190,170),font=F_SANS_R,glow=6),W//2,1280,alpha=min(1,max(0,(tg-3.5)/0.8)))

def sc_law(r,tg,fi,shot):
    y=820
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.line((120,y,W-120,y),fill=(120,136,152,220),width=4)
    r.put(lay,0,0,anchor='tl')
    nodes=[('2025-03','公布',0.6),('2025-09','施行',2.6),('平台核验','显式 + 隐式标识',4.6)]
    for i,(k,v,t0) in enumerate(nodes):
        a=max(0,min(1,(tg-t0)/0.7))
        if a<=0: continue
        x=210+i*240
        lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.ellipse((x-14,y-14,x+14,y+14),fill=(120,220,235,255))
        r.put(lay,0,0,anchor='tl',alpha=a)
        r.put(text_tex(k,28,COOL,font=F_MONO),x,y-80,alpha=a)
        r.put(text_tex(v,24,GREY,font=F_SANS_R),x,y+70,alpha=a)
    if tg>5.4:
        r.put(text_tex('可 是 谁 在 隐 藏 标 识',44,WHITE,font=F_SANS,glow=16,glow_color=(120,200,255),glow_strength=0.5),W//2,1120,alpha=min(1,(tg-5.4)/0.8))

def sc_dual(r,tg,fi,shot):
    for i in range(2):
        cx=250+i*400; cy=820; w,h=300,600
        lay=Image.new('RGBA',(w,h),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.rounded_rectangle((1,1,w-2,h-2),radius=24,fill=(10,14,20,255),outline=(90,110,130),width=3)
        r.put(lay,cx,cy)
        # 内容块
        lay2=Image.new('RGBA',(w-30,110),(0,0,0,0)); d2=ImageDraw.Draw(lay2)
        d2.rounded_rectangle((1,1,w-32,108),radius=8,fill=(30,40,52)); r.put(lay2,cx-1,cy-200)
        r.put(text_tex('某条内容',24,(200,210,220),font=F_SANS_R),cx,cy-140)
    # 左：AI 生成 标识
    chip(r,'AI 生成',140,1080,color=COOL,fill=(14,30,44,240))
    # 右：标识被抹掉
    if tg>2.2:
        a=min(1,(tg-2.2)/0.7)
        chip(r,'标识已隐藏',450,1080,color=RED,fill=(40,16,16,240))
        lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.rounded_rectangle((480,1080,800,1180),radius=30,outline=RED,width=4); r.put(lay,0,0,anchor='tl',alpha=a)
    r.put(text_tex('左：合规发布　右：换个号再发',24,(160,170,180),font=F_SANS_R),W//2,1320)

def sc_sieve(r,tg,fi,shot):
    ang=0.35+0.55*tg
    R0=2.05
    cam=E.Camera((R0*math.sin(ang),-R0*math.cos(ang),1.15),(0,0,0.15),fov_deg=42); r.cam=cam
    # 金属盘面（半透明填充）
    disc=[]
    for k in range(48):
        a=k/48*2*math.pi; disc.append([0.5*math.cos(a),0.5*math.sin(a),0.0])
    scr,zc=cam.project(np.array(disc))
    if (zc>0.1).all():
        lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.polygon([(float(x),float(y)) for x,y in scr],fill=(150,166,182,130))
        r.put(lay,0,0,anchor='tl',alpha=0.9,depth=0.7)
    # 暖金外圈
    ringpts=[]
    for k in range(61):
        a=k/60*2*math.pi; ringpts.append([0.52*math.cos(a),0.52*math.sin(a),0.0])
    scr,zc=cam.project(np.array(ringpts))
    if (zc>0.1).all():
        lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.line([(float(x),float(y)) for x,y in scr],fill=(240,195,105,235),width=5,joint='curve')
        r.put(lay,0,0,anchor='tl',alpha=0.9,depth=0.75)
    # 筛子环
    for ring in [0.5,0.36,0.22]:
        pts=[]
        for k in range(41):
            a=k/40*2*math.pi
            pts.append([ring*math.cos(a),ring*math.sin(a),0.0])
        scr,zc=cam.project(np.array(pts))
        if (zc<=0.1).any(): continue
        lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.line([(float(x),float(y)) for x,y in scr],fill=(225,236,248,240),width=4,joint='curve')
        r.put(lay,0,0,anchor='tl',alpha=0.9,depth=0.5)
    # 金属筛网：横竖细线
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    for gx in range(-5,6):
        scr,zc=cam.project(np.array([[gx*0.1,-0.5,0],[gx*0.1,0.5,0]]))
        if (zc<=0.1).any(): continue
        d.line([(float(scr[0][0]),float(scr[0][1])),(float(scr[1][0]),float(scr[1][1]))],fill=(205,218,232,120),width=1)
    for gy in range(-5,6):
        scr,zc=cam.project(np.array([[-0.5,gy*0.1,0],[0.5,gy*0.1,0]]))
        if (zc<=0.1).any(): continue
        d.line([(float(scr[0][0]),float(scr[0][1])),(float(scr[1][0]),float(scr[1][1]))],fill=(205,218,232,120),width=1)
    r.put(lay,0,0,anchor='tl',alpha=0.55,depth=0.6)
    # 辐条
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    for k in range(12):
        a=k/12*2*math.pi
        scr,zc=cam.project(np.array([[0,0,0],[0.5*math.cos(a),0.5*math.sin(a),0]]))
        if (zc<=0.1).any(): continue
        d.line([(float(scr[0][0]),float(scr[0][1])),(float(scr[1][0]),float(scr[1][1]))],fill=(190,204,218,200),width=2)
    r.put(lay,0,0,anchor='tl',alpha=0.8,depth=0.4)
    # 上方被筛的粒子
    for i,p in enumerate(PARTS[:48]):
        y=1.15-((tg*0.5+p['ph']*0.08)%1.1)
        pos=np.array([[0.4*math.sin(p['ph']*2.3)*0.5+0.05*math.sin(tg+p['ph']), y, 0.02]])
        scr,zc=cam.project(pos)
        if zc[0]<=0.1: continue
        sx,sy=scr[0][0],scr[0][1]
        if y<0.35: continue
        r.put(glyph_tex(p['g'],COOL,20*p['s']),sx,sy,alpha=0.22,depth=float(zc[0]))
    # 下方光流（被筛下的真）
    pts=[]
    for k in range(30):
        y=-0.1-k*0.045; pts.append([0.06*math.sin(tg*2+k*0.4),y,0.05])
    scr,zc=cam.project(np.array(pts))
    if (zc>0.1).all():
        lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.line([(float(x),float(y)) for x,y in scr],fill=(245,205,115,255),width=8,joint='curve')
        # 光流辉光
        bloom=Image.new('RGBA',(W,H),(0,0,0,0)); bd=ImageDraw.Draw(bloom)
        bd.line([(float(x),float(y)) for x,y in scr],fill=(255,215,130,110),width=26,joint='curve')
        r.put(bloom.filter(ImageFilter.GaussianBlur(14)),0,0,anchor='tl',alpha=0.9,depth=0.25)
        r.put(lay,0,0,anchor='tl',alpha=0.98,depth=0.2)
        r.put(text_tex('真的',32,WARM,font=F_SANS,glow=14),scr[-1][0],scr[-1][1]+60,alpha=0.9)

def sc_source(r,tg,fi,shot):
    ve=Image.new('RGBA',(W,H),(2,4,8,150)); r.img.alpha_composite(ve)
    chips=[('来源①  官方通报','cool'),('来源②  主流媒体','cool'),('来源③  原始文件','cool')]
    for i,(tx,_) in enumerate(chips):
        a=max(0,min(1,(tg-0.4-i*0.6)/0.6))
        if a<=0: continue
        chip(r,tx,120,360+i*150,size=32,color=COOL,fill=(14,26,38,240))
    if tg>2.6:
        a=min(1,(tg-2.6)/0.7)
        chip(r,'署名：作者本名/机构',120,880,size=32,color=WARM,fill=(34,26,14,240))
        chip(r,'责任：出了事谁担',120,1030,size=32,color=WARM,fill=(34,26,14,240))
        r.put(text_tex('可核 · 可署名 · 可负责',44,WHITE,font=F_SANS,glow=16,glow_color=(240,200,110),glow_strength=0.5),W//2,1250,alpha=a)

def sc_city(r,tg,fi,shot):
    ve=Image.new('RGBA',(W,H),(2,4,10,110)); r.img.alpha_composite(ve)
    for i in range(3):
        x=200+i*250; y=1150-int((tg*40+i*30)%120)
        r.put(text_tex(['热搜','推荐','辟谣'][i],20,COOL,font=F_SANS_R,glow=4),x,y,alpha=0.5)

def sc_scroll(r,tg,fi,shot):
    ve=Image.new('RGBA',(W,H),(2,4,8,140)); r.img.alpha_composite(ve)
    cx,cy=W//2,H//2-40
    phone_frame(r,cx,cy,520,920); ox,oy=screen_origin(cx,cy,520,920)
    scroll=tg*260
    for i in range(5):
        y=oy+60+((i*190-scroll)%760)
        if y<oy+40: continue
        feed_card(r,ox+20,y,480,140,'第 %d 条'%((i+int(tg*2))%9+1),'划走',alpha=0.9)
    if tg>7.0:
        a=min(1,(tg-7.0)/0.8)
        r.put(text_tex('长按 · 停住',34,WHITE,font=F_SANS,glow=12),W//2,oy+720,alpha=a)

def sc_clause(r,tg,fi,shot):
    ve=Image.new('RGBA',(W,H),(2,4,8,170)); r.img.alpha_composite(ve)
    lines=['条款一：什么范围内我担着','条款二：什么范围外我不担','条款三：出了事，第一个动作是认账']
    for i,l in enumerate(lines):
        a=max(0,min(1,(tg-0.6-i*1.0)/0.7))
        if a<=0: continue
        lay=Image.new('RGBA',(700,100),(0,0,0,0)); d=ImageDraw.Draw(lay)
        d.rounded_rectangle((1,1,698,98),radius=12,fill=(18,24,30,245),outline=(80,140,150))
        r.put(lay,100,500+i*160,alpha=a)
        r.put(text_tex(l,30,WHITE,font=F_SANS_R),450,550+i*160,alpha=a)
    if tg>4.4:
        r.put(text_tex('不是表态 是兜底',52,WARM,font=F_SANS,glow=20,glow_color=(240,190,100),glow_strength=0.5),W//2,1150,alpha=min(1,(tg-4.4)/0.8))

def sc_publish(r,tg,fi,shot):
    ve=Image.new('RGBA',(W,H),(2,4,8,170)); r.img.alpha_composite(ve)
    cx,cy=W//2,H//2-60
    phone_frame(r,cx,cy,480,860); ox,oy=screen_origin(cx,cy,480,860)
    lay=Image.new('RGBA',(360,100),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.rounded_rectangle((2,2,358,98),radius=50,fill=(40,160,110,255))
    r.put(lay,ox+60,oy+560,anchor='tl')
    r.put(text_tex('发 布',34,WHITE,font=F_SANS),ox+240,oy+610)
    if tg>1.6:
        r.put(text_tex('本片含 AI 辅助制作',22,(200,210,220),font=F_SANS_R,glow=4),ox+240,oy+700,alpha=min(1,(tg-1.6)/0.8))

def sc_lamp(r,tg,fi,shot):
    ve=Image.new('RGBA',(W,H),(2,3,6,110)); r.img.alpha_composite(ve)

def endcard(r,tg,fi,shot):
    lay=Image.new('RGBA',(W,H),(0,0,0,255)); r.img=lay
    a=min(1,tg/1.0)
    r.put(text_tex('内容洪水里',52,WHITE,font=F_SERIF,glow=10),W//2,620,alpha=a)
    r.put(text_tex('最贵的是「真的」',64,WARM,font=F_SERIF,glow=18,glow_color=(240,190,100),glow_strength=0.5),W//2,750,alpha=a)
    r.put(text_tex('关注 · 一起做点经得起核实的内容',26,(170,180,190),font=F_SANS_R,glow=6),W//2,1000,alpha=max(0,min(1,(tg-1.2)/0.8)))
    r.put(text_tex('画面与配音含 AI 辅助制作',20,(120,130,140),font=F_SANS_R),W//2,1450,alpha=0.8)

SCENE={'cold':sc_cold,'phone_feed':sc_phone_feed,'phone_forward':sc_phone_forward,'phone_rumor':sc_phone_rumor,
 'data':sc_data,'glitch':sc_glitch,'expert':sc_expert,'erase':sc_erase,'flood':sc_flood,'curve':sc_curve,
 'creator':sc_creator,'law':sc_law,'dual':sc_dual,'hist_print':lambda r,tg,fi,s: sc_hist(r,tg,fi,s,'印刷术','活字 · 报纸'),
 'hist_tv':lambda r,tg,fi,s: sc_hist(r,tg,fi,s,'电视','频道 · 收视率'),'hist_phone':lambda r,tg,fi,s: sc_hist(r,tg,fi,s,'互联网','网站 · 平台'),
 'sieve':sc_sieve,'source':sc_source,'city':sc_city,'scroll':sc_scroll,'clause':sc_clause,'publish':sc_publish,'lamp':sc_lamp,'endcard':endcard}

def sc_hist(r,tg,fi,shot,era,sub):
    ve=Image.new('RGBA',(W,H),(2,4,8,95)); r.img.alpha_composite(ve)
    a=min(1,tg/0.8)
    r.put(text_tex(era,84,WHITE,font=F_SERIF,glow=22,glow_color=(240,220,180),glow_strength=0.6,stroke=2),W//2,430,alpha=a)
    r.put(text_tex(sub,32,(235,220,195),font=F_SANS_R,glow=8),W//2,540,alpha=a)
    # 扫描线
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    for yy in range(0,H,4): d.line((0,yy,W,yy),fill=(0,0,0,60))
    r.put(lay,0,0,anchor='tl',alpha=0.5)
    for i in range(24):
        y=(i*61+int(tg*120))%H
        r.put(glyph_tex(FLOOD_GLYPHS[i%len(FLOOD_GLYPHS)],COOL,20),60+i*35,y,alpha=0.35)

def shot_at(t):
    for s in SHOTS:
        if s['start']<=t<s['end']: return s
    return SHOTS[-1]

def load_bg(fi):
    p=os.path.join(ROOT,'work','bg',f'f{fi:05d}.jpg')
    if os.path.exists(p):
        try: return Image.open(p).convert('RGBA')
        except Exception: pass
    return None

def render_frame(fi):
    t=fi/FPS
    shot=shot_at(t); tg=t-shot['start']
    bg=load_bg(fi)
    r=R(bg if bg else dark_bg(t, seed=shot['i']))
    if bg is not None:
        ve=Image.new('RGBA',(W,H),(4,8,14,40)); r.img.alpha_composite(ve)
    fn=SCENE.get(shot['label'])
    if fn: fn(r,tg,fi,shot)
    # 花字
    for (si,off,txt,col) in HUA:
        if shot['i']==si and tg>=off:
            a=min(1,(tg-off)/0.5); h=hua_tex(txt,0,color=col)
            r.put(h,W//2,360,alpha=a)
    # 转场淡入（每个镜头前 0.25s）
    if tg<0.25:
        black=Image.new('RGBA',(W,H),(0,0,0,int(255*(1-tg/0.25)))); r.img.alpha_composite(black)
    r.flush()
    caption(r,t)
    return post(r.img,fi)

def write(fi):
    im=render_frame(fi)
    im.save(os.path.join(ROOT,'work','frames',f'f{fi:05d}.jpg'),quality=91)

def main(start,end):
    os.makedirs(os.path.join(ROOT,'work','frames'),exist_ok=True)
    t0=time.time()
    for fi in range(start,end):
        write(fi)
        if (fi-start)%200==0: print(fi,'/',end,'%.1fs'%(time.time()-t0),flush=True)

if __name__=='__main__':
    a=int(sys.argv[1]); b=int(sys.argv[2]); main(a,b)
