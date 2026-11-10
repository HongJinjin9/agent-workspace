import os, json, re, subprocess, urllib.parse
ROOT='/app/vedio/ep02-flood'
def load_keys():
    for line in open('/app/vedio/china-aigc/keys.env', encoding='utf-8'):
        m=re.match(r'\s*export\s+([A-Z_]+)\s*=\s*(.+)', line)
        if m: os.environ[m.group(1)]=m.group(2).strip().strip('"').strip("'")
load_keys()
KEY=os.environ.get('PEXELS_API_KEY','')
os.makedirs(f'{ROOT}/assets/stock', exist_ok=True)
Q={
 'phone_scroll':'scrolling phone screen',
 'phone_dark':'phone in hand dark',
 'printing_press':'printing press newspaper',
 'old_tv':'old tv static',
 'flood_water':'water flood',
 'metal_mesh':'metal mesh',
 'editing_timeline':'video editing screen',
 'crowd_screen':'people crowd screen',
 'night_desk':'desk night lamp',
 'tv_screen':'television screen',
}
def search(q, per=5):
    url='https://api.pexels.com/videos/search?'+urllib.parse.urlencode({'query':q,'per_page':per,'orientation':'landscape'})
    out=subprocess.run(['curl','-sL','-m','60','-H',f'Authorization: {KEY}','-A','Mozilla/5.0',url],capture_output=True,text=True).stdout
    try: return json.loads(out)
    except Exception: return {}
def pick(v):
    files=[f for f in v.get('video_files',[]) if (f.get('width') or 0)>=1280 and f.get('file_type')=='video/mp4']
    files.sort(key=lambda f:(f.get('width') or 0))
    return files[0]['link'] if files else None
for name,q in Q.items():
    if os.path.exists(f'{ROOT}/assets/stock/{name}.mp4'):
        print('skip',name); continue
    data=search(q)
    url=None
    for v in data.get('videos',[]):
        url=pick(v)
        if url: break
    if not url:
        print('MISS',name,flush=True); continue
    subprocess.run(['curl','-sL','-m','180','-A','Mozilla/5.0','-o',f'{ROOT}/assets/stock/{name}.mp4',url],check=True)
    print('ok',name,os.path.getsize(f'{ROOT}/assets/stock/{name}.mp4'),flush=True)
