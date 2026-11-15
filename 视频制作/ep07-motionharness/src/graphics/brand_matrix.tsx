// 品牌矩阵 / 对照刻度 / 参数牌：价签矩阵 + 0–100 刻度对照
import { FACTS } from '../data/facts';
import { C, W, GFXLayer, Txt, Box, Rule, CornerTicks, Speckles, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba } from './prims';

export interface BrandMatrixProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  exhibit?: string;
}

type Row = { name: string; value?: number; note?: string; trend?: 'up' | 'down' | 'flat'; color?: string };

const SCALE_X = 240;
const SCALE_W = 1440;
const SCALE_Y = 676;
const VMAX = 70;

function scalePos(v: number) {
  return SCALE_X + (clamp(v, 0, 100) / VMAX) * SCALE_W;
}

export function BrandMatrix({ time, from = 0, headline = '', sub, exhibit = 'EXHIBIT 10 / 品牌价签' }: BrandMatrixProps) {
  const t = useLocal(time, from);
  const headIn = inRamp(t, 0.02, 0.28);
  const ruleIn = easeOutCubic(prog(t, 0.08, 0.42));
  const param = /参数/.test(headline);
  const newEnergyContrast = /燃油|日系|保时捷/.test(headline);
  const luxury = /豪华/.test(headline);
  const joint = /合资/.test(headline);
  const domestic = /自主/.test(headline);

  const header = (
    <>
      <Txt text="PRICE TAGS · 保值率价签" x={168} y={200} size={18} font="mono" color={C.paper} alpha={0.38} track={3} />
      <Txt text={exhibit} x={W - 168} y={200} size={18} font="mono" color={C.paper} alpha={0.34} track={2} align="right" />
      <CornerTicks x={132} y={176} w={1656} h={690} color={C.paper} alpha={0.11} size={16} />
      <Txt text={headline} x={168} y={270} size={50} font="serif" color={C.paper} alpha={0.94 * headIn} track={2} weight={600} style={{ clipPath: `inset(0% ${(1 - headIn) * 100}% 0% 0%)` }} />
      {sub ? <Txt text={sub} x={170} y={344} size={24} font="mono" color={C.amber} alpha={0.8 * headIn} track={2} /> : null}
      <Rule x={168} y={388} w={1584} h={1} color={C.paper} alpha={0.2} progress={ruleIn} />
    </>
  );

  if (param) {
    // 参数牌：800V / 5C 超充 / 城区智驾 —— 领先一年就旧
    return (
      <GFXLayer>
        {header}
        {FACTS.techParams.map((p, i) => {
          const pp = easeOutQuint(prog(t, 0.2 + i * 0.16, 0.5 + i * 0.16));
          const grey = easeOutCubic(prog(t, 1.1 + i * 0.12, 1.5 + i * 0.12));
          return (
            <Box key={p} x={0} y={0} w={0} h={0} alpha={pp}>
              <div
                style={{
                  position: 'absolute',
                  left: 200 + i * 520,
                  top: 470,
                  width: 460,
                  height: 210,
                  border: `2px solid ${grey > 0 ? rgba(C.metalLight, 0.5) : rgba(C.paper, 0.6)}`,
                  background: 'rgba(10,13,16,.55)',
                  opacity: 1 - grey * 0.55,
                  transform: `translateY(${lerp(26, 0, pp)}px)`,
                }}
              >
                <Txt text={p} x={34} y={70} size={56} font="mono" color={grey > 0.4 ? C.metalLight : C.amber} alpha={1 - grey * 0.4} track={1} weight={700} />
                <Txt text={`PARAM 0${i + 1}`} x={36} y={150} size={14} font="mono" color={C.paper} alpha={0.4 - grey * 0.2} track={2} />
                {grey > 0.5 ? (
                  <Txt text="旧" x={372} y={28} size={62} font="serif" color={C.red} alpha={(grey - 0.5) * 1.6} weight={700} />
                ) : null}
              </div>
            </Box>
          );
        })}
        <Txt text="参数表上的领先，一年就旧" x={W / 2} y={790} size={30} font="sans" color={C.paper} alpha={0.55 * inRamp(t, 1.3, 0.4)} track={2} align="center" />
        <Speckles x={0} y={132} w={1920} h={816} seed={1401} count={16} maxAlpha={0.05} />
      </GFXLayer>
    );
  }

  if (newEnergyContrast) {
    // 0–100% 对照刻度：燃油 50%+ / 日系 54%+ / 保时捷 66.2%
    const marks = [
      { label: '燃油车 · 普遍 50% 以上', v: 50, color: C.paper, active: /燃油/.test(headline) },
      { label: '日系合资 · 54% 以上', v: 54, color: C.amber, active: /日系/.test(headline) },
      { label: '保时捷 · 66.2%', v: 66.2, color: C.red, active: /保时捷/.test(headline) },
    ];
    return (
      <GFXLayer>
        {header}
        <Rule x={SCALE_X} y={SCALE_Y} w={SCALE_W} h={2} color={C.paper} alpha={0.3} progress={ruleIn} />
        {Array.from({ length: 15 }).map((_, i) => {
          const v = i * 5;
          const x = scalePos(v);
          const big = v % 10 === 0;
          return (
            <Box key={i} x={0} y={0} w={0} h={0} alpha={ruleIn}>
              <div style={{ position: 'absolute', left: x, top: SCALE_Y - (big ? 14 : 8), width: 2, height: big ? 14 : 8, background: C.paper, opacity: big ? 0.5 : 0.22 }} />
              {big ? <Txt text={`${v}`} x={x} y={SCALE_Y + 24} size={16} font="mono" color={C.paper} alpha={0.4} track={1} align="center" /> : null}
            </Box>
          );
        })}
        {marks.map((m, i) => {
          const mp = easeOutQuint(prog(t, 0.26 + i * 0.18, 0.56 + i * 0.18));
          const x = scalePos(m.v);
          const col = m.active ? m.color : rgba(m.color === C.red ? C.red : m.color, 0.55);
          return (
            <Box key={m.label} x={0} y={0} w={0} h={0} alpha={mp}>
              <div style={{ position: 'absolute', left: x - 2, top: 420, width: 4, height: 240, background: col, opacity: m.active ? 0.95 : 0.42, boxShadow: m.active ? `0 0 24px ${rgba(m.color, 0.4)}` : undefined }} />
              <Txt text={`${m.v}%`} x={x} y={388} size={54} font="mono" color={col} alpha={m.active ? 1 : 0.5} track={-1} weight={700} align="center" />
              <Txt text={m.label} x={Math.min(x, W - 260)} y={800} size={22} font="mono" color={C.paper} alpha={m.active ? 0.85 : 0.4} track={1} align="center" />
            </Box>
          );
        })}
        <Speckles x={0} y={132} w={1920} h={816} seed={1409} count={16} maxAlpha={0.05} />
      </GFXLayer>
    );
  }

  // 品牌价签矩阵（豪华 / 合资 / 自主）
  let rows: Row[] = [];
  let title = '';
  if (luxury) {
    title = '豪华品牌';
    rows = [
      { name: '保时捷', value: FACTS.luxury.porsche, color: C.amber },
      { name: '雷克萨斯', note: FACTS.luxury.lexus === '强' ? '强' : undefined, color: C.amber },
      { name: '沃尔沃', value: FACTS.luxury.volvo, color: C.paper },
      { name: '捷豹', value: FACTS.luxury.jaguar, color: C.paper },
      { name: '英菲尼迪', value: FACTS.luxury.infiniti, color: C.paper },
    ];
  } else if (joint) {
    title = '合资品牌';
    rows = [
      { name: '本田 / 丰田 / 马自达', note: '近五成', value: 50, color: C.amber, trend: 'flat' },
      { name: '标致 / 斯柯达 / 福特', note: '< 43%', value: 43, color: C.paper, trend: 'down' },
    ];
  } else if (domestic) {
    title = '自主品牌';
    rows = [
      { name: '传祺 / 坦克', note: '领跑', value: 52, color: C.amber, trend: 'flat' },
      { name: '领克 / 长安欧尚 / 极氪', note: '上涨', trend: 'up', color: C.amber },
    ];
  } else {
    title = '品牌价签';
    rows = [
      { name: '保时捷', value: FACTS.luxury.porsche, color: C.amber },
      { name: '沃尔沃', value: FACTS.luxury.volvo, color: C.paper },
      { name: '捷豹', value: FACTS.luxury.jaguar, color: C.paper },
    ];
  }

  return (
    <GFXLayer>
      {header}
      <Txt text={title} x={168} y={420} size={24} font="mono" color={C.amber} alpha={0.72 * ruleIn} track={5} />
      {rows.map((r, i) => {
        const y = 468 + i * 82;
        const rp = easeOutQuint(prog(t, 0.2 + i * 0.12, 0.5 + i * 0.12));
        const col = r.color ?? C.paper;
        return (
          <Box key={r.name} x={0} y={0} w={0} h={0} alpha={rp}>
            <div style={{ position: 'absolute', left: 168, top: y, width: 1584, height: 1, background: C.paper, opacity: 0.14 }} />
            <Txt text={r.name} x={168} y={y + 18} size={32} font="sans" color={C.paper} alpha={0.92} track={2} />
            {r.value != null ? (
              <div style={{ position: 'absolute', left: 1060, top: y + 24, width: (r.value / VMAX) * 560, height: 14, background: rgba(col, 0.22), borderLeft: `3px solid ${col}` }} />
            ) : null}
            <Txt text={r.note ?? (r.value != null ? `${r.value.toFixed(1)}%` : '')} x={1640} y={y + 14} size={40} font="mono" color={col} alpha={0.95} track={-1} weight={700} align="right" />
            {r.trend === 'up' ? <Txt text="↑" x={1690} y={y + 12} size={44} font="mono" color={C.amber} alpha={0.9} /> : null}
            {r.trend === 'down' ? <Txt text="↓" x={1690} y={y + 12} size={44} font="mono" color={C.red} alpha={0.85} /> : null}
          </Box>
        );
      })}
      <Txt text="品牌名仅用于陈述报告数据" x={168} y={802} size={16} font="mono" color={C.paper} alpha={0.3} track={1} />
      <Speckles x={0} y={132} w={1920} h={816} seed={1417} count={16} maxAlpha={0.05} />
    </GFXLayer>
  );
}
