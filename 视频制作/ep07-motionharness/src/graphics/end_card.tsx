// 片尾声明页：片名 + 三条声明（数据来源 / 不构成购买建议 / AI 辅助制作）+ HUMAN_LINE + 来源 + CTA
import { FACTS } from '../data/facts';
import { C, F, W, H, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, SealMark, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';

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
  const g = typeof time === 'number' ? time : from + t;
  const fadeOut = to != null ? clamp((to - g) / 1.2) : 1;
  const pink = Math.min(fadeOut, 1);

  const kickIn = inRamp(t, 0.02, 0.3);
  const titleIn = easeOutCubic(prog(t, 0.1, 0.5));
  const ruleIn = easeOutCubic(prog(t, 0.3, 0.62));
  const declT = [0.5, 0.68, 0.86];
  const bandIn = easeOutCubic(prog(t, 1.12, 1.5));
  const humanIn = inRamp(t, 1.2, 0.34);
  const srcRule = easeOutCubic(prog(t, 1.45, 1.8));
  const ctaIn = easeOutCubic(prog(t, 1.84, 2.2));
  const sealHit = easeOutQuint(prog(t, 1.66, 1.9));
  const sealBleed = clamp((t - 1.7) / 0.9);

  return (
    <GFXLayer>
      <div style={{ position: 'absolute', inset: 0, opacity: pink }}>
        {/* dark formal page */}
        <div
          className="gfx-charcoal"
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            width: W,
            height: H,
            background: `radial-gradient(120% 95% at 50% 26%, #151b22 0%, #0d1116 44%, ${C.bgDeep} 100%)`,
          }}
        />
        <div className="gfx-grid" style={{ position: 'absolute', inset: 0, opacity: 0.4 }} />
        <CornerTicks x={132} y={176} w={W - 264} h={690} color={C.paper} alpha={0.18} size={18} />
        <Rule x={132} y={176} w={W - 264} h={1} color={C.paper} alpha={0.16} progress={ruleIn} />
        <Rule x={132} y={866} w={W - 264} h={1} color={C.paper} alpha={0.16} progress={ruleIn} />

        <Txt text={kicker} x={W / 2} y={228} size={24} font="mono" color={C.paper} alpha={0.6 * kickIn} track={6} align="center" />
        <Txt
          text={title}
          x={W / 2}
          y={286}
          size={54}
          font="serif"
          color={C.paper}
          alpha={0.97 * titleIn}
          track={3}
          weight={600}
          align="center"
          style={{ clipPath: `inset(0% ${(1 - titleIn) * 100}% 0% 0%)` }}
        />
        <Rule x={W / 2 - 260} y={376} w={520} h={2} color={C.amber} alpha={0.8} progress={ruleIn} origin="center" />

        {/* declarations */}
        {decls.slice(0, 3).map((d, i) => {
          const p = easeOutCubic(prog(t, declT[i] ?? 1, (declT[i] ?? 1) + 0.4));
          return (
            <Txt
              key={i}
              text={d}
              x={W / 2}
              y={430 + i * 62}
              size={38}
              font="serif"
              color={C.paper}
              alpha={0.95 * p}
              track={1.5}
              align="center"
              style={{
                clipPath: `inset(0% ${(1 - p) * 100}% 0% 0%)`,
                transform: `translateY(${lerp(8, 0, p)}px)`,
              }}
            />
          );
        })}

        {/* human line — amber on an ink band */}
        <Box x={W / 2 - 590} y={628} w={1180} h={82} alpha={bandIn}>
          <div style={{ position: 'absolute', inset: 0, background: '#12161b', borderLeft: `3px solid ${C.amber}`, borderRight: `3px solid ${C.amber}` }} />
        </Box>
        <Txt
          text={human}
          x={W / 2}
          y={669}
          size={38}
          font="serif"
          color={C.amber}
          alpha={clamp(humanIn) * 0.98}
          track={4}
          weight={600}
          align="center"
          style={{ transform: 'translateY(-50%)' }}
        />

        {/* sources */}
        <Rule x={W / 2 - 380} y={760} w={760} h={1} color={C.paper} alpha={0.22} progress={srcRule} />
        {sources.slice(0, 3).map((s, i) => (
          <Txt
            key={i}
            text={s}
            x={W / 2}
            y={776 + i * 26}
            size={17}
            font="mono"
            color={C.paper}
            alpha={0.52 * inRamp(t, 1.52 + i * 0.08, 0.3)}
            track={0.5}
            align="center"
          />
        ))}

        <Txt
          text={cta}
          x={W / 2}
          y={886}
          size={34}
          font="sans"
          color={C.red}
          alpha={0.92 * ctaIn}
          track={7}
          align="center"
        />
        <Txt text="EP07 · END CARD / 卷宗 07" x={168} y={908} size={15} font="mono" color={C.paper} alpha={0.32} track={2} />
        <Txt text="2026.11.10 · 中国汽车流通协会保值率报告" x={W - 168} y={908} size={15} font="mono" color={C.paper} alpha={0.3} track={1} align="right" />
        {sourceNote ? <Txt text={sourceNote} x={W / 2} y={936} size={13} font="mono" color={C.paper} alpha={0.3} track={1} align="center" /> : null}

        <SealMark x={1600} y={300} size={132} text={seal} sub="EP07" rot={7} color={C.red} hit={sealHit} bleed={sealBleed} blend={false} />
        <Speckles x={0} y={0} w={W} h={H} seed={1201} count={24} maxAlpha={0.05} />
        <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(120% 90% at 50% 45%, transparent 46%, ${rgba('#000000', 0.5)} 100%)` }} />
      </div>
    </GFXLayer>
  );
}
