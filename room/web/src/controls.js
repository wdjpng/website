import * as THREE from 'three';
import { StepDetector, requestMotionPermission } from './motion.js';

// First-person walking controls for mouse/trackpad/keyboard and touch.
//  - drag (mouse, or one finger anywhere except the thumbstick): look around ("grab the room")
//  - WASD / arrow keys, on-screen thumbstick (touch), two-finger trackpad scroll: walk
//  - click / tap on a spot: glide there
//  - pinch / ctrl+wheel: zoom (field of view)
//  - optional device motion on phones: turning the phone looks around, walking with it (steps) walks forward

const _euler = new THREE.Euler(0, 0, 0, 'YXZ');
const _q = new THREE.Quaternion();
const _q1 = new THREE.Quaternion(-Math.sqrt(0.5), 0, 0, Math.sqrt(0.5)); // -90° around X
const _zee = new THREE.Vector3(0, 0, 1);
const _fwd = new THREE.Vector3();

export class WalkControls {
  constructor(camera, dom, walkmap, opts = {}) {
    this.camera = camera;
    this.dom = dom;
    this.map = walkmap;
    this.eye = opts.eyeHeight ?? 1.6;
    this.eye0 = this.eye;
    this.eyeTarget = this.eye;
    this.minEye = opts.minEye ?? 0.95;
    this.maxEye = opts.maxEye ?? 1.95;
    this.speed = opts.speed ?? 1.25; // m/s
    this.pos = new THREE.Vector2(0, 0); // x, z
    this.yaw = 0;
    this.pitch = 0;
    this.vel = new THREE.Vector2();
    this.keys = new Set();
    this.joy = new THREE.Vector2(); // x: strafe, y: forward (-1..1)
    this.wheelMove = new THREE.Vector2(); // accumulated trackpad movement (metres)
    this.target = null; // glide target [x, z]
    this.targetBlockedTime = 0;
    this.fov = camera.fov;
    this.fovTarget = camera.fov;
    this.minFov = 30;
    this.maxFov = 95;
    this.gyro = { enabled: false, alpha: 0, beta: 0, gamma: 0, orient: 0, yawOffset: 0, have: false };
    this.stepPending = 0; // metres still to walk from detected steps
    this.steps = new StepDetector((len) => { this.stepPending = Math.min(this.stepPending + len, 2.5); if (this.onStep) this.onStep(len); });
    this.onTap = null; // (ndcX, ndcY) => [x, z] | null
    this.onInteract = null;
    this.changed = true;
    this.pointers = new Map();
    this._bind();
  }

  setPose(x, z, yaw, pitch = 0) {
    const p = this.map.nearest(x, z) ?? [x, z];
    this.pos.set(p[0], p[1]);
    this.yaw = yaw;
    this.pitch = pitch;
    this.vel.set(0, 0);
    this.target = null;
    this.eyeTarget = this.eye0;
    if (this.gyro.enabled) this._resetGyroYaw();
    this.changed = true;
  }

  _bind() {
    const el = this.dom;
    el.addEventListener('pointerdown', (e) => this._down(e));
    window.addEventListener('pointermove', (e) => this._move(e));
    window.addEventListener('pointerup', (e) => this._up(e));
    window.addEventListener('pointercancel', (e) => this._up(e, true));
    el.addEventListener('wheel', (e) => this._wheel(e), { passive: false });
    window.addEventListener('keydown', (e) => this._key(e, true));
    window.addEventListener('keyup', (e) => this._key(e, false));
    window.addEventListener('blur', () => { this.keys.clear(); this.joy.set(0, 0); this._stickUp(); });
    el.addEventListener('contextmenu', (e) => e.preventDefault());
    el.addEventListener('pointerleave', () => { if (this.onHover) this.onHover(null); });
    // Safari pinch gestures on trackpads
    el.addEventListener('gesturestart', (e) => e.preventDefault());
    el.addEventListener('gesturechange', (e) => e.preventDefault());
  }

  _interact() { if (this.onInteract) this.onInteract(); }

  _down(e) {
    this.dom.focus({ preventScroll: true });
    this._interact();
    const isTouch = e.pointerType === 'touch';
    const p = { id: e.pointerId, x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, t: performance.now(), kind: 'look', moved: 0, touch: isTouch };
    if (isTouch) {
      const others = [...this.pointers.values()];
      const hasJoy = others.some((q) => q.kind === 'joy');
      const looks = others.filter((q) => q.kind === 'look' || q.kind === 'pinch');
      if (!hasJoy && this._onStick(e.clientX, e.clientY)) {
        p.kind = 'joy';
        this._stickDown(e.clientX, e.clientY);
      } else if (looks.length === 1) {
        // second finger next to a looking finger: pinch to zoom
        const o = looks[0];
        o.kind = 'pinch';
        p.kind = 'pinch';
        this.pinch = { a: o, b: p, d0: Math.hypot(o.x - p.x, o.y - p.y), fov0: this.fovTarget };
      }
    } else {
      this.dom.classList.add('dragging');
      if (this.onHover) this.onHover(null);
    }
    this.pointers.set(e.pointerId, p);
    try { this.dom.setPointerCapture(e.pointerId); } catch (_) { /* ignore */ }
  }

  _move(e) {
    const p = this.pointers.get(e.pointerId);
    if (!p) {
      // mouse hovering (no button): preview where a click would take you
      if (e.pointerType === 'mouse' && this.onHover && e.target === this.dom) {
        this.onHover((e.clientX / window.innerWidth) * 2 - 1, -(e.clientY / window.innerHeight) * 2 + 1);
      }
      return;
    }
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    p.moved = Math.max(p.moved, Math.hypot(p.x - p.sx, p.y - p.sy));
    if (p.kind === 'look') {
      if (p.moved < 4 && p.touch) return;
      // "grab the room": the point under the finger follows it
      const fovRad = THREE.MathUtils.degToRad(this.camera.fov);
      const k = fovRad / window.innerHeight;
      this.yaw += dx * k;
      if (this.gyro.enabled) this.gyro.yawOffset += dx * k;
      else this.pitch = THREE.MathUtils.clamp(this.pitch + dy * k, -1.45, 1.45);
      this.target = null;
      this.changed = true;
    } else if (p.kind === 'joy') {
      const R = this.stickRadius;
      let jx = (p.x - this.stickCx) / R, jy = (p.y - this.stickCy) / R;
      const l = Math.hypot(jx, jy);
      if (l > 1) { jx /= l; jy /= l; }
      // small dead zone, then a gentle curve so slow walking is easy
      const m = Math.min(1, l);
      const g = m < 0.12 ? 0 : Math.pow((m - 0.12) / 0.88, 1.4) / Math.max(m, 1e-6);
      this.joy.set(jx * g, -jy * g);
      this.knob.style.transform = `translate(${jx * R}px, ${jy * R}px)`;
      this.target = null;
    } else if (p.kind === 'pinch' && this.pinch) {
      const { a, b, d0, fov0 } = this.pinch;
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      if (d0 > 10) this.fovTarget = THREE.MathUtils.clamp(fov0 * d0 / Math.max(d, 1), this.minFov, this.maxFov);
    }
  }

  _up(e, cancelled = false) {
    const p = this.pointers.get(e.pointerId);
    if (!p) return;
    this.pointers.delete(e.pointerId);
    if (p.kind === 'joy') {
      this.joy.set(0, 0);
      this._stickUp();
    } else if (p.kind === 'pinch') {
      this.pinch = null;
      for (const q of this.pointers.values()) if (q.kind === 'pinch') { q.kind = 'look'; q.moved = 99; }
    } else if (!cancelled && p.kind === 'look' && p.moved < 6 && performance.now() - p.t < 450 && this.onTap) {
      const ndcX = (e.clientX / window.innerWidth) * 2 - 1;
      const ndcY = -(e.clientY / window.innerHeight) * 2 + 1;
      const t = this.onTap(ndcX, ndcY);
      if (t) { this.target = t; this.targetBlockedTime = 0; }
    }
    if (![...this.pointers.values()].some((q) => !q.touch)) this.dom.classList.remove('dragging');
  }

  _wheel(e) {
    e.preventDefault();
    this._interact();
    let dx = e.deltaX, dy = e.deltaY;
    if (e.deltaMode === 1) { dx *= 16; dy *= 16; }
    if (e.ctrlKey) {
      // trackpad pinch (or ctrl + wheel): zoom
      this.fovTarget = THREE.MathUtils.clamp(this.fovTarget * Math.exp(dy * 0.01), this.minFov, this.maxFov);
      return;
    }
    // two-finger scroll walks: push away = forward, sideways = strafe
    const k = 0.0035;
    this.wheelMove.x += dx * k;
    this.wheelMove.y += dy * k;
    this.target = null;
  }

  _key(e, down) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.code;
    const handled = ['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyQ', 'KeyE', 'KeyR', 'KeyF', 'KeyC', 'PageUp', 'PageDown', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ShiftLeft', 'ShiftRight'].includes(k);
    if (!handled) return;
    if (down && k === 'KeyC' && !e.repeat) this.toggleCrouch();
    if (down) { this.keys.add(k); this.target = null; this._interact(); if (this.onHover) this.onHover(null); } else this.keys.delete(k);
    if (k.startsWith('Arrow')) e.preventDefault();
  }

  // ---- on-screen thumbstick (always visible on touch screens) ----
  enableStick() {
    this.joyEl = document.getElementById('joystick');
    this.knob = document.getElementById('joystick-knob');
    this.joyEl.hidden = false;
    this._layoutStick();
    window.addEventListener('resize', () => this._layoutStick());
  }

  _layoutStick() {
    if (!this.joyEl) return;
    const r = this.joyEl.getBoundingClientRect();
    this.stickCx = r.left + r.width / 2;
    this.stickCy = r.top + r.height / 2;
    this.stickRadius = r.width / 2 - 10;
  }

  _onStick(x, y) {
    if (!this.joyEl || this.joyEl.hidden) return false;
    this._layoutStick();
    return Math.hypot(x - this.stickCx, y - this.stickCy) < this.stickRadius + 40;
  }

  _stickDown() { this.joyEl.classList.add('active'); this.knob.style.transition = 'none'; }

  _stickUp() {
    if (!this.joyEl) return;
    this.joyEl.classList.remove('active');
    this.knob.style.transition = 'transform 0.15s ease';
    this.knob.style.transform = 'translate(0px, 0px)';
  }

  toggleCrouch() {
    this.eyeTarget = this.eyeTarget < this.eye0 - 0.2 ? this.eye0 : this.minEye + 0.15;
    this.changed = true;
    return this.eyeTarget < this.eye0 - 0.2;
  }

  // ---- device orientation ----
  async enableGyro(withSteps = true) {
    if (typeof DeviceOrientationEvent === 'undefined') return false;
    if (!(await requestMotionPermission())) return false;
    if (!this._gyroBound) {
      window.addEventListener('deviceorientation', (e) => {
        if (e.alpha == null) return;
        const g = this.gyro;
        g.alpha = THREE.MathUtils.degToRad(e.alpha);
        g.beta = THREE.MathUtils.degToRad(e.beta);
        g.gamma = THREE.MathUtils.degToRad(e.gamma);
        if (!g.have) { g.have = true; if (g.enabled) this._resetGyroYaw(); }
        if (g.enabled) this.changed = true;
      });
      const so = () => { this.gyro.orient = THREE.MathUtils.degToRad((screen.orientation && screen.orientation.angle) || window.orientation || 0); };
      window.addEventListener('orientationchange', so);
      if (screen.orientation) screen.orientation.addEventListener('change', so);
      so();
      this._gyroBound = true;
    }
    this.gyro.enabled = true;
    if (this.gyro.have) this._resetGyroYaw();
    if (withSteps) this.steps.start();
    return true;
  }

  disableGyro() {
    this.steps.stop();
    this.stepPending = 0;
    if (!this.gyro.enabled) return;
    // keep the current view direction
    this._applyGyroQuat(_q);
    _euler.setFromQuaternion(_q, 'YXZ');
    this.yaw = _euler.y;
    this.pitch = THREE.MathUtils.clamp(_euler.x, -1.45, 1.45);
    this.gyro.enabled = false;
    this.changed = true;
  }

  _deviceQuat(out) {
    const g = this.gyro;
    _euler.set(g.beta, g.alpha, -g.gamma, 'YXZ');
    out.setFromEuler(_euler);
    out.multiply(_q1);
    out.multiply(new THREE.Quaternion().setFromAxisAngle(_zee, -g.orient));
    return out;
  }

  _resetGyroYaw() {
    const dq = this._deviceQuat(new THREE.Quaternion());
    _euler.setFromQuaternion(dq, 'YXZ');
    this.gyro.yawOffset = this.yaw - _euler.y;
  }

  _applyGyroQuat(out) {
    this._deviceQuat(out);
    const yq = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), this.gyro.yawOffset);
    out.premultiply(yq);
    return out;
  }

  // ---- per frame ----
  update(dt) {
    dt = Math.min(dt, 0.05);
    const keys = this.keys;
    const run = keys.has('ShiftLeft') || keys.has('ShiftRight') ? 1.8 : 1;
    let f = 0, s = 0, turn = 0;
    if (keys.has('KeyW') || keys.has('ArrowUp')) f += 1;
    if (keys.has('KeyS') || keys.has('ArrowDown')) f -= 1;
    if (keys.has('KeyD')) s += 1;
    if (keys.has('KeyA')) s -= 1;
    if (keys.has('ArrowLeft') || keys.has('KeyQ')) turn += 1;
    if (keys.has('ArrowRight') || keys.has('KeyE')) turn -= 1;
    f += this.joy.y;
    s += this.joy.x;
    const l = Math.hypot(f, s);
    if (l > 1) { f /= l; s /= l; }

    let lift = 0;
    if (keys.has('KeyR') || keys.has('PageUp')) lift += 1;
    if (keys.has('KeyF') || keys.has('PageDown')) lift -= 1;
    if (lift) this.eyeTarget = THREE.MathUtils.clamp(this.eyeTarget + lift * 0.8 * dt, this.minEye, this.maxEye);
    if (Math.abs(this.eyeTarget - this.eye) > 1e-4) {
      this.eye += (this.eyeTarget - this.eye) * (1 - Math.exp(-dt * 10));
      this.changed = true;
    }

    if (turn) {
      this.yaw += turn * 1.6 * dt;
      if (this.gyro.enabled) this.gyro.yawOffset += turn * 1.6 * dt;
      this.changed = true;
    }

    // heading on the floor plane
    let heading = this.yaw;
    if (this.gyro.enabled && this.gyro.have) {
      this._applyGyroQuat(_q);
      _fwd.set(0, 0, -1).applyQuaternion(_q);
      heading = Math.atan2(-_fwd.x, -_fwd.z);
    }
    const sin = Math.sin(heading), cos = Math.cos(heading);
    // forward = (-sin, -cos), right = (cos, -sin)
    let wx = (-sin * f + cos * s) * this.speed * run;
    let wz = (-cos * f - sin * s) * this.speed * run;

    // glide to a tapped target
    if (this.target && l === 0) {
      const tx = this.target[0] - this.pos.x, tz = this.target[1] - this.pos.y;
      const d = Math.hypot(tx, tz);
      if (d < 0.03) this.target = null;
      else {
        const sp = Math.min(this.speed * 1.4, d * 3.0 + 0.15);
        wx = (tx / d) * sp;
        wz = (tz / d) * sp;
      }
    }

    // smooth acceleration
    const a = 1 - Math.exp(-dt * 10);
    this.vel.x += (wx - this.vel.x) * a;
    this.vel.y += (wz - this.vel.y) * a;

    let mx = this.vel.x * dt, mz = this.vel.y * dt;

    // real steps (phone motion mode): walk the detected distance smoothly along the view direction
    if (this.stepPending > 1e-4) {
      const sp = THREE.MathUtils.clamp(this.stepPending * 3.2, 0.35, 1.8);
      const d = Math.min(this.stepPending, sp * dt);
      this.stepPending -= d;
      mx += -sin * d;
      mz += -cos * d;
      this.target = null;
    }

    // trackpad scroll movement (already in metres), applied smoothly
    if (this.wheelMove.lengthSq() > 1e-8) {
      const take = 1 - Math.exp(-dt * 14);
      const wf = this.wheelMove.y * take, ws = this.wheelMove.x * take;
      this.wheelMove.multiplyScalar(1 - take);
      mx += -sin * wf + cos * ws;
      mz += -cos * wf - sin * ws;
    }

    if (Math.abs(mx) + Math.abs(mz) > 1e-7) {
      const [nx, nz, blocked] = this.map.move(this.pos.x, this.pos.y, mx, mz);
      if (this.target) {
        if (blocked && Math.hypot(nx - this.pos.x, nz - this.pos.y) < Math.hypot(mx, mz) * 0.3) {
          this.targetBlockedTime += dt;
          if (this.targetBlockedTime > 0.25) this.target = null;
        } else this.targetBlockedTime = 0;
      }
      if (nx !== this.pos.x || nz !== this.pos.y) this.changed = true;
      this.pos.set(nx, nz);
    }

    // zoom easing
    if (Math.abs(this.fovTarget - this.camera.fov) > 0.01) {
      this.camera.fov += (this.fovTarget - this.camera.fov) * (1 - Math.exp(-dt * 12));
      this.camera.updateProjectionMatrix();
      this.changed = true;
    }

    // apply to camera
    this.camera.position.set(this.pos.x, this.eye, this.pos.y);
    if (this.gyro.enabled && this.gyro.have) {
      this._applyGyroQuat(this.camera.quaternion);
    } else {
      _euler.set(this.pitch, this.yaw, 0, 'YXZ');
      this.camera.quaternion.setFromEuler(_euler);
    }
    const c = this.changed;
    this.changed = false;
    return c;
  }
}
