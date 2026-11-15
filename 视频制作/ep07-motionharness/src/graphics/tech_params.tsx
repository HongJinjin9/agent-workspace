// 参数牌 v2：800V / 5C 超充 / 城区智驾 —— flash 三连砸入 / compare 老车变灰 vs 新车点亮
import { FACTS } from '../data/facts';
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, Camera, Kinetic, ScanBeam, Dust, SealMark, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from '../graphics/prims';

export interface TechParamsProps {
  time?: number;
  from?: number;
  to?: number;
  items?: string[];
  mode?: 'flash' | 'compare';
  headline?: string;
  sub?: string | null;
  exhibit?: string;
}

export function TechParams({ time, from = 0, to = 4, items = FACTS.techParams, mode = 'flash', headline = '', sub, exhibit = 'EXHIBIT 20' }: TechParamsProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 4) - from);
  const headIn = inRamp(t, 0, 0.26);
  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={1.0}>
        <Txt text={exhibit} x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.4} track={3} />
        <Txt text={mode === 'flash' ? 'PARAM FLASH · 一年一迭代' : 'PARAM COMPARE · 落后两代'} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.3} track={2} align="right" />
        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />
        {headline ? <Kinetic text={headline} x={168} y={272} size={42} color={C.paper} local={t} delay={0.02} track={2} weight={600} /> : null}

        {mode === 'flash' ? (
          <Box x={0} y={0} w={0} h={0} alpha={1}>
            {items.map((p, i) => {
              const pp = easeOutQuint(prog(t, 0.06 + i * 0.15, 0.28 + i * 0.15));
              const flash = 1 - clamp((t - (0.06 + i * 0.15)) / 0.45);
              return (
                <Box key={p} x={0} y={0} w={0} h={0} alpha={pp} style={{ transform: `translateY(${lerp(50, 0, pp)}px) scale(${lerp(1.12, 1, pp)})` }}>
                  <div style={{ position: 'absolute', left: 200 + i * 510, top: 460, width: 450, height: 180, border: `2px solid ${rgba(C.amber, 0.45 + flash * 0.5)}`, background: 'rgba(10,13,16,.46)', boxShadow: `0 0 ${40 * flash}px ${rgba(C.amber, 0.25 * flash)}` }}>
                    <Txt text={p} x={225} y={90} size={62} font="mono" color={C.amber} alpha={0.98} track={1} weight={700} align="center" style={{ transform: 'translate(-50%,-50%)' }} />
                    <Txt text={`0${i + 1}`} x={26} y={20} size={15} font="mono" color={C.paper} alpha={0.4} track={2} />
                    <div style={{ position: 'absolute', left: 0, bottom: 0, width: 450 * pp, height: 3, background: C.amber, opacity: 0.7 }} />
                  </div>
                </Box>
              );
            })}
            <Kinetic text="一年一迭代，参数表上的领先，一年就旧" x={W / 2} y={740} size={30} color={C.paper} local={t} delay={0.9} step={0.012} track={2} align="center" font="sans" weight={500} />
          </Box>
        ) : (
          <Box x={0} y={0} w={0} h={0} alpha={1}>
            {[{ k: 'old', title: '三年前的车', dim: true }, { k: 'new', title: '现在的车', dim: false }].map((col, ci) => {
              const cp = easeOutQuint(prog(t, 0.1 + ci * 0.16, 0.4 + ci * 0.16));
              const x = 220 + ci * 760;
              return (
                <Box key={col.k} x={0} y={0} w={0} h={0} alpha={cp} style={{ transform: `translateY(${lerp(40, 0, cp)}px)` }}>
                  <Txt text={col.title} x={x} y={368} size={30} font="sans" color={col.dim ? C.metalLight : C.amber} alpha={0.85} track={3} />
                  {items.map((p, i) => {
                    const pp = inRamp(t, 0.3 + ci * 0.2 + i * 0.08, 0.3);
                    return (
                      <Box key={p} x={0} y={0} w={0} h={0} alpha={pp}>
                        <div style={{ position: 'absolute', left: x, top: 430 + i * 96, width: 620, height: 78, border: `1px solid ${col.dim ? rgba(C.metalLight, 0.35) : rgba(C.amber, 0.5)}`, background: col.dim ? 'rgba(20,24,30,.6)' : 'rgba(10,13,16,.6)' }}>
                          <Txt text={p} x={30} y={468 + i * 96} size={40} font="mono" color={col.dim ? C.metalLight : C.amber} alpha={col.dim ? 0.6 : 0.98} track={1} weight={700} style={{ transform: 'translateY(-50%)' }} />
                          {col.dim ? (
                            <div style={{ position: 'absolute', left: 26, top: 38, width: 560, height: 3, background: C.metalLight, opacity: 0.5, transform: `scaleX(${inRamp(t, 0.8 + i * 0.1, 0.3)})`, transformOrigin: '0% 50%' }} />
                          ) : null}
                        </div>
                      </Box>
                    );
                  })}
                </Box>
              );
            })}
            <SealMark x={800} y={740} size={170} text="落后" sub="两代" rot={-7} color={C.red} hit={easeOutQuint(prog(t, 0.8, 1.04))} bleed={clamp((t - 0.84) / 0.9)} blend={false} />
          </Box>
        )}
        <ScanBeam local={t} y0={260} y1={860} speed={0.12} alpha={0.08} />
        <Dust local={t} count={10} seed={2201} alpha={0.3} />
        <Speckles x={0} y={132} w={1920} h={816} seed={2201} count={12} maxAlpha={0.04} />
      </Camera>
    </GFXLayer>
  );
}
