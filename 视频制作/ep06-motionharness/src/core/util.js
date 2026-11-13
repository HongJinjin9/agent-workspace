// 确定性工具函数（mh-motion）。所有画面必须只依赖项目时间，禁止 rAF / 墙钟。

export function clamp(v, lo = 0, hi = 1) {
  return v < lo ? lo : v > hi ? hi : v;
}

export function lerp(a, b, p) {
  return a + (b - a) * p;
}

export function easeInOutCubic(p) {
  const x = clamp(p);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}

export function easeOutCubic(p) {
  const x = clamp(p);
  return 1 - Math.pow(1 - x, 3);
}

export function easeOutQuint(p) {
  const x = clamp(p);
  return 1 - Math.pow(1 - x, 5);
}

export function smoothstep(a, b, x) {
  const p = clamp((x - a) / (b - a || 1e-9));
  return p * p * (3 - 2 * p);
}

/** 确定性伪随机：同一 seed 永远得到同一序列。 */
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hashStr(text) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

/** 打字机：随时间逐字显示（确定性）。 */
export function typewriter(text, t, cps = 22, start = 0) {
  const chars = Array.from(String(text ?? ''));
  if (t <= start) return '';
  const n = Math.floor((t - start) * cps);
  return n >= chars.length ? chars.join('') : chars.slice(0, n).join('');
}

/** 数字滚动：0..value，dur 秒内缓出（整数，确定性）。 */
export function countUp(value, t, dur, from = 0) {
  const p = dur > 0 ? easeOutCubic(t / dur) : 1;
  return Math.round(lerp(from, value, p));
}

export function fmtInt(n) {
  const v = Math.round(Number(n) || 0);
  return v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/** 帧序号：同一 t 永远同一帧号（用于颗粒等帧级确定性动画）。 */
export function frameAt(t, fps = 24) {
  return Math.max(0, Math.floor(t * fps + 1e-6));
}

/** 0..1 的缓出 reveal，start 前为 0，start+dur 后为 1。 */
export function reveal(t, start = 0, dur = 0.3) {
  return dur > 0 ? easeOutCubic((t - start) / dur) : t >= start ? 1 : 0;
}

/** 两位数补零。 */
export function pad2(n) {
  return String(Math.floor(n)).padStart(2, '0');
}

/** 全局时间 -> HH:MM:SS:FF */
export function timecode(t, fps = 24) {
  const total = Math.max(0, t);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = Math.floor(total % 60);
  const f = Math.floor((total - Math.floor(total)) * fps + 1e-6);
  return `${pad2(h)}:${pad2(m)}:${pad2(s)}:${pad2(f)}`;
}
