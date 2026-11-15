// 价签：新车优惠 ↔ 二手挂牌价 / 翻面 / 两签并排落下
import type { ReactNode } from 'react';
import { FACTS } from '../data/facts';
import { C, F, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';

export interface PriceTagProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  exhibit?: string;
}

function TagCard({
  x,
  y,
  w,
  h,
  label,
  value,
  note,
  color = C.amber,
  rot = 0,
  alpha = 1,
  strikeNote = false,
  children,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  value: string;
  note?: string;
  color?: string;
  rot?: number;
  alpha?: number;
  strikeNote?: boolean;
  children?: ReactNode;
}) {
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, height: h, opacity: alpha, transform: `rotate(${rot}deg)`, transformOrigin: '50% 0%' }}>
      {/* hanger wire */}
      <div style={{ position: 'absolute', left: w / 2 - 1, top: -y + 132, height: y - 132, width: 2, background: rgba(C.paper, 0.28) }} />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: `linear-gradient(180deg, #f0ebe0 0%, ${C.paper} 52%, ${C.paperShade} 100%)`,
          boxShadow: '0 26px 60px rgba(0,0,0,.55), inset 0 0 0 1px rgba(80,62,38,.22)',
          overflow: 'hidden',
        }}
      >
        <div className="gfx-fibre" style={{ position: 'absolute', inset: 0, opacity: 0.7 }} />
        <div style={{ position: 'absolute', left: w / 2 - 7, top: 16, width: 14, height: 14, borderRadius: '50%', background: 'rgba(11,14,17,.4)', boxShadow: 'inset 0 2px 3px rgba(0,0,0,.5)' }} />
        <div style={{ position: 'absolute', left: 0, top: 46, width: w, height: 3, background: color, opacity: 0.85 }} />
        <Txt text={label} x={26} y={64} size={22} font="mono" color={C.inkSoft} alpha={0.8} track={2} />
        <Txt text={value} x={26} y={104} size={Math.min(88, w * 0.26)} font="mono" color={color === C.paper ? C.ink : color} alpha={0.98} track={-2} weight={700} />
        {note ? (
          <Txt
            text={note}
            x={26}
            y={h - 56}
            size={20}
            font="mono"
            color={C.inkSoft}
            alpha={0.7}
            track={1}
            style={strikeNote ? { textDecoration: 'line-through', textDecorationColor: C.red, textDecorationThickness: 2 } : undefined}
          />
        ) : null}
        {children}
      </div>
    </div>
  );
}

export function PriceTag({ time, from = 0, headline = '', sub, exhibit = 'EXHIBIT 24 / 价签' }: PriceTagProps) {
  const t = useLocal(time, from);
  const headIn = inRamp(t, 0.02, 0.28);
  const flip = /透支|下坠/.test(headline);
  const drop = /定残值|落下/.test(headline);
  const pair = !flip && !drop;

  const header = (
    <>
      <Txt text="PRICE TAG · 两张价签" x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.38} track={3} />
      <Txt text={exhibit} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.34} track={2} align="right" />
      <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.11} size={16} />
    </>
  );

  if (pair || drop) {
    const inL = inRamp(t, 0.12, 0.36);
    const inR = inRamp(t, 0.28, 0.36);
    const dropY = drop ? lerp(0, 44, easeOutCubic(prog(t, 0.6, 4.2))) : 0;
    return (
      <GFXLayer>
        {header}
        <Box x={0} y={0} w={0} h={0} alpha={1} style={{ transform: `translateY(${dropY}px)` }}>
          <Box x={0} y={0} w={0} h={0} alpha={inL} style={{ transform: `translateY(${lerp(-40, 0, inL)}px)` }}>
            <TagCard
              x={384}
              y={402}
              w={352}
              h={296}
              label={drop ? '新车发布会' : '新车 · 优惠后'}
              value="18 万"
              note={drop ? '定卖价 20 万' : '原 20 万'}
              strikeNote={!drop}
              color={drop ? C.paper : C.amber}
              rot={-2.2}
            />
          </Box>
          <Box x={0} y={0} w={0} h={0} alpha={inR} style={{ transform: `translateY(${lerp(-40, 0, inR)}px)` }}>
            <TagCard
              x={1184}
              y={446}
              w={352}
              h={296}
              label={drop ? '二手车市场' : '二手 · 挂牌价'}
              value="9 万"
              note={drop ? '定残值 9 万' : '三年残值'}
              color={C.amber}
              rot={2}
            />
          </Box>
        </Box>
        {/* red downward line between the two tags */}
        <div
          style={{
            position: 'absolute',
            left: 756,
            top: 520,
            width: 400,
            height: 4,
            background: C.red,
            opacity: 0.8 * easeOutCubic(prog(t, 0.7, 1.05)),
            transform: `rotate(5deg) scaleX(${easeOutCubic(prog(t, 0.7, 1.05))})`,
            transformOrigin: '0% 50%',
          }}
        />
        <Txt
          text={headline}
          x={W / 2}
          y={802}
          size={34}
          font="sans"
          color={C.paper}
          alpha={0.85 * inRamp(t, 0.5, 0.36)}
          track={3}
          align="center"
        />
        <Speckles x={0} y={132} w={1920} h={816} seed={1501} count={16} maxAlpha={0.05} />
      </GFXLayer>
    );
  }

  // flip: 一张价签翻面，数字下坠
  const flipP = clamp(prog(t, 0.55, 0.95));
  const scaleX = Math.abs(Math.cos(flipP * Math.PI));
  const showBack = flipP > 0.5;
  return (
    <GFXLayer>
      {header}
      <Txt text={headline} x={168} y={270} size={50} font="serif" color={C.paper} alpha={0.94 * headIn} track={2} weight={600} />
      <Box x={0} y={0} w={0} h={0} alpha={inRamp(t, 0.1, 0.32)} style={{ transform: `translateY(${lerp(-30, 0, inRamp(t, 0.1, 0.32))}px)` }}>
        <div style={{ position: 'absolute', left: 760, top: 380, width: 400, height: 330, transform: `scaleX(${scaleX})`, transformOrigin: '50% 50%' }}>
          <TagCard
            x={0}
            y={0}
            w={400}
            h={330}
            label={showBack ? '三年后 · 残值' : '新车 · 落地价'}
            value={showBack ? '9 万' : '20 万'}
            note={showBack ? '市场定价' : '发布会定价'}
            color={showBack ? C.amber : C.paper}
            rot={0}
          />
        </div>
        <Txt text="↓" x={W / 2} y={730} size={64} font="mono" color={C.red} alpha={0.85 * easeOutCubic(prog(t, 0.9, 1.25))} align="center" />
        <Txt text="降价透支旧车价" x={W / 2} y={800} size={32} font="sans" color={C.paper} alpha={0.8 * inRamp(t, 0.6, 0.4)} track={3} align="center" />
      </Box>
      <Txt text="两张价签：发布会定卖价，市场定残值" x={168} y={440} size={22} font="mono" color={C.paper} alpha={0.4} track={2} />
      <Speckles x={0} y={132} w={1920} h={816} seed={1511} count={16} maxAlpha={0.05} />
    </GFXLayer>
  );
}
