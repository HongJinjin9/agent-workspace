// ep07 合成入口：3D 世界（ThreeCanvas）→ H3 证据影像 → 图形/排版层 → chrome → 字幕
import { useMemo } from 'react';
import { ThreeCanvas } from '@motionharness/sdk/three';
import shots from './data/shots.json';
import type { Shot } from './data/types';
import { findShot } from './three/math';
import { World } from './three/World';
import { Chrome } from './layers/Chrome';
import { Subtitles } from './layers/Subtitles';
import { FootageLayer } from './layers/FootageLayer';
import { GraphicsLayer } from './graphics/index';
import { LowerThird } from './layers/LowerThird';
import './style.css';

export interface StageValues {
  background: string;
  h3Opacity: number;
  grainStrength: number;
  subtitles: boolean;
}

export function Stage({ time, values }: { time: number; values: StageValues }) {
  const list = shots as Shot[];
  const shot = useMemo(() => findShot(list, time), [time]);
  // Plan-B：H3 全幅镜头用极简 lower-third；纯 3D/排版镜头才挂图形层（片头/榜单/片尾）
  const h3Fill = shot.h3mode === 'fill';
  return (
    <div className="ep07-root" style={{ background: values.background }}>
      <div className="ep07-3d">
        <ThreeCanvas width={1920} height={1080} camera={{ fov: 34, near: 0.04, far: 260, position: [0, 1.3, 0.6] }}>
          <World time={time} shot={shot} />
        </ThreeCanvas>
      </div>
      <FootageLayer time={time} shot={shot} opacity={values.h3Opacity} />
      {/* 合成压暗层：H3 全幅只压底部/左侧保证字幕与 lower-third 可读；3D/排版镜头压成暗场 */}
      <div className={h3Fill ? 'ep07-scrim ep07-scrim-h3' : 'ep07-scrim'} />
      {/* 图形/排版层（mh-graphics，仅纯 3D 镜头：S01 片头 / S37-38 榜单 / S50 片尾） */}
      {h3Fill ? <LowerThird shot={shot} time={time} /> : <GraphicsLayer time={time} />}
      <Chrome time={time} shot={shot} strength={values.grainStrength} />
      {values.subtitles ? <Subtitles time={time} /> : null}
    </div>
  );
}
