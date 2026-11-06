#!/usr/bin/env node
/**
 * AFTER capture driver for VStudio ("V视听") evidence.
 * Steps:
 *  1. attach main window, switch side-pane launcher to 「应用」 tab, screenshot drawer/grid
 *  2. locate app item containing 「视听」/VStudio in the grid, click it (real mouse)
 *  3. wait for new CDP page target (VStudio window), screenshot it + panel clips
 *  4. collect console/exceptions on both windows, verify main chat input
 * Writes PNGs + report.json into --out dir.
 *
 * Usage: node capture-after.js --out /tmp/vstudio-evidence/after [--no-click]
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const WS = require('/app/VCPChat/node_modules/ws');

const PORT = 9222;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function argv(name, def) {
  const i = process.argv.indexOf('--' + name);
  if (i === -1) return def;
  const v = process.argv[i + 1];
  return v && !v.startsWith('--') ? v : true;
}

function httpGetJson(urlPath) {
  return new Promise((resolve, reject) => {
    const req = http.get({ host: '127.0.0.1', port: PORT, path: urlPath, timeout: 10000 }, (res) => {
      let data = '';
      res.on('data', (c) => (data += c));
      res.on('end', () => { try { resolve(JSON.parse(data)); } catch (e) { reject(new Error('bad json')); } });
    });
    req.on('timeout', () => req.destroy(new Error('timeout')));
    req.on('error', reject);
  });
}
const listTargets = async () => (await httpGetJson('/json')).filter((p) => p.type === 'page');

class CDP {
  constructor(wsUrl) { this.wsUrl = wsUrl; this.id = 0; this.pending = new Map(); this.handlers = new Map(); }
  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WS(this.wsUrl, { perMessageDeflate: false });
      this.ws.on('open', resolve);
      this.ws.on('error', reject);
      this.ws.on('message', (raw) => {
        let msg; try { msg = JSON.parse(raw.toString()); } catch (e) { return; }
        if (msg.id !== undefined && this.pending.has(msg.id)) {
          const { resolve: res, reject: rej } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
        } else if (msg.method) {
          (this.handlers.get(msg.method) || []).forEach((h) => { try { h(msg.params); } catch (e) {} });
        }
      });
    });
  }
  on(m, f) { if (!this.handlers.has(m)) this.handlers.set(m, []); this.handlers.get(m).push(f); }
  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++this.id;
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); reject(new Error('CDP timeout ' + method)); } }, 30000);
    });
  }
  close() { try { this.ws.close(); } catch (e) {} }
}

async function evaluate(cdp, expression) {
  const r = await cdp.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true, userGesture: true });
  if (r.exceptionDetails) throw new Error('eval exception: ' + JSON.stringify(r.exceptionDetails));
  return r.result.value;
}

async function rect(cdp, selector) {
  return evaluate(cdp, `(()=>{const el=document.querySelector(${JSON.stringify(selector)}); if(!el) return null; const r=el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2};})()`);
}

async function clickSel(cdp, selector, offsetY = 0) {
  const r = await rect(cdp, selector);
  if (!r) throw new Error('no rect for ' + selector);
  const x = Math.round(r.cx), y = Math.round(r.cy + offsetY);
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'none', buttons: 0 });
  await sleep(60);
  await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', buttons: 1, clickCount: 1 });
  await sleep(50);
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', buttons: 0, clickCount: 1 });
  return { x, y };
}

async function shot(cdp, outPath, clipSel = null) {
  let clip = null;
  if (clipSel) {
    const r = await rect(cdp, clipSel);
    if (!r) throw new Error('clip selector missing: ' + clipSel);
    clip = { x: r.x, y: r.y, width: r.w, height: r.h, scale: 1 };
  }
  const r = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false, ...(clip ? { clip } : {}) });
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, Buffer.from(r.data, 'base64'));
  return outPath;
}

async function collectLogs(cdp, durationMs) {
  const events = [];
  await cdp.send('Runtime.enable');
  await cdp.send('Log.enable');
  cdp.on('Runtime.consoleAPICalled', (p) => {
    const text = (p.args || []).map((a) => (a.value !== undefined ? String(a.value) : (a.description || a.type))).join(' ');
    events.push({ source: 'console', level: p.type, text });
  });
  cdp.on('Runtime.exceptionThrown', (p) => {
    const d = p.exceptionDetails || {}; const ex = d.exception || {};
    events.push({ source: 'exception', level: 'error', text: ex.description || ex.value || d.text || JSON.stringify(d) });
  });
  cdp.on('Log.entryAdded', (p) => {
    const e = p.entry || {};
    events.push({ source: 'log', level: e.level, text: e.text, url: e.url || '' });
  });
  await sleep(durationMs);
  return events;
}

function attachLogCapture(cdp, bucket) {
  cdp.on('Runtime.consoleAPICalled', (p) => {
    const text = (p.args || []).map((a) => (a.value !== undefined ? String(a.value) : (a.description || a.type))).join(' ');
    bucket.push({ source: 'console', level: p.type, text });
  });
  cdp.on('Runtime.exceptionThrown', (p) => {
    const d = p.exceptionDetails || {}; const ex = d.exception || {};
    bucket.push({ source: 'exception', level: 'error', text: ex.description || ex.value || d.text || JSON.stringify(d) });
  });
  cdp.on('Log.entryAdded', (p) => {
    const e = p.entry || {};
    bucket.push({ source: 'log', level: e.level, text: e.text, url: e.url || '' });
  });
  return Promise.all([cdp.send('Runtime.enable'), cdp.send('Log.enable')]).catch(() => {});
}

async function main() {
  const outDir = path.resolve(argv('out', '/tmp/vstudio-evidence/after'));
  fs.mkdirSync(outDir, { recursive: true });
  const report = { startedAt: new Date().toISOString(), outDir, steps: [] };
  const log = (m, extra) => { const s = { ts: new Date().toISOString(), msg: m, ...extra }; report.steps.push(s); console.log(JSON.stringify(s)); };

  const before = await listTargets();
  report.targetsBefore = before.map((p) => ({ title: p.title, url: p.url }));
  log('targets-listed', { count: before.length });

  const mainTarget = before.find((p) => (p.title || '') === 'VCPChat' || /main\.html/.test(p.url || ''));
  if (!mainTarget) throw new Error('main window target not found');

  // If a VStudio window is already open (e.g. from a previous check), close it first so that
  // clicking the tray entry genuinely opens a fresh window (real user flow evidence).
  const isVsTarget = (p) => /vstudio/i.test(p.url || '') || /V视听|VStudio|VCP 视频协同工坊/i.test(p.title || '');
  let existingVs = before.find(isVsTarget) || null;
  report.existingVstudioTarget = existingVs ? { title: existingVs.title, url: existingVs.url } : null;
  if (existingVs && !argv('no-close-existing', false)) {
    log('closing-existing-vstudio', { title: existingVs.title });
    const exCdp = new CDP(existingVs.webSocketDebuggerUrl);
    try {
      await exCdp.connect();
      try { await evaluate(exCdp, `(()=>{const b=document.querySelector('#close-btn'); if(b){b.click(); return true;} return false;})()`); } catch (e) {}
      await sleep(500);
    } finally { exCdp.close(); }
    for (let i = 0; i < 20; i++) {
      const now = await listTargets();
      if (!now.some((p) => p.id === existingVs.id)) { log('existing-vstudio-closed'); break; }
      await sleep(400);
    }
    existingVs = null;
  }
  const mainCdp = new CDP(mainTarget.webSocketDebuggerUrl);
  await mainCdp.connect();
  const logs = { main: [], vstudio: [] };
  attachLogCapture(mainCdp, logs.main); // 尽早开始收集主窗口 console/异常
  try {
    const vp = await evaluate(mainCdp, `({w: innerWidth, h: innerHeight, dpr: devicePixelRatio, theme: document.documentElement.getAttribute('data-theme') || document.body.className})`);
    report.mainViewport = vp;
    log('main-viewport', vp);
    await shot(mainCdp, path.join(outDir, 'after-main.png'));
    log('main-shot', 'after-main.png');

    // ensure apps tab of launcher is active
    const tabSel = '#sidePaneViewLauncher .side-pane-launcher-tab[data-launcher-tab="apps"]';
    const tabState = await evaluate(mainCdp, `(()=>{const b=document.querySelector(${JSON.stringify(tabSel)}); return b? b.getAttribute('aria-selected') : null;})()`);
    if (tabState !== 'true') {
      await clickSel(mainCdp, tabSel);
      await sleep(700);
    }
    const appInfo = await evaluate(mainCdp, `(()=>{
      const g = document.querySelector('#sidePaneViewLauncher .side-pane-launcher-app-grid');
      if (!g) return null;
      return [...g.children].map(c => {
        const r = c.getBoundingClientRect();
        const label = (c.querySelector('.side-pane-launcher-app-label')||c).innerText.trim();
        return { id: c.getAttribute('data-launcher-app') || null, label, text: c.innerText.trim().slice(0,40), rect: [Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)] };
      });
    })()`);
    report.appGrid = appInfo;
    log('app-grid', { count: appInfo ? appInfo.length : 0 });
    await shot(mainCdp, path.join(outDir, 'after-tray.png'));
    await shot(mainCdp, path.join(outDir, 'after-apps-grid.png'), '#sidePaneViewLauncher .side-pane-launcher-app-grid');

    const targetApp = (appInfo || []).find((a) => /视听|vstudio|VStudio|videostudio/i.test((a.label || '') + ' ' + (a.id || '') + ' ' + (a.text || '')));
    report.vstudioAppItem = targetApp || null;
    log('vstudio-app-item', { item: targetApp || 'NOT_FOUND' });
    if (!targetApp) throw new Error('「视听」 app item NOT FOUND in launcher grid');
    if (!argv('no-click', false)) {
      await clickSel(mainCdp, `[data-launcher-app="${targetApp.id}"]`);
      log('clicked-app', { id: targetApp.id });
    } else {
      log('skipped-click');
    }

    // wait for the VStudio window target (a brand-new one, or the pre-existing focused one)
    let vstudioTarget = null;
    const known = new Set(before.map((p) => p.id));
    const deadline = Date.now() + 25000;
    while (Date.now() < deadline) {
      const now = await listTargets();
      const fresh = now.find((p) => !known.has(p.id) && isVsTarget(p));
      const any = now.find(isVsTarget);
      vstudioTarget = fresh || any || null;
      if (vstudioTarget) break;
      await sleep(500);
    }
    if (!vstudioTarget) {
      report.targetsAfter = (await listTargets()).map((p) => ({ title: p.title, url: p.url }));
      throw new Error('VStudio window target did not appear');
    }
    report.vstudioTargetIsNew = !known.has(vstudioTarget.id);
    report.vstudioTarget = { title: vstudioTarget.title, url: vstudioTarget.url, id: vstudioTarget.id };
    log('vstudio-target', report.vstudioTarget);
    const vsCdp = new CDP(vstudioTarget.webSocketDebuggerUrl);
    await vsCdp.connect();
    attachLogCapture(vsCdp, logs.vstudio); // 新窗口一出现就收集 console/异常
    try {
      // settle
      await sleep(2500);
      report.vstudioViewport = await evaluate(vsCdp, `({w: innerWidth, h: innerHeight, dpr: devicePixelRatio})`);
      log('vstudio-viewport', report.vstudioViewport);
      report.vstudioDom = await evaluate(vsCdp, `(()=>{
        const txt = (sel) => { const el = document.querySelector(sel); return el ? el.innerText.trim().slice(0, 600) : null; };
        const count = (sel) => document.querySelectorAll(sel).length;
        return {
          title: document.title,
          projectCount: txt('#project-count'), projectListText: txt('#project-list'),
          assetCount: txt('#assets-count'), assetsText: txt('#assets-list'),
          previewMeta: txt('#preview-meta'), stageEmptyVisible: (()=>{const e=document.querySelector('#stage-empty'); return e? !e.hidden && getComputedStyle(e).display!=='none' : null;})(),
          videoHidden: (()=>{const v=document.querySelector('#preview-video'); return v? v.hidden : null;})(),
          timelineMeta: txt('#timeline-meta'), timelineRows: count('#tl-rows .tl-row'), tlRowText: txt('#tl-rows'),
          annCount: txt('#ann-count'), annListText: txt('#ann-list'), annPins: count('#annotation-layer > *'),
          annotationLayerHtml: (document.querySelector('#annotation-layer')||{}).innerHTML ? document.querySelector('#annotation-layer').innerHTML.slice(0,800) : null,
          playerText: txt('.transport'), renderChip: txt('#render-chip'),
          bodyText: document.body.innerText.slice(0, 3000),
        };
      })()`);
      log('vstudio-dom', Object.keys(report.vstudioDom));

      await shot(vsCdp, path.join(outDir, 'after-vstudio.png'));
      // panel clips
      const clips = {
        'after-vstudio-projects.png': '.projects-panel',
        'after-vstudio-preview.png': '.preview-panel',
        'after-vstudio-timeline.png': '.timeline-panel',
        'after-vstudio-annotations.png': '.annotations-panel',
        'after-vstudio-agent.png': '.agent-panel',
      };
      for (const [file, sel] of Object.entries(clips)) {
        try { await shot(vsCdp, path.join(outDir, file), sel); log('clip-saved', { file, sel }); }
        catch (e) { log('clip-skipped', { file, sel, err: String(e.message) }); }
      }
      // let late console errors surface
      await sleep(1500);
      log('vstudio-logs', { count: logs.vstudio.length, errors: logs.vstudio.filter((e) => e.level === 'error' || e.source === 'exception').length });
    } finally { vsCdp.close(); }

    // main window: chat input health + logs
    report.mainHealth = await evaluate(mainCdp, `(()=>{
      const t = document.querySelector('#messageInput, #chatInput, textarea');
      return { title: document.title, chatInputPresent: !!document.querySelector('#messageInput'), chatInputVisible: t ? t.offsetParent !== null : false, chatInputPlaceholder: t ? t.placeholder : null, url: location.href };
    })()`);
    log('main-health', report.mainHealth);
    await sleep(1500);
    log('main-logs', { count: logs.main.length, errors: logs.main.filter((e) => e.level === 'error' || e.source === 'exception').length });
  } finally { mainCdp.close(); }

  report.logs = logs;
  report.finishedAt = new Date().toISOString();
  fs.writeFileSync(path.join(outDir, 'capture-report.json'), JSON.stringify(report, null, 2));
  console.log('DONE -> ' + path.join(outDir, 'capture-report.json'));
}

main().then(() => setTimeout(() => process.exit(0), 100)).catch((e) => { console.error('ERROR: ' + (e && e.stack ? e.stack : e)); process.exit(1); });
