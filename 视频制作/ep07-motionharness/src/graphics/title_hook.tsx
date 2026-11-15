// 片头 3 秒钩子：落地 20 万 → 三年后 9 万（红笔划掉 + 数字砸下）→ 片名
// 文案 props 由 data 传入；数字来自 FACTS；无硬编码数据。
import { FACTS } from '../data/facts';
import {
  C,
  F,
  W,
  H,
  GFXLayer,
  Txt,
  Box,
  Rule,
  CornerTicks,
  Speckles,
  Kicker,
  useLocal,
  inRamp,
  prog,
  easeOutCubic,
  easeOutQuint,
  lerp,
  clamp,
  fmtInt,
  RedStroke,
} from './prims';

export interface TitleHookProps {
  time?: number;
  from?: number;
  to?: number;
  kicker?: string;
  title?: string;
  sub?: string;
  source?: string;
}

export function TitleHook({
  time,
  from = 0,
  kicker = 'VIBE 知识共赏 · 第 07 期',
  title = '三年之后，你的车还值多少钱',
  sub = '一份刚发布的保值率报告，正在给电动车重新定价',
  source = '数据：中国汽车流通协会《2026 年 10 月中国汽车保值率报告》',
}: TitleHookProps) {
  const t = useLocal(time, from);
  const h = FACTS.hook;
  const kp = inRamp(t, 0.02, 0.3);
  const priceIn = inRamp(t, 0.12, 0.34);
  const strike = easeOutCubic(prog(t, 0.42, 0.72));
  const usedIn = inRamp(t, 0.62, 0.34);
  const usedScale = lerp(1.14, 1, easeOutQuint(prog(t, 0.62, 0.92)));
  const capIn = inRamp(t, 0.98, 0.3);
  const ruleIn = easeOutCubic(prog(t, 1.22, 1.56));
  const titleIn = easeOutCubic(prog(t, 1.42, 1.78));
  const subIn = inRamp(t, 1.86, 0.3);
  const metaIn = inRamp(t, 2.2, 0.3);

  return (
    <GFXLayer>
      {/* faint appraisal-sheet fragment on the right, as if the report is already on the table */}
      <Box
        x={1272}
        y={236}
        w={486}
        h={560}
        rot={-2.4}
        alpha={0.92 * inRamp(t, 0.18, 0.42)}
        style={{
          background: `linear-gradient(180deg, rgba(233,228,216,0.97) 0%, ${C.paperShade} 100%)`,
          boxShadow: '0 30px 70px rgba(0,0,0,.6)',
          overflow: 'hidden',
        }}
      >
        <div className="gfx-fibre" style={{ position: 'absolute', inset: 0, opacity: 0.8 }} />
        <Speckles x={0} y={0} w={486} h={560} seed={71} count={22} maxAlpha={0.09} />
        <Txt text="二手车鉴定评估单" x={38} y={34} size={26} font="serif" color={C.ink} track={3} weight={600} />
        <Txt text="RESIDUAL VALUE APPRAISAL" x={38} y={74} size={13} font="mono" color={C.inkSoft} track={2} alpha={0.7} />
        <Rule x={38} y={108} w={410} h={2} color={C.ink} alpha={0.5} progress={inRamp(t, 0.3, 0.5)} />
        {[
          ['项目', '数值'],
          ['新车落地价', '20.0 万'],
          ['使用年限', '3 年'],
          ['残值报价', '9.0 万'],
          ['年均折旧', '3.7 万'],
        ].map((row, i) => (
          <Box key={i} x={0} y={0} w={0} h={0}>
            <Txt
              text={row[0]}
              x={38}
              y={140 + i * 62}
              size={20}
              font="sans"
              color={i === 0 ? C.inkSoft : C.ink}
              alpha={(i === 0 ? 0.55 : 0.92) * inRamp(t, 0.4 + i * 0.06, 0.3)}
              track={2}
            />
            <Txt
              text={row[1]}
              x={448}
              y={130 + i * 62}
              size={30}
              font="mono"
              color={i === 3 ? C.red : C.ink}
              alpha={(i === 0 ? 0 : 0.95) * inRamp(t, 0.4 + i * 0.06, 0.3)}
              align="right"
            />
          </Box>
        ))}
        <Rule x={38} y={140 + 62} w={410} h={1} color={C.ink} alpha={0.22} progress={inRamp(t, 0.42, 0.3)} />
        <Txt text="EXHIBIT 01 / 评估单" x={38} y={500} size={14} font="mono" color={C.inkSoft} alpha={0.55} track={2} />
      </Box>

      {/* main hook typography */}
      <Kicker text={kicker} x={168} y={318} alpha={0.72 * kp} track={6} />
      <Txt
        text={`落地 ${fmtInt(h.newPrice)} 万`}
        x={168}
        y={388}
        size={132}
        font="mono"
        color={C.paper}
        alpha={0.96 * priceIn}
        track={-2}
        style={{ transform: `translateY(${lerp(16, 0, priceIn)}px)` }}
      />
      {/* red pen strike through the original price */}
      <RedStroke
        d="M 176 452 C 340 436, 560 470, 742 444"
        progress={strike}
        width={7}
        alpha={0.92}
        x={0}
        y={0}
      />
      <Txt
        text={`三年后 ${fmtInt(h.usedPrice)} 万`}
        x={168}
        y={548}
        size={168}
        font="mono"
        color={C.amber}
        alpha={clamp(usedIn * 1.4)}
        track={-3}
        style={{
          transform: `translateY(${lerp(18, 0, usedIn)}px) scale(${usedScale})`,
          transformOrigin: '0% 50%',
          textShadow: '0 0 36px rgba(217,164,65,.35)',
        }}
      />
      <Txt
        text={`一台车，三年蒸发 ${fmtInt(h.diff)} 万`}
        x={172}
        y={752}
        size={34}
        font="sans"
        color={C.paper}
        alpha={0.75 * capIn}
        track={2}
      />
      <Rule x={172} y={812} w={520} h={1} color={C.amber} alpha={0.55} progress={ruleIn} />

      {/* film title — second beat of the hook */}
      <Txt
        text={title}
        x={168}
        y={832}
        size={58}
        font="serif"
        color={C.paper}
        alpha={0.97 * titleIn}
        track={3}
        weight={600}
        style={{
          clipPath: `inset(0% ${(1 - titleIn) * 100}% 0% 0%)`,
          transform: `translateY(${lerp(10, 0, titleIn)}px)`,
        }}
      />
      <Txt text={sub} x={170} y={900} size={24} font="sans" color={C.paper} alpha={0.55 * subIn} track={2} />
      <Txt text={source} x={W - 168} y={902} size={16} font="mono" color={C.paper} alpha={0.34 * metaIn} track={1} align="right" />

      {/* evidence frame + EXHIBIT */}
      <CornerTicks x={132} y={176} w={W - 264} h={690} color={C.paper} alpha={0.16} size={16} />
      <Txt text="CASE FILE · EP07" x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.4 * kp} track={4} />
      <Txt text="2026.11.10 · 保值率报告" x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.36 * kp} track={2} align="right" />
      {/* vertical red case rule */}
      <Box x={150} y={236} w={2} h={598} alpha={0.32 * kp} style={{ background: C.red }} />
      <Speckles x={0} y={132} w={W} h={816} seed={703} count={20} maxAlpha={0.06} />
    </GFXLayer>
  );
}
