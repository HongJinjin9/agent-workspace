// 对照柱 v2：两根柱从基线长出（一多半 vs 四成半），数字滚动、50% 参照线、差值括号
import { FACTS } from '../data/facts';
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, Camera, Odometer, Kinetic, ScanBeam, Dust, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from '../graphics/prims';

export interface CompareBarsProps {
  time?: number;
  from?: number;
  to?: number;
  items?: Array<{ label: string; value: number; highlight?: boolean; display?: string; note?: string }>;
  max?: number;
  unit?: string;
  headline?: string;
  sub?: string | null;
  exhibit?: string;
}

export function CompareBars({ time, from = 0, to = 4, items, max = 60, unit = '%', headline = '', sub, exhibit = 'EXHIBIT 13' }: CompareBarsProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 4) - from);
  const data = items ?? [
    { label: '中大型 SUV', value: FACTS.categories.largeSuv, highlight: true },
    { label: '纯电', value: FACTS.overall.bev },
  ];
  const baseY = 776;
  const hMax = 400;
  const bw = 190;
  const x0 = 470;
  const gap = 330;
  const refY = baseY - (50 / max) * hMax;
  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={0.9}>
        <Txt text={exhibit} x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.4} track={3} />
        <Txt text="对照 · 三年保值率" x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.3} track={2} align="right" />
        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />
        {headline ? <Kinetic text={headline} x={168} y={268} size={42} color={C.paper} local={t} delay={0.02} track={2} weight={600} /> : null}
        <Rule x={240} y={baseY} w={W - 480} h={2} color={C.paper} alpha={0.5} progress={easeOutCubic(prog(t, 0.06, 0.4))} />
        {/* 50% reference */}
        <Box x={0} y={0} w={0} h={0} alpha={easeOutCubic(prog(t, 0.3, 0.6))}>
          <div style={{ position: 'absolute', left: 240, top: refY, width: W - 480, height: 1, background: 'repeating-linear-gradient(90deg, rgba(233,228,216,.3) 0 14px, transparent 14px 30px)' }} />
          <Txt text="50% · 五成线" x={W - 240} y={refY - 30} size={18} font="mono" color={C.paper} alpha={0.5} track={2} align="right" />
        </Box>
        {data.map((d, i) => {
          const p = easeOutQuint(prog(t, 0.14 + i * 0.2, 0.66 + i * 0.2));
          const h = (d.value / max) * hMax * p;
          const x = x0 + i * gap;
          const col = d.highlight ? C.amber : C.paper;
          return (
            <Box key={d.label} x={0} y={0} w={0} h={0} alpha={1}>
              <div style={{ position: 'absolute', left: x, top: baseY - h, width: bw, height: h, background: `linear-gradient(180deg, ${rgba(col, 0.42)}, ${rgba(col, 0.1)})`, borderTop: `3px solid ${col}`, borderLeft: `2px solid ${col}` }} />
              <div style={{ position: 'absolute', left: x + bw / 2 - 2, top: baseY - h - 8, width: 4, height: 8, background: col, opacity: 0.9 }} />
              {d.display ? (
                <Txt text={d.display} x={x + bw / 2} y={baseY - h - 84} size={52} font="mono" color={col} alpha={Math.min(1, p * 2)} align="center" weight={700} />
              ) : (
                <Odometer value={d.value} x={x + bw / 2} y={baseY - h - 104} size={64} color={col} local={t} delay={0.14 + i * 0.2} dur={0.6} digitsAfter={1} suffix={unit} align="center" glow={0.25} />
              )}
              <Txt text={d.label} x={x + bw / 2} y={baseY + 34} size={30} font="sans" color={C.paper} alpha={0.9} track={2} align="center" />
              {d.note ? <Txt text={d.note} x={x + bw / 2} y={baseY + 76} size={18} font="mono" color={col} alpha={0.62} track={2} align="center" /> : null}
            </Box>
          );
        })}
        {data.length === 2 ? (
          <Box x={0} y={0} w={0} h={0} alpha={easeOutCubic(prog(t, 0.8, 1.15))}>
            <Txt text={`${(data[0].value - data[1].value).toFixed(1)} 个百分点`} x={W / 2} y={baseY + 140} size={26} font="mono" color={C.amber} alpha={0.7} track={2} align="center" />
          </Box>
        ) : null}
        {data.length === 2 && !data.some((d) => d.note) && !sub ? (
          <Txt text="同样三年，差别这么大" x={W - 240} y={baseY + 140} size={22} font="mono" color={C.paper} alpha={0.4 * inRamp(t, 1.0, 0.3)} track={2} align="right" />
        ) : null}
        <ScanBeam local={t} y0={260} y1={860} speed={0.12} alpha={0.08} />
        <Dust local={t} count={10} seed={2301} alpha={0.3} />
        <Speckles x={0} y={132} w={1920} h={816} seed={2301} count={12} maxAlpha={0.04} />
      </Camera>
    </GFXLayer>
  );
}
