// year_montage — 四年判决「账本」：2020 被判死刑 / 2021 翻了案 / 2025 判它的人开始造它 / 2026 它自己开始退潮
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
  easeOutQuint,
  clamp,
  lerp,
  el,
} from "./prims.js";

export function mount(ctx) {
  const shot = ctx.shot || {};
  const dur = shot.dur > 0 ? shot.dur : 14.4;
  const years =
    Array.isArray(shot.years) && shot.years.length
      ? shot.years
      : [
          ["2020", "被判死刑"],
          ["2021", "翻了案"],
          ["2025", "判它的人开始造它"],
          ["2026", "它自己开始退潮"],
        ];

  const S = sceneRoot(ctx, { bg: D.bg });
  const d = S.design;
  darkGround(d, { seed: 641, beam: true, warm: true });
  evidenceFrame(d, { x: 132, y: 176, w: W - 264, h: 700, alpha: 0.16, tick: 16, rules: false });

  meta(d, { x: 168, y: 208, text: "收束 · 六年四次判决", alpha: 0.6, size: 20, track: 3 });
  meta(d, { x: W - 168, y: 208, text: "2020 — 2026 / 卷宗 06", alpha: 0.4, size: 18, track: 2, align: "right" });
  const headRule = rule(d, { x: 168, y: 246, w: W - 336, h: 1, color: D.paper, alpha: 0.24 });

  // timeline spine
  const spine = el(
    "div",
    `position:absolute;left:342px;top:336px;width:2px;height:480px;background:${D.paper};opacity:0;transform-origin:50% 0%;transform:scaleY(0);`
  );
  d.append(spine);

  const ROW_Y = [352, 470, 596, 722];
  const rows = [];
  for (let i = 0; i < years.length; i++) {
    const final = i === years.length - 1;
    const [year, line] = years[i];
    const node = el(
      "i",
      `position:absolute;left:336px;top:${ROW_Y[i] + 26}px;width:14px;height:14px;background:${
        final ? D.red : D.amber
      };opacity:0;`
    );
    d.append(node);
    const yearNode = txt(d, {
      text: year,
      x: 336,
      y: ROW_Y[i],
      size: 74,
      font: "mono",
      color: final ? D.red : D.amber,
      track: 0,
      align: "right",
      weight: 700,
      alpha: 0,
    });
    const lineNode = txt(d, {
      text: line,
      x: 700,
      y: ROW_Y[i] + 6,
      size: 58,
      font: "serif",
      color: D.paper,
      track: 3,
      weight: 500,
      alpha: 0,
    });
    const rowRule = rule(d, {
      x: 700,
      y: ROW_Y[i] + 88,
      w: 760,
      h: 1,
      color: final ? D.red : D.paper,
      alpha: final ? 0.72 : 0.16,
    });
    rows.push({ node, yearNode, lineNode, rowRule, final });
  }

  meta(d, { x: 168, y: 862, text: "四年 · 四次重写", alpha: 0.28, size: 17, track: 3 });
  meta(d, { x: W - 168, y: 862, text: "EXHIBIT 06 / TIMELINE", alpha: 0.28, size: 17, track: 2, align: "right" });

  // beat times spread across the real shot duration
  const beats = [
    0.14,
    0.14 + (dur - 0.5) * 0.263,
    0.14 + (dur - 0.5) * 0.526,
    0.14 + (dur - 0.5) * 0.789,
  ];

  return {
    update(t) {
      d.style.opacity = String(sceneOpacity(t, dur, 0.22));
      setRule(headRule, easeOutCubic(prog(t, 0.05, 0.7)));
      spine.style.opacity = String(0.26 * clamp((t - 0.15) / 0.8));
      spine.style.transform = `scaleY(${clamp(easeOutCubic(prog(t, 0.15, 2.2)))})`;

      const dimAll = 1 - 0.5 * clamp(easeOutCubic(prog(t, beats[3], beats[3] + 0.9)));
      for (let i = 0; i < rows.length; i++) {
        const r = rows[i];
        const b = beats[i];
        const p = easeOutQuint(prog(t, b, b + 0.62));
        const dim = r.final ? 1 : 0.32 + 0.68 * (i === rows.length - 2 ? dimAll : 1);

        r.node.style.opacity = String(clamp(p * 1.5) * (r.final ? 1 : 0.85));
        r.node.style.transform = `scale(${lerp(2.4, 1, easeOutQuint(prog(t, b, b + 0.35)))})`;

        r.yearNode.style.opacity = String(clamp(p * 1.4) * (r.final ? 1 : 0.92 * dim));
        r.yearNode.style.transform = `translateX(-100%) translateY(${lerp(14, 0, p)}px) scale(${lerp(
          1.18,
          1,
          easeOutQuint(prog(t, b, b + 0.4))
        )})`;

        const lp = clamp(easeOutCubic(prog(t, b + 0.1, b + 0.75)));
        r.lineNode.style.clipPath = `inset(0% ${(1 - lp) * 100}% 0% 0%)`;
        r.lineNode.style.opacity = String(clamp(prog(t, b + 0.1, b + 0.4)) * (r.final ? 1 : 0.35 + 0.6 * dim));
        r.lineNode.style.transform = `translateY(${lerp(12, 0, p)}px)`;
        r.lineNode.style.letterSpacing = `${lerp(7, 2, p)}px`;

        setRule(r.rowRule, easeOutCubic(prog(t, b + 0.25, b + 0.9)));
        r.rowRule.style.opacity = String((r.final ? 0.72 : 0.16) * (r.final ? 1 : 0.5 + 0.5 * dim));
      }

      // final emphasis glow
      const fp = easeOutCubic(prog(t, beats[3] + 1.4, beats[3] + 2.3));
      rows[rows.length - 1].rowRule.style.boxShadow = `0 0 ${18 * fp}px rgba(179,57,46,${0.55 * fp})`;
    },
    dispose() {
      S.dispose();
    },
  };
}
