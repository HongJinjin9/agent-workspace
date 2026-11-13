// 公共图元 — 卷宗体（dossier）图形场景基础设施
// mh-graphics 所有。所有函数只做确定性 DOM/SVG 构建；动画一律由 update(t) 赋样式。
import { THEME } from "../theme.js";

export const T = THEME;
export const D = THEME.color;
export const W = 1920;
export const H = 1080;
export const BAR = THEME.letterbox; // 132
export const TOP = BAR;
export const BOT = H - BAR; // 948

// ---------------------------------------------------------------- math
export const clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, p) => a + (b - a) * p;
export const easeOutCubic = (p) => 1 - Math.pow(1 - clamp(p), 3);
export const easeInCubic = (p) => Math.pow(clamp(p), 3);
export const easeInOutCubic = (p) => {
  p = clamp(p);
  return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
};
export const easeOutQuint = (p) => 1 - Math.pow(1 - clamp(p), 5);
export const easeInOutQuint = (p) => {
  p = clamp(p);
  return p < 0.5 ? 16 * p * p * p * p * p : 1 - Math.pow(-2 * p + 2, 5) / 2;
};
export const smoothstep = (a, b, x) => {
  const p = clamp((x - a) / Math.max(1e-6, b - a));
  return p * p * (3 - 2 * p);
};
/** 0..1 progress between t0/t1 (inclusive, clamped) */
export const prog = (t, t0, t1) => clamp((t - t0) / Math.max(1e-6, t1 - t0));
/** in/hold/out window */
export function win(t, t0, t1, fin = 0.3, fout = 0.3) {
  if (t < t0 || t > t1) return 0;
  const a = fin > 0 ? clamp((t - t0) / fin) : 1;
  const b = fout > 0 ? clamp((t1 - t) / fout) : 1;
  return Math.min(a, b);
}
/** scene-in opacity (~0.22s), optional fade-out at end */
export function sceneOpacity(t, dur, inDur = 0.22, outDur = 0) {
  const a = inDur > 0 ? clamp(t / inDur) : 1;
  const b = outDur > 0 ? clamp((dur - t) / outDur) : 1;
  return Math.min(a, b);
}
export function fmtInt(n) {
  const v = Math.round(Number(n) || 0);
  return String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}
/** eased integer count-up between t0..t1 */
export function countUp(value, t, t0, t1, from = 0) {
  const p = easeOutCubic(prog(t, t0, t1));
  return Math.round(lerp(from, value, p));
}
/** number of whole characters typed by t for cps chars/sec */
export function typedCount(text, t, t0, cps) {
  const n = Math.floor(Math.max(0, t - t0) * cps + 1e-6);
  return clamp(n, 0, text.length);
}
export function cursorOn(t, rate = 2.2) {
  return Math.floor(t * rate * 2) % 2 === 0 ? 1 : 0;
}
/** deterministic PRNG */
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export function hashStr(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}
export function hexA(hex, a) {
  const h = String(hex).replace("#", "");
  const v = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const r = parseInt(v.slice(0, 2), 16);
  const g = parseInt(v.slice(2, 4), 16);
  const b = parseInt(v.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}
/** split CJK quote into lines preferring punctuation break */
export function wrapCJK(text, perLine) {
  const lines = [];
  let cur = "";
  const brk = "，。；、！？：";
  for (let i = 0; i < text.length; i++) {
    cur += text[i];
    const last = text[i];
    if (cur.length >= perLine) {
      lines.push(cur);
      cur = "";
    } else if (brk.includes(last) && cur.length >= Math.max(2, perLine - 4)) {
      lines.push(cur);
      cur = "";
    }
  }
  if (cur) lines.push(cur);
  return lines;
}

// ---------------------------------------------------------------- DOM factory
export function el(tag, css, html) {
  const n = document.createElement(tag);
  if (css) n.style.cssText = css;
  if (html != null) n.innerHTML = html;
  return n;
}
export function svgEl(tag, attrs) {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  if (attrs) for (const k in attrs) n.setAttribute(k, String(attrs[k]));
  return n;
}
export function svgRoot(css) {
  const s = svgEl("svg", {
    width: W,
    height: H,
    viewBox: `0 0 ${W} ${H}`,
    preserveAspectRatio: "none",
    xmlns: "http://www.w3.org/2000/svg",
  });
  s.style.cssText = `position:absolute;left:0;top:0;overflow:visible;${css || ""}`;
  return s;
}

/** scene root: 1920x1080 design canvas scaled to ctx size */
export function sceneRoot(ctx, opts = {}) {
  const host = ctx.el;
  host.innerHTML = "";
  const wrap = el("div", `position:absolute;inset:0;overflow:hidden;background:${opts.bg || D.bg};`);
  const design = el("div", "position:absolute;left:0;top:0;width:1920px;height:1080px;transform-origin:0 0;");
  const sx = (ctx.width || W) / W;
  const sy = (ctx.height || H) / H;
  design.style.transform = `scale(${sx},${sy})`;
  wrap.append(design);
  host.append(wrap);
  let disposed = false;
  return {
    wrap,
    design,
    dispose() {
      if (disposed) return;
      disposed = true;
      host.innerHTML = "";
    },
  };
}

/** duration fallback when engine passes a missing dur */
export function shotDur(ctx, fallback = 3) {
  const d = ctx && ctx.shot ? ctx.shot.dur : null;
  return typeof d === "number" && d > 0 ? d : fallback;
}

// ---------------------------------------------------------------- backgrounds
/** cold charcoal ground: soft light + fibre + vignette. */
export function darkGround(design, opts = {}) {
  const g = el("div", "position:absolute;inset:0;pointer-events:none;");
  g.style.background = opts.warm
    ? "radial-gradient(120% 95% at 50% 26%, #1b1915 0%, #100f0d 42%, #08090c 100%)"
    : "radial-gradient(120% 95% at 50% 26%, #171a1f 0%, #0d0f13 44%, #08090c 100%)";
  g.style.backgroundColor = "#08090c";
  design.append(g);
  if (opts.beam !== false) {
    const beam = el(
      "div",
      "position:absolute;left:50%;top:-18%;width:1180px;height:900px;transform:translateX(-50%) rotate(-9deg);pointer-events:none;"
    );
    beam.style.background =
      "radial-gradient(50% 50% at 50% 50%, rgba(217,164,65,.055) 0%, rgba(217,164,65,.02) 45%, transparent 72%)";
    g.append(beam);
  }
  const vig = el("div", "position:absolute;inset:0;pointer-events:none;");
  vig.style.background =
    "radial-gradient(125% 92% at 50% 44%, transparent 42%, rgba(0,0,0,.34) 78%, rgba(0,0,0,.62) 100%)," +
    "linear-gradient(180deg, rgba(0,0,0,.35) 0%, transparent 16%, transparent 84%, rgba(0,0,0,.42) 100%)";
  g.append(vig);
  grainLayer(g, opts.seed || 606, opts.speckles == null ? 150 : opts.speckles, 0.5);
  return g;
}

/** deterministic fibre gradient + speckle layer */
export function grainLayer(parent, seed = 1, count = 140, alpha = 0.5) {
  const rnd = mulberry32(seed);
  const fib = el("div", "position:absolute;inset:0;pointer-events:none;mix-blend-mode:soft-light;");
  fib.style.opacity = String(alpha);
  fib.style.backgroundImage =
    "repeating-linear-gradient(0deg, rgba(226,218,200,.03) 0px, rgba(226,218,200,.03) 1px, transparent 1px, transparent 3px)," +
    "repeating-linear-gradient(90deg, rgba(120,104,78,.028) 0px, rgba(120,104,78,.028) 1px, transparent 1px, transparent 5px)," +
    "radial-gradient(90% 60% at 40% 30%, rgba(217,164,65,.035) 0%, transparent 70%)";
  parent.append(fib);
  const spec = el("div", "position:absolute;inset:0;pointer-events:none;");
  spec.style.opacity = String(0.5 * alpha);
  let html = "";
  for (let i = 0; i < count; i++) {
    const x = rnd() * W;
    const y = rnd() * H;
    const r = 0.6 + rnd() * 1.9;
    const a = 0.05 + rnd() * 0.2;
    const warm = rnd() > 0.5;
    const c = warm ? "233,227,214" : "120,105,80";
    html += `<i style="position:absolute;left:${x.toFixed(1)}px;top:${y.toFixed(1)}px;width:${r.toFixed(
      2
    )}px;height:${(r * (0.7 + rnd())).toFixed(2)}px;background:rgba(${c},${a.toFixed(
      3
    )});border-radius:50%;"></i>`;
  }
  spec.innerHTML = html;
  parent.append(spec);
  return spec;
}

// ---------------------------------------------------------------- paper page
/**
 * paper page: cream stock + fibre + foxing + soft edge shadow.
 * opts: {x,y,w,h,rot,seed,shadow}
 */
export function paperPage(design, opts = {}) {
  const { x = 0, y = 0, w = W, h = H, rot = 0, seed = 11 } = opts;
  const page = el(
    "div",
    `position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;transform-origin:50% 50%;transform:rotate(${rot}deg);`
  );
  const fill = el("div", "position:absolute;inset:0;pointer-events:none;");
  fill.style.background = "radial-gradient(120% 90% at 30% 18%, #f3eddf 0%, #e9e3d6 46%, #dcd4c2 100%)";
  fill.style.backgroundColor = "#e9e3d6";
  page.append(fill);
  page.append(
    el(
      "div",
      "position:absolute;inset:0;background:radial-gradient(130% 100% at 24% 6%, rgba(255,252,244,.50) 0%, rgba(255,252,244,.08) 32%, rgba(120,98,66,.10) 78%, rgba(70,54,32,.22) 100%);mix-blend-mode:multiply;pointer-events:none;"
    )
  );
  grainLayer(page, seed, 170, 0.75);
  // foxing spots
  const rnd = mulberry32(seed * 7 + 3);
  const fox = el("div", "g-root");
  let fh = "";
  for (let i = 0; i < 26; i++) {
    const fx = rnd() * w;
    const fy = rnd() * h;
    const r = 2 + rnd() * 9;
    const a = 0.02 + rnd() * 0.05;
    fh += `<i style="position:absolute;left:${(fx - r).toFixed(1)}px;top:${(fy - r).toFixed(
      1
    )}px;width:${(r * 2).toFixed(1)}px;height:${(r * 1.6).toFixed(
      1
    )}px;border-radius:50%;background:rgba(140,104,58,${a.toFixed(3)});filter:blur(1px);"></i>`;
  }
  fox.innerHTML = fh;
  page.append(fox);
  page.append(
    el(
      "div",
      "position:absolute;inset:0;box-shadow:inset 0 0 100px rgba(70,54,32,.22), inset 0 0 2px rgba(50,40,25,.5);pointer-events:none;"
    )
  );
  if (opts.shadow !== false && (x > 0 || y > 0)) {
    page.style.filter = "drop-shadow(0 26px 60px rgba(0,0,0,.55))";
  }
  design.append(page);
  return page;
}

// ---------------------------------------------------------------- rules / tabs / meta
export function rule(parent, opts = {}) {
  const { x = 0, y = 0, w = 400, h = 1, color = D.amber, alpha = 0.6, origin = "left" } = opts;
  const n = el(
    "div",
    `position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;background:${color};opacity:${alpha};transform-origin:${origin} 50%;transform:scaleX(0);`
  );
  parent.append(n);
  return n;
}
export function setRule(n, p) {
  if (n) n.style.transform = `scaleX(${clamp(p)})`;
}

export function cornerTicks(parent, box = {}, opts = {}) {
  const { x = 120, y = 180, w = W - 240, h = 640 } = box;
  const { color = D.paper, alpha = 0.34, size = 18, thick = 2 } = opts;
  const n = el("div", "g-root");
  n.style.opacity = String(alpha);
  const corners = [
    [x, y, 1, 1],
    [x + w, y, -1, 1],
    [x, y + h, 1, -1],
    [x + w, y + h, -1, -1],
  ];
  for (const [cx, cy, dx, dy] of corners) {
    n.append(
      el(
        "i",
        `position:absolute;left:${dx > 0 ? cx : cx - size}px;top:${cy - thick / 2}px;width:${size}px;height:${thick}px;background:${color};`
      )
    );
    n.append(
      el(
        "i",
        `position:absolute;left:${cx - thick / 2}px;top:${dy > 0 ? cy : cy - size}px;width:${thick}px;height:${size}px;background:${color};`
      )
    );
  }
  parent.append(n);
  return n;
}

/** text node. opts: text,x,y,size,font('serif'|'sans'|'mono'),color,alpha,track,weight,align,vAlign,lineHeight,maxWidth,nowrap,italic,upper */
export function txt(parent, o = {}) {
  const {
    text = "",
    x = 0,
    y = 0,
    size = 32,
    font = "sans",
    color = D.paper,
    alpha = 1,
    track = 0,
    weight = 400,
    align = "left",
    vAlign = "top",
    lineHeight = 1.4,
    maxWidth = 0,
    nowrap = true,
    italic = false,
    upper = false,
    z = 0,
  } = o;
  const ff = font === "serif" ? T.font.serif : font === "mono" ? T.font.mono : T.font.sans;
  const n = el("div", "");
  n.style.cssText = `position:absolute;left:${x}px;top:${y}px;font-family:${ff};font-size:${size}px;font-weight:${weight};color:${color};line-height:${lineHeight};letter-spacing:${track}px;white-space:${
    nowrap ? "nowrap" : "normal"
  };${maxWidth ? `width:${maxWidth}px;` : ""}${italic ? "font-style:italic;" : ""}transform-origin:${
    align === "center" ? "50%" : align === "right" ? "100%" : "0%"
  } 50%;opacity:${clamp(alpha)};`;
  let transforms = [];
  if (align === "center") transforms.push("translateX(-50%)");
  else if (align === "right") transforms.push("translateX(-100%)");
  if (vAlign === "center") transforms.push("translateY(-50%)");
  n.style.transform = transforms.join(" ");
  n.textContent = upper ? text.toUpperCase() : text;
  if (z) n.style.zIndex = String(z);
  parent.append(n);
  return n;
}

export function setA(n, a) {
  if (n) n.style.opacity = String(clamp(a));
}
export function setText(n, s) {
  if (n && n.textContent !== s) n.textContent = s;
}

/** mask reveal. dir: 'left' | 'up' | 'down' | 'center' */
export function mask(n, p, dir = "left") {
  if (!n) return;
  const q = clamp(p);
  if (dir === "up") n.style.clipPath = `inset(${(1 - q) * 100}% 0% 0% 0%)`;
  else if (dir === "down") n.style.clipPath = `inset(0% 0% ${(1 - q) * 100}% 0%)`;
  else if (dir === "center") {
    const cut = (1 - q) * 50;
    n.style.clipPath = `inset(0% ${cut}% 0% ${cut}%)`;
  } else n.style.clipPath = `inset(0% ${(1 - q) * 100}% 0% 0%)`;
}

/** case-file tab (paper slip) */
export function tab(parent, o = {}) {
  const { x = 150, y = 200, w = 320, h = 108, text = "第二幕", sub = "", rot = 0 } = o;
  const n = el(
    "div",
    `position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;transform:rotate(${rot}deg);`
  );
  const p = el(
    "div",
    "position:absolute;inset:0;background:linear-gradient(180deg,#efe9dc 0%,#e2dbc9 100%);box-shadow:0 12px 26px rgba(0,0,0,.5), inset 0 0 0 1px rgba(80,62,38,.25);"
  );
  p.append(el("i", "position:absolute;left:0;top:0;bottom:0;width:10px;background:#b3392e;opacity:.88;"));
  p.append(
    el(
      "i",
      "position:absolute;left:24px;top:50%;width:15px;height:15px;margin-top:-7.5px;border-radius:50%;background:#c6bca8;box-shadow:inset 0 2px 3px rgba(60,46,26,.55);"
    )
  );
  txt(p, {
    text,
    x: 56,
    y: h / 2 - 24,
    size: 40,
    font: "serif",
    color: "#211f19",
    track: 6,
    weight: 600,
  });
  if (sub) txt(p, { text: sub, x: 58, y: h / 2 + 20, size: 14, font: "mono", color: "#6c6455", track: 2 });
  n.append(p);
  parent.append(n);
  return n;
}

/**
 * red rubber seal: slam + ink bloom + flecks.
 * returns {node, body, bloom, set(t,t0,opts)}
 */
export function seal(parent, o = {}) {
  const {
    x = W / 2,
    y = H / 2,
    size = 210,
    text = "判决",
    sub = "",
    rot = -7,
    color = D.red,
    round = false,
    blend = "",
    z = 5,
  } = o;
  const holder = el("div", `position:absolute;left:${x}px;top:${y}px;width:0;height:0;z-index:${z};`);
  holder.style.transform = "translate(-50%,-50%)";
  const bloom = el(
    "i",
    `position:absolute;left:${-size * 1.55}px;top:${-size * 1.55}px;width:${size * 3.1}px;height:${
      size * 3.1
    }px;border-radius:50%;`
  );
  bloom.style.background = `radial-gradient(circle, ${hexA(color, 0.34)} 0%, ${hexA(color, 0.16)} 38%, ${hexA(
    color,
    0.05
  )} 62%, transparent 74%)`;
  bloom.style.filter = "blur(8px)";
  bloom.style.opacity = "0";
  const rnd = mulberry32(hashStr(text + size));
  const flecks = el("div", "position:absolute;left:0;top:0;");
  let fh = "";
  for (let i = 0; i < 13; i++) {
    const ang = rnd() * Math.PI * 2;
    const dd = size * (0.55 + rnd() * 0.42);
    const r = 1.2 + rnd() * 2.6;
    fh += `<i style="position:absolute;left:${(Math.cos(ang) * dd - r).toFixed(1)}px;top:${(
      Math.sin(ang) * dd - r
    ).toFixed(1)}px;width:${(r * 2).toFixed(1)}px;height:${(r * 2).toFixed(
      1
    )}px;border-radius:50%;background:${hexA(color, 0.5)};opacity:0;"></i>`;
  }
  flecks.innerHTML = fh;
  const body = el(
    "div",
    `position:absolute;left:${-size / 2}px;top:${-size / 2}px;width:${size}px;height:${size}px;display:flex;flex-direction:column;align-items:center;justify-content:center;border:${Math.max(
      4,
      size * 0.028
    )}px solid ${color};border-radius:${round ? "50%" : `${size * 0.03}px`};color:${color};opacity:0;transform-origin:50% 50%;`
  );
  if (blend) body.style.mixBlendMode = blend;
  const innerRing = el(
    "i",
    `position:absolute;left:${size * 0.075}px;top:${size * 0.075}px;right:${size * 0.075}px;bottom:${
      size * 0.075
    }px;border:${Math.max(1.2, size * 0.008)}px solid ${color};border-radius:${round ? "50%" : "2px"};opacity:.75;`
  );
  if (blend) innerRing.style.mixBlendMode = blend;
  body.append(innerRing);
  const tt = el("div", "");
  tt.style.cssText = `font-family:${T.font.serif};font-size:${size * 0.3}px;font-weight:700;letter-spacing:${
    size * 0.028
  }px;line-height:1;white-space:nowrap;`;
  tt.textContent = text;
  if (blend) tt.style.mixBlendMode = blend;
  body.append(tt);
  if (sub) {
    const ss = el("div", "");
    ss.style.cssText = `margin-top:${size * 0.055}px;font-family:${T.font.mono};font-size:${Math.max(
      13,
      size * 0.088
    )}px;letter-spacing:1.2px;opacity:.85;white-space:nowrap;`;
    ss.textContent = sub;
    if (blend) ss.style.mixBlendMode = blend;
    body.append(ss);
  }
  holder.append(bloom, flecks, body);
  parent.append(holder);

  const fleckNodes = Array.from(flecks.children);
  function set(t, t0, opts2 = {}) {
    const settle = opts2.settle == null ? 0.26 : opts2.settle;
    const p = clamp((t - t0) / settle);
    if (p <= 0) {
      body.style.opacity = "0";
      bloom.style.opacity = "0";
      fleckNodes.forEach((f) => (f.style.opacity = "0"));
      return 0;
    }
    const e = easeOutQuint(p);
    const sc = lerp(1.55, 1, e);
    body.style.opacity = String(0.94 * clamp(p * 2.2));
    body.style.transform = `rotate(${lerp(rot + 5, rot, e)}deg) scale(${sc})`;
    const bleed = clamp((t - t0 - 0.05) / 0.9);
    bloom.style.opacity = String(0.85 * bleed * clamp(p * 2));
    bloom.style.transform = `scale(${lerp(0.7, 1.06, easeOutCubic(bleed))})`;
    fleckNodes.forEach((f, i) => {
      const q = clamp((t - t0 - 0.04 - i * 0.012) / 0.35);
      f.style.opacity = String((0.45 + 0.4 * (((i * 37) % 11) / 11)) * q * clamp(p * 2));
      f.style.transform = `translate(${(i % 2 ? 1 : -1) * q * 2}px, ${q * 3}px)`;
    });
    return clamp(p * 2);
  }
  return { node: holder, body, bloom, set };
}

/** mono dossier meta label */
export function meta(parent, o = {}) {
  const { x = 150, y = 160, text = "", color = D.paper, alpha = 0.5, size = 20, align = "left", track = 3 } = o;
  return txt(parent, { text, x, y, size, font: "mono", color, alpha, track, align, vAlign: "center" });
}

/** four corner ticks + hairline frame; returns rule nodes for later animation */
export function evidenceFrame(design, o = {}) {
  const {
    x = 120,
    y = 170,
    w = W - 240,
    h = 660,
    color = D.paper,
    alpha = 0.3,
    tick = 18,
    rules = true,
  } = o;
  cornerTicks(design, { x, y, w, h }, { color, alpha, size: tick });
  if (rules) {
    return {
      top: rule(design, { x, y: y - 1, w, h: 1, color, alpha: alpha * 0.6 }),
      bot: rule(design, { x, y: y + h, w, h: 1, color, alpha: alpha * 0.6 }),
    };
  }
  return {};
}

// ---------------------------------------------------------------- svg chart helpers
export function drawLine(lineNode, length, p) {
  if (!lineNode) return;
  lineNode.style.strokeDasharray = `${length}`;
  lineNode.style.strokeDashoffset = `${length * (1 - clamp(p))}`;
}

export function underlineSwipe(parent, o = {}) {
  const { x = 0, y = 0, w = 300, h = 8, color = D.amber, alpha = 0.75 } = o;
  const n = el(
    "div",
    `position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;background:${color};opacity:${alpha};transform-origin:0% 50%;transform:scaleX(0);border-radius:1px;`
  );
  parent.append(n);
  return n;
}

/** temporary placeholder while a scene file is still stubbed (not used by finished scenes) */
export function makeStub(ctx, name) {
  const S = sceneRoot(ctx, { bg: "#08090c" });
  const d = S.design;
  darkGround(d, { seed: hashStr(name) });
  txt(d, {
    text: name + " · stub",
    x: W / 2,
    y: H / 2,
    size: 40,
    font: "serif",
    color: D.paper,
    align: "center",
    vAlign: "center",
    alpha: 0.55,
  });
  return { update() {}, dispose() { S.dispose(); } };
}

/** routed annotation: leader line + anchor dot + text. anchor in percent (x,y). */
export function annotation(design, o = {}) {
  const { text = "", x = 50, y = 30, side = "right", color = D.amber } = o;
  const ax = (x / 100) * W;
  const ay = (y / 100) * H;
  const s = side === "right" ? 1 : -1;
  const tx = ax + s * 210;
  const ty = ay - 92;
  const line1 = rule(design, { x: Math.min(tx, ax), y: ty, w: Math.abs(ax - tx), h: 2, color, alpha: 0.9, origin: "left" });
  // v line from elbow to anchor
  const vl = el(
    "div",
    `position:absolute;left:${ax - 1}px;top:${ty}px;width:2px;height:${Math.max(
      2,
      Math.abs(ty - ay)
    )}px;background:${color};opacity:.9;transform-origin:50% 0%;transform:scaleY(0);`
  );
  design.append(vl);
  const dot = el(
    "i",
    `position:absolute;left:${ax - 7}px;top:${ay - 7}px;width:14px;height:14px;border:2px solid ${color};border-radius:50%;background:rgba(8,9,12,.55);opacity:0;`
  );
  const dot2 = el(
    "i",
    `position:absolute;left:${ax - 2}px;top:${ay - 2}px;width:4px;height:4px;border-radius:50%;background:${color};opacity:0;`
  );
  design.append(dot, dot2);
  const label = txt(design, {
    text,
    x: tx,
    y: ty - 16,
    size: 30,
    font: "mono",
    color: D.cream || "#f2ecdf",
    align: s > 0 ? "left" : "right",
    track: 1,
    alpha: 0,
  });
  return { line1, vl, dot, dot2, label, ax, ay };
}
