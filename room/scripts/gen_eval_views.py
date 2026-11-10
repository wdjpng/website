import json, math, numpy as np, glob, os, sys
src = '/home/muenzel_lukas/room/in/cr-3/outputs'
def euler_xyz(rx, ry, rz):
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]]); Ry = np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]]); Rz = np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]])
    return Rz @ Ry @ Rx
base = json.load(open('/home/muenzel_lukas/room/work/views_test.json'))
for orient, (W, H) in (('land', (1600, 1200)), ('port', (1200, 1600))):
    views = []
    for f in sorted(glob.glob(src + '/0*.render.json')):
        d = json.load(open(f)); c = d['camera']
        w, h = d['render_settings']['resolution']
        if (w > h) != (orient == 'land'):
            continue
        M = np.eye(4); M[:3, :3] = euler_xyz(*c['rotation_radians']); M[:3, 3] = c['location_m']
        f_mm = c['focal_length_mm']
        if w >= h:
            fov_x = 2 * math.atan(18 / f_mm)
        else:
            fov_y = 2 * math.atan(18 / f_mm); fov_x = 2 * math.atan(math.tan(fov_y / 2) * W / H)
        name = os.path.basename(f).split('.')[0]
        views.append({'name': 'e_' + name, 'idx': 9000 + len(views) + (0 if orient == 'land' else 10), 'c2w': M.tolist(), 'fov_x': fov_x})
    cfg = dict(base); cfg['width'], cfg['height'] = W, H; cfg['views'] = views; cfg['noise_threshold'] = 0.004
    json.dump(cfg, open(f'/home/muenzel_lukas/room/scripts/views_eval_{orient}.json', 'w'))
    print(orient, [v['name'] for v in views])
