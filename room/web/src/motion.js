// Turning real walking into walking in the room.
//  - StepDetector: phones without WebXR (iPhone): counts steps from the accelerometer (DeviceMotion) and reports a
//    step length, so the view moves forward as you walk with the phone.
//  - Android Chrome with ARCore uses a WebXR 'immersive-ar' session instead (see main.js), which tracks the phone's
//    real position in metres.

export class StepDetector {
  constructor(onStep) {
    this.onStep = onStep; // (lengthMetres) => void
    this.g = null; // low-passed gravity (device axes)
    this.v = 0; // smoothed acceleration along gravity
    this.armed = false; // went below the low threshold since the last step
    this.lo = 0; this.hi = 0; // extremes within the current step cycle
    this.lastStep = 0;
    this.pending = []; // steps waiting for confirmation (times, lengths)
    this.walking = false;
    this.t0 = 0;
    this._h = (e) => this._motion(e);
    this.enabled = false;
  }

  start() {
    if (this.enabled) return;
    window.addEventListener('devicemotion', this._h);
    this.enabled = true;
  }

  stop() {
    window.removeEventListener('devicemotion', this._h);
    this.enabled = false;
    this.g = null; this.walking = false; this.pending = [];
  }

  _motion(e) {
    const a = e.accelerationIncludingGravity;
    if (!a || a.x == null) return;
    const t = performance.now() / 1000;
    const dt = this.t0 ? Math.min(0.1, Math.max(0.002, t - this.t0)) : 0.016;
    this.t0 = t;
    const ax = a.x, ay = a.y, az = a.z;
    if (!this.g) { this.g = [ax, ay, az]; return; }
    // gravity estimate (slow low-pass); sign conventions differ between iOS and Android, so everything is
    // measured relative to this estimate
    const kg = 1 - Math.exp(-dt / 0.5);
    const g = this.g;
    g[0] += (ax - g[0]) * kg; g[1] += (ay - g[1]) * kg; g[2] += (az - g[2]) * kg;
    const gn = Math.hypot(g[0], g[1], g[2]) || 1;
    const vRaw = ((ax - g[0]) * g[0] + (ay - g[1]) * g[1] + (az - g[2]) * g[2]) / gn;
    // smooth to the step band (~2.5 Hz)
    this.v += (vRaw - this.v) * (1 - Math.exp(-dt / 0.065));
    const v = this.v;
    this.lo = Math.min(this.lo, v); this.hi = Math.max(this.hi, v);
    const T = 0.75; // m/s^2, above hand jitter, below walking bounce
    if (v < -T) this.armed = true;
    if (this.armed && v > T && t - this.lastStep > 0.27) {
      this.armed = false;
      const amp = this.hi - this.lo;
      this.lo = 0; this.hi = 0;
      // Weinberg step length estimate, clamped to normal walking
      const len = Math.min(0.85, Math.max(0.45, 0.47 * Math.pow(Math.max(amp, 0.1), 0.25)));
      const gap = t - this.lastStep;
      this.lastStep = t;
      if (gap > 1.6) { this.walking = false; this.pending = []; }
      if (this.walking) { this.onStep(len); return; }
      // the first steps are only counted once a second one follows (ignores single bumps)
      this.pending.push(len);
      if (this.pending.length >= 2) {
        this.walking = true;
        for (const l of this.pending) this.onStep(l);
        this.pending = [];
      }
    }
  }
}

// Ask for motion + orientation access (iOS needs a tap). Both requests start inside the same tap.
export async function requestMotionPermission() {
  const reqs = [];
  if (typeof DeviceMotionEvent !== 'undefined' && typeof DeviceMotionEvent.requestPermission === 'function') reqs.push(DeviceMotionEvent.requestPermission());
  if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') reqs.push(DeviceOrientationEvent.requestPermission());
  if (!reqs.length) return true;
  try {
    const r = await Promise.all(reqs);
    return r.every((x) => x === 'granted');
  } catch (_) {
    return false;
  }
}

export async function arSupported() {
  try {
    return !!(navigator.xr && await navigator.xr.isSessionSupported('immersive-ar'));
  } catch (_) {
    return false;
  }
}
