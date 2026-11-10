// 2D walkability grid on the floor plane (three.js coordinates, Y up).
// Cell value 1 = the player's centre may stand here (already shrunk by the player radius).

export class WalkMap {
  constructor(json) {
    this.x0 = json.origin[0];
    this.z0 = json.origin[1];
    this.cell = json.cell;
    this.w = json.width;
    this.h = json.height;
    const bin = atob(json.data);
    // data is run-length encoded: alternating counts of 0s and 1s, as uint16 little endian pairs
    const runs = new Uint16Array(bin.length / 2);
    for (let i = 0; i < runs.length; i++) runs[i] = bin.charCodeAt(2 * i) | (bin.charCodeAt(2 * i + 1) << 8);
    this.grid = new Uint8Array(this.w * this.h);
    let p = 0, v = 0;
    for (let i = 0; i < runs.length; i++) {
      this.grid.fill(v, p, p + runs[i]);
      p += runs[i];
      v ^= 1;
    }
  }

  walkable(x, z) {
    const i = Math.floor((x - this.x0) / this.cell);
    const j = Math.floor((z - this.z0) / this.cell);
    if (i < 0 || j < 0 || i >= this.w || j >= this.h) return false;
    return this.grid[j * this.w + i] === 1;
  }

  // Move from (x,z) by (dx,dz) with wall sliding. Returns [x, z, blocked].
  move(x, z, dx, dz) {
    const len = Math.hypot(dx, dz);
    const steps = Math.max(1, Math.ceil(len / (this.cell * 0.5)));
    const sx = dx / steps, sz = dz / steps;
    let blocked = false;
    for (let s = 0; s < steps; s++) {
      if (this.walkable(x + sx, z + sz)) { x += sx; z += sz; continue; }
      blocked = true;
      if (this.walkable(x + sx, z)) { x += sx; continue; }
      if (this.walkable(x, z + sz)) { z += sz; continue; }
      break;
    }
    return [x, z, blocked];
  }

  // Nearest walkable cell centre to (x,z), searching outward in rings.
  nearest(x, z, maxR = 2.0) {
    if (this.walkable(x, z)) return [x, z];
    const ci = Math.floor((x - this.x0) / this.cell);
    const cj = Math.floor((z - this.z0) / this.cell);
    const maxRing = Math.ceil(maxR / this.cell);
    for (let r = 1; r <= maxRing; r++) {
      let best = null, bestD = Infinity;
      for (let dj = -r; dj <= r; dj++) {
        for (let di = -r; di <= r; di++) {
          if (Math.max(Math.abs(di), Math.abs(dj)) !== r) continue;
          const i = ci + di, j = cj + dj;
          if (i < 0 || j < 0 || i >= this.w || j >= this.h) continue;
          if (this.grid[j * this.w + i] !== 1) continue;
          const d = di * di + dj * dj;
          if (d < bestD) { bestD = d; best = [this.x0 + (i + 0.5) * this.cell, this.z0 + (j + 0.5) * this.cell]; }
        }
      }
      if (best) return best;
    }
    return null;
  }
}
