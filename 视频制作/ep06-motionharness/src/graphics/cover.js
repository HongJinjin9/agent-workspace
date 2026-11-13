// cover — 卷宗封面：系列小标 + 大标题 wipe + 副题 + 墨红「卷宗 06」落章
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
  seal,
  sceneOpacity,
  prog,
  easeOutCubic,
  lerp,
  clamp,
} from "./prims.js";

export function mount(ctx) {
  const shot = ctx.shot || {};
  const dur = shot.dur > 0 ? shot.dur : 2.8;
  const S = sceneRoot(ctx, { bg: D.bg });
  const d = S.design;

  darkGround(d, { seed: 601, beam: true });
  const frame = evidenceFrame(d, {
    x: 130,
    y: 176,
    w: W - 260,
    h: 688,
    alpha: 0.26,
    tick: 20,
    color: D.paper,
  });

  meta(d, { x: 168, y: 202, text: "CASE FILE · EP06 / 卷宗", alpha: 0.4, size: 19, track: 4 });
  meta(d, {
    x: W - 168,
    y: 202,
    text: "2020 — 2026 · 六年纪录",
    alpha: 0.4,
    size: 19,
    track: 4,
    align: "right",
  });

  const kicker = txt(d, {
    text: shot.kicker || "VIBE 知识共赏 · 第 06 期",
    x: W / 2,
    y: 318,
    size: 26,
    font: "sans",
    color: D.paper,
    track: 12,
    align: "center",
    alpha: 0,
  });

  const title = txt(d, {
    text: shot.title || "他们说，这是最糟糕的方案",
    x: W / 2,
    y: 396,
    size: 88,
    font: "serif",
    color: D.paper,
    track: 4,
    align: "center",
    weight: 600,
  });

  const rule1 = rule(d, {
    x: W / 2 - 280,
    y: 552,
    w: 560,
    h: 1,
    color: D.amber,
    alpha: 0.85,
    origin: "center",
  });

  const sub = txt(d, {
    text: shot.sub || "",
    x: W / 2,
    y: 588,
    size: 32,
    font: "sans",
    color: D.paper,
    track: 2.5,
    align: "center",
    alpha: 0,
  });

  meta(d, { x: 168, y: 842, text: "主题 · 增程式电动车的六年", alpha: 0.3, size: 18, track: 3 });
  meta(d, {
    x: W - 168,
    y: 842,
    text: "AI 辅助制作 · 声明见片尾",
    alpha: 0.28,
    size: 18,
    track: 3,
    align: "right",
  });

  const st = seal(d, {
    x: 1606,
    y: 738,
    size: 146,
    text: "卷宗",
    sub: "06 / 2026",
    rot: -8,
  });

  return {
    update(t) {
      d.style.opacity = String(sceneOpacity(t, dur, 0.26));

      const fr = easeOutCubic(prog(t, 0.08, 0.8));
      setRule(frame.top, fr);
      setRule(frame.bot, fr);

      const kp = easeOutCubic(prog(t, 0.1, 0.62));
      kicker.style.opacity = String(0.72 * kp);
      kicker.style.letterSpacing = `${lerp(20, 7, kp)}px`;
      kicker.style.transform = `translateX(-50%) translateY(${lerp(10, 0, kp)}px)`;

      const tp = easeOutCubic(prog(t, 0.3, 1.12));
      title.style.clipPath = `inset(0% ${(1 - tp) * 100}% 0% 0%)`;
      title.style.letterSpacing = `${lerp(11, 3, tp)}px`;
      title.style.transform = `translateX(-50%) translateY(${lerp(16, 0, tp)}px)`;

      setRule(rule1, easeOutCubic(prog(t, 0.5, 1.05)));

      const sp = easeOutCubic(prog(t, 0.82, 1.42));
      sub.style.opacity = String(0.66 * sp);
      sub.style.transform = `translateX(-50%) translateY(${lerp(8, 0, sp)}px)`;

      st.set(t, 1.55);
    },
    dispose() {
      S.dispose();
    },
  };
}
