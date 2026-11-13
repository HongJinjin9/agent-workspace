// evidence_card — 卷宗证据卡：纸页 + 标签 + 大标题 + 副题 + 注记 + 证据角标 + 墨红「证据」章
import {
  D,
  W,
  H,
  sceneRoot,
  darkGround,
  paperPage,
  cornerTicks,
  rule,
  setRule,
  txt,
  meta,
  seal,
  sceneOpacity,
  prog,
  easeOutCubic,
  clamp,
  lerp,
  el,
} from "./prims.js";

// rough advance-width estimator for mixed CJK / latin (unit = em)
function unitsOf(s) {
  let u = 0;
  for (const ch of s) {
    if (/[\u2e80-\u9fff\uff00-\uffef]/.test(ch)) u += 1;
    else if (ch === " ") u += 0.3;
    else if (/[·—、，。：；！？]/.test(ch)) u += 0.55;
    else if (/[A-Z]/.test(ch)) u += 0.72;
    else u += 0.58;
  }
  return u;
}

export function mount(ctx) {
  const shot = ctx.shot || {};
  const dur = shot.dur > 0 ? shot.dur : 4;

  const CW = 1420;
  const CH = 700;
  const CX = (W - CW) / 2;
  const CY = 190;

  const S = sceneRoot(ctx, { bg: D.bg });
  const d = S.design;
  darkGround(d, { seed: 631, beam: true });

  const card = paperPage(d, { x: CX, y: CY, w: CW, h: CH, rot: -0.5, seed: 88 });
  cornerTicks(card, { x: 34, y: 34, w: CW - 68, h: CH - 68 }, { color: D.ink, alpha: 0.28, size: 20, thick: 2 });

  const tagSquare = el("i", `position:absolute;left:72px;top:76px;width:12px;height:12px;background:${D.amber};`);
  card.append(tagSquare);
  const tag = txt(card, {
    text: shot.tag || "证据",
    x: 100,
    y: 70,
    size: 24,
    font: "mono",
    color: D.inkSoft,
    track: 3,
    alpha: 0,
  });
  const item = txt(card, {
    text: "EVIDENCE · 卷宗 06",
    x: CW - 72,
    y: 74,
    size: 18,
    font: "mono",
    color: D.inkSoft,
    track: 2,
    align: "right",
    alpha: 0,
  });
  const tagRule = rule(card, { x: 72, y: 120, w: CW - 144, h: 1, color: D.ink, alpha: 0.22 });

  // title — auto fit to a single line
  const titleText = shot.title || "";
  const maxW = CW - 144;
  const fit = clamp(maxW / Math.max(1, unitsOf(titleText)), 52, 112);
  const title = txt(card, {
    text: titleText,
    x: 72,
    y: 196,
    size: Math.round(fit),
    font: "serif",
    color: D.ink,
    track: 2,
    weight: 600,
    lineHeight: 1.2,
    alpha: 0,
  });
  const titleRule = rule(card, {
    x: 74,
    y: 196 + Math.round(fit) * 1.24 + 16,
    w: 420,
    h: 4,
    color: D.amber,
    alpha: 0.85,
  });

  const sub = txt(card, {
    text: shot.sub || "",
    x: 72,
    y: 214 + Math.round(fit) * 1.24 + 64,
    size: 38,
    font: "sans",
    color: D.inkSoft,
    track: 1.5,
    lineHeight: 1.5,
    maxWidth: CW - 300,
    nowrap: false,
    alpha: 0,
  });

  const noteRule = rule(card, { x: 72, y: CH - 128, w: CW - 144, h: 1, color: D.ink, alpha: 0.18 });
  const note = txt(card, {
    text: shot.note || "",
    x: 74,
    y: CH - 104,
    size: 22,
    font: "mono",
    color: D.inkSoft,
    track: 2,
    alpha: 0,
  });

  const st = seal(card, {
    x: CW - 168,
    y: CH - 168,
    size: 116,
    text: "证据",
    sub: "EP06",
    rot: -7,
    color: D.red,
    blend: "multiply",
  });

  return {
    update(t) {
      d.style.opacity = String(sceneOpacity(t, dur, 0.24));
      const inP = easeOutCubic(prog(t, 0.0, 0.42));
      const push = 1 + 0.014 * clamp(t / Math.max(dur, 0.001));
      card.style.transform = `translateY(${lerp(26, 0, inP)}px) rotate(-0.5deg) scale(${push})`;

      const tagP = easeOutCubic(prog(t, 0.18, 0.68));
      tag.style.opacity = String(0.85 * tagP);
      tag.style.transform = `translateX(${lerp(-16, 0, tagP)}px)`;
      tagSquare.style.opacity = String(tagP);
      item.style.opacity = String(0.55 * easeOutCubic(prog(t, 0.3, 0.85)));
      setRule(tagRule, easeOutCubic(prog(t, 0.22, 0.8)));

      const tp = easeOutCubic(prog(t, 0.38, 1.05));
      title.style.clipPath = `inset(${(1 - tp) * 100}% 0% 0% 0%)`;
      title.style.transform = `translateY(${lerp(18, 0, tp)}px)`;
      title.style.opacity = String(clamp(tp * 1.5));
      setRule(titleRule, easeOutCubic(prog(t, 0.72, 1.25)));

      const sp = easeOutCubic(prog(t, 0.85, 1.45));
      sub.style.opacity = String(0.9 * clamp(sp));
      sub.style.transform = `translateY(${lerp(10, 0, sp)}px)`;

      setRule(noteRule, easeOutCubic(prog(t, 1.15, 1.7)));
      const np = easeOutCubic(prog(t, 1.25, 1.8));
      note.style.opacity = String(0.78 * clamp(np));

      st.set(t, 1.35);
    },
    dispose() {
      S.dispose();
    },
  };
}
