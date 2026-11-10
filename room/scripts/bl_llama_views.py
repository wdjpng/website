# Generate close-up camera views around the llama for a dedicated llama splat model.
# Cameras stay inside the room, keep clear of walls, and must see the llama without anything in between.
# usage: blender -b scene.blend --python bl_llama_views.py -- base_views.json out_views.json n_views seed
import bpy, sys, json, math, random
import numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:]
BASE, OUT, NV, SEED = argv[0], argv[1], int(argv[2]), int(argv[3])
rng = random.Random(SEED)
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()

llama = [o for o in sc.objects if o.name.startswith('Llama')]
lo = np.array([1e9] * 3); hi = -lo
for o in llama:
    for c in o.bound_box:
        w = np.array(o.matrix_world @ Vector(c))
        lo = np.minimum(lo, w); hi = np.maximum(hi, w)
print('LLAMA_BOX', ','.join('%.4f' % v for v in list(lo) + list(hi)), flush=True)
mag = [o for o in sc.objects if o.name.startswith('Framed art')]
mlo = np.array([1e9] * 3); mhi = -mlo
for o in mag:
    for c in o.bound_box:
        w = np.array(o.matrix_world @ Vector(c))
        mlo = np.minimum(mlo, w); mhi = np.maximum(mhi, w)
print('MAGNET_BOX', ','.join('%.4f' % v for v in list(mlo) + list(mhi)), flush=True)

skin = bpy.data.objects['Llama / skin']
me = skin.evaluated_get(dg).to_mesh()
V = np.array([skin.matrix_world @ v.co for v in me.vertices]); Nn = np.array([(skin.matrix_world.to_3x3() @ v.normal).normalized() for v in me.vertices])
sel = np.random.default_rng(SEED).choice(len(V), 260, replace=False)
centre = (lo + hi) / 2
centre[2] = lo[2] + 0.45 * (hi[2] - lo[2])
llama_names = {o.name for o in llama}

def first_hit(a, b):
    d = Vector(b) - Vector(a); L = d.length
    hit, loc, nrm, idx, ob, mat = sc.ray_cast(dg, Vector(a), d.normalized(), distance=L)
    return (ob.name if hit else None), ((loc - Vector(a)).length if hit else L)

def first_nonllama_hit(a, b):
    # walk along the segment, skipping llama meshes
    a = Vector(a); b = Vector(b); d = (b - a); L = d.length; d.normalize(); t = 0.0
    while t < L:
        hit, loc, nrm, idx, ob, mat = sc.ray_cast(dg, a + d * t, d, distance=L - t)
        if not hit:
            return None, L
        tt = t + (loc - (a + d * t)).length
        if ob.name not in llama_names:
            return ob.name, tt
        t = tt + 1e-4
    return None, L

# points on the outer fleece envelope that are in free space (not under the sill or inside the window)
probe = []
for i in sel:
    p = V[i] + Nn[i] * 0.035
    if first_hit(V[i] + Nn[i] * 0.002, p)[0] is None:
        probe.append(p)
probe = np.array(probe)
print('probes', len(probe), flush=True)

def clear(p, r=0.06):
    for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
        hit, loc, *_ = sc.ray_cast(dg, Vector(p), Vector(d), distance=r)
        if hit:
            return False
    return True

base = json.load(open(BASE))
views = []; tries = 0
while len(views) < NV and tries < 20000:
    tries += 1
    # distances: mostly close-ups, some mid-range
    r = math.exp(rng.uniform(math.log(0.20), math.log(1.6))) if rng.random() < 0.8 else rng.uniform(1.0, 2.4)
    az = math.radians(rng.uniform(-88, 88))           # around +X (the llama faces the room)
    el = math.radians(rng.uniform(-8, 62))
    d = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    tgt = centre + np.array([rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), rng.uniform(-0.04, 0.07)])
    cam = tgt + d * r
    if cam[2] < 0.3 or cam[2] > 2.3:
        continue
    # the camera must be reachable from the llama (not behind a wall) and have some clearance
    nm, dist = first_nonllama_hit(tgt, cam)
    if nm is not None:
        continue
    if not clear(cam):
        continue
    # nothing but the llama between the camera and the fleece envelope
    # occluders only count when they are in front of the llama (window parts behind its back do not)
    occl = 0
    dc = np.linalg.norm(centre - cam)
    for p in probe:
        nm, dist = first_hit(cam, p)
        if nm is not None and nm not in llama_names and dist < dc - 0.03:
            occl += 1
    if occl > 0:
        continue
    fwd = tgt - cam; fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    c2w = np.eye(4); c2w[:3, 0] = right; c2w[:3, 1] = up; c2w[:3, 2] = -fwd; c2w[:3, 3] = cam
    half = rng.uniform(0.13, 0.22)                     # half-width of the framed region (m)
    fov = 2 * math.atan(half / r)
    fov = min(max(fov, math.radians(25)), math.radians(80))
    i = len(views)
    views.append({'c2w': c2w.tolist(), 'fov_x': fov, 'name': 'l%04d' % i, 'idx': 7000 + i})
print('views', len(views), 'tries', tries, flush=True)
out = {k: base[k] for k in ('width', 'height', 'noise_threshold', 'color', 'glass_objects') if k in base}
out['views'] = views
json.dump(out, open(OUT, 'w'))
print('WROTE', OUT, flush=True)
