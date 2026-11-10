import json, os
ROOT=os.path.dirname(os.path.abspath(__file__))
D=json.load(open(f'{ROOT}/work/tts/durations.json'))  # s1..s6
COLD=4.0; GAP=0.8; TAIL=4.0
order=['s1','s2','s3','s4','s5','s6']
segs=[]; t=COLD
for k in order:
    d=D[k]; segs.append({'id':k.upper(),'file':f'work/tts/{k}.mp3','start':round(t,3),'dur':round(d,3),'vo_start':round(t,3),'vo_dur':round(d,3)})
    t+=d+GAP
total=round(t-GAP+TAIL,3)  # last narrated segment end + tail
seg_map={s['id']:s for s in segs}
S1,S2,S3,S4,S5,S6=[seg_map[x] for x in ['S1','S2','S3','S4','S5','S6']]
# 分镜（与稿件 v2.2 §3 对齐，按实测时间轴微调）
def sh(i,a,b,kind,src=None,label=''):
    return {'i':i,'start':round(a,3),'end':round(b,3),'kind':kind,'src':src,'label':label}
shots=[
 sh(1,0.0,COLD,'dark',None,'cold'),
 sh(2,COLD,S1['start']+6.0,'dark',None,'phone_feed'),
 sh(3,S1['start']+6.0,S1['start']+12.0,'dark',None,'phone_forward'),
 sh(4,S1['start']+12.0,S1['start']+S1['dur'],'dark',None,'phone_rumor'),
 sh(5,S2['start'],S2['start']+12.0,'stock','datacenter','data'),
 sh(6,S2['start']+12.0,S2['start']+22.0,'stock','old_tv','glitch'),
 sh(7,S2['start']+22.0,S2['start']+33.0,'dark',None,'expert'),
 sh(8,S2['start']+33.0,S2['start']+S2['dur'],'stock','desk_lamp','erase'),
 sh(9,S3['start'],S3['start']+15.0,'dark',None,'flood'),
 sh(10,S3['start']+15.0,S3['start']+S3['dur'],'dark',None,'curve'),
 sh(11,S4['start'],S4['start']+15.0,'stock','laptop_night','creator'),
 sh(12,S4['start']+15.0,S4['start']+30.0,'dark',None,'law'),
 sh(13,S4['start']+30.0,S4['start']+S4['dur'],'dark',None,'dual'),
 sh(14,S5['start'],S5['start']+5.0,'stock','printing_press','hist_print'),
 sh(15,S5['start']+5.0,S5['start']+10.0,'stock','old_tv','hist_tv'),
 sh(16,S5['start']+10.0,S5['start']+15.5,'stock','phone_scroll','hist_phone'),
 sh(17,S5['start']+15.5,S5['start']+S5['dur'],'dark',None,'sieve'),
 sh(18,S6['start'],S6['start']+14.0,'stock','pen_writing','source'),
 sh(19,S6['start']+14.0,S6['start']+28.0,'stock','citynight','city'),
 sh(20,S6['start']+28.0,S6['start']+42.0,'stock','phone_dark','scroll'),
 sh(21,S6['start']+42.0,S6['start']+54.0,'stock','servers','clause'),
 sh(22,S6['start']+54.0,S6['start']+62.0,'stock','phone_dark','publish'),
 sh(23,S6['start']+62.0,S6['start']+S6['dur'],'stock','desk_lamp','lamp'),
 sh(24,S6['start']+S6['dur'],total,'dark',None,'endcard'),
]
tl={'total':total,'fps':24,'segments':segs,'shots':shots}
json.dump(tl,open(f'{ROOT}/work/timeline.json','w'),ensure_ascii=False,indent=1)
print('total',total,'frames',round(total*24),'shots',len(shots))
for s in segs: print(s['id'],s['start'],s['dur'],'vo_start',s['vo_start'])
