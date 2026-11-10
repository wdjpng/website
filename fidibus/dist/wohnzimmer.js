import {loadCatalog, fmt, pos} from '/wohnzimmer-shared.js';
const $ = s => document.querySelector(s);
const SLOW = +new URLSearchParams(location.search).get('slow') || 1;
if (new URLSearchParams(location.search).has('debug')) { window.__errs = []; addEventListener('error', e => __errs.push(e.message + ' @' + e.lineno)); addEventListener('unhandledrejection', e => __errs.push('rej ' + (e.reason?.stack || e.reason))); }   // ?slow=8 to study the animation
const wait = ms => new Promise(r => setTimeout(r, ms * SLOW));
const items = await loadCatalog();
// what is actually on each tape (identified from the recordings); falls back to "Band NN"
const tapes = await fetch('/tapes.json').then(r => r.ok ? r.json() : {}).catch(() => ({}));
const v = $('#v'), tube = $('#tube'), shelf = $('#shelf'), stage = $('#stage');
let loaded = null, loadedSpine = null, tvOn = false, seekTimer = null, busy = false, autoZoom = true;

// ---------- fit the stage to any screen ----------
let S = 1, zoomed = false;
function fit() {
  const w = document.documentElement.clientWidth, h = window.visualViewport?.height || document.documentElement.clientHeight;
  if (!w || !h) return;
  const portrait = w / h < .85;
  document.body.classList.toggle('P', portrait); document.body.classList.toggle('L', !portrait);
  const W = portrait ? 820 : 1440, H = portrait ? 1480 : 900;
  S = Math.min(w / W, h / H);
  stage.style.transform = `translate(${(w - W * S) / 2}px,${(h - H * S) / 2}px) scale(${S})`;
  if (zoomed) {
    // move the camera into the TV: the picture (not the whole tube) fills the screen, a sliver of
    // curved glass and bezel stays visible at the edges where the aspect ratios differ
    const tv = $('#tv'), tx = tv.offsetLeft + tube.offsetLeft, ty = tv.offsetTop + tube.offsetTop, tw = tube.offsetWidth, th = tube.offsetHeight;
    const a = (v.videoWidth && v.videoHeight) ? v.videoWidth / v.videoHeight : 4 / 3;
    const vw = tw / th > a ? th * a : tw, vh = tw / th > a ? th : tw / a;
    const Z = Math.min(w / vw, h / vh) * 1.015;
    stage.style.transform = `translate(${w / 2 - (tx + tw / 2) * Z}px,${h / 2 - (ty + th / 2) * Z}px) scale(${Z})`;
  }
  document.querySelector('#vp').style.setProperty('--floor', (h - H * S) / 2 + (portrait ? 1440 : 790) * S + 'px');  // continue the floor line into the letterbox
}
fit(); addEventListener('resize', fit); addEventListener('orientationchange', () => setTimeout(fit, 300));
// a rect in stage coordinates (the stage is scaled)
// a rect in stage coordinates, from the layout itself (immune to the stage's scale/zoom and its transitions)
function sr(el) { let x = 0, y = 0, n = el; while (n && n !== stage) { x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; } return {x, y, w: el.offsetWidth, h: el.offsetHeight}; }

// ---------- sound: synthesised mechanics (no files) ----------
let ac = null; const muted = false;
addEventListener('pointerdown', () => { if (!ac) { ac = new (window.AudioContext || window.webkitAudioContext)(); } if (ac.state === 'suspended') ac.resume(); }, {capture: true});
function noise(dur) { const b = ac.createBuffer(1, ac.sampleRate * dur, ac.sampleRate), d = b.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; const s = ac.createBufferSource(); s.buffer = b; return s; }
function env(node, t0, a, peak, dur) { const g = ac.createGain(); g.gain.setValueAtTime(0, t0); g.gain.linearRampToValueAtTime(peak, t0 + a); g.gain.exponentialRampToValueAtTime(.0001, t0 + dur); node.connect(g); g.connect(ac.destination); return g; }
const sfx = {
  click(at = 0) { if (!ac || muted) return; const t = ac.currentTime + at, n = noise(.03), f = ac.createBiquadFilter(); f.type = 'bandpass'; f.frequency.value = 2600; n.connect(f); env(f, t, .002, .35, .03); n.start(t); },
  slide(dur, at = 0) { if (!ac || muted) return; const t = ac.currentTime + at, n = noise(dur), f = ac.createBiquadFilter(); f.type = 'bandpass'; f.frequency.value = 900; f.Q.value = .7; n.connect(f); env(f, t, dur * .3, .12, dur); n.start(t); },
  motor(dur, at = 0) { if (!ac || muted) return; const t = ac.currentTime + at, o = ac.createOscillator(), f = ac.createBiquadFilter(); o.type = 'sawtooth'; o.frequency.setValueAtTime(70, t); o.frequency.linearRampToValueAtTime(130, t + dur * .4); o.frequency.linearRampToValueAtTime(95, t + dur); f.type = 'lowpass'; f.frequency.value = 420; o.connect(f); env(f, t, .05, .09, dur); o.start(t); o.stop(t + dur + .05); const n = noise(dur), f2 = ac.createBiquadFilter(); f2.type = 'highpass'; f2.frequency.value = 3000; n.connect(f2); env(f2, t, .05, .02, dur); n.start(t); },
  clunk(at = 0) { if (!ac || muted) return; const t = ac.currentTime + at, o = ac.createOscillator(); o.frequency.setValueAtTime(120, t); o.frequency.exponentialRampToValueAtTime(45, t + .12); env(o, t, .003, .5, .18); o.start(t); o.stop(t + .2); const n = noise(.06), f = ac.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 1200; n.connect(f); env(f, t, .002, .3, .06); n.start(t); },
  heads(at = 0) { if (!ac || muted) return; const t = ac.currentTime + at, o = ac.createOscillator(), f = ac.createBiquadFilter(); o.type = 'triangle'; o.frequency.setValueAtTime(40, t); o.frequency.exponentialRampToValueAtTime(300, t + 1.1); f.type = 'lowpass'; f.frequency.value = 900; o.connect(f); env(f, t, .3, .05, 1.4); o.start(t); o.stop(t + 1.5); },
  crt(at = 0) { if (!ac || muted) return; const t = ac.currentTime + at, n = noise(.25), f = ac.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 400; n.connect(f); env(f, t, .005, .4, .25); n.start(t); const o = ac.createOscillator(); o.frequency.value = 15600; env(o, t, .2, .006, 3); o.start(t); o.stop(t + 3); },
};

// ---------- the shelf ----------
const rnd = (id, n) => { let h = 0; for (const c of id + n) h = (h * 31 + c.charCodeAt(0)) >>> 0; return (h % 1000) / 1000; };
const overwritten = ['Tatort','Derrick','Skispringen','Maus','Traumschiff','Formel 1','Silvester 89','Wetten dass'];
const stickers = ['#f4f1e6','#f4f1e6','#fdf3b0','#d7ecf7','#f6d4d4','#f4f1e6'];
const sleeves = {stage:['#7d1620','#1f4b3a','#2b3f7a','#8a5a12','#4b2a5e'], short:['#c0392b','#16697a','#a0522d','#3d5a80'], backstage:['#444','#5e503f','#2f3e46']};
function look(it, i) {
  if (it.category === 'vhs') {
    const n = it.short.replace('Band ', ''), t = tapes[it.id];
    const old = !t && rnd(it.id,'o') < .45 ? `<s>${overwritten[Math.floor(rnd(it.id,'t')*overwritten.length)]}</s>` : '';
    const marker = rnd(it.id,'m') < .35;
    const label = t ? t.label : marker ? `FIDIBUS ${n}` : (old ? `Fidibus ${n}` : `Fidibus – Band ${n}`);
    return {cls: 'bare' + (marker ? ' marker' : ''), c: stickers[Math.floor(rnd(it.id,'c')*stickers.length)], label,
      html: `<div class="sticker"></div><div class="txt">${old}<span>${label}</span></div>`};
  }
  const pal = sleeves[it.category], c = pal[i % pal.length];
  const t = it.category === 'stage' ? it.title : it.title.split(' · ').reverse().join(' – ').replace('Die Schauspielerinnen und Schauspieler','Ensemble');
  return {cls: 'print', c, label: t, html: `<div class="txt"><span>${t}</span>${it.category === 'stage' ? '<small>FIDIBUS</small>' : ''}</div>`};
}
for (const [cat, label] of [['stage','Stücke'],['vhs','Bänder'],['short','Kostproben']]) {
  const b = document.createElement('div'); b.className = 'board'; b.dataset.label = label.toUpperCase();
  const list = items.filter(i => cat === 'short' ? (i.category === 'short' || i.category === 'backstage') : i.category === cat);
  list.forEach((it, i) => {
    const L = look(it, i), el = document.createElement('div');
    el.className = 'spine'; el.title = (it.play || it.title) + (it.note ? ' — ' + it.note : '');
    el.innerHTML = `<div class="sp ${L.cls}" style="--c:${L.c}">${L.html}</div>`;
    Object.assign(el, {_it: it, _look: L});
    if (pos.get(it.id) > 30) el.insertAdjacentHTML('beforeend', '<div class="rew" title="Bitte zurückspulen!">↺</div>');
    el.onclick = () => insert(el);
    b.appendChild(el);
  });
  shelf.appendChild(b);
}

// ---------- snow ----------
const cv = $('#snow'), cx = cv.getContext('2d'), img = cx.createImageData(160, 120);
(function snow() {
  if (tube.classList.contains('noise')) { for (let i = 0; i < img.data.length; i += 4) { const g = Math.random() * 255; img.data[i] = img.data[i+1] = img.data[i+2] = g; img.data[i+3] = 255; } cx.putImageData(img, 0, 0); }
  requestAnimationFrame(snow);
})();

// ---------- OSD / VFD ----------
let osdTimer;
function osd(l, sticky) { $('#osdL').textContent = l; clearTimeout(osdTimer); if (!sticky) osdTimer = setTimeout(() => $('#osdL').textContent = '', 2500); }
function vfd(txt, small = '') { $('#vfd').innerHTML = `<small>${small}</small>${txt}${loaded ? '<span class="cas-ico">▭</span>' : ''}`; }
function counter() { const t = fmt(v.currentTime); return t.length > 5 ? t : '0:' + t.padStart(5, '0'); }
v.ontimeupdate = () => {
  if (!loaded) return;
  vfd(counter(), v.paused ? 'II' : '▶ HQ'); pos.set(loaded.id, v.currentTime);
  const d = v.duration || loaded.duration; $('#prog i').style.width = (v.currentTime / d * 100) + '%'; $('#fsTime').textContent = fmt(v.currentTime) + ' / ' + fmt(d);
};

async function power(on) {
  if (on === tvOn) return; tvOn = on;
  $('#tv').classList.toggle('on', on);
  if (on) { sfx.crt(); tube.classList.remove('off','poweroff'); tube.classList.add('poweron'); await wait(500); tube.classList.remove('poweron'); if (!loaded) { tube.classList.add('bluescreen'); osd('AV  KEINE KASSETTE', true); } }
  else { tube.classList.add('poweroff'); await wait(450); tube.classList.add('off'); v.pause(); }
}
$('#pwr').onclick = () => power(!tvOn);

// ---------- cassette handling, in 3D ----------
// Box: length L (x), thickness H (y), depth D (z). The label spine faces you. `e` = how much of the depth is
// outside the machine; while inserting, the far end stays flush with the front panel (z = 0).
const L = 180, H = 24, D = 102, cas = $('#cas'), air = $('#air');
const F = {back: $('#casBack'), front: $('#casFront'), top: $('#casTop'), bottom: $('#casBottom'), l: $('#casL'), r: $('#casR')};
const box = (el, w, h, tf) => { el.style.cssText = `width:${w}px;height:${h}px;left:${-w / 2}px;top:${-h / 2}px;transform:${tf}`; };
let pose = null;
function render(p) {
  pose = p; if (window.__trace) window.__trace.push([performance.now(), p.x, p.y, p.z, p.rx, p.rz, p.e]); const e = Math.max(.5, p.e);
  cas.style.transform = `translate3d(${p.x}px,${p.y}px,${p.z}px) rotateY(${p.ry || 0}deg) rotateX(${p.rx || 0}deg) rotateZ(${p.rz || 0}deg)`;
  box(F.back, L, H, `translateZ(${e / 2}px)`);
  box(F.front, L, H, `rotateY(180deg) translateZ(${e / 2}px)`);
  box(F.top, L, e, `rotateX(90deg) translateZ(${H / 2}px)`);
  box(F.bottom, L, e, `rotateX(-90deg) translateZ(${H / 2}px)`);
  box(F.l, e, H, `rotateY(-90deg) translateZ(${L / 2}px)`);
  box(F.r, e, H, `rotateY(90deg) translateZ(${L / 2}px)`);
  // where the top face meets the slot it gets dark (ambient occlusion); only while it is in the slot
  $('#casAO').style.opacity = p.e < D - .5 ? 1 : 0;
  // contact shadow on the VCR front grows as the cassette gets close / sits in the slot
  const o = slotCenter(), near = Math.max(0, 1 - Math.hypot(p.x - o.x, p.y - o.y, p.z - D / 2) / 160);
  $('#slotShadow').style.opacity = (p.e < D - .5 ? .35 + .5 * p.e / D : .8 * near).toFixed(3);
}
function dressCassette(spine) {
  const Lk = spine._look, it = spine._it;
  F.back.innerHTML = `<div class="sp ${Lk.cls}" style="--c:${Lk.c};inset:auto;left:${L / 2 - H / 2}px;top:${H / 2 - L / 2}px;width:${H}px;height:${L}px;transform:rotate(90deg)">${Lk.html}</div>`;
  const lab = $('#casLab'); lab.className = 'lab' + (Lk.cls === 'print' ? ' print' : ''); lab.style.setProperty('--c', Lk.c); lab.textContent = Lk.label;
  const f = Math.min(1, pos.get(it.id) / it.duration || 0);   // tape on each reel = where you stopped
  $('#casWin').style.setProperty('--r1', 13 + 18 * (1 - f) + 'px'); $('#casWin').style.setProperty('--r2', 13 + 18 * f + 'px');
}
function slotCenter() { const h = sr($('#inside')); return {x: h.x + h.w / 2, y: h.y + h.h / 2 + 1}; }
function spineCenter(spine) { const r = sr(spine), lift = matchMedia('(hover:hover)').matches && spine.matches(':hover') ? 14 : 0; return {x: r.x + r.w / 2, y: r.y + r.h / 2 - lift}; }
// the viewer sits on the sofa, eyes at the height of the TV picture: you look *down* onto the VCR
function eye() { const t = sr(tube); air.style.perspectiveOrigin = `${t.x + t.w / 2}px ${t.y + t.h * .55}px`; }

const ease = {
  io: t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
  out: t => 1 - Math.pow(1 - t, 3),
  in: t => t * t * t,
  push: t => t < .15 ? (t / .15) ** 2 * .1 : .1 + .9 * (1 - Math.pow(1 - (t - .15) / .85, 2)),   // finger finds the spine, then pushes
  motor: t => t < .2 ? (t / .2) ** 2 * .12 : .12 + .88 * ((t - .2) / .8),                        // spins up, then constant speed
  spit: t => { const b = 1 - Math.pow(1 - t, 3); return b + Math.sin(t * Math.PI) * .04; },
};
const lerp = (a, b, t) => a + (b - a) * t;
const bez = (a, c, b, t) => (1 - t) * (1 - t) * a + 2 * (1 - t) * t * c + t * t * b;
// move from pose A to pose B; positions may follow a curve through `via`
function go(A, B, ms, fn = ease.io, via = null) {
  return new Promise(res => {
    const t0 = performance.now(), dur = ms * SLOW;
    (function step(now) {
      const k = Math.min(1, Math.max(0, (now - t0) / dur)), t = fn(k), p = {};
      for (const key of ['x', 'y', 'z', 'rx', 'ry', 'rz', 'e']) p[key] = lerp(A[key] ?? 0, B[key] ?? 0, t);
      if (via) { const u = ease.io(k); p.x = bez(A.x, via.x, B.x, u); p.y = bez(A.y, via.y, B.y, u); p.z = bez(A.z, via.z, B.z, u); }
      // inserting: keep the far end flush with the panel
      if (B.flush && A.flush) p.z = p.e / 2;
      render(p);
      k < 1 ? requestAnimationFrame(step) : res(p);
    })(t0);
  });
}
const flap = $('#flap'), vcrEl = $('#vcr');
function thud() { for (const el of [vcrEl, $('#vcrTop')]) { el.classList.remove('thud'); void el.offsetWidth; el.classList.add('thud'); } }
// One continuous move through several poses: a Catmull-Rom spline through all of them (position *and*
// rotation), timed by arc length with a single minimum-jerk speed profile, so it never stops in mid-air.
const minJerk = t => t * t * t * (10 - 15 * t + 6 * t * t);
const KEYS = ['x', 'y', 'z', 'rx', 'ry', 'rz'];
function flight(pts, ms, profile = minJerk) {
  pts = pts.map(p => ({rx: 0, ry: 0, rz: 0, ...p}));
  const n = pts.length - 1;
  const cr = (a, b, c, d, u) => .5 * (2 * b + (c - a) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (3 * b - a - 3 * c + d) * u * u * u);
  const at = s => {                                   // s in [0, n]: spline position through all poses
    const i = Math.min(n - 1, Math.floor(s)), u = s - i, p = {e: D};
    const a = pts[Math.max(0, i - 1)], b = pts[i], c = pts[i + 1], d = pts[Math.min(n, i + 2)];
    for (const key of KEYS) p[key] = cr(a[key], b[key], c[key], d[key], u);
    return p;
  };
  // sample densely and measure the real distance travelled (rotation counts too), so the speed along the
  // whole path follows the profile exactly instead of changing from one segment to the next
  const N = 600, table = [0]; let prev = at(0);
  for (let j = 1; j <= N; j++) { const q = at(j / N * n); table.push(table[j - 1] + Math.hypot(q.x - prev.x, q.y - prev.y, q.z - prev.z, 2.2 * (q.rx - prev.rx), 2.2 * (q.ry - prev.ry), 2.2 * (q.rz - prev.rz))); prev = q; }
  const L = table[N] || 1;
  const sOf = g => { const target = g * L; let lo = 0, hi = N; while (hi - lo > 1) { const m = (lo + hi) >> 1; table[m] < target ? lo = m : hi = m; } const f = (target - table[lo]) / ((table[hi] - table[lo]) || 1); return (lo + f) / N * n; };
  const seed = Math.random() * 10;
  return new Promise(res => {
    const t0 = performance.now(), dur = ms * SLOW;
    (function step(now) {
      const k = Math.min(1, Math.max(0, (now - t0) / dur)), g = profile(k), p = at(sOf(g));
      // a living hand: a little tremor, strongest mid-flight, gone at both ends
      const w = Math.sin(Math.PI * g), tt = (now - t0) / 1000 / SLOW + seed;
      p.rz += w * .8 * Math.sin(tt * 4.3); p.rx += w * .6 * Math.sin(tt * 3.1 + 1); p.y += w * 1.2 * Math.sin(tt * 2.7 + 2);
      render(p);
      k < 1 ? requestAnimationFrame(step) : res(p);
    })(t0);
  });
}
function poses(spine) {
  const s = spineCenter(spine), o = slotCenter();
  return {
    shelf:  {x: s.x, y: s.y, z: 0, rz: -90, e: D},
    pulled: {x: s.x, y: s.y - 6, z: 70, rz: -90, rx: 0, ry: 8, e: D},
    hand:   {x: o.x - 70, y: o.y - 250, z: 470, rx: -48, ry: 6, rz: -10, e: D},   // in your hand, in front of the screen   // held in front of you, label up
    lineup: {x: o.x + 6, y: o.y - 34, z: D / 2 + 90, rx: -10, rz: -3, e: D},
    touch:  {x: o.x + 2, y: o.y - 3, z: D / 2 + 6, rx: -3, rz: -1.2, e: D},
    mouth:  {x: o.x, y: o.y, z: D / 2 + .5, e: D, flush: true},
    o,
  };
}
async function takeOut(spine) {
  eye(); dressCassette(spine);
  const P = poses(spine);
  render(P.shelf); cas.style.display = 'block'; spine.classList.add('out');
  sfx.slide(.3);
  // off the shelf, label-up in your hand, over to the machine, into the guides: one movement
  await flight([P.shelf, P.pulled, P.hand, P.lineup, P.touch, P.mouth], 2100);
}
async function pushIn(spine) {
  const P = poses(spine), M = P.mouth;
  sfx.click(); flap.classList.add('open'); sfx.slide(.45);
  const pushed = {...M, e: D * .58, flush: true};
  await go(M, pushed, 520, ease.push);                                 // your hand pushes it a good way in
  await wait(140);                                                     // …the machine feels it…
  sfx.motor(.75); vfd('LOAD');
  await go(pushed, {...M, e: 0, flush: true}, 560, ease.motor);        // …and draws it in
  cas.style.display = 'none'; $('#slotShadow').style.opacity = 0;
  flap.classList.remove('open'); sfx.click(.04);
  await wait(260); sfx.clunk(); thud();                                // lowered onto the drum
  sfx.heads(.2);
}
async function pushOut(spine) {
  eye(); dressCassette(spine);
  const P = poses(spine), M = P.mouth;
  sfx.motor(.7); sfx.clunk(.02); thud();
  await wait(320);
  flap.classList.add('open'); sfx.click(); cas.style.display = 'block';
  await go({...M, e: 0, flush: true}, {...M, e: D * .42, flush: true}, 620, ease.spit);   // spits it half out
}
async function putBack(spine) {
  const P = poses(spine), M = P.mouth;
  sfx.slide(.35);
  await go({...M, e: D * .42, flush: true}, {...M, e: D, flush: true}, 300, ease.in);   // grab it and pull…
  flap.classList.remove('open'); sfx.click(.03);
  // …and keep going without a stop: back up, turn it, slide it into its gap
  const out = {...M, z: D / 2, flush: false};
  const m0 = minJerk(.25);   // start already moving (you are pulling), then come smoothly to rest in the shelf
  await flight([out, P.lineup, P.hand, P.pulled, P.shelf], 1900, t => (minJerk(.25 + .75 * t) - m0) / (1 - m0));
  sfx.slide(.25);
  spine.classList.remove('out'); cas.style.display = 'none';
}
if (new URLSearchParams(location.search).has('debug')) window.__fid = {poses, render, dressCassette, eye, D, cas, spines: () => [...document.querySelectorAll('.spine')]};

// ---------- VCR logic ----------
async function eject() {
  if (!loaded || busy) return; busy = true;
  if (zoomed) { zoom(false); await wait(1500); }
  clearInterval(seekTimer); seekTimer = null; v.pause(); vfd('EJECT');
  const spine = loadedSpine, it = loaded; loaded = null; loadedSpine = null;
  dressCassette(spine);
  osd('⏏', true); tube.classList.remove('vhsfx','noise','seek'); tube.classList.add('bluescreen');
  v.removeAttribute('src'); v.load();
  await pushOut(spine); await wait(250); await putBack(spine);
  if (pos.get(it.id) > 30 && !spine.querySelector('.rew')) spine.insertAdjacentHTML('beforeend', '<div class="rew" title="Bitte zurückspulen!">↺</div>');
  vfd('--:--'); osd('AV  KEINE KASSETTE', true); busy = false;
}

async function insert(spine) {
  if (busy || spine === loadedSpine) return;
  const it = spine._it;
  // iOS only lets a video start with sound from inside a tap. Start it *now*, muted and hidden,
  // so it is buffering while the cassette travels; it is un-muted once the tape is in.
  if (loaded) await eject();
  busy = true;
  autoZoom = sessionStorage.getItem('fid-room') !== '1';
  if (autoZoom) enterPageFS();
  v.src = it.src; v.muted = true; tube.classList.add('hidevid'); v.play().catch(() => {});
  const r = pos.get(it.id);
  if (!tvOn) power(true);
  await takeOut(spine);
  await pushIn(spine);
  loaded = it; loadedSpine = spine;
  tube.classList.remove('bluescreen'); tube.classList.add('noise'); osd('', true);
  tube.classList.toggle('vhsfx', it.category === 'vhs');
  await wait(900);
  v.pause(); v.currentTime = r > 30 ? r : 0; tube.classList.remove('hidevid');
  busy = false;
  play();
  // let the picture come up on the set for a moment, then move in
  setTimeout(() => { if (loaded === it) autoZoom ? zoom(true) : hintRoom(); }, 1300);
  if (it.play) osd(it.play.toUpperCase(), false);
}

function play() {
  if (!loaded) return toast('Keine Kassette eingelegt.');
  clearInterval(seekTimer); seekTimer = null; tube.classList.remove('seek','bluescreen');
  v.muted = false;
  v.play().then(() => { tube.classList.remove('noise'); $('#osdB').textContent = ''; }).catch(() => {
    // Safari refused sound without a fresh tap: ask for one
    $('#osdB').textContent = '▶ ZUM ABSPIELEN TIPPEN'; tube.classList.remove('noise');
  });
  v.addEventListener('playing', () => tube.classList.remove('noise'), {once: true});
  osd('▶ PLAY'); $('[data-f=pp]').textContent = '❚❚';
}
function pause() { if (!loaded) return; v.pause(); osd('❚❚', true); $('[data-f=pp]').textContent = '▶'; }
function stop() { if (!loaded) return; v.pause(); osd('■ STOP'); tube.classList.add('bluescreen'); vfd(counter(), '■'); }
function search(dir) {
  if (!loaded) return;
  v.pause(); tube.classList.add('seek'); tube.classList.remove('bluescreen'); sfx.motor(.4);
  osd(dir > 0 ? '▶▶ SUCHLAUF' : '◀◀ SUCHLAUF', true);
  let speed = 4;
  seekTimer = setInterval(() => { speed = Math.min(speed * 1.08, 60); v.currentTime = Math.max(0, v.currentTime + dir * speed); v.ontimeupdate(); }, 110);
}
function endSearch() { if (!seekTimer) return; clearInterval(seekTimer); seekTimer = null; tube.classList.remove('seek'); play(); }
function hold(btn, dir) {
  btn.onpointerdown = e => { e.preventDefault(); btn.setPointerCapture?.(e.pointerId); btn.classList.add('held'); sfx.click(); search(dir); };
  btn.onpointerup = btn.onpointercancel = () => { btn.classList.remove('held'); endSearch(); };
  btn.oncontextmenu = e => e.preventDefault();
}
document.querySelectorAll('.btns button').forEach(b => {
  const k = b.dataset.k;
  if (k === 'ff' || k === 'rew') hold(b, k === 'ff' ? 1 : -1);
  else b.onclick = () => { sfx.click(); ({eject, play, pause, stop, full: fullscreen, rec: () => toast('Schreibschutz! Die Lasche ist rausgebrochen. ✂')})[k](); };
});

// remote control: index search 0–9 jumps to 0 %…90 % of the tape
const remote = $('#remote');
['1','2','3','4','5','6','7','8','9','◀◀','0','▶▶'].forEach(n => {
  const b = document.createElement('button'); b.textContent = n; remote.appendChild(b);
  if (/\d/.test(n)) b.onclick = () => { if (!loaded) return; tube.classList.add('seek'); osd('INDEX ' + n, true); v.currentTime = (v.duration || loaded.duration) * (+n) / 10; setTimeout(() => { tube.classList.remove('seek'); play(); }, 600); };
  else { const d = n === '▶▶' ? 30 : -30; b.onclick = () => { if (loaded) { v.currentTime += d; osd(n + ' ' + (d > 0 ? '+' : '') + d + 's'); } }; }
});
['▶','❚❚','⏏'].forEach((n, i) => { const b = document.createElement('button'); b.textContent = n; b.onclick = [play, () => v.paused ? play() : pause(), eject][i]; remote.appendChild(b); });

// volume knob (iOS ignores video.volume — then say so)
let vy = null; const knob = $('#vol');
knob.onpointerdown = e => { vy = e.clientY; knob.setPointerCapture(e.pointerId); };
knob.onpointermove = e => {
  if (vy === null) return; const before = v.volume, want = Math.min(1, Math.max(0, v.volume - (e.clientY - vy) / 150)); vy = e.clientY;
  v.volume = want; if (v.volume === before && want !== before) { toast('Lautstärke bitte am Gerät einstellen.'); vy = null; return; }
  knob.style.transform = `rotate(${v.volume * 270 - 135}deg)`; osd('LAUTST. ' + '▮'.repeat(Math.round(v.volume * 12)));
};
knob.onpointerup = () => vy = null;

// ---------- full screen = the camera moves into the TV ----------
// The tap on a tape is the only moment the browser allows real fullscreen, so the page goes fullscreen right
// then (the room fills the screen); once the picture is on, the camera dollies into the set.
// iPhone has no page fullscreen: there only the camera move happens.
const docFS = () => !!(document.fullscreenElement || document.webkitFullscreenElement);
function enterPageFS() {
  const el = document.documentElement, rq = el.requestFullscreen || el.webkitRequestFullscreen;
  if (rq && !docFS() && sessionStorage.getItem('fid-room') !== '1') try { const r = rq.call(el, {navigationUI: 'hide'}); r?.catch?.(() => {}); } catch {}
}
function zoom(on) {
  if (on === zoomed) return;
  if (on && !loaded) return toast('Erst eine Kassette einlegen.');
  zoomed = on; document.body.classList.toggle('zoomed', on); tube.classList.remove('hint');
  if (on) { calmSoon(); screen.orientation?.lock?.('landscape').catch(() => {}); }
  else { clearTimeout(calmT); document.body.classList.remove('calm'); if (docFS()) (document.exitFullscreen || document.webkitExitFullscreen).call(document); }
  stage.classList.add('moving'); fit(); clearTimeout(zoom.t); zoom.t = setTimeout(() => stage.classList.remove('moving'), 1700);
}
function fullscreen() { if (!zoomed) enterPageFS(); zoom(!zoomed); }
// leaving browser fullscreen (Esc, swipe) also steps back into the room
const onFSchange = () => { if (!docFS() && zoomed) zoom(false); };
document.addEventListener('fullscreenchange', onFSchange); document.addEventListener('webkitfullscreenchange', onFSchange);
tube.addEventListener('click', () => {
  if ($('#osdB').textContent) { play(); return; }               // the "tap to play" fallback
  if (zoomed) { document.body.classList.toggle('calm'); if (!document.body.classList.contains('calm')) calmSoon(); return; }
  fullscreen();
});
let calmT; function calmSoon() { clearTimeout(calmT); calmT = setTimeout(() => document.body.classList.add('calm'), 3000); }
addEventListener('pointermove', () => { if (zoomed) { document.body.classList.remove('calm'); calmSoon(); } });
let hintT; function hintRoom() { if (zoomed || !loaded) return; tube.classList.remove('hint'); void tube.offsetWidth; tube.classList.add('hint'); clearTimeout(hintT); hintT = setTimeout(() => tube.classList.remove('hint'), 6000); }
document.querySelectorAll('.fsbar button').forEach(b => {
  const f = b.dataset.f;
  if (f === 'ff' || f === 'rew') hold(b, f === 'ff' ? 1 : -1);
  else b.onclick = e => { e.stopPropagation(); calmSoon(); if (f === 'pp') v.paused ? play() : pause(); if (f === 'exit') { sessionStorage.setItem('fid-room', '1'); zoom(false); hintRoom(); } };
});
v.addEventListener('loadedmetadata', () => { if (zoomed) fit(); });
const prog = $('#prog');
prog.onpointerdown = e => { e.stopPropagation(); const r = prog.getBoundingClientRect(); if (loaded) { v.currentTime = (v.duration || loaded.duration) * Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)); osd('▶▶ SPRUNG'); } };

addEventListener('keydown', e => {
  if (e.code === 'Space') { e.preventDefault(); v.paused ? play() : pause(); }
  if (e.key === 'ArrowRight') v.currentTime += 10;
  if (e.key === 'ArrowLeft') v.currentTime -= 10;
  if (e.key === 'f') fullscreen();
  if (e.key === 'Escape' && zoomed) { sessionStorage.setItem('fid-room', '1'); zoom(false); hintRoom(); }
});
v.onended = () => { osd('■ BANDENDE', true); vfd('END'); };
let tt; function toast(t) { $('#toast').textContent = t; $('#toast').classList.add('show'); clearTimeout(tt); tt = setTimeout(() => $('#toast').classList.remove('show'), 2600); }
