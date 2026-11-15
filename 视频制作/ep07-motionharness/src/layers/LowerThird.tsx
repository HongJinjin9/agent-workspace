// H3 镜头上的动态 lower-third：短句 + 可选数字 count-up + 生长线 + 轻微位移；一个视觉焦点。
import type { Shot } from '../data/types';
import { THEME } from '../data/theme';
import { clamp, easeOutCubic, countUp } from '../three/math';

const NUM = /(\d+(?:\.\d+)?)\s*(%|万|年|公里)?/;

export function LowerThird({ shot, time }: { shot: Shot; time: number }) {
  const local = Math.max(0, time - shot.start);
  const inP = easeOutCubic(clamp((local - 0.10) / 0.42));
  const outP = easeOutCubic(clamp((shot.end - time) / 0.30));
  const alpha = Math.min(inP, outP);
  if (alpha <= 0.01) return null;
  const sub = shot.sub ?? '';
  // 仅当 sub 含 % / 万 类指标时给大字数字（避免“8 年”这类干扰）
  const m = sub.match(/(\d+(?:\.\d+)?)\s*(%|万)/);
  let big: string | null = null;
  if (m) {
    const value = parseFloat(m[1]);
    const decimals = m[1].includes('.') ? 1 : 0;
    const shown = countUp(value, local, 0.55, 0);
    big = `${shown.toFixed(decimals)}${m[2]}`;
  }
  const lineW = 26 + 58 * easeOutCubic(clamp((local - 0.14) / 0.5));
  return (
    <div style={{
      position: 'absolute', left: 0, bottom: 176, padding: '26px 130px 26px 110px',
      opacity: alpha, transform: `translateY(${((1 - inP) * 16).toFixed(2)}px)`, pointerEvents: 'none',
      background: 'linear-gradient(90deg, rgba(4,6,9,.74) 0%, rgba(4,6,9,.52) 46%, rgba(4,6,9,0) 80%)',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 26 }}>
        {big ? (
          <div style={{ font: `600 96px/0.92 ${THEME.font.mono}`, color: THEME.color.amber, letterSpacing: '-0.02em', textShadow: '0 2px 26px rgba(0,0,0,.9)' }}>{big}</div>
        ) : null}
        <div style={{ paddingBottom: big ? 12 : 0 }}>
          <div style={{ font: `600 36px/1.28 ${THEME.font.serif}`, color: 'rgba(255,253,247,.99)', letterSpacing: '.05em', textShadow: '0 2px 18px rgba(0,0,0,.95)' }}>
            {shot.headline}
          </div>
          {sub && !big ? (
            <div style={{ marginTop: 8, font: `500 23px/1.3 ${THEME.font.sans}`, color: 'rgba(233,228,216,.82)', letterSpacing: '.07em', textShadow: '0 1px 12px rgba(0,0,0,.85)' }}>{sub}</div>
          ) : null}
        </div>
      </div>
      <div style={{ marginTop: 16, width: lineW, height: 2, background: 'rgba(217,164,65,.9)' }} />
    </div>
  );
}
