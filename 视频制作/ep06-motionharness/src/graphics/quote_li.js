// quote_li — 李想八字回应（案卷纸页 + 大字打字机 + 引号 + 落款）
import {
  D,
  T,
  W,
  H,
  sceneRoot,
  paperPage,
  rule,
  setRule,
  txt,
  meta,
  sceneOpacity,
  prog,
  easeOutCubic,
  clamp,
  lerp,
  cursorOn,
  el,
} from "./prims.js";
import { FACTS } from "../data/facts.js";

export function mount(ctx) {
  const shot = ctx.shot || {};
  const dur = shot.dur > 0 ? shot.dur : 3.46;
  const text = shot.text || FACTS.li.quote;

  const SIZE = 124;
  const TRACK = 9;
  const ADV = SIZE + TRACK;
  const X = 300;
  const Y = 468;

  const S = sceneRoot(ctx, { bg: D.bg });
  const d = S.design;
  const page = paperPage(d, { x: 0, y: 0, w: W, h: H, seed: 73 });

  const ruled = el("div", "position:absolute;inset:0;pointer-events:none;");
  ruled.style.backgroundImage =
    "repeating-linear-gradient(0deg, rgba(74,70,61,.10) 0px, rgba(74,70,61,.10) 1px, transparent 1px, transparent 56px)";
  ruled.style.opacity = "0.45";
  page.append(ruled);

  // faint 2021 watermark on the sheet
  const wm = txt(page, {
    text: "2021",
    x: W - 120,
    y: 700,
    size: 300,
    font: "mono",
    color: "rgba(27,26,23,0.05)",
    track: -4,
    align: "right",
  });

  page.append(
    el(
      "i",
      `position:absolute;left:250px;top:132px;width:2px;height:${H - 264}px;background:${D.red};opacity:.42;`
    )
  );
  page.append(
    el(
      "i",
      `position:absolute;left:258px;top:132px;width:1px;height:${H - 264}px;background:${D.red};opacity:.16;`
    )
  );

  meta(page, { text: "CASE FILE · EP06 / 卷宗", x: 150, y: 172, color: D.inkSoft, alpha: 0.62, size: 19, track: 4 });
  meta(page, {
    text: "EXHIBIT 02 · 回应",
    x: W - 150,
    y: 172,
    color: D.inkSoft,
    alpha: 0.62,
    size: 19,
    track: 4,
    align: "right",
  });
  const headRule = rule(page, { x: 150, y: 206, w: W - 300, h: 1, color: D.ink, alpha: 0.22 });

  const openQ = txt(page, {
    text: "“",
    x: 224,
    y: 356,
    size: 210,
    font: "serif",
    color: D.red,
    alpha: 0,
  });

  const quote = txt(page, {
    text: "",
    x: X,
    y: Y,
    size: SIZE,
    font: "serif",
    color: D.ink,
    track: TRACK,
    weight: 500,
    lineHeight: 1.2,
  });

  const cursor = el("div", `position:absolute;left:0;top:0;width:5px;height:112px;background:${D.red};opacity:0;`);
  page.append(cursor);

  const closeQ = txt(page, {
    text: "”",
    x: 0,
    y: 0,
    size: 168,
    font: "serif",
    color: D.red,
    alpha: 0,
  });

  const capRule = rule(page, { x: X, y: 664, w: 210, h: 2, color: D.amber, alpha: 0.9 });
  const speaker = txt(page, {
    text: "—— " + (shot.speaker || FACTS.li.name),
    x: X,
    y: 682,
    size: 40,
    font: "serif",
    color: D.ink,
    track: 2,
    alpha: 0,
    weight: 600,
  });
  const dateL = txt(page, {
    text: `${shot.date || FACTS.li.date}（${shot.source || FACTS.li.source}）`,
    x: X,
    y: 748,
    size: 24,
    font: "mono",
    color: D.inkSoft,
    track: 0.5,
    alpha: 0,
  });

  // amber marker swipe under the last half of the sentence
  const swipe = el(
    "div",
    `position:absolute;left:${X + Math.floor(text.length / 2) * ADV}px;top:${Y + SIZE + 20}px;width:${Math.ceil(
      text.length / 2
    ) * ADV}px;height:9px;background:${D.amber};opacity:.42;transform-origin:0% 50%;transform:scaleX(0);`
  );
  page.append(swipe);

  meta(page, { text: "EP06 · EXHIBIT 02 / 微博原文", x: 150, y: 906, color: D.inkSoft, alpha: 0.4, size: 16, track: 2 });
  meta(page, { text: "据公开报道转录", x: W - 150, y: 906, color: D.inkSoft, alpha: 0.34, size: 16, track: 2, align: "right" });

  const edge = el(
    "div",
    `position:absolute;left:1842px;top:388px;width:66px;height:198px;background:${D.red};opacity:.9;box-shadow:0 10px 24px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;`
  );
  const vt = el(
    "div",
    `writing-mode:vertical-rl;font-family:${T.font.serif};font-size:26px;letter-spacing:7px;color:#efe9dc;`
  );
  vt.textContent = "回应 · 02";
  edge.append(vt);
  page.append(edge);

  const T0 = 0.22;
  const tEnd = 2.5;
  const cps = text.length / (tEnd - T0);

  return {
    update(t) {
      d.style.opacity = String(sceneOpacity(t, dur, 0.22));
      page.style.transform = `translateY(${lerp(10, 0, sceneOpacity(t, dur, 0.28))}px)`;
      wm.style.transform = `translateX(-100%) translateX(${lerp(0, -14, clamp(t / Math.max(dur, 0.001)))}px)`;

      setRule(headRule, easeOutCubic(prog(t, 0.08, 0.6)));
      openQ.style.opacity = String(0.78 * clamp((t - 0.1) / 0.4));

      const shown = Math.min(text.length, Math.floor(Math.max(0, t - T0) * cps + 1e-6));
      quote.textContent = text.slice(0, shown);

      const typing = shown < text.length;
      if (typing) {
        cursor.style.opacity = String(0.88 * cursorOn(t, 2.1));
        cursor.style.left = `${X + shown * ADV}px`;
        cursor.style.top = `${Y + 8}px`;
      } else {
        cursor.style.opacity = "0";
      }

      if (!typing) {
        const cp = easeOutCubic(prog(t, tEnd, tEnd + 0.26));
        closeQ.style.opacity = String(0.8 * cp);
        closeQ.style.left = `${X + text.length * ADV + 12}px`;
        closeQ.style.top = `${Y - 6}px`;
      }

      swipe.style.transform = `scaleX(${easeOutCubic(prog(t, 2.62, 3.06))})`;

      const cap = easeOutCubic(prog(t, 2.45, 2.98));
      setRule(capRule, cap);
      speaker.style.opacity = String(clamp(cap * 1.4));
      speaker.style.transform = `translateY(${lerp(10, 0, cap)}px)`;
      const dateP = easeOutCubic(prog(t, 2.62, 3.12));
      dateL.style.opacity = String(0.92 * clamp(dateP));
    },
    dispose() {
      S.dispose();
    },
  };
}
