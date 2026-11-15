// CanvasTexture 文字/图版工具：中文用系统 Noto 字体绘制到 canvas，再贴到 3D 平面。
// 全部确定性、带缓存（同一 key 只生成一次）。
import * as THREE from 'three';
import { THEME } from '../data/theme';

const { paper, ink, inkSoft, amber, red, redDeep, metal, metalLight } = THEME.color;
const F = THEME.font;

type Align = 'left' | 'center' | 'right';
interface TextOpts {
  w?: number; h?: number; fontSize?: number; font?: string; color?: string;
  align?: Align; lineHeight?: number; tracking?: number; weight?: number;
  pad?: number; bg?: string | null; alpha?: number; maxWidth?: number;
}

const cache = new Map<string, THREE.CanvasTexture>();

function makeCanvas(w: number, h: number) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return c;
}

function drawLines(ctx: CanvasRenderingContext2D, lines: string[], o: Required<Pick<TextOpts, 'w' | 'h' | 'fontSize' | 'font' | 'color' | 'align' | 'lineHeight' | 'tracking' | 'weight' | 'pad' | 'alpha'>>) {
  ctx.clearRect(0, 0, o.w, o.h);
  ctx.textBaseline = 'top';
  ctx.font = `${o.weight} ${o.fontSize}px ${o.font}`;
  ctx.fillStyle = o.color;
  ctx.globalAlpha = o.alpha;
  const totalH = lines.length * o.fontSize * o.lineHeight;
  let y = (o.h - totalH) / 2 + o.fontSize * 0.16;
  for (const line of lines) {
    const chars = Array.from(line);
    const width = chars.reduce((sum, ch) => sum + ctx.measureText(ch).width, 0) + Math.max(0, chars.length - 1) * o.tracking;
    let x = o.align === 'center' ? (o.w - width) / 2 : o.align === 'right' ? o.w - o.pad - width : o.pad;
    ctx.textAlign = 'left';
    for (const ch of chars) { ctx.fillText(ch, x, y); x += ctx.measureText(ch).width + o.tracking; }
    y += o.fontSize * o.lineHeight;
  }
  ctx.globalAlpha = 1;
}

/** 多行文字贴图（默认纸色字，透明底）。 */
export function textTexture(lines: string | string[], opts: TextOpts = {}): THREE.CanvasTexture {
  const arr = Array.isArray(lines) ? lines : [lines];
  const key = `t|${arr.join('\u0001')}|${JSON.stringify(opts)}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const o = {
    w: opts.w ?? 512, h: opts.h ?? 256, fontSize: opts.fontSize ?? 64,
    font: opts.font ?? F.serif, color: opts.color ?? paper, align: opts.align ?? 'center',
    lineHeight: opts.lineHeight ?? 1.25, tracking: opts.tracking ?? 0,
    weight: opts.weight ?? 500, pad: opts.pad ?? 24, alpha: opts.alpha ?? 1,
  };
  const canvas = makeCanvas(o.w, o.h);
  const ctx = canvas.getContext('2d')!;
  if (opts.bg) { ctx.fillStyle = opts.bg; ctx.fillRect(0, 0, o.w, o.h); }
  drawLines(ctx, arr, o);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  cache.set(key, tex);
  return tex;
}

/** 绘制整张评估单（复杂版面），返回 canvas 便于做纸面/翻页。 */
export function sheetCanvas(): HTMLCanvasElement {
  const W = 768, H = 1080;
  const c = makeCanvas(W, H);
  const g = c.getContext('2d')!;
  // 纸底 + 纤维
  g.fillStyle = paper; g.fillRect(0, 0, W, H);
  g.fillStyle = 'rgba(27,26,23,0.035)';
  for (let i = 0; i < H; i += 4) g.fillRect(0, i, W, 1);
  // 页眉
  g.fillStyle = ink; g.font = `600 30px ${F.serif}`; g.textBaseline = 'top';
  g.fillText('残值评估单', 60, 64);
  g.fillStyle = inkSoft; g.font = `500 20px ${F.mono}`;
  g.fillText('APPRAISAL / 2026.11.10', 60, 108);
  g.strokeStyle = 'rgba(27,26,23,0.35)'; g.lineWidth = 2;
  g.beginPath(); g.moveTo(60, 152); g.lineTo(W - 60, 152); g.stroke();
  // 字段行
  const rows: [string, string][] = [
    ['车型', '纯电 / 中大型 SUV'], ['落地价', '20.0 万'], ['车龄', '36 个月'],
    ['里程', '48,000 km'], ['三年残值', '9.0 万'], ['年均折旧', '3.7 万'],
  ];
  g.font = `500 24px ${F.sans}`;
  rows.forEach(([k, val], i) => {
    const y = 200 + i * 64;
    g.fillStyle = inkSoft; g.fillText(k, 60, y);
    g.fillStyle = ink; g.font = `600 26px ${F.sans}`; g.fillText(val, 250, y);
    g.font = `500 24px ${F.sans}`;
    g.strokeStyle = 'rgba(27,26,23,0.12)'; g.lineWidth = 1;
    g.beginPath(); g.moveTo(60, y + 40); g.lineTo(W - 60, y + 40); g.stroke();
  });
  // 重点：20 万划掉 -> 9 万
  g.fillStyle = inkSoft; g.font = `500 22px ${F.sans}`; g.fillText('落地价', 60, 620);
  g.font = `700 86px ${F.mono}`; g.fillStyle = ink; g.fillText('20', 60, 650);
  g.font = `500 34px ${F.sans}`; g.fillText('万', 168, 700);
  g.strokeStyle = red; g.lineWidth = 6;
  g.beginPath(); g.moveTo(52, 706); g.lineTo(230, 690); g.stroke();
  g.fillStyle = red; g.font = `700 76px ${F.serif}`; g.fillText('9', 320, 652);
  g.font = `500 30px ${F.sans}`; g.fillText('万', 400, 700);
  g.fillStyle = inkSoft; g.font = `500 22px ${F.sans}`; g.fillText('三年残值', 320, 620);
  // 红圈：谁
  g.strokeStyle = red; g.lineWidth = 4;
  g.beginPath(); g.ellipse(600, 840, 92, 70, -0.1, 0, Math.PI * 2); g.stroke();
  g.fillStyle = red; g.font = `700 54px ${F.serif}`; g.fillText('谁', 566, 812);
  // 印章：评估
  g.save(); g.translate(160, 900); g.rotate(-0.12);
  g.strokeStyle = redDeep; g.lineWidth = 6; g.strokeRect(-80, -58, 160, 116);
  g.fillStyle = red; g.font = `700 52px ${F.serif}`; g.textAlign = 'center'; g.fillText('评估', 0, -26);
  g.font = `500 18px ${F.mono}`; g.fillText('EP07 · 001', 0, 34);
  g.restore();
  // 页脚
  g.fillStyle = inkSoft; g.font = `500 18px ${F.mono}`;
  g.fillText('数据：中国汽车流通协会 2026-10 报告', 60, 1010);
  return c;
}

export function sheetTexture(): THREE.CanvasTexture {
  const hit = cache.get('sheet');
  if (hit) return hit;
  const tex = new THREE.CanvasTexture(sheetCanvas());
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  cache.set('sheet', tex);
  return tex;
}

/** 价签贴图：品牌/年份 + 残值百分比。 */
export function tagTexture(label: string, value: string, tone: 'paper' | 'amber' | 'red' = 'paper', sub?: string): THREE.CanvasTexture {
  const key = `tag|${label}|${value}|${tone}|${sub ?? ''}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const W = 256, H = 384;
  const c = makeCanvas(W, H);
  const g = c.getContext('2d')!;
  const bg = tone === 'amber' ? '#e7c887' : tone === 'red' ? '#e2c9c3' : '#e9e4d8';
  g.fillStyle = bg; g.fillRect(0, 0, W, H);
  g.fillStyle = 'rgba(27,26,23,0.05)'; for (let i = 0; i < H; i += 3) g.fillRect(0, i, W, 1);
  g.fillStyle = 'rgba(27,26,23,0.18)'; g.fillRect(0, 0, W, 6); g.fillRect(0, H - 6, W, 6);
  g.fillStyle = tone === 'red' ? redDeep : ink; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.font = `600 38px ${F.sans}`; g.fillText(label, W / 2, 84);
  g.font = `500 20px ${F.mono}`; g.fillStyle = inkSoft; g.fillText(sub ?? '三年保值率', W / 2, 138);
  g.fillStyle = tone === 'red' ? redDeep : tone === 'amber' ? '#8a5a12' : ink;
  g.font = `700 96px ${F.mono}`; g.fillText(value, W / 2, 236);
  g.strokeStyle = 'rgba(27,26,23,0.3)'; g.lineWidth = 2;
  g.beginPath(); g.arc(W / 2, 22, 8, 0, Math.PI * 2); g.stroke();
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  cache.set(key, tex);
  return tex;
}

/** 榜单面板：标题 + 多行条目，可高亮某行。 */
export function panelTexture(title: string, rows: string[], highlight = -1): THREE.CanvasTexture {
  const key = `panel|${title}|${rows.join('|')}|${highlight}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const W = 1024, H = 640;
  const c = makeCanvas(W, H);
  const g = c.getContext('2d')!;
  g.fillStyle = '#10151b'; g.fillRect(0, 0, W, H);
  g.strokeStyle = 'rgba(233,228,216,0.35)'; g.lineWidth = 2; g.strokeRect(10, 10, W - 20, H - 20);
  g.fillStyle = paper; g.font = `600 46px ${F.serif}`; g.textAlign = 'left'; g.textBaseline = 'top';
  g.fillText(title, 48, 44);
  g.strokeStyle = 'rgba(217,164,65,0.8)'; g.lineWidth = 3;
  g.beginPath(); g.moveTo(48, 112); g.lineTo(W - 48, 112); g.stroke();
  g.font = `500 34px ${F.sans}`;
  rows.forEach((row, i) => {
    const y = 156 + i * 54;
    if (i === highlight) { g.fillStyle = 'rgba(217,164,65,0.18)'; g.fillRect(40, y - 8, W - 80, 50); }
    g.fillStyle = i === highlight ? amber : paper;
    g.fillText(row, 64, y);
  });
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  cache.set(key, tex);
  return tex;
}

/** 衰减条/数字牌等通用小图版 */
export function plateTexture(text: string, opts: TextOpts = {}): THREE.CanvasTexture {
  const key = `plate|${text}|${JSON.stringify(opts)}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const W = opts.w ?? 512, H = opts.h ?? 256;
  const c = makeCanvas(W, H);
  const g = c.getContext('2d')!;
  g.clearRect(0, 0, W, H);
  g.fillStyle = opts.color ?? paper; g.textAlign = opts.align ?? 'center'; g.textBaseline = 'middle';
  g.font = `${opts.weight ?? 600} ${opts.fontSize ?? 96}px ${opts.font ?? F.mono}`;
  g.fillText(text, opts.align === 'left' ? 16 : opts.align === 'right' ? W - 16 : W / 2, H / 2);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  cache.set(key, tex);
  return tex;
}

/** 黄昏车场背景渐变（配 CanvasTexture，避免 3D 天空盒开销） */
export function skyTexture(): THREE.CanvasTexture {
  const hit = cache.get('sky');
  if (hit) return hit;
  const W = 1024, H = 512;
  const c = makeCanvas(W, H);
  const g = c.getContext('2d')!;
  const grad = g.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, '#0d1420');
  grad.addColorStop(0.42, '#2b3240');
  grad.addColorStop(0.68, '#6d5a4a');
  grad.addColorStop(0.82, '#c08a52');
  grad.addColorStop(0.92, '#e0a663');
  grad.addColorStop(1, '#8a5f3c');
  g.fillStyle = grad; g.fillRect(0, 0, W, H);
  // 低角度太阳光晕 + 云层条
  const sun = g.createRadialGradient(W * 0.62, H * 0.86, 10, W * 0.62, H * 0.86, 260);
  sun.addColorStop(0, 'rgba(255,225,170,0.9)'); sun.addColorStop(0.4, 'rgba(240,180,105,0.35)'); sun.addColorStop(1, 'rgba(240,180,105,0)');
  g.fillStyle = sun; g.fillRect(0, 0, W, H);
  g.fillStyle = 'rgba(20,24,30,0.35)';
  for (let i = 0; i < 6; i++) {
    const y = 120 + i * 26 + (i % 2) * 10;
    g.fillRect(0, y, W, 4 + (i % 3));
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  cache.set('sky', tex);
  return tex;
}
