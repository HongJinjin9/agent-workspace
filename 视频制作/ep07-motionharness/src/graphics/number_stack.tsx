// 数字链条 v2：20 万 → 翻转 → 9 万（红笔划掉），差额 11 万，11÷3≈3.7 万/年，3000+/月
import { FACTS } from '../data/facts';
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, Camera, Odometer, OdometerInt, FlipPanel, Kinetic, ScanBeam, Dust, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';

export interface NumberStackProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  variant?: string;
  newPrice?: number;
  usedPrice?: number;
  diff?: number;
  perYear?: number;
  exhibit?: string;
}

export function NumberStack({
  time,
  from = 0,
  to,
  headline = '',
  sub,
  variant,
  newPrice = FACTS.hook.newPrice,
  usedPrice = FACTS.hook.usedPrice,
  diff = FACTS.hook.diff,
  perYear = FACTS.hook.perYear,
  exhibit = 'EXHIBIT 14',
}: NumberStackProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 3.5) - from);
  const calc = /÷/.test(headline);
  const tco = variant === 'tco' || (/使用成本/.test(headline) && !calc);
  const month = !calc && !tco && (/3000|一个月/.test(headline) || /3000/.test(String(sub ?? '')));
  const headIn = inRamp(t, 0, 0.26);
  const flipAt = 0.62;
  const strike = easeOutCubic(prog(t, 0.32, 0.58));
  const diffIn = inRamp(t, 1.0, 0.34);
  const row2In = easeOutCubic(prog(t, 1.35, 0.5));

  const header = (
    <>
      <Txt text={exhibit} x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.4} track={3} />
      <Txt text={calc ? '计算器 · 差额 ÷ 三年' : tco ? '总拥有成本' : '一台车 · 三年的账'} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.3} track={2} align="right" />
      <Rule x={168} y={240} w={W - 336} h={1} color={C.paper} alpha={0.16} progress={easeOutCubic(prog(t, 0.04, 0.4))} />
      <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />
      {headline ? <Kinetic text={headline} x={168} y={276} size={40} color={C.paper} local={t} delay={0.02} track={2} weight={600} /> : null}
      {sub ? <Txt text={sub} x={170} y={338} size={22} font="mono" color={C.amber} alpha={0.8 * headIn} track={2} /> : null}
    </>
  );

  if (calc) {
    // 11 ÷ 3 ≈ 3.7 万/年 + 3000+/月
    const divIn = easeOutQuint(prog(t, 0.12, 0.5));
    return (
      <GFXLayer>
        <Camera local={t} dur={dur} strength={0.9}>
          {header}
          <OdometerInt value={diff} x={320} y={400} size={216} color={C.paper} local={t} delay={0.1} dur={0.5} />
          <div style={{ position: 'absolute', left: 700, top: 430, fontSize: 140, fontFamily: 'DejaVu Sans Mono, monospace', color: C.paper, opacity: 0.72 * divIn }}>÷</div>
          <OdometerInt value={FACTS.hook.years} x={880} y={400} size={216} color={C.paper} local={t} delay={0.18} dur={0.5} />
          <div style={{ position: 'absolute', left: 1150, top: 430, fontSize: 130, fontFamily: 'DejaVu Sans Mono, monospace', color: C.amber, opacity: 0.8 * divIn }}>=</div>
          <Odometer value={perYear} x={1352} y={372} size={196} color={C.amber} local={t} delay={0.28} dur={0.55} digitsAfter={1} suffix=" 万" align="left" glow={0.4} />
          <Txt text="/ 年" x={1700} y={700} size={28} font="sans" color={C.paper} alpha={0.5 * row2In} track={2} align="right" />
          <Rule x={320} y={676} w={1260} h={1} color={C.paper} alpha={0.2} progress={row2In} />
          <Txt text="摊到每年 ≈ 3.7 万 · 每月 " x={W / 2 - 60} y={754} size={30} font="sans" color={C.paper} alpha={0.55 * row2In} track={2} align="right" />
          <OdometerInt value={3000} x={W / 2 + 40} y={730} size={48} color={C.amber} local={t} delay={1.5} dur={0.45} />
          <Txt text="+" x={W / 2 + 236} y={744} size={30} font="mono" color={C.amber} alpha={0.8 * row2In} />
          <ScanBeam local={t} y0={300} y1={820} speed={0.14} alpha={0.08} />
          <Dust local={t} count={10} seed={1009} alpha={0.3} />
          <Speckles x={0} y={132} w={1920} h={816} seed={1009} count={12} maxAlpha={0.04} />
        </Camera>
      </GFXLayer>
    );
  }

  if (tco) {
    // 20 − 9 + 使用成本：三张卡 + 折旧约 11 万
    const terms = [
      { label: '落地价', v: newPrice, color: C.paper, suffix: ' 万', dec: 0 },
      { label: '−  残值', v: usedPrice, color: C.red, suffix: ' 万', dec: 0 },
      { label: '+  使用成本', v: 0, color: C.amber, suffix: '', dec: 0 },
    ];
    return (
      <GFXLayer>
        <Camera local={t} dur={dur} strength={0.9}>
          {header}
          {terms.map((term, i) => {
            const pp = easeOutQuint(prog(t, 0.12 + i * 0.2, 0.44 + i * 0.2));
            return (
              <Box key={term.label} x={0} y={0} w={0} h={0} alpha={pp} style={{ transform: `translateY(${lerp(30, 0, pp)}px)` }}>
                <div style={{ position: 'absolute', left: 200 + i * 500, top: 420, width: 440, height: 196, border: `2px solid ${rgba(C.paper, 0.3)}`, background: 'rgba(10,13,16,.55)', overflow: 'hidden' }}>
                  <Txt text={term.label} x={28} y={26} size={24} font="mono" color={C.paper} alpha={0.62} track={2} />
                  {i < 2 ? (
                    <Odometer value={term.v} x={28} y={82} size={72} color={term.color} local={t} delay={0.16 + i * 0.2} dur={0.5} digitsAfter={0} suffix=" 万" align="left" glow={0.2} />
                  ) : (
                    <Txt text="保险 · 电费 · 保养" x={28} y={100} size={30} font="sans" color={C.amber} alpha={0.95} track={2} />
                  )}
                </div>
              </Box>
            );
          })}
          <Txt text="=" x={1660} y={470} size={68} font="mono" color={C.paper} alpha={0.6 * inRamp(t, 0.8, 0.3)} />
          <Kinetic text={`折旧约 ${diff} 万，没人给你算`} x={200} y={700} size={40} color={C.paper} local={t} delay={1.0} track={2} weight={600} />
          <Kinetic text="当残值变成显性成本，价格战就不再免费" x={200} y={770} size={26} color={C.amber} local={t} delay={1.4} track={1} font="sans" weight={500} />
          <ScanBeam local={t} y0={300} y1={830} speed={0.13} alpha={0.08} />
          <Dust local={t} count={10} seed={1013} alpha={0.3} />
        </Camera>
      </GFXLayer>
    );
  }

  if (month) {
    // 一个月 3000 多：把年折旧摊到月
    return (
      <GFXLayer>
        <Camera local={t} dur={dur} strength={1.0}>
          {header}
          <Txt text="每年 ≈ 3.7 万 ÷ 12" x={200} y={398} size={30} font="mono" color={C.paper} alpha={0.55 * inRamp(t, 0.06, 0.3)} track={2} />
          <Txt text="≈" x={200} y={470} size={90} font="mono" color={C.amber} alpha={0.7 * inRamp(t, 0.2, 0.3)} />
          <OdometerInt value={3000} x={330} y={430} size={210} color={C.amber} local={t} delay={0.22} dur={0.5} />
          <Txt text="+" x={330 + 4 * 210 * 0.62 + 16} y={452} size={140} font="mono" color={C.amber} alpha={0.9 * inRamp(t, 0.5, 0.3)} />
          <Txt text="元 / 月" x={330 + 4 * 210 * 0.62 + 120} y={530} size={44} font="mono" color={C.paper} alpha={0.6 * inRamp(t, 0.6, 0.3)} track={2} />
          <Rule x={200} y={720} w={1520} h={1} color={C.paper} alpha={0.2} progress={easeOutCubic(prog(t, 0.5, 0.9))} />
          <Kinetic text="月供之外，还有一笔折旧" x={200} y={764} size={34} color={C.paper} local={t} delay={0.7} step={0.014} track={2} font="sans" weight={500} />
          <ScanBeam local={t} y0={300} y1={830} speed={0.13} alpha={0.08} />
          <Dust local={t} count={10} seed={1017} alpha={0.3} />
        </Camera>
      </GFXLayer>
    );
  }

  // default：20 万 → 翻转 → 9 万，差额 11 万，11÷3≈3.7 万/年
  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={1.0}>
        {header}
        <Txt text="落地价" x={172} y={392} size={22} font="mono" color={C.paper} alpha={0.5 * inRamp(t, 0.04, 0.3)} track={2} />
        <FlipPanel
          local={t}
          at={flipAt}
          dur={0.32}
          x={168}
          y={424}
          w={760}
          h={200}
          front={
            <Box x={0} y={0} w={760} h={200} alpha={1}>
              <Odometer value={newPrice} x={0} y={0} size={168} color={C.paper} local={t} delay={0.04} dur={0.4} digitsAfter={0} suffix=" 万" align="left" glow={0.2} />
              <div style={{ position: 'absolute', left: 0, top: 70, width: 560 * strike, height: 8, background: C.red, opacity: 0.9, transform: 'rotate(-4deg)', transformOrigin: '0% 50%', boxShadow: `0 0 18px ${rgba(C.red, 0.4)}` }} />
            </Box>
          }
          back={
            <Box x={0} y={0} w={760} h={200} alpha={1}>
              <Odometer value={usedPrice} x={0} y={0} size={196} color={C.amber} local={t} delay={flipAt + 0.08} dur={0.32} digitsAfter={0} suffix=" 万" align="left" glow={0.4} />
              <Txt text="三年后残值" x={4} y={190} size={22} font="mono" color={C.amber} alpha={0.7 * diffIn} track={2} />
            </Box>
          }
        />
        <Box x={0} y={0} w={0} h={0} alpha={diffIn} style={{ transform: `translateX(${lerp(30, 0, diffIn)}px)` }}>
          <Txt text="差额" x={1000} y={420} size={22} font="mono" color={C.paper} alpha={0.55} track={3} />
          <OdometerInt value={diff} x={1000} y={452} size={170} color={C.amber} local={t} delay={1.0} dur={0.45} />
          <Txt text="万" x={1178} y={512} size={44} font="sans" color={C.amber} alpha={0.9} track={2} />
        </Box>
        <Rule x={168} y={680} w={W - 336} h={1} color={C.paper} alpha={0.2} progress={easeOutCubic(prog(t, 0.9, 1.3))} />
        <Box x={0} y={0} w={0} h={0} alpha={row2In} style={{ transform: `translateY(${lerp(24, 0, row2In)}px)` }}>
          <OdometerInt value={diff} x={200} y={718} size={96} color={C.paper} local={t} delay={1.4} dur={0.4} />
          <Txt text="÷" x={396} y={736} size={74} font="mono" color={C.paper} alpha={0.7} />
          <OdometerInt value={FACTS.hook.years} x={486} y={726} size={86} color={C.paper} local={t} delay={1.48} dur={0.4} />
          <Txt text="≈" x={630} y={736} size={74} font="mono" color={C.amber} alpha={0.8} />
          <Odometer value={perYear} x={764} y={706} size={104} color={C.amber} local={t} delay={1.56} dur={0.45} digitsAfter={1} suffix=" 万" align="left" glow={0.3} />
          <Txt text="/ 年" x={1226} y={746} size={36} font="sans" color={C.paper} alpha={0.6} track={2} />
          <Txt text="每月 3000 多" x={200} y={842} size={24} font="sans" color={C.paper} alpha={0.45} track={2} />
        </Box>
        <ScanBeam local={t} y0={280} y1={840} speed={0.11} alpha={0.08} />
        <Dust local={t} count={12} seed={1009} alpha={0.35} />
      </Camera>
    </GFXLayer>
  );
}
