// 报告封面 v2：文件砸入 + 红线拉出 + 标题 kinetic + 「刚发布」印章砸下
import { FACTS } from '../data/facts';
import { C, W, GFXLayer, Txt, Box, Paper, Rule, CornerTicks, Speckles, Camera, Kinetic, ScanBeam, Dust, SealMark, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp } from './prims';

export interface ReportCoverProps {
  time?: number;
  from?: number;
  to?: number;
  title?: string;
  publisher?: string;
  date?: string;
  stamp?: string;
  source?: string;
  exhibit?: string;
}

export function ReportCover({
  time,
  from = 0,
  to = 4,
  title = FACTS.report.title,
  publisher = FACTS.report.publisher,
  date = FACTS.report.date,
  stamp = '刚发布',
  source,
  exhibit = 'EXHIBIT 02',
}: ReportCoverProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 4) - from);
  const slam = easeOutQuint(prog(t, 0.04, 0.34));
  const cardIn = inRamp(t, 0.02, 0.3);
  const rule1 = easeOutCubic(prog(t, 0.24, 0.6));
  const stampHit = easeOutQuint(prog(t, 0.5, 0.74));
  const stampBleed = clamp((t - 0.54) / 0.9);
  const float = Math.sin(t * 0.9) * 2.5;

  const idx = title.indexOf('中国汽车');
  const line1 = idx > 0 ? title.slice(0, idx).trim() : title;
  const line2 = idx > 0 ? title.slice(idx) : '';

  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={1.0}>
        <Box
          x={556}
          y={206 + float}
          w={808}
          h={664}
          rot={-1.2}
          alpha={cardIn}
          style={{ transform: `translateY(${lerp(-70, 0, slam)}px) scale(${lerp(1.05, 1, slam)})`, filter: `blur(${(1 - slam) * 2.2}px)` }}
        >
          <Paper x={0} y={0} w={808} h={664} rot={0} opacity={1}>
            <CornerTicks x={26} y={26} w={756} h={612} color={C.ink} alpha={0.26} size={18} />
            <Txt text={publisher} x={64} y={56} size={23} font="sans" color={C.inkSoft} alpha={0.8 * inRamp(t, 0.14, 0.3)} track={4} />
            <Txt text="CHINA AUTOMOBILE DEALERS ASSOCIATION" x={64} y={92} size={12} font="mono" color={C.inkSoft} alpha={0.42 * inRamp(t, 0.16, 0.3)} track={2} />
            <Txt text={exhibit} x={744} y={58} size={15} font="mono" color={C.inkSoft} alpha={0.6 * inRamp(t, 0.18, 0.3)} track={2} align="right" />
            <Rule x={64} y={124} w={680} h={3} color={C.red} alpha={0.85} progress={rule1} />
            <Kinetic text={line1} x={64} y={168} size={64} color={C.ink} local={t} delay={0.2} step={0.02} track={2} weight={700} />
            <Kinetic text={line2} x={64} y={250} size={64} color={C.ink} local={t} delay={0.3} step={0.02} track={2} weight={700} />
            <Txt text="三年保值率 / 二手车残值" x={64} y={346} size={24} font="mono" color={C.inkSoft} alpha={0.7 * inRamp(t, 0.5, 0.3)} track={3} />
            <Rule x={64} y={394} w={680} h={1} color={C.ink} alpha={0.3} progress={easeOutCubic(prog(t, 0.55, 0.85))} />
            <Box x={64} y={0} w={0} h={0} alpha={inRamp(t, 0.56, 0.3)}>
              <Txt text="发布日期" x={0} y={430} size={18} font="sans" color={C.inkSoft} alpha={0.65} track={2} />
              <Txt text={date} x={0} y={460} size={42} font="mono" color={C.ink} track={1} weight={700} />
              <Txt text="发布机构" x={0} y={532} size={18} font="sans" color={C.inkSoft} alpha={0.65} track={2} />
              <Txt text={publisher} x={0} y={562} size={30} font="sans" color={C.ink} track={2} />
              <Txt text="报告口径 · 2026 年 10 月" x={0} y={612} size={16} font="mono" color={C.inkSoft} alpha={0.5} track={1} />
            </Box>
            <Txt text="数据来源：中国汽车流通协会公开发布" x={64} y={628} size={14} font="mono" color={C.inkSoft} alpha={0.5} track={1} />
            <SealMark x={628} y={520} size={196} text={stamp} rot={-9} color={C.red} hit={stampHit} bleed={stampBleed} blend />
          </Paper>
        </Box>
        <Kinetic text="报告 · REPORT" x={168} y={312} size={22} color={C.paper} local={t} delay={0.02} track={5} font="mono" weight={400} rise={10} />
        <Txt text="CASE FILE · EP07 / 报告封面" x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.34 * cardIn} track={3} />
        <Txt text="EXHIBIT 02 · 数据来源页" x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.3 * cardIn} track={2} align="right" />
        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.12} size={16} />
        {source ? <Txt text={source} x={168} y={898} size={16} font="mono" color={C.paper} alpha={0.36 * inRamp(t, 0.8, 0.3)} track={1} /> : null}
        <ScanBeam local={t} y0={240} y1={870} speed={0.1} alpha={0.07} />
        <Dust local={t} count={10} seed={811} alpha={0.28} />
      </Camera>
    </GFXLayer>
  );
}
