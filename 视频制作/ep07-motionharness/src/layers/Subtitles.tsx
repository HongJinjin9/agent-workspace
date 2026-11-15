// DOM 字幕层：单条活动 cue，切口处直接显示，空隙处 0.12s 淡入淡出，绝不重叠。
import srt from '../data/srt.json';
import { THEME } from '../data/theme';

interface Cue { start: number; end: number; text: string; }
const cues = srt as Cue[];
const FADE = 0.12;
const CONTIGUOUS = 0.06;

function activeIndex(t: number) {
  let lo = 0, hi = cues.length - 1, found = -1;
  while (lo <= hi) { const mid = (lo + hi) >> 1; if (cues[mid].start <= t + 1e-9) { found = mid; lo = mid + 1; } else hi = mid - 1; }
  return found >= 0 && t < cues[found].end ? found : -1;
}

export function Subtitles({ time }: { time: number }) {
  // 片尾声明段（198.4s 起）由 end_card 排版承载，字幕层静默，避免双重文字
  if (time >= 198.35) return null;
  const i = activeIndex(time);
  let text = '';
  let opacity = 0;
  if (i >= 0) {
    const cue = cues[i];
    const prev = cues[i - 1];
    const next = cues[i + 1];
    const gapIn = prev ? cue.start - prev.end : 1;
    const gapOut = next ? next.start - cue.end : 1;
    let o = 1;
    if (gapIn > CONTIGUOUS) o = Math.min(o, Math.max(0, Math.min(1, (time - cue.start) / FADE)));
    if (gapOut > CONTIGUOUS) o = Math.min(o, Math.max(0, Math.min(1, (cue.end - time) / FADE)));
    text = cue.text; opacity = o;
  } else {
    // 刚结束的 cue 淡出
    let j = -1;
    for (let k = cues.length - 1; k >= 0; k--) { if (cues[k].end <= time) { j = k; break; } }
    if (j >= 0) {
      const cue = cues[j];
      const after = time - cue.end;
      if (after >= 0 && after < FADE) { text = cue.text; opacity = 1 - after / FADE; }
    }
  }
  if (!text || opacity <= 0.001) return null;
  return (
    <div className="ep07-sub-box">
      <div className="ep07-sub-text" style={{ opacity, fontFamily: THEME.font.sans }}>{text}</div>
    </div>
  );
}
