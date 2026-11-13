// 第 06 期 · MotionHarness 入口（mh-motion）
// 数据驱动：src/data/shots.json（46 镜）、srt.json（72 条字幕）、overlays.json（9 个叠加事件）。
// 画面只依赖项目时间，prepareFrame 可重复 / 回退 / 跳帧。
import './style.css';
import shots from './data/shots.json';
import cues from './data/srt.json';
import overlayEvents from './data/overlays.json';
import { THEME } from './theme.js';
import { FACTS, DECLARATIONS, HUMAN_LINE } from './data/facts.js';
import { helpers } from './core/helpers.js';
import { createEngine } from './core/engine.js';
import { mountGraphic } from './graphics/index.js';
import { mountOverlay } from './graphics/overlays.js';

export default function ({ root, width, height, pixelRatio, media }) {
  return createEngine({
    root,
    width,
    height,
    pixelRatio,
    media,
    theme: THEME,
    facts: { FACTS, DECLARATIONS, HUMAN_LINE },
    data: { shots, cues, overlayEvents, helpers },
    mountGraphic,
    mountOverlay,
  });
}
