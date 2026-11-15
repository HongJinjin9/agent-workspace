// 三本账 v2：三张评估纸叠放 → 依次翻开 + 盖章 + 内容行 type-in（电池账带成本堆叠上升）
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, Camera, Kinetic, ScanBeam, Dust, SealMark, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from '../graphics/prims';

export interface LedgerBooksProps {
  time?: number;
  from?: number;
  to?: number;
  index?: 1 | 2 | 3;
  label?: string;
  headline?: string;
  sub?: string | null;
  exhibit?: string;
}

const BOOKS = [
  { n: '01', label: '技术', color: C.amber },
  { n: '02', label: '价格', color: C.paper },
  { n: '03', label: '电池', color: C.red },
];

export function LedgerBooks({ time, from = 0, to = 5, index = 1, label, headline = '', sub, exhibit = 'EXHIBIT 18' }: LedgerBooksProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 4.5) - from);
  const active = clamp(index, 1, 3) - 1;
  const pages = BOOKS.map((b, i) => (i === active ? { ...b, label: label ?? b.label } : b));
  const activeIn = easeOutQuint(prog(t, 0.08, 0.42));
  const openP = easeOutQuint(prog(t, 0.24, 0.72));
  const stampHit = easeOutQuint(prog(t, 0.62, 0.86));
  const stampBleed = clamp((t - 0.66) / 0.9);
  const lineIn = (d: number) => inRamp(t, d, 0.34);

  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={1.0}>
        <Txt text={exhibit} x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.4} track={3} />
        <Txt text="三本账 · THREE LEDGERS" x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.32} track={2} align="right" />
        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />

        {/* stacked ledgers */}
        {pages.map((b, i) => {
          const isActive = i === active;
          const off = i - active;
          const y = 560 + off * 26;
          const x = 1180 + off * 46;
          const rot = -3 + off * 2.2;
          const open = isActive ? openP : easeOutQuint(prog(t, 0.12 + Math.max(0, 2 - i) * 0.08, 0.5));
          return (
            <Box key={b.n} x={0} y={0} w={0} h={0} alpha={isActive ? 1 : 0.55 * clamp(open * 1.4)} style={{ transform: `translateY(${lerp(70, 0, isActive ? activeIn : open)}px)` }}>
              <div
                style={{
                  position: 'absolute',
                  left: x,
                  top: y,
                  width: 420,
                  height: 300,
                  transform: `rotate(${rot}deg) ${isActive ? 'rotateY(-10deg)' : ''} scale(${isActive ? lerp(0.96, 1.06, open) : 0.92})`,
                  transformOrigin: '0% 50%',
                  perspective: 900,
                  background: `linear-gradient(180deg, #f0ebe0 0%, ${C.paper} 52%, ${C.paperShade} 100%)`,
                  boxShadow: '0 30px 70px rgba(0,0,0,.6), inset 0 0 0 1px rgba(80,62,38,.22)',
                  overflow: 'hidden',
                }}
              >
                <div className="gfx-fibre" style={{ position: 'absolute', inset: 0, opacity: 0.7 }} />
                <i style={{ position: 'absolute', left: 24, top: 22, width: 46, height: 46, border: `2px solid ${b.color}`, opacity: 0.8 }} />
                <Txt text={b.n} x={38} y={34} size={22} font="mono" color={b.color} weight={700} />
                <Txt text={`账${b.n === '01' ? '①' : b.n === '02' ? '②' : '③'} ${b.label}`} x={92} y={30} size={30} font="serif" color={C.ink} track={3} weight={700} />
                <Rule x={26} y={92} w={368} h={1} color={C.ink} alpha={0.35} progress={openP} />
                {['检测项', '折 旧', '残 值'].map((row, k) => (
                  <Box key={row} x={0} y={0} w={0} h={0} alpha={isActive ? lineIn(0.34 + k * 0.09) : 0.5}>
                    <Txt text={row} x={28} y={124 + k * 46} size={18} font="mono" color={C.inkSoft} alpha={0.7} track={2} />
                    <div style={{ position: 'absolute', left: 140, top: 136 + k * 46, width: (150 + k * 44) * (isActive ? lineIn(0.4 + k * 0.09) : 1), height: 1, background: C.ink, opacity: 0.3 }} />
                  </Box>
                ))}
                {isActive && b.n === '03' ? null : null}
                <Txt text="CASE FILE · EP07" x={26} y={262} size={12} font="mono" color={C.inkSoft} alpha={0.5} track={2} />
              </div>
            </Box>
          );
        })}

        {/* active ledger copy + stamp */}
        <Box x={0} y={0} w={0} h={0} alpha={activeIn}>
          <Txt text={`账${active === 0 ? '①' : active === 1 ? '②' : '③'}`} x={168} y={330} size={26} font="mono" color={C.amber} alpha={0.85} track={4} />
          <Kinetic text={pages[active].label} x={168} y={378} size={120} color={C.paper} local={t} delay={0.16} step={0.03} track={4} weight={700} />
          {headline ? <Kinetic text={headline} x={172} y={556} size={38} color={C.paper} local={t} delay={0.4} step={0.015} track={2} weight={500} font="sans" /> : null}
          {sub ? <Txt text={sub} x={172} y={612} size={22} font="mono" color={C.amber} alpha={0.7 * lineIn(0.6)} track={2} /> : null}
          <Rule x={172} y={660} w={520} h={1} color={C.paper} alpha={0.24} progress={easeOutCubic(prog(t, 0.5, 0.9))} />
          <SealMark x={560} y={470} size={200} text={active === 2 ? '存疑' : '入账'} rot={-8} color={active === 2 ? C.red : C.amber} hit={stampHit} bleed={stampBleed} blend={false} />
        </Box>

        {/* battery cost stack for book 3 */}
        {active === 2 ? (
          <Box x={0} y={0} w={0} h={0} alpha={1}>
            {[0, 1, 2, 3, 4].map((k) => {
              const p = easeOutQuint(prog(t, 0.5 + k * 0.11, 0.82 + k * 0.11));
              return (
                <div key={k} style={{ position: 'absolute', left: 760 + k * 150, top: 700 - 220 * p, width: 118, height: 220 * p, background: `linear-gradient(180deg, ${rgba(C.red, 0.55)}, ${rgba(C.red, 0.12)})`, borderTop: `2px solid ${C.red}` }} />
              );
            })}
            <Txt text="电池 · 成本大头" x={760} y={742} size={24} font="mono" color={C.paper} alpha={0.6 * lineIn(0.8)} track={2} />
            <Txt text="检测没标准，衰减看不见" x={760} y={788} size={22} font="sans" color={C.paper} alpha={0.45 * lineIn(1.0)} track={1} />
          </Box>
        ) : null}
        <ScanBeam local={t} y0={260} y1={860} speed={0.11} alpha={0.08} />
        <Dust local={t} count={12} seed={2101} alpha={0.32} />
        <Speckles x={0} y={132} w={1920} h={816} seed={2101} count={14} maxAlpha={0.04} />
      </Camera>
    </GFXLayer>
  );
}
