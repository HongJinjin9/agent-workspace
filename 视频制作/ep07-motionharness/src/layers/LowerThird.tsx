// H3 全幅证据镜头上的极简排版：一个视觉焦点（短句 + 可选数字），左下角，位于 132px 遮幅内容区内。
// 依赖 shots.json 的 headline/sub；纯时间函数，无 rAF。
import type { Shot } from '../data/types';
import { THEME } from '../data/theme';

const NUM = /(\d+(?:\.\d+)?\s*%?|\d+[.,]\d+|万|亿|\+\s*\d+)/;

export function LowerThird({ shot, time }: { shot: Shot; time: number }) {
  const local = Math.max(0, time - shot.start);
  const inP = Math.min(1, Math.max(0, (local - 0.18) / 0.5));
  const outP = Math.min(1, Math.max(0, (shot.end - time) / 0.35));
  const alpha = Math.min(inP, outP);
  if (alpha <= 0.01) return null;
  const sub = shot.sub ?? '';
  // 只把「百分比 / 万」这类真正的数字指标做成大字；年龄/里程等不抢焦点
  const numMatch = sub.match(/(\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*万)/);
  const hasNum = Boolean(numMatch);
  return (
    <div style={{ position: 'absolute', left: 0, bottom: 176, padding: '26px 120px 26px 110px', opacity: alpha, transform: `translateY(${(1 - inP) * 14}px)`, pointerEvents: 'none',
      background: 'linear-gradient(90deg, rgba(4,6,9,.72) 0%, rgba(4,6,9,.52) 46%, rgba(4,6,9,0) 78%)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 26 }}>
        {hasNum ? (
          <div style={{ font: `600 92px/0.95 ${THEME.font.mono}`, color: THEME.color.amber, letterSpacing: '-0.02em', textShadow: '0 2px 22px rgba(0,0,0,.8)' }}>
            {numMatch![1].replace(/\s+/g, '')}
          </div>
        ) : null}
        <div style={{ paddingBottom: hasNum ? 10 : 0 }}>
          <div style={{ font: `600 34px/1.3 ${THEME.font.serif}`, color: 'rgba(255,253,247,.99)', letterSpacing: '.06em', textShadow: '0 2px 18px rgba(0,0,0,.95), 0 0 4px rgba(0,0,0,.8)' }}>
            {shot.headline}
          </div>
          {sub && !hasNum ? (
            <div style={{ marginTop: 8, font: `500 22px/1.3 ${THEME.font.sans}`, color: 'rgba(233,228,216,.8)', letterSpacing: '.08em', textShadow: '0 1px 12px rgba(0,0,0,.8)' }}>{sub}</div>
          ) : null}
        </div>
      </div>
      <div style={{ marginTop: 16, width: 64, height: 2, background: 'rgba(217,164,65,.85)' }} />
    </div>
  );
}
