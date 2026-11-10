# Pick the training views in which the llama or the magnet is visible (by projecting their boxes and checking depth).
import json, math, os, sys, numpy as np
import OpenEXR
data, out = sys.argv[1], sys.argv[2]
cfg = json.load(open(f'{data}/views.json'))
W, H = cfg['width'], cfg['height']
boxes = [np.array([[-1.865, -0.385, 0.735], [-1.60, -0.16, 1.03]]),     # llama incl. pompom (old and new)
         np.array([[-1.72, -0.45, 0.735], [-1.66, -0.35, 0.89]])]        # magnet (old and new frame)
def rd(p):
    ch = OpenEXR.File(p).channels(); a = np.asarray(list(ch.values())[0].pixels, np.float32); return a[..., 0] if a.ndim == 3 else a
sel = []
for v in cfg['views']:
    dp = f"{data}/depth_{v['idx']:04d}.exr"
    if not os.path.exists(dp):
        continue
    M = np.array(v['c2w']); R = M[:3, :3]; C = M[:3, 3]
    f = (W / 2) / math.tan(v['fov_x'] / 2)
    vis = False
    for lo, hi in boxes:
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        pc = (corners - C) @ R              # camera coords (x right, y up, -z forward)
        zf = -pc[:, 2]
        if (zf <= 0.02).all():
            continue
        zf = np.maximum(zf, 0.02)
        u = W / 2 + f * pc[:, 0] / zf; w = H / 2 - f * pc[:, 1] / zf
        u0, u1 = int(max(0, u.min())), int(min(W, u.max())); w0, w1 = int(max(0, w.min())), int(min(H, w.max()))
        if u1 - u0 < 2 or w1 - w0 < 2:
            continue
        depth = rd(dp)[w0:w1, u0:u1]
        near = zf.min()
        # pixels whose surface is at or behind the near face of the box: the box is not hidden there
        if (depth >= near - 0.03).sum() > 30:
            vis = True; break
    if vis:
        sel.append(v)
sub = dict(cfg); sub['views'] = sel
json.dump(sub, open(out, 'w'))
print('selected', len(sel), 'of', len(cfg['views']))
