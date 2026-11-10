import numpy as np, json, math, sys
rng = np.random.default_rng(int(sys.argv[2]) if len(sys.argv) > 2 else 0)
out = sys.argv[1]
N_POS = int(sys.argv[3]) if len(sys.argv) > 3 else 220
W, H = (int(sys.argv[4]), int(sys.argv[5])) if len(sys.argv) > 5 else (1440, 1080)
dist = np.load('/home/muenzel_lukas/room/work/dist_blender.npy')
CELL, X0, Y0 = 0.02, -1.86, -0.84
ok = np.argwhere(dist >= 0.12)  # (row=y, col=x)
cand = np.stack([X0 + (ok[:, 1] + rng.random(len(ok))) * CELL, Y0 + (ok[:, 0] + rng.random(len(ok))) * CELL], 1)
# farthest point sampling for even coverage
sel = [rng.integers(len(cand))]
d2 = np.sum((cand - cand[sel[0]]) ** 2, 1)
for _ in range(N_POS - 1):
    i = int(np.argmax(d2)); sel.append(i)
    d2 = np.minimum(d2, np.sum((cand - cand[i]) ** 2, 1))
pos = cand[sel]
print('min spacing ~', np.sqrt(d2.max()))
fov_x = math.radians(80)
def c2w(p, yaw, pitch, roll=0.0):
    d = np.array([math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)])
    up = np.array([0, 0, 1.0])
    r = np.cross(d, up); r /= np.linalg.norm(r)
    u = np.cross(r, d)
    if roll:
        c, s = math.cos(roll), math.sin(roll)
        r, u = c * r + s * u, -s * r + c * u
    M = np.eye(4); M[:3, 0] = r; M[:3, 1] = u; M[:3, 2] = -d; M[:3, 3] = p
    return M
pitches = [-12, -40, 2, -24, 32, -62]
views = []
for k, (x, y) in enumerate(pos):
    u = rng.random()
    h = rng.uniform(1.40, 1.85) if u < 0.65 else (rng.uniform(0.90, 1.40) if u < 0.9 else rng.uniform(1.85, 2.0))
    base = rng.uniform(0, 2 * math.pi)
    for j in range(6):
        yaw = base + j * math.pi / 3 + rng.uniform(-0.15, 0.15)
        pitch = math.radians(pitches[(j + k) % 6] + rng.uniform(-8, 8))
        views.append({'name': 'v%05d' % len(views), 'idx': len(views) + 1, 'c2w': c2w(np.array([x, y, h]), yaw, pitch).tolist(), 'fov_x': fov_x})
cfg = {
    'width': W, 'height': H, 'noise_threshold': 0.006,
    'color': {'view_transform': 'AgX', 'look': 'AgX - Medium High Contrast', 'exposure': 4.5, 'wb_temp': 8500.0, 'wb_tint': 10.0},
    'glass_objects': ['Window / double glazed pane'],
    'views': views,
}
json.dump(cfg, open(out, 'w'))
print('views', len(views))
