// 提供给图形场景 / 叠加层的公共 helpers（mh-graphics 的 ctx.helpers）。
// 纯函数、确定性：同一 t 永远同一画面。
import {
  clamp, lerp, easeInOutCubic, easeOutCubic, easeOutQuint, smoothstep,
  mulberry32, hashStr, typewriter, countUp, fmtInt, frameAt, reveal,
} from './util.js';

export const helpers = {
  clamp,
  lerp,
  easeInOutCubic,
  easeOutCubic,
  easeOutQuint,
  smoothstep,
  mulberry32,
  hashStr,
  typewriter,
  countUp,
  fmtInt,
  frameAt,
  reveal,
};
