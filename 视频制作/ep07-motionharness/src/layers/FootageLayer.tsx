// EP07 v2 H3 证据影像层：全幅（132px 遮幅内）强关联插入 + 每镜不同的运动处理。
// 处理：push_in / push_out / pan_l / pan_r / punch_in / mirror / panel / fill；速度 0.85–1.15x 斜坡。
// 素材晚绑定：assets/h3/<clip>.mp4 渲染时读取；缺失/失败自动隐藏（3D/图形兜底，不黑帧）。
import { useRef } from 'react';
import { useFrame } from '@motionharness/sdk';
import type { Shot, Treatment } from '../data/types';
import { clamp, easeInOutCubic, easeOutCubic } from '../three/math';

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
      const q = Math.round(Math.max(0, Math.min(target, Math.max(0, dur - 0.05))) * 24) / 24;
      const t = Math.min(q, Math.max(0, dur - 0.05));
      if (!video.seeking && Math.abs(video.currentTime - t) < 1e-3) return finish();
      video.currentTime = t;
    };
    const onReady = () => start();
    const onSeeked = () => finish();
    const timer = setTimeout(finish, 800);
    video.addEventListener('error', finish, { once: true });
    if (video.readyState >= 2) start();
    else video.addEventListener('loadeddata', onReady, { once: true });
  });
}

/** 每镜不同的运动处理 → 视频元素的 transform / 容器样式（纯时间函数） */
function treatment(treat: Treatment, p: number, local: number): { video: React.CSSProperties; panel: React.CSSProperties | null } {
  const e = easeInOutCubic(p);
  const punch = easeOutCubic(clamp(local / 0.42));
  const base: React.CSSProperties = { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', opacity: 1 };
  const grade = 'saturate(.95) contrast(1.05) brightness(1.04)';
  switch (treat) {
    case 'push_in':
      return { video: { ...base, filter: grade, transform: `scale(${(1.02 + 0.11 * e).toFixed(4)})` }, panel: null };
    case 'push_out':
      return { video: { ...base, filter: grade, transform: `scale(${(1.15 - 0.13 * e).toFixed(4)}) translateY(${((0.5 - p) * 1.2).toFixed(2)}%)` }, panel: null };
    case 'pan_l':
      return { video: { ...base, filter: grade, transform: `scale(1.14) translateX(${(3 - 6 * e).toFixed(2)}%)` }, panel: null };
    case 'pan_r':
      return { video: { ...base, filter: grade, transform: `scale(1.14) translateX(${(-3 + 6 * e).toFixed(2)}%)` }, panel: null };
    case 'punch_in':
      return { video: { ...base, filter: grade, transform: `scale(${(1 + 0.15 * punch + 0.02 * e).toFixed(4)}) translateY(${((1 - punch) * 1.5).toFixed(2)}%)` }, panel: null };
    case 'mirror':
      return { video: { ...base, filter: grade, transform: `scaleX(-1) scale(${(1.03 + 0.08 * e).toFixed(4)})` }, panel: null };
    case 'panel':
      return {
        video: { ...base, filter: grade, transform: `scale(${(1.0 + 0.07 * e).toFixed(4)})` },
        panel: { inset: '10% 12% 16% 12%', border: '1px solid rgba(233,228,216,.22)', boxShadow: '0 26px 70px rgba(0,0,0,.7)' },
      };
    case 'fill':
    default:
      return { video: { ...base, filter: grade, transform: `scale(${(1.03 + 0.04 * e).toFixed(4)})` }, panel: null };
  }
}

function H3Clip({ shot, time }: { shot: Shot; time: number }) {
  const ref = useRef<HTMLVideoElement | null>(null);
  const name = shot.clip!;
  const local = Math.max(0, time - shot.start);
  const p = shot.dur > 0 ? clamp(local / shot.dur) : 0;
  const st = treatment((shot.treat as Treatment) ?? 'fill', p, local);

  useFrame(async () => {
    const v = ref.current;
    if (!v || v.error || BROKEN.has(name)) return;
    const dur = Number.isFinite(v.duration) && v.duration > 0 ? v.duration : CLIP_DUR;
    // 每镜不同起点（确定性、避免同一素材同一起点重复出现）
    const inPoint = 0.18 + ((shot.n * 0.73) % 2.2);
    const rate = clamp(0.85 + 0.3 * p, 0.85, 1.15) * Math.min(1, (dur - inPoint) / Math.max(1, shot.dur)) * 1.02;
    await seek(v, inPoint + local * rate);
  }, [shot.id, shot.treat, name]);

  return (
    <div
      className={shot.treat === 'panel' ? 'ep07-h3fill ep07-h3panel' : 'ep07-h3fill'}
      style={st.panel ?? undefined}
    >
      <video
        ref={ref}
        src={h3Url(name)}
        muted
        playsInline
        preload="auto"
        style={st.video}
        onError={(e) => { BROKEN.add(name); (e.currentTarget.parentElement as HTMLElement).style.display = 'none'; }}
      />
      {shot.treat === 'panel' && <span className="ep07-pip-label">EVIDENCE / {name}</span>}
    </div>
  );
}

export function FootageLayer({ time, shot, opacity = 1 }: { time: number; shot: Shot; opacity?: number }) {
  if (!shot.clip || opacity <= 0.01) return null;
  return (
    <div className="ep07-h3-layer" style={{ opacity }}>
      <H3Clip shot={shot} time={time} />
    </div>
  );
}
