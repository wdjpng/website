# Replace the llama in a room splat model with a dedicated, higher-detail llama model.
# Room splats are removed when they lie inside the llama's visual hull (carved from the alpha masks of the
# object-only renders) or within ~9 mm of the llama model's splats (catches the older, slightly larger fleece of
# the room model). The magnet next to the llama and the sill below it are protected. Llama-model splats outside
# the visual hull (floaters) are dropped. Then the llama splats are appended.
# usage: python merge_llama.py room.ply llama.ply llama_render_dir out.ply llama_box zmin [protect_box]
import sys, json, os, math
import numpy as np, torch, torch.nn.functional as F
from PIL import Image

room_p, llama_p, rdir, out_p, box_s, zmin = sys.argv[1:7]
protect = [float(v) for v in sys.argv[7].split(',')] if len(sys.argv) > 7 else None
zmin = float(zmin)
box = np.array([float(v) for v in box_s.split(',')])
dev = 'cuda' if torch.cuda.is_available() else 'cpu'

def load(p):
    with open(p, 'rb') as f:
        hdr = b''
        while True:
            l = f.readline(); hdr += l
            if l.strip() == b'end_header': break
        n = int([l for l in hdr.split(b'\n') if l.startswith(b'element vertex')][0].split()[-1])
        props = [l.split()[-1].decode() for l in hdr.split(b'\n') if l.startswith(b'property')]
        a = np.fromfile(f, dtype=np.float32, count=n * len(props)).reshape(n, len(props))
    return props, a

props, room = load(room_p)
props2, ll = load(llama_p)
assert props == props2, 'ply layouts differ'
iop = props.index('opacity')

# ---- visual hull test from the object-only renders
cfg = json.load(open(os.path.join(rdir, 'views.json')))
W, H = cfg['width'], cfg['height']
masks = []
for v in cfg['views']:
    png = os.path.join(rdir, v['name'] + '.png')
    if not os.path.exists(png):
        continue
    im = Image.open(png)
    if im.mode != 'RGBA':
        continue
    a = torch.from_numpy(np.asarray(im)[..., 3].copy()).to(dev).float()[None, None] / 255
    a = F.max_pool2d(F.avg_pool2d(a, 2), 5, stride=1, padding=2)[0, 0]      # half-res, dilated by ~5 px
    c2w = np.array(v['c2w']) @ np.diag([1, -1, -1, 1])
    masks.append((a, torch.from_numpy(np.linalg.inv(c2w).astype(np.float32)).to(dev), (W / 2) / math.tan(v['fov_x'] / 2)))
print('views used', len(masks), flush=True)
# optional extra render dirs (e.g. the previous llama) whose visual hull is also carved out of the room model
extra_masks = []
for ed in [d for d in os.environ.get('EXTRA_CARVE', '').split(':') if d]:
    ecfg = json.load(open(os.path.join(ed, 'views.json')))
    for v in ecfg['views']:
        png = os.path.join(ed, v['name'] + '.png')
        if not os.path.exists(png):
            continue
        im = Image.open(png)
        if im.mode != 'RGBA':
            continue
        a = torch.from_numpy(np.asarray(im)[..., 3].copy()).to(dev).float()[None, None] / 255
        a = F.max_pool2d(F.avg_pool2d(a, 2), 5, stride=1, padding=2)[0, 0]
        c2w = np.array(v['c2w']) @ np.diag([1, -1, -1, 1])
        extra_masks.append((a, torch.from_numpy(np.linalg.inv(c2w).astype(np.float32)).to(dev), (ecfg['width'] / 2) / math.tan(v['fov_x'] / 2)))
print('extra carve views', len(extra_masks), flush=True)

def in_hull(xyz, min_views=8, frac=0.97, mask_list=None):
    P = torch.from_numpy(xyz.astype(np.float32)).to(dev)
    inframe = torch.zeros(len(P), device=dev); inmask = torch.zeros(len(P), device=dev)
    for a, w2c, fx in (masks if mask_list is None else mask_list):
        h, w = a.shape
        pc = P @ w2c[:3, :3].T + w2c[:3, 3]
        z = pc[:, 2]
        u = (pc[:, 0] / z.clamp(min=1e-4) * fx + W / 2) / 2
        vv = (pc[:, 1] / z.clamp(min=1e-4) * fx + H / 2) / 2
        ok = (z > 0.02) & (u >= 0) & (u < w - 1) & (vv >= 0) & (vv < h - 1)
        val = a[vv.clamp(0, h - 1).long(), u.clamp(0, w - 1).long()]
        inframe += ok.float(); inmask += (ok & (val > 0.15)).float()
    return ((inframe >= min_views) & (inmask >= frac * inframe)).cpu().numpy()

# ---- clean the llama model: drop floaters outside its own (slightly looser) hull
keep_ll = in_hull(ll[:, :3], min_views=4, frac=0.90)
print('llama splats', len(ll), 'kept inside hull', keep_ll.sum(), flush=True)
ll = ll[keep_ll]

# ---- room splats to remove
xyz = room[:, :3]
pad = 0.02
cand = np.where((xyz[:, 0] > box[0] - pad) & (xyz[:, 0] < box[3] + pad) & (xyz[:, 1] > box[1] - pad) & (xyz[:, 1] < box[4] + pad)
                & (xyz[:, 2] > zmin) & (xyz[:, 2] < box[5] + pad))[0]
if protect is not None:
    pb = np.array(protect)
    inside_pb = ((xyz[cand] > pb[:3] - 0.004) & (xyz[cand] < pb[3:] + 0.004)).all(1)
    cand = cand[~inside_pb]
print('room splats', len(room), 'candidates', len(cand), flush=True)
hull = in_hull(xyz[cand])
if extra_masks:
    hull_old = in_hull(xyz[cand], mask_list=extra_masks)
    print('extra carve (previous llama hull)', int((hull_old & ~hull).sum()), flush=True)
    hull = hull | hull_old
# proximity to the llama model (3 mm voxels, dilated by 3 voxels)
vs = 0.003
lo = box[:3] - pad - 0.01
dims = np.ceil((box[3:] + pad + 0.01 - lo) / vs).astype(int)
occ = torch.zeros(tuple(dims), device=dev)
dense = ll[1 / (1 + np.exp(-ll[:, iop])) > 0.15, :3]
ijk = np.floor((dense - lo) / vs).astype(int)
okk = ((ijk >= 0) & (ijk < dims)).all(1); ijk = ijk[okk]
occ[ijk[:, 0], ijk[:, 1], ijk[:, 2]] = 1
occ = F.max_pool3d(occ[None, None], 7, stride=1, padding=3)[0, 0]
cijk = np.floor((xyz[cand] - lo) / vs).astype(int)
okc = ((cijk >= 0) & (cijk < dims)).all(1)
near = np.zeros(len(cand), bool)
ci = torch.from_numpy(cijk[okc]).to(dev)
near[okc] = (occ[ci[:, 0], ci[:, 1], ci[:, 2]] > 0).cpu().numpy()
rm = cand[hull | near]
print('removed room splats: hull', hull.sum(), 'near', near.sum(), 'total', len(rm), flush=True)
keep = np.ones(len(room), bool); keep[rm] = False
out = np.concatenate([room[keep], ll], 0)
with open(out_p, 'wb') as f:
    f.write(('ply\nformat binary_little_endian 1.0\nelement vertex %d\n' % len(out)).encode())
    for pr in props:
        f.write(('property float %s\n' % pr).encode())
    f.write(b'end_header\n')
    f.write(out.astype(np.float32).tobytes())
print('MERGED', out_p, len(out), flush=True)
