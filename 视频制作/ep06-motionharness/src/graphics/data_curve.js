// data_curve — 证据图版：左「增程销量」123 万 / 41 万（柱高 ∝ 数值）+ -9.7%；
// 右「增程份额」10.3% → 7.0%（SVG dash 画出）+ -24.9%。stage1 左 / stage2 右。
import {
  D,
  W,
  sceneRoot,
  darkGround,
  evidenceFrame,
  rule,
  setRule,
  txt,
  meta,
  svgRoot,
  svgEl,
  sceneOpacity,
  prog,
  easeOutCubic,
  clamp,
  lerp,
  countUp,
  fmtInt,
  el,
} from "./prims.js";
import { FACTS } from "../data/facts.js";

export function mount(ctx) {
  const shot = ctx.shot || {};
  const F = (ctx.facts && ctx.facts.FACTS) || FACTS;
  const M = F.market;
  const dur = shot.dur > 0 ? shot.dur : 8;
  const stage = Number(shot.stage) || 1;

  const S = sceneRoot(ctx, { bg: D.bg });
  const d = S.design;
  darkGround(d, { seed: 617, beam: true });
  evidenceFrame(d, { x: 132, y: 176, w: W - 264, h: 700, alpha: 0.16, tick: 16, rules: false });

  meta(d, { x: 168, y: 208, text: "证据图版 · 增程退潮", alpha: 0.6, size: 20, track: 3 });
  meta(d, {
    x: W - 168,
    y: 208,
    text: "EXHIBIT 05 / DATA · 来源：乘联会",
    alpha: 0.4,
    size: 18,
    track: 2,
    align: "right",
  });
  const headRule = rule(d, { x: 168, y: 246, w: W - 336, h: 1, color: D.paper, alpha: 0.24 });

  // ---------------- left panel: 增程销量
  const LX = 200;
  const LW = 720;
  const baseY = 812;
  const hMax = 352;
  const vMax = M.year2025.value;
  const bx1 = 428;
  const bx2 = 704;
  const bw = 164;
  const h1 = (M.year2025.value / vMax) * hMax;
  const h2 = (M.year2026.value / vMax) * hMax;
  const ty1 = baseY - h1;
  const ty2 = baseY - h2;

  txt(d, { text: "增程销量 · 万辆", x: LX, y: 302, size: 22, font: "mono", color: D.paper, track: 3, alpha: 0.6 });
  const lHead = rule(d, { x: LX, y: 332, w: LW, h: 1, color: D.paper, alpha: 0.18 });

  const baseL = el(
    "div",
    `position:absolute;left:${LX}px;top:${baseY}px;width:${LW}px;height:2px;background:${D.paper};opacity:0;`
  );
  d.append(baseL);

  function mkBar(x, color, fill1, fill2) {
    const n = el(
      "div",
      `position:absolute;left:${x - bw / 2}px;top:${baseY}px;width:${bw}px;height:0;opacity:0;background:linear-gradient(180deg, ${fill1} 0%, ${fill2} 60%, rgba(10,10,10,.5) 100%);border-top:2px solid ${color};border-left:1px solid ${color};`
    );
    d.append(n);
    return n;
  }
  const bar1 = mkBar(bx1, D.amber, "rgba(217,164,65,.34)", "rgba(217,164,65,.10)");
  const bar2 = mkBar(bx2, D.cool, "rgba(143,163,184,.26)", "rgba(143,163,184,.07)");

  const n1 = txt(d, { text: "0", x: bx1, y: ty1 - 84, size: 86, font: "mono", color: D.amber, track: 0, align: "center", weight: 700, alpha: 0 });
  n1.style.textShadow = "0 0 24px rgba(217,164,65,.4)";
  const n1u = txt(d, { text: " " + M.year2025.unit, x: bx1 + 92, y: ty1 - 70, size: 34, font: "sans", color: D.amber, alpha: 0 });
  const n2 = txt(d, { text: "0", x: bx2, y: ty2 - 70, size: 60, font: "mono", color: D.cool, track: 0, align: "center", weight: 700, alpha: 0 });
  const n2u = txt(d, { text: " " + M.year2026.unit, x: bx2 + 52, y: ty2 - 60, size: 26, font: "sans", color: D.cool, alpha: 0 });

  const lab1 = txt(d, { text: M.year2025.label, x: bx1, y: baseY + 34, size: 27, font: "sans", color: D.paper, track: 1.5, align: "center", alpha: 0 });
  const lab2 = txt(d, { text: M.year2026.label, x: bx2, y: baseY + 34, size: 27, font: "sans", color: D.paper, track: 1.5, align: "center", alpha: 0 });

  const yoyNum = txt(d, { text: M.yoy, x: bx2, y: 470, size: 62, font: "mono", color: D.amber, track: 0, align: "center", weight: 700, alpha: 0 });
  const yoyLab = txt(d, { text: "1–5 月累计同比", x: bx2, y: 552, size: 21, font: "sans", color: D.paper, track: 2, align: "center", alpha: 0 });

  // ---------------- right panel: 增程份额
  const RX = 1060;
  const RW = 670;
  txt(d, {
    text: "增程份额 · 2025-05 → 2026-05",
    x: RX,
    y: 302,
    size: 22,
    font: "mono",
    color: D.paper,
    track: 3,
    alpha: 0.6,
  });
  const rHead = rule(d, { x: RX, y: 332, w: RW, h: 1, color: D.paper, alpha: 0.18 });

  const px0 = 1136;
  const px1 = 1700;
  const pyB = 812;
  const pyT = 420;
  const sFrom = parseFloat(M.shareFrom);
  const sTo = parseFloat(M.shareTo);
  const sMin = 6;
  const sMax = 11;
  const sy = (v) => pyB - ((v - sMin) / (sMax - sMin)) * (pyB - pyT);
  const yFrom = sy(sFrom);
  const yTo = sy(sTo);

  const axisB = el(
    "div",
    `position:absolute;left:${px0}px;top:${pyB}px;width:${px1 - px0}px;height:1px;background:${D.paper};opacity:0;`
  );
  const axisL = el(
    "div",
    `position:absolute;left:${px0}px;top:${pyT}px;width:1px;height:${pyB - pyT}px;background:${D.paper};opacity:0;`
  );
  d.append(axisB, axisL);
  const tickNodes = [];
  for (let v = sMin; v <= sMax; v++) {
    const y = sy(v);
    const tk = el(
      "div",
      `position:absolute;left:${px0 - 8}px;top:${y}px;width:8px;height:1px;background:${D.paper};opacity:0;`
    );
    const tl = txt(d, {
      text: v + "%",
      x: px0 - 16,
      y,
      size: 17,
      font: "mono",
      color: D.paper,
      track: 0,
      align: "right",
      vAlign: "center",
      alpha: 0,
    });
    d.append(tk);
    tickNodes.push({ tk, tl });
  }
  const xLab1 = txt(d, { text: "2025-05", x: px0, y: 842, size: 18, font: "mono", color: D.paper, track: 1, align: "center", alpha: 0 });
  const xLab2 = txt(d, { text: "2026-05", x: px1, y: 842, size: 18, font: "mono", color: D.paper, track: 1, align: "center", alpha: 0 });

  // SVG share line (drawn with dash offset)
  const svg = svgRoot();
  const line = svgEl("line", {
    x1: px0,
    y1: yFrom,
    x2: px1,
    y2: yTo,
    stroke: D.amber,
    "stroke-width": 3.6,
    "stroke-linecap": "round",
  });
  line.style.filter = "drop-shadow(0 0 9px rgba(217,164,65,.5))";
  const dotA = svgEl("circle", { cx: px0, cy: yFrom, r: 6, fill: D.cool, opacity: 0 });
  dotA.style.filter = "drop-shadow(0 0 8px rgba(143,163,184,.5))";
  const dotB = svgEl("circle", { cx: px1, cy: yTo, r: 7, fill: D.amber, opacity: 0 });
  dotB.style.filter = "drop-shadow(0 0 10px rgba(217,164,65,.6))";
  svg.append(line, dotA, dotB);
  d.append(svg);
  const lineLen = Math.hypot(px1 - px0, yTo - yFrom);

  const pFrom = txt(d, { text: M.shareFrom, x: px0 + 16, y: yFrom - 52, size: 44, font: "mono", color: D.cool, track: 0, alpha: 0, weight: 700 });
  const pTo = txt(d, { text: M.shareTo, x: px1 - 4, y: yTo - 54, size: 48, font: "mono", color: D.amber, track: 0, align: "right", alpha: 0, weight: 700 });
  const mayLab = txt(d, { text: "5 月单月批发 · 同比", x: 1408, y: 712, size: 19, font: "sans", color: D.paper, track: 2, align: "right", alpha: 0 });
  const mayNum = txt(d, { text: M.may, x: 1408, y: 736, size: 46, font: "mono", color: D.amber, track: 0, align: "right", alpha: 0, weight: 700 });

  const foot = txt(d, {
    text: "口径：不同周期仅示意量级；-9.7% 为 2026 年 1–5 月累计同比 · 来源：乘联会",
    x: 200,
    y: 902,
    size: 18,
    font: "mono",
    color: D.paper,
    track: 0.5,
    alpha: 0,
  });

  const divider = el(
    "div",
    `position:absolute;left:980px;top:300px;width:1px;height:600px;background:${D.paper};opacity:0;`
  );
  d.append(divider);

  return {
    update(t) {
      d.style.opacity = String(sceneOpacity(t, dur, 0.2));
      setRule(headRule, easeOutCubic(prog(t, 0.05, 0.6)));
      setRule(lHead, easeOutCubic(prog(t, 0.25, 0.8)));
      setRule(rHead, easeOutCubic(prog(t, 0.4, 0.95)));
      divider.style.opacity = String(0.12 * clamp((t - 0.3) / 0.5));

      const baseIn = clamp((t - 0.15) / 0.5);
      baseL.style.opacity = String(0.5 * baseIn);
      axisB.style.opacity = String((stage === 1 ? 0.22 : 0.5) * clamp((t - 0.5) / 0.7));
      axisL.style.opacity = String((stage === 1 ? 0.18 : 0.45) * clamp((t - 0.5) / 0.7));
      for (const { tk, tl } of tickNodes) {
        tk.style.opacity = String((stage === 1 ? 0.14 : 0.32) * clamp((t - 0.6) / 0.7));
        tl.style.opacity = String((stage === 1 ? 0.16 : 0.42) * clamp((t - 0.6) / 0.7));
      }
      xLab1.style.opacity = String((stage === 1 ? 0.18 : 0.5) * clamp((t - 0.7) / 0.7));
      xLab2.style.opacity = String((stage === 1 ? 0.18 : 0.5) * clamp((t - 0.7) / 0.7));

      let e1, e2;
      if (stage === 1) {
        e1 = easeOutCubic(prog(t, 0.4, 2.5));
        e2 = easeOutCubic(prog(t, 0.7, 2.85));
      } else {
        e1 = 1;
        e2 = 1;
      }
      bar1.style.height = `${h1 * e1}px`;
      bar1.style.top = `${baseY - h1 * e1}px`;
      bar1.style.opacity = String(clamp(e1 * 3));
      bar2.style.height = `${h2 * e2}px`;
      bar2.style.top = `${baseY - h2 * e2}px`;
      bar2.style.opacity = String(clamp(e2 * 3));

      const c1 = stage === 1 ? countUp(M.year2025.value, t, 0.4, 2.5) : M.year2025.value;
      const c2 = stage === 1 ? countUp(M.year2026.value, t, 0.75, 2.9) : M.year2026.value;
      n1.textContent = fmtInt(c1);
      n2.textContent = fmtInt(c2);
      n1.style.top = `${baseY - h1 * e1 - 84}px`;
      n1u.style.top = `${baseY - h1 * e1 - 68}px`;
      n2.style.top = `${baseY - h2 * e2 - 70}px`;
      n2u.style.top = `${baseY - h2 * e2 - 58}px`;
      n1.style.opacity = String(clamp((t - (stage === 1 ? 0.45 : 0.1)) / 0.35));
      n1u.style.opacity = String(0.9 * clamp((t - (stage === 1 ? 0.55 : 0.2)) / 0.4));
      n2.style.opacity = String(clamp((t - (stage === 1 ? 0.8 : 0.1)) / 0.35));
      n2u.style.opacity = String(0.9 * clamp((t - (stage === 1 ? 0.9 : 0.2)) / 0.4));

      const lb1 = easeOutCubic(prog(t, stage === 1 ? 1.3 : 0.2, stage === 1 ? 1.85 : 0.7));
      lab1.style.opacity = String(clamp(lb1));
      const lb2 = easeOutCubic(prog(t, stage === 1 ? 1.6 : 0.5, stage === 1 ? 2.15 : 1.0));
      lab2.style.opacity = String(clamp(lb2));

      const yp = easeOutCubic(prog(t, stage === 1 ? 2.8 : 0.3, stage === 1 ? 3.35 : 0.95));
      yoyNum.style.opacity = String(clamp(yp));
      yoyNum.style.transform = `translateX(-50%) translateY(${lerp(12, 0, yp)}px)`;
      yoyLab.style.opacity = String(0.78 * clamp(easeOutCubic(prog(t, stage === 1 ? 3.0 : 0.5, stage === 1 ? 3.6 : 1.2))));

      // right line: only stage 2 (stage 1 keeps the panel dormant)
      if (stage === 2) {
        const lp = easeOutCubic(prog(t, 1.4, 4.2));
        line.style.strokeDasharray = `${lineLen}`;
        line.style.strokeDashoffset = `${lineLen * (1 - lp)}`;
        dotA.style.opacity = String(clamp(easeOutCubic(prog(t, 1.4, 1.9))));
        dotB.style.opacity = String(clamp(easeOutCubic(prog(t, 4.05, 4.35))));
        const fp = easeOutCubic(prog(t, 2.1, 2.7));
        pFrom.style.opacity = String(clamp(fp));
        pFrom.style.transform = `translateY(${lerp(8, 0, fp)}px)`;
        const tp = easeOutCubic(prog(t, 4.3, 4.9));
        pTo.style.opacity = String(clamp(tp));
        pTo.style.transform = `translateX(-100%) translateY(${lerp(8, 0, tp)}px)`;
        const mp = easeOutCubic(prog(t, 5.35, 6.05));
        mayLab.style.opacity = String(0.62 * clamp(mp));
        mayNum.style.opacity = String(clamp(mp));
        mayNum.style.transform = `translateX(-100%) translateY(${lerp(10, 0, mp)}px)`;
      }
      foot.style.opacity = String(
        0.38 * clamp(easeOutCubic(prog(t, stage === 1 ? 1.0 : 0.7, stage === 1 ? 1.8 : 1.5)))
      );
    },
    dispose() {
      S.dispose();
    },
  };
}
