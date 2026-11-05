import json, os, subprocess, re, sys
spec=json.load(open('beats.json',encoding='utf-8'))
os.makedirs('assets/tts',exist_ok=True)
FFMPEG='/home/admin/.local/bin/ffmpeg'
def dur(f):
    o=subprocess.run([FFMPEG,'-hide_banner','-i',f],capture_output=True,text=True).stderr
    m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',o)
    return int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3))
out=[]
for b in spec['beats']:
    f=f"assets/tts/{b['id']}.mp3"
    if not (os.path.exists(f) and os.path.getsize(f)>1000):
        subprocess.run(['/home/admin/.local/bin/edge-tts','--voice',spec['voice'],'--rate',spec['rate'],'--text',b['text'],'--write-media',f],check=True)
    d=dur(f); out.append({**b,'file':f,'duration':d})
    print(b['id'], round(d,2), 's')
json.dump(out,open('work/narration.json','w'),ensure_ascii=False,indent=2)
print('total', round(sum(x['duration'] for x in out),2), 's')
