// EP07 v2 合成入口：3D 评估室背景（暗场）→ H3 强关联证据影像（带运镜处理）→ 压暗/局部 scrim
// → 图形排版层（motion-graphics 主视觉，data/split/end 镜头）或 H3 镜头的动态 lower-third → chrome → 字幕。
import { useMemo } from 'react';
import { ThreeCanvas } from '@motionharness/sdk/three';
import shots from './data/shots.json';
import cuesData from './data/graphics_cues.json';
import type { Shot } from './data/types';
import { findShot } from './three/math';
import { World } from './three/World';
import { Chrome } from './layers/Chrome';
import { Subtitles } from './layers/Subtitles';
import { FootageLayer } from './layers/FootageLayer';
import { LowerThird } from './layers/LowerThird';
import { GraphicsLayer, GRAPHICS, type GraphicCue } from './graphics/index';
import './style.css';

const RAW_CUES = ((cuesData as { cues?: GraphicCue[] }).cues ?? []) as GraphicCue[];
// Phase-2 块未落地时用现有块兜底，保证预览/渲染不出现空镜（块一到自动切换，无需改数据）
const FALLBACK: Record<string, string> = {
  ledger_books: 'paper_sheet', three_books: 'paper_sheet',
  tech_params: 'statement', compare_bars: 'category_bars',
  depreciation_curve: 'number_stack', split_screen: 'statement',
};
const CUES: GraphicCue[] = RAW_CUES.map((c) => {
  const registered = (GRAPHICS as Record<string, unknown>)[c.block];
  const fallback = FALLBACK[c.block];
  return registered || !fallback ? c : { ...c, block: fallback };
});

export interface StageValues {
  background: string;
  h3Opacity: number;
  grainStrength: number;
  subtitles: boolean;
}

function worldShotOf(shot: Shot): Shot {
  return { ...shot, motion: (shot.spaceMotion ?? 'slow') as Shot['spaceMotion'] } as Shot;
}

export function Stage({ time, values }: { time: number; values: StageValues }) {
  const list = shots as unknown as Shot[];
  const shot = useMemo(() => findShot(list, time), [time]);
  const isGraphics = shot.kind === 'data' || shot.kind === 'split' || shot.kind === 'end';
  const hasH3 = shot.kind === 'h3' || shot.kind === 'split';
  return (
    <div className="ep07-root" style={{ background: values.background }}>
      <div className="ep07-3d">
        <ThreeCanvas width={1920} height={1080} camera={{ fov: 34, near: 0.04, far: 260, position: [0, 1.3, 0.6] }}>
          <World time={time} shot={worldShotOf(shot)} bare={isGraphics} />
        </ThreeCanvas>
      </div>
      {hasH3 ? <FootageLayer time={time} shot={shot} opacity={values.h3Opacity} /> : null}
      {/* H3 全幅镜头只压底部/左侧；图形镜头把 3D 压成暗场，让排版成为第一视觉 */}
      <div className={hasH3 ? 'ep07-scrim ep07-scrim-h3' : 'ep07-scrim'} />
      {isGraphics ? <GraphicsLayer time={time} cues={CUES} /> : <LowerThird shot={shot} time={time} />}
      <Chrome time={time} shot={shot} strength={values.grainStrength} />
      {values.subtitles ? <Subtitles time={time} shot={shot} /> : null}
    </div>
  );
}
