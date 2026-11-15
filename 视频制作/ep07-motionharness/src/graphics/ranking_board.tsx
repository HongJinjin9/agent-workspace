// 榜单：一年期 TOP10（新势力占八席）vs 三年期（看接盘）—— 席位数示意，不虚构车名
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';

export interface RankingBoardProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  exhibit?: string;
}

function Panel({
  x,
  y,
  w,
  h,
  title,
  tag,
  rows,
  accent,
  rowInBase,
  t,
  note,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  tag: string;
  /** each row: chip label ('新势力' | '其他' | '—') */
  rows: string[];
  accent: string;
  rowInBase: number;
  t: number;
  note?: string;
}) {
  const panelIn = inRamp(t, rowInBase - 0.16, 0.3);
  return (
    <Box x={x} y={y} w={w} h={h} alpha={1} style={{ opacity: panelIn, transform: `translateY(${lerp(24, 0, panelIn)}px)` }}>
      <div style={{ position: 'absolute', inset: 0, background: 'rgba(10,13,16,.62)', border: `1px solid ${rgba(C.paper, 0.22)}` }} />
      <div style={{ position: 'absolute', left: 0, top: 0, width: 4, height: h, background: accent, opacity: 0.85 }} />
      <Txt text={tag} x={28} y={22} size={13} font="mono" color={accent} alpha={0.8} track={3} />
      <Txt text={title} x={28} y={46} size={30} font="serif" color={C.paper} alpha={0.94} track={2} weight={600} />
      <div style={{ position: 'absolute', left: 28, top: 90, width: w - 56, height: 1, background: C.paper, opacity: 0.2 }} />
      {rows.map((chip, i) => {
        const rp = easeOutQuint(prog(t, rowInBase + i * 0.055, rowInBase + 0.26 + i * 0.055));
        const on = chip !== '—';
        const chipColor = chip === '新势力' ? C.amber : on ? C.metalLight : rgba(C.paper, 0.2);
        return (
          <Box key={i} x={0} y={0} w={0} h={0} alpha={rp}>
            <Txt text={String(i + 1).padStart(2, '0')} x={28} y={104 + i * 31} size={18} font="mono" color={C.paper} alpha={0.55} track={1} />
            <div
              style={{
                position: 'absolute',
                left: 88,
                top: 113 + i * 31,
                width: (on ? 0.78 : 0.34) * (w - 300),
                height: 9,
                background: `linear-gradient(90deg, ${rgba(chipColor, 0.5)}, ${rgba(chipColor, 0.12)})`,
                borderLeft: `2px solid ${chipColor}`,
              }}
            />
            <Txt text={chip} x={w - 26} y={106 + i * 31} size={16} font="mono" color={chipColor} alpha={on ? 0.85 : 0.4} track={2} align="right" />
          </Box>
        );
      })}
      {note ? <Txt text={note} x={28} y={h - 24} size={14} font="mono" color={C.paper} alpha={0.45} track={1} /> : null}
    </Box>
  );
}

export function RankingBoard({ time, from = 0, headline = '', sub, exhibit = 'EXHIBIT 37 / 榜单' }: RankingBoardProps) {
  const t = useLocal(time, from);
  const headIn = inRamp(t, 0.02, 0.28);
  const compare = /三年期|接盘|热度/.test(headline);
  const oneYearRows = Array.from({ length: 10 }, (_, i) => (i < 8 ? '新势力' : '其他'));
  const threeYearRows = Array.from({ length: 10 }, () => '—');
  const newForces = oneYearRows.filter((r) => r === '新势力').length;

  return (
    <GFXLayer>
      <Txt text="RANKING · 保值率榜单" x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.38} track={3} />
      <Txt text={exhibit} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.34} track={2} align="right" />
      <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.11} size={16} />
      <Txt text={headline} x={168} y={252} size={44} font="serif" color={C.paper} alpha={0.94 * headIn} track={2} weight={600} style={{ clipPath: `inset(0% ${(1 - headIn) * 100}% 0% 0%)` }} />
      {sub ? <Txt text={sub} x={170} y={314} size={22} font="mono" color={C.amber} alpha={0.8 * headIn} track={2} /> : null}

      {compare ? (
        <>
          <Panel x={168} y={352} w={700} h={478} title="一年期 TOP10" tag="2025-10 · 一年期" rows={oneYearRows} accent={C.amber} rowInBase={0.24} t={t} note="小米 / 问界 靠前" />
          <Panel x={1052} y={352} w={700} h={478} title="三年期 TOP10" tag="三年期 · 看接盘" rows={threeYearRows} accent={C.metalLight} rowInBase={0.5} t={t} note="三年后还有没有人接" />
          <div style={{ position: 'absolute', left: 884, top: 570, width: 152, height: 3, background: C.amber, opacity: 0.8 * easeOutCubic(prog(t, 0.8, 1.2)) }} />
          <Txt text="→" x={884} y={538} size={46} font="mono" color={C.amber} alpha={0.9 * easeOutCubic(prog(t, 0.8, 1.2))} />
          <Txt text="一年期看热度，三年期看接盘" x={W / 2} y={856} size={28} font="sans" color={C.paper} alpha={0.6 * inRamp(t, 1.2, 0.4)} track={3} align="center" />
        </>
      ) : (
        <>
          <Panel x={560} y={352} w={800} h={478} title="一年期 TOP10" tag="2025-10 · 一年期" rows={oneYearRows} accent={C.amber} rowInBase={0.22} t={t} note="小米 / 问界 靠前" />
          <Txt text={`国产新势力占 ${newForces} 席`} x={W / 2} y={852} size={40} font="serif" color={C.amber} alpha={0.95 * inRamp(t, 1.05, 0.4)} track={3} align="center" weight={600} />
          <Txt text="榜单仅统计报告披露的席位数与阵营" x={W / 2} y={896} size={16} font="mono" color={C.paper} alpha={0.35 * inRamp(t, 1.2, 0.4)} track={1} align="center" />
        </>
      )}
      <Speckles x={0} y={132} w={1920} h={816} seed={1601} count={16} maxAlpha={0.05} />
    </GFXLayer>
  );
}
