// 榜单 v2：行逐条 build（条形生长 + 序号滚动），一年期 vs 三年期双面板对比
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, Camera, Kinetic, ScanBeam, Dust, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';

export interface RankingBoardProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  exhibit?: string;
  title?: string;
  rows?: Array<{ label?: string; chip?: string; value?: number; ratio?: number }>;
  build?: boolean;
  compareWith?: string;
}

function Panel({
  x,
  y,
  w,
  h,
  tag,
  title,
  rows,
  accent,
  base,
  t,
  note,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  tag: string;
  title: string;
  rows: Array<{ chip: string; ratio: number }>;
  accent: string;
  base: number;
  t: number;
  note?: string;
}) {
  const panelIn = inRamp(t, base - 0.12, 0.28);
  return (
    <Box x={x} y={y} w={w} h={h} alpha={1} style={{ opacity: panelIn, transform: `translateY(${lerp(26, 0, panelIn)}px)` }}>
      <div style={{ position: 'absolute', inset: 0, background: 'rgba(10,13,16,.66)', border: `1px solid ${rgba(C.paper, 0.2)}` }} />
      <div style={{ position: 'absolute', left: 0, top: 0, width: 4, height: h, background: accent, opacity: 0.85 }} />
      <Txt text={tag} x={26} y={20} size={13} font="mono" color={accent} alpha={0.8} track={3} />
      <Txt text={title} x={26} y={42} size={28} font="serif" color={C.paper} alpha={0.94} track={2} weight={600} />
      <div style={{ position: 'absolute', left: 26, top: 88, width: w - 52, height: 1, background: C.paper, opacity: 0.2 }} />
      {rows.map((r, i) => {
        const p = easeOutQuint(prog(t, base + i * 0.05, base + 0.24 + i * 0.05));
        const on = r.chip !== '—';
        const col = r.chip === '新势力' ? C.amber : on ? C.metalLight : rgba(C.paper, 0.2);
        return (
          <Box key={i} x={0} y={0} w={0} h={0} alpha={p}>
            <Txt text={String(i + 1).padStart(2, '0')} x={26} y={102 + i * 31} size={18} font="mono" color={C.paper} alpha={0.55} track={1} />
            <div style={{ position: 'absolute', left: 86, top: 111 + i * 31, width: r.ratio * (w - 290) * p, height: 9, background: `linear-gradient(90deg, ${rgba(col, 0.55)}, ${rgba(col, 0.12)})`, borderLeft: `2px solid ${col}` }} />
            <Txt text={r.chip} x={w - 24} y={104 + i * 31} size={16} font="mono" color={col} alpha={on ? 0.85 : 0.4} track={2} align="right" />
          </Box>
        );
      })}
      {note ? <Txt text={note} x={26} y={h - 22} size={14} font="mono" color={C.paper} alpha={0.45} track={1} /> : null}
    </Box>
  );
}

export function RankingBoard({ time, from = 0, to = 5, headline = '', sub, exhibit = 'EXHIBIT 37', title, rows, compareWith }: RankingBoardProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 4.5) - from);
  const compare = /三年期|接盘|热度/.test(headline) || !!compareWith;
  const oneRows = (rows ?? Array.from({ length: 10 }, (_, i) => ({ chip: i < 8 ? '新势力' : '其他', ratio: i < 8 ? 0.78 - i * 0.03 : 0.3 }))).map((r) => ({ chip: r.chip ?? '—', ratio: (r as { ratio?: number }).ratio ?? 0.5 }));
  const threeRows = Array.from({ length: 10 }, (_, i) => ({ chip: i < 3 ? '传统品牌' : '—', ratio: i < 3 ? 0.6 - i * 0.08 : 0.22 }));
  const newForces = oneRows.filter((r) => r.chip === '新势力').length;

  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={0.9}>
        <Txt text="RANKING · 保值率榜单" x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.38} track={3} />
        <Txt text={exhibit} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.32} track={2} align="right" />
        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />
        <Kinetic text={headline} x={168} y={250} size={42} color={C.paper} local={t} delay={0.02} step={0.016} track={2} weight={600} />
        {sub ? <Txt text={sub} x={170} y={312} size={22} font="mono" color={C.amber} alpha={0.8 * inRamp(t, 0.1, 0.3)} track={2} /> : null}
        {compare ? (
          <>
            <Panel x={168} y={352} w={700} h={478} tag="2025-10 · 一年期" title="一年期 TOP10" rows={oneRows} accent={C.amber} base={0.24} t={t} note="小米 / 问界 靠前" />
            <Panel x={1052} y={352} w={700} h={478} tag="三年期 · 看接盘" title="三年期 TOP10" rows={threeRows} accent={C.metalLight} base={0.5} t={t} note="三年后还有没有人接" />
            <div style={{ position: 'absolute', left: 884, top: 578, width: 152 * easeOutCubic(prog(t, 0.7, 1.1)), height: 3, background: C.amber, opacity: 0.8 }} />
            <Txt text="→" x={884} y={544} size={46} font="mono" color={C.amber} alpha={0.9 * easeOutCubic(prog(t, 0.7, 1.1))} />
            <Kinetic text="一年期看热度，三年期看接盘" x={W / 2} y={856} size={28} color={C.paper} local={t} delay={1.0} step={0.012} track={3} align="center" font="sans" weight={500} />
          </>
        ) : (
          <>
            <Panel x={560} y={352} w={800} h={478} tag="2025-10 · 一年期" title="一年期 TOP10" rows={oneRows} accent={C.amber} base={0.22} t={t} note="小米 / 问界 靠前" />
            <Kinetic text={`国产新势力占 ${newForces} 席`} x={W / 2} y={852} size={40} color={C.amber} local={t} delay={0.8} step={0.02} track={3} align="center" weight={600} />
            <Txt text="榜单仅统计报告披露的席位数与阵营" x={W / 2} y={896} size={16} font="mono" color={C.paper} alpha={0.35 * inRamp(t, 0.9, 0.3)} track={1} align="center" />
          </>
        )}
        <ScanBeam local={t} y0={260} y1={860} speed={0.1} alpha={0.07} />
        <Dust local={t} count={10} seed={1601} alpha={0.28} />
        <Speckles x={0} y={132} w={1920} h={816} seed={1601} count={12} maxAlpha={0.04} />
      </Camera>
    </GFXLayer>
  );
}
