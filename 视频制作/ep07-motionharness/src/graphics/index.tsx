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

export { TitleHook, ReportCover, BigNumber, NumberStack, CategoryBars, BrandMatrix, PriceTag, RankingBoard, RedAnnotation, Stamp, PaperSheetBlock, PaperSheet, Statement, SectionLabel, EndCard };
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
};

function numFrom(v: unknown): number | undefined {
  const n = parseFloat(String(v ?? '').replace(/[^\d.]/g, ''));
  return Number.isFinite(n) ? n : undefined;
}

function renderCue(cue: GraphicCue, time: number) {
  const Comp = GRAPHICS[cue.block];
  if (!Comp) return null;
  const p = cue.props ?? {};
  const common = { key: cue.id, time, from: cue.from, to: cue.to, seg: cue.seg, id: cue.id, exhibit: cue.id };
  if (cue.block === 'big_number') {
    return <Comp {...common} label={(p.headline as string) ?? ''} value={numFrom(p.sub)} />;
  }
  if (cue.block === 'title_hook') {
    // hook copy is data-driven inside the block (FACTS); don't let cue.sub override the film subtitle
    return <Comp {...common} />;
  }
  if (cue.block === 'report_cover' || cue.block === 'end_card') {
    return <Comp {...common} />;
  }
  return <Comp {...common} headline={(p.headline as string) ?? ''} sub={(p.sub as string) ?? undefined} />;
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
