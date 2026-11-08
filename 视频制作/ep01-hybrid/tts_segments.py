import json, subprocess, os
from pathlib import Path
EDGE='/home/admin/.local/bin/edge-tts'
FF='/home/admin/.local/bin/ffmpeg'
segs=json.load(open('narration/segments.json'))
os.makedirs('work/tts',exist_ok=True)
out={}
for k in ['S1','S2','S3','S4','S5','S6']:
    txt=segs[k]
    mp3=f'work/tts/{k.lower()}.mp3'
    subprocess.run([EDGE,'--voice','zh-CN-YunjianNeural','--text',txt,'--write-media',mp3],check=True)
    r=subprocess.run([FF,'-hide_banner','-i',mp3],capture_output=True,text=True)
    import re
    m=re.search(r'Duration: (\d+):(\d+):([\d.]+)', r.stderr)
    dur=int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3))
    out[k]={'file':mp3,'duration':round(dur,2),'text':txt}
    print(k, round(dur,2), flush=True)
json.dump(out, open('work/tts/durations.json','w'), ensure_ascii=False, indent=1)
print('total', round(sum(v['duration'] for v in out.values()),2))
