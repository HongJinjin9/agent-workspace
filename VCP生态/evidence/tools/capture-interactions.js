#!/usr/bin/env node
/**
 * AFTER interaction capture for the VStudio window:
 *   - select the demo project (if none active)
 *   - wait until the rendered <video> is ready (readyState >= 2), then play 1-2s and capture a real playing frame
 *   - click an annotation card so its pin highlights on the preview, capture "批注 pin + 批注列表"
 *   - collect console/exceptions of the VStudio window
 * Assumes the VStudio window is already open (run capture-after.js first).
 * Usage: node capture-interactions.js --out /tmp/vstudio-evidence/after
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
function httpGetJson(p) {
  return new Promise((resolve, reject) => {
    const req = http.get({ host: '127.0.0.1', port: PORT, path: p, timeout: 10000 }, (res) => {
      let d = ''; res.on('data', (c) => (d += c)); res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } });
    });
    req.on('timeout', () => req.destroy(new Error('timeout'))); req.on('error', reject);
  });
}
const listTargets = async () => (await httpGetJson('/json')).filter((p) => p.type === 'page');

class CDP {
  constructor(wsUrl) { this.wsUrl = wsUrl; this.id = 0; this.pending = new Map(); this.handlers = new Map(); }
  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WS(this.wsUrl, { perMessageDeflate: false });
      this.ws.on('open', resolve); this.ws.on('error', reject);
      this.ws.on('message', (raw) => {
        let msg; try { msg = JSON.parse(raw.toString()); } catch (e) { return; }
        if (msg.id !== undefined && this.pending.has(msg.id)) {
          const { resolve: r, reject: j } = this.pending.get(msg.id); this.pending.delete(msg.id);
          msg.error ? j(new Error(JSON.stringify(msg.error))) : r(msg.result);
        } else if (msg.method) {
          (this.handlers.get(msg.method) || []).forEach((h) => { try { h(msg.params); } catch (e) {} });
        }
      });
    });
  }
  on(m, f) { if (!this.handlers.has(m)) this.handlers.set(m, []); this.handlers.get(m).push(f); }
  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++this.id; this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); reject(new Error('timeout ' + method)); } }, 30000);
    });
  }
  close() { try { this.ws.close(); } catch (e) {} }
}
async function evaluate(cdp, expression) {
  const r = await cdp.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true, userGesture: true });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
  return r.result.value;
}
async function rect(cdp, sel) {
  return evaluate(cdp, `(()=>{const el=document.querySelector(${JSON.stringify(sel)}); if(!el) return null; const r=el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2};})()`);
}
async function clickSel(cdp, sel) {
  const r = await rect(cdp, sel);
  if (!r) throw new Error('no rect ' + sel);
  const x = Math.round(r.cx), y = Math.round(r.cy);
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
    if (!r) throw new Error('clip missing ' + clipSel);
    clip = { x: r.x, y: r.y, width: r.w, height: r.h, scale: 1 };
  }
  const r = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false, ...(clip ? { clip } : {}) });
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, Buffer.from(r.data, 'base64'));
  return outPath;
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
  const report = { capturedAt: new Date().toISOString(), steps: [] };
  const logs = [];
  const log = (m, extra = {}) => { const s = { ts: new Date().toISOString(), msg: m, ...extra }; report.steps.push(s); console.log(JSON.stringify(s)); };

  const pages = await listTargets();
  const target = pages.find((p) => /vstudio/i.test(p.url || '') || /V视听|VStudio|VCP 视频协同工坊/i.test(p.title || ''));
  if (!target) throw new Error('VStudio target not found; have: ' + pages.map((p) => p.title + ' ' + p.url).join(' | '));
  log('target', { title: target.title, url: target.url });

  const cdp = new CDP(target.webSocketDebuggerUrl);
  await cdp.connect();
  attachLogCapture(cdp, logs);
  try {
    // wait for project list / video to settle
    const settleDeadline = Date.now() + 25000;
    let state = null;
    while (Date.now() < settleDeadline) {
      state = await evaluate(cdp, `(()=>{
        const list = document.querySelector('#project-list');
        const v = document.querySelector('#preview-video');
        return {
          projectItems: list ? list.children.length : 0,
          activeProject: (()=>{const el=document.querySelector('.project-item.active'); return el? el.getAttribute('data-id') : null;})(),
          videoSrc: v ? (v.currentSrc || v.src) : null,
          videoHidden: v ? v.hidden : null,
          videoReadyState: v ? v.readyState : null,
          annCards: document.querySelectorAll('.ann-card').length,
        };
      })()`);
      if (state.projectItems > 0 && (state.activeProject || state.videoSrc)) break;
      await sleep(500);
    }
    report.initialState = state;
    log('initial-state', state);

    // select a project if none active
    const pick = await evaluate(cdp, `(()=>{
      const el = document.querySelector('.project-item.active');
      if (el) return { id: el.getAttribute('data-id') };
      const f = document.querySelector('.project-item');
      if (!f) return null;
      return { noActive: true, id: f.getAttribute('data-id') };
    })()`);
    log('active-project', pick);
    if (pick && pick.noActive) {
      await clickSel(cdp, '.project-item');
      log('clicked-project', pick.id);
      await sleep(2500);
    }

    // wait for <video> readiness (readyState >= 2 means current frame data available)
    let videoState = null;
    const vDeadline = Date.now() + 15000;
    while (Date.now() < vDeadline) {
      videoState = await evaluate(cdp, `(()=>{
        const v = document.querySelector('#preview-video');
        const p = document.querySelector('#poster-img');
        return {
          src: v ? (v.currentSrc || v.src) : null,
          hidden: v ? v.hidden : null,
          readyState: v ? v.readyState : null,
          duration: v ? (isFinite(v.duration) ? Math.round(v.duration*100)/100 : null) : null,
          paused: v ? v.paused : null,
          posterHidden: p ? p.hidden : null,
          posterSrc: p ? (p.currentSrc || p.src) : null,
          posterComplete: p ? p.complete : null,
          posterNaturalW: p ? p.naturalWidth : null,
        };
      })()`);
      if (videoState && videoState.hidden === false && videoState.readyState >= 2) break;
      await sleep(500);
    }
    report.videoState = videoState;
    log('video-state', videoState);

    const loaded = await evaluate(cdp, `(()=>{
      const active = document.querySelector('.project-item.active');
      return {
        activeProject: active ? active.getAttribute('data-id') : null,
        activeProjectName: active ? active.innerText.replace(/\\s+/g,' ').trim().slice(0,120) : null,
        timelineDuration: (document.querySelector('#timeline-duration')||{}).innerText || null,
        annPins: document.querySelectorAll('#annotation-layer .ann-pin').length,
        regionBoxes: document.querySelectorAll('#annotation-layer .ann-region-box').length,
        annCards: document.querySelectorAll('.ann-card').length,
        annCountText: (document.querySelector('#ann-count')||{}).innerText || null,
        renderChip: (document.querySelector('#render-chip')||{}).innerText || null,
        projectCount: (document.querySelector('#project-count')||{}).innerText || null,
      };
    })()`);
    report.loadedState = loaded;
    log('loaded-state', loaded);
    report.windowViewport = await evaluate(cdp, `({w:innerWidth,h:innerHeight,dpr:devicePixelRatio,theme:document.body.className})`);
    log('window-viewport', report.windowViewport);
    await shot(cdp, path.join(outDir, 'after-vstudio-project.png'));

    // ---- annotation pin + annotation list ----
    if (loaded.annCards > 0) {
      try {
        await clickSel(cdp, '.ann-card');
        log('clicked-ann-card');
        await sleep(900);
        const pinState = await evaluate(cdp, `(()=>{
          const pins=[...document.querySelectorAll('#annotation-layer .ann-pin')];
          return {
            pinCount: pins.length,
            pins: pins.map(p=>({cls:p.className, label:p.innerText.trim().slice(0,10)})),
            selectedPin: (()=>{const s=document.querySelector('#annotation-layer .ann-pin.selected, #annotation-layer .ann-region-box.selected'); return s? s.className : null;})(),
            selectedCard: (()=>{const s=document.querySelector('.ann-card.selected'); return s? s.innerText.replace(/\\s+/g,' ').trim().slice(0,300) : null;})(),
            annCountText: (document.querySelector('#ann-count')||{}).innerText || null,
            annListText: (document.querySelector('#ann-list')||{}).innerText.replace(/\\s+/g,' ').trim().slice(0,1200),
            frame: (document.querySelector('#tc-frame')||{}).innerText || null,
            timecode: (document.querySelector('#tc-time')||{}).innerText || null,
          };
        })()`);
        report.annotationState = pinState;
        log('annotation-state', { pinCount: pinState.pinCount, selectedPin: pinState.selectedPin, frame: pinState.frame });
        await shot(cdp, path.join(outDir, 'after-vstudio-annotation.png'));
        try { await shot(cdp, path.join(outDir, 'after-vstudio-annotation-pin.png'), '.preview-panel'); log('pin-clip-saved'); } catch (e) { log('pin-clip-skipped', { err: String(e.message) }); }
        try { await shot(cdp, path.join(outDir, 'after-vstudio-annotation-list.png'), '.annotations-panel'); log('list-clip-saved'); } catch (e) { log('list-clip-skipped', { err: String(e.message) }); }
      } catch (e) { log('annotation-step-failed', { err: String(e.message) }); }
    } else {
      log('no-annotations', { annCards: loaded.annCards });
    }

    // ---- playback: readyState>=2, seek mid, play 1-2s, capture real frame ----
    const canPlay = videoState && videoState.hidden === false && videoState.readyState >= 2 && videoState.src;
    if (canPlay) {
      try {
        const seek = await evaluate(cdp, `(async()=>{const v=document.querySelector('#preview-video'); if(!v) return null; const d=isFinite(v.duration)&&v.duration>0?v.duration:3; try{ v.currentTime=Math.min(Math.max(1.0, d*0.35), Math.max(1.0, d-0.5)); }catch(e){}; v.pause(); await new Promise(r=>setTimeout(r,300)); return {t:v.currentTime, readyState:v.readyState, paused:v.paused};})()`);
        log('seeked', seek);
        await clickSel(cdp, '#play-btn');
        const t1 = await evaluate(cdp, `(()=>{const v=document.querySelector('#preview-video'); return v?{t:v.currentTime,paused:v.paused,readyState:v.readyState}:null;})()`);
        await sleep(1400);
        const t2 = await evaluate(cdp, `(()=>{const v=document.querySelector('#preview-video'); const tc=document.querySelector('#tc-time'); const frame=document.querySelector('#tc-frame'); return v?{t:v.currentTime,paused:v.paused,readyState:v.readyState,timecode:tc?tc.innerText:null,frame:frame?frame.innerText:null}:null;})()`);
        report.playback = { t1, t2, advanced: t1 && t2 ? t2.t > t1.t + 0.05 : false };
        log('playback', report.playback);
        await shot(cdp, path.join(outDir, 'after-vstudio-playing.png'));
        try { await shot(cdp, path.join(outDir, 'after-vstudio-playing-preview.png'), '.preview-panel'); log('playing-clip-saved'); } catch (e) {}
        // pause again to leave the UI stable
        await clickSel(cdp, '#play-btn');
        await sleep(300);
        report.playback.pausedAfter = await evaluate(cdp, `(()=>{const v=document.querySelector('#preview-video'); return v? v.paused : null;})()`);
      } catch (e) { log('playback-step-failed', { err: String(e.message) }); }
    } else {
      log('skip-playback', { videoState });
    }
  } finally { cdp.close(); }

  await sleep(1200); // let late errors surface
  report.logs = logs;
  report.errorCount = logs.filter((e) => e.level === 'error' || e.source === 'exception').length;
  report.errors = logs.filter((e) => e.level === 'error' || e.source === 'exception');
  report.finishedAt = new Date().toISOString();
  fs.writeFileSync(path.join(outDir, 'interaction-report.json'), JSON.stringify(report, null, 2));
  console.log('DONE -> ' + path.join(outDir, 'interaction-report.json') + ' errors=' + report.errorCount);
}
main().then(() => setTimeout(() => process.exit(0), 100)).catch((e) => { console.error('ERROR: ' + (e && e.stack ? e.stack : e)); process.exit(1); });
