// H3 证据影像 DOM 层（Plan-B：H3 为主画面）
// 模式：fill = 全幅（132px 遮幅内 1920×816 cover，一镜一素材）；bg = 低透明全幅压底；pip = 画中画证据窗
// 素材晚绑定：assets/h3/<clip>.mp4 在渲染时才读取；缺失/解码失败自动隐藏（3D 兜底，不黑帧、不改源码）。
import { useRef } from 'react';
import { useFrame } from '@motionharness/sdk';
import type { Shot } from '../data/types';
import { THEME } from '../data/theme';

const BROKEN = new Set<string>();
const CLIP_DUR = 5.184;

function h3Url(name: string) {
  return new URL(`../../assets/h3/${name}.mp4`, import.meta.url).href;
}

function seek(video: HTMLVideoElement, target: number): Promise<void> {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      video.removeEventListener('loadeddata', onReady);
      video.removeEventListener('seeked', onSeeked);
      video.removeEventListener('error', finish);
      resolve();
    };
    const start = () => {
      if (video.error) return finish();
      const dur = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 5;
      // 量化到 24fps 素材帧格：同一解码帧不重复 seek（导出提速）
      const q = Math.round(Math.max(0, Math.min(target, Math.max(0, dur - 0.05))) * 24) / 24;
      const t = Math.min(q, Math.max(0, dur - 0.05));
      if (!video.seeking && Math.abs(video.currentTime - t) < 1e-3) return finish();
      video.currentTime = t;
    };
    const onReady = () => start();
    const onSeeked = () => finish();
    const timer = setTimeout(finish, 800); // 任何异常都必须结束帧等待，避免整片卡死
    video.addEventListener('error', finish, { once: true });
    if (video.readyState >= 2) start();
    else video.addEventListener('loadeddata', onReady, { once: true });
  });
}

export type FootageMode = 'fill' | 'bg' | 'pip';

function H3Clip({ shot, time, mode }: { shot: Shot; time: number; mode: FootageMode }) {
  const ref = useRef<HTMLVideoElement | null>(null);
  const name = shot.h3!;
  useFrame(async () => {
    const v = ref.current;
    if (!v || v.error || BROKEN.has(name)) return;
    const local = Math.max(0, time - shot.start);
    const inPoint = Number.isFinite(shot.in) ? (shot.in as number) : 0.15;
    const dur = Number.isFinite(v.duration) && v.duration > 0 ? v.duration : CLIP_DUR;
    const rate = Math.min(1, Math.max(0.35, (dur - inPoint - 0.1) / Math.max(1, shot.dur))) * 0.98;
    await seek(v, inPoint + local * rate);
  }, [shot.id, mode, name]);
  const style: React.CSSProperties =
    mode === 'fill'
      ? { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', opacity: 1, filter: 'saturate(.86) contrast(1.06) brightness(.9)' }
      : mode === 'bg'
        ? { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', opacity: 0.42, filter: 'saturate(.8) contrast(1.02) brightness(.8)' }
        : { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', opacity: 0.95, filter: 'saturate(.9) contrast(1.03)' };
  return (
    <div className={mode === 'fill' ? 'ep07-h3fill' : mode === 'pip' ? 'ep07-pip' : 'ep07-h3bg'}>
      <video ref={ref} src={h3Url(name)} muted playsInline preload="auto" style={style} onError={(e) => { BROKEN.add(name); (e.currentTarget.parentElement as HTMLElement).style.display = 'none'; }} />
      {mode === 'pip' && (
        <>
          <span className="ep07-pip-label" style={{ fontFamily: THEME.font.mono }}>EVIDENCE / {name}</span>
          <span className="ep07-tick ep07-tick-tl" />
          <span className="ep07-tick ep07-tick-tr" />
          <span className="ep07-tick ep07-tick-bl" />
          <span className="ep07-tick ep07-tick-br" />
        </>
      )}
    </div>
  );
}

export function FootageLayer({ time, shot, opacity = 1 }: { time: number; shot: Shot; opacity?: number }) {
  if (!shot.h3 || shot.h3mode === 'none' || opacity <= 0.01) return null;
  return (
    <div className="ep07-h3-layer" style={{ opacity }}>
      <H3Clip shot={shot} time={time} mode={shot.h3mode as FootageMode} />
    </div>
  );
}
