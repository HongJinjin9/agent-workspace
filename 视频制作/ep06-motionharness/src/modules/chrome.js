// chrome 层：2.35:1 遮幅（132px 纯黑上下条）、暗角、确定性胶片颗粒、
// 镜头 caption/证据角标、幕标签（只给幕语境，不做剪辑编号）、片头品牌字样。
// 颗粒按“帧号”确定性生成（同一 t 永远同一张），与墙钟/rAF 无关。
import { clamp, mulberry32 } from '../core/util.js';

const SEG_LABEL = {
  COLD: '冷开场',
  ACT1: '第一幕 · 立判',
  ACT2: '第二幕 · 验证',
  ACT3: '第三幕 · 改判',
  ACT4: '第四幕 · 再判',
  CLOSE: '收束',
};

const GRAIN_TILES = 24; // 1s @24fps
const GRAIN_W = 320;
const GRAIN_H = 180;

function el(tag, className, parent) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (parent) parent.append(node);
  return node;
}

function makeGrainTile(seed) {
  const canvas = document.createElement('canvas');
  canvas.width = GRAIN_W;
  canvas.height = GRAIN_H;
  const ctx = canvas.getContext('2d');
  const image = ctx.createImageData(GRAIN_W, GRAIN_H);
  const rnd = mulberry32(seed);
  for (let i = 0; i < image.data.length; i += 4) {
    const v = (rnd() * 255) | 0;
    image.data[i] = v;
    image.data[i + 1] = v;
    image.data[i + 2] = v;
    image.data[i + 3] = rnd() < 0.45 ? 0 : 30;
  }
  ctx.putImageData(image, 0, 0);
  return canvas;
}

export function mountChrome({ el: layer, width, height, theme }) {
  layer.innerHTML = '';
  const bar = theme.letterbox ?? 132;
  const mono = theme.font.mono;
  const serif = theme.font.serif;

  // 内容区装饰（只作用在遮幅之间，保证上下条纯黑）
  const content = el('div', 'mh-chrome-content', layer);
  content.style.top = `${bar}px`;
  content.style.bottom = `${bar}px`;
  const vignette = el('div', 'mh-vignette', content);

  const grain = el('canvas', 'mh-grain', content);
  grain.width = GRAIN_W;
  grain.height = GRAIN_H;
  const grainCtx = grain.getContext('2d');
  const tiles = new Map();
  let lastGrainFrame = -1;

  // 遮幅
  el('div', 'mh-bar mh-bar-top', layer).style.height = `${bar}px`;
  el('div', 'mh-bar mh-bar-bottom', layer).style.height = `${bar}px`;

  // 字幕条上下的极柔内阴影，让 2.35 遮幅过渡不生硬
  el('div', 'mh-edge mh-edge-top', content);
  el('div', 'mh-edge mh-edge-bottom', content);

  // 顶部条：左品牌 / 右幕标签（只给幕语境，不显示镜号，避免“剪辑代理”感）
  const brand = el('div', 'mh-brand', layer);
  brand.textContent = 'VIBE 知识共赏 · 第 06 期';
  brand.style.fontFamily = mono;
  const act = el('div', 'mh-act', layer);
  act.style.fontFamily = mono;

  // 镜头 caption / 证据角标（左下，内容区内）
  const caption = el('div', 'mh-caption', content);
  for (const pos of ['tl', 'tr', 'bl', 'br']) el('span', `mh-cap-tick mh-cap-${pos}`, caption);
  el('span', 'mh-caption-line', caption);
  const captionText = el('span', 'mh-caption-text', caption);
  captionText.style.fontFamily = serif;
  let captionShown = false;

  const cache = { act: '', caption: '' };
  let lastCaptionAlpha = -1;

  function drawGrain(frame) {
    if (frame === lastGrainFrame) return;
    lastGrainFrame = frame;
    const index = ((frame % GRAIN_TILES) + GRAIN_TILES) % GRAIN_TILES;
    let tile = tiles.get(index);
    if (!tile) {
      tile = makeGrainTile(0x9e3779b9 ^ (index * 7919 + 13));
      tiles.set(index, tile);
    }
    grainCtx.clearRect(0, 0, GRAIN_W, GRAIN_H);
    grainCtx.drawImage(tile, 0, 0);
  }

  function update({ t, shot, idx, total, local, frame }) {
    drawGrain(frame);

    const actText = SEG_LABEL[shot.seg] ?? shot.seg ?? '';
    if (actText !== cache.act) {
      cache.act = actText;
      act.textContent = actText;
    }

    const text = shot.caption || '';
    if (text) {
      if (!captionShown) {
        captionShown = true;
        caption.style.display = 'flex';
      }
      if (text !== cache.caption) {
        cache.caption = text;
        captionText.textContent = text;
      }
      const alpha = clamp((local - 0.12) / 0.4);
      if (Math.abs(alpha - lastCaptionAlpha) > 0.002) {
        lastCaptionAlpha = alpha;
        caption.style.opacity = String(alpha);
        caption.style.transform = `translateY(${((1 - alpha) * 8).toFixed(2)}px)`;
      }
    } else if (captionShown) {
      captionShown = false;
      caption.style.display = 'none';
      lastCaptionAlpha = -1;
    }
  }

  function dispose() {
    tiles.clear();
    layer.innerHTML = '';
  }

  return { update, dispose };
}
