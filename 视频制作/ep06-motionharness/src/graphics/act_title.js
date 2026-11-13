// act_title — 幕卡：案卷标签滑入 + 幕名 + 年份章砸下 + 细线
import {
  D,
  W,
  H,
  sceneRoot,
  darkGround,
  evidenceFrame,
  rule,
  setRule,
  txt,
  meta,
  tab,
  sceneOpacity,
  prog,
  easeOutCubic,
  easeOutQuint,
  lerp,
  clamp,
  el,
} from "./prims.js";

export function mount(ctx) {
  const shot = ctx.shot || {};
  const dur = shot.dur > 0 ? shot.dur : 3;
  const act = shot.act || "第二幕";
  const actTitle = shot.title || "验证";
  const year = String(shot.year || "2021");
  const actNo = act.replace("第", "").replace("幕", "");

  const S = sceneRoot(ctx, { bg: D.bg });
  const d = S.design;
  darkGround(d, { seed: 602, beam: true, warm: false });

  // huge faint year as a watermark behind everything
  const wm = txt(d, {
    text: year,
    x: W - 60,
    y: 236,
    size: 430,
    font: "mono",
    color: "rgba(233,227,214,0.038)",
    track: -8,
    align: "right",
  });

  evidenceFrame(d, { x: 130, y: 176, w: W - 260, h: 688, alpha: 0.14, tick: 16, rules: false });

  meta(d, { x: 168, y: 202, text: "EP06 · CASE TAB", alpha: 0.38, size: 18, track: 4 });
  meta(d, {
    x: W - 168,
    y: 202,
    text: `ACT ${actNo === "一" ? "01" : actNo === "二" ? "02" : actNo === "三" ? "03" : "04"} / ${year}`,
    alpha: 0.36,
    size: 18,
    track: 4,
    align: "right",
  });

  // paper case-file tab (slides in from left)
  const tabNode = tab(d, {
    x: 168,
    y: 252,
    w: 330,
    h: 104,
    text: act,
    sub: `ACT · ${year}`,
    rot: 0,
  });

  // divider + horizontal rules
  const vRule = el(
    "div",
    `position:absolute;left:1006px;top:392px;width:1px;height:300px;background:${D.paper};opacity:.18;transform-origin:50% 0%;transform:scaleY(0);`
  );
  d.append(vRule);
  const hRule = rule(d, { x: 168, y: 726, w: 1500, h: 1, color: D.paper, alpha: 0.22 });
  const hRule2 = rule(d, { x: 168, y: 250, w: 330, h: 2, color: D.amber, alpha: 0.7 });

  // act name — the first focus
  const name = txt(d, {
    text: actTitle,
    x: 168,
    y: 398,
    size: 186,
    font: "serif",
    color: D.paper,
    track: 12,
    weight: 600,
  });

  // year — big mono numeral stamped in
  const yearLabel = txt(d, {
    text: "YEAR",
    x: W - 168,
    y: 418,
    size: 17,
    font: "mono",
    color: D.amber,
    track: 7,
    align: "right",
    alpha: 0.55,
  });
  const yearNode = txt(d, {
    text: year,
    x: W - 168,
    y: 566,
    size: 208,
    font: "mono",
    color: D.amber,
    track: 0,
    align: "right",
    vAlign: "center",
    weight: 700,
  });

  meta(d, { x: 168, y: 790, text: `${act} · ${actTitle}`, alpha: 0.36, size: 18, track: 4 });
  meta(d, {
    x: W - 168,
    y: 790,
    text: "卷宗 06 · 技术判决",
    alpha: 0.3,
    size: 18,
    track: 3,
    align: "right",
  });

  return {
    update(t) {
      d.style.opacity = String(sceneOpacity(t, dur, 0.18));

      // watermark drifts slowly
      wm.style.transform = `translateX(-100%) translateY(${lerp(26, -8, clamp(t / Math.max(dur, 0.001)))}px)`;

      // tab slides in
      const tp = easeOutQuint(prog(t, 0.05, 0.5));
      tabNode.style.transform = `translateX(${lerp(-560, 0, tp)}px)`;
      tabNode.style.opacity = String(clamp(tp * 1.6));

      setRule(hRule2, easeOutCubic(prog(t, 0.42, 0.9)));

      // act name reveal
      const np = easeOutCubic(prog(t, 0.24, 0.92));
      name.style.clipPath = `inset(${(1 - np) * 100}% 0% 0% 0%)`;
      name.style.transform = `translateY(${lerp(26, 0, np)}px)`;
      name.style.letterSpacing = `${lerp(24, 10, np)}px`;

      // year stamp
      const yp = easeOutQuint(prog(t, 0.6, 0.95));
      yearNode.style.opacity = String(clamp(yp * 1.4));
      yearNode.style.transform = `translateX(-100%) translateY(-50%) scale(${lerp(1.35, 1, yp)}) rotate(${lerp(-2.4, 0, yp)}deg)`;
      yearLabel.style.opacity = String(0.55 * clamp((t - 0.5) / 0.4));

      vRule.style.transform = `scaleY(${easeOutCubic(prog(t, 0.7, 1.3))})`;
      setRule(hRule, easeOutCubic(prog(t, 0.62, 1.24)));
    },
    dispose() {
      S.dispose();
    },
  };
}
