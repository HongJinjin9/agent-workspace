// 第 07 期图形层入口（mh-graphics 所有）
// 普通 React 组件 + 纯时间函数；mh-motion 在合成树里挂 <GraphicsLayer time={time} />，
// 它读取 src/data/graphics_cues.json，在各自窗口内挂载对应块（3D/H3 之上、chrome/字幕之下）。
import './graphics.css';
import type { ComponentType } from 'react';
import cuesData from '../data/graphics_cues.json';

import { TitleHook } from './title_hook';
import { ReportCover } from './report_cover';
import { BigNumber } from './big_number';
import { NumberStack } from './number_stack';
import { CategoryBars } from './category_bars';
import { BrandMatrix } from './brand_matrix';
import { PriceTag } from './price_tag';
import { RankingBoard } from './ranking_board';
import { RedAnnotation } from './red_annotation';
import { Stamp } from './stamp';
import { PaperSheetBlock } from './paper_sheet';
import { PaperSheet } from './paper_sheet';
import { Statement } from './statement';
import { SectionLabel } from './section_label';
import { EndCard } from './end_card';
import { LedgerBooks } from './ledger_books';
import { TechParams } from './tech_params';
import { CompareBars } from './compare_bars';
import { DepreciationCurve } from './depreciation_curve';
import { SplitScreen } from './split_screen';

export { TitleHook, ReportCover, BigNumber, NumberStack, CategoryBars, BrandMatrix, PriceTag, RankingBoard, RedAnnotation, Stamp, PaperSheetBlock, PaperSheet, Statement, SectionLabel, EndCard, LedgerBooks, TechParams, CompareBars, DepreciationCurve, SplitScreen };
export type { TitleHookProps } from './title_hook';
export type { ReportCoverProps } from './report_cover';
export type { BigNumberProps, CompareTick } from './big_number';
export type { NumberStackProps } from './number_stack';
export type { CategoryBarsProps } from './category_bars';
export type { BrandMatrixProps } from './brand_matrix';
export type { PriceTagProps } from './price_tag';
export type { RankingBoardProps } from './ranking_board';
export type { RedAnnotationProps } from './red_annotation';
export type { StampProps } from './stamp';
export type { PaperSheetProps } from './paper_sheet';
export type { PaperSheetBlockProps } from './paper_sheet';
export type { StatementProps } from './statement';
export type { SectionLabelProps } from './section_label';
export type { EndCardProps } from './end_card';
export type { LedgerBooksProps } from './ledger_books';
export type { TechParamsProps } from './tech_params';
export type { CompareBarsProps } from './compare_bars';
export type { DepreciationCurveProps } from './depreciation_curve';
export type { SplitScreenProps } from './split_screen';
export * from './prims';

export interface GraphicCue {
  id: string;
  block: string;
  from: number;
  to: number;
  seg?: string;
  props?: { headline?: string | null; sub?: string | null; h3?: string | null; space?: string | null } & Record<string, unknown>;
}

export interface CuesFile {
  cues: GraphicCue[];
}

/** block registry used by GraphicsLayer */
export const GRAPHICS: Record<string, ComponentType<any>> = {
  title_hook: TitleHook,
  report_cover: ReportCover,
  big_number: BigNumber,
  count_up: BigNumber,
  number_stack: NumberStack,
  category_bars: CategoryBars,
  brand_matrix: BrandMatrix,
  price_tag: PriceTag,
  ranking_board: RankingBoard,
  red_annotation: RedAnnotation,
  stamp: Stamp,
  paper_sheet: PaperSheetBlock,
  statement: Statement,
  section_label: SectionLabel,
  end_card: EndCard,
  ledger_books: LedgerBooks,
  three_books: LedgerBooks,
  tech_params: TechParams,
  compare_bars: CompareBars,
  depreciation_curve: DepreciationCurve,
  split_screen: SplitScreen,
};

const C_compare = '#e9e4d8';

/** normalized copy comparison — hides a subtitle that merely repeats the headline */
function normCopy(v: unknown): string {
  return String(v ?? '').replace(/[\s，。、：；！？·…—\-\/|()（）「」“”"']/g, '').toLowerCase();
}
function dedupeSub(p: { headline?: unknown; sub?: unknown }): string | undefined {
  const h = normCopy(p.headline);
  const s = normCopy(p.sub);
  if (!s) return undefined;
  if (h && (h === s || h.includes(s) || s.includes(h))) return undefined;
  return String(p.sub);
}

function numFrom(v: unknown): number | undefined {
  const n = parseFloat(String(v ?? '').replace(/[^\d.]/g, ''));
  return Number.isFinite(n) ? n : undefined;
}

function renderCue(cue: GraphicCue, time: number) {
  const Comp = GRAPHICS[cue.block];
  if (!Comp) return null;
  const p = cue.props ?? {};
  const common = { key: cue.id, time, from: cue.from, to: cue.to, seg: cue.seg, id: cue.id, exhibit: cue.id };
  if (cue.block === 'big_number' || cue.block === 'count_up') {
    const rawSub = String(p.sub ?? '').trim();
    const label = (p.label as string) ?? (p.headline as string) ?? '';
    if (rawSub === '?' || rawSub === '？') {
      return <Comp {...common} label={label} question />;
    }
    const vs = rawSub.match(/(\d+(?:\.\d+)?)\s*(?:%|万)?\s*(?:vs|VS|比)\s*(\d+(?:\.\d+)?)/);
    const v = (p.value as number | undefined) ?? numFrom(rawSub);
    let suffix = (p.suffix as string | undefined) ?? '';
    let decimals = (p.decimals as number | undefined);
    if (!suffix) {
      if (rawSub.includes('%')) suffix = rawSub.includes('%+') ? '%+' : '%';
      else if (rawSub.includes('万')) suffix = ' 万';
      else if (rawSub.endsWith('+')) suffix = '+';
      else suffix = '';
    }
    if (decimals == null) decimals = Number.isInteger(v ?? 0) ? 0 : 1;
    const wantCompare = p.compare === true || !!vs || /插混/.test(String(p.headline ?? ''));
    const compare = wantCompare
      ? vs
        ? [{ value: parseFloat(vs[2]), label: `另一边 ${parseFloat(vs[2])}${suffix || '%'}`, color: C_compare }]
        : [{ value: 45.1, label: '纯电 45.1%', color: C_compare }]
      : undefined;
    const gauge = p.gauge !== false;
    return (
      <Comp
        {...common}
        label={label}
        value={v}
        suffix={suffix}
        decimals={decimals}
        compare={compare}
        gauge={gauge}
        colorChoice={(p.color as string | undefined) ?? undefined}
        note={(p.note as string | undefined) ?? undefined}
      />
    );
  }
  if (cue.block === 'title_hook') {
    // hook copy is data-driven inside the block (FACTS); don't let cue.sub override the film subtitle
    return <Comp {...common} />;
  }
  if (cue.block === 'report_cover' || cue.block === 'end_card') {
    return <Comp {...common} />;
  }
  if (cue.block === 'ledger_books' || cue.block === 'three_books') {
    return (
      <Comp
        {...common}
        index={(p.index as number | undefined) ?? 1}
        label={(p.label as string | undefined) ?? undefined}
        headline={(p.headline as string) ?? ''}
        sub={(p.sub as string) ?? undefined}
      />
    );
  }
  if (cue.block === 'tech_params') {
    return <Comp {...common} items={(p.items as string[] | undefined) ?? undefined} mode={(p.mode as 'flash' | 'compare' | undefined) ?? 'flash'} headline={(p.headline as string) ?? ''} sub={(p.sub as string) ?? undefined} />;
  }
  if (cue.block === 'compare_bars') {
    return <Comp {...common} items={(p.items as any) ?? undefined} max={(p.max as number | undefined) ?? 60} headline={(p.headline as string) ?? ''} sub={(p.sub as string) ?? undefined} />;
  }
  if (cue.block === 'depreciation_curve') {
    return <Comp {...common} headline={(p.headline as string) ?? ''} sub={(p.sub as string) ?? undefined} start={(p.start as number | undefined) ?? undefined} end={(p.end as number | undefined) ?? undefined} />;
  }
  if (cue.block === 'split_screen') {
    return <Comp {...common} headline={(p.headline as string) ?? ''} leftTitle={(p.leftTitle as string | undefined) ?? undefined} rightTitle={(p.rightTitle as string | undefined) ?? undefined} />;
  }
  if (cue.block === 'brand_matrix') {
    return (
      <Comp
        {...common}
        headline={(p.headline as string) ?? ''}
        sub={dedupeSub(p as { headline?: unknown; sub?: unknown })}
        groups={(p.groups as any) ?? undefined}
        title={(p.title as string | undefined) ?? undefined}
        mode={(p.mode as 'rise' | 'fall' | 'matrix' | undefined) ?? undefined}
      />
    );
  }
  if (cue.block === 'ranking_board') {
    return (
      <Comp
        {...common}
        headline={(p.headline as string) ?? ''}
        sub={dedupeSub(p as { headline?: unknown; sub?: unknown })}
        rows={(p.rows as any) ?? undefined}
        title={(p.title as string | undefined) ?? undefined}
        compareWith={(p.compareWith as string | undefined) ?? undefined}
      />
    );
  }
  if (cue.block === 'category_bars') {
    const items = p.items as Array<{ label: string; value: number; highlight?: boolean }> | undefined;
    if (items && items.length) {
      return <CompareBars {...common} items={items} max={(p.max as number | undefined) ?? 70} unit="%" headline={(p.headline as string) ?? ''} sub={(p.sub as string) ?? undefined} />;
    }
    const rawSub = String(p.sub ?? '');
    if (/%/.test(rawSub)) {
      return (
        <CompareBars
          {...common}
          items={[{ label: (p.headline as string) ?? '', value: numFrom(rawSub) ?? 0, highlight: true }]}
          max={60}
          headline={(p.headline as string) ?? ''}
          sub={(p.sub as string) ?? undefined}
        />
      );
    }
    return <CategoryBars {...common} headline={(p.headline as string) ?? ''} sub={(p.sub as string) ?? undefined} />;
  }
  if (cue.block === 'compare_bars') {
    let items = p.items as Array<{ label: string; value: number; highlight?: boolean }> | undefined;
    if (!items || !items.length) {
      const h = String(p.headline ?? '');
      if (/MPV/.test(h) && /小型车/.test(h)) {
        items = [
          { label: 'MPV', value: 48.7 },
          { label: '小型车', value: 48.3 },
        ];
      } else if (/中大型/.test(h) && /MPV/.test(h)) {
        items = [
          { label: '中大型 SUV', value: 50.6, highlight: true },
          { label: 'MPV', value: 48.7 },
        ];
      }
    }
    return <CompareBars {...common} items={items} max={(p.max as number | undefined) ?? 60} unit={(p.unit as string | undefined) ?? '%'} headline={(p.headline as string) ?? ''} sub={dedupeSub(p as { headline?: unknown; sub?: unknown })} />;
  }
  if (cue.block === 'number_stack') {
    return <Comp {...common} headline={(p.headline as string) ?? ''} sub={(p.sub as string) ?? undefined} variant={(p.variant as string | undefined) ?? undefined} />;
  }
  if (cue.block === 'price_tag') {
    return <Comp {...common} headline={(p.headline as string) ?? ''} sub={(p.sub as string) ?? undefined} />;
  }
  return <Comp {...common} headline={(p.headline as string) ?? ''} sub={dedupeSub(p as { headline?: unknown; sub?: unknown })} />;
}

const DEFAULT_CUES: GraphicCue[] = ((cuesData as CuesFile)?.cues ?? []).slice();

/**
 * mh-motion integration contract: `<GraphicsLayer time={time} />`.
 * Renders exactly the graphic block(s) whose cue window contains `time`.
 * `cues` can be overridden for previews/tests.
 */
export function GraphicsLayer({ time, cues = DEFAULT_CUES }: { time: number; cues?: GraphicCue[] }) {
  return (
    <>
      {cues.map((cue) => {
        if (time < cue.from || time >= cue.to) return null;
        return renderCue(cue, time);
      })}
    </>
  );
}

export default GraphicsLayer;
