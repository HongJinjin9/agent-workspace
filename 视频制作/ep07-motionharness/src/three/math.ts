// 确定性数学工具（只依赖项目时间）
export function clamp(v: number, lo = 0, hi = 1) { return v < lo ? lo : v > hi ? hi : v; }
export function lerp(a: number, b: number, p: number) { return a + (b - a) * p; }
export function easeInOutCubic(p: number) { const x = clamp(p); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; }
export function easeOutCubic(p: number) { const x = clamp(p); return 1 - Math.pow(1 - x, 3); }
export function easeOutQuint(p: number) { const x = clamp(p); return 1 - Math.pow(1 - x, 5); }
export function smoothstep(a: number, b: number, x: number) { const p = clamp((x - a) / (b - a || 1e-9)); return p * p * (3 - 2 * p); }
export function mulberry32(seed: number) { let a = seed >>> 0; return function () { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
export function hashStr(s: string) { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; } return h >>> 0; }
export function fmtInt(n: number) { return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
export function typewriter(text: string, t: number, cps = 22, start = 0) { const chars = Array.from(String(text ?? '')); if (t <= start) return ''; const n = Math.floor((t - start) * cps); return n >= chars.length ? chars.join('') : chars.slice(0, n).join(''); }
export function countUp(value: number, t: number, dur: number, from = 0) { const p = dur > 0 ? easeOutCubic(t / dur) : 1; return Math.round(lerp(from, value, p)); }
export function progress(t: number, start: number, end: number) { return clamp((t - start) / Math.max(1e-6, end - start)); }

import type { Shot } from '../data/types';
export function findShot(shots: Shot[], t: number): Shot {
  let lo = 0, hi = shots.length - 1, found = 0;
  while (lo <= hi) { const mid = (lo + hi) >> 1; if (shots[mid].start <= t + 1e-9) { found = mid; lo = mid + 1; } else hi = mid - 1; }
  return shots[found];
}
