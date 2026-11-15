// 数字链条：20 − 9 = 11 万；11 ÷ 3 ≈ 3.7 万/年；20 − 9 + 使用成本（计算器节奏、等宽数字）
import { FACTS } from '../data/facts';
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, countUp, fmtInt, rgba } from './prims';

export interface NumberStackProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  newPrice?: number;
  usedPrice?: number;
  diff?: number;
  perYear?: number;
  exhibit?: string;
}

const numStyle = (color: string, p: number, scale: number) => ({
  transform: `translateY(${lerp(16, 0, p)}px) scale(${scale})`,
  transformOrigin: '0% 50%',
  textShadow: `0 0 40px ${rgba(color, 0.3)}`,
  lineHeight: 1,
});

export function NumberStack({
  time,
  from = 0,
  headline = '',
  sub,
  newPrice = FACTS.hook.newPrice,
  usedPrice = FACTS.hook.usedPrice,
  diff = FACTS.hook.diff,
  perYear = FACTS.hook.perYear,
  exhibit = 'EXHIBIT 14 / 折旧换算',
}: NumberStackProps) {
  const t = useLocal(time, from);
  const calc = /÷/.test(headline);
  const tco = /使用成本|\+/.test(headline) && !calc;
  const p1 = inRamp(t, 0.04, 0.3);
  const s1 = lerp(1.14, 1, easeOutQuint(prog(t, 0.04, 0.3)));
  const p2 = inRamp(t, 0.3, 0.3);
  const s2 = lerp(1.14, 1, easeOutQuint(prog(t, 0.3, 0.56)));
  const p3 = inRamp(t, 0.62, 0.34);
  const s3 = lerp(1.18, 1, easeOutQuint(prog(t, 0.62, 0.9)));
  const opIn = inRamp(t, 0.56, 0.3);
  const row2In = easeOutCubic(prog(t, 1.42, 1.82));
  const row2S = lerp(1.1, 1, easeOutQuint(prog(t, 1.42, 1.76)));
  const n1 = countUp(newPrice, t, 0.04, 0.32);
  const n2 = countUp(usedPrice, t, 0.3, 0.32);
  const n3 = countUp(diff, t, 0.62, 0.34);
  const n4 = countUp(Math.round(perYear * 10), t, 1.5, 0.5); // 3.7 → 37
  const capIn = inRamp(t, 0.02, 0.26);

  const header = (
    <>
      <Txt text={exhibit} x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.4} track={3} />
      <Txt text="一台车 · 三年的账" x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.3} track={2} align="right" />
      <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.12} size={16} />
      {headline ? (
        <Txt text={headline} x={168} y={276} size={42} font="serif" color={C.paper} alpha={0.9 * capIn} track={2} weight={600} style={{ clipPath: `inset(0% ${(1 - capIn) * 100}% 0% 0%)` }} />
      ) : null}
      {sub ? <Txt text={sub} x={170} y={338} size={22} font="mono" color={C.amber} alpha={0.78 * inRamp(t, 0.2, 0.32)} track={2} /> : null}
    </>
  );

  if (calc) {
    // 11 ÷ 3 = 3.7 万/年：把整段话读成一个算式
    const q = easeOutQuint(prog(t, 0.12, 0.5));
    const a = countUp(diff, t, 0.12, 0.36);
    const b = countUp(Math.round(perYear * 10), t, 0.5, 0.4);
    return (
      <GFXLayer>
        {header}
        <Txt text={fmtInt(a)} x={320} y={420} size={220} font="mono" color={C.paper} alpha={clamp(q * 1.5)} track={-6} weight={700} style={{ lineHeight: 1 }} />
        <Txt text="÷" x={700} y={452} size={140} font="mono" color={C.paper} alpha={0.72 * q} />
        <Txt text={fmtInt(FACTS.hook.years)} x={880} y={420} size={220} font="mono" color={C.paper} alpha={clamp(q * 1.5)} track={-6} weight={700} style={{ lineHeight: 1 }} />
        <Txt text="=" x={1160} y={452} size={130} font="mono" color={C.amber} alpha={0.8 * q} />
        <Txt text={`${(b / 10).toFixed(1)} 万`} x={1360} y={400} size={190} font="mono" color={C.amber} alpha={clamp(q * 1.5)} track={-5} weight={700} style={{ transform: `scale(${row2S})`, transformOrigin: '0% 50%', lineHeight: 1, textShadow: `0 0 44px ${rgba(C.amber, 0.32)}` }} />
        <Txt text="/ 年" x={1700} y={700} size={28} font="sans" color={C.paper} alpha={0.5 * q} track={2} align="right" />
        <Rule x={320} y={676} w={1260} h={1} color={C.paper} alpha={0.2} progress={easeOutCubic(prog(t, 0.6, 1.0))} />
        <Txt text="摊到每年 ≈ 3.7 万 · 每月 3000 多" x={W / 2} y={760} size={30} font="sans" color={C.paper} alpha={0.6 * inRamp(t, 1.1, 0.4)} track={2} align="center" />
        <Txt text="计算器：差额 ÷ 三年" x={W - 168} y={812} size={18} font="mono" color={C.paper} alpha={0.3} track={2} align="right" />
        <Speckles x={0} y={132} w={1920} h={816} seed={1009} count={16} maxAlpha={0.05} />
      </GFXLayer>
    );
  }

  if (tco) {
    // 20 − 9 + 使用成本：把「买车的账」摊开
    const terms = [
      { label: '落地价', value: `${newPrice} 万`, color: C.paper },
      { label: '−  残值', value: `${usedPrice} 万`, color: C.red },
      { label: '+  使用成本', value: '保险 · 电费 · 保养', color: C.amber },
    ];
    return (
      <GFXLayer>
        {header}
        {terms.map((term, i) => {
          const pp = easeOutQuint(prog(t, 0.14 + i * 0.24, 0.48 + i * 0.24));
          return (
            <Box key={term.label} x={0} y={0} w={0} h={0} alpha={pp}>
              <div style={{ position: 'absolute', left: 200 + i * 500, top: 430, width: 440, height: 190, border: `2px solid ${rgba(C.paper, 0.32)}`, background: 'rgba(10,13,16,.55)' }}>
                <Txt text={term.label} x={30} y={26} size={24} font="mono" color={C.paper} alpha={0.62} track={2} />
                <Txt text={term.value} x={30} y={84} size={i === 2 ? 30 : 70} font={i === 2 ? 'sans' : 'mono'} color={term.color} alpha={0.98} track={i === 2 ? 2 : -2} weight={700} />
              </div>
            </Box>
          );
        })}
        <Txt text={`折旧约 ${diff} 万，没人给你算`} x={W / 2} y={730} size={34} font="sans" color={C.paper} alpha={0.72 * inRamp(t, 1.0, 0.4)} track={2} align="center" />
        <Txt text="当残值变成显性成本，价格战就不再免费" x={W / 2} y={790} size={24} font="mono" color={C.paper} alpha={0.42 * inRamp(t, 1.25, 0.4)} track={1} align="center" />
        <Speckles x={0} y={132} w={1920} h={816} seed={1013} count={16} maxAlpha={0.05} />
      </GFXLayer>
    );
  }

  return (
    <GFXLayer>
      {header}
      {/* row 1: 20 − 9 = 11 */}
      <Txt text={fmtInt(n1)} x={300} y={400} size={190} font="mono" color={C.paper} alpha={clamp(p1 * 1.5)} track={-4} style={numStyle(C.paper, p1, s1)} />
      <Txt text="−" x={598} y={420} size={120} font="mono" color={C.red} alpha={0.9 * opIn} />
      <Txt text={fmtInt(n2)} x={764} y={408} size={176} font="mono" color={C.paper} alpha={clamp(p2 * 1.5)} track={-4} style={numStyle(C.paper, p2, s2)} />
      <Txt text="=" x={1010} y={420} size={110} font="mono" color={C.amber} alpha={0.9 * opIn} />
      <Txt text={`${fmtInt(n3)} 万`} x={1176} y={388} size={196} font="mono" color={C.amber} alpha={clamp(p3 * 1.5)} track={-4} style={numStyle(C.amber, p3, s3)} />
      <Txt text="落地价" x={302} y={604} size={24} font="sans" color={C.paper} alpha={0.5 * p1} track={3} />
      <Txt text="三年后残值" x={766} y={604} size={24} font="sans" color={C.paper} alpha={0.5 * p2} track={3} />
      <Txt text="差额" x={1180} y={604} size={24} font="sans" color={C.amber} alpha={0.62 * p3} track={3} />
      <Rule x={300} y={570} w={1320} h={1} color={C.paper} alpha={0.18} progress={easeOutCubic(prog(t, 0.52, 0.92))} />

      {/* row 2: 11 ÷ 3 ≈ 3.7 万/年 */}
      <Box x={0} y={0} w={0} h={0} alpha={row2In} style={{ transform: `translateY(${lerp(26, 0, row2In)}px)` }}>
        <Txt text={`${fmtInt(diff)}`} x={300} y={676} size={112} font="mono" color={C.paper} alpha={0.92} track={-3} />
        <Txt text="÷" x={492} y={694} size={84} font="mono" color={C.paper} alpha={0.7} />
        <Txt text={`${fmtInt(FACTS.hook.years)}`} x={590} y={686} size={96} font="mono" color={C.paper} alpha={0.92} />
        <Txt text="≈" x={742} y={694} size={84} font="mono" color={C.amber} alpha={0.8} />
        <Txt text={`${(n4 / 10).toFixed(1)} 万`} x={878} y={672} size={118} font="mono" color={C.amber} alpha={0.97} track={-2} style={{ transform: `scale(${row2S})`, transformOrigin: '0% 50%', textShadow: `0 0 32px ${rgba(C.amber, 0.3)}` }} />
        <Txt text="/ 年" x={1322} y={708} size={40} font="sans" color={C.paper} alpha={0.62} track={2} />
        <Txt text="摊到每年 ≈ 3.7 万 · 每月 3000 多" x={302} y={806} size={26} font="sans" color={C.paper} alpha={0.6} track={2} />
      </Box>
      <Txt text="计算器：差额 ÷ 三年" x={W - 168} y={812} size={18} font="mono" color={C.paper} alpha={0.3} track={2} align="right" />
      <Speckles x={0} y={132} w={1920} h={816} seed={1009} count={16} maxAlpha={0.05} />
    </GFXLayer>
  );
}
