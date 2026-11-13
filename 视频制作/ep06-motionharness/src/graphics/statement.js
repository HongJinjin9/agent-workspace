// statement — 大字号编辑型论断：逐行遮罩上浮 + 小字注 + 细线
// 常规镜头居中；a4_hold（第四幕结论，画面上有「再判」印章叠加）改用左栏三行版式，给印章让出右侧。
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
  sceneOpacity,
  prog,
  easeOutCubic,
  lerp,
  clamp,
  el,
} from "./prims.js";

export function mount(ctx) {
  const shot = ctx.shot || {};
  const dur = shot.dur > 0 ? shot.dur : 3;
  const lines = Array.isArray(shot.lines) && shot.lines.length ? shot.lines : ["这不是观点。", "这是热力学。"];
  const note = shot.note || "";
  // the 「再判」 rubber stamp lands at 58% / 54% of frame in this shot: keep the
  // statement block in the left column so the two never fight.
  const stampShot = shot.id === "a4_hold" || /结论/.test(note);

  const S = sceneRoot(ctx, { bg: D.bg });
  const d = S.design;
  darkGround(d, { seed: 609, beam: true });
  evidenceFrame(d, { x: 150, y: 186, w: W - 300, h: 660, alpha: 0.16, tick: 16, rules: false });

  const noteNode = txt(d, {
    text: note,
    x: W / 2,
    y: 258,
    size: 23,
    font: "mono",
    color: D.amber,
    track: 8,
    align: "center",
    alpha: 0,
  });
  const noteW = Math.max(120, note.length * 15 + 80);
  const noteRuleL = rule(d, {
    x: W / 2 - noteW / 2 - 90,
    y: 268,
    w: 120,
    h: 1,
    color: D.amber,
    alpha: 0.45,
    origin: "right",
  });
  const noteRuleR = rule(d, {
    x: W / 2 + noteW / 2 + 90,
    y: 268,
    w: 120,
    h: 1,
    color: D.amber,
    alpha: 0.45,
  });

  // build physical lines: the conclusion shot splits the second sentence at its comma
  let display = lines.slice();
  if (stampShot && display.length === 2) {
    const second = display[1];
    const at = second.indexOf("，");
    if (at > 1 && at < second.length - 1) {
      display = [display[0], second.slice(0, at + 1), second.slice(at + 1)];
    }
  }

  const longest = Math.max(...display.map((l) => l.length));
  const SIZE = stampShot ? 96 : longest <= 8 ? 116 : longest <= 11 ? 104 : longest <= 14 ? 92 : 82;
  const STEP = Math.round(SIZE * 1.4);

  const lineNodes = [];
  let vRule = null;
  if (stampShot) {
    const X = 150;
    const Y0 = 336;
    vRule = el(
      "div",
      `position:absolute;left:${X - 26}px;top:${Y0 - 10}px;width:2px;height:${STEP * 2 + SIZE * 1.1}px;background:${D.amber};opacity:0;transform-origin:50% 0%;transform:scaleY(0);`
    );
    d.append(vRule);
    for (let i = 0; i < display.length; i++) {
      lineNodes.push(
        txt(d, {
          text: display[i],
          x: X,
          y: Y0 + i * STEP,
          size: SIZE,
          font: "serif",
          color: i === display.length - 1 ? D.amber : D.paper,
          track: 3,
          weight: 600,
          alpha: 0,
          lineHeight: 1.3,
        })
      );
    }
  } else {
    const LINE_H = SIZE * 1.34;
    const GAP = 30;
    const totalH = display.length * LINE_H + (display.length - 1) * GAP;
    const startTop = 548 - totalH / 2;
    for (let i = 0; i < display.length; i++) {
      lineNodes.push(
        txt(d, {
          text: display[i],
          x: W / 2,
          y: startTop + i * (LINE_H + GAP),
          size: SIZE,
          font: "serif",
          color: i === 0 ? D.paper : D.amber,
          track: 4,
          weight: 600,
          align: "center",
          alpha: 0,
        })
      );
    }
  }

  const botRule = rule(d, {
    x: W / 2 - 190,
    y: 802,
    w: 380,
    h: 1,
    color: D.paper,
    alpha: 0.3,
    origin: "center",
  });
  meta(d, { x: 150, y: 846, text: "EP06 · STATEMENT", alpha: 0.3, size: 17, track: 3 });
  meta(d, { x: W - 150, y: 846, text: "卷宗 06 · 技术判决", alpha: 0.28, size: 17, track: 3, align: "right" });

  return {
    update(t) {
      d.style.opacity = String(sceneOpacity(t, dur, 0.22));

      const np = easeOutCubic(prog(t, 0.02, 0.5));
      noteNode.style.opacity = String(0.78 * np);
      setRule(noteRuleL, np);
      setRule(noteRuleR, np);

      if (vRule) {
        vRule.style.opacity = String(0.55 * clamp((t - 0.1) / 0.6));
        vRule.style.transform = `scaleY(${clamp(easeOutCubic(prog(t, 0.1, 1.0)))})`;
      }

      for (let i = 0; i < lineNodes.length; i++) {
        const t0 = 0.14 + i * 0.42;
        const p = easeOutCubic(prog(t, t0, t0 + 0.7));
        const n = lineNodes[i];
        n.style.clipPath = `inset(${(1 - p) * 100}% 0% 0% 0%)`;
        const base = stampShot ? "" : "translateX(-50%) ";
        n.style.transform = `${base}translateY(${lerp(22, 0, p)}px)`;
        n.style.letterSpacing = `${lerp(9, 3, p)}px`;
        n.style.opacity = String(clamp(p * 1.2));
      }

      setRule(botRule, easeOutCubic(prog(t, 0.9 + lineNodes.length * 0.35, 1.5 + lineNodes.length * 0.35)));
    },
    dispose() {
      S.dispose();
    },
  };
}
