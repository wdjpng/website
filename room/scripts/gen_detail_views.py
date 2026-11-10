# Close-up training views around detailed objects, merged with a subset of the walk-area views.
import json, math, numpy as np
rng = np.random.default_rng(11)
boxes = json.load(open('/home/muenzel_lukas/room/work/obj_boxes.json'))
skip = ('Architecture', 'Exterior', 'Trim', 'Switch', 'Data outlet', 'Lamp outlet', 'Window outlet', 'Blind', 'Door', 'Entry door', 'Door beside bed')
obst = []
for k, (lo, hi) in boxes.items():
    if k.startswith(skip):
        continue
    lo = np.array(lo) - 0.04; hi = np.array(hi) + 0.04
    if (hi - lo).max() > 6:
        continue
    obst.append((k, lo, hi))
ROOM_LO = np.array([-1.80, -0.78, 0.30]); ROOM_HI = np.array([1.79, 2.71, 2.10])
ROOM_C = np.array([0.0, 0.97, 1.4])

def free(p):
    if np.any(p < ROOM_LO) or np.any(p > ROOM_HI):
        return False
    for k, lo, hi in obst:
        if np.all(p > lo) and np.all(p < hi):
            return False
    return True

def look(p, t, fov_x):
    d = t - p; d /= np.linalg.norm(d)
    up = np.array([0, 0, 1.0])
    if abs(d @ up) > 0.97:
        up = np.array([1.0, 0, 0])
    r = np.cross(d, up); r /= np.linalg.norm(r); u = np.cross(r, d)
    M = np.eye(4); M[:3, 0] = r; M[:3, 1] = u; M[:3, 2] = -d; M[:3, 3] = p
    return {'c2w': M.tolist(), 'fov_x': fov_x}

# name, centre, radius, count, dmin, dmax, min_x (keep cameras out of the window recess)
POIS = [
    ('llama', (-1.73, -0.27, 0.88), 0.13, 70, 0.25, 0.70, -1.50),
    ('lily', (-1.69, 0.21, 0.91), 0.13, 40, 0.25, 0.70, -1.50),
    ('books', (-1.73, 0.78, 0.90), 0.30, 50, 0.35, 0.90, -1.50),
    ('sill_front', (-1.68, -0.15, 0.78), 0.25, 30, 0.30, 0.80, -1.50),
    ('sill', (-1.75, 0.30, 0.85), 0.80, 15, 0.70, 1.30, -1.50),
    ('bedside_top', (1.63, 0.75, 0.70), 0.22, 80, 0.30, 0.80, -9),
    ('salt_lamp', (1.77, 0.67, 0.75), 0.12, 25, 0.30, 0.70, -9),
    ('nightstand', (1.64, 0.76, 0.33), 0.30, 15, 0.50, 1.00, -9),
    ('chair', (-1.18, 2.13, 0.45), 0.55, 50, 0.50, 1.20, -9),
    ('reading_lamp', (-1.36, 2.50, 1.30), 0.40, 20, 0.40, 1.00, -9),
    ('paper_lamp', (1.52, -0.54, 0.80), 0.60, 25, 0.40, 1.00, -9),
    ('purifier', (0.92, -0.56, 0.30), 0.25, 15, 0.40, 0.90, -9),
    ('bed', (0.60, 1.80, 0.50), 1.00, 20, 0.50, 1.20, -9),
]
detail = []
for name, c, r, n, dmin, dmax, minx in POIS:
    c = np.array(c); got = 0; tries = 0
    to_room = ROOM_C - c; to_room[2] = 0; to_room /= np.linalg.norm(to_room)
    while got < n and tries < 200000:
        tries += 1
        v = rng.normal(size=3); v /= np.linalg.norm(v)
        if v @ to_room < 0.15 or v[2] < -0.35:
            continue
        d = rng.uniform(dmin, dmax)
        p = c + v * d
        if p[0] < minx or not free(p):
            continue
        t = c + rng.uniform(-0.4, 0.4, 3) * r
        fov = float(np.clip(2 * math.atan(1.7 * r / d), math.radians(32), math.radians(72)))
        detail.append(dict(look(p, t, fov), poi=name)); got += 1
    print(name, got, tries)
main = json.load(open('/home/muenzel_lukas/room/scripts/views_main.json'))
main_views = main['views'][:540]
rng.shuffle(detail)
merged = []
di = 0
for i, v in enumerate(main_views):
    merged.append({'c2w': v['c2w'], 'fov_x': v['fov_x'], 'src': 'main'})
    # interleave detail views evenly
    while di < len(detail) and di < (i + 1) * len(detail) / len(main_views):
        merged.append({'c2w': detail[di]['c2w'], 'fov_x': detail[di]['fov_x'], 'src': detail[di]['poi']}); di += 1
for k, v in enumerate(merged):
    v['name'] = 'w%05d' % k; v['idx'] = k + 1
cfg = {k: main[k] for k in main if k != 'views'}
cfg['views'] = merged
json.dump(cfg, open('/home/muenzel_lukas/room/scripts/views_v2.json', 'w'))
print('total', len(merged), 'detail', len(detail))
