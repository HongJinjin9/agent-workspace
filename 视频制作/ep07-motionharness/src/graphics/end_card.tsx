// 片尾 v2：声明页 + 缓慢运动（纸面呼吸/扫描线/印章脉冲/逐条 kinetic/末尾淡出）
import { FACTS } from '../data/facts';
import { C, W, H, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, Camera, Kinetic, ScanBeam, Dust, SealMark, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';

export interface EndCardProps {
  time?: number;
  from?: number;
  to?: number;
  title?: string;
  kicker?: string;
  decls?: string[];
  human?: string;
  cta?: string;
  sources?: string[];
  seal?: string;
  sourceNote?: string;
}

export function EndCard({
  time,
  from = 0,
  to,
  title = '三年之后，你的车还值多少钱',
  kicker = 'VIBE 知识共赏 · 第 07 期',
  decls = FACTS.declarations,
  human = '选题、核实与判断，由人完成',
  cta = '点赞 · 关注，下期见',
  sources = FACTS.sources,
  seal = '结案',
  sourceNote,
}: EndCardProps) {
  const t = useLocal(time, from);
  const dur = Math.max(1, (to ?? from + 8) - from);
  const g = typeof time === 'number' ? time : from + t;
  const fadeOut = to != null ? clamp((to - g) / 1.2) : 1;
  const sealHit = easeOutQuint(prog(t, 1.5, 1.74));
  const sealBleed = clamp((t - 1.54) / 0.9);
  const sweep = ((t * 0.16) % 1) * (W + 600) - 300;
  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={0.7} origin="50% 50%">
        <div style={{ position: 'absolute', inset: 0, opacity: fadeOut, background: `radial-gradient(120% 95% at 50% 26%, #151b22 0%, #0d1116 44%, ${C.bgDeep} 100%)` }} />
        <div className="gfx-grid" style={{ position: 'absolute', inset: 0, opacity: 0.35 }} />
        <CornerTicks x={132} y={176} w={W - 264} h={690} color={C.paper} alpha={0.18} size={18} />
        <Rule x={132} y={176} w={W - 264} h={1} color={C.paper} alpha={0.16} progress={easeOutCubic(prog(t, 0.05, 0.5))} />
        <Rule x={132} y={866} w={W - 264} h={1} color={C.paper} alpha={0.16} progress={easeOutCubic(prog(t, 0.1, 0.5))} />
        <Kinetic text={kicker} x={W / 2} y={228} size={24} color={C.paper} local={t} delay={0.02} step={0.012} track={6} font="mono" weight={400} align="center" rise={8} />
        <Kinetic text={title} x={W / 2} y={286} size={54} color={C.paper} local={t} delay={0.1} step={0.018} track={3} weight={600} align="center" />
        <Rule x={W / 2 - 260} y={376} w={520} h={2} color={C.amber} alpha={0.8} progress={easeOutCubic(prog(t, 0.3, 0.6))} origin="center" />
        {decls.slice(0, 3).map((d, i) => (
          <Kinetic key={i} text={d} x={W / 2} y={430 + i * 62} size={38} color={C.paper} local={t} delay={0.36 + i * 0.14} step={0.01} track={1.5} weight={500} align="center" />
        ))}
        <Box x={W / 2 - 590} y={628} w={1180} h={82} alpha={inRamp(t, 1.0, 0.34)} style={{ transform: `scaleX(${lerp(0.94, 1, inRamp(t, 1.0, 0.4))})` }}>
          <div style={{ position: 'absolute', inset: 0, background: '#12161b', borderLeft: `3px solid ${C.amber}`, borderRight: `3px solid ${C.amber}` }} />
        </Box>
        <Kinetic text={human} x={W / 2} y={648} size={38} color={C.amber} local={t} delay={1.1} step={0.015} track={4} weight={600} align="center" />
        <Rule x={W / 2 - 380} y={760} w={760} h={1} color={C.paper} alpha={0.22} progress={easeOutCubic(prog(t, 1.3, 1.65))} />
        {sources.slice(0, 3).map((s, i) => (
          <Txt key={i} text={s} x={W / 2} y={776 + i * 26} size={17} font="mono" color={C.paper} alpha={0.5 * inRamp(t, 1.4 + i * 0.08, 0.3)} track={0.5} align="center" />
        ))}
        <Kinetic text={cta} x={W / 2} y={886} size={34} color={C.red} local={t} delay={1.7} step={0.03} track={7} font="sans" weight={600} align="center" />
        <Txt text="EP07 · END CARD / 卷宗 07" x={168} y={908} size={15} font="mono" color={C.paper} alpha={0.32} track={2} />
        <Txt text="2026.11.10 · 中国汽车流通协会保值率报告" x={W - 168} y={908} size={15} font="mono" color={C.paper} alpha={0.3} track={1} align="right" />
        {sourceNote ? <Txt text={sourceNote} x={W / 2} y={936} size={13} font="mono" color={C.paper} alpha={0.3} track={1} align="center" /> : null}
        <SealMark x={1600} y={300} size={132} text={seal} sub="EP07" rot={7} color={C.red} hit={sealHit} bleed={sealBleed} blend={false} />
        {/* moving light sweep over the page */}
        <div style={{ position: 'absolute', left: sweep, top: 0, width: 300, height: H, background: `linear-gradient(90deg, transparent, ${rgba(C.amber, 0.05)}, transparent)`, transform: 'rotate(8deg)', opacity: 0.8 }} />
        <ScanBeam local={t} y0={200} y1={880} speed={0.08} alpha={0.05} />
        <Dust local={t} count={14} seed={1201} alpha={0.3} />
        <Speckles x={0} y={0} w={W} h={H} seed={1201} count={18} maxAlpha={0.04} />
        <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(120% 90% at 50% 45%, transparent 46%, ${rgba('#000000', 0.5)} 100%)` }} />
      </Camera>
    </GFXLayer>
  );
}
