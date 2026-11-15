// 段落标题 v2：幕标 + kinetic 一句话判断（快进快出）
import { THEME } from '../data/theme';
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Camera, Kinetic, ScanBeam, Dust, useLocal, inRamp, prog, easeOutCubic, lerp } from './prims';

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
  const dur = Math.max(0.6, (to ?? from + 3.2) - from);
  const g = typeof time === 'number' ? time : from + t;
  const outP = to != null ? 1 - inRamp(g, to - 0.3, 0.28) : 1;
  const segLabel = THEME.segments.find((s) => s.id === seg)?.label ?? seg;
  const lines = headline.includes('，') ? headline.split('，').map((s) => s.trim()) : [headline];
  const long = Math.max(...lines.map((l) => l.length)) > 9;
  const size = long ? 76 : 94;
  if (outP <= 0.001) return null;
  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={1.0}>
        <div style={{ position: 'absolute', inset: 0, opacity: outP }}>
          <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />
          <Box x={0} y={0} w={0} h={0} alpha={inRamp(t, 0.02, 0.24)} style={{ transform: `translateX(${lerp(-26, 0, inRamp(t, 0.02, 0.3))}px)` }}>
            <div style={{ position: 'absolute', left: 168, top: 206, width: 10, height: 10, background: C.amber, opacity: 0.9 }} />
            <Txt text={segLabel} x={190} y={198} size={20} font="mono" color={C.amber} alpha={0.72} track={4} />
            <Txt text={exhibit} x={W - 168} y={198} size={18} font="mono" color={C.paper} alpha={0.32} track={3} align="right" />
          </Box>
          {lines.map((line, i) => (
            <Kinetic key={i} text={line} x={196} y={392 + i * (size * 1.26)} size={size} color={i === 0 ? C.paper : C.amber} local={t} delay={0.06 + i * 0.1} step={0.02} track={3} weight={600} />
          ))}
          {sub ? <Txt text={sub} x={198} y={392 + lines.length * size * 1.26 + 16} size={28} font="mono" color={C.amber} alpha={0.7 * inRamp(t, 0.24, 0.3)} track={2} /> : null}
          <Rule x={196} y={392 + lines.length * size * 1.26 + (sub ? 74 : 34)} w={560} h={1} color={C.amber} alpha={0.5} progress={easeOutCubic(prog(t, 0.2, 0.56))} />
          <Txt text="卷宗 07 · 保值率报告" x={196} y={846} size={16} font="mono" color={C.paper} alpha={0.3} track={2} />
          <ScanBeam local={t} y0={240} y1={860} speed={0.13} alpha={0.07} />
          <Dust local={t} count={10} seed={1901} alpha={0.28} />
        </div>
      </Camera>
    </GFXLayer>
  );
}
