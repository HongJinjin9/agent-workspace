// 大数字：三年保值率（45.1 纯电 / 42.2 插混 / 50.6 中大型 SUV …）
// 快节奏：≈0.35–0.45s 计数 + 砸下；等宽字体；刻度尺 0–100%。
import { FACTS } from '../data/facts';
import {
  C,
  F,
  W,
  GFXLayer,
  Txt,
  Box,
  Rule,
  CornerTicks,
  Speckles,
  useLocal,
  inRamp,
  prog,
  easeOutCubic,
  easeOutQuint,
  lerp,
  clamp,
  countUp,
  fmtInt,
  rgba,
} from './prims';

export interface CompareTick {
  value: number;
  label: string;
  color?: string;
}

export interface BigNumberProps {
  time?: number;
  from?: number;
  to?: number;
  value?: number;
  label?: string;
  sub?: string;
  note?: string;
  accent?: 'amber' | 'paper' | 'red';
  /** optional reference tick(s) on the 0–100% gauge */
  compare?: CompareTick[];
  /** where the number sits: center (default) or left */
  align?: 'center' | 'left';
  unit?: string;
  exhibit?: string;
}

export function BigNumber({
  time,
  from = 0,
  value = FACTS.overall.bev,
  label = '纯电 · 三年保值率',
  sub,
  note,
  accent = 'amber',
  compare,
  align = 'center',
  unit = '%',
  exhibit = 'EXHIBIT 03 / 保值率',
}: BigNumberProps) {
  const t = useLocal(time, from);
  const color = accent === 'red' ? C.red : accent === 'paper' ? C.paper : C.amber;
  const refTicks =
    compare ??
    (/插混/.test(label)
      ? [{ value: FACTS.overall.bev, label: `纯电 ${FACTS.overall.bev}%`, color: C.paper }]
      : undefined);
  const numIn = inRamp(t, 0.03, 0.34);
  const slam = lerp(1.18, 1, easeOutQuint(prog(t, 0.03, 0.3)));
  const labelIn = inRamp(t, 0.16, 0.3);
  const ruleIn = easeOutCubic(prog(t, 0.22, 0.56));
  const subIn = inRamp(t, 0.4, 0.32);
  const gaugeIn = easeOutCubic(prog(t, 0.5, 0.95));
  const numP = easeOutQuint(prog(t, 0.03, 0.43));
  const shownNum = lerp(0, value, numP);
  const digits = Number.isInteger(value) ? 0 : 1;
  const shownText = digits ? shownNum.toFixed(1) : fmtInt(Math.round(shownNum));
  const X = align === 'center' ? W / 2 : 300;
  const alignCenter = align === 'center';
  const gaugeW = 1040;
  const gaugeX = W / 2 - gaugeW / 2;
  const gaugeY = 792;
  const numY = 430;
  const numSize = 300;

  return (
    <GFXLayer>
      {/* kicker + label */}
      <Txt
        text={label}
        x={alignCenter ? W / 2 : X}
        y={288}
        size={34}
        font="sans"
        color={C.paper}
        alpha={0.82 * labelIn}
        track={6}
        align={alignCenter ? 'center' : 'left'}
      />
      {/* 0–100 gauge */}
      <Box x={0} y={0} w={0} h={0} alpha={1}>
        <Rule x={gaugeX} y={gaugeY} w={gaugeW} h={2} color={C.paper} alpha={0.32} progress={gaugeIn} />
        {Array.from({ length: 11 }).map((_, i) => {
          const v = i * 10;
          const gx = gaugeX + (v / 100) * gaugeW;
          const big = i % 5 === 0;
          return (
            <Box key={i} x={0} y={0} w={0} h={0} alpha={gaugeIn}>
              <div
                style={{
                  position: 'absolute',
                  left: gx,
                  top: gaugeY - (big ? 14 : 8),
                  width: 2,
                  height: big ? 14 : 8,
                  background: C.paper,
                  opacity: big ? 0.5 : 0.26,
                }}
              />
              {big ? (
                <Txt text={`${v}`} x={gx} y={gaugeY + 22} size={17} font="mono" color={C.paper} alpha={0.4} track={1} align="center" />
              ) : null}
            </Box>
          );
        })}
        {/* reference ticks (e.g. 50% 五成线 / 54% / 66.2%) */}
        {(refTicks ?? []).map((c, i) => {
          const cx = gaugeX + (clamp(c.value, 0, 100) / 100) * gaugeW;
          const ci = easeOutCubic(prog(t, 0.62 + i * 0.16, 0.92 + i * 0.16));
          return (
            <Box key={`ref${i}`} x={0} y={0} w={0} h={0} alpha={ci}>
              <div
                style={{
                  position: 'absolute',
                  left: cx - 1,
                  top: gaugeY - 46,
                  width: 2,
                  height: 46,
                  background: c.color ?? C.paper,
                  opacity: 0.65,
                }}
              />
              <Txt
                text={c.label}
                x={cx}
                y={gaugeY - 86}
                size={20}
                font="mono"
                color={c.color ?? C.paper}
                alpha={0.8}
                track={1}
                align="center"
              />
            </Box>
          );
        })}
        {/* value marker on the gauge */}
        <Box x={0} y={0} w={0} h={0} alpha={gaugeIn}>
          <div
            style={{
              position: 'absolute',
              left: gaugeX + (clamp(value, 0, 100) / 100) * gaugeW - 2,
              top: gaugeY - 26,
              width: 4,
              height: 52,
              background: color,
              boxShadow: `0 0 18px ${rgba(color, 0.55)}`,
            }}
          />
          <Txt
            text={`${value}${unit}`}
            x={gaugeX + (clamp(value, 0, 100) / 100) * gaugeW}
            y={gaugeY + 54}
            size={26}
            font="mono"
            color={color}
            alpha={0.95}
            track={1}
            align="center"
          />
        </Box>
      </Box>

      {/* big number */}
      <Txt
        text={shownText}
        x={alignCenter ? W / 2 : X}
        y={numY}
        size={numSize}
        font="mono"
        color={color}
        alpha={clamp(numIn * 1.5)}
        track={-8}
        align={alignCenter ? 'center' : 'left'}
        style={{
          transform: `translateY(${lerp(20, 0, numIn)}px) scale(${slam})`,
          textShadow: `0 0 60px ${rgba(color, 0.28)}`,
          lineHeight: 1,
        }}
      />
      <Txt
        text={unit}
        x={alignCenter ? W / 2 + 330 : X + 322}
        y={numY + 152}
        size={104}
        font="mono"
        color={color}
        alpha={0.9 * numIn}
        weight={400}
        style={{ transform: `translateY(${lerp(20, 0, numIn)}px)` }}
      />
      <Rule x={alignCenter ? W / 2 - 300 : X} y={numY + 300} w={600} h={2} color={color} alpha={0.55} progress={ruleIn} />
      {sub ? (
        <Txt
          text={sub}
          x={alignCenter ? W / 2 : X}
          y={numY + 342}
          size={30}
          font="sans"
          color={C.paper}
          alpha={0.7 * subIn}
          track={2}
          align={alignCenter ? 'center' : 'left'}
        />
      ) : null}
      {note ? (
        <Txt
          text={note}
          x={alignCenter ? W / 2 : X}
          y={numY + 396}
          size={20}
          font="mono"
          color={C.paper}
          alpha={0.44 * subIn}
          track={1}
          align={alignCenter ? 'center' : 'left'}
        />
      ) : null}

      <Txt text={exhibit} x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.4} track={3} />
      <Txt text="三年保值率 · 2026 年 10 月报告" x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.3} track={2} align="right" />
      <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.12} size={16} />
      <Speckles x={0} y={132} w={1920} h={816} seed={907} count={18} maxAlpha={0.05} />
    </GFXLayer>
  );
}
