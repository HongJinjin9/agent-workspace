// count_up / big_number v2：滚动数字 + 环形仪表 + 对照刻度（快节奏，主体 1.2s 内完成）
import { FACTS } from '../data/facts';
import { C, W, H, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, Camera, Odometer, GaugeArc, Kinetic, ScanBeam, Dust, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';

export interface CompareTick { value: number; label: string; color?: string }

export interface BigNumberProps {
  time?: number;
  from?: number;
  to?: number;
  value?: number;
  label?: string;
  sub?: string;
  note?: string;
  suffix?: string;
  decimals?: number;
  accent?: 'amber' | 'paper' | 'red';
  colorChoice?: 'amber' | 'paper' | 'red';
  compare?: CompareTick[] | boolean;
  gauge?: boolean;
  question?: boolean;
  align?: 'center' | 'left';
  exhibit?: string;
}

export function BigNumber({
  time,
  from = 0,
  to = 5,
  value = FACTS.overall.bev,
  label = '纯电 · 三年保值率',
  sub,
  note,
  suffix = '%',
  decimals = 1,
  accent,
  colorChoice,
  compare,
  gauge = true,
  question = false,
  align = 'center',
  exhibit = 'EXHIBIT 03',
}: BigNumberProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.5, (to ?? from + 4) - from);
  const pick = colorChoice ?? accent;
  const color = pick === 'red' ? C.red : pick === 'paper' ? C.paper : C.amber;
  const refs = Array.isArray(compare) ? compare : undefined;
  const X = align === 'center' ? W / 2 : 320;
  const center = align === 'center';
  const gaugeCx = W / 2;
  const gaugeCy = 548;
  const labelIn = inRamp(t, 0.0, 0.26);
  const subIn = inRamp(t, 0.42, 0.3);
  const metaIn = inRamp(t, 0.2, 0.3);
  const gaugeW = 1040;
  const gx = gaugeCx - gaugeW / 2;
  const gy = 790;

  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={0.8}>
        {gauge ? <GaugeArc value={value} x={gaugeCx} y={gaugeCy} r={332} color={rgba(color, 0.5)} local={t} delay={0.12} dur={0.8} width={8} alpha={0.55} /> : null}
        <Box x={0} y={0} w={0} h={0} alpha={metaIn}>
          <Rule x={168} y={252} w={W - 336} h={1} color={C.paper} alpha={0.18} progress={easeOutCubic(prog(t, 0.05, 0.5))} />
          <Txt text={exhibit} x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.4} track={3} />
          <Txt text="三年保值率 · 2026-10 报告" x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.3} track={2} align="right" />
        </Box>
        <Txt text={label} x={center ? W / 2 : X} y={300} size={32} font="sans" color={C.paper} alpha={0.8 * labelIn} track={5} align={center ? 'center' : 'left'} />
        {/* rolling number (or a big question mark) */}
        {question ? (
          <Txt text="?" x={center ? W / 2 : X} y={330} size={340} font="serif" color={C.amber} alpha={easeOutCubic(prog(t, 0.1, 0.5))} align={center ? 'center' : 'left'} weight={700} style={{ transform: `translateY(${lerp(26, 0, easeOutCubic(prog(t, 0.1, 0.5)))}px)` }} />
        ) : (
          <Odometer value={value} x={center ? W / 2 : X} y={372} size={282} color={color} local={t} delay={0.06} dur={0.58} digitsAfter={decimals} suffix={suffix} align={center ? 'center' : 'left'} glow={0.35} />
        )}
        {/* gauge 0–100 markers */}
        <Box x={0} y={0} w={0} h={0} alpha={!gauge || question ? 0 : easeOutCubic(prog(t, 0.22, 0.7))}>
          <Rule x={gx} y={gy} w={gaugeW} h={2} color={C.paper} alpha={0.3} progress={1} />
          {Array.from({ length: 11 }).map((_, i) => {
            const v = i * 10;
            const x = gx + (v / 100) * gaugeW;
            const big = i % 5 === 0;
            return (
              <Box key={i} x={0} y={0} w={0} h={0} alpha={1}>
                <div style={{ position: 'absolute', left: x, top: gy - (big ? 13 : 7), width: 2, height: big ? 13 : 7, background: C.paper, opacity: big ? 0.5 : 0.24 }} />
                {big ? <Txt text={`${v}`} x={x} y={gy + 22} size={16} font="mono" color={C.paper} alpha={0.38} track={1} align="center" /> : null}
              </Box>
            );
          })}
          <div style={{ position: 'absolute', left: gx + (clamp(value, 0, 100) / 100) * gaugeW - 2, top: gy - 24, width: 4, height: 48, background: color, boxShadow: `0 0 20px ${rgba(color, 0.6)}` }} />
          <Txt text={`${value}${suffix}`} x={gx + (clamp(value, 0, 100) / 100) * gaugeW} y={gy + 52} size={24} font="mono" color={color} alpha={0.95} track={1} align="center" />
          {(refs ?? []).map((c, i) => {
            const cx2 = gx + (clamp(c.value, 0, 100) / 100) * gaugeW;
            const ci = easeOutCubic(prog(t, 0.52 + i * 0.14, 0.82 + i * 0.14));
            return (
              <Box key={i} x={0} y={0} w={0} h={0} alpha={ci}>
                <div style={{ position: 'absolute', left: cx2 - 1, top: gy - 44, width: 2, height: 44, background: c.color ?? C.paper, opacity: 0.6 }} />
                <Txt text={c.label} x={cx2} y={gy - 76} size={19} font="mono" color={c.color ?? C.paper} alpha={0.8} track={1} align="center" />
              </Box>
            );
          })}
        </Box>
        {sub ? <Txt text={sub} x={center ? W / 2 : X} y={700} size={30} font="sans" color={C.paper} alpha={0.68 * subIn} track={2} align={center ? 'center' : 'left'} /> : null}
        {note ? <Txt text={note} x={center ? W / 2 : X} y={752} size={20} font="mono" color={C.paper} alpha={0.4 * subIn} track={1} align={center ? 'center' : 'left'} /> : null}
        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />
        <ScanBeam local={t} y0={280} y1={860} speed={0.09} alpha={0.08} />
        <Dust local={t} count={10} seed={907} alpha={0.3} />
        <Speckles x={0} y={132} w={1920} h={816} seed={907} count={12} maxAlpha={0.04} />
      </Camera>
    </GFXLayer>
  );
}
