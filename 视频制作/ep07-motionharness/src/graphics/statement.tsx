// 大字论断 v2：逐字 kinetic + 动线 + 快节奏（2–4.5s 窗口内主要入场 ≤1.2s）
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, Camera, Kinetic, ScanBeam, Dust, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';

export interface StatementProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  exhibit?: string;
}

export function Statement({ time, from = 0, to, headline = '', sub, exhibit = 'EXHIBIT 45' }: StatementProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 3.5) - from);
  const chips = headline.includes('·');
  const list = /、/.test(headline) && !chips;
  const parts = chips ? headline.split('·') : list ? headline.split('、') : headline.includes('：') ? headline.split('：') : headline.split('，');
  const trimmed = parts.map((s) => s.trim()).filter(Boolean);
  const longest = Math.max(...trimmed.map((p) => p.length), 1);
  const fit = Math.floor(1620 / Math.max(1, longest));
  const baseSize = Math.min(chips ? 92 : list ? 88 : longest <= 6 ? 136 : longest <= 9 ? 116 : 100, fit);
  const underline = easeOutCubic(prog(t, 0.9, 1.5));

  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={0.9}>
        <Txt text="STATEMENT" x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.34} track={4} />
        <Txt text={exhibit} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.28} track={2} align="right" />
        <Rule x={168} y={240} w={W - 336} h={1} color={C.paper} alpha={0.16} progress={easeOutCubic(prog(t, 0.04, 0.42))} />
        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />

        {chips ? (
          <Box x={0} y={0} w={0} h={0} alpha={1}>
            {trimmed.map((p, i) => {
              const pp = easeOutQuint(prog(t, 0.1 + i * 0.16, 0.36 + i * 0.16));
              return (
                <Box key={p} x={0} y={0} w={0} h={0} alpha={pp} style={{ transform: `translateY(${lerp(40, 0, pp)}px) scale(${lerp(0.96, 1, pp)})` }}>
                  <div style={{ position: 'absolute', left: 220 + i * 500, top: 470, width: 440, height: 150, border: `1px solid ${rgba(C.paper, 0.28)}`, background: 'rgba(10,13,16,.5)' }}>
                    <Txt text={p} x={220} y={540} size={64} font="mono" color={C.amber} alpha={0.98} track={0} weight={700} align="center" style={{ transform: 'translate(-50%,-50%)' }} />
                    <Txt text={`0${i + 1}`} x={26} y={22} size={16} font="mono" color={C.paper} alpha={0.4} track={2} />
                  </div>
                </Box>
              );
            })}
            <Kinetic text="一年一迭代" x={W / 2} y={716} size={32} color={C.paper} local={t} delay={0.7} track={4} align="center" font="sans" weight={500} />
          </Box>
        ) : list ? (
          <Box x={0} y={0} w={0} h={0} alpha={1}>
            {trimmed.map((p, i) => (
              <Kinetic key={p} text={p} x={240} y={410 + i * 118} size={baseSize} color={i === trimmed.length - 1 ? C.amber : C.paper} local={t} delay={0.06 + i * 0.12} step={0.02} track={4} weight={600} />
            ))}
            {trimmed.map((_, i) => (
              <div key={`sq${i}`} style={{ position: 'absolute', left: 200, top: 420 + i * 118, width: 12, height: 12, background: C.amber, opacity: 0.9 * easeOutCubic(prog(t, 0.1 + i * 0.12, 0.4 + i * 0.12)) }} />
            ))}
          </Box>
        ) : (
          <Box x={0} y={0} w={0} h={0} alpha={1}>
            {trimmed.map((p, i) => {
              const y = trimmed.length === 1 ? 460 : 384 + i * (baseSize * 1.28);
              return <Kinetic key={i} text={p} x={W / 2} y={y} size={baseSize} color={i === 1 ? C.amber : C.paper} local={t} delay={0.05 + i * 0.14} step={0.018} track={3} weight={600} align="center" />;
            })}
            <div
              style={{
                position: 'absolute',
                left: W / 2 - (Math.max(200, (trimmed[trimmed.length - 1]?.length ?? 4) * baseSize * 0.5)) / 2,
                top: (trimmed.length === 1 ? 460 : 384 + (trimmed.length - 1) * baseSize * 1.28) + baseSize * 1.16,
                width: Math.max(200, (trimmed[trimmed.length - 1]?.length ?? 4) * baseSize * 0.5) * underline,
                height: 5,
                background: C.amber,
                opacity: 0.75,
                boxShadow: `0 0 22px ${rgba(C.amber, 0.35)}`,
              }}
            />
            {sub ? <Txt text={sub} x={W / 2} y={(trimmed.length === 1 ? 460 : 384 + (trimmed.length - 1) * baseSize * 1.28) + baseSize * 1.34} size={24} font="mono" color={C.paper} alpha={0.45 * inRamp(t, 0.5, 0.34)} track={2} align="center" /> : null}
          </Box>
        )}
        <ScanBeam local={t} y0={260} y1={860} speed={0.12} alpha={0.07} />
        <Dust local={t} count={10} seed={1801} alpha={0.3} />
        <Speckles x={0} y={132} w={1920} h={816} seed={1801} count={12} maxAlpha={0.04} />
      </Camera>
    </GFXLayer>
  );
}
