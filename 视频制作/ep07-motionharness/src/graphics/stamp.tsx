// 印章：重估 / 重新评估 / 有异议 —— 落下 + 墨迹扩散 + 一句判词（评估系统的判断动作）
import { C, W, H, GFXLayer, Txt, CornerTicks, SealMark, useLocal, clamp, easeOutQuint, prog, inRamp } from './prims';

export interface StampProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  /** seal center in 1920×1080 px */
  x?: number;
  y?: number;
  size?: number;
  rot?: number;
  color?: string;
  /** local second of the hit */
  at?: number;
  scrim?: boolean;
  exhibit?: string;
}

export function Stamp({
  time,
  from = 0,
  headline = '',
  sub,
  x = W / 2,
  y = 468,
  size = 300,
  rot = -7,
  color = C.red,
  at = 0.12,
  scrim = true,
  exhibit = 'EXHIBIT 17 / 判断章',
}: StampProps) {
  const t = useLocal(time, from);
  const hit = easeOutQuint(prog(t, at, at + 0.22));
  if (hit <= 0) return null;
  const bleed = clamp((t - at - 0.02) / 0.9);
  const reEval = /判刑|重新评估/.test(headline);
  const text = reEval ? '重新评估' : '重估';
  const capIn = inRamp(t, at + 0.22, 0.32);
  const lines = headline.includes('，') ? headline.split('，').map((s) => s.trim()) : [headline];
  return (
    <GFXLayer>
      <Txt text="VERDICT STAMP · 判断章" x={168} y={200} size={18} font="mono" color={C.red} alpha={0.55} track={3} />
      <Txt text={exhibit} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.3} track={2} align="right" />
      <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />
      {scrim ? (
        <div
          style={{
            position: 'absolute',
            left: x - size * 1.6,
            top: y - size * 1.6,
            width: size * 3.2,
            height: size * 3.2,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(4,5,7,.34) 0%, rgba(4,5,7,.14) 44%, transparent 70%)',
            opacity: clamp(hit * 1.4),
          }}
        />
      ) : null}
      <SealMark x={x} y={y} size={size} text={text} sub="EP07" rot={rot} color={color} hit={hit} bleed={bleed} blend={false} />
      {lines.map((line, i) => (
        <Txt
          key={i}
          text={line}
          x={W / 2}
          y={706 + i * 66}
          size={46}
          font="serif"
          color={i === 0 ? C.paper : C.amber}
          alpha={0.95 * capIn}
          track={3}
          weight={600}
          align="center"
          style={{ clipPath: `inset(0% ${(1 - capIn) * 100}% 0% 0%)` }}
        />
      ))}
      {sub ? <Txt text={sub} x={W / 2} y={706 + lines.length * 66 + 10} size={22} font="mono" color={C.paper} alpha={0.45 * capIn} track={2} align="center" /> : null}
      <Txt text="一个品类，正在被重新估值" x={W / 2} y={848} size={20} font="mono" color={C.paper} alpha={0.34 * capIn} track={2} align="center" />
    </GFXLayer>
  );
}
