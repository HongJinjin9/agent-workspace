// 段落小标 / 编辑型短句：ACT 幕标 + 一句话判断（快进快出，不做常驻章节卡）
import { THEME } from '../data/theme';
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, useLocal, inRamp, prog, easeOutCubic, lerp } from './prims';

export interface SectionLabelProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  seg?: string;
  exhibit?: string;
}

export function SectionLabel({ time, from = 0, to, headline = '', sub, seg = 'ACT1', exhibit = 'CASE FILE · EP07' }: SectionLabelProps) {
  const t = useLocal(time, from);
  const g = typeof time === 'number' ? time : from + t;
  const outP = to != null ? 1 - inRamp(g, to - 0.34, 0.3) : 1;
  const inP = inRamp(t, 0.02, 0.28);
  const a = inP * outP;
  if (a <= 0.001) return null;
  const segLabel = THEME.segments.find((s) => s.id === seg)?.label ?? seg;
  const long = headline.length > 9;
  const size = long ? 76 : 92;
  const lines = headline.includes('，') ? headline.split('，').map((s) => s.trim()) : [headline];

  return (
    <GFXLayer>
      <div style={{ position: 'absolute', inset: 0, opacity: a }}>
        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />
        {/* act kicker */}
        <div style={{ position: 'absolute', left: 168, top: 206, width: 10, height: 10, background: C.amber, opacity: 0.9 }} />
        <Txt text={segLabel} x={190} y={198} size={20} font="mono" color={C.amber} alpha={0.72} track={4} />
        <Txt text={exhibit} x={W - 168} y={198} size={18} font="mono" color={C.paper} alpha={0.32} track={3} align="right" />

        {/* editorial line */}
        {lines.map((line, i) => {
          const pp = easeOutCubic(prog(t, 0.06 + i * 0.14, 0.44 + i * 0.14));
          return (
            <Txt
              key={i}
              text={line}
              x={196}
              y={392 + i * (size * 1.28)}
              size={size}
              font="serif"
              color={i === 0 ? C.paper : C.amber}
              alpha={0.97 * pp}
              track={lerp(10, 3, pp)}
              weight={600}
              style={{ clipPath: `inset(0% ${(1 - pp) * 100}% 0% 0%)`, transform: `translateY(${lerp(18, 0, pp)}px)` }}
            />
          );
        })}
        {sub ? <Txt text={sub} x={198} y={392 + lines.length * size * 1.28 + 22} size={28} font="mono" color={C.amber} alpha={0.7 * inRamp(t, 0.24, 0.34)} track={2} /> : null}
        <Rule x={196} y={392 + lines.length * size * 1.28 + (sub ? 80 : 40)} w={560} h={1} color={C.amber} alpha={0.5} progress={easeOutCubic(prog(t, 0.2, 0.6))} />
        <Txt text="卷宗 07 · 保值率报告" x={196} y={846} size={16} font="mono" color={C.paper} alpha={0.3} track={2} />
        <Speckles x={0} y={132} w={1920} h={816} seed={1901} count={14} maxAlpha={0.04} />
      </div>
    </GFXLayer>
  );
}
