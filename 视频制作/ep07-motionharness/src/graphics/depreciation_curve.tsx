// 折旧曲线 v2：20 万 → 9 万 沿时间画出（面积渐显 + 移动端点 + 11 万括号 + 3.7 万/年）
import { FACTS } from '../data/facts';
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, Camera, Odometer, Kinetic, ScanBeam, Dust, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from '../graphics/prims';

export interface DepreciationCurveProps {
  time?: number;
  from?: number;
  to?: number;
  start?: number;
  end?: number;
  years?: number;
  headline?: string;
  sub?: string | null;
  exhibit?: string;
}

const PX0 = 300;
const PX1 = 1600;
const PY0 = 320; // y for start value (top)
const PY1 = 780; // y for 0
const VMAX = 22;

export function DepreciationCurve({
  time,
  from = 0,
  to = 5,
  start = FACTS.hook.newPrice,
  end = FACTS.hook.usedPrice,
  years = FACTS.hook.years,
  headline = '',
  sub,
  exhibit = 'EXHIBIT 05',
}: DepreciationCurveProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 5) - from);
  const yOf = (v: number) => PY1 - (v / VMAX) * (PY1 - PY0);
  const pts = Array.from({ length: years + 1 }, (_, i) => {
    const v = lerp(start, end, i / years);
    return { x: PX0 + (i / years) * (PX1 - PX0), y: yOf(v), v };
  });
  const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const area = `${d} L ${PX1} ${PY1} L ${PX0} ${PY1} Z`;
  const draw = easeOutCubic(prog(t, 0.24, 1.5));
  const dotP = easeOutCubic(prog(t, 0.24, 1.5));
  const dotX = lerp(PX0, PX1, dotP);
  const dotY = lerp(yOf(start), yOf(end), dotP);
  const dotV = lerp(start, end, dotP);
  const endIn = inRamp(t, 1.2, 0.36);
  const deltaIn = inRamp(t, 1.5, 0.36);

  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={0.9}>
        <Txt text={exhibit} x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.4} track={3} />
        <Txt text="折旧 · RESIDUAL VALUE" x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.3} track={2} align="right" />
        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />
        {headline ? <Kinetic text={headline} x={168} y={268} size={40} color={C.paper} local={t} delay={0.02} track={2} weight={600} /> : null}

        {/* axes + grid */}
        <Rule x={PX0} y={PY1} w={PX1 - PX0} h={2} color={C.paper} alpha={0.45} progress={easeOutCubic(prog(t, 0.06, 0.4))} />
        <div style={{ position: 'absolute', left: PX0, top: PY0, width: 1, height: PY1 - PY0, background: C.paper, opacity: 0.35 }} />
        {[0, 5, 10, 15, 20].map((v) => (
          <Box key={v} x={0} y={0} w={0} h={0} alpha={easeOutCubic(prog(t, 0.1, 0.4))}>
            <div style={{ position: 'absolute', left: PX0 - 8, top: yOf(v), width: 8, height: 1, background: C.paper, opacity: 0.4 }} />
            <Txt text={`${v} 万`} x={PX0 - 18} y={yOf(v)} size={17} font="mono" color={C.paper} alpha={0.4} track={1} align="right" style={{ transform: 'translateY(-50%)' }} />
          </Box>
        ))}
        {/* year ticks */}
        {Array.from({ length: years + 1 }).map((_, i) => {
          const x = PX0 + (i / years) * (PX1 - PX0);
          return (
            <Box key={i} x={0} y={0} w={0} h={0} alpha={easeOutCubic(prog(t, 0.12 + i * 0.04, 0.4 + i * 0.04))}>
              <div style={{ position: 'absolute', left: x, top: PY1, width: 2, height: 12, background: C.paper, opacity: 0.45 }} />
              <Txt text={i === 0 ? '新车' : `${i} 年`} x={x} y={PY1 + 24} size={18} font="mono" color={C.paper} alpha={0.5} track={1} align="center" />
            </Box>
          );
        })}

        {/* area + line SVG */}
        <svg width={W} height={1080} style={{ position: 'absolute', left: 0, top: 0, overflow: 'visible' }}>
          <defs>
            <linearGradient id="dep-area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={rgba(C.amber, 0.32)} />
              <stop offset="100%" stopColor={rgba(C.amber, 0.02)} />
            </linearGradient>
          </defs>
          <path d={area} fill="url(#dep-area)" opacity={draw} />
          <path d={d} fill="none" stroke={C.amber} strokeWidth={5} strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw} style={{ filter: `drop-shadow(0 0 14px ${rgba(C.amber, 0.5)})` }} />
          <circle cx={dotX} cy={dotY} r={9} fill={C.amber} style={{ filter: `drop-shadow(0 0 14px ${rgba(C.amber, 0.7)})` }} />
          <circle cx={dotX} cy={dotY} r={18} fill="none" stroke={rgba(C.amber, 0.5)} strokeWidth={2} />
        </svg>
        <Txt text={`${dotV.toFixed(1)} 万`} x={dotX + 26} y={dotY - 42} size={40} font="mono" color={C.amber} alpha={0.95} track={-1} weight={700} />
        <Txt text="残值" x={dotX + 28} y={dotY + 4} size={18} font="mono" color={C.paper} alpha={0.55} track={2} />
        <Odometer value={end} x={PX1 - 6} y={yOf(end) - 96} size={58} color={C.paper} local={t} delay={1.2} dur={0.5} digitsAfter={0} suffix=" 万" align="right" glow={0.2} />

        {/* 11 万 bracket */}
        <Box x={0} y={0} w={0} h={0} alpha={deltaIn}>
          <div style={{ position: 'absolute', left: PX1 + 26, top: yOf(start), width: 2, height: yOf(end) - yOf(start), background: C.red, opacity: 0.8 }} />
          <div style={{ position: 'absolute', left: PX1 + 18, top: yOf(start), width: 18, height: 2, background: C.red, opacity: 0.8 }} />
          <div style={{ position: 'absolute', left: PX1 + 18, top: yOf(end), width: 18, height: 2, background: C.red, opacity: 0.8 }} />
          <Txt text={`蒸发 ${FACTS.hook.diff} 万`} x={PX1 + 46} y={(yOf(start) + yOf(end)) / 2 - 34} size={38} font="mono" color={C.red} alpha={0.95} track={1} weight={700} />
          <Txt text={`年均 ≈ ${FACTS.hook.perYear} 万`} x={PX1 + 46} y={(yOf(start) + yOf(end)) / 2 + 18} size={22} font="mono" color={C.paper} alpha={0.6} track={2} />
        </Box>
        <Txt text="按年均折旧示意 · 不计使用成本" x={PX0} y={PY1 + 82} size={16} font="mono" color={C.paper} alpha={0.3 * endIn} track={1} />
        <ScanBeam local={t} y0={280} y1={860} speed={0.1} alpha={0.08} />
        <Dust local={t} count={10} seed={2401} alpha={0.3} />
        <Speckles x={0} y={132} w={1920} h={816} seed={2401} count={12} maxAlpha={0.04} />
      </Camera>
    </GFXLayer>
  );
}
