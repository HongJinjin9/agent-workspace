"""Parse edge-tts SRT cues and build precisely timed caption lines (<=14 chars)."""
import re, json, os

ROOT = os.path.dirname(os.path.abspath(__file__))
SEGS = ['s1', 's2', 's3', 's4', 's5', 's6']


def parse_srt(path):
    txt = open(path, encoding='utf-8').read().strip()
    cues = []
    for block in re.split(r'\n\s*\n', txt):
        lines = [l for l in block.split('\n') if l.strip()]
        if len(lines) < 2:
            continue
        m = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)', lines[1] if '-->' in lines[1] else lines[0])
        if not m:
            continue
        g = list(map(int, m.groups()))
        start = g[0]*3600 + g[1]*60 + g[2] + g[3]/1000.0
        end = g[4]*3600 + g[5]*60 + g[6] + g[7]/1000.0
        text = ''.join(lines[2:]) if '-->' in lines[1] else ''.join(lines[1:])
        cues.append((start, end, text.strip()))
    return cues


def _split(text, maxlen=14):
    parts = re.split(r'(?<=[。；！？，、：])', text)
    out = []
    for p in parts:
        p = p.strip()
        while len(p) > maxlen:
            out.append(p[:maxlen]); p = p[maxlen:]
        if p:
            out.append(p)
    merged = []
    for p in out:
        if merged and len(merged[-1]) + len(p) <= maxlen:
            merged[-1] += p
        else:
            merged.append(p)
    return merged


def build_caps(timeline):
    segs = {s['id'].lower(): s for s in timeline['segments']}
    caps = []
    for key in SEGS:
        seg = segs[key]
        srt = os.path.join(ROOT, 'work', 'srt', key + '.srt')
        if not os.path.exists(srt):
            continue
        cues = parse_srt(srt)
        for (cs, ce, text) in cues:
            chunks = _split(text)
            if not chunks:
                continue
            total = sum(len(c) for c in chunks)
            t = seg['vo_start'] + cs
            dur = max(0.12, ce - cs)
            for c in chunks:
                d = dur * len(c) / total
                caps.append({'start': round(t, 3), 'end': round(t + d, 3), 'text': c})
                t += d
    caps.sort(key=lambda x: x['start'])
    # avoid gaps/overlaps between consecutive lines from different cues
    for i in range(1, len(caps)):
        if caps[i]['start'] < caps[i-1]['end'] and caps[i]['start'] > caps[i-1]['start']:
            caps[i-1]['end'] = caps[i]['start']
    return caps


if __name__ == '__main__':
    tl = json.load(open(os.path.join(ROOT, 'work', 'timeline.json'), encoding='utf-8'))
    caps = build_caps(tl)
    print(len(caps), 'caption lines')
    for c in caps[:6] + caps[-4:]:
        print(c)
