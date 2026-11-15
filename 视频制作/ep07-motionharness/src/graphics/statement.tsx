// 大字论断：参数 / 判断 / 金句（两行遮罩、三词标签、三连排比）
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';

export interface StatementProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  exhibit?: string;
}

export function Statement({ time, from = 0, headline = '', sub, exhibit = 'EXHIBIT 45 / 判断' }: StatementProps) {
  const t = useLocal(time, from);
  const chips = headline.includes('·');
  const list = /、/.test(headline) && !chips;
  const parts = chips ? headline.split('·').map((s) => s.trim()).filter(Boolean) : list ? headline.split('、').map((s) => s.trim()).filter(Boolean) : headline.split('，').map((s) => s.trim()).filter(Boolean);
  const longest = Math.max(...parts.map((p) => p.length), 1);
  const baseSize = chips ? 96 : list ? 88 : longest <= 7 ? 132 : longest <= 10 ? 112 : 96;

  return (
    <GFXLayer>
      <Txt text="STATEMENT" x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.34} track={4} />
      <Txt text={exhibit} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.3} track={2} align="right" />
      <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />

      {chips ? (
        // 800V · 5C 超充 · 城区智驾 —— 快闪参数牌
        <Box x={0} y={0} w={0} h={0} alpha={1}>
          {parts.map((p, i) => {
            const pp = easeOutCubic(prog(t, 0.08 + i * 0.22, 0.42 + i * 0.22));
            return (
              <Box key={p} x={0} y={0} w={0} h={0} alpha={pp}>
                <div style={{ position: 'absolute', left: 220 + i * 500, top: 470, width: 440, height: 150, border: `1px solid ${rgba(C.paper, 0.28)}`, background: 'rgba(10,13,16,.5)' }}>
                  <Txt text={p} x={220} y={540} size={64} font="mono" color={C.amber} alpha={0.98} track={0} weight={700} align="center" style={{ transform: 'translate(-50%,-50%)' }} />
                  <Txt text={`0${i + 1}`} x={26} y={22} size={16} font="mono" color={C.paper} alpha={0.4} track={2} />
                </div>
              </Box>
            );
          })}
          <Txt text="一年一迭代" x={W / 2} y={720} size={30} font="sans" color={C.paper} alpha={0.55 * inRamp(t, 0.9, 0.4)} track={4} align="center" />
        </Box>
      ) : list ? (
        // 给哪台车、哪个品牌、哪套技术打分 —— 三连排比
        <Box x={0} y={0} w={0} h={0} alpha={1}>
          {parts.map((p, i) => {
            const pp = easeOutQuint(prog(t, 0.08 + i * 0.18, 0.42 + i * 0.18));
            return (
              <Box key={p} x={0} y={0} w={0} h={0} alpha={pp}>
                <div style={{ position: 'absolute', left: 200, top: 412 + i * 118, width: 12, height: 12, background: C.amber, opacity: 0.9 }} />
                <Txt text={p} x={240} y={402 + i * 118} size={baseSize} font="serif" color={i === parts.length - 1 ? C.amber : C.paper} alpha={0.96} track={4} weight={600} style={{ clipPath: `inset(0% ${(1 - pp) * 100}% 0% 0%)` }} />
              </Box>
            );
          })}
        </Box>
      ) : (
        // 两行大字（第二行琥珀）
        <Box x={0} y={0} w={0} h={0} alpha={1}>
          {parts.map((p, i) => {
            const pp = easeOutCubic(prog(t, 0.06 + i * 0.2, 0.4 + i * 0.2));
            const y = parts.length === 1 ? 460 : 400 + i * (baseSize * 1.28);
            return (
              <Box key={i} x={0} y={0} w={0} h={0} alpha={1}>
                <Txt
                  text={p}
                  x={W / 2}
                  y={y}
                  size={baseSize}
                  font="serif"
                  color={i === 1 ? C.amber : C.paper}
                  alpha={0.97 * pp}
                  track={lerp(10, 3, pp)}
                  weight={600}
                  align="center"
                  style={{ clipPath: `inset(0% ${(1 - pp) * 100}% 0% 0%)`, transform: `translateX(-50%) translateY(${lerp(16, 0, pp)}px)` }}
                />
              </Box>
            );
          })}
          {sub ? <Txt text={sub} x={W / 2} y={parts.length === 1 ? 640 : 400 + parts.length * baseSize * 1.28 + 34} size={24} font="mono" color={C.paper} alpha={0.45 * inRamp(t, 0.6, 0.4)} track={2} align="center" /> : null}
        </Box>
      )}
      <Speckles x={0} y={132} w={1920} h={816} seed={1801} count={16} maxAlpha={0.05} />
    </GFXLayer>
  );
}
