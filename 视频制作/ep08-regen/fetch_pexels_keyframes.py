#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为 H3 交接包补「无实拍素材」镜的 Pexels 首帧（引擎侧临时素材，不入库源片）。

只下载 Pexels Photos 的 landscape 大图（最快、够 864×480 / 1280×736 首帧），
记录 photo id / 作者 / 页面 URL / license 到 work/pexels-keyframes.json。
下载失败或网络不可用不阻断：对应镜保持 first_frame=null → H3 走 T2V。
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "assets", "pexels", "keyframes")
MAN = os.path.join(ROOT, "work", "pexels-keyframes.json")
KEYFILE = "/app/vedio/china-aigc/keys.env"

# 需要补的镜 → Pexels 搜索词（英文）
WANT = {
    "S01": "electric car dashboard interior screen",
    "S07": "car wheel closeup low angle",
    "S10": "brake disc closeup car",
    "S20": "electric car high voltage cables battery",
    "S25": "car pedal footwell interior",
    "S30": "brake disc red hot glowing",
    "S44": "frost on car window winter morning",
    "S49": "car tire rain water spray",
    "S50": "car rain wet road driving night",
    "S53": "car accelerator brake pedals",
    "S55": "cup holder car interior",
    "S58": "brake caliper closeup",
    "S59": "rusty brake disc",
    "H24": "electric car charging port plug",
}


def load_key():
    try:
        txt = open(KEYFILE, encoding="utf-8", errors="ignore").read()
    except OSError:
        return None
    m = re.search(r"PEXELS_API_KEY\s*=\s*['\"]?([A-Za-z0-9]+)", txt)
    return m.group(1) if m else None


def search(key, query, n=3):
    url = ("https://api.pexels.com/v1/search?query=%s&orientation=landscape&per_page=%d"
           % (urllib.parse.quote(query), n))
    req = urllib.request.Request(url, headers={"Authorization": key,
                                               "Accept": "application/json",
                                               "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    import urllib.parse
    key = os.environ.get("PEXELS_API_KEY") or load_key()
    if not key:
        print("[pexels] 无 API key，跳过（对应镜保持 T2V）")
        return 0
    os.makedirs(OUT, exist_ok=True)
    man = {}
    if os.path.isfile(MAN):
        try:
            man = json.load(open(MAN, encoding="utf-8"))
        except Exception:
            man = {}
    ok = 0
    for sid, query in WANT.items():
        try:
            res = search(key, query)
            photos = res.get("photos") or []
            if not photos:
                print("[pexels]", sid, "无结果", query)
                continue
            # 选第一张横图（尽量大）：src.original / large2x
            ph = photos[0]
            src = ph.get("src", {})
            url = src.get("large2x") or src.get("original") or src.get("large")
            if not url:
                continue
            dst = os.path.join(OUT, sid + ".jpg")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            if len(data) < 20000:
                print("[pexels]", sid, "图片过小，跳过")
                continue
            open(dst, "wb").write(data)
            man[sid] = {"query": query, "photo_id": ph.get("id"),
                        "photographer": ph.get("photographer"),
                        "page": ph.get("url"), "license": "Pexels License",
                        "src": dst, "w": ph.get("width"), "h": ph.get("height")}
            ok += 1
            print("[pexels]", sid, "OK", ph.get("id"), ph.get("photographer"))
        except Exception as e:
            print("[pexels]", sid, "FAIL", repr(e)[:160])
    json.dump(man, open(MAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[pexels] done, %d/%d" % (ok, len(WANT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
