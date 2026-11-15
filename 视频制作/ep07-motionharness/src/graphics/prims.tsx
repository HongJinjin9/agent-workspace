// 第 07 期图形层公共图元 —— 评估系统（appraisal system）2D 图元。
// 纯函数 + 普通 React；所有动画是 local seconds 的确定性函数，无 state/rAF/timer。
import type { CSSProperties, ReactNode } from 'react';
import { useTime } from '@motionharness/sdk';
import { THEME } from '../data/theme';

export const T = THEME;
export const C = THEME.color;
export const F = THEME.font;
export const LB = THEME.letterbox;
export const W = 1920;
export const H = 1080;
export const TOP = LB;
export const BOT = H - LB;

// ---------------------------------------------------------------- math
export const clamp = (v: number, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
export const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
export const easeOutCubic = (p: number) => 1 - Math.pow(1 - clamp(p), 3);
export const easeOutQuint = (p: number) => 1 - Math.pow(1 - clamp(p), 5);
export const easeInOutCubic = (p: number) => {
  const x = clamp(p);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
};
export const easeInCubic = (p: number) => Math.pow(clamp(p), 3);
export const smoothstep = (a: number, b: number, x: number) => {
  const p = clamp((x - a) / Math.max(1e-6, b - a));
  return p * p * (3 - 2 * p);
};
export const prog = (t: number, a: number, b: number) => clamp((t - a) / Math.max(1e-6, b - a));
/** fast entry ramp: 0..1 over `dur` after `delay` (ep07 pacing: 0.22–0.36s) */
export const inRamp = (local: number, delay = 0, dur = 0.3) => easeOutCubic(prog(local, delay, delay + dur));
export const win = (t: number, a: number, b: number, fin = 0.2, fout = 0.2) => {
  if (t < a || t > b) return 0;
  return Math.min(fin > 0 ? clamp((t - a) / fin) : 1, fout > 0 ? clamp((b - t) / fout) : 1);
};
export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------- numbers
export const fmtInt = (n: number) =>
  String(Math.round(Number(n) || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
export const pct = (v: number | string, digits = 1) =>
  typeof v === 'string' ? v : `${Number(v).toFixed(digits)}%`;
export const yuan = (v: number | string) => `${v} 万`;
export function countUp(value: number, local: number, delay = 0, dur = 0.42, from = 0) {
  return Math.round(lerp(from, value, easeOutQuint(prog(local, delay, delay + dur))));
}
/** typewriter visible char count */
export function typed(text: string, local: number, delay = 0, cps = 26) {
  return clamp(Math.floor(Math.max(0, local - delay) * cps + 1e-6), 0, text.length);
}
/** deterministic fast number shimmer 0..1 for slam accent */
export function slamScale(local: number, delay = 0, settle = 0.22) {
  return lerp(1.16, 1, easeOutQuint(prog(local, delay, delay + settle)));
}

// ---------------------------------------------------------------- time
/** local seconds inside a block; `time` prop (global secs) wins over useTime */
export function useLocal(time?: number, from = 0): number {
  const globalTime = useTime();
  return (typeof time === 'number' ? time : globalTime) - from;
}

// ---------------------------------------------------------------- styles / nodes
const baseText: CSSProperties = { position: 'absolute', whiteSpace: 'nowrap', margin: 0, padding: 0 };

export type Align = 'left' | 'center' | 'right';

export interface TxtProps {
  text: string;
  x: number;
  y: number;
  size: number;
  font?: 'serif' | 'sans' | 'mono';
  color?: string;
  alpha?: number;
  track?: number;
  weight?: number;
  align?: Align;
  lineHeight?: number;
  maxWidth?: number;
  nowrap?: boolean;
  style?: CSSProperties;
}
/** absolutely positioned text node */
export function Txt(p: TxtProps) {
  const align = p.align ?? 'left';
  const transform =
    align === 'center' ? 'translateX(-50%)' : align === 'right' ? 'translateX(-100%)' : undefined;
  const fontFamily = p.font === 'serif' ? F.serif : p.font === 'mono' ? F.mono : F.sans;
  return (
    <div
      style={{
        ...baseText,
        left: p.x,
        top: p.y,
        fontFamily,
        fontSize: p.size,
        fontWeight: p.weight ?? 400,
        color: p.color ?? C.paper,
        opacity: p.alpha ?? 1,
        letterSpacing: p.track ?? 0,
        lineHeight: p.lineHeight ?? 1.25,
        whiteSpace: p.nowrap === false ? 'normal' : 'nowrap',
        width: p.maxWidth,
        transform,
        ...p.style,
      }}
    >
      {p.text}
    </div>
  );
}

export interface NodeProps {
  children?: ReactNode;
  x: number;
  y: number;
  w?: number;
  h?: number;
  rot?: number;
  alpha?: number;
  style?: CSSProperties;
}

/** generic absolutely positioned box */
export function Box({ children, x, y, w, h, rot = 0, alpha = 1, style }: NodeProps) {
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        width: w,
        height: h,
        opacity: alpha,
        transform: rot ? `rotate(${rot}deg)` : undefined,
        transformOrigin: '50% 50%',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** full-frame layer: 1920x1080, transparent, pointer-events none, clipped */
export function GFXLayer({ children }: { children?: ReactNode }) {
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        top: 0,
        width: W,
        height: H,
        overflow: 'hidden',
        pointerEvents: 'none',
      }}
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------- paper & texture
export interface PaperProps {
  x: number;
  y: number;
  w: number;
  h: number;
  rot?: number;
  shade?: boolean;
  opacity?: number;
  children?: ReactNode;
  style?: CSSProperties;
}
/** cream appraisal paper sheet with fibre, foxing, edge falloff */
export function Paper({ x, y, w, h, rot = 0, shade = true, opacity = 1, children, style }: PaperProps) {
  const rnd = mulberry32(Math.round(x * 7 + y * 13 + w));
  const spots: ReactNode[] = [];
  for (let i = 0; i < 18; i++) {
    const sx = rnd() * w;
    const sy = rnd() * h;
    const r = 2 + rnd() * 8;
    spots.push(
      <i
        key={i}
        style={{
          position: 'absolute',
          left: sx - r,
          top: sy - r * 0.8,
          width: r * 2,
          height: r * 1.6,
          borderRadius: '50%',
          background: `rgba(140,104,58,${(0.02 + rnd() * 0.045).toFixed(3)})`,
          filter: 'blur(1px)',
        }}
      />
    );
  }
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        width: w,
        height: h,
        opacity,
        transform: `rotate(${rot}deg)`,
        transformOrigin: '50% 50%',
        background: `radial-gradient(120% 90% at 30% 18%, #f3eee2 0%, ${C.paper} 46%, ${C.paperShade} 100%)`,
        boxShadow: '0 24px 60px rgba(0,0,0,.55), inset 0 0 90px rgba(70,54,32,.20), inset 0 0 2px rgba(50,40,25,.45)',
        overflow: 'hidden',
        ...style,
      }}
    >
      <div className="gfx-fibre" style={{ position: 'absolute', inset: 0, opacity: 0.75 }} />
      {spots}
      {shade ? (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'radial-gradient(130% 100% at 24% 6%, rgba(255,252,244,.45) 0%, rgba(255,252,244,.06) 32%, rgba(120,98,66,.10) 78%, rgba(70,54,32,.22) 100%)',
            mixBlendMode: 'multiply',
          }}
        />
      ) : null}
      {children}
    </div>
  );
}

/** thin editorial rule; progress 0..1 scales from origin */
export function Rule({
  x,
  y,
  w,
  h = 1,
  color = C.amber,
  alpha = 0.7,
  progress = 1,
  origin = 'left',
}: {
  x: number;
  y: number;
  w: number;
  h?: number;
  color?: string;
  alpha?: number;
  progress?: number;
  origin?: 'left' | 'right' | 'center';
}) {
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        width: w,
        height: h,
        background: color,
        opacity: alpha,
        transform: `scaleX(${clamp(progress)})`,
        transformOrigin: `${origin} 50%`,
      }}
    />
  );
}

/** four evidence corner ticks around a box */
export function CornerTicks({
  x,
  y,
  w,
  h,
  color = C.paper,
  alpha = 0.32,
  size = 18,
  thick = 2,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  color?: string;
  alpha?: number;
  size?: number;
  thick?: number;
}) {
  const corners: Array<[number, number, number, number]> = [
    [x, y, 1, 1],
    [x + w, y, -1, 1],
    [x, y + h, 1, -1],
    [x + w, y + h, -1, -1],
  ];
  return (
    <div style={{ position: 'absolute', inset: 0, opacity: alpha }}>
      {corners.map(([cx, cy, dx, dy], i) => (
        <span key={i}>
          <i
            style={{
              position: 'absolute',
              left: dx > 0 ? cx : cx - size,
              top: cy - thick / 2,
              width: size,
              height: thick,
              background: color,
            }}
          />
          <i
            style={{
              position: 'absolute',
              left: cx - thick / 2,
              top: dy > 0 ? cy : cy - size,
              width: thick,
              height: size,
              background: color,
            }}
          />
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- ink / red pen
/** hand-drawn red pen stroke from SVG path; progress 0..1 draws with dashoffset */
export function RedStroke({
  d,
  x = 0,
  y = 0,
  w = W,
  h = H,
  progress = 1,
  color = C.red,
  width = 5,
  alpha = 1,
  rough = true,
}: {
  d: string;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  progress?: number;
  color?: string;
  width?: number;
  alpha?: number;
  rough?: boolean;
}) {
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width={w}
      height={h}
      style={{ position: 'absolute', left: x, top: y, overflow: 'visible', opacity: alpha }}
    >
      <path
        d={d}
        fill="none"
        stroke={color}
        strokeWidth={width}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={1}
        strokeDasharray={1}
        strokeDashoffset={1 - clamp(progress)}
        style={{ filter: rough ? 'url(#gfx-rough)' : undefined }}
      />
      {rough ? (
        <defs>
          <filter id="gfx-rough">
            <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="1" seed="7" result="n" />
            <feDisplacementMap in="SourceGraphic" in2="n" scale="2.2" />
          </filter>
        </defs>
      ) : null}
    </svg>
  );
}

// ---------------------------------------------------------------- seal / stamp
export interface SealProps {
  x: number;
  y: number;
  size: number;
  text: string;
  sub?: string;
  rot?: number;
  color?: string;
  /** 0..1 slam progress (0 hidden, 1 settled) */
  hit?: number;
  /** 0..1 ink bleed */
  bleed?: number;
  blend?: boolean;
  z?: number;
}
/** red rubber seal: border + text + ink bloom + spatter flecks (deterministic) */
export function SealMark({ x, y, size, text, sub, rot = -6, color = C.red, hit = 1, bleed = 0, blend = true, z = 5 }: SealProps) {
  const rnd = mulberry32(Math.round(size * 17 + text.length * 31));
  const flecks: ReactNode[] = [];
  for (let i = 0; i < 12; i++) {
    const ang = rnd() * Math.PI * 2;
    const dd = size * (0.55 + rnd() * 0.4);
    const r = 1 + rnd() * 2.4;
    flecks.push(
      <i
        key={i}
        style={{
          position: 'absolute',
          left: Math.cos(ang) * dd - r,
          top: Math.sin(ang) * dd - r,
          width: r * 2,
          height: r * 2,
          borderRadius: '50%',
          background: color,
          opacity: 0.55 * bleed,
        }}
      />
    );
  }
  if (hit <= 0) return null;
  const scale = lerp(1.22, 1, easeOutQuint(hit));
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: 0, height: 0, zIndex: z }}>
      <div
        style={{
          position: 'absolute',
          left: -size * 1.5,
          top: -size * 1.5,
          width: size * 3,
          height: size * 3,
          borderRadius: '50%',
          background: `radial-gradient(circle, ${rgba(color, 0.3)} 0%, ${rgba(color, 0.13)} 38%, ${rgba(
            color,
            0.04
          )} 62%, transparent 74%)`,
          filter: 'blur(7px)',
          opacity: 0.85 * bleed,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: -size / 2,
          top: -size / 2,
          width: size,
          height: size,
          transform: `rotate(${lerp(rot + 4, rot, easeOutQuint(hit))}deg) scale(${scale})`,
          transformOrigin: '50% 50%',
          border: `${Math.max(4, size * 0.03)}px solid ${color}`,
          borderRadius: size * 0.03,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          color,
          opacity: 0.94 * clamp(hit * 2),
          mixBlendMode: blend ? 'multiply' : 'normal',
          boxSizing: 'border-box',
        }}
      >
        <i
          style={{
            position: 'absolute',
            left: size * 0.075,
            top: size * 0.075,
            right: size * 0.075,
            bottom: size * 0.075,
            border: `${Math.max(1.2, size * 0.008)}px solid ${color}`,
            borderRadius: 2,
            opacity: 0.7,
          }}
        />
        <div
          style={{
            fontFamily: F.serif,
            fontSize: size * 0.28,
            fontWeight: 700,
            letterSpacing: size * 0.03,
            lineHeight: 1,
            whiteSpace: 'nowrap',
          }}
        >
          {text}
        </div>
        {sub ? (
          <div
            style={{
              marginTop: size * 0.05,
              fontFamily: F.mono,
              fontSize: Math.max(12, size * 0.085),
              letterSpacing: 1,
              opacity: 0.85,
              whiteSpace: 'nowrap',
            }}
          >
            {sub}
          </div>
        ) : null}
        {flecks}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- misc
export function rgba(hex: string, a: number) {
  const h = String(hex).replace('#', '');
  const v = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  const r = parseInt(v.slice(0, 2), 16);
  const g = parseInt(v.slice(2, 4), 16);
  const b = parseInt(v.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}

/** deterministic grain speckles; use sparingly (12–24 per card) */
export function Speckles({
  x = 0,
  y = 0,
  w = W,
  h = H,
  seed = 7,
  count = 16,
  color = '233,228,216',
  maxAlpha = 0.1,
}: {
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  seed?: number;
  count?: number;
  color?: string;
  maxAlpha?: number;
}) {
  const rnd = mulberry32(seed);
  const dots: ReactNode[] = [];
  for (let i = 0; i < count; i++) {
    const r = 0.6 + rnd() * 1.8;
    dots.push(
      <i
        key={i}
        style={{
          position: 'absolute',
          left: x + rnd() * w,
          top: y + rnd() * h,
          width: r,
          height: r * (0.7 + rnd()),
          borderRadius: '50%',
          background: `rgba(${color},${(0.03 + rnd() * maxAlpha).toFixed(3)})`,
        }}
      />
    );
  }
  return <div style={{ position: 'absolute', inset: 0 }}>{dots}</div>;
}

/** small series kicker row: e.g. "VIBE 知识共赏 · 第 07 期" */
export function Kicker({ text, x, y, alpha = 0.7, track = 5, color = C.paper, align = 'left' }: { text: string; x: number; y: number; alpha?: number; track?: number; color?: string; align?: Align }) {
  return <Txt text={text} x={x} y={y} size={22} font="mono" color={color} alpha={alpha} track={track} align={align} />;
}

/** thin side label with rule, e.g. "EXHIBIT 04 / 评估单" */
export function MetaRow({ left, right, y = 196, alpha = 0.5 }: { left: string; right?: string; y?: number; alpha?: number }) {
  return (
    <>
      <Txt text={left} x={150} y={y} size={18} font="mono" color={C.paper} alpha={alpha} track={3} />
      {right ? (
        <Txt text={right} x={W - 150} y={y} size={18} font="mono" color={C.paper} alpha={alpha * 0.85} track={2} align="right" />
      ) : null}
    </>
  );
}
