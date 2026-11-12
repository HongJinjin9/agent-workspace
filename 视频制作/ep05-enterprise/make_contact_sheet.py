#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 delivery/stills 合成联系表（交付评论用）。"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
STILLS = os.path.join(ROOT, "delivery", "stills")
OUT = os.path.join(ROOT, "delivery", "contact-sheet.jpg")
COLS = 4
TW, TH = 432, 243
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def main():
    files = sorted(f for f in os.listdir(STILLS) if f.endswith(".jpg"))
    rows = (len(files) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * TW, rows * (TH + 26)), (8, 8, 10))
    d = ImageDraw.Draw(sheet)
    fnt = ImageFont.truetype(FONT, 14)
    for i, f in enumerate(files):
        im = Image.open(os.path.join(STILLS, f)).convert("RGB").resize((TW, TH))
        x, y = (i % COLS) * TW, (i // COLS) * (TH + 26)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + TH + 4), f[:-4], font=fnt, fill=(190, 196, 204))
    sheet.save(OUT, quality=86)
    print(OUT, sheet.size)


if __name__ == "__main__":
    main()
