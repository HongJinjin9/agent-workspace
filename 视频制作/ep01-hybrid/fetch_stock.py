import os, json, re, subprocess, urllib.parse
ROOT='/app/vedio/ep01-hybrid'
def load_keys():
    for line in open('/app/vedio/china-aigc/keys.env', encoding='utf-8'):
        m=re.match(r'\s*export\s+([A-Z_]+)\s*=\s*(.+)', line)
        if m: os.environ[m.group(1)]=m.group(2).strip().strip('"').strip("'")
load_keys()
KEY=os.environ.get('PEXELS_API_KEY','')
os.makedirs(f'{ROOT}/assets/stock', exist_ok=True)
Q={
 'car_dash':'car dashboard',
 'steering_night':'driving car night',
 'brake_pedal':'car pedal foot',
 'desk_lamp':'desk lamp night',
 'laptop_night':'laptop keyboard night',
 'metro_window':'subway train window',
 'city_day':'city traffic aerial',
 'piano_hands':'piano hands',
 'woodworking':'woodworking hands',
 'keyboard_typing':'typing keyboard',
 'phone_desk':'phone on desk',
 'empty_chair':'empty chair office',
 'pen_writing':'writing pen paper',
 'rain_window':'rain window night',
 'crumpled_paper':'crumpled paper',
 'city_night_aerial':'city night aerial',
 'car_interior_night':'car interior night',
 'desk_notebook':'notebook desk',
 'car_engine':'car engine',
 'battery':'battery',
 'running':'running morning',
 'tea':'tea steam',
 'reading':'book reading hands',
}
def search(q, per=5):
    url='https://api.pexels.com/videos/search?'+urllib.parse.urlencode({'query':q,'per_page':per,'orientation':'landscape'})
    out=subprocess.run(['curl','-sL','-m','60','-H',f'Authorization: {KEY}','-A','Mozilla/5.0',url],capture_output=True,text=True).stdout
    return json.loads(out)
def pick(v):
    files=[f for f in v.get('video_files',[]) if (f.get('width') or 0)>=1280 and f.get('file_type')=='video/mp4']
    files=sorted(files, key=lambda f:(abs((f.get('width') or 0)-1920), (f.get('height') or 0)))
    return files[0] if files else None
for name,q in Q.items():
    out=f'{ROOT}/assets/stock/{name}.mp4'
    if os.path.exists(out) and os.path.getsize(out)>50000: print('skip',name); continue
    try:
        d=search(q)
        got=None
        for v in d.get('videos',[]):
            f=pick(v)
            if f: got=(v,f); break
        if not got: print('no',name); continue
        v,f=got
        subprocess.run(['curl','-sL','-m','180','-o',out,f['link']],check=True)
        print('ok',name,f.get('width'),'x',f.get('height'),v.get('duration'),'s',os.path.getsize(out),flush=True)
    except Exception as e:
        print('ERR',name,str(e)[:100],flush=True)
