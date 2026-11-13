// still 模块：<img> 静帧 + camera 变换（camera 由引擎应用在 .mh-cam 上）。
// 图片惰性加载（挂载时创建 <img>，host 在 prepareFrame 后统一等待 decode）。
import { stillUrl } from '../core/assets.js';

export function mountStill({ el, shot, theme, assets }) {
  el.innerHTML = '';
  const img = document.createElement('img');
  img.className = 'mh-still';
  img.loading = 'eager';
  img.decoding = 'async';
  img.draggable = false;
  img.alt = shot.caption || shot.id;
  img.src = assets ? assets.stillUrl(shot.asset) : stillUrl(shot.asset);
  img.style.opacity = '1';
  img.style.filter = shot.look === 'warm'
    ? 'saturate(1.02) contrast(1.04) brightness(0.95) sepia(0.16)'
    : 'saturate(0.8) contrast(1.06) brightness(0.92)';

  const grade = document.createElement('div');
  grade.className = `mh-grade ${shot.look === 'warm' ? 'mh-grade-warm' : 'mh-grade-cool'}`;

  el.append(img, grade);

  return {
    update() {
      /* 静帧无时间相关更新；camera 在引擎 wrapper 上 */
    },
    dispose() {
      img.remove();
      grade.remove();
    },
  };
}
