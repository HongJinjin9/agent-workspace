// quote_feng — 冯思翰引述卡（案卷纸页 + 打字机逐字 + 引号 + 出处小字 + 墨红「引述」章）
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
  seal,
  sceneOpacity,
  prog,
  easeOutCubic,
  clamp,
  lerp,
  wrapCJK,
  cursorOn,
  el,
} from "./prims.js";
import { FACTS } from "../data/facts.js";

export function mount(ctx) {
  const shot = ctx.shot || {};
  const dur = shot.dur > 0 ? shot.dur : 6;
  const text = shot.text || FACTS.feng.quote;
  const lines = wrapCJK(text, 19);
  const total = lines.reduce((a, l) => a + l.length, 0);

  const SIZE = 58;
  const TRACK = 1.5;
  const ADV = SIZE + TRACK;
  const X = 316;
  const Y0 = 330;
  const GAP = 94;

  const S = sceneRoot(ctx, { bg: D.bg });
  const d = S.design;
  const page = paperPage(d, { x: 0, y: 0, w: W, h: H, seed: 62 });

  // ruled paper + red margin rules
  const ruled = el("div", "position:absolute;inset:0;pointer-events:none;");
  ruled.style.backgroundImage =
    "repeating-linear-gradient(0deg, rgba(74,70,61,.10) 0px, rgba(74,70,61,.10) 1px, transparent 1px, transparent 56px)";
  ruled.style.opacity = "0.5";
  page.append(ruled);
  page.append(
    el(
      "i",
      `position:absolute;left:250px;top:${132}px;width:2px;height:${H - 264}px;background:${D.red};opacity:.42;`
    )
  );
  page.append(
    el(
      "i",
      `position:absolute;left:258px;top:${132}px;width:1px;height:${H - 264}px;background:${D.red};opacity:.18;`
    )
  );

  // page header
  meta(page, { text: "CASE FILE · EP06 / 卷宗", x: 150, y: 172, color: D.inkSoft, alpha: 0.62, size: 19, track: 4 });
  meta(page, {
    text: "EXHIBIT 01 · 引述",
    x: W - 150,
    y: 172,
    color: D.inkSoft,
    alpha: 0.62,
    size: 19,
    track: 4,
    align: "right",
  });
  const headRule = rule(page, { x: 150, y: 206, w: W - 300, h: 1, color: D.ink, alpha: 0.22 });

  // opening quote mark
  const openQ = txt(page, {
    text: "“",
    x: 236,
    y: 226,
    size: 196,
    font: "serif",
    color: D.red,
    alpha: 0,
  });

  // quote lines (typewriter)
  const lineNodes = [];
  const lineColors = [D.ink, D.ink, D.red];
  for (let i = 0; i < lines.length; i++) {
    const n = txt(page, {
      text: "",
      x: X,
      y: Y0 + i * GAP,
      size: SIZE,
      font: "serif",
      color: lineColors[Math.min(i, lineColors.length - 1)],
      track: TRACK,
      weight: 400,
      lineHeight: 1.3,
    });
    lineNodes.push(n);
  }

  // typewriter cursor
  const cursor = el(
    "div",
    `position:absolute;left:0;top:0;width:5px;height:56px;background:${D.red};opacity:0;`
  );
  page.append(cursor);

  // closing quote mark
  const closeQ = txt(page, {
    text: "”",
    x: 0,
    y: 0,
    size: 150,
    font: "serif",
    color: D.red,
    alpha: 0,
  });

  // caption: speaker / role / date+source
  const capRule = rule(page, { x: X, y: 706, w: 190, h: 2, color: D.amber, alpha: 0.9 });
  const speaker = txt(page, {
    text: "—— " + (shot.speaker || FACTS.feng.name),
    x: X,
    y: 722,
    size: 38,
    font: "serif",
    color: D.ink,
    track: 2,
    alpha: 0,
    weight: 600,
  });
  const role = txt(page, {
    text: shot.role || FACTS.feng.role,
    x: X,
    y: 782,
    size: 27,
    font: "sans",
    color: D.inkSoft,
    track: 1.5,
    alpha: 0,
  });
  const dateL = txt(page, {
    text: `${shot.date || FACTS.feng.date} · ${shot.source || FACTS.feng.source}`,
    x: X,
    y: 820,
    size: 22,
    font: "mono",
    color: D.inkSoft,
    track: 0.5,
    alpha: 0,
  });

  // short dotted date derived from the source date string
  const dnum = String(shot.date || FACTS.feng.date).match(/\d+/g) || ["2020", "9", "8"];
  const dShort = `${dnum[0]}.${String(dnum[1] || "1").padStart(2, "0")}.${String(dnum[2] || "1").padStart(2, "0")}`;

  // rubber stamp: 引述
  const st = seal(page, {
    x: 1512,
    y: 706,
    size: 118,
    text: "引述",
    sub: dShort,
    rot: 8,
    color: D.red,
    blend: "multiply",
  });

  meta(page, { text: "EP06 · EXHIBIT 01 / 原件存档", x: 150, y: 906, color: D.inkSoft, alpha: 0.4, size: 16, track: 2 });
  meta(page, { text: "据公开报道转录", x: W - 150, y: 906, color: D.inkSoft, alpha: 0.34, size: 16, track: 2, align: "right" });

  // right-edge file tab
  const edge = el(
    "div",
    `position:absolute;left:1842px;top:388px;width:66px;height:198px;background:${D.red};opacity:.9;box-shadow:0 10px 24px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;`
  );
  const vt = el(
    "div",
    `writing-mode:vertical-rl;font-family:${T.font.serif};font-size:26px;letter-spacing:7px;color:#efe9dc;`
  );
  vt.textContent = "引述 · 01";
  edge.append(vt);
  page.append(edge);

  const T0 = 0.35;
  const tEnd = Math.max(T0 + 0.8, dur - 0.55);
  const cps = total / (tEnd - T0);

  return {
    update(t) {
      d.style.opacity = String(sceneOpacity(t, dur, 0.24));
      page.style.transform = `translateY(${lerp(10, 0, sceneOpacity(t, dur, 0.3))}px)`;

      setRule(headRule, easeOutCubic(prog(t, 0.1, 0.7)));
      openQ.style.opacity = String(0.8 * clamp((t - 0.12) / 0.42));

      const shown = Math.min(total, Math.floor(Math.max(0, t - T0) * cps + 1e-6));
      let acc = 0;
      let cLine = -1;
      let cN = 0;
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const n = clamp(shown - acc, 0, line.length);
        lineNodes[i].textContent = line.slice(0, n);
        if (n > 0 || i === 0) {
          if (shown <= acc + line.length) {
            cLine = i;
            cN = n;
          }
        }
        acc += line.length;
      }
      const typing = shown < total;
      const blink = cursorOn(t, 2.1);
      if (typing && cLine >= 0) {
        cursor.style.opacity = String(0.85 * blink);
        cursor.style.left = `${X + cN * ADV}px`;
        cursor.style.top = `${Y0 + cLine * GAP + 6}px`;
      } else {
        cursor.style.opacity = "0";
      }

      // closing quote after the last character
      if (!typing) {
        const cp = easeOutCubic(prog(t, tEnd, tEnd + 0.28));
        const last = lines[lines.length - 1] || "";
        closeQ.style.opacity = String(0.78 * cp);
        closeQ.style.left = `${X + last.length * ADV + 12}px`;
        closeQ.style.top = `${Y0 + (lines.length - 1) * GAP - 4}px`;
      }

      const cap = easeOutCubic(prog(t, 1.05, 1.6));
      setRule(capRule, cap);
      speaker.style.opacity = String(clamp(cap * 1.4));
      speaker.style.transform = `translateY(${lerp(10, 0, cap)}px)`;
      const roleP = easeOutCubic(prog(t, 1.2, 1.75));
      role.style.opacity = String(clamp(roleP));
      const dateP = easeOutCubic(prog(t, 1.35, 1.9));
      dateL.style.opacity = String(0.9 * clamp(dateP));

      st.set(t, 1.3);
    },
    dispose() {
      S.dispose();
    },
  };
}
