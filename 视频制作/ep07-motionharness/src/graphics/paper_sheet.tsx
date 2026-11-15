// 评估单纸页模板：页眉（二手车鉴定评估单 / CASE FILE · EP07）、左侧红线、横线、页脚（EXHIBIT / 来源）
import type { ReactNode } from 'react';

export interface PaperSheetProps {
  time?: number;
  from?: number;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  rot?: number;
  opacity?: number;
  showHeader?: boolean;
  showFooter?: boolean;
  exhibit?: string;
  source?: string;
  pageNo?: string;
  children?: ReactNode;
}

/** full appraisal-sheet page with dossier header/footer. Children are positioned inside the page box. */
export function PaperSheet({
  time,
  from = 0,
  x = 180,
  y = 170,
  w = 1560,
  h = 740,
  rot = 0,
  opacity,
  showHeader = true,
  showFooter = true,
  exhibit = 'EXHIBIT 02',
  source,
  pageNo = 'P.01 / 06',
  children,
}: PaperSheetProps) {
  const t = useLocal(time, from);
  const inP = inRamp(t, 0.01, 0.3);
  const headP = easeOutCubic(prog(t, 0.1, 0.5));
  const footP = inRamp(t, 0.3, 0.35);
  const alpha = opacity ?? inP;

  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        top: 0,
        width: W,
        height: H,
        opacity: alpha,
        transform: `translateY(${lerp(18, 0, inP)}px)`,
      }}
    >
      <Paper x={x} y={y} w={w} h={h} rot={rot}>
        <CornerTicks x={26} y={26} w={w - 52} h={h - 52} color={C.ink} alpha={0.24} size={18} />
        <i style={{ position: 'absolute', left: 96, top: 26, bottom: 26, width: 2, background: C.red, opacity: 0.45 }} />
        <i style={{ position: 'absolute', left: 104, top: 26, bottom: 26, width: 1, background: C.red, opacity: 0.16 }} />
        <div
          className="gfx-fibre"
          style={{
            position: 'absolute',
            inset: 0,
            opacity: 0.35,
            backgroundImage:
              'repeating-linear-gradient(0deg, rgba(74,70,61,.10) 0px, rgba(74,70,61,.10) 1px, transparent 1px, transparent 58px)',
          }}
        />
        {showHeader ? (
          <>
            <Txt text="二手车鉴定评估单" x={136} y={54} size={34} font="serif" color={C.ink} alpha={0.97 * headP} track={4} weight={700} />
            <Txt text="USED CAR RESIDUAL VALUE APPRAISAL" x={138} y={102} size={14} font="mono" color={C.inkSoft} alpha={0.6 * headP} track={2} />
            <Txt text="CASE FILE · EP07" x={w - 72} y={58} size={16} font="mono" color={C.inkSoft} alpha={0.62 * headP} track={3} align="right" />
            <Txt text={exhibit} x={w - 72} y={86} size={14} font="mono" color={C.inkSoft} alpha={0.48 * headP} track={2} align="right" />
            <Rule x={136} y={128} w={w - 208} h={2} color={C.ink} alpha={0.55} progress={easeOutCubic(prog(t, 0.14, 0.5))} />
          </>
        ) : null}
        {showFooter ? (
          <>
            <Rule x={136} y={h - 74} w={w - 208} h={1} color={C.ink} alpha={0.25} progress={footP} />
            <Txt text="评估系统 · APPRAISAL SYSTEM" x={136} y={h - 56} size={14} font="mono" color={C.inkSoft} alpha={0.5 * footP} track={2} />
            <Txt text={pageNo} x={w - 72} y={h - 56} size={14} font="mono" color={C.inkSoft} alpha={0.45 * footP} track={2} align="right" />
            {source ? <Txt text={source} x={136} y={h - 34} size={12} font="mono" color={C.inkSoft} alpha={0.38 * footP} track={1} /> : null}
          </>
        ) : null}
        {children}
      </Paper>
    </div>
  );
}

// 评估单整页：衰减条款 / 三件事 / 总拥有成本公式 —— 纸页 + 页眉页脚
import { FACTS } from '../data/facts';
import { C, H, W, Paper, CornerTicks, Txt, Box, Rule, Speckles, Camera, ScanBeam, Dust, useLocal, inRamp, prog, easeOutCubic, easeOutQuint, lerp, clamp, rgba, RedStroke } from './prims';

export interface PaperSheetBlockProps {
  time?: number;
  from?: number;
  to?: number;
  headline?: string;
  sub?: string | null;
  seg?: string;
  exhibit?: string;
  source?: string;
}

const PAGE = { x: 180, y: 170, w: 1560, h: 740 };

export function PaperSheetBlock({ time, from = 0, to, headline = '', sub, exhibit = 'EXHIBIT 29', source }: PaperSheetBlockProps) {
  const t = useLocal(time, from);
  const dur = Math.max(0.8, (to ?? from + 4) - from);
  const peel = easeOutQuint(prog(t, 0.02, 0.42));
  const formula = /−|-/.test(headline) && /残值/.test(headline);
  const warranty = /8 年|12 万/.test(sub ?? '') || /看不见/.test(headline);
  const headIn = easeOutCubic(prog(t, 0.12, 0.5));

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <Camera local={t} dur={dur} strength={0.8}>
      <PaperSheet time={time} from={from} x={PAGE.x} y={PAGE.y} w={PAGE.w} h={PAGE.h} exhibit={exhibit} source={source} pageNo="P.01 / 06">
        {formula ? (
          <Box x={0} y={0} w={PAGE.w} h={PAGE.h} alpha={1}>
            <Txt text="TOTAL COST OF OWNERSHIP" x={170} y={190} size={16} font="mono" color={C.inkSoft} alpha={0.55 * headIn} track={3} />
            <Txt text="总拥有成本" x={170} y={222} size={48} font="serif" color={C.ink} alpha={0.96 * headIn} track={4} weight={700} />
            {/* three terms */}
            {[
              { label: '落地价', value: '20 万', color: C.ink },
              { label: '−  残值', value: '9 万', color: C.red },
              { label: '+  使用成本', value: '保险 · 电费 · 保养', color: C.amber },
            ].map((term, i) => {
              const pp = easeOutQuint(prog(t, 0.28 + i * 0.2, 0.6 + i * 0.2));
              return (
                <Box key={term.label} x={0} y={0} w={0} h={0} alpha={pp}>
                  <div style={{ position: 'absolute', left: 170 + i * 430, top: 330, width: 390, height: 170, border: `2px solid ${rgba(C.ink, 0.35)}`, background: 'rgba(233,228,216,.4)' }}>
                    <Txt text={term.label} x={26} y={24} size={24} font="mono" color={C.inkSoft} alpha={0.85} track={2} />
                    <Txt text={term.value} x={26} y={78} size={i === 2 ? 30 : 64} font={i === 2 ? 'sans' : 'mono'} color={term.color} alpha={0.98} track={i === 2 ? 1 : -2} weight={700} />
                  </div>
                </Box>
              );
            })}
            <Txt text="−" x={566} y={378} size={72} font="mono" color={C.red} alpha={0.85 * easeOutCubic(prog(t, 0.9, 1.2))} />
            <Txt text="+" x={996} y={378} size={72} font="mono" color={C.amber} alpha={0.85 * easeOutCubic(prog(t, 1.0, 1.3))} />
            <Txt text="买车真正花的钱，不是落地价" x={170} y={574} size={30} font="sans" color={C.inkSoft} alpha={0.9 * inRamp(t, 1.1, 0.4)} track={2} />
            <Txt text={headline} x={170} y={622} size={26} font="mono" color={C.red} alpha={0.8 * inRamp(t, 1.3, 0.4)} track={1} />
          </Box>
        ) : warranty ? (
          <Box x={0} y={0} w={PAGE.w} h={PAGE.h} alpha={1}>
            <Txt text={headline} x={170} y={196} size={72} font="serif" color={C.ink} alpha={0.97 * headIn} track={3} weight={700} style={{ clipPath: `inset(0% ${(1 - headIn) * 100}% 0% 0%)` }} />
            <Txt text={sub ?? ''} x={172} y={300} size={26} font="mono" color={C.inkSoft} alpha={0.85 * inRamp(t, 0.4, 0.4)} track={2} />
            {/* battery capacity timeline */}
            <Txt text="电池健康度" x={170} y={396} size={20} font="mono" color={C.inkSoft} alpha={0.7} track={3} />
            <div style={{ position: 'absolute', left: 170, top: 448, width: 1100, height: 34, background: rgba(C.ink, 0.12) }}>
              <div style={{ position: 'absolute', left: 0, top: 0, width: 1040 * easeOutCubic(prog(t, 0.3, 1.1)), height: 34, background: `linear-gradient(90deg, ${rgba(C.ink, 0.55)}, ${rgba(C.red, 0.55)})` }} />
            </div>
            <Txt text="新车 100%" x={170} y={500} size={20} font="mono" color={C.inkSoft} alpha={0.7} track={1} />
            <Txt text="8 年 / 12 万公里后 · 报价看衰减" x={170 + 1040} y={500} size={20} font="mono" color={C.inkSoft} alpha={0.7} track={1} align="right" />
            <div style={{ position: 'absolute', left: 170, top: 448, width: 2, height: 34, background: C.red }} />
            <div style={{ position: 'absolute', left: 170 + 1040, top: 448, width: 2, height: 34, background: C.red }} />
            <RedStroke d="M 168 514 C 420 498, 700 570, 1040 486" progress={easeOutCubic(prog(t, 0.7, 1.25))} width={5} alpha={0.85} />
            <Txt text="屏幕上看不见衰减" x={170} y={560} size={40} font="serif" color={C.red} alpha={0.95 * inRamp(t, 0.9, 0.4)} track={2} weight={600} />
            <Txt text="报价里全是衰减" x={170} y={624} size={30} font="mono" color={C.inkSoft} alpha={0.85 * inRamp(t, 1.15, 0.4)} track={2} />
            <Txt text="电池是成本大头；检测没标准，衰减看不见" x={170} y={664} size={22} font="sans" color={C.inkSoft} alpha={0.6 * inRamp(t, 1.3, 0.4)} track={1} />
          </Box>
        ) : (
          <Box x={0} y={0} w={PAGE.w} h={PAGE.h} alpha={1}>
            {headline.split('，').map((line, i) => {
              const pp = easeOutCubic(prog(t, 0.14 + i * 0.16, 0.5 + i * 0.16));
              return (
                <Txt
                  key={i}
                  text={line}
                  x={170}
                  y={200 + i * 112}
                  size={84}
                  font="serif"
                  color={C.ink}
                  alpha={0.97 * pp}
                  track={3}
                  weight={700}
                  style={{ clipPath: `inset(0% ${(1 - pp) * 100}% 0% 0%)` }}
                />
              );
            })}
            {/* three numbered slots — this sheet is where the three accounts land */}
            {[0, 1, 2].map((i) => {
              const pp = easeOutQuint(prog(t, 0.5 + i * 0.16, 0.8 + i * 0.16));
              return (
                <Box key={i} x={0} y={0} w={0} h={0} alpha={pp}>
                  <Txt text={`0${i + 1}`} x={170} y={452 + i * 84} size={26} font="mono" color={C.inkSoft} alpha={0.6} track={2} />
                  <div style={{ position: 'absolute', left: 240, top: 462 + i * 84, width: 940, height: 1, background: rgba(C.ink, 0.3) }} />
                  <div style={{ position: 'absolute', left: 236, top: 444 + i * 84, width: 10, height: 10, background: i === 2 ? C.red : C.ink, opacity: 0.8 }} />
                </Box>
              );
            })}
            <Txt text={sub ?? ''} x={170} y={690} size={22} font="mono" color={C.inkSoft} alpha={0.7 * inRamp(t, 1.1, 0.4)} track={2} />
          </Box>
        )}
        <Speckles x={0} y={0} w={PAGE.w} h={PAGE.h} seed={2001} count={20} maxAlpha={0.06} />
      </PaperSheet>
      <Txt text="评估单 · APPRAISAL SHEET" x={168} y={936} size={14} font="mono" color={C.paper} alpha={0.3} track={2} />
      <Txt text={FACTS.warranty} x={W - 168} y={936} size={14} font="mono" color={C.paper} alpha={0.3} track={1} align="right" />
      {/* page-peel: a cream leaf swings away to reveal the sheet (open-the-dossier motion) */}
      <div style={{ position: 'absolute', left: PAGE.x, top: PAGE.y, width: PAGE.w, height: PAGE.h, perspective: 1400, pointerEvents: 'none' }}>
        <div style={{ position: 'absolute', inset: 0, background: `linear-gradient(100deg, #f3eee2 0%, ${C.paperShade} 100%)`, transform: `rotateY(${-118 * peel}deg)`, transformOrigin: '0% 50%', opacity: 1 - peel * 0.9, boxShadow: '0 26px 60px rgba(0,0,0,.45)' }} />
      </div>
      <ScanBeam local={t} y0={240} y1={860} speed={0.1} alpha={0.06} />
      <Dust local={t} count={10} seed={2001} alpha={0.28} />
      </Camera>
    </div>
  );
}
