// end_card — 片尾正式声明页：标题 + 两条 AI 声明 + HUMAN_LINE + 参考资料 + CTA
import {
  D,
  W,
  H,
  sceneRoot,
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
import { FACTS, DECLARATIONS, HUMAN_LINE } from "../data/facts.js";

export function mount(ctx) {
  const shot = ctx.shot || {};
  const dur = shot.dur > 0 ? shot.dur : 15.6;
  const decls = Array.isArray(shot.decls) && shot.decls.length ? shot.decls : DECLARATIONS;
  const human = shot.human || HUMAN_LINE;
  const sources = Array.isArray(shot.sources) && shot.sources.length ? shot.sources : FACTS.sources;
  const cta = shot.cta || "点赞 · 关注，下期见";

  const S = sceneRoot(ctx, { bg: D.bg });
  const d = S.design;
  const page = paperPage(d, { x: 0, y: 0, w: W, h: H, seed: 99 });
  cornerTicks(page, { x: 116, y: 168, w: W - 232, h: 700 }, { color: D.ink, alpha: 0.2, size: 18, thick: 2 });

  meta(page, { text: "EP06 · END CARD", x: 150, y: 174, color: D.inkSoft, alpha: 0.55, size: 18, track: 3 });
  meta(page, {
    text: "卷宗 06 · 结案",
    x: W - 150,
    y: 174,
    color: D.inkSoft,
    alpha: 0.55,
    size: 18,
    track: 3,
    align: "right",
  });
  const headRule = rule(page, { x: 150, y: 208, w: W - 300, h: 1, color: D.ink, alpha: 0.2 });

  const title = txt(page, {
    text: shot.title || "他们说，这是最糟糕的方案",
    x: W / 2,
    y: 266,
    size: 54,
    font: "serif",
    color: D.ink,
    track: 3,
    align: "center",
    weight: 600,
    alpha: 0,
  });
  const titleRule = rule(page, {
    x: W / 2 - 280,
    y: 358,
    w: 560,
    h: 2,
    color: D.amber,
    alpha: 0.9,
    origin: "center",
  });

  // two AI declarations — the prominent reading
  const declNodes = [];
  for (let i = 0; i < decls.length; i++) {
    const n = txt(page, {
      text: decls[i],
      x: W / 2,
      y: 420 + i * 74,
      size: 42,
      font: "serif",
      color: D.ink,
      track: 1.5,
      align: "center",
      weight: 500,
      alpha: 0,
    });
    declNodes.push(n);
  }

  // human line — amber on an ink band
  const bandW = 1180;
  const band = el(
    "div",
    `position:absolute;left:${W / 2 - bandW / 2}px;top:566px;width:${bandW}px;height:86px;background:#14120f;opacity:0;`
  );
  page.append(band);
  const bandRuleL = el(
    "i",
    `position:absolute;left:${W / 2 - bandW / 2 - 90}px;top:566px;width:90px;height:2px;background:${D.amber};opacity:0;`
  );
  const bandRuleR = el(
    "i",
    `position:absolute;left:${W / 2 + bandW / 2}px;top:566px;width:90px;height:2px;background:${D.amber};opacity:0;`
  );
  page.append(bandRuleL, bandRuleR);
  const humanNode = txt(page, {
    text: human,
    x: W / 2,
    y: 566 + 43,
    size: 40,
    font: "serif",
    color: D.amber,
    track: 4,
    align: "center",
    vAlign: "center",
    weight: 600,
    alpha: 0,
  });

  // sources
  const srcRule = rule(page, { x: W / 2 - 380, y: 696, w: 760, h: 1, color: D.ink, alpha: 0.18 });
  const srcNodes = [];
  for (let i = 0; i < sources.length; i++) {
    srcNodes.push(
      txt(page, {
        text: sources[i],
        x: W / 2,
        y: 710 + i * 32,
        size: 21,
        font: "mono",
        color: D.inkSoft,
        track: 0.5,
        align: "center",
        alpha: 0,
      })
    );
  }

  const ctaNode = txt(page, {
    text: cta,
    x: W / 2,
    y: 842,
    size: 36,
    font: "sans",
    color: D.red,
    track: 7,
    align: "center",
    alpha: 0,
  });

  meta(page, { text: "EXHIBIT 07 / END", x: 150, y: 908, color: D.inkSoft, alpha: 0.32, size: 16, track: 3 });
  meta(page, {
    text: "全片终 · 时长 230s",
    x: W - 150,
    y: 908,
    color: D.inkSoft,
    alpha: 0.32,
    size: 16,
    track: 2,
    align: "right",
  });

  const st = seal(page, {
    x: W - 218,
    y: 292,
    size: 122,
    text: "结案",
    sub: "EP06",
    rot: 7,
    color: D.red,
    blend: "multiply",
  });

  return {
    update(t) {
      const fade = clamp((dur - t) / 1.2);
      d.style.opacity = String(sceneOpacity(t, dur, 0.24) * fade);
      const push = 1 + 0.006 * clamp(t / Math.max(dur, 0.001));
      page.style.transform = `translateY(${lerp(8, 0, easeOutCubic(prog(t, 0, 0.4)))}px) scale(${push})`;

      setRule(headRule, easeOutCubic(prog(t, 0.05, 0.55)));

      const tp = easeOutCubic(prog(t, 0.15, 0.72));
      title.style.opacity = String(clamp(tp * 1.2));
      title.style.letterSpacing = `${lerp(8, 3, tp)}px`;
      title.style.transform = `translateX(-50%) translateY(${lerp(10, 0, tp)}px)`;
      setRule(titleRule, easeOutCubic(prog(t, 0.4, 0.95)));

      for (let i = 0; i < declNodes.length; i++) {
        const t0 = 0.55 + i * 0.2;
        const p = easeOutCubic(prog(t, t0, t0 + 0.5));
        declNodes[i].style.opacity = String(clamp(p));
        declNodes[i].style.transform = `translateX(-50%) translateY(${lerp(10, 0, p)}px)`;
        declNodes[i].style.clipPath = `inset(${(1 - p) * 100}% 0% 0% 0%)`;
      }

      const bp = easeOutCubic(prog(t, 1.02, 1.5));
      band.style.opacity = String(clamp(bp));
      band.style.transform = `scaleX(${lerp(0.9, 1, bp)})`;
      bandRuleL.style.opacity = String(0.8 * bp);
      bandRuleR.style.opacity = String(0.8 * bp);
      const hp = easeOutCubic(prog(t, 1.12, 1.62));
      humanNode.style.opacity = String(clamp(hp));
      humanNode.style.letterSpacing = `${lerp(10, 4, hp)}px`;

      setRule(srcRule, easeOutCubic(prog(t, 1.3, 1.8)));
      for (let i = 0; i < srcNodes.length; i++) {
        const p = easeOutCubic(prog(t, 1.38 + i * 0.1, 1.78 + i * 0.1));
        srcNodes[i].style.opacity = String(0.88 * clamp(p));
      }

      const cp = easeOutCubic(prog(t, 1.8, 2.3));
      ctaNode.style.opacity = String(0.92 * clamp(cp));
      ctaNode.style.transform = `translateX(-50%) translateY(${lerp(8, 0, cp)}px)`;

      st.set(t, 1.9);
    },
    dispose() {
      S.dispose();
    },
  };
}
