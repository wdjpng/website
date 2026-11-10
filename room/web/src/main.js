import * as THREE from 'three';
import { SparkRenderer, SplatMesh, SparkXr } from '@sparkjsdev/spark';
import { WalkControls } from './controls.js';
import { WalkMap } from './walkmap.js';
import { arSupported } from './motion.js';

const ASSET_BASE = './assets/';

const canvas = document.getElementById('c');
const loaderEl = document.getElementById('loader');
const barFill = document.getElementById('bar-fill');
const loaderText = document.getElementById('loader-text');
const hud = document.getElementById('hud');
const hint = document.getElementById('hint');

const params = new URLSearchParams(location.search);

// static Cycles render of the start view while the splats load
const poster = document.getElementById('poster');
poster.onload = () => poster.classList.add('shown');
poster.src = ASSET_BASE + (window.innerHeight > window.innerWidth ? 'poster-mobile.jpg' : 'poster-desktop.jpg');
const isTouch = params.get('touch') === '1' || matchMedia('(pointer: coarse)').matches || (navigator.maxTouchPoints > 1 && 'ontouchend' in document);

function fail(msg) {
  loaderEl.classList.add('done');
  const d = document.createElement('div');
  d.id = 'error';
  d.textContent = msg;
  document.body.appendChild(d);
}

let renderer;
try {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance', alpha: false, stencil: true });
} catch (e) {
  fail('Sorry, this browser could not start WebGL, which the 3D room needs.');
  throw e;
}
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.setClearColor(0x000000, 1); // the splats were trained over black (except behind the window glass)

// ---- quality tier ----
const gl = renderer.getContext();
const dpr = window.devicePixelRatio || 1;
const smallScreen = Math.min(screen.width, screen.height) < 600;
const mobile = isTouch || smallScreen;
const tier = params.get('q') || (mobile ? 'mobile' : 'high');
let maxPixelRatio = Math.min(dpr, tier === 'high' ? 2 : 2);
let pixelRatio = Math.min(dpr, tier === 'high' ? 1.5 : 1.25);
if (params.get('pr')) pixelRatio = maxPixelRatio = parseFloat(params.get('pr'));
renderer.setPixelRatio(pixelRatio);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.02, 400);
// the camera sits in a rig; outside VR the rig is the identity, in VR it carries the walk position and heading
const rig = new THREE.Group();
rig.add(camera);
scene.add(rig);

let needsRender = true;
const spark = new SparkRenderer({
  renderer,
  onDirty: () => { needsRender = true; },
  // phones: trim the faint outer tails of each Gaussian to save fill rate
  // draw each Gaussian out to 3 sigma like the trainer (gsplat); cutting the tails earlier leaves faint rings
  // that make flat walls look mottled. Phones stop a little earlier to save fill rate.
  maxStdDev: params.get('sd') ? parseFloat(params.get('sd')) : (tier === 'mobile' ? Math.sqrt(8) : 3.0),
  clipXY: 2.0,
  // sort by view depth like the trainer; Spark's radial sort (?sort=radial) blends overlapping wall splats in a
  // different order than in training, which shows up as blotches
  sortRadial: params.get('sort') === 'radial',
});
scene.add(spark);

function draw() {
  renderer.render(scene, camera);
}

let controls = null;
function baseFov() {
  const portrait = window.innerHeight > window.innerWidth;
  return portrait ? 80 : 68;
}
function resize(resetFov = true) {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  if (resetFov) {
    if (controls) controls.fovTarget = baseFov();
    else camera.fov = baseFov();
  }
  camera.updateProjectionMatrix();
  needsRender = true;
  // redraw immediately: a resized canvas is cleared and would otherwise flash for a frame
  if (controls && !renderer.xr.isPresenting) { draw(); needsRender = false; }
}
window.addEventListener('resize', () => resize(true));
resize();

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

// download with byte progress
async function fetchBytes(url, onBytes) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  const total = Number(r.headers.get('content-length')) || 0;
  if (!r.body || !r.body.getReader) {
    const b = new Uint8Array(await r.arrayBuffer());
    onBytes(b.length, b.length);
    return b;
  }
  const reader = r.body.getReader();
  const chunks = [];
  let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    got += value.length;
    onBytes(got, total);
  }
  const out = new Uint8Array(got);
  let o = 0;
  for (const c of chunks) { out.set(c, o); o += c.length; }
  return out;
}

const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);

// The view out of the window: a partial sphere textured with a Cycles panorama (exterior only).
// Same mapping as the training background (see train_gs.py): Blender coords, looking along -X.
function buildExterior(ext) {
  // versioned URL: the image and its lat/lon range in room.json must never come from different deploys
  const tex = new THREE.TextureLoader().load(ASSET_BASE + ext.file + '?v=' + __BUILD__, () => { needsRender = true; });
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  const a = THREE.MathUtils.degToRad(ext.lon_half_deg);
  const la0 = THREE.MathUtils.degToRad(ext.lat_min_deg), la1 = THREE.MathUtils.degToRad(ext.lat_max_deg);
  const R = ext.radius;
  const [cx, cy, cz] = ext.center; // blender
  const nu = 128, nv = 96;
  const pos = new Float32Array((nu + 1) * (nv + 1) * 3);
  const uv = new Float32Array((nu + 1) * (nv + 1) * 2);
  let k = 0, m = 0;
  for (let j = 0; j <= nv; j++) {
    const v = j / nv, lat = la0 + (la1 - la0) * v;
    for (let i = 0; i <= nu; i++) {
      const u = i / nu, phi = a - 2 * a * u;
      // blender: fwd=(-1,0,0), left=(0,-1,0), up=(0,0,1)
      const bx = cx - R * Math.cos(lat) * Math.cos(phi);
      const by = cy - R * Math.cos(lat) * Math.sin(phi);
      const bz = cz + R * Math.sin(lat);
      pos[k++] = bx; pos[k++] = bz; pos[k++] = -by; // -> three
      uv[m++] = u; uv[m++] = v;
    }
  }
  const idx = [];
  for (let j = 0; j < nv; j++) for (let i = 0; i < nu; i++) {
    const p = j * (nu + 1) + i;
    idx.push(p, p + 1, p + nu + 1, p + 1, p + nu + 2, p + nu + 1);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setIndex(idx);
  // the panorama is only drawn through the window opening (stencil portal), never behind the walls
  const mat = new THREE.MeshBasicMaterial({
    map: tex, side: THREE.DoubleSide, toneMapped: false,
    stencilWrite: true, stencilRef: 1, stencilFunc: THREE.EqualStencilFunc,
    stencilFail: THREE.KeepStencilOp, stencilZFail: THREE.KeepStencilOp, stencilZPass: THREE.KeepStencilOp,
  });
  const mesh = new THREE.Mesh(g, mat);
  mesh.renderOrder = -1;
  mesh.frustumCulled = false;
  const group = new THREE.Group();
  group.add(mesh);
  if (ext.portal) {
    const [x, y0, z0, y1, z1] = ext.portal; // blender: plane x, y range, z range
    const pg = new THREE.BufferGeometry();
    pg.setAttribute('position', new THREE.BufferAttribute(new Float32Array([
      x, z0, -y0, x, z0, -y1, x, z1, -y1, x, z1, -y0,
    ]), 3));
    pg.setIndex([0, 1, 2, 0, 2, 3]);
    const pm = new THREE.MeshBasicMaterial({
      colorWrite: false, depthWrite: false, side: THREE.DoubleSide,
      stencilWrite: true, stencilRef: 1, stencilFunc: THREE.AlwaysStencilFunc, stencilZPass: THREE.ReplaceStencilOp,
    });
    const portal = new THREE.Mesh(pg, pm);
    portal.renderOrder = -2;
    portal.frustumCulled = false;
    group.add(portal);
  } else {
    mat.stencilWrite = false;
  }
  return group;
}
const raycaster = new THREE.Raycaster();

async function init() {
  const meta = await fetchJSON(ASSET_BASE + 'room.json?v=' + __BUILD__);
  const walk = new WalkMap(await fetchJSON(ASSET_BASE + 'walkmap.json?v=' + __BUILD__));
  const entry = meta.splats[tier] || meta.splats.mobile;
  if (meta.exterior) scene.add(buildExterior(meta.exterior));
  loaderText.textContent = 'Loading room…';
  const bytes = await fetchBytes(ASSET_BASE + entry.file, (l, t) => {
    const total = t || entry.bytes || 0;
    if (total) {
      barFill.style.width = `${Math.min(99, Math.round((l / total) * 100))}%`;
      loaderText.textContent = `Loading room… ${(l / 1e6).toFixed(0)} / ${(total / 1e6).toFixed(0)} MB`;
    }
  });
  loaderText.textContent = 'Preparing…';
  const shOpt = params.get('sh') != null ? { maxSh: parseInt(params.get('sh'), 10) } : (meta.maxSh != null ? { maxSh: meta.maxSh } : {});
  const splats = new SplatMesh({ fileBytes: bytes, fileName: entry.file.split('?')[0], extSplats: !!entry.ext, ...shOpt });
  await splats.initialized;
  // trained in Blender coordinates (Z up) -> three.js (Y up); the file is recentred on the room
  splats.quaternion.setFromAxisAngle(new THREE.Vector3(1, 0, 0), -Math.PI / 2);
  if (meta.splatOffset && !entry.noOffset) splats.position.fromArray(meta.splatOffset);
  scene.add(splats);

  controls = new WalkControls(camera, canvas, walk, { eyeHeight: meta.eyeHeight ?? 1.6, speed: isTouch ? 1.0 : 1.25 });
  if (isTouch) controls.enableStick();

  const start = meta.start;
  controls.setPose(start.x, start.z, start.yaw, start.pitch ?? 0);
  resize();

  const room = meta.room; // interior box in three coords
  const box = new THREE.Box3(new THREE.Vector3(room.min[0], 0, room.min[2]), new THREE.Vector3(room.max[0], room.max[1], room.max[2]));
  controls.onTap = (nx, ny) => {
    raycaster.setFromCamera({ x: nx, y: ny }, camera);
    const ray = raycaster.ray;
    const hit = new THREE.Vector3();
    let tx, tz;
    if (ray.direction.y < -0.02 && ray.intersectPlane(floorPlane, hit) && box.containsPoint(new THREE.Vector3(hit.x, 0.1, hit.z))) {
      tx = hit.x; tz = hit.z;
    } else {
      // aim at a wall: walk towards it and stop a little before
      const far = ray.at(20, new THREE.Vector3());
      const inv = new THREE.Ray(far, ray.direction.clone().negate());
      if (!inv.intersectBox(box, hit)) return null;
      const dir = new THREE.Vector2(hit.x - camera.position.x, hit.z - camera.position.z);
      const d = dir.length();
      if (d < 0.5) return null;
      dir.multiplyScalar((d - 0.45) / d);
      tx = camera.position.x + dir.x; tz = camera.position.z + dir.y;
    }
    return walk.nearest(tx, tz, 1.2);
  };

  // ---- HUD ----
  hint.textContent = isTouch
    ? 'Drag to look around · stick to walk · tap the floor to go there'
    : 'Drag to look · WASD / arrows or two-finger scroll to walk · click the floor to go there';
  if (isTouch) hint.classList.add('touch');
  let hintTimer = null;
  controls.onInteract = () => {
    if (hintTimer) return;
    hintTimer = setTimeout(() => hint.classList.add('faded'), 6000);
  };

  document.getElementById('btn-reset').addEventListener('click', (e) => {
    e.stopPropagation();
    controls.setPose(start.x, start.z, start.yaw, start.pitch ?? 0);
  });

  const sitBtn = document.getElementById('btn-sit');
  if (isTouch) {
    sitBtn.hidden = false;
    sitBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const low = controls.toggleCrouch();
      sitBtn.textContent = low ? 'Stand' : 'Sit';
      sitBtn.classList.toggle('on', low);
    });
  }

  // Motion: on Android phones with ARCore, a WebXR AR session tracks the phone's real position (walk around and the
  // view moves 1:1). Elsewhere (iPhone) turning the phone looks around and walking with it is detected step by step.
  const gyroBtn = document.getElementById('btn-gyro');
  if (isTouch && (typeof DeviceOrientationEvent !== 'undefined' || navigator.xr)) {
    gyroBtn.hidden = false;
    let canAR = false;
    arSupported().then((v) => { canAR = v; });
    gyroBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (canAR && !controls.gyro.enabled) {
        if (await startAR()) return;
      }
      if (controls.gyro.enabled) {
        controls.disableGyro();
        gyroBtn.classList.remove('on');
        showHint(null);
      } else if (await controls.enableGyro(true)) {
        gyroBtn.classList.add('on');
        showHint('Turn your phone to look around · walk with it to move');
      } else {
        showHint('Motion access was not allowed');
      }
    });
  }

  hud.hidden = false;
  showHint = (text) => {
    if (!text) { hint.classList.add('faded'); return; }
    hint.textContent = text;
    hint.classList.remove('faded');
    clearTimeout(showHint.t);
    showHint.t = setTimeout(() => hint.classList.add('faded'), 7000);
  };
  last = performance.now();
  needsRender = true;
  renderer.setAnimationLoop(frame);
  setupXr(walk);
  // let the first sort finish before revealing
  setTimeout(() => loaderEl.classList.add('done'), 350);
}

// ---- frame loop with adaptive resolution ----
let last = 0;
let showHint = () => {};
const debugPose = params.get('debugpose') ? params.get('debugpose').split(',').map(Number) : null;
let debugFirst = true;
let frameTimes = [];
let lastAdapt = 0;
let prCeiling = Infinity;

function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000);
  last = now;
  if (renderer.xr.isPresenting) { xrFrame(dt); return; }
  let moved = debugPose ? debugFirst : controls.update(dt);
  if (debugPose) {
    debugFirst = false;
    const [x, y, z, yaw, pitch, fov] = debugPose;
    camera.position.set(x, y, z);
    camera.quaternion.setFromEuler(new THREE.Euler(pitch, yaw, 0, 'YXZ'));
    if (fov) { camera.fov = fov; camera.updateProjectionMatrix(); }
  }
  if (!(moved || needsRender)) { frameTimes = []; return; }
  needsRender = false;
  draw();

  if (moved) {
    frameTimes.push(dt);
    if (frameTimes.length > 45) frameTimes.shift();
  }
  if (!params.get('pr') && now - lastAdapt > 1500 && frameTimes.length >= 40) {
    const sorted = [...frameTimes].sort((a, b) => a - b);
    const med = sorted[Math.floor(sorted.length / 2)];
    if (med > 1 / 36 && pixelRatio > 0.6) {
      // too slow: step down, and never come back above this level (prevents ping-ponging)
      prCeiling = pixelRatio - 0.2;
      setPixelRatioNow(Math.max(0.6, pixelRatio - 0.2));
      lastAdapt = now; frameTimes = [];
    } else if (med < 1 / 57 && pixelRatio < Math.min(maxPixelRatio, prCeiling)) {
      setPixelRatioNow(Math.min(maxPixelRatio, prCeiling, pixelRatio + 0.2));
      lastAdapt = now; frameTimes = [];
    }
  }
}

// change resolution and draw straight away, so the browser never shows a cleared canvas
function setPixelRatioNow(pr) {
  pixelRatio = pr;
  renderer.setPixelRatio(pr);
  resize(false);
  draw();
  needsRender = false;
}

// ---- WebXR (headsets such as Quest or Vision Pro): head tracking, left stick walks, right stick turns ----
let xrWalk = null;
let snapLatch = false;
const _v = new THREE.Vector3();
function setupXr(walk) {
  xrWalk = walk;
  if (!navigator.xr) return;
  try {
    new SparkXr({
      renderer,
      elementId: 'btn-vr',
      mode: 'vr',
      referenceSpaceType: 'local-floor',
      frameBufferScaleFactor: 1.0,
      onEnterXr: () => {
        const c = controls;
        rig.position.set(c.pos.x, 0, c.pos.y);
        rig.rotation.set(0, c.yaw, 0);
        camera.position.set(0, 0, 0);
        camera.quaternion.identity();
      },
      onExitXr: () => {
        rig.position.set(0, 0, 0);
        rig.rotation.set(0, 0, 0);
        controls.changed = true;
        needsRender = true;
      },
    });
  } catch (e) { console.warn('XR unavailable', e); }
}
// ---- AR walking (Android Chrome + ARCore): the phone's tracked position drives the camera, 1:1 in metres ----
let arSession = null;
let arAlign = false;
let backdrop = null;
async function startAR() {
  const overlay = document.getElementById('xr-overlay');
  let session;
  try {
    session = await navigator.xr.requestSession('immersive-ar', {
      requiredFeatures: ['local-floor'],
      optionalFeatures: ['dom-overlay'],
      domOverlay: { root: overlay },
    });
  } catch (e) {
    console.warn('AR session failed', e);
    return false;
  }
  if (!backdrop) {
    // AR clears to transparent (camera image); the room must stay opaque, so draw a black backdrop first
    backdrop = new THREE.Mesh(new THREE.SphereGeometry(150, 16, 12), new THREE.MeshBasicMaterial({ color: 0x000000, side: THREE.BackSide, depthWrite: false }));
    backdrop.renderOrder = -10;
    backdrop.frustumCulled = false;
    scene.add(backdrop);
  }
  backdrop.visible = true;
  renderer.xr.enabled = true;
  renderer.xr.setReferenceSpaceType('local-floor');
  renderer.xr.setFramebufferScaleFactor(tier === 'mobile' ? 0.8 : 1.0);
  rig.position.set(0, 0, 0);
  rig.rotation.set(0, 0, 0);
  camera.position.set(0, 0, 0);
  camera.quaternion.identity();
  arSession = session;
  arAlign = true;
  overlay.hidden = false;
  document.getElementById('xr-exit').onclick = () => session.end();
  session.addEventListener('end', () => {
    // continue in the normal view from where you walked to
    const cam = renderer.xr.getCamera();
    const p = new THREE.Vector3(), d = new THREE.Vector3();
    cam.getWorldPosition(p);
    cam.getWorldDirection(d);
    arSession = null;
    overlay.hidden = true;
    backdrop.visible = false;
    rig.position.set(0, 0, 0);
    rig.rotation.set(0, 0, 0);
    if (Number.isFinite(p.x)) controls.setPose(p.x, p.z, Math.atan2(-d.x, -d.z), 0);
    controls.changed = true;
    needsRender = true;
  });
  await renderer.xr.setSession(session);
  return true;
}

// place the AR origin so that the phone starts where you were standing, looking the same way
function alignAR() {
  const frame = renderer.xr.getFrame();
  const ref = renderer.xr.getReferenceSpace();
  if (!frame || !ref) return;
  const pose = frame.getViewerPose(ref);
  if (!pose) return;
  const t = pose.transform;
  const q = new THREE.Quaternion(t.orientation.x, t.orientation.y, t.orientation.z, t.orientation.w);
  const f = new THREE.Vector3(0, 0, -1).applyQuaternion(q);
  const psi0 = Math.atan2(-f.x, -f.z);
  const theta = controls.yaw - psi0;
  rig.rotation.set(0, theta, 0);
  const p0 = new THREE.Vector3(t.position.x, 0, t.position.z).applyAxisAngle(new THREE.Vector3(0, 1, 0), theta);
  rig.position.set(controls.pos.x - p0.x, 0, controls.pos.y - p0.z);
  arAlign = false;
}

function xrFrame(dt) {
  if (arSession) {
    if (arAlign) alignAR();
    renderer.render(scene, camera);
    return;
  }
  const session = renderer.xr.getSession();
  let mx = 0, my = 0, turn = 0;
  if (session) {
    for (const src of session.inputSources) {
      const gp = src.gamepad;
      if (!gp || !gp.axes) continue;
      const ax = gp.axes;
      const x = ax.length >= 4 ? ax[2] : ax[0];
      const y = ax.length >= 4 ? ax[3] : ax[1];
      if (src.handedness === 'left') { mx = x; my = y; } else if (src.handedness === 'right') turn = x;
    }
  }
  const xrCam = renderer.xr.getCamera();
  xrCam.getWorldPosition(_v);
  const head = _v.clone();
  if (Math.hypot(mx, my) > 0.15) {
    const dir = new THREE.Vector3();
    xrCam.getWorldDirection(dir);
    const h = Math.atan2(dir.x, dir.z);
    const sp = 1.2 * dt;
    // forward = -y on the stick
    const dx = (Math.sin(h) * -my - Math.cos(h) * mx) * sp;
    const dz = (Math.cos(h) * -my + Math.sin(h) * mx) * sp;
    const [nx, nz] = xrWalk.move(head.x, head.z, dx, dz);
    rig.position.x += nx - head.x;
    rig.position.z += nz - head.z;
  }
  if (Math.abs(turn) > 0.7 && !snapLatch) {
    snapLatch = true;
    const a = turn > 0 ? -Math.PI / 6 : Math.PI / 6;
    // rotate the rig around the head
    rig.position.sub(head).applyAxisAngle(new THREE.Vector3(0, 1, 0), a).add(head);
    rig.rotation.y += a;
  } else if (Math.abs(turn) < 0.3) snapLatch = false;
  renderer.render(scene, camera);
}

init().catch((e) => {
  console.error(e);
  fail('Sorry, the room failed to load. ' + (e && e.message ? e.message : ''));
});

// for debugging and screenshots
window.__room = { renderer, scene, camera, rig, spark, get controls() { return controls; }, render: () => { needsRender = true; } };
