// 相机路径：镜头数据 -> 由时间驱动的确定性机位（位置/注视点/焦距）
import { CAM_PRESETS } from './pose';
import type { Shot } from '../data/types';
import { clamp, easeInOutCubic, lerp } from './math';

export interface Pose { pos: [number, number, number]; look: [number, number, number]; fov: number; }

const v = {
  sub: (a: number[], b: number[]) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]] as [number, number, number],
  add: (a: number[], b: number[], s = 1) => [a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s] as [number, number, number],
  norm: (a: number[]) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l] as [number, number, number]; },
  cross: (a: number[], b: number[]) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]] as [number, number, number],
};

/** 镜头相机：起始/结束机位由预设 + 运动类型决定；镜头内 easeInOutCubic 插值。 */
export function poseForShot(shot: Shot, localT: number, indexSeed = 0): Pose {
  const base = (CAM_PRESETS[(shot.cam ?? 'sheet') as keyof typeof CAM_PRESETS] ?? CAM_PRESETS.sheet) as unknown as Pose;
  const dir = v.norm(v.sub(base.look, base.pos));           // 视线方向
  const side = v.norm(v.cross(dir, [0, 1, 0]));              // 水平侧向
  const p = clamp(shot.dur > 0 ? localT / shot.dur : 0);
  const e = easeInOutCubic(p);
  let fromPos: [number, number, number] = base.pos;
  let toPos: [number, number, number] = base.pos;
  let fromLook: [number, number, number] = base.look;
  let toLook: [number, number, number] = base.look;
  switch (shot.motion) {
    case 'push':
      toPos = v.add(base.pos, dir, 0.22);
      fromPos = v.add(base.pos, dir, -0.06);
      break;
    case 'pull':
      fromPos = v.add(base.pos, dir, 0.14);
      toPos = v.add(base.pos, dir, -0.45);
      break;
    case 'lateral': {
      const s = (shot.n % 2 === 0 ? 1 : -1) * 0.34;
      fromPos = v.add(base.pos, side, -s);
      toPos = v.add(base.pos, side, s);
      break;
    }
    case 'dolly': {
      fromPos = v.add(base.pos, dir, -0.10);
      toPos = v.add(base.pos, dir, 0.30);
      fromLook = base.look;
      toLook = base.look;
      break;
    }
    case 'slow': {
      const drift = Math.sin((localT + indexSeed) * 0.7) * 0.02;
      fromPos = v.add(base.pos, side, drift);
      toPos = v.add(base.pos, side, -drift);
      toLook = v.add(base.look, side, drift * 1.6);
      break;
    }
    case 'pan': {
      fromPos = v.add(base.pos, side, -0.26);
      toPos = v.add(base.pos, side, 0.26);
      break;
    }
    case 'rise':
      fromPos = base.pos;
      toPos = [base.pos[0], base.pos[1] + 0.55, base.pos[2]];
      toLook = [base.look[0], base.look[1] + 0.35, base.look[2]];
      break;
    case 'still':
    default: {
      const breathe = Math.sin((localT + indexSeed) * 0.9) * 0.012;
      fromPos = v.add(base.pos, side, breathe);
      toPos = v.add(base.pos, side, -breathe);
      break;
    }
  }
  const pos = v.add(fromPos, v.sub(toPos, fromPos), e);
  const look = v.add(fromLook, v.sub(toLook, fromLook), e);
  const fov = lerp(base.fov, base.fov * 0.985, e);
  return { pos, look, fov };
}
