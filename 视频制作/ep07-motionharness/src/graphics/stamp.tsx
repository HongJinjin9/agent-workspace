// 印章 v2：落下冲击 + 冲击环 + 墨迹扩散 + 判词 kinetic（评估系统的判断动作）
import { C, W, GFXLayer, Txt, CornerTicks, SealMark, Camera, Kinetic, ScanBeam, useLocal, clamp, easeOutQuint, easeOutCubic, prog, inRamp, rgba } from './prims';

export interface StampProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  x?: number;
  y?: number;
  size?: number;
  rot?: number;
  color?: string;
  at?: number;
  scrim?: boolean;
  exhibit?: string;
}

export function Stamp({ time, from = 0, to = 3, headline = '', sub, x = W / 2, y = 466, size = 300, rot = -7, color = C.red, at = 0.1, scrim = true, exhibit = 'EXHIBIT 17' }: StampProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 3) - from);
  const hit = easeOutQuint(prog(t, at, at + 0.2));
  if (hit <= 0) return null;
  const bleed = clamp((t - at - 0.02) / 0.9);
  const ring = easeOutCubic(prog(t, at + 0.02, at + 0.5));
  const text = /判刑|重新评估/.test(headline) ? '重新评估' : '重估';
  const capIn = inRamp(t, at + 0.18, 0.3);
  const lines = headline.includes('，') ? headline.split('，').map((s) => s.trim()) : [headline];
  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={1.1}>
        <Txt text="VERDICT STAMP" x={168} y={200} size={18} font="mono" color={C.red} alpha={0.55} track={3} />
        <Txt text={exhibit} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.3} track={2} align="right" />
        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />
        {scrim ? <div style={{ position: 'absolute', left: x - size * 1.7, top: y - size * 1.7, width: size * 3.4, height: size * 3.4, borderRadius: '50%', background: 'radial-gradient(circle, rgba(4,5,7,.4) 0%, rgba(4,5,7,.16) 44%, transparent 70%)', opacity: clamp(hit * 1.4) }} /> : null}
        {/* impact rings */}
        <div style={{ position: 'absolute', left: x - size * (0.7 + ring * 0.9), top: y - size * (0.7 + ring * 0.9), width: size * 2 * (0.7 + ring * 0.9), height: size * 2 * (0.7 + ring * 0.9), borderRadius: '50%', border: `2px solid ${rgba(C.red, 0.4 * (1 - ring))}`, opacity: 1 - ring }} />
        <div style={{ position: 'absolute', left: x - size * (0.7 + ring * 1.4), top: y - size * (0.7 + ring * 1.4), width: size * 2 * (0.7 + ring * 1.4), height: size * 2 * (0.7 + ring * 1.4), borderRadius: '50%', border: `1px solid ${rgba(C.red, 0.3 * (1 - ring))}`, opacity: 1 - ring }} />
        <SealMark x={x} y={y} size={size} text={text} sub="EP07" rot={rot} color={color} hit={hit} bleed={bleed} blend={false} />
        {lines.map((line, i) => (
          <Kinetic key={i} text={line} x={W / 2} y={700 + i * 66} size={46} color={i === 0 ? C.paper : C.amber} local={t} delay={at + 0.22 + i * 0.14} step={0.02} track={3} weight={600} align="center" />
        ))}
        {sub ? <Txt text={sub} x={W / 2} y={700 + lines.length * 66 + 8} size={22} font="mono" color={C.paper} alpha={0.45 * capIn} track={2} align="center" /> : null}
        <ScanBeam local={t} y0={240} y1={860} speed={0.12} alpha={0.07} />
      </Camera>
    </GFXLayer>
  );
}
