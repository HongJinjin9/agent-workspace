// 分屏 v2：左「发布会 · 定卖价」图表屏（不透明）/ 右「二手车场 · 定残值」透明取景框（露出 H3 实拍）
import { FACTS } from '../data/facts';
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Camera, Odometer, Kinetic, ScanBeam, Dust, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from '../graphics/prims';

export interface SplitScreenProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  leftTitle?: string;
  rightTitle?: string;
  exhibit?: string;
}

export function SplitScreen({
  time,
  from = 0,
  to = 4,
  headline = '',
  leftTitle = '新车发布会',
  rightTitle = '二手车市场 · 黄昏',
  exhibit = 'EXHIBIT 47',
}: SplitScreenProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 4) - from);
  const split = easeOutQuint(prog(t, 0.08, 0.5));
  const leftIn = inRamp(t, 0.2, 0.4);
  const rightIn = inRamp(t, 0.45, 0.4);
  const splitX = 980;
  const top = 200;
  const bottom = 880;
  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={0.8}>
        <Txt text={exhibit} x={168} y={168} size={18} font="mono" color={C.paper} alpha={0.4} track={3} />
        <Txt text="SPLIT · 发布会 vs 车场" x={W - 168} y={168} size={18} font="mono" color={C.paper} alpha={0.3} track={2} align="right" />
        <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />

        {/* left: opaque dashboard screen */}
        <Box x={0} y={0} w={0} h={0} alpha={leftIn} style={{ transform: `translateX(${lerp(-60, 0, leftIn)}px)` }}>
          <div style={{ position: 'absolute', left: 150, top, width: splitX - 190, height: bottom - top, background: 'linear-gradient(160deg, #131a22 0%, #0b1015 70%)', border: `1px solid ${rgba(C.paper, 0.16)}`, boxShadow: '0 30px 80px rgba(0,0,0,.6)', overflow: 'hidden' }}>
            <div style={{ position: 'absolute', left: 34, top: 26, width: 10, height: 10, background: C.red, opacity: 0.9, animation: undefined }} />
            <Txt text={`${leftTitle} · 大屏`} x={58} y={20} size={24} font="mono" color={C.paper} alpha={0.8} track={2} />
            <Txt text="NEW CAR LAUNCH" x={36} y={62} size={13} font="mono" color={C.paper} alpha={0.4} track={2} />
            <Rule x={36} y={92} w={splitX - 280} h={1} color={C.paper} alpha={0.24} progress={easeOutCubic(prog(t, 0.3, 0.7))} />
            <Txt text="新车指导价" x={36} y={130} size={22} font="mono" color={C.paper} alpha={0.55} track={2} />
            <Odometer value={FACTS.hook.newPrice} x={36} y={166} size={148} color={C.amber} local={t} delay={0.4} dur={0.5} digitsAfter={0} suffix=" 万" align="left" glow={0.35} />
            <Txt text={FACTS.techParams.join(' · ')} x={36} y={356} size={22} font="mono" color={C.amber} alpha={0.65} track={1} />
            <Rule x={36} y={402} w={splitX - 280} h={1} color={C.paper} alpha={0.16} progress={easeOutCubic(prog(t, 0.6, 0.9))} />
            <Txt text="配置表每一年都在变，标价是一次性定下的" x={36} y={430} size={20} font="sans" color={C.paper} alpha={0.45} track={1} />
            <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 96, background: 'linear-gradient(180deg, transparent, rgba(7,9,12,.9))' }} />
            <Txt text="发布会定卖价" x={36} y={bottom - top - 70} size={34} font="serif" color={C.paper} alpha={0.95} track={3} weight={600} />
          </div>
        </Box>

        {/* right: transparent framed window — H3 behind shows through */}
        <Box x={0} y={0} w={0} h={0} alpha={rightIn} style={{ transform: `translateX(${lerp(60, 0, rightIn)}px)` }}>
          <div style={{ position: 'absolute', left: splitX + 40, top, width: 1700 - splitX, height: bottom - top, border: `1px solid ${rgba(C.amber, 0.35)}` }}>
            <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(7,9,12,.06) 0%, rgba(7,9,12,0) 40%, rgba(7,9,12,.42) 100%)' }} />
            <Txt text={`${rightTitle}`} x={26} y={22} size={22} font="mono" color={C.amber} alpha={0.8} track={2} />
            <Txt text="USED CAR LOT · DUSK" x={26} y={56} size={13} font="mono" color={C.paper} alpha={0.4} track={2} />
            <Txt text="市场定残值" x={26} y={bottom - top - 84} size={34} font="serif" color={C.amber} alpha={0.95} track={3} weight={600} />
            <Odometer value={FACTS.hook.usedPrice} x={26} y={bottom - top - 210} size={116} color={C.amber} local={t} delay={0.7} dur={0.5} digitsAfter={0} suffix=" 万" align="left" glow={0.35} />
            <Txt text="三年后 · 二手残值" x={26} y={bottom - top - 246} size={18} font="mono" color={C.paper} alpha={0.6} track={2} />
          </div>
        </Box>

        {/* center slash */}
        <div style={{ position: 'absolute', left: splitX, top: top - 40, width: 3, height: (bottom - top + 80) * split, background: C.amber, opacity: 0.85, boxShadow: `0 0 22px ${rgba(C.amber, 0.4)}` }} />
        <div style={{ position: 'absolute', left: splitX - 24, top: (top + bottom) / 2 - 24, width: 48, height: 48, borderRadius: '50%', border: `1px solid ${rgba(C.amber, 0.6)}`, background: 'rgba(7,9,12,.7)', opacity: split }} />
        <Txt text="VS" x={splitX} y={(top + bottom) / 2} size={18} font="mono" color={C.amber} alpha={0.9 * split} track={2} align="center" style={{ transform: 'translateY(-50%)' }} />
        {headline ? <Kinetic text={headline} x={W / 2} y={914} size={26} color={C.paper} local={t} delay={0.6} step={0.014} track={2} align="center" font="sans" weight={500} /> : null}
        <ScanBeam local={t} y0={260} y1={840} speed={0.12} alpha={0.07} />
        <Dust local={t} count={10} seed={2501} alpha={0.28} />
      </Camera>
    </GFXLayer>
  );
}
