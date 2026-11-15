// 片头 3-5s 钩子 v2：20 万 → 翻转 → 9 万（红笔划掉）+ 片名 kinetic + 纸卡入画
import { FACTS } from '../data/facts';
import { C, F, W, GFXLayer, Txt, Box, Paper, Rule, CornerTicks, Speckles, Camera, Odometer, FlipPanel, Kinetic, ScanBeam, Dust, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';

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
  to = 5.6,
  kicker = 'VIBE 知识共赏 · 第 07 期',
  title = '三年之后，你的车还值多少钱',
  sub = '一份刚发布的保值率报告，正在给电动车重新定价',
  source = '数据：中国汽车流通协会《2026 年 10 月中国汽车保值率报告》',
}: TitleHookProps) {
  const t = useLocal(time, from);
  const dur = Math.max(1, (to ?? from + 5.6) - from);
  const h = FACTS.hook;
  const cardIn = inRamp(t, 0.08, 0.34);
  const kick = inRamp(t, 0.0, 0.24);
  const strike = easeOutCubic(prog(t, 0.34, 0.6));
  const flip = 0.62;
  const usedIn = inRamp(t, 0.82, 0.34);
  const diffIn = inRamp(t, 1.08, 0.3);
  const titleIn = easeOutCubic(prog(t, 1.5, 1.9));
  const subIn = inRamp(t, 2.0, 0.3);
  const metaIn = inRamp(t, 2.4, 0.3);

  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={1.1}>
        {/* 评估单纸卡：从右侧滑入，行文 type-in */}
        <Box x={1240} y={240} w={520} h={560} rot={-2} alpha={cardIn} style={{ transform: `translateY(${lerp(40, 0, cardIn)}px) translateX(${lerp(60, 0, cardIn)}px)` }}>
          <Paper x={0} y={0} w={520} h={560} rot={0} opacity={1}>
            <Txt text="二手车鉴定评估单" x={40} y={36} size={28} font="serif" color={C.ink} track={3} weight={700} />
            <Txt text="RESIDUAL VALUE APPRAISAL" x={42} y={80} size={13} font="mono" color={C.inkSoft} track={2} alpha={0.7} />
            <Rule x={40} y={114} w={440} h={2} color={C.ink} alpha={0.5} progress={easeOutCubic(prog(t, 0.2, 0.6))} />
            {[
              ['新车落地价', '20.0 万'],
              ['使用年限', '3 年'],
              ['残值报价', '9.0 万'],
              ['年均折旧', '3.7 万'],
            ].map((row, i) => {
              const p = inRamp(t, 0.3 + i * 0.1, 0.3);
              return (
                <Box key={row[0]} x={0} y={0} w={0} h={0} alpha={p}>
                  <Txt text={row[0]} x={40} y={156 + i * 62} size={21} font="sans" color={C.inkSoft} alpha={0.85} track={2} />
                  <Txt text={row[1]} x={480} y={148 + i * 62} size={32} font="mono" color={i === 2 ? C.red : C.ink} alpha={0.95} track={-1} weight={700} align="right" />
                </Box>
              );
            })}
            <Rule x={40} y={430} w={440} h={1} color={C.ink} alpha={0.2} progress={inRamp(t, 0.6, 0.4)} />
            <Txt text="EXHIBIT 01 / 评估单" x={40} y={500} size={14} font="mono" color={C.inkSoft} alpha={0.55} track={2} />
          </Paper>
        </Box>

        {/* hook numbers: 20 万 → 翻转 → 9 万 */}
        <Kinetic text={kicker} x={168} y={300} size={24} color={C.paper} local={t} delay={0.02} track={6} font="mono" weight={400} rise={10} />
        <Txt text="落地价" x={170} y={368} size={22} font="mono" color={C.paper} alpha={0.5 * kick} track={2} />
        <FlipPanel
          local={t}
          at={flip}
          dur={0.34}
          x={168}
          y={404}
          w={700}
          h={220}
          front={
            <Box x={0} y={0} w={700} h={220} alpha={1}>
              <Odometer value={h.newPrice} x={0} y={0} size={176} color={C.paper} local={t} delay={0.08} dur={0.42} digitsAfter={0} suffix=" 万" align="left" glow={0.2} />
              <div style={{ position: 'absolute', left: 0, top: 0, width: 560 * strike, height: 8, background: C.red, opacity: 0.9, transform: 'rotate(-4deg)', transformOrigin: '0% 50%', boxShadow: `0 0 18px ${rgba(C.red, 0.4)}` }} />
            </Box>
          }
          back={
            <Box x={0} y={0} w={700} h={220} alpha={1}>
              <Odometer value={h.usedPrice} x={0} y={0} size={208} color={C.amber} local={t} delay={flip + 0.1} dur={0.34} digitsAfter={0} suffix=" 万" align="left" glow={0.4} />
              <Txt text="三年后残值" x={4} y={206} size={22} font="mono" color={C.amber} alpha={0.7 * usedIn} track={2} />
            </Box>
          }
        />
        <Kinetic text={`一台车，三年蒸发 ${h.diff} 万`} x={172} y={650} size={38} color={C.paper} local={t} delay={1.08} font="sans" weight={600} track={2} />
        <Rule x={172} y={716} w={520} h={1} color={C.amber} alpha={0.6} progress={easeOutCubic(prog(t, 1.4, 1.8))} />

        {/* film title — kinetic */}
        <Kinetic text={title} x={168} y={760} size={58} color={C.paper} local={t} delay={1.5} step={0.022} track={3} weight={600} />
        <Kinetic text={sub} x={170} y={838} size={24} color={C.paper} local={t} delay={2.05} step={0.01} track={2} font="sans" weight={400} rise={10} />
        <Txt text={source} x={W - 168} y={880} size={16} font="mono" color={C.paper} alpha={0.34 * metaIn} track={1} align="right" />

        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.14} size={16} />
        <Txt text="CASE FILE · EP07" x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.4 * kick} track={4} />
        <Txt text="2026.11.10 · 保值率报告" x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.34 * kick} track={2} align="right" />
        <Box x={150} y={236} w={2} h={598} alpha={0.32 * kick} style={{ background: C.red }} />
        <ScanBeam local={t} y0={260} y1={860} speed={0.1} alpha={0.07} />
        <Dust local={t} count={12} seed={703} alpha={0.3} />
      </Camera>
    </GFXLayer>
  );
}
