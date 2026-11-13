// footage 模块：复用素材池里的 <video>（muted/preload=auto/playsInline），
// 按 target = shot.in + t*rate 定位（clamp 到素材时长），await seek 完成。
// look: "cool" 冷灰案卷 / "warm" 暖金档案。
import { clamp } from '../core/util.js';

const SEEK_EPS = 1e-3;

// 基础调色（叠在 CSS 调色层之下）：冷灰 / 暖金
const LOOK_FILTER = {
  cool: 'saturate(0.78) contrast(1.08) brightness(0.9)',
  warm: 'saturate(1.02) contrast(1.04) brightness(0.95) sepia(0.16)',
};

function gradeClass(look) {
  return look === 'warm' ? 'mh-grade-warm' : 'mh-grade-cool';
}

export function mountFootage({ el, shot, theme, assets }) {
  el.innerHTML = '';
  const grade = document.createElement('div');
  grade.className = `mh-grade ${gradeClass(shot.look)}`;
  el.append(grade);

  let handle = null;
  let destroyed = false;
  let video = null;

  const ready = assets.video(shot.asset).then((h) => {
    if (destroyed) return;
    handle = h;
    video = h.element;
    video.classList.add('mh-video');
    video.style.filter = LOOK_FILTER[shot.look === 'warm' ? 'warm' : 'cool'];
    el.insertBefore(video, grade);
    return h;
  });

  function targetTime(t) {
    const source = (Number(shot.in) || 0) + Math.max(0, t) * (Number(shot.rate) || 1);
    const duration = video && Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 0;
    return duration ? Math.min(source, Math.max(0, duration - 0.04)) : Math.max(0, source);
  }

  return {
    async update(t) {
      await ready;
      if (!handle || destroyed) return;
      const target = targetTime(t);
      const current = video.currentTime;
      if (!video.seeking && Math.abs(current - target) <= SEEK_EPS) return;
      await handle.prepareFrame(target);
    },
    dispose() {
      destroyed = true;
      if (video) {
        try {
          video.pause();
        } catch {
          /* noop */
        }
        video.remove();
      }
      grade.remove();
    },
  };
}
