// bar_compare — 证据图表：13,438 对 12,445（柱高严格 ∝ 数值，等宽数字随柱生长）
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
  const dur = shot.dur > 0 ? shot.dur : 10;
  const stage = Number(shot.stage) || 1;

  const ideal = { value: 13438, ...F.sales.idealOne, ...(stage === 1 ? shot : {}) };
  const vw = { value: 12445, delta: 993, ...F.sales.vwFive, ...(stage === 2 ? shot : {}) };
  const baseY = 786;
  const hMax = 420;
  const vMax = ideal.value;
  const barW = 196;
  const x1 = 620;
  const x2 = 1222;
  const h1 = (ideal.value / vMax) * hMax;
  const h2 = (vw.value / vMax) * hMax;
  const y1 = baseY - h1;
  const y2 = baseY - h2;
  const pct = vw.value > 0 ? ((vw.delta / vw.value) * 100).toFixed(1) : "8.0";

  const S = sceneRoot(ctx, { bg: D.bg });
  const d = S.design;
  darkGround(d, { seed: 613, beam: true });
  evidenceFrame(d, { x: 132, y: 176, w: W - 264, h: 690, alpha: 0.18, tick: 16, rules: false });

  meta(d, { x: 168, y: 208, text: "证据图表 · 单月上险量对比", alpha: 0.6, size: 20, track: 3 });
  meta(d, { x: W - 168, y: 208, text: "EXHIBIT 03 / CHART · 单位：台", alpha: 0.4, size: 18, track: 2, align: "right" });
  const headRule = rule(d, { x: 168, y: 246, w: W - 336, h: 1, color: D.paper, alpha: 0.24 });

  // baseline + grid
  const base = el(
    "div",
    `position:absolute;left:230px;top:${baseY}px;width:${1460}px;height:2px;background:${D.paper};opacity:0;`
  );
  d.append(base);
  const grid = [];
  for (const v of [5000, 10000]) {
    const gy = baseY - (v / vMax) * hMax;
    const ln = el(
      "div",
      `position:absolute;left:230px;top:${gy}px;width:1460px;height:1px;opacity:0;background:repeating-linear-gradient(90deg, rgba(233,227,214,.28) 0 14px, transparent 14px 30px);`
    );
    const lb = txt(d, {
      text: fmtInt(v),
      x: 218,
      y: gy,
      size: 17,
      font: "mono",
      color: D.paper,
      track: 0,
      align: "right",
      vAlign: "center",
      alpha: 0,
    });
    grid.push({ ln, lb });
    d.append(ln);
  }

  function makeBar(x, color, extra) {
    const w = barW;
    const body = el(
      "div",
      `position:absolute;left:${x - w / 2}px;top:0;width:${w}px;height:0;opacity:0;background:linear-gradient(180deg, ${extra.fill1} 0%, ${extra.fill2} 55%, rgba(12,12,12,.55) 100%);border-top:2px solid ${color};border-left:1px solid ${color};box-shadow:0 0 34px ${extra.glow};`
    );
    d.append(body);
    return body;
  }
  const bar1 = makeBar(x1, D.amber, { fill1: "rgba(217,164,65,.34)", fill2: "rgba(217,164,65,.10)", glow: "rgba(217,164,65,.10)" });
  const bar2 = makeBar(x2, D.cool, { fill1: "rgba(143,163,184,.26)", fill2: "rgba(143,163,184,.07)", glow: "rgba(143,163,184,.08)" });
  bar2.style.borderTopColor = D.cool;
  bar2.style.borderLeftColor = D.cool;

  const num1 = txt(d, {
    text: "0",
    x: x1,
    y: y1 - 78,
    size: 92,
    font: "mono",
    color: D.amber,
    track: 0,
    align: "center",
    alpha: 0,
    weight: 700,
  });
  num1.style.textShadow = "0 0 26px rgba(217,164,65,.45)";
  const num2 = txt(d, {
    text: "0",
    x: x2,
    y: y2 - 70,
    size: 80,
    font: "mono",
    color: D.coolSoft || D.cool,
    track: 0,
    align: "center",
    alpha: 0,
    weight: 700,
  });

  const lab1 = txt(d, {
    text: ideal.label || "理想 ONE",
    x: x1,
    y: baseY + 34,
    size: 32,
    font: "sans",
    color: D.paper,
    track: 2,
    align: "center",
    alpha: 0,
  });
  const sub1 = txt(d, {
    text: ideal.sub || "",
    x: x1,
    y: baseY + 78,
    size: 21,
    font: "mono",
    color: D.paper,
    track: 1,
    align: "center",
    alpha: 0,
  });
  const lab2 = txt(d, {
    text: vw.label || "大众五款中大型 SUV",
    x: x2,
    y: baseY + 34,
    size: 32,
    font: "sans",
    color: D.paper,
    track: 2,
    align: "center",
    alpha: 0,
  });
  const sub2 = txt(d, {
    text: vw.sub || "",
    x: x2,
    y: baseY + 78,
    size: 20,
    font: "mono",
    color: D.paper,
    track: 0.5,
    align: "center",
    alpha: 0,
  });

  // ghost outline of the second bar (stage 1 teaser)
  const ghost = el(
    "div",
    `position:absolute;left:${x2 - barW / 2}px;top:${y2}px;width:${barW}px;height:${h2}px;border:2px dashed ${D.cool};opacity:0;`
  );
  d.append(ghost);
  const ghostLabel = txt(d, {
    text: "同一月 · 另一组数字",
    x: x2,
    y: y2 - 42,
    size: 22,
    font: "mono",
    color: D.cool,
    track: 2,
    align: "center",
    alpha: 0,
  });

  // delta bracket (+993 台 / 仅多 8.0%)
  const bx = 1606;
  const yTop = Math.min(y1, y2);
  const yBot = Math.max(y1, y2);
  const dLineTop = el(
    "div",
    `position:absolute;left:${x1 + barW / 2 + 12}px;top:${y1}px;width:${bx - (x1 + barW / 2 + 12)}px;height:1px;opacity:0;background:repeating-linear-gradient(90deg, ${D.amber} 0 12px, transparent 12px 24px);`
  );
  const dLineBot = el(
    "div",
    `position:absolute;left:${x2 + barW / 2 + 12}px;top:${y2}px;width:${bx - (x2 + barW / 2 + 12)}px;height:1px;opacity:0;background:repeating-linear-gradient(90deg, ${D.cool} 0 12px, transparent 12px 24px);`
  );
  const bracket = el(
    "div",
    `position:absolute;left:${bx}px;top:${yTop}px;width:2px;height:${yBot - yTop}px;background:${D.amber};opacity:0;transform-origin:50% 0%;transform:scaleY(0);`
  );
  const capA = el("div", `position:absolute;left:${bx - 10}px;top:${yTop - 1}px;width:22px;height:2px;background:${D.amber};opacity:0;`);
  const capB = el("div", `position:absolute;left:${bx - 10}px;top:${yBot - 1}px;width:22px;height:2px;background:${D.amber};opacity:0;`);
  d.append(dLineTop, dLineBot, bracket, capA, capB);
  const deltaNum = txt(d, {
    text: "+" + fmtInt(vw.delta) + " 台",
    x: bx + 26,
    y: (yTop + yBot) / 2 - 46,
    size: 46,
    font: "mono",
    color: D.amber,
    track: 0,
    alpha: 0,
    weight: 700,
  });
  const deltaPct = txt(d, {
    text: `仅多 ${pct}%`,
    x: bx + 26,
    y: (yTop + yBot) / 2 + 6,
    size: 25,
    font: "sans",
    color: D.paper,
    track: 1.5,
    alpha: 0,
  });

  // NOTE: no bottom summary line here on purpose — the +993 台 / 仅多 8.0% bracket
  // already states it, and a centred note on the sub-label row collided with
  // 「2021-11 · 单月上险（台）」/「途昂 / 途锐 / …」 (film-time fix, see QA qa6).
  meta(d, { x: 168, y: 892, text: "数据来源：中国产经网（引用上险数据）", alpha: 0.34, size: 17, track: 1 });

  return {
    update(t) {
      d.style.opacity = String(sceneOpacity(t, dur, 0.2));
      setRule(headRule, easeOutCubic(prog(t, 0.05, 0.6)));
      base.style.opacity = String(0.5 * clamp((t - 0.08) / 0.4));
      const gA = clamp((t - 0.15) / 0.5);
      for (const g of grid) {
        g.ln.style.opacity = String(0.35 * gA);
        g.lb.style.opacity = String(0.45 * gA);
      }

      let n1 = 0;
      let n2 = 0;
      let e1 = 0;
      let e2 = 0;
      if (stage === 1) {
        e1 = easeOutCubic(prog(t, 0.28, 3.05));
        n1 = countUp(ideal.value, t, 0.28, 3.05);
        bar1.style.height = `${h1 * e1}px`;
        bar1.style.top = `${baseY - h1 * e1}px`;
        bar1.style.opacity = String(clamp(e1 * 3));
        num1.style.top = `${baseY - h1 * e1 - 78}px`;
        num1.textContent = fmtInt(n1);
        num1.style.opacity = String(clamp((t - 0.3) / 0.35));
        // labels
        const lp = easeOutCubic(prog(t, 0.7, 1.25));
        lab1.style.opacity = String(clamp(lp));
        lab1.style.transform = `translateX(-50%) translateY(${lerp(8, 0, lp)}px)`;
        sub1.style.opacity = String(0.62 * clamp(easeOutCubic(prog(t, 1.0, 1.55))));
        // ghost second bar teaser
        const gp = easeOutCubic(prog(t, 5.0, 6.0));
        ghost.style.opacity = String(0.42 * gp);
        ghostLabel.style.opacity = String(0.5 * clamp(easeOutCubic(prog(t, 5.4, 6.2))));
      } else {
        // stage 2: bar 1 already settled, bar 2 grows and stops short
        e1 = 1;
        bar1.style.height = `${h1}px`;
        bar1.style.top = `${y1}px`;
        bar1.style.opacity = "1";
        n1 = countUp(ideal.value, t, 0.05, 0.7);
        num1.textContent = fmtInt(n1);
        num1.style.opacity = "0.96";
        num1.style.top = `${y1 - 78}px`;
        lab1.style.opacity = "1";
        sub1.style.opacity = "0.62";

        e2 = easeOutCubic(prog(t, 0.9, 4.05));
        bar2.style.height = `${h2 * e2}px`;
        bar2.style.top = `${baseY - h2 * e2}px`;
        bar2.style.opacity = String(clamp(e2 * 3));
        n2 = countUp(vw.value, t, 0.9, 4.05);
        num2.textContent = fmtInt(n2);
        num2.style.top = `${baseY - h2 * e2 - 70}px`;
        num2.style.opacity = String(clamp((t - 0.95) / 0.4));
        const lp = easeOutCubic(prog(t, 1.25, 1.8));
        lab2.style.opacity = String(clamp(lp));
        lab2.style.transform = `translateX(-50%) translateY(${lerp(8, 0, lp)}px)`;
        sub2.style.opacity = String(0.62 * clamp(easeOutCubic(prog(t, 1.55, 2.1))));

        // delta bracket after bars settle
        const dp = easeOutCubic(prog(t, 4.35, 5.15));
        dLineTop.style.opacity = String(0.5 * dp);
        dLineBot.style.opacity = String(0.5 * dp);
        bracket.style.transform = `scaleY(${clamp(easeOutCubic(prog(t, 4.5, 5.1)))})`;
        bracket.style.opacity = String(0.85 * dp);
        const capP = clamp(easeOutCubic(prog(t, 5.0, 5.4)));
        capA.style.opacity = String(capP);
        capB.style.opacity = String(capP);
        const dn = easeOutCubic(prog(t, 5.15, 5.75));
        deltaNum.style.opacity = String(clamp(dn));
        deltaNum.style.transform = `translateY(${lerp(12, 0, dn)}px)`;
        deltaPct.style.opacity = String(0.72 * clamp(easeOutCubic(prog(t, 5.45, 6.05))));
      }
    },
    dispose() {
      S.dispose();
    },
  };
}
