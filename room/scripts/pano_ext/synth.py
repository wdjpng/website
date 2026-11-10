# Fill the navy void around the exterior photo cards in the extended panorama with a plausible continuation.
# Geometry (Blender coords): tower facade ~ plane x=-54, bay photo plane x=-140, ground plane z=-132.
# Textures are resampled from the render itself (so colours match), extended procedurally in plane space,
# projected back to the equirect grid (with horizontal supersampling at grazing angles), and the original
# card pixels are pasted back last with an inward feather.
import numpy as np, cv2, sys
from common import P0, PPD, LATMAX, W, H, pix_of_point, sample_plane_x


def remap1d(img, cx, cy, border):
    n = cx.size; k = 1024; m = (n + k - 1) // k
    X = np.zeros(m * k, np.float32); Y = np.zeros(m * k, np.float32); X[:n] = cx.ravel(); Y[:n] = cy.ravel()
    o = cv2.remap(img, X.reshape(m, k), Y.reshape(m, k), cv2.INTER_LINEAR, borderMode=border)
    return o.reshape(-1, 3)[:n]

rng = np.random.default_rng(7)
comp = cv2.imread('composite.png')  # BGR, full grid, original pixels inside rows 307..3378
NAVY = np.array([34, 27, 18], np.float32)  # BGR

# ---------------- tower texture ----------------
TX, TY0, TZ1, TPPM = -54.0, -9.5, 32.5, 24.0
T = sample_plane_x(comp, TX, TY0, 36.5, -58.5, TZ1, TPPM).astype(np.float32)
T_LEFT = int(round((-9.1 - TY0) * TPPM)) + 2   # first tower column (left edge, inside)
T_RIGHT = 1072                                 # last good column (right edge of the return face)
T_TOP, T_BOT = 18, 2162                        # good rows (card edge AA excluded)
PF, PH = 88.1, 71.0                            # floor period / slab line phase (texture rows)
C0 = 598                                       # mullion column: periodic block [C0, T_RIGHT)
PB = T_RIGHT - C0
SRC_FLOORS = [k for k in range(40) if PH + k * PF >= 420 and PH + (k + 1) * PF <= 2000]
ROOF_Z = 95.0; SETBACK_Y = -3.7
def tower_color(y, z, lvl):
    """y, z: plane coords (arrays). returns colour (N,3) using the mip level image lvl."""
    col = (y - TY0) * TPPM - 0.5
    row = (TZ1 - z) * TPPM - 0.5
    # column mapping and block id
    blk = np.where(col < C0, -2, -1).astype(np.int64)
    over = col >= T_RIGHT
    k = np.floor((col - T_RIGHT) / PB).astype(np.int64)
    scol = np.where(over, C0 + (col - T_RIGHT) - k * PB, col)
    blk = np.where(over, k, blk)
    # row mapping: inside original rows keep, else random interior floor
    fl = np.floor((row - PH) / PF).astype(np.int64)
    off = row - PH - fl * PF
    inside = (row >= T_TOP) & (row <= T_BOT) & ~over
    h = (fl * 73856093 + (blk + 7) * 19349663) & 0x7fffffff
    src = np.array(SRC_FLOORS)[h % len(SRC_FLOORS)]
    srow = np.where(inside, row, PH + src * PF + off)
    return remap1d(lvl, scol, srow, cv2.BORDER_REPLICATE)

# ---------------- bay texture ----------------
BX, BY0, BZ1, BPPM = -140.0, -118.0, 101.0, 10.0
B = sample_plane_x(comp, BX, BY0, -10.3, -132, BZ1, BPPM).astype(np.float32)
B_W = int((-24.5 - BY0) * BPPM)       # columns not hidden behind the tower
B_TOP, B_BOT, B_LEFT = 4, B.shape[0] - 4, 3
HOR = 937                              # horizon row (approx.)
skyrow = cv2.GaussianBlur(B[:, B_LEFT:B_W].mean(1, keepdims=True), (1, 0), sigmaX=0.1, sigmaY=25).reshape(-1, 3)
c_top = B[B_TOP:B_TOP + 60, B_LEFT:B_W].reshape(-1, 3).mean(0)
# strip sequence going left from the card's left edge: segment 0 = mirror of the edge, then random strips
SEGS = []
x = 0.0
for i in range(400):
    L = 260 if i == 0 else int(rng.integers(180, 340))
    if i == 0:
        SEGS.append((x, L, B_LEFT, True))
    else:
        s = int(rng.integers(45, B_W - L - 45)); SEGS.append((x, L, s, bool(rng.integers(0, 2))))
    x += L
SEG_X = np.array([s[0] for s in SEGS]); SEG_L = np.array([s[1] for s in SEGS]); SEG_S = np.array([s[2] for s in SEGS]); SEG_F = np.array([s[3] for s in SEGS])
FADE = 40.0
def bay_strip(d, row, lvl):
    """d = distance (texels) to the left of the card's left edge (>=0)."""
    i = np.clip(np.searchsorted(SEG_X, d, side='right') - 1, 0, len(SEGS) - 1)
    def src_col(i, d):
        loc = d - SEG_X[i]
        return np.where(SEG_F[i], SEG_S[i] + loc, SEG_S[i] + SEG_L[i] - 1 - loc)
    c1 = src_col(i, d)
    # crossfade with the next segment near the segment end
    loc = d - SEG_X[i]
    w = np.clip((loc - (SEG_L[i] - FADE)) / FADE, 0, 1)
    i2 = np.minimum(i + 1, len(SEGS) - 1)
    c2 = np.where(SEG_F[i2], SEG_S[i2] + (loc - SEG_L[i]), SEG_S[i2] + SEG_L[i2] - 1 - (loc - SEG_L[i]))
    c2 = np.clip(c2, 0, B.shape[1] - 1)
    r = row
    a = remap1d(lvl, c1, r, cv2.BORDER_REFLECT)
    b = remap1d(lvl, c2, r, cv2.BORDER_REFLECT)
    return a * (1 - w[:, None]) + b * w[:, None]
def bay_color(y, z, lvl):
    col = (y - BY0) * BPPM - 0.5
    row = (BZ1 - z) * BPPM - 0.5
    rowc = np.clip(row, 0, B.shape[0] - 1)
    sky = skyrow[np.clip(np.round(row), 0, B.shape[0] - 1).astype(int)]
    sky = np.where((row < B_TOP)[:, None], c_top[None, :], sky)
    # inside the card
    cin = np.clip(col, B_LEFT, B.shape[1] - 1)
    inner = remap1d(lvl, cin, rowc, cv2.BORDER_REPLICATE)
    d = np.maximum(B_LEFT - col, 0)
    strip = bay_strip(d, rowc, lvl)
    out = np.where((col >= B_LEFT)[:, None], inner, strip)
    # far to the left: the sky becomes the smooth row mean; city/sea keep the strips
    wsky = np.clip((HOR - 40 - row) / 120, 0, 1) * np.clip(d / 500, 0, 1)
    out = out * (1 - wsky[:, None]) + sky * wsky[:, None]
    # above the card: smooth sky (blend over 40 texels)
    wtop = np.clip((B_TOP + 40 - row) / 40, 0, 1)
    out = out * (1 - wtop[:, None]) + sky * wtop[:, None]
    return out

# ---------------- ground texture (city seen from above) ----------------
G = cv2.GaussianBlur(B[1650:B_BOT, 40:B_W - 10], (0, 0), 1.5) * 0.85
GPPM = 9.0
GT, GF = 150.0, 40.0   # ground tile pitch / crossfade (texels)
GSX = rng.uniform(0, 1, (512, 512)); GSY = rng.uniform(0, 1, (512, 512)); GFL = rng.integers(0, 2, (512, 512))
def ground_color(x, y, lvl):
    u = (y - 0.3) * GPPM; v = (-x - 0.5) * GPPM
    gh, gw = G.shape[:2]
    acc = 0; wsum = 0
    iu0 = np.floor(u / GT).astype(np.int64); iv0 = np.floor(v / GT).astype(np.int64)
    for du in (0, -1):
        for dv in (0, -1):
            iu = iu0 + du; iv = iv0 + dv
            lu = u - iu * GT; lv = v - iv * GT          # local coords in tile (0 .. GT+GF)
            ok = (lu <= GT + GF) & (lv <= GT + GF)
            wu = np.clip(np.minimum(lu, GT + GF - lu) / GF, 0, 1); wv = np.clip(np.minimum(lv, GT + GF - lv) / GF, 0, 1)
            w = np.where(ok, np.maximum(wu, 1e-4) * np.maximum(wv, 1e-4), 0)
            a = iu % 512; b = iv % 512
            sx = GSX[a, b] * (gw - GT - GF - 2); sy = GSY[a, b] * (gh - GT - GF - 2)
            fl = GFL[a, b] == 1
            cx = np.where(fl, sx + GT + GF - lu, sx + lu); cy = sy + GT + GF - lv
            acc = acc + remap1d(lvl, cx, cy, cv2.BORDER_REFLECT) * w[:, None]; wsum = wsum + w
    return acc / np.maximum(wsum, 1e-6)[:, None]

def mips(img, n):
    out = [img]
    for i in range(1, n):
        k = 2 ** i
        out.append(cv2.blur(img, (k + 1, max(1, k // 4) + 1)))
    return out
TM, BM, GM = mips(T, 7), mips(B, 7), mips(G, 7)

def shade(cf, rf):
    """colour for equirect sample positions (flattened float arrays of column/row)."""
    lon = np.radians(100 - (cf + 0.5) / PPD); lat = np.radians(LATMAX - (rf + 0.5) / PPD)
    dx, dy, dz = -np.cos(lat) * np.cos(lon), -np.cos(lat) * np.sin(lon), np.sin(lat)
    n = cf.size
    best_t = np.full(n, np.inf); col = np.tile(c_top, (n, 1)).astype(np.float32)
    which = np.zeros(n, np.int8)
    # texel footprint per pixel (horizontal): d(plane coord)/d(lon) * (1 pixel in rad)
    dpix = np.radians(1 / PPD)
    with np.errstate(divide='ignore', invalid='ignore'):
        # bay plane
        t = (BX - P0[0]) / dx; ok = (dx < -1e-6)
        yb = P0[1] + t * dy; zb = P0[2] + t * dz; ok &= zb >= -132
        hit_b = ok & (t < best_t); best_t = np.where(hit_b, t, best_t); which[hit_b] = 1
        # tower plane
        t = (TX - P0[0]) / dx; ok = (dx < -1e-6)
        yt = P0[1] + t * dy; zt = P0[2] + t * dz
        ok &= (yt >= -9.1) & (zt >= -132) & (zt <= np.where(yt < SETBACK_Y, 31.9, ROOF_Z))
        hit_t = ok & (t < best_t); best_t = np.where(hit_t, t, best_t); which[hit_t] = 2
        # ground
        t = (-132 - P0[2]) / dz; ok = dz < -1e-6
        xg = P0[0] + t * dx; yg = P0[1] + t * dy
        hit_g = ok & (t < best_t); best_t = np.where(hit_g, t, best_t); which[hit_g] = 3
    for code, fn, M, ppm, args in ((1, bay_color, BM, BPPM, (yb, zb)), (2, tower_color, TM, TPPM, (yt, zt)), (3, ground_color, GM, GPPM, None)):
        m = which == code
        if not m.any(): continue
        tt = best_t[m]
        # footprint in texels: distance * dpix / cos(incidence) along the dominant axis
        if code == 3:
            fp = tt * dpix * ppm / np.maximum(np.abs(dz[m]), 0.02)
            a = (xg[m], yg[m])
        else:
            fp = tt * dpix * ppm / np.maximum(np.abs(dx[m]) / np.hypot(dx[m], dy[m]), 0.02)
            a = (args[0][m], args[1][m])
        lvlf = np.clip(np.log2(np.maximum(fp, 1)), 0, len(M) - 1)
        lo = np.floor(lvlf).astype(int); fr = (lvlf - lo)[:, None]
        res = np.zeros((m.sum(), 3), np.float32)
        for L in np.unique(lo):
            s = lo == L
            ca = fn(a[0][s], a[1][s], M[L])
            cb = fn(a[0][s], a[1][s], M[min(L + 1, len(M) - 1)]) if L + 1 < len(M) else ca
            res[s] = ca * (1 - fr[s]) + cb * fr[s]
        col[m] = res
    return col, which

cc, rr = np.meshgrid(np.arange(W, dtype=np.float64), np.arange(H, dtype=np.float64))
out = np.zeros((H * W, 3), np.float32)
CH = 400
for r0 in range(0, H, CH):
    sl = slice(r0 * W, min(H, r0 + CH) * W)
    acc = 0
    for ox, oy in ((-0.25, -0.25), (0.25, -0.25), (-0.25, 0.25), (0.25, 0.25)):
        c, _ = shade(cc.ravel()[sl] + ox, rr.ravel()[sl] + oy); acc = acc + c
    out[sl] = acc / 4
    print('rows', r0, flush=True)
syn = out.reshape(H, W, 3)
syn += rng.normal(0, 0.6, syn.shape).astype(np.float32)  # dither against banding
cv2.imwrite('synth.png', np.clip(np.round(syn), 0, 255).astype(np.uint8))

# ---------------- paste the original card pixels back ----------------
orig = comp.astype(np.float32)
d = np.abs(orig - NAVY).max(2)
m = (d > 3).astype(np.uint8)
m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
n, lab, st, _ = cv2.connectedComponentsWithStats(m)
keep = [i for i in range(1, n) if st[i, 4] > 100000]
m = np.isin(lab, keep).astype(np.uint8)
ff = m.copy(); mm = np.zeros((H + 2, W + 2), np.uint8); cv2.floodFill(ff, mm, (0, 0), 1); m = m | (1 - ff)
dist = cv2.distanceTransform(m, cv2.DIST_L2, 5)
FE0, FE1 = 3.0, 28.0
w = np.clip((dist - FE0) / (FE1 - FE0), 0, 1)
w = w * w * (3 - 2 * w)
final = orig * w[..., None] + syn * (1 - w[..., None])
final = np.clip(np.round(final), 0, 255).astype(np.uint8)
cv2.imwrite('final.png', final)
np.save('paste_weight.npy', w.astype(np.float16))
print('identical px fraction inside mask', float((w[m > 0] >= 1).mean()))
