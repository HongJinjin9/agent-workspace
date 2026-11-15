// 品类柱：中大型 SUV 50.6 / MPV 48.7 / 小型车 48.3（对照「五成线」）；分屏变体：一半多 vs 四成半
import { FACTS } from '../data/facts';
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, countUp, rgba } from './prims';

export interface CategoryBarsProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  /** optional explicit rows override */
  rows?: Array<{ label: string; value: number; color?: string; active?: boolean }>;
  exhibit?: string;
}

const BAR_X = 560;
const BAR_W = 1000;
const ROW_Y = 424;
const ROW_H = 108;
const BAR_H = 46;
const VALUE_MAX = 70;

export function CategoryBars({ time, from = 0, headline = '', sub, rows, exhibit = 'EXHIBIT 08 / 品类柱' }: CategoryBarsProps) {
  const t = useLocal(time, from);
  const split = /一半|四成半/.test(headline);
  const headIn = inRamp(t, 0.02, 0.28);
  const ruleIn = easeOutCubic(prog(t, 0.1, 0.46));

  if (split) {
    // 分屏：一边一半多（中大型 SUV 50.6%），一边四成半（纯电 45.1%）
    const leftVal = FACTS.categories.largeSuv;
    const rightVal = FACTS.overall.bev;
    const lp = inRamp(t, 0.04, 0.34);
    const rp = inRamp(t, 0.2, 0.34);
    return (
      <GFXLayer>
        <Txt text="CATEGORY SPLIT · 同三年，不同命" x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.4} track={3} />
        <Txt text={exhibit} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.36} track={2} align="right" />
        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.12} size={16} />
        <div style={{ position: 'absolute', left: W / 2, top: 300, width: 1, height: 460, background: C.paper, opacity: 0.18 * ruleIn }} />
        <Rule x={168} y={330} w={700} h={2} color={C.amber} alpha={0.6} progress={ruleIn} />
        <Rule x={W - 168 - 700} y={330} w={700} h={2} color={C.paper} alpha={0.3} progress={ruleIn} />
        <Txt text="一半多" x={W / 4} y={386} size={30} font="sans" color={C.amber} alpha={0.85 * lp} track={4} align="center" />
        <Txt text={`${leftVal}%`} x={W / 4} y={440} size={190} font="mono" color={C.amber} alpha={clamp(lp * 1.4)} track={-4} align="center" style={{ textShadow: `0 0 40px ${rgba(C.amber, 0.28)}`, lineHeight: 1 }} />
        <Txt text="中大型 SUV" x={W / 4} y={674} size={30} font="sans" color={C.paper} alpha={0.6 * lp} track={3} align="center" />
        <Txt text="四成半" x={(W * 3) / 4} y={386} size={30} font="sans" color={C.paper} alpha={0.75 * rp} track={4} align="center" />
        <Txt text={`${rightVal}%`} x={(W * 3) / 4} y={440} size={190} font="mono" color={C.paper} alpha={clamp(rp * 1.4)} track={-4} align="center" style={{ lineHeight: 1 }} />
        <Txt text="纯电" x={(W * 3) / 4} y={674} size={30} font="sans" color={C.paper} alpha={0.6 * rp} track={3} align="center" />
        <Txt text="同样三年，差别这么大" x={W / 2} y={788} size={24} font="mono" color={C.paper} alpha={0.42 * inRamp(t, 1.1, 0.4)} track={2} align="center" />
        <Speckles x={0} y={132} w={1920} h={816} seed={1301} count={16} maxAlpha={0.05} />
      </GFXLayer>
    );
  }

  const baseRows = rows ?? [
    { label: '中大型 SUV', value: FACTS.categories.largeSuv, color: C.amber, active: /中大型/.test(headline) },
    { label: 'MPV', value: FACTS.categories.mpv, color: C.paper, active: /MPV/.test(headline) },
    { label: '小型车', value: FACTS.categories.smallCar, color: C.paper, active: /小型车/.test(headline) },
  ];
  const anyActive = baseRows.some((r) => r.active);
  const fiveLineX = BAR_X + (50 / VALUE_MAX) * BAR_W;

  return (
    <GFXLayer>
      <Txt text="DATA WALL · 品类保值率" x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.4} track={3} />
      <Txt text={exhibit} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.36} track={2} align="right" />
      <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.12} size={16} />
      <Txt text={headline} x={168} y={276} size={46} font="serif" color={C.paper} alpha={0.92 * headIn} track={2} weight={600} style={{ clipPath: `inset(0% ${(1 - headIn) * 100}% 0% 0%)` }} />
      {sub ? <Txt text={sub} x={170} y={344} size={24} font="mono" color={C.amber} alpha={0.8 * headIn} track={2} /> : null}
      <Rule x={168} y={386} w={1584} h={1} color={C.paper} alpha={0.2} progress={ruleIn} />

      {/* 50% five-tenths reference */}
      <Box x={0} y={0} w={0} h={0} alpha={ruleIn}>
        <div style={{ position: 'absolute', left: fiveLineX, top: 424, width: 1, height: 330, background: C.amber, opacity: 0.55 }} />
        <Txt text="50% · 五成线" x={fiveLineX} y={396} size={18} font="mono" color={C.amber} alpha={0.8} track={1} align="center" />
      </Box>

      {baseRows.map((r, i) => {
        const y = ROW_Y + i * ROW_H;
        const rp = easeOutQuint(prog(t, 0.18 + i * 0.14, 0.56 + i * 0.14));
        const vp = easeOutQuint(prog(t, 0.18 + i * 0.14, 0.62 + i * 0.14));
        const shown = lerp(0, r.value, vp);
        const active = r.active || !anyActive;
        const col = active ? r.color ?? C.amber : C.paper;
        const a = active ? 1 : 0.45;
        return (
          <Box key={r.label} x={0} y={0} w={0} h={0} alpha={a}>
            <Txt text={r.label} x={168} y={y + 34} size={30} font="sans" color={C.paper} alpha={0.92 * inRamp(t, 0.1 + i * 0.1, 0.3)} track={2} />
            <div
              style={{
                position: 'absolute',
                left: BAR_X,
                top: y + 12,
                width: (clamp(r.value, 0, VALUE_MAX) / VALUE_MAX) * BAR_W * rp,
                height: BAR_H,
                background: `linear-gradient(90deg, ${rgba(col, 0.42)} 0%, ${rgba(col, 0.16)} 100%)`,
                borderLeft: `3px solid ${col}`,
                boxShadow: active ? `0 0 26px ${rgba(col, 0.18)}` : undefined,
              }}
            />
            <Txt text={`${shown.toFixed(1)}%`} x={BAR_X + 22 + (clamp(r.value, 0, VALUE_MAX) / VALUE_MAX) * BAR_W * rp} y={y + 18} size={40} font="mono" color={col} alpha={clamp(rp * 1.5)} track={-1} weight={700} />
            {Math.abs(r.value - 50) > 0.05 ? (
              <Txt text={r.value > 50 ? '唯一站上五成' : '未到五成'} x={W - 168} y={y + 30} size={18} font="mono" color={r.value > 50 ? C.amber : C.paper} alpha={0.45 * rp} track={2} align="right" />
            ) : null}
          </Box>
        );
      })}
      <Txt text="三年保值率 · 中国汽车流通协会 2026-10" x={W - 168} y={802} size={16} font="mono" color={C.paper} alpha={0.3} track={1} align="right" />
      <Speckles x={0} y={132} w={1920} h={816} seed={1307} count={16} maxAlpha={0.05} />
    </GFXLayer>
  );
}
