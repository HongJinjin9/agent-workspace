#!/usr/bin/env python3
"""逐段 edge-tts：生成 mp3 + 句级 SRT + 实测时长。"""
import json, os, re, subprocess
ROOT=os.path.dirname(os.path.abspath(__file__))
FF='/home/admin/.local/bin/ffmpeg'
EDGE='/home/admin/.local/bin/edge-tts'
VOICE='zh-CN-YunjianNeural'
os.makedirs(f'{ROOT}/work/tts',exist_ok=True); os.makedirs(f'{ROOT}/work/srt',exist_ok=True)
d={}
for key,text in json.load(open(f'{ROOT}/narration/segments.json',encoding='utf-8')).items():
    k=key.lower()
    open(f'{ROOT}/narration/{k}.txt','w',encoding='utf-8').write(text)
    subprocess.run([EDGE,'--voice',VOICE,'--file',f'{ROOT}/narration/{k}.txt','--write-media',f'{ROOT}/work/tts/{k}.mp3',
                    '--write-subtitles',f'{ROOT}/work/srt/{k}.srt','--no-progress'],check=True)
    r=subprocess.run([FF,'-hide_banner','-i',f'{ROOT}/work/tts/{k}.mp3'],capture_output=True,text=True)
    m=re.search(r'Duration: (\d+):(\d+):([\d.]+)',r.stderr)
    d[k]=round(int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3)),3)
json.dump(d,open(f'{ROOT}/work/tts/durations.json','w'))
print(d,'total',round(sum(d.values()),2))
