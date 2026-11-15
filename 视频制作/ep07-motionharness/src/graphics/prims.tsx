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

// ================================================================ v2 motion primitives
// 人类评审 v2：所有图形必须「会动」，且动作为叙事服务（数字滚动/画线/落牌/翻页/盖章）。

/** continuous camera push — makes even a "hold" frame feel alive (deterministic) */
export function Camera({
  local,
  dur,
  children,
  strength = 1,
  origin = '50% 54%',
}: {
  local: number;
  dur: number;
  children?: ReactNode;
  strength?: number;
  origin?: string;
}) {
  const p = clamp(local / Math.max(1e-6, dur));
  const s = 1 + 0.035 * strength * easeInOutCubic(p);
  const ty = -14 * strength * easeInOutCubic(p);
  const tx = 7 * strength * Math.sin(p * Math.PI * 0.9);
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        transform: `translate(${tx.toFixed(2)}px,${ty.toFixed(2)}px) scale(${s.toFixed(4)})`,
        transformOrigin: origin,
        willChange: 'transform',
      }}
    >
      {children}
    </div>
  );
}

/** thin amber scan line drifting through the frame (x / 1000s) */
export function ScanBeam({ local, y0 = 300, y1 = 820, speed = 0.12, alpha = 0.1 }: { local: number; y0?: number; y1?: number; speed?: number; alpha?: number }) {
  const p = ((local * speed) % 1 + 1) % 1;
  const y = y0 + (y1 - y0) * p;
  return (
    <div
      style={{
        position: 'absolute',
        left: 120,
        top: y,
        width: 1680,
        height: 1,
        background: `linear-gradient(90deg, transparent 0%, ${rgba(C.amber, 0.55)} 30%, ${rgba(C.amber, 0.55)} 70%, transparent 100%)`,
        opacity: alpha,
      }}
    />
  );
}

/** deterministic drifting dust motes */
export function Dust({ local, count = 14, seed = 31, alpha = 0.35 }: { local: number; count?: number; seed?: number; alpha?: number }) {
  const rnd = mulberry32(seed);
  const motes: ReactNode[] = [];
  for (let i = 0; i < count; i++) {
    const x = rnd() * W;
    const y0 = 160 + rnd() * 760;
    const sp = 3 + rnd() * 6;
    const ph = rnd() * Math.PI * 2;
    const r = 0.8 + rnd() * 1.8;
    motes.push(
      <i
        key={i}
        style={{
          position: 'absolute',
          left: x + Math.sin(local * (sp / 6) + ph) * 9,
          top: y0 + Math.cos(local * (sp / 8) + ph) * 7,
          width: r,
          height: r,
          borderRadius: '50%',
          background: rgba(C.paper, 0.5),
          opacity: (0.25 + 0.45 * (0.5 + 0.5 * Math.sin(local * sp + ph))) * alpha,
        }}
      />
    );
  }
  return <div style={{ position: 'absolute', inset: 0 }}>{motes}</div>;
}

/** rolling odometer digit column */
function OdoColumn({ o, size, color, weight = 700 }: { o: number; size: number; color: string; weight?: number }) {
  const rowH = size * 1.1;
  const rows: ReactNode[] = [];
  for (let i = 0; i < 20; i++) {
    rows.push(
      <div key={i} style={{ height: rowH, lineHeight: `${rowH}px`, fontSize: size, color, fontWeight: weight, fontFamily: F.mono, textAlign: 'center' }}>
        {i % 10}
      </div>
    );
  }
  return (
    <div style={{ position: 'relative', width: size * 0.655, height: rowH, overflow: 'hidden', flexShrink: 0 }}>
      <div style={{ position: 'absolute', left: 0, top: 0, width: '100%', transform: `translateY(${-o * rowH}px)` }}>{rows}</div>
    </div>
  );
}

/**
 * Odometer: rolling digits, count-up from 0 to value with continuous roll-through.
 * Renders absolutely at (x,y); align controls horizontal anchoring of the whole readout.
 */
export function Odometer({
  value,
  x,
  y,
  size = 240,
  color = C.amber,
  local,
  delay = 0,
  dur = 0.5,
  digitsAfter = 1,
  suffix = '%',
  align = 'left',
  glow = 0.3,
  weight = 700,
}: {
  value: number;
  x: number;
  y: number;
  size?: number;
  color?: string;
  local: number;
  delay?: number;
  dur?: number;
  digitsAfter?: number;
  suffix?: string;
  align?: Align;
  glow?: number;
  weight?: number;
}) {
  const p = easeOutQuint(prog(local, delay, delay + dur));
  const D = Math.pow(10, digitsAfter);
  const finalTicks = Math.round(value * D);
  const intDigits = String(Math.max(0, Math.floor(value))).length;
  // Each drum rolls 0 → its EXACT final digit and settles there, so a finished
  // counter always reads the true value (a real odometer's half-rolled tens wheel
  // would misread e.g. 29.1 as 39.1). Higher-order places roll over the full 0..9
  // only when their digit actually wraps during the count-up.
  const cols: ReactNode[] = [];
  const totalPlaces = intDigits + digitsAfter;
  for (let pos = totalPlaces - 1; pos >= 0; pos--) {
    const digit = Math.floor(finalTicks / Math.pow(10, pos)) % 10;
    const fullRoll = p * digit;
    cols.push(<OdoColumn key={`d${pos}`} o={clamp(fullRoll, 0, 9.999)} size={size} color={color} weight={weight} />);
    if (pos === digitsAfter) {
      cols.push(
        <div key="dot" style={{ height: size * 1.1, lineHeight: `${size * 1.1}px`, fontSize: size, color, fontWeight: weight, fontFamily: F.mono, padding: `0 ${size * 0.02}px` }}>
          .
        </div>
      );
    }
  }
  const totalW = intDigits * size * 0.655 + (digitsAfter > 0 ? size * 0.22 + digitsAfter * size * 0.655 : 0);
  const anchor = align === 'center' ? -totalW / 2 : align === 'right' ? -totalW : 0;
  return (
    <div style={{ position: 'absolute', left: x + anchor, top: y, display: 'flex', alignItems: 'flex-start' }}>
      {cols}
      {suffix ? (
        <div style={{ height: size * 1.1, lineHeight: `${size * 1.1}px`, fontSize: size * 0.6, color, fontWeight: weight, fontFamily: F.mono, marginLeft: size * 0.06, opacity: 0.9 }}>
          {suffix}
        </div>
      ) : null}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: '100%',
          height: '100%',
          boxShadow: glow > 0 ? `0 0 ${size * 0.28}px ${rgba(color, glow * 0.5)}` : undefined,
          pointerEvents: 'none',
        }}
      />
    </div>
  );
}

/** huge hand-set counter (odometer digits, no suffixes) — integer values */
export function OdometerInt({ value, x, y, size, color = C.paper, local, delay = 0, dur = 0.5, align = 'left', weight = 700 }: { value: number; x: number; y: number; size: number; color?: string; local: number; delay?: number; dur?: number; align?: Align; weight?: number }) {
  return <Odometer value={value} x={x} y={y} size={size} color={color} local={local} delay={delay} dur={dur} digitsAfter={0} suffix="" align={align} glow={0.18} weight={weight} />;
}

/** 3D flip panel: front → back (used for 20万 → 9万) */
export function FlipPanel({
  local,
  at = 0.6,
  dur = 0.34,
  front,
  back,
  x,
  y,
  w,
  h,
  perspective = 900,
}: {
  local: number;
  at?: number;
  dur?: number;
  front: ReactNode;
  back: ReactNode;
  x: number;
  y: number;
  w: number;
  h: number;
  perspective?: number;
}) {
  const p = clamp(prog(local, at, at + dur));
  const frontRot = -90 * easeInOutCubic(p);
  const backRot = 90 * (1 - easeInOutCubic(p));
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, height: h, perspective }}>
      <div style={{ position: 'absolute', inset: 0, transform: `rotateX(${frontRot}deg)`, transformOrigin: '50% 50%', backfaceVisibility: 'hidden', opacity: p < 0.5 ? 1 : 0 }}>
        {front}
      </div>
      <div style={{ position: 'absolute', inset: 0, transform: `rotateX(${backRot}deg)`, transformOrigin: '50% 50%', backfaceVisibility: 'hidden', opacity: p >= 0.5 ? 1 : 0 }}>
        {back}
      </div>
    </div>
  );
}

/** kinetic per-character text: staggered clip/translate reveal (CJK serif headlines) */
export function Kinetic({
  text,
  x,
  y,
  size,
  color = C.paper,
  local,
  delay = 0,
  step = 0.022,
  charDur = 0.34,
  track = 3,
  font = 'serif',
  weight = 600,
  align = 'left',
  rise = 16,
  clip = true,
}: {
  text: string;
  x: number;
  y: number;
  size: number;
  color?: string;
  local: number;
  delay?: number;
  step?: number;
  charDur?: number;
  track?: number;
  font?: 'serif' | 'sans' | 'mono';
  weight?: number;
  align?: Align;
  rise?: number;
  clip?: boolean;
}) {
  const chars = Array.from(text);
  const fontFamily = font === 'serif' ? F.serif : font === 'mono' ? F.mono : F.sans;
  const totalW = chars.length * (size + track);
  const anchor = align === 'center' ? -totalW / 2 : align === 'right' ? -totalW : 0;
  return (
    <div style={{ position: 'absolute', left: x + anchor, top: y, whiteSpace: 'nowrap', fontFamily, fontSize: size, fontWeight: weight, letterSpacing: track, lineHeight: 1.2 }}>
      {chars.map((ch, i) => {
        const p = easeOutCubic(prog(local, delay + i * step, delay + i * step + charDur));
        return (
          <span
            key={i}
            style={{
              display: 'inline-block',
              color,
              opacity: p,
              transform: `translateY(${lerp(rise, 0, p)}px)`,
              clipPath: clip ? `inset(${(1 - p) * 100}% 0% 0% 0%)` : undefined,
              marginRight: ch === ' ' ? size * 0.15 : undefined,
            }}
          >
            {ch}
          </span>
        );
      })}
    </div>
  );
}

/** animated arc gauge (0–100) with moving needle — continuous motion after entry */
export function GaugeArc({
  value,
  x,
  y,
  r = 300,
  color = C.amber,
  local,
  delay = 0.1,
  dur = 0.7,
  width = 10,
  alpha = 0.85,
  breathe = true,
}: {
  value: number;
  x: number;
  y: number;
  r?: number;
  color?: string;
  local: number;
  delay?: number;
  dur?: number;
  width?: number;
  alpha?: number;
  breathe?: boolean;
}) {
  const p = easeOutQuint(prog(local, delay, delay + dur));
  const v = clamp(value / 100, 0, 1) * p;
  const C0 = 2 * Math.PI * r;
  const live = breathe ? v + 0.004 * Math.sin(local * 2.1) : v;
  return (
    <svg width={2 * r + 80} height={2 * r + 80} viewBox={`0 0 ${2 * r + 80} ${2 * r + 80}`} style={{ position: 'absolute', left: x - r - 40, top: y - r - 40, opacity: alpha }}>
      <circle cx={r + 40} cy={r + 40} r={r} fill="none" stroke={rgba(C.paper, 0.12)} strokeWidth={width} />
      <circle
        cx={r + 40}
        cy={r + 40}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={width}
        strokeLinecap="round"
        strokeDasharray={C0}
        strokeDashoffset={C0 * (1 - live)}
        transform={`rotate(-90 ${r + 40} ${r + 40})`}
        style={{ filter: `drop-shadow(0 0 12px ${rgba(color, 0.35)})` }}
      />
      {Array.from({ length: 21 }).map((_, i) => {
        const a = (i / 20) * Math.PI * 2 - Math.PI / 2;
        const big = i % 5 === 0;
        const r1 = r + (big ? 18 : 12);
        const r2 = r + 26;
        return (
          <line
            key={i}
            x1={r + 40 + Math.cos(a) * r1}
            y1={r + 40 + Math.sin(a) * r1}
            x2={r + 40 + Math.cos(a) * r2}
            y2={r + 40 + Math.sin(a) * r2}
            stroke={rgba(C.paper, big ? 0.42 : 0.2)}
            strokeWidth={big ? 2 : 1.5}
          />
        );
      })}
      <circle cx={r + 40 + Math.cos(live * Math.PI * 2 - Math.PI / 2) * r} cy={r + 40 + Math.sin(live * Math.PI * 2 - Math.PI / 2) * r} r={width * 0.9} fill={color} style={{ filter: `drop-shadow(0 0 10px ${rgba(color, 0.55)})` }} />
    </svg>
  );
}

/** reusable hanging price tag (paper) with value / label / swing */
export function TagCard({
  x,
  y,
  w,
  h,
  label,
  value,
  note,
  color = C.amber,
  rot = 0,
  alpha = 1,
  strikeNote = false,
  swing = 0,
  children,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  value: string;
  note?: string;
  color?: string;
  rot?: number;
  alpha?: number;
  strikeNote?: boolean;
  swing?: number;
  children?: ReactNode;
}) {
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, height: h, opacity: alpha, transform: `rotate(${rot + swing}deg)`, transformOrigin: '50% 0%' }}>
      <div style={{ position: 'absolute', left: w / 2 - 1, top: -y + 132, height: y - 132, width: 2, background: rgba(C.paper, 0.26) }} />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: `linear-gradient(180deg, #f0ebe0 0%, ${C.paper} 52%, ${C.paperShade} 100%)`,
          boxShadow: '0 26px 60px rgba(0,0,0,.55), inset 0 0 0 1px rgba(80,62,38,.22)',
          overflow: 'hidden',
        }}
      >
        <div className="gfx-fibre" style={{ position: 'absolute', inset: 0, opacity: 0.7 }} />
        <div style={{ position: 'absolute', left: w / 2 - 7, top: 16, width: 14, height: 14, borderRadius: '50%', background: 'rgba(11,14,17,.4)', boxShadow: 'inset 0 2px 3px rgba(0,0,0,.5)' }} />
        <div style={{ position: 'absolute', left: 0, top: 46, width: w, height: 3, background: color, opacity: 0.85 }} />
        <Txt text={label} x={26} y={64} size={22} font="mono" color={C.inkSoft} alpha={0.8} track={2} />
        <Txt text={value} x={26} y={104} size={Math.min(88, w * 0.26)} font="mono" color={color === C.paper ? C.ink : color} alpha={0.98} track={-2} weight={700} />
        {note ? (
          <Txt
            text={note}
            x={26}
            y={h - 56}
            size={20}
            font="mono"
            color={C.inkSoft}
            alpha={0.7}
            track={1}
            style={strikeNote ? { textDecoration: 'line-through', textDecorationColor: C.red, textDecorationThickness: 2 } : undefined}
          />
        ) : null}
        {children}
      </div>
    </div>
  );
}
