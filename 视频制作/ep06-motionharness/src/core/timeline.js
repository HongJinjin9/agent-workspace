// 时间轴索引：镜头二分查找、字幕活动 cue、叠加层活动事件。
// 所有函数都是时间的纯函数（支持重复 / 回退 / 跳帧 seek）。

/** 最后一个 start <= t 的下标（不存在返回 -1）。 */
function lastAtOrBefore(items, t) {
  let lo = 0;
  let hi = items.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (items[mid].start <= t + 1e-9) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return found;
}

/**
 * 当前镜头。跳过零时长镜头（data 里 a3_year dur=0），保证帧时间始终落在可播放镜头上。
 */
export function findShotIndex(shots, t) {
  if (!shots.length) return -1;
  const last = shots[shots.length - 1];
  const time = Math.min(Math.max(0, t), Math.max(0, last.end - 1e-6));
  let i = lastAtOrBefore(shots, time);
  if (i < 0) i = 0;
  // 前跳零时长镜头
  while (i < shots.length - 1 && shots[i].dur <= 0) i++;
  // 若跳到末尾之后，回退到最后一个有时长的镜头
  let guard = shots.length;
  while (i > 0 && (shots[i].dur <= 0 || shots[i].start > time + 1e-9) && guard-- > 0) i--;
  while (i < shots.length - 1 && shots[i].dur <= 0) i++;
  return i;
}

/** 活动字幕 cue：start <= t < end。没有返回 -1。 */
export function findCueIndex(cues, t) {
  const i = lastAtOrBefore(cues, t);
  if (i < 0) return -1;
  return t < cues[i].end ? i : -1;
}

/** 活动叠加事件（返回事件下标数组，按 at 排序）。 */
export function findActiveOverlays(overlays, t) {
  const active = [];
  for (let i = 0; i < overlays.length; i++) {
    const e = overlays[i];
    if (t >= e.at - 1e-9 && t < e.at + e.dur) active.push(i);
  }
  return active;
}
