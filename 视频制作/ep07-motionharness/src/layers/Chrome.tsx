// DOM chrome：2.35:1 遮幅（132px 纯黑上下条）+ 暗角 + 胶片颗粒 + 幕标签
// 颗粒用静态 SVG turbulence（确定性）；时间只影响幕标签与微光。
import { THEME } from '../data/theme';
import type { Shot } from '../data/types';

const GRAIN_URI =
  'url("data:image/svg+xml;utf8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter><rect width="240" height="240" filter="url(#n)" opacity="0.5"/></svg>',
  ) +
  '")';

export function Chrome({ time, shot, strength = 1 }: { time: number; shot: Shot; strength?: number }) {
  const bar = THEME.letterbox;
  return (
    <>
      {/* 内容区装饰：暗角 / 颗粒 / 顶底柔边（不覆盖遮幅） */}
      <div className="ep07-chrome-content">
        <div className="ep07-vignette" />
        <div className="ep07-grain" style={{ opacity: 0.16 * strength, backgroundImage: GRAIN_URI }} />
        <div className="ep07-edge ep07-edge-top" />
        <div className="ep07-edge ep07-edge-bottom" />
      </div>
      {/* 遮幅（纯黑） */}
      <div className="ep07-bar" style={{ top: 0, height: bar }} />
      <div className="ep07-bar" style={{ bottom: 0, height: bar }} />
      {/* 顶部/底部遮幅保持纯黑：品牌与幕语境由图形层 section_label 承担，避免双重标题 */}
    </>
  );
}
