// 品牌价签矩阵 v2：价签升起/落下 + 数字滚动 + 上涨箭头；对照刻度 / 参数对比（复用 tech_params）
import { FACTS } from '../data/facts';
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, Camera, Odometer, Kinetic, TagCard, ScanBeam, Dust, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';
import { TechParams } from './tech_params';

export interface BrandMatrixProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  exhibit?: string;
  mode?: 'rise' | 'fall' | 'matrix';
  title?: string;
  groups?: Array<{ name: string; value?: number; tone?: 'high' | 'low' | 'up'; note?: string }>;
}

const SCALE_X = 240;
const SCALE_W = 1440;
const SCALE_Y = 690;
const VMAX = 70;

export function BrandMatrix({ time, from = 0, to = 5, headline = '', sub, exhibit = 'EXHIBIT 33', title, groups }: BrandMatrixProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 4.5) - from);
  if (/参数/.test(headline)) {
    return <TechParams time={time} from={from} to={to} mode="compare" headline={headline} sub={sub} exhibit={exhibit} />;
  }
  const contrast = /燃油|日系|保时捷/.test(headline);
  const headIn = inRamp(t, 0, 0.26);
  const ruleIn = easeOutCubic(prog(t, 0.05, 0.4));

  const header = (
    <>
      <Txt text="PRICE TAGS · 保值率价签" x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.38} track={3} />
      <Txt text={exhibit} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.32} track={2} align="right" />
      <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.1} size={16} />
      <Kinetic text={headline} x={168} y={266} size={46} color={C.paper} local={t} delay={0.02} step={0.016} track={2} weight={600} />
      {sub ? <Txt text={sub} x={170} y={334} size={22} font="mono" color={C.amber} alpha={0.8 * headIn} track={2} /> : null}
      <Rule x={168} y={376} w={1584} h={1} color={C.paper} alpha={0.2} progress={ruleIn} />
    </>
  );

  if (contrast) {
    const marks = [
      { label: '燃油车 · 普遍 50%+', v: 50, color: C.paper, on: /燃油/.test(headline) },
      { label: '日系合资 · 54%+', v: 54, color: C.amber, on: /日系/.test(headline) },
      { label: '保时捷 · 66.2%', v: 66.2, color: C.red, on: /保时捷/.test(headline) },
    ];
    const xOf = (v: number) => SCALE_X + (clamp(v, 0, 100) / VMAX) * SCALE_W;
    return (
      <GFXLayer>
        <Camera local={t} dur={dur} strength={0.9}>
          {header}
          <Rule x={SCALE_X} y={SCALE_Y} w={SCALE_W} h={2} color={C.paper} alpha={0.35} progress={ruleIn} />
          {Array.from({ length: 15 }).map((_, i) => {
            const v = i * 5;
            const x = xOf(v);
            const big = v % 10 === 0;
            return (
              <Box key={i} x={0} y={0} w={0} h={0} alpha={ruleIn}>
                <div style={{ position: 'absolute', left: x, top: SCALE_Y - (big ? 13 : 7), width: 2, height: big ? 13 : 7, background: C.paper, opacity: big ? 0.5 : 0.22 }} />
                {big ? <Txt text={`${v}`} x={x} y={SCALE_Y + 24} size={16} font="mono" color={C.paper} alpha={0.38} track={1} align="center" /> : null}
              </Box>
            );
          })}
          {marks.map((m, i) => {
            const mp = easeOutQuint(prog(t, 0.2 + i * 0.16, 0.5 + i * 0.16));
            const x = xOf(m.v);
            const breathe = 1 + 0.04 * Math.sin(t * 3 + i);
            return (
              <Box key={m.label} x={0} y={0} w={0} h={0} alpha={mp}>
                <div style={{ position: 'absolute', left: x - 2, top: 430, width: 4, height: 250, background: m.color, opacity: m.on ? 0.95 : 0.4, transform: `scaleY(${breathe})`, transformOrigin: '50% 100%', boxShadow: m.on ? `0 0 26px ${rgba(m.color, 0.45)}` : undefined }} />
                <Odometer value={m.v} x={x} y={392} size={52} color={m.on ? m.color : rgba(m.color, 0.55)} local={t} delay={0.2 + i * 0.16} dur={0.5} digitsAfter={1} suffix="%" align="center" glow={m.on ? 0.3 : 0.1} />
                <Txt text={m.label} x={Math.min(x, W - 280)} y={712} size={22} font="mono" color={C.paper} alpha={m.on ? 0.85 : 0.4} track={1} align="center" />
              </Box>
            );
          })}
          <ScanBeam local={t} y0={260} y1={860} speed={0.11} alpha={0.07} />
          <Dust local={t} count={10} seed={1401} alpha={0.28} />
        </Camera>
      </GFXLayer>
    );
  }

  // 品牌价签矩阵：tags rise / fall
  let list: Array<{ name: string; value?: number; tone?: 'high' | 'low' | 'up'; note?: string }> = groups ?? [];
  let cluster = title ?? '';
  if (!list.length) {
    if (/豪华/.test(headline)) {
      cluster = '豪华品牌';
      list = [
        { name: '保时捷', value: FACTS.luxury.porsche, tone: 'high' },
        { name: '雷克萨斯', note: '强', tone: 'high' },
        { name: '沃尔沃', value: FACTS.luxury.volvo, tone: 'low' },
        { name: '捷豹', value: FACTS.luxury.jaguar, tone: 'low' },
        { name: '英菲尼迪', value: FACTS.luxury.infiniti, tone: 'low' },
      ];
    } else if (/合资/.test(headline)) {
      cluster = '合资品牌';
      list = [
        { name: '本田 / 丰田 / 马自达', tone: 'high', note: '近五成' },
        { name: '标致 / 斯柯达 / 福特', tone: 'low', note: '<43%' },
      ];
    } else if (/自主/.test(headline)) {
      cluster = '自主品牌';
      list = [
        { name: '传祺 / 坦克', tone: 'high', note: '领跑' },
        { name: '领克 / 长安欧尚 / 极氪', tone: 'up', note: '上涨' },
      ];
    } else {
      cluster = '品牌价签';
      list = [
        { name: '保时捷', value: FACTS.luxury.porsche, tone: 'high' },
        { name: '沃尔沃', value: FACTS.luxury.volvo, tone: 'low' },
      ];
    }
  }
  const cols = list.length <= 2 ? list.length : Math.min(3, list.length);
  const tagW = cols === 1 ? 360 : cols === 2 ? 400 : 300;
  const gapX = 70;
  const startX = W / 2 - ((tagW + gapX) * cols - gapX) / 2;
  const rise = /落|跌|衰/.test(headline) ? -1 : 1;

  return (
    <GFXLayer>
      <Camera local={t} dur={dur} strength={0.9}>
        {header}
        <Txt text={cluster} x={168} y={420} size={24} font="mono" color={C.amber} alpha={0.75 * ruleIn} track={5} />
        {list.map((b, i) => {
          const pp = easeOutQuint(prog(t, 0.2 + i * 0.12, 0.56 + i * 0.12));
          const swing = 1.6 * Math.sin(t * 1.8 + i * 1.7) * pp;
          const baseY = 408 + Math.floor(i / cols) * 276;
          const x = startX + (i % cols) * (tagW + gapX);
          const tone = b.tone ?? (b.value && b.value >= 50 ? 'high' : 'low');
          const color = tone === 'high' ? C.amber : tone === 'up' ? C.amber : C.paper;
          return (
            <Box key={b.name} x={0} y={0} w={0} h={0} alpha={pp} style={{ transform: `translateY(${lerp(rise * 90, 0, pp)}px)` }}>
              <TagCard x={x} y={baseY} w={tagW} h={250} label={b.name} value="" note="" color={color} rot={0} swing={swing}>
                {b.value != null ? (
                  <div style={{ position: 'absolute', left: 26, top: 104, width: tagW - 52 }}>
                    <Odometer value={b.value} x={0} y={0} size={Math.min(58, tagW * 0.18)} color={tone === 'low' ? C.inkSoft : C.ink} local={t} delay={0.3 + i * 0.12} dur={0.5} digitsAfter={1} suffix="%" align="left" glow={0} />
                  </div>
                ) : null}
                {b.note ? <Txt text={b.note} x={26} y={190} size={22} font="mono" color={C.inkSoft} alpha={0.75} track={2} /> : null}
                {tone === 'up' ? (
                  <Box x={0} y={0} w={0} h={0} alpha={pp} style={{ transform: `translateY(${lerp(30, 0, pp)}px)` }}>
                    <Txt text="↑" x={tagW - 70} y={80} size={54} font="mono" color={C.red} alpha={0.9} />
                  </Box>
                ) : null}
                {tone === 'low' ? <Txt text="↓" x={tagW - 60} y={78} size={34} font="mono" color={C.red} alpha={0.55} /> : null}
              </TagCard>
            </Box>
          );
        })}
        <Txt text="品牌名仅用于陈述报告数据" x={168} y={806} size={16} font="mono" color={C.paper} alpha={0.3} track={1} />
        <ScanBeam local={t} y0={260} y1={860} speed={0.11} alpha={0.07} />
        <Dust local={t} count={10} seed={1409} alpha={0.28} />
      </Camera>
    </GFXLayer>
  );
}
