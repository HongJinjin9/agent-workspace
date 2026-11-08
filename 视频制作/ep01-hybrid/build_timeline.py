import json, math
D=json.load(open('work/tts/durations.json'))
LEAD=3.0
segs=[]
prev=0.0
gaps={'S1':None,'S2':1.6,'S3':1.8,'S4':2.4,'S5':2.6,'S6':5.2}
for i,k in enumerate(['S1','S2','S3','S4','S5','S6']):
    vo=D[k]['duration']
    dur=(LEAD+vo) if k=='S1' else (vo+gaps[k])
    start=prev
    vo_start=start+(LEAD if k=='S1' else 0.3)
    segs.append({'id':k,'start':round(start,2),'dur':round(dur,2),'end':round(start+dur,2),
                 'vo_start':round(vo_start,2),'vo_dur':round(vo,2),'text':D[k]['text'],'file':D[k]['file']})
    prev=start+dur
TOTAL=round(prev,2)
# design shot ranges per segment (design absolute seconds)
DESIGN={'S1':(0,22),'S2':(22,67),'S3':(67,101),'S4':(101,180),'S5':(180,208),'S6':(208,260)}
SHOTS=[
 (1,'S1',0,3,'single','car_dash',0.0,'dash'),
 (2,'S1',3,9,'single','car_dash',2.0,'dash'),
 (3,'S1',9,17,'single','brake_pedal',2.0,'regen'),
 (4,'S1',17,22,'single','desk_lamp',1.0,'desk'),
 (5,'S2',22,31,'split',['metro_window','desk_lamp'],0.0,'split'),
 (6,'S2',31,40,'montage',['piano_hands','woodworking','keyboard_typing'],0.0,'montage'),
 (7,'S2',40,55,'single','phone_desk',1.0,'phone'),
 (8,'S2',55,67,'single','empty_chair',1.0,'pullout'),
 (9,'S3',67,74,'dark',None,0.0,'diagram_intro'),
 (10,'S3',74,93,'dark',None,0.0,'diagram_modes'),
 (11,'S3',93,97,'single','pen_writing',0.5,'write'),
 (12,'S3',97,101,'dark',None,0.0,'fourgrid'),
 (13,'S4',101,115,'single','rain_window',1.0,'quiet'),
 (14,'S4',115,133,'single','keyboard_typing',1.0,'ai'),
 (15,'S4',133,156,'montage',['running','tea','reading'],0.0,'warm'),
 (16,'S4',156,174,'single','car_interior_night',1.0,'regen2'),
 (17,'S4',174,180,'dark',None,0.0,'fourgrid2'),
 (18,'S5',180,187,'single','crumpled_paper',0.5,'paper'),
 (19,'S5',187,194,'single','rain_window',2.0,'rain'),
 (20,'S5',194,199,'single','crumpled_paper',3.0,'paper2'),
 (21,'S5',199,208,'single','pen_writing',2.0,'write2'),
 (22,'S6',208,228,'single','city_night_aerial',0.0,'city'),
 (23,'S6',228,242,'single','car_interior_night',3.0,'hud'),
 (24,'S6',242,257,'single','desk_lamp',8.0,'outro'),
 (25,'S6',257,260,'dark',None,0.0,'endcard'),
]
shots=[]
for sid,(design0,design1) in DESIGN.items():
    seg=next(s for s in segs if s['id']==sid)
    for (num,s_,d0,d1,typ,src,src_t,kind) in SHOTS:
        if s_!=sid: continue
        a=seg['start']+(d0-design0)/(design1-design0)*seg['dur']
        b=seg['start']+(d1-design0)/(design1-design0)*seg['dur']
        shots.append({'n':num,'start':round(a,3),'end':round(b,3),'dur':round(b-a,3),
                      'type':typ,'src':src,'src_t':src_t,'kind':kind,'seg':sid})
json.dump({'fps':24,'total':TOTAL,'segments':segs,'shots':shots}, open('work/timeline.json','w'), ensure_ascii=False, indent=1)
print('total', TOTAL, 'frames', int(TOTAL*24), 'shots', len(shots))
for s in shots: print(s['n'], s['start'], s['end'], s['kind'])
