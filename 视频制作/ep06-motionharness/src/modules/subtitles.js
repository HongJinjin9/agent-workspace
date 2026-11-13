// subtitles 层：srt.json -> 底部 48px 字幕（同一时刻最多一条，绝不重叠）。
// 连续讲话（cue 首尾相接）直接换字不闪；有间隙时 0.12s 淡入 / 淡出。
import { findCueIndex } from '../core/timeline.js';
import { clamp } from '../core/util.js';

const FADE = 0.12;
const CONTIGUOUS = 0.05; // 相邻 cue 间隙小于该值视为连续
const CUT_EPS = 0.03; // cue 起点距镜头切点小于该值视为“硬切同步”

export function mountSubtitles({ el: layer, width, height, theme, cues, cuts = [] }) {
  const sortedCuts = [...cuts].sort((a, b) => a - b);

  function nearCut(t) {
    let lo = 0;
    let hi = sortedCuts.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (sortedCuts[mid] < t - CUT_EPS) lo = mid + 1;
      else if (sortedCuts[mid] > t + CUT_EPS) hi = mid - 1;
      else return true;
    }
    return false;
  }
  layer.innerHTML = '';
  const box = document.createElement('div');
  box.className = 'mh-sub-box';
  const text = document.createElement('div');
  text.className = 'mh-sub-text';
  text.style.fontFamily = theme.font.sans;
  box.append(text);
  layer.append(box);

  let current = -1;
  let lastText = null;
  let lastOpacity = -1;
  let visible = null;

  function setVisible(on) {
    if (visible === on) return;
    visible = on;
    box.style.visibility = on ? 'visible' : 'hidden';
  }

  function setText(value) {
    if (value === lastText) return;
    lastText = value;
    text.textContent = value;
  }

  function setOpacity(value) {
    if (Math.abs(value - lastOpacity) <= 0.002) return;
    lastOpacity = value;
    text.style.opacity = value.toFixed(3);
  }

  function update(t) {
    const i = findCueIndex(cues, t);
    if (i >= 0) {
      const cue = cues[i];
      if (i !== current) {
        setText(cue.text);
        current = i;
      }
      const prev = cues[i - 1];
      const next = cues[i + 1];
      const gapIn = prev ? cue.start - prev.end : 1;
      const gapOut = next ? next.start - cue.end : 1;
      let opacity = 1;
      if (gapIn > CONTIGUOUS && !nearCut(cue.start)) {
        opacity = Math.min(opacity, clamp((t - cue.start) / FADE));
      }
      if (gapOut > CONTIGUOUS) opacity = Math.min(opacity, clamp((cue.end - t) / FADE));
      setVisible(true);
      setOpacity(opacity);
      return;
    }

    // 无活动 cue：若上一条刚结束（<FADE 内的间隙），做淡出。
    const cue = current >= 0 ? cues[current] : null;
    if (cue && t >= cue.start) {
      const after = t - cue.end;
      if (after >= 0 && after < FADE) {
        setText(cue.text);
        setVisible(true);
        setOpacity(1 - after / FADE);
        return;
      }
    }
    if (cue && t < cue.start) {
      current = -1;
    }
    setVisible(false);
    setOpacity(0);
  }

  function dispose() {
    layer.innerHTML = '';
  }

  return { update, dispose };
}
