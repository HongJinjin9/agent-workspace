// 报告封面卡：中国汽车流通协会 2026 年 10 月保值率报告（红章「刚发布」）
import { FACTS } from '../data/facts';
import {
  C,
  GFXLayer,
  Txt,
  Box,
  Paper,
  Rule,
  CornerTicks,
  Speckles,
  Kicker,
  MetaRow,
  useLocal,
  inRamp,
  prog,
  easeOutCubic,
  easeOutQuint,
  lerp,
  clamp,
  SealMark,
} from './prims';

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
  title = FACTS.report.title,
  publisher = FACTS.report.publisher,
  date = FACTS.report.date,
  stamp = '刚发布',
  source,
  exhibit = 'EXHIBIT 02 / 报告',
}: ReportCoverProps) {
  const t = useLocal(time, from);
  const cardIn = inRamp(t, 0.02, 0.32);
  const cardScale = lerp(0.985, 1, easeOutQuint(prog(t, 0.02, 0.4)));
  const headIn = inRamp(t, 0.16, 0.3);
  const rule1 = easeOutCubic(prog(t, 0.24, 0.6));
  const titleIn = easeOutCubic(prog(t, 0.3, 0.66));
  const rule2 = easeOutCubic(prog(t, 0.5, 0.86));
  const metaIn = inRamp(t, 0.56, 0.32);
  const stampHit = easeOutQuint(prog(t, 0.78, 1.02));
  const stampBleed = clamp((t - 0.82) / 0.9);

  // split the report title at the year so two lines read as a document
  const idx = title.indexOf('中国汽车');
  const line1 = idx > 0 ? title.slice(0, idx).trim() : title;
  const line2 = idx > 0 ? title.slice(idx) : '';

  return (
    <GFXLayer>
      <Box
        x={0}
        y={0}
        w={0}
        h={0}
        alpha={1}
        style={{ transform: `translateY(${lerp(22, 0, cardIn)}px)` }}
      >
        <Paper x={556} y={206} w={808} h={664} rot={-1.2} opacity={cardIn}>
          <CornerTicks x={26} y={26} w={756} h={612} color={C.ink} alpha={0.26} size={18} />
          {/* header */}
          <Txt
            text="中国汽车流通协会"
            x={64}
            y={56}
            size={22}
            font="sans"
            color={C.inkSoft}
            alpha={0.75 * headIn}
            track={4}
          />
          <Txt
            text="CHINA AUTOMOBILE DEALERS ASSOCIATION"
            x={64}
            y={90}
            size={12}
            font="mono"
            color={C.inkSoft}
            alpha={0.45 * headIn}
            track={2}
          />
          <Txt text={exhibit} x={744} y={58} size={15} font="mono" color={C.inkSoft} alpha={0.6 * headIn} track={2} align="right" />
          <Rule x={64} y={122} w={680} h={2} color={C.red} alpha={0.8} progress={rule1} />
          {/* report title */}
          <Txt
            text={line1}
            x={64}
            y={168}
            size={64}
            font="serif"
            color={C.ink}
            alpha={0.97 * titleIn}
            track={2}
            weight={700}
            style={{ clipPath: `inset(0% ${(1 - titleIn) * 100}% 0% 0%)` }}
          />
          <Txt
            text={line2}
            x={64}
            y={248}
            size={64}
            font="serif"
            color={C.ink}
            alpha={0.97 * easeOutCubic(prog(t, 0.38, 0.74))}
            track={2}
            weight={700}
            style={{ clipPath: `inset(0% ${(1 - easeOutCubic(prog(t, 0.38, 0.74))) * 100}% 0% 0%)` }}
          />
          <Txt
            text="三年保值率 / 二手车残值"
            x={64}
            y={344}
            size={24}
            font="mono"
            color={C.inkSoft}
            alpha={0.7 * metaIn}
            track={3}
          />
          <Rule x={64} y={392} w={680} h={1} color={C.ink} alpha={0.3} progress={rule2} />
          {/* meta block */}
          <Box x={64} y={0} w={0} h={0} alpha={metaIn}>
            <Txt text="发布日期" x={0} y={428} size={18} font="sans" color={C.inkSoft} alpha={0.65} track={2} />
            <Txt text={date} x={0} y={458} size={40} font="mono" color={C.ink} track={1} />
            <Txt text="发布机构" x={0} y={528} size={18} font="sans" color={C.inkSoft} alpha={0.65} track={2} />
            <Txt text={publisher} x={0} y={558} size={30} font="sans" color={C.ink} track={2} />
            <Txt text="报告口径 · 2026 年 10 月" x={0} y={606} size={16} font="mono" color={C.inkSoft} alpha={0.5} track={1} />
          </Box>
          <Txt text="数据来源：中国汽车流通协会公开发布" x={64} y={622} size={14} font="mono" color={C.inkSoft} alpha={0.5} track={1} />
          {/* stamp */}
          <SealMark
            x={624}
            y={520}
            size={188}
            text={stamp}
            rot={-9}
            color={C.red}
            hit={stampHit}
            bleed={stampBleed}
            blend
          />
        </Paper>
      </Box>

      <Kicker text="报告 · 2026.11.10" x={168} y={312} alpha={0.55 * headIn} track={5} />
      <MetaRow left="CASE FILE · EP07 / 报告封面" right="EXHIBIT 02 · 数据来源页" y={200} alpha={0.34} />
      <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.12} size={16} />
      {source ? (
        <Txt text={source} x={168} y={898} size={16} font="mono" color={C.paper} alpha={0.36 * inRamp(t, 0.9, 0.4)} track={1} />
      ) : null}
      <Speckles x={0} y={132} w={1920} h={816} seed={811} count={18} maxAlpha={0.05} />
    </GFXLayer>
  );
}
