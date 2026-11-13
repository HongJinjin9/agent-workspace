// 素材池：footage 用 host media 解码助手（muted、irregular seek 安全、可取消），
// still 用惰性 Image 预载。所有 URL 相对 import.meta.url，随工程迁移。
//
// media 由 host 注入：media.video(url) -> Promise<{ element, prepareFrame(srcSeconds) }>
// 这些元素是 muted/preload=auto/playsInline，prepareFrame 会 pause + seek 到素材秒。

const FOOTAGE_COUNT = 14;

export function footageUrl(name) {
  return new URL(`../../assets/footage/${name}.mp4`, import.meta.url).href;
}

export function stillUrl(name) {
  return new URL(`../../assets/stills/${name}.jpg`, import.meta.url).href;
}

export function createAssetPool(media) {
  /** name -> { promise, handle, prepared } */
  const videos = new Map();
  /** name -> Promise (Image decode) */
  const stills = new Map();
  /** name -> Image (保持引用，避免被回收后重复下载) */
  const imageCache = new Map();
  let disposed = false;

  function video(name) {
    let rec = videos.get(name);
    if (!rec) {
      rec = { promise: null, handle: null, prepared: false };
      rec.promise = media.video(footageUrl(name)).then((handle) => {
        rec.handle = handle;
        return handle;
      });
      videos.set(name, rec);
    }
    return rec.promise;
  }

  /** 预载下一个 footage 镜头的首帧（只在素材尚未出场时做，避免抢当前镜头的 seek）。 */
  async function warm(name, sourceTime) {
    if (disposed) return;
    const rec = videos.get(name);
    if (rec && rec.prepared) return;
    const handle = await video(name);
    const target = videos.get(name);
    if (!target || target.prepared || disposed) return;
    target.prepared = true;
    try {
      await handle.prepareFrame(sourceTime);
    } catch {
      /* 预载失败不影响正式出帧（正式 update 会再等一次） */
    }
  }

  function still(name) {
    let promise = stills.get(name);
    if (!promise) {
      const img = new Image();
      img.decoding = 'async';
      img.src = stillUrl(name);
      promise = (img.decode ? img.decode() : Promise.resolve()).catch(() => undefined);
      stills.set(name, promise);
      imageCache.set(name, img);
    }
    return promise;
  }

  /** 给 still 模块用：返回一个已预热的 <img> 的 src（模块自己建 img 交给 host 等 decode）。 */
  function stillSource(name) {
    still(name);
    return stillUrl(name);
  }

  function dispose() {
    disposed = true;
    for (const rec of videos.values()) {
      const el = rec.handle?.element;
      if (el) {
        try {
          el.pause();
          el.removeAttribute('src');
          el.load();
        } catch {
          /* noop */
        }
      }
    }
    videos.clear();
    stills.clear();
    imageCache.clear();
  }

  return {
    count: FOOTAGE_COUNT,
    footageUrl,
    stillUrl,
    video,
    warm,
    stillSource,
    dispose,
  };
}
