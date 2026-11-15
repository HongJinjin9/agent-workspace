// 价签 v2：落牌/摆动/翻面（20 万 → 18 万 → 9 万）+ 数字滚动 + 红线拉伸
import { FACTS } from '../data/facts';
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, Camera, Odometer, Kinetic, TagCard, ScanBeam, Dust, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';

export interface PriceTagProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  exhibit?: string;
}

export function PriceTag({ time, from = 0, to = 4, headline = '', sub, exhibit = 'EXHIBIT 24' }: PriceTagProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 4) - from);
  const single = /%/.test(headline) && !/↔/.test(String(sub ?? ''));
  const dip = /掉一半|先崩/.test(headline);
  const drop = /定残值|落下/.test(headline);
  const flip = /透支|下坠/.test(headline);
  const headIn = inRamp(t, 0, 0.26);
  const pairVals = (() => {
    const m = String(sub ?? '').match(/(\d+)\s*万[^\d]*(\d+)\s*万/);
    return m ? [parseFloat(m[1]), parseFloat(m[2])] : [20, 18];
  })();
  const swing = (i: number) => 1.4 * Math.sin(t * 1.6 + i * 2.1) * inRamp(t, 0.4, 0.4);
  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={0.9}>
        <Txt text="PRICE TAG · 两张价签" x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.38} track={3} />
        <Txt text={exhibit} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.32} track={2} align="right" />
        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />
        <Kinetic text={headline} x={168} y={268} size={44} color={C.paper} local={t} delay={0.02} step={0.016} track={2} weight={600} />

        {single ? (
          <Box x={0} y={0} w={0} h={0} alpha={1}>
            {(() => {
              const m = headline.match(/([^\s\d%]+)\s*(\d+(?:\.\d+)?)\s*%/);
              const brand = (m ? m[1] : headline).replace(/[：:·].*$/, '').trim();
              const val = m ? parseFloat(m[2]) : 66.2;
              const pp = easeOutQuint(prog(t, 0.1, 0.5));
              return (
                <Box x={0} y={0} w={0} h={0} alpha={pp} style={{ transform: `translateY(${lerp(-120, 0, pp)}px)` }}>
                  <TagCard x={W / 2 - 260} y={420} w={520} h={330} label="豪华品牌 · 三年保值率" value="" note="" color={C.amber} rot={-2} swing={1.4 * Math.sin(t * 1.7)}>
                    <div style={{ position: 'absolute', left: 28, top: 96, width: 460 }}>
                      <Odometer value={val} x={0} y={0} size={96} color={C.amber} local={t} delay={0.16} dur={0.55} digitsAfter={1} suffix="%" align="left" glow={0.3} />
                    </div>
                    <Txt text={brand} x={28} y={236} size={34} font="serif" color={C.ink} alpha={0.95} track={3} weight={700} />
                    <Txt text={sub ?? '报告最高价签'} x={28} y={284} size={18} font="mono" color={C.inkSoft} alpha={0.6} track={2} />
                  </TagCard>
                </Box>
              );
            })()}
            <Kinetic text="保值率最高的，往往不新" x={W / 2} y={820} size={30} color={C.paper} local={t} delay={0.7} step={0.014} track={2} align="center" font="sans" weight={500} />
          </Box>
        ) : dip ? (
          <Box x={0} y={0} w={0} h={0} alpha={1}>
            {(() => {
              const p1 = easeOutQuint(prog(t, 0.08, 0.46));
              const fall = easeOutCubic(prog(t, 0.7, 2.2));
              return (
                <>
                  <Box x={0} y={0} w={0} h={0} alpha={p1} style={{ transform: `translateY(${lerp(-120, 0, p1) + fall * 40}px)` }}>
                    <TagCard x={440} y={400} w={400} h={320} label="新车 · 落地价" value="" note="" color={C.paper} rot={-2} swing={1.6 * Math.sin(t * 1.6)}>
                      <div style={{ position: 'absolute', left: 28, top: 96, width: 344 }}>
                        <Odometer value={20} x={0} y={0} size={92} color={C.ink} local={t} delay={0.14} dur={0.5} digitsAfter={0} suffix=" 万" align="left" glow={0} />
                      </div>
                      <Txt text="一半" x={28} y={230} size={24} font="mono" color={C.inkSoft} alpha={0.7} track={2} />
                    </TagCard>
                  </Box>
                  <Box x={0} y={0} w={0} h={0} alpha={easeOutQuint(prog(t, 0.55, 0.95))} style={{ transform: `translateY(${lerp(-160, 0, easeOutQuint(prog(t, 0.55, 0.95))) + fall * 90}px)` }}>
                    <TagCard x={1020} y={470} w={400} h={300} label="二手 · 三年残值" value="" note="" color={C.amber} rot={2} swing={1.6 * Math.sin(t * 1.6 + 2)}>
                      <div style={{ position: 'absolute', left: 28, top: 96, width: 344 }}>
                        <Odometer value={9} x={0} y={0} size={92} color={C.amber} local={t} delay={0.6} dur={0.5} digitsAfter={0} suffix=" 万" align="left" glow={0.25} />
                      </div>
                      <Txt text="蒸发一半" x={28} y={214} size={24} font="mono" color={C.red} alpha={0.85} track={2} />
                    </TagCard>
                  </Box>
                  <Txt text="↓ 蒸发一半" x={W / 2} y={820} size={32} font="sans" color={C.red} alpha={0.85 * inRamp(t, 0.8, 0.35)} track={3} align="center" />
                </>
              );
            })()}
          </Box>
        ) : flip ? (
          <Box x={0} y={0} w={0} h={0} alpha={1}>
            {[
              { label: '新车 · 落地价', v: 20, color: C.paper, note: '发布会定价', at: 0.1, tone: 'old' },
              { label: '三年后 · 残值', v: 9, color: C.amber, note: '市场定价', at: 0.55, tone: 'new' },
            ].map((tag, i) => {
              const pp = easeOutQuint(prog(t, tag.at, tag.at + 0.4));
              const dip = easeOutCubic(prog(t, tag.at + 0.2, tag.at + 0.8));
              return (
                <Box key={tag.label} x={0} y={0} w={0} h={0} alpha={pp}>
                  <TagCard x={i === 0 ? 320 : 1080} y={430 + dip * 46} w={470} h={300} label={tag.label} value={tag.note} note="" color={tag.color} rot={i === 0 ? -2 : 2} swing={swing(i)}>
                    <div style={{ position: 'absolute', left: 26, top: 96, width: 418 }}>
                      <Odometer value={tag.v} x={0} y={0} size={84} color={tag.tone === 'old' ? C.ink : C.amber} local={t} delay={tag.at + 0.08} dur={0.5} digitsAfter={0} suffix=" 万" align="left" glow={0.15} />
                    </div>
                  </TagCard>
                </Box>
              );
            })}
            <div style={{ position: 'absolute', left: 790, top: 560, width: 290 * easeOutCubic(prog(t, 0.6, 1.0)), height: 4, background: C.red, opacity: 0.85, transform: 'rotate(6deg)', transformOrigin: '0% 50%' }} />
            <Txt text="↓ 降价透支旧车价" x={W / 2} y={812} size={32} font="sans" color={C.red} alpha={0.85 * inRamp(t, 0.9, 0.34)} track={3} align="center" />
          </Box>
        ) : (
          <Box x={0} y={0} w={0} h={0} alpha={1}>
            {[
              { label: drop ? '新车发布会' : '新车 · 优惠后', v: drop ? 20 : pairVals[0], color: drop ? C.paper : C.amber, note: drop ? '定卖价' : `原 ${pairVals[0]} 万`, x: 384, rot: -2.2, at: 0.08 },
              { label: drop ? '二手车市场' : '二手 · 挂牌价', v: drop ? 9 : pairVals[1], color: C.amber, note: drop ? '定残值' : '三年残值', x: 1180, rot: 2, at: 0.22 },
            ].map((tag, i) => {
              const pp = easeOutQuint(prog(t, tag.at, tag.at + 0.44));
              const fall = drop ? easeOutCubic(prog(t, 0.6, dur)) * 40 : 0;
              return (
                <Box key={tag.label} x={0} y={0} w={0} h={0} alpha={pp} style={{ transform: `translateY(${lerp(-110, 0, pp) + fall}px)` }}>
                  <TagCard x={tag.x} y={412} w={356} h={300} label={tag.label} value="" note="" color={tag.color} rot={tag.rot} swing={swing(i)}>
                    <div style={{ position: 'absolute', left: 26, top: 96, width: 304 }}>
                      <Odometer value={tag.v} x={0} y={0} size={78} color={tag.color === C.paper ? C.ink : C.amber} local={t} delay={tag.at + 0.12} dur={0.5} digitsAfter={0} suffix=" 万" align="left" glow={0.15} />
                    </div>
                    {i === 0 && !drop ? <Txt text={`原 ${pairVals[0]} 万`} x={26} y={218} size={20} font="mono" color={C.inkSoft} alpha={0.6} track={1} style={{ textDecoration: 'line-through', textDecorationColor: C.red }} /> : null}
                  </TagCard>
                </Box>
              );
            })}
            <div style={{ position: 'absolute', left: 770, top: 520, width: 380 * easeOutCubic(prog(t, 0.55, 0.95)), height: 4, background: C.red, opacity: 0.75, transform: 'rotate(6deg)', transformOrigin: '0% 50%' }} />
            <Kinetic text={drop ? '市场定残值 · 发布会定卖价' : '新车优惠一改，二手标尺就变'} x={W / 2} y={806} size={30} color={C.paper} local={t} delay={0.7} step={0.012} track={2} align="center" font="sans" weight={500} />
          </Box>
        )}
        <ScanBeam local={t} y0={260} y1={860} speed={0.12} alpha={0.07} />
        <Dust local={t} count={10} seed={1501} alpha={0.28} />
        <Speckles x={0} y={132} w={1920} h={816} seed={1501} count={12} maxAlpha={0.04} />
      </Camera>
    </GFXLayer>
  );
}
