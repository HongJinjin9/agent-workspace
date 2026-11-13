// MotionHarness 引擎（mh-motion）：全局时间 -> 分层 DOM 的确定性画面。
//
// 层级（自下而上）：
//   #stage      当前镜头（footage / still / graphic），内含 camera 变换的 .mh-cam
//   #overlays   时间轴叠加事件（印章 / 记分 / 标签），按事件挂载、销毁
//   #chrome     2.35:1 遮幅、暗角、胶片颗粒、镜头 caption/证据角标、幕标签、时间码
//   #subtitles  srt.json 底部字幕（同一时刻最多一条）
//
// prepareFrame(globalT) 幂等、可回退/跳帧：镜头二分开址、硬切、await 视频 seek。

import { createAssetPool } from './assets.js';
import { cameraTransform } from './camera.js';
import { findShotIndex, findCueIndex, findActiveOverlays } from './timeline.js';
import { clamp, frameAt } from './util.js';
import { mountFootage } from '../modules/footage.js';
import { mountStill } from '../modules/still.js';
import { mountChrome } from '../modules/chrome.js';
import { mountSubtitles } from '../modules/subtitles.js';

const PRELOAD_FOOTAGE = 1.5; // 距切点 <1.5s 时预热下一个 footage 镜头
const PRELOAD_STILL = 1.5;

function div(className, parent) {
  const el = document.createElement('div');
  el.className = className;
  if (parent) parent.append(el);
  return el;
}

export function createEngine({
  root,
  width,
  height,
  media,
  data,
  theme,
  facts,
  mountGraphic,
  mountOverlay,
}) {
  const { shots, cues, overlayEvents } = data;
  const assets = createAssetPool(media);

  const wrap = div('mh-root');
  const stage = div('mh-layer mh-stage', wrap);
  stage.id = 'stage';
  const overlaysLayer = div('mh-layer mh-overlays', wrap);
  overlaysLayer.id = 'overlays';
  const chromeLayer = div('mh-layer mh-chrome', wrap);
  chromeLayer.id = 'chrome';
  const subtitlesLayer = div('mh-layer mh-subtitles', wrap);
  subtitlesLayer.id = 'subtitles';
  root.append(wrap);

  const chrome = mountChrome({ el: chromeLayer, width, height, theme });
  const subtitles = mountSubtitles({
    el: subtitlesLayer,
    width,
    height,
    theme,
    cues,
    // 镜头切点：恰好落在硬切上的字幕直接显示（不淡入），避免切点首帧字幕不可见。
    cuts: shots.filter((shot) => shot.dur > 0).map((shot) => shot.start),
  });

  const mountedOverlays = new Map(); // eventIndex -> { el, mod }
  let active = null; // { idx, shot, el, camEl, mod, asset }
  let disposed = false;
  const warned = new Set();

  function warnOnce(key, error) {
    if (warned.has(key)) return;
    warned.add(key);
    // eslint-disable-next-line no-console
    console.warn(`[mh] ${key}:`, error);
  }

  function graphicCtx(shot, el) {
    return { el, width, height, shot, theme, facts, helpers: data.helpers };
  }

  function mountGraphicSafe(shot, camEl) {
    const ctx = graphicCtx(shot, camEl);
    let mod;
    try {
      mod = mountGraphic(shot.asset, ctx);
      if (!mod || typeof mod.update !== 'function') throw new Error('mountGraphic returned no update()');
    } catch (error) {
      warnOnce(`graphic:${shot.asset}`, error);
      camEl.innerHTML = '';
      const fallback = div('mh-graphic-fallback', camEl);
      fallback.textContent = `${shot.asset} · unavailable`;
      return { update() {}, dispose() { fallback.remove(); } };
    }
    return mod;
  }

  function disposeActive() {
    if (!active) return;
    try {
      active.mod?.dispose?.();
    } catch (error) {
      warnOnce(`dispose:${active.shot.id}`, error);
    }
    active.el.remove();
    active = null;
  }

  function activateShot(idx) {
    disposeActive();
    const shot = shots[idx];
    const el = div('mh-shot', stage);
    const camEl = div('mh-cam', el);
    let mod;
    let asset = shot.asset;
    if (shot.kind === 'footage') {
      mod = mountFootage({ el: camEl, shot, theme, assets });
    } else if (shot.kind === 'still') {
      mod = mountStill({ el: camEl, shot, theme, assets });
    } else {
      mod = mountGraphicSafe(shot, camEl);
      asset = null;
    }
    active = { idx, shot, el, camEl, mod, asset };
  }

  /** 镜头相机运动（每帧应用；graphic 无 camera 时清空 transform）。 */
  function applyCamera(shot, p) {
    if (!active) return;
    const transform = shot.camera ? cameraTransform(shot.camera, p) : '';
    if (active.camEl.style.transform !== transform) active.camEl.style.transform = transform;
  }

  function nextPlayableIndex(idx) {
    for (let i = idx + 1; i < shots.length; i++) {
      if (shots[i].dur > 0) return i;
    }
    return -1;
  }

  function preloadAhead(idx, t) {
    const shot = shots[idx];
    if (!shot || t < shot.end - PRELOAD_FOOTAGE) return;
    const next = shots[nextPlayableIndex(idx)];
    if (!next) return;
    if (next.kind === 'footage') {
      // 正在播放的同一素材不能预热（会抢当前 seek）
      if (active?.asset === next.asset) return;
      assets.warm(next.asset, next.in || 0);
    } else if (next.kind === 'still') {
      if (t >= shot.end - PRELOAD_STILL) assets.stillSource(next.asset);
    }
  }

  async function updateOverlays(t) {
    const wanted = new Set(findActiveOverlays(overlayEvents, t));
    for (const [i, rec] of mountedOverlays) {
      if (!wanted.has(i)) {
        try {
          rec.mod?.dispose?.();
        } catch (error) {
          warnOnce(`overlay-dispose:${i}`, error);
        }
        rec.el.remove();
        mountedOverlays.delete(i);
      }
    }
    for (const i of wanted) {
      const event = overlayEvents[i];
      let rec = mountedOverlays.get(i);
      if (!rec) {
        const el = div('mh-overlay', overlaysLayer);
        let mod;
        try {
          mod = mountOverlay({
            el,
            width,
            height,
            shot: active?.shot ?? null,
            theme,
            facts,
            helpers: data.helpers,
            event,
          });
        } catch (error) {
          warnOnce(`overlay:${event.type}-${i}`, error);
          el.remove();
          continue;
        }
        rec = { el, mod };
        mountedOverlays.set(i, rec);
      }
      const local = Math.max(0, t - event.at);
      try {
        const pending = rec.mod?.update?.(local, event.dur);
        if (pending && typeof pending.then === 'function') await pending;
      } catch (error) {
        warnOnce(`overlay-update:${i}`, error);
      }
    }
  }

  async function prepareFrame(globalT) {
    if (disposed) throw new Error('engine disposed');
    const last = shots[shots.length - 1];
    const duration = last?.end ?? 0;
    const t = clamp(Number(globalT) || 0, 0, Math.max(0, duration - 1e-6));

    const idx = findShotIndex(shots, t);
    if (!active || active.idx !== idx) activateShot(idx);
    const shot = shots[idx];
    const local = Math.max(0, t - shot.start);
    const p = shot.dur > 0 ? clamp(local / shot.dur) : 0;

    applyCamera(shot, p);
    if (active?.mod?.update) {
      // footage 在这里 await seek；host 会等本 Promise 完成后才截图。
      // 单帧模块异常不中断整片渲染：记一次告警，保留上一帧状态继续（QC 时逐帧检查）。
      try {
        await active.mod.update(local, shot.dur);
      } catch (error) {
        warnOnce(`update:${shot.id}`, error);
      }
    }

    preloadAhead(idx, t);
    await updateOverlays(t);
    chrome.update({ t, shot, idx, total: shots.length, local, p, frame: frameAt(t) });
    subtitles.update(t);
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    for (const rec of mountedOverlays.values()) {
      try {
        rec.mod?.dispose?.();
      } catch {
        /* noop */
      }
      rec.el.remove();
    }
    mountedOverlays.clear();
    disposeActive();
    try {
      chrome.dispose?.();
      subtitles.dispose?.();
      assets.dispose();
    } catch {
      /* noop */
    }
    wrap.remove();
  }

  return { prepareFrame, dispose };
}
