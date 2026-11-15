// 红笔批注：划价 / 下压箭头 / 三个特征 / 传导链（评估系统的「判断」动作）
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, RedStroke, Camera, ScanBeam, Dust, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';

export interface RedAnnotationProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  exhibit?: string;
}

export function RedAnnotation({ time, from = 0, to, headline = '', sub, exhibit = 'EXHIBIT 22 / 批注' }: RedAnnotationProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 4) - from);
  const headIn = inRamp(t, 0.02, 0.28);
  const chain = /→/.test(headline);
  const three = /三个特征/.test(headline) && !!sub;
  const cut = /两万|划/.test(headline) && !chain;

  const header = (
    <>
      <Txt text="RED PEN · 批注" x={168} y={200} size={18} font="mono" color={C.red} alpha={0.6} track={3} />
      <Txt text={exhibit} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.32} track={2} align="right" />
      <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.11} size={16} />
    </>
  );

  if (chain) {
    const parts = headline.split('→').map((s) => s.trim()).filter(Boolean);
    return (
      <GFXLayer>
      <Camera local={t} dur={dur} strength={0.9}>
        {header}
        <Txt text="传导链" x={168} y={282} size={24} font="mono" color={C.paper} alpha={0.45 * headIn} track={4} />
        {parts.map((p, i) => {
          const pp = easeOutQuint(prog(t, 0.14 + i * 0.3, 0.44 + i * 0.3));
          const x = 200 + i * 520;
          const isLast = i === parts.length - 1;
          return (
            <Box key={p} x={0} y={0} w={0} h={0} alpha={pp}>
              <div
                style={{
                  position: 'absolute',
                  left: x,
                  top: 468,
                  width: 400,
                  height: 132,
                  border: `2px solid ${isLast ? C.red : rgba(C.paper, 0.4)}`,
                  background: isLast ? rgba(C.red, 0.12) : 'rgba(10,13,16,.6)',
                }}
              >
                <Txt text={p} x={28} y={40} size={44} font="serif" color={isLast ? C.red : C.paper} alpha={0.96} track={2} weight={600} />
              </div>
              {i < parts.length - 1 ? (
                <Box x={0} y={0} w={0} h={0} alpha={easeOutCubic(prog(t, 0.4 + i * 0.3, 0.7 + i * 0.3))}>
                  <div style={{ position: 'absolute', left: x + 412, top: 528, width: 90, height: 3, background: C.red, opacity: 0.85 }} />
                  <div style={{ position: 'absolute', left: x + 478, top: 518, width: 0, height: 0, borderTop: '8px solid transparent', borderBottom: '8px solid transparent', borderLeft: `14px solid ${C.red}` }} />
                </Box>
              ) : null}
            </Box>
          );
        })}
        <Txt text="价格战打的不是新车，是三年后的残值" x={W / 2} y={802} size={28} font="sans" color={C.paper} alpha={0.55 * inRamp(t, 1.4, 0.4)} track={2} align="center" />
        <Speckles x={0} y={132} w={1920} h={816} seed={1701} count={16} maxAlpha={0.05} />
      </Camera>
      </GFXLayer>
    );
  }

  if (three) {
    const items = sub.split('·').map((s) => s.trim()).filter(Boolean);
    return (
      <GFXLayer>
      <Camera local={t} dur={dur} strength={0.9}>
        {header}
        <Txt text={headline} x={168} y={286} size={56} font="serif" color={C.paper} alpha={0.96 * headIn} track={2} weight={600} style={{ clipPath: `inset(0% ${(1 - headIn) * 100}% 0% 0%)` }} />
        {items.map((it, i) => {
          const pp = easeOutQuint(prog(t, 0.3 + i * 0.26, 0.6 + i * 0.26));
          const y = 430 + i * 120;
          return (
            <Box key={it} x={0} y={0} w={0} h={0} alpha={pp}>
              <svg width={120} height={120} viewBox="0 0 120 120" style={{ position: 'absolute', left: 220, top: y - 18 }}>
                <circle cx={60} cy={60} r={44} fill="none" stroke={C.red} strokeWidth={6} strokeLinecap="round" strokeDasharray={276} strokeDashoffset={276 * (1 - pp)} transform="rotate(-90 60 60)" opacity={0.9} />
                <path d="M 34 62 L 52 82 L 88 40" fill="none" stroke={C.red} strokeWidth={7} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={110} strokeDashoffset={110 * (1 - easeOutCubic(prog(t, 0.4 + i * 0.26, 0.7 + i * 0.26)))} />
              </svg>
              <Txt text={it} x={320} y={y + 6} size={44} font="serif" color={C.paper} alpha={0.95} track={3} weight={500} />
              <div style={{ position: 'absolute', left: 320, top: y + 74, width: 620, height: 1, background: C.red, opacity: 0.4 }} />
            </Box>
          );
        })}
        <Txt text="保值率高的车，往往不新" x={W / 2} y={802} size={24} font="mono" color={C.paper} alpha={0.42 * inRamp(t, 1.3, 0.4)} track={2} align="center" />
        <Speckles x={0} y={132} w={1920} h={816} seed={1709} count={16} maxAlpha={0.05} />
      </Camera>
      </GFXLayer>
    );
  }

  if (cut) {
    // 新车降两万：20 万被红笔划到 18 万
    const slash = easeOutCubic(prog(t, 0.2, 0.55));
    const toIn = inRamp(t, 0.6, 0.34);
    return (
      <GFXLayer>
      <Camera local={t} dur={dur} strength={0.9}>
        {header}
        <Txt text="收车单 · 昨天 vs 今天" x={168} y={276} size={24} font="mono" color={C.paper} alpha={0.5 * headIn} track={3} />
        <Box x={0} y={0} w={0} h={0} alpha={inRamp(t, 0.04, 0.3)}>
          <div style={{ position: 'absolute', left: 220, top: 400, width: 460, height: 220, background: 'linear-gradient(180deg,#f0ebe0,#e2dbc9)', boxShadow: '0 24px 50px rgba(0,0,0,.5)' }}>
            <div className="gfx-fibre" style={{ position: 'absolute', inset: 0, opacity: 0.7 }} />
            <Txt text="昨天收车价" x={30} y={26} size={20} font="mono" color={C.inkSoft} alpha={0.8} track={2} />
            <Txt text="20 万" x={30} y={70} size={74} font="mono" color={C.ink} alpha={0.95} track={-2} weight={700} />
          </div>
        </Box>
        <RedStroke d="M 232 372 C 392 430, 560 470, 690 512" progress={slash} width={9} alpha={0.92} />
        <Box x={0} y={0} w={0} h={0} alpha={toIn}>
          <div style={{ position: 'absolute', left: 800, top: 400, width: 460, height: 220, background: 'rgba(10,13,16,.6)', border: `2px solid ${C.red}` }}>
            <Txt text="今天新车价" x={30} y={26} size={20} font="mono" color={C.paper} alpha={0.7} track={2} />
            <Txt text="18 万" x={30} y={70} size={74} font="mono" color={C.red} alpha={0.98} track={-2} weight={700} />
          </div>
        </Box>
        <Txt text="−2 万" x={690} y={330} size={46} font="mono" color={C.red} alpha={0.9 * slash} track={-1} weight={700} align="center" />
        <Txt text={headline} x={W / 2} y={710} size={34} font="sans" color={C.paper} alpha={0.88 * inRamp(t, 0.8, 0.36)} track={2} align="center" />
        <Txt text="收车的人，比买车的人更懂价" x={W / 2} y={770} size={24} font="mono" color={C.paper} alpha={0.42 * inRamp(t, 1.0, 0.4)} track={2} align="center" />
        <Speckles x={0} y={132} w={1920} h={816} seed={1717} count={16} maxAlpha={0.05} />
      </Camera>
      </GFXLayer>
    );
  }

  // press：一句判断 + 红笔下压箭头，压在最后一个短句上
  const parts = headline.split('，');
  const head = parts.length > 1 ? parts[0] : headline;
  const pressed = parts.length > 1 ? parts.slice(1).join('，') : '残值';
  const arrowIn = easeOutQuint(prog(t, 0.34, 0.72));
  return (
    <GFXLayer>
      {header}
      <Txt text={head} x={200} y={330} size={60} font="serif" color={C.paper} alpha={0.95 * headIn} track={2} weight={600} style={{ clipPath: `inset(0% ${(1 - headIn) * 100}% 0% 0%)` }} />
      <Box x={0} y={0} w={0} h={0} alpha={arrowIn}>
        <svg width={220} height={240} viewBox="0 0 220 240" style={{ position: 'absolute', left: 520, top: 420 }}>
          <path d="M 110 8 L 110 190" stroke={C.red} strokeWidth={10} strokeLinecap="round" strokeDasharray={182} strokeDashoffset={182 * (1 - arrowIn)} />
          <path d="M 62 146 L 110 200 L 158 146" fill="none" stroke={C.red} strokeWidth={11} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={140} strokeDashoffset={140 * (1 - clamp((arrowIn - 0.4) / 0.6))} />
        </svg>
        <div style={{ position: 'absolute', left: 470, top: 612, width: 520, height: 140, border: `3px solid ${C.red}`, background: rgba(C.red, 0.1) }}>
          <Txt text={pressed} x={260} y={70} size={48} font="serif" color={C.red} alpha={0.98} track={2} weight={700} align="center" style={{ transform: 'translate(-50%,-50%)' }} />
        </div>
      </Box>
      <Txt text="看不见的那部分，才最贵" x={W / 2} y={802} size={24} font="mono" color={C.paper} alpha={0.42 * inRamp(t, 1.0, 0.4)} track={2} align="center" />
      <Speckles x={0} y={132} w={1920} h={816} seed={1723} count={16} maxAlpha={0.05} />
    </GFXLayer>
  );
}
