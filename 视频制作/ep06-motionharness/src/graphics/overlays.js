// 时间轴叠加层 — stamp（墨红图章）/ tally（判决计分纸签）/ label（证据标注）
// 由引擎在事件窗口内挂载，update(t, dur) 的 t 是事件内局部秒；全透明全屏，确定性。
import {
  D,
  W,
  H,
  sceneRoot,
  txt,
  seal,
  rule,
  setRule,
  sceneOpacity,
  prog,
  easeOutCubic,
  easeOutQuint,
  clamp,
  lerp,
  el,
} from "./prims.js";

function unitsOf(s) {
  let u = 0;
  for (const ch of String(s)) {
    if (/[\u2e80-\u9fff\uff00-\uffef]/.test(ch)) u += 1;
    else if (ch === " ") u += 0.3;
    else u += 0.62;
  }
  return u;
}

// ------------------------------------------------------------------ stamp
function mountStamp(ctx, event) {
  const S = sceneRoot(ctx, { bg: "transparent" });
  const d = S.design;
  const color = event.color === "amber" ? D.amber : event.color === "ink" ? D.paper : D.red;
  const x = (Number(event.x) / 100) * W;
  const y = (Number(event.y) / 100) * H;
  const rot = Number(event.rot) || 0;

  // soft dark scrim so a red seal reads over busy footage
  const scrim = el("i", `position:absolute;left:${x - 300}px;top:${y - 300}px;width:600px;height:600px;`);
  scrim.style.background = "radial-gradient(circle, rgba(4,5,7,.34) 0%, rgba(4,5,7,.16) 42%, transparent 70%)";
  d.append(scrim);

  const st = seal(d, {
    x,
    y,
    size: 232,
    text: event.text || "判决",
    rot,
    color,
  });

  return {
    update(t, dur) {
      const a = sceneOpacity(t, dur, 0.12);
      d.style.opacity = String(a);
      st.set(t, 0.0, { settle: 0.24 });
    },
    dispose() {
      S.dispose();
    },
  };
}

// ------------------------------------------------------------------ tally
function mountTally(ctx, event) {
  const S = sceneRoot(ctx, { bg: "transparent" });
  const d = S.design;
  const counts = String(event.counts || "");
  const note = String(event.note || "");
  const stage = clamp(Number(event.stage) || 1, 1, 4);
  const cjk = /[\u2e80-\u9fff\uff00-\uffef]/.test(counts);

  const CW = Math.max(310, Math.round(unitsOf(counts) * (cjk ? 44 : 30) + 118));
  const CH = 154;
  const x = W - 150 - CW;
  const y = 182;

  const chip = el(
    "div",
    `position:absolute;left:${x}px;top:${y}px;width:${CW}px;height:${CH}px;`
  );
  const paper = el(
    "div",
    "position:absolute;inset:0;background:linear-gradient(180deg,#f0eadd 0%,#e4ddcc 100%);box-shadow:0 14px 34px rgba(0,0,0,.55), inset 0 0 0 1px rgba(80,62,38,.25);"
  );
  paper.append(el("i", `position:absolute;left:0;top:0;bottom:0;width:8px;background:${D.red};opacity:.9;`));
  paper.append(
    el("i", `position:absolute;left:0;right:0;top:26px;height:1px;background:${D.ink};opacity:.16;`)
  );
  txt(paper, { text: "判决 · VERDICT", x: 26, y: 35, size: 14, font: "mono", color: D.inkSoft, track: 2, alpha: 0.7 });
  if (CW >= 350) {
    txt(paper, {
      text: "EP06 / 卷宗",
      x: CW - 22,
      y: 35,
      size: 13,
      font: "mono",
      color: D.inkSoft,
      track: 2,
      align: "right",
      alpha: 0.5,
    });
  }
  const countsNode = txt(paper, {
    text: counts,
    x: 26,
    y: 56,
    size: cjk ? 38 : 44,
    font: cjk ? "sans" : "mono",
    color: D.ink,
    track: 1,
    weight: 700,
    alpha: 0,
  });
  const noteNode = txt(paper, {
    text: note,
    x: 26,
    y: 112,
    size: 18,
    font: "sans",
    color: D.inkSoft,
    track: 1,
    alpha: 0,
  });
  // stage ticks
  const ticks = [];
  for (let i = 0; i < 4; i++) {
    const on = i < stage;
    const tk = el(
      "i",
      `position:absolute;left:${CW - 24 - (3 - i) * 22}px;top:${CH - 26}px;width:16px;height:6px;background:${
        on ? (i === stage - 1 ? D.red : D.ink) : "rgba(27,26,23,.22)"
      };opacity:0;`
    );
    paper.append(tk);
    ticks.push(tk);
  }
  chip.append(paper);
  d.append(chip);

  return {
    update(t, dur) {
      d.style.opacity = String(sceneOpacity(t, dur, 0.12));
      const p = easeOutQuint(prog(t, 0.02, 0.4));
      chip.style.transform = `translateX(${lerp(70, 0, p)}px) rotate(${lerp(-2.6, -1.3, p)}deg)`;
      chip.style.opacity = String(clamp(p * 1.4));

      const cp = easeOutCubic(prog(t, 0.14, 0.5));
      countsNode.style.opacity = String(clamp(cp));
      countsNode.style.clipPath = `inset(${(1 - cp) * 100}% 0% 0% 0%)`;
      const np = easeOutCubic(prog(t, 0.34, 0.78));
      noteNode.style.opacity = String(0.85 * clamp(np));
      for (let i = 0; i < ticks.length; i++) {
        const tp = easeOutCubic(prog(t, 0.4 + i * 0.06, 0.6 + i * 0.06));
        ticks[i].style.opacity = String(clamp(tp));
      }
    },
    dispose() {
      S.dispose();
    },
  };
}

// ------------------------------------------------------------------ label
function mountLabel(ctx, event) {
  const S = sceneRoot(ctx, { bg: "transparent" });
  const d = S.design;
  const text = String(event.text || "");
  const ax = (Number(event.x) / 100) * W;
  const ay = (Number(event.y) / 100) * H;
  const above = ay > H * 0.5;
  const toRight = ax < W * 0.6;
  const s = toRight ? 1 : -1;
  const tx = ax + s * 96;
  const ty = above ? ay - 128 : ay + 74;

  const textW = Math.round(unitsOf(text) * 31 + 40);
  const labelX = toRight ? tx + 26 : tx - 26;

  // soft scrim behind the label block
  const scrim = el(
    "i",
    `position:absolute;left:${(toRight ? labelX : labelX - textW) - 30}px;top:${ty - 44}px;width:${
      textW + 60
    }px;height:76px;border-radius:4px;`
  );
  scrim.style.background = "radial-gradient(60% 70% at 50% 50%, rgba(4,5,7,.5) 0%, rgba(4,5,7,.22) 60%, transparent 100%)";
  d.append(scrim);

  // elbow leader: horizontal from anchor, then vertical to the label row
  const hLine = el(
    "div",
    `position:absolute;left:${Math.min(ax, tx)}px;top:${ty}px;width:${Math.abs(tx - ax)}px;height:2px;background:${D.amber};opacity:.9;transform-origin:left center;transform:scaleX(0);`
  );
  const vLine = el(
    "div",
    `position:absolute;left:${ax - 1}px;top:${Math.min(ay, ty)}px;width:2px;height:${Math.max(
      2,
      Math.abs(ty - ay)
    )}px;background:${D.amber};opacity:.9;transform-origin:50% 0%;transform:scaleY(0);`
  );
  d.append(hLine, vLine);

  const dotOuter = el(
    "i",
    `position:absolute;left:${ax - 9}px;top:${ay - 9}px;width:18px;height:18px;border:2px solid ${D.amber};border-radius:50%;background:rgba(8,9,12,.55);opacity:0;`
  );
  const dotInner = el(
    "i",
    `position:absolute;left:${ax - 2.5}px;top:${ay - 2.5}px;width:5px;height:5px;border-radius:50%;background:${D.amber};opacity:0;`
  );
  d.append(dotOuter, dotInner);

  const label = txt(d, {
    text,
    x: labelX,
    y: ty - 22,
    size: 30,
    font: "mono",
    color: D.paper,
    track: 1,
    align: toRight ? "left" : "right",
    alpha: 0,
  });

  return {
    update(t, dur) {
      d.style.opacity = String(sceneOpacity(t, dur, 0.12));
      const lp = easeOutCubic(prog(t, 0.06, 0.44));
      hLine.style.transform = `scaleX(${clamp(lp)})`;
      vLine.style.transform = `scaleY(${clamp(easeOutCubic(prog(t, 0.16, 0.5)))})`;
      const dp = easeOutCubic(prog(t, 0.3, 0.6));
      dotOuter.style.opacity = String(clamp(dp));
      dotOuter.style.transform = `scale(${lerp(0.4, 1, dp)})`;
      dotInner.style.opacity = String(clamp(dp) * 0.9);
      const tpv = easeOutCubic(prog(t, 0.34, 0.72));
      label.style.opacity = String(clamp(tpv));
      label.style.transform = `${toRight ? "" : "translateX(-100%) "}translateY(${lerp(6, 0, tpv)}px)`;
      scrim.style.opacity = String(0.9 * clamp(tpv));
    },
    dispose() {
      S.dispose();
    },
  };
}

export function mountOverlay(ctx) {
  const event = ctx.event || ctx.shot || {};
  const type = event.type || "label";
  if (type === "stamp") return mountStamp(ctx, event);
  if (type === "tally") return mountTally(ctx, event);
  return mountLabel(ctx, event);
}
