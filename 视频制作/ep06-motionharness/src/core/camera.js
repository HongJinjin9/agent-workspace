// 镜头运动：把 camera{from,to} 按镜头进度 p 缓动为 CSS transform。
// from/to = {s:缩放, x:像素平移, y:像素平移}（1920x1080 逻辑像素）。
import { clamp, easeInOutCubic } from './util.js';

export function cameraAt(cam, p) {
  const e = easeInOutCubic(clamp(p));
  const from = cam?.from ?? { s: 1, x: 0, y: 0 };
  const to = cam?.to ?? from;
  return {
    s: (from.s ?? 1) + ((to.s ?? from.s ?? 1) - (from.s ?? 1)) * e,
    x: (from.x ?? 0) + ((to.x ?? 0) - (from.x ?? 0)) * e,
    y: (from.y ?? 0) + ((to.y ?? 0) - (from.y ?? 0)) * e,
  };
}

export function cameraTransform(cam, p) {
  if (!cam) return '';
  const c = cameraAt(cam, p);
  // 轻微量化，避免同一目标在相邻帧出现无意义的浮点抖动。
  const s = Math.round(c.s * 1e4) / 1e4;
  const x = Math.round(c.x * 1e2) / 1e2;
  const y = Math.round(c.y * 1e2) / 1e2;
  return `translate3d(${x}px, ${y}px, 0) scale(${s})`;
}
