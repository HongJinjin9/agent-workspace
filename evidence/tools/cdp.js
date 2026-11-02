#!/usr/bin/env node
/**
 * Generic CDP helper for VStudio evidence capture.
 * Usage:
 *   node cdp.js list
 *   node cdp.js eval <targetMatch> <expression> [--awaitPromise]
 *   node cdp.js shot <targetMatch> <outPath> [--clipsel=<selector>] [--full]
 *   node cdp.js click <targetMatch> <selector> [--offsetY=n]
 *   node cdp.js wait <targetMatch> <selector> <timeoutMs>
 *   node cdp.js logs <targetMatch> <durationMs> <outJsonl>
 *   node cdp.js targets-dump
 *
 * targetMatch: substring match against page title or url.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const WS = require('/app/VCPChat/node_modules/ws');

const DEBUG = { host: '127.0.0.1', port: 9222 };

function httpGetJson(urlPath) {
  return new Promise((resolve, reject) => {
    const req = http.get({ host: DEBUG.host, port: DEBUG.port, path: urlPath, timeout: 10000 }, (res) => {
      let data = '';
      res.on('data', (c) => (data += c));
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch (e) { reject(new Error('bad json: ' + data.slice(0, 300))); }
      });
    });
    req.on('timeout', () => { req.destroy(new Error('timeout')); });
    req.on('error', reject);
  });
}

async function listTargets() {
  const pages = await httpGetJson('/json');
  return pages.filter((p) => p.type === 'page');
}

function findTarget(pages, match) {
  const m = (match || '').toLowerCase();
  const found = pages.find((p) => (p.title || '').toLowerCase().includes(m) || (p.url || '').toLowerCase().includes(m));
  if (!found) throw new Error('target not found for match=' + match + '; have: ' + pages.map((p) => p.title).join(' | '));
  return found;
}

class CDP {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.id = 0;
    this.pending = new Map();
    this.handlers = new Map();
    this.ws = null;
  }
  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WS(this.wsUrl, { perMessageDeflate: false });
      this.ws.on('open', resolve);
      this.ws.on('error', reject);
      this.ws.on('message', (raw) => {
        let msg;
        try { msg = JSON.parse(raw.toString()); } catch (e) { return; }
        if (msg.id !== undefined && this.pending.has(msg.id)) {
          const { resolve: res, reject: rej } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          if (msg.error) rej(new Error(JSON.stringify(msg.error)));
          else res(msg.result);
        } else if (msg.method) {
          const hs = this.handlers.get(msg.method) || [];
          hs.forEach((h) => { try { h(msg.params); } catch (e) {} });
        }
      });
    });
  }
  on(method, fn) {
    if (!this.handlers.has(method)) this.handlers.set(method, []);
    this.handlers.get(method).push(fn);
  }
  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++this.id;
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => {
        if (this.pending.has(id)) { this.pending.delete(id); reject(new Error('CDP timeout: ' + method)); }
      }, 30000);
    });
  }
  close() { try { this.ws.close(); } catch (e) {} }
}

async function evalOn(cdp, expression, awaitPromise = true) {
  const r = await cdp.send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise,
    userGesture: true,
  });
  if (r.exceptionDetails) {
    throw new Error('eval exception: ' + JSON.stringify(r.exceptionDetails));
  }
  return r.result.value;
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function waitForSelector(cdp, selector, timeoutMs = 10000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const ok = await evalOn(cdp, `!!document.querySelector(${JSON.stringify(selector)})`);
    if (ok) return true;
    await sleep(200);
  }
  return false;
}

async function getRect(cdp, selector) {
  return evalOn(cdp, `(() => {
    const el = document.querySelector(${JSON.stringify(selector)});
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x: r.x, y: r.y, width: r.width, height: r.height, cx: r.x + r.width/2, cy: r.y + r.height/2};
  })()`);
}

async function clickSelector(cdp, selector, offsetY = 0) {
  const rect = await getRect(cdp, selector);
  if (!rect) throw new Error('no rect for ' + selector);
  const x = Math.round(rect.cx);
  const y = Math.round(rect.cy + offsetY);
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'none', buttons: 0 });
  await sleep(60);
  await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', buttons: 1, clickCount: 1 });
  await sleep(50);
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', buttons: 0, clickCount: 1 });
  return { x, y, rect };
}

async function capture(cdp, outPath, clip = null) {
  const params = { format: 'png', captureBeyondViewport: false };
  if (clip) params.clip = { x: clip.x, y: clip.y, width: clip.width, height: clip.height, scale: 1 };
  const r = await cdp.send('Page.captureScreenshot', params);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, Buffer.from(r.data, 'base64'));
  return outPath;
}

async function main() {
  const [cmd, ...args] = process.argv.slice(2);
  const pages = await listTargets();
  if (cmd === 'list') {
    console.log(JSON.stringify(pages.map((p) => ({ id: p.id, title: p.title, url: p.url, ws: p.webSocketDebuggerUrl })), null, 2));
    return;
  }
  if (cmd === 'targets-dump') {
    for (const p of pages) {
      const cdp = new CDP(p.webSocketDebuggerUrl);
      await cdp.connect();
      try {
        const info = await evalOn(cdp, `({title: document.title, w: innerWidth, h: innerHeight, dpr: devicePixelRatio, ua: navigator.userAgent, url: location.href})`);
        console.log(JSON.stringify({ id: p.id, title: p.title, info }));
      } catch (e) {
        console.log(JSON.stringify({ id: p.id, title: p.title, error: String(e.message) }));
      }
      cdp.close();
    }
    return;
  }

  const target = findTarget(pages, args[0]);
  const cdp = new CDP(target.webSocketDebuggerUrl);
  await cdp.connect();
  try {
    if (cmd === 'eval') {
      const expression = args[1];
      const v = await evalOn(cdp, expression, true);
      console.log(typeof v === 'string' ? v : JSON.stringify(v, null, 2));
    } else if (cmd === 'shot') {
      let outPath = args[1];
      let clip = null;
      const clipSelArg = args.find((a) => a.startsWith('--clipsel='));
      if (clipSelArg) {
        const sel = clipSelArg.slice('--clipsel='.length);
        const rect = await getRect(cdp, sel);
        if (!rect) throw new Error('clip selector not found: ' + sel);
        clip = { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
      }
      const info = await evalOn(cdp, `({w: innerWidth, h: innerHeight, dpr: devicePixelRatio})`);
      await capture(cdp, outPath, clip);
      console.log(JSON.stringify({ saved: outPath, viewport: info, clip }));
    } else if (cmd === 'click') {
      const res = await clickSelector(cdp, args[1], args[2] ? parseInt(args[2], 10) : 0);
      console.log(JSON.stringify(res));
    } else if (cmd === 'wait') {
      const ok = await waitForSelector(cdp, args[1], args[2] ? parseInt(args[2], 10) : 10000);
      console.log(JSON.stringify({ found: ok }));
      if (!ok) process.exitCode = 1;
    } else if (cmd === 'logs') {
      const durationMs = parseInt(args[1] || '5000', 10);
      const outJsonl = args[2];
      const events = [];
      await cdp.send('Runtime.enable');
      await cdp.send('Log.enable');
      cdp.on('Runtime.consoleAPICalled', (p) => {
        const text = (p.args || []).map((a) => (a.value !== undefined ? String(a.value) : (a.description || a.type))).join(' ');
        events.push({ ts: Date.now(), source: 'console', level: p.type, text, url: (p.stackTrace && p.stackTrace.callFrames && p.stackTrace.callFrames[0] && p.stackTrace.callFrames[0].url) || '' });
      });
      cdp.on('Runtime.exceptionThrown', (p) => {
        const d = p.exceptionDetails || {};
        const ex = d.exception || {};
        events.push({ ts: Date.now(), source: 'exception', level: 'error', text: ex.description || ex.value || d.text || JSON.stringify(d) });
      });
      cdp.on('Log.entryAdded', (p) => {
        const e = p.entry || {};
        events.push({ ts: Date.now(), source: 'log', level: e.level, text: e.text, url: e.url || '' });
      });
      await sleep(durationMs);
      // Also grab any pre-existing JS errors registered by page (if page exposes).
      if (outJsonl) fs.writeFileSync(outJsonl, events.map((e) => JSON.stringify(e)).join('\n'), { flag: 'a' });
      console.log(JSON.stringify({ count: events.length, events }, null, 2));
    } else {
      console.error('unknown command: ' + cmd);
      process.exitCode = 1;
    }
  } finally {
    cdp.close();
  }
}

main().then(() => { setTimeout(() => process.exit(0), 100); }).catch((e) => { console.error('ERROR: ' + (e && e.stack ? e.stack : e)); process.exit(1); });
