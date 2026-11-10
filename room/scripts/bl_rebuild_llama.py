# Rebuild the alpaca plush ("llama") on the windowsill from the user's reference photos, and fix the panda
# fridge magnet ("Framed art"). Saves a new .blend.
# usage: blender -b bedroom_reconstruction.blend --python bl_rebuild_llama.py -- out.blend magnet_texture.png [quality]
import bpy, bmesh, sys, math, numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:]
OUT_BLEND, MAGNET_TEX = argv[0], argv[1]
QUALITY = float(argv[2]) if len(argv) > 2 else 1.0   # strand count multiplier (use <1 for quick previews)
rng = np.random.default_rng(7)
sc = bpy.context.scene
coll = sc.collection

# ------------------------------------------------------------------ remove the old llama
old = [o for o in bpy.data.objects if o.name.startswith('Llama')]
for o in old:
    bpy.data.objects.remove(o, do_unlink=True)
print('removed', len(old), 'old llama objects', flush=True)

# ------------------------------------------------------------------ placement (Blender coords, facing +X into the room)
Y0 = -0.272
SILL = 0.742
FWD = np.array([1.0, 0, 0]); UP = np.array([0, 0, 1.0]); SIDE = np.array([0, 1.0, 0])
BODY_C = np.array([-1.750, Y0, SILL + 0.068]); BODY_R = np.array([0.064, 0.052, 0.046])
NECK_A = np.array([-1.708, Y0, 0.845]); NECK_B = np.array([-1.686, Y0, 0.940]); NECK_R = 0.022
HEAD_C = np.array([-1.674, Y0, 0.957]); HEAD_R = 0.029
MUZ_C = np.array([-1.6465, Y0, 0.9475]); MUZ_R = np.array([0.0128, 0.0112, 0.0102])

def link(obj):
    coll.objects.link(obj)
    return obj

def mat_principled(name, color, rough=0.8, sheen=0.0, sss=0.0, spec=0.3):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    for k, v in (('Sheen Weight', sheen), ('Subsurface Weight', sss), ('Specular IOR Level', spec)):
        if k in b.inputs:
            b.inputs[k].default_value = v
    if 'Sheen Tint' in b.inputs:
        try:
            b.inputs['Sheen Tint'].default_value = (1, 1, 1, 1)
        except TypeError:
            pass
    return m

# ------------------------------------------------------------------ skin mesh (union of primitives, voxel remeshed)
def ellipsoid_bm(bm, c, r, segs=48, rings=24):
    m = Matrix.Translation(Vector(c)) @ Matrix.Diagonal(Vector((r[0], r[1], r[2], 1.0)))
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0, matrix=m)

def capsule_bm(bm, a, b, r, n=10):
    for t in np.linspace(0, 1, n):
        ellipsoid_bm(bm, a + (b - a) * t, (r, r, r), 32, 16)

bm = bmesh.new()
ellipsoid_bm(bm, BODY_C, BODY_R)
# chest bulge + rump so the profile is a soft cloud rather than an egg
ellipsoid_bm(bm, BODY_C + np.array([0.036, 0, 0.008]), (0.040, 0.045, 0.040))
ellipsoid_bm(bm, BODY_C + np.array([-0.03, 0, -0.002]), (0.045, 0.05, 0.044))
capsule_bm(bm, NECK_A, NECK_B, NECK_R)
ellipsoid_bm(bm, HEAD_C, (HEAD_R * 1.12, HEAD_R * 0.92, HEAD_R * 0.98))
me = bpy.data.meshes.new('Llama skin'); bm.to_mesh(me); bm.free()
skin = link(bpy.data.objects.new('Llama / skin', me))
rm = skin.modifiers.new('remesh', 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = 0.0022
sm = skin.modifiers.new('smooth', 'LAPLACIANSMOOTH'); sm.iterations = 12; sm.lambda_factor = 0.8
dg = bpy.context.evaluated_depsgraph_get()
me2 = bpy.data.meshes.new_from_object(skin.evaluated_get(dg))
skin.modifiers.clear(); old_me = skin.data; skin.data = me2; bpy.data.meshes.remove(old_me)
for p in skin.data.polygons:
    p.use_smooth = True
skin_mat = mat_principled('Llama v2 / skin under fleece', (0.78, 0.74, 0.68), rough=0.9)
skin.data.materials.append(skin_mat)
skin.visible_shadow = True
print('skin verts', len(skin.data.vertices), flush=True)

# ------------------------------------------------------------------ sample fur roots
me = skin.data
me.calc_loop_triangles()
V = np.array([v.co[:] for v in me.vertices])
T = np.array([t.vertices[:] for t in me.loop_triangles])
a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
fn = np.cross(b - a, c - a); area = np.linalg.norm(fn, axis=1) * 0.5; fn /= (np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12)
# vertex normals for smooth interpolation
VN = np.zeros_like(V)
for k in range(3):
    np.add.at(VN, T[:, k], fn * area[:, None])
VN /= np.linalg.norm(VN, axis=1, keepdims=True) + 1e-12

def sample(n):
    tri = rng.choice(len(T), n, p=area / area.sum())
    u = rng.random(n); v = rng.random(n); f = u + v > 1; u[f] = 1 - u[f]; v[f] = 1 - v[f]
    w = 1 - u - v
    P = a[tri] * w[:, None] + b[tri] * u[:, None] + c[tri] * v[:, None]
    N = VN[T[tri, 0]] * w[:, None] + VN[T[tri, 1]] * u[:, None] + VN[T[tri, 2]] * v[:, None]
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    return P, N

def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

def vnoise(P, freq, seed):
    # cheap smooth 3D noise: sum of random sinusoids
    r = np.random.default_rng(seed); acc = np.zeros(len(P))
    for _ in range(6):
        k = r.normal(size=3); k /= np.linalg.norm(k); ph = r.random() * 6.283
        acc += np.sin(P @ k * freq * (0.7 + 0.6 * r.random()) + ph)
    return acc / 6

NSTR = int(420000 * QUALITY)
P, N = sample(NSTR)
# exclude roots inside the muzzle volume (it is a separate felt piece)
dm = (P - MUZ_C) / (MUZ_R * 1.02)
inside_muz = (dm ** 2).sum(1) < 1.0
P, N = P[~inside_muz], N[~inside_muz]
n = len(P)

# ---- region masks
d_head = np.linalg.norm(P - HEAD_C, axis=1)
headness = 1 - smoothstep(HEAD_R * 1.0, HEAD_R * 1.6, d_head)
seg = NECK_B - NECK_A; tt = np.clip(((P - NECK_A) @ seg) / (seg @ seg), 0, 1)
d_neck = np.linalg.norm(P - (NECK_A + tt[:, None] * seg), axis=1)
neckness = (1 - smoothstep(NECK_R * 1.0, NECK_R * 1.9, d_neck)) * (1 - headness)
bodyness = np.clip(1 - headness - neckness, 0, 1)
d_muz = np.linalg.norm((P - MUZ_C) / MUZ_R, axis=1)
EYE_L = HEAD_C + np.array([0.0115, 0.0255, 0.0065]); EYE_R = EYE_L * np.array([1, 0, 1]) + np.array([0, 2 * Y0 - EYE_L[1], 0])
d_eye = np.minimum(np.linalg.norm(P - EYE_L, axis=1), np.linalg.norm(P - EYE_R, axis=1))

# ---- lengths (m)
L_body = rng.uniform(0.036, 0.055, n)
L_neck = rng.uniform(0.018, 0.027, n)
L_head = rng.uniform(0.016, 0.024, n)
L = L_body * bodyness + L_neck * neckness + L_head * headness
L *= 0.35 + 0.65 * smoothstep(1.05, 2.3, d_muz)        # short clipped fleece around the muzzle
L *= 0.30 + 0.70 * smoothstep(0.004, 0.013, d_eye)     # eyes stay visible
EAR_L = HEAD_C + np.array([-0.012, 0.0185, 0.024]); EAR_R = EAR_L * np.array([1, 0, 1]) + np.array([0, 2 * Y0 - EAR_L[1], 0])
d_ear = np.minimum(np.linalg.norm(P - EAR_L, axis=1), np.linalg.norm(P - EAR_R, axis=1))
L *= 0.35 + 0.65 * smoothstep(0.008, 0.020, d_ear)     # ears poke out of the crown
L *= 1 + 0.18 * vnoise(P, 90, 3)                         # locks / uneven fleece
# under the body the fleece is squashed against the sill
bottom = smoothstep(SILL + 0.035, SILL + 0.012, P[:, 2])
L *= 1 - 0.45 * bottom

# ---- colour: beige/tan on the head top and back of the neck, white body and face front
# reference photos: the whole head and neck are beige, the body is white; the face right around the muzzle is lighter
back = smoothstep(-1.660, -1.700, P[:, 0])                       # behind the eyes / back of neck
face = 1 - smoothstep(1.3, 3.2, d_muz)
tan = headness * (1 - 0.55 * face)
tan = np.maximum(tan, neckness * (0.5 + 0.5 * back))
tan = np.maximum(tan, bodyness * smoothstep(0.850, 0.895, P[:, 2]) * (0.35 + 0.45 * back))   # soft transition into the body
tan *= 1 - 0.8 * (1 - smoothstep(1.0, 1.6, d_muz))
tan = np.clip(tan, 0, 1)
tan *= smoothstep(0.004, 0.014, d_eye) * 0.4 + 0.6
tan = np.clip(tan * (0.85 + 0.3 * vnoise(P, 60, 5)), 0, 1)
melanin = 0.045 + 0.33 * tan + rng.normal(0, 0.012, n).clip(-0.03, 0.03)
melanin = np.clip(melanin, 0.02, 0.6)

# ---- strand geometry
K = 9
gravity = np.array([0, 0, -1.0])
droop = 0.38 * bodyness + 0.22 * neckness + 0.10 * headness
jit = rng.normal(size=(n, 3)); jit -= (jit * N).sum(1, keepdims=True) * N
D0 = N + droop[:, None] * gravity + 0.30 * jit
D0 /= np.linalg.norm(D0, axis=1, keepdims=True)
# bottom roots point sideways rather than into the sill
side = D0.copy(); side[:, 2] = np.maximum(side[:, 2], 0.05); side /= np.linalg.norm(side, axis=1, keepdims=True)
D0 = D0 * (1 - bottom[:, None]) + side * bottom[:, None]
# two perpendicular axes for the crimp
A1 = np.cross(D0, rng.normal(size=(n, 3))); A1 /= np.linalg.norm(A1, axis=1, keepdims=True)
A2 = np.cross(D0, A1)
freq = rng.uniform(2.5, 4.0, n)            # crimp waves along the fibre
amp = rng.uniform(0.07, 0.12, n)           # relative to length
phase = rng.random(n) * 6.283
s = np.linspace(0, 1, K)
pts = np.zeros((n, K, 3))
for k, sk in enumerate(s):
    # fibres curl slightly towards their tips and gain random frizz
    bend = 0.25 * sk * sk
    dirk = D0 + bend * (droop[:, None] * gravity + 0.3 * A1)
    dirk /= np.linalg.norm(dirk, axis=1, keepdims=True)
    wave = np.sin(phase + freq * sk * 6.283)[:, None] * A1 + np.cos(phase + freq * sk * 6.283)[:, None] * A2 * 0.6
    frizz = rng.normal(size=(n, 3)) * 0.012 * sk
    pts[:, k] = P + dirk * (L * sk)[:, None] + (wave * (amp * L * min(1.0, sk * 3))[:, None]) + frizz * L[:, None]
# locks: strands rooted close together share a common tip so the fleece forms soft tufts
nl = max(500, n // 120)
lock_roots = P[rng.choice(n, nl, replace=False)]
from mathutils.kdtree import KDTree
kd = KDTree(nl)
for i, q in enumerate(lock_roots): kd.insert(q.tolist(), i)
kd.balance()
lid = np.array([kd.find(q.tolist())[1] for q in P])
lock_tip = np.zeros((nl, 3)); cntl = np.zeros(nl)
np.add.at(lock_tip, lid, pts[:, -1]); np.add.at(cntl, lid, 1)
lock_tip /= np.maximum(cntl, 1)[:, None]
clump = rng.uniform(0.25, 0.55, n) * bodyness + rng.uniform(0.1, 0.3, n) * (1 - bodyness)
root = pts[:, 0].copy(); tip = pts[:, -1].copy(); ltip = lock_tip[lid]
for k, sk in enumerate(s):
    w = (clump * sk ** 1.5)[:, None]
    dev = pts[:, k] - (root + (tip - root) * sk)
    target = root + (ltip - root) * sk + 0.6 * dev
    pts[:, k] = pts[:, k] * (1 - w) + target * w
pts[:, :, 2] = np.maximum(pts[:, :, 2], SILL + 0.0015)
# keep the fleece out of the felt muzzle
for k in range(1, K):
    q = (pts[:, k] - MUZ_C) / MUZ_R; r = np.linalg.norm(q, axis=1)
    inside = r < 1.04
    if inside.any():
        pts[inside, k] = MUZ_C + q[inside] / r[inside, None] * 1.04 * MUZ_R

def make_curves(name, points, radius_root, radius_tip, attrs, material):
    cnt, kk = points.shape[0], points.shape[1]
    hc = bpy.data.hair_curves.new(name)
    hc.add_curves([kk] * cnt)
    hc.position_data.foreach_set('vector', points.reshape(-1).astype(np.float32))
    rad = np.linspace(radius_root, radius_tip, kk)[None, :].repeat(cnt, 0).reshape(-1).astype(np.float32)
    ra = hc.attributes.get('radius') or hc.attributes.new('radius', 'FLOAT', 'POINT')
    ra.data.foreach_set('value', rad)
    for an, (vals, typ) in attrs.items():
        at = hc.attributes.new(an, typ, 'CURVE')
        if typ == 'FLOAT':
            at.data.foreach_set('value', vals.astype(np.float32))
        else:
            at.data.foreach_set('color', vals.astype(np.float32).reshape(-1))
    hc.materials.append(material)
    return link(bpy.data.objects.new(name, hc))

# fleece material: Principled Hair (melanin), melanin per curve from attribute
fm = bpy.data.materials.new('Llama v2 / alpaca fleece'); fm.use_nodes = True
nt = fm.node_tree; nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputMaterial')
hb = nt.nodes.new('ShaderNodeBsdfHairPrincipled')
try:
    hb.model = 'CHIANG'
except Exception:
    pass
hb.parametrization = 'COLOR'
att = nt.nodes.new('ShaderNodeAttribute'); att.attribute_name = 'fcol'; att.attribute_type = 'GEOMETRY'
nt.links.new(att.outputs['Color'], hb.inputs['Color'])
hb.inputs['Roughness'].default_value = 0.5
hb.inputs['Radial Roughness'].default_value = 0.75
hb.inputs['Coat'].default_value = 0.0
for k_, v_ in (('IOR', 1.55), ('Random Roughness', 0.25)):
    if k_ in hb.inputs: hb.inputs[k_].default_value = v_
nt.links.new(hb.outputs['BSDF'], out.inputs['Surface'])

white = np.array([0.93, 0.91, 0.87]); tanc = np.array([0.21, 0.13, 0.068])
fcol = white[None] * (1 - tan[:, None]) + tanc[None] * tan[:, None]
fcol *= rng.uniform(0.93, 1.03, (n, 1))
fcol = np.concatenate([np.clip(fcol, 0, 1), np.ones((n, 1))], 1)
fleece = make_curves('Llama / alpaca fleece', pts, 0.000048, 0.000014, {'fcol': (fcol, 'FLOAT_COLOR')}, fm)
print('fleece strands', n, 'tan>0.5 fraction %.3f' % (tan > 0.5).mean(), flush=True)

# ------------------------------------------------------------------ felt muzzle with stitching
felt_white = mat_principled('Llama v2 / white felt', (0.74, 0.72, 0.68), rough=0.95, sheen=0.3, sss=0.0)
bm = bmesh.new(); ellipsoid_bm(bm, MUZ_C, MUZ_R, 40, 20)
me = bpy.data.meshes.new('muzzle'); bm.to_mesh(me); bm.free()
for p in me.polygons: p.use_smooth = True
muz = link(bpy.data.objects.new('Llama / felt muzzle', me)); me.materials.append(felt_white)

def on_muzzle(dirs, lift=0.0004):
    d = np.array(dirs, float); d /= np.linalg.norm(d, axis=1, keepdims=True)
    # point on ellipsoid along direction d from the centre
    t = 1.0 / np.sqrt(((d / MUZ_R) ** 2).sum(1))
    p = MUZ_C + d * t[:, None]
    nrm = (p - MUZ_C) / MUZ_R ** 2; nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    return p + nrm * lift

def thread(name, pts3, radius, material):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = radius; cu.bevel_resolution = 3; cu.use_fill_caps = True
    sp = cu.splines.new('POLY'); sp.points.add(len(pts3) - 1)
    for i, p in enumerate(pts3):
        sp.points[i].co = (*p, 1)
    cu.materials.append(material)
    return link(bpy.data.objects.new(name, cu))

black_thread = mat_principled('Llama v2 / black thread', (0.015, 0.014, 0.014), rough=0.7, sheen=0.3)
red_thread = mat_principled('Llama v2 / red thread', (0.55, 0.03, 0.03), rough=0.7, sheen=0.3)
# "Y" seen from the front: vertical line down the front + a V over the top
top_front = np.array([0.85, 0, 0.38])        # the Y junction on the front of the muzzle
centre = np.array([0.95, 0, -0.22])
ts = np.linspace(0, 1, 14)
vert = on_muzzle([top_front * (1 - t) + centre * t for t in ts])
thread('Llama / stitch nose', vert, 0.00045, black_thread)
for sgn in (1, -1):
    vline = on_muzzle([top_front * (1 - t) + np.array([0.30, 0.58 * sgn, 0.78]) * t for t in ts])
    thread('Llama / stitch top %d' % sgn, vline, 0.00045, black_thread)
    mouth = on_muzzle([np.array([0.93, 0, -0.30]) * (1 - t) + np.array([0.25, 0.92 * sgn, -0.38]) * t for t in ts])
    thread('Llama / stitch mouth %d' % sgn, mouth, 0.00042, black_thread)
# red stitch under the mouth line (visible in profile)
thread('Llama / stitch red', on_muzzle([np.array([0.55, 0.55, -0.55]) * (1 - t) + np.array([0.0, 0.85, -0.45]) * t for t in ts]), 0.00045, red_thread)

# ------------------------------------------------------------------ halter, cord, pompom
cols = {'red': (0.62, 0.035, 0.035), 'yellow': (0.80, 0.50, 0.05), 'blue': (0.04, 0.08, 0.42), 'black': (0.02, 0.02, 0.025)}
ymats = {k: mat_principled('Llama v2 / yarn ' + k, c, rough=0.85, sheen=0.4) for k, c in cols.items()}
ring_x = MUZ_C[0] - 0.0105
for i, k in enumerate(['red', 'yellow', 'blue', 'black']):
    xr = ring_x - i * 0.0012
    ang = np.linspace(0, 2 * math.pi, 49)
    # ring hugs the muzzle cross-section at this x
    sx = math.sqrt(max(1e-6, 1 - ((xr - MUZ_C[0]) / MUZ_R[0]) ** 2))
    ry, rz = MUZ_R[1] * sx + 0.0012, MUZ_R[2] * sx + 0.0012
    ring = [(xr, MUZ_C[1] + ry * math.cos(t), MUZ_C[2] + rz * math.sin(t)) for t in ang]
    thread('Llama / halter %s' % k, ring, 0.00062, ymats[k])

POM_C = np.array([-1.640, Y0 + 0.004, MUZ_C[2] - 0.041]); POM_R = 0.0145
cord_top = np.array([ring_x - 0.002, Y0, MUZ_C[2] - MUZ_R[2] - 0.0008])
cord_bot = POM_C + np.array([-0.002, 0, POM_R * 0.85])
for i, k in enumerate(['red', 'yellow', 'blue']):
    pts3 = []
    for t in np.linspace(0, 1, 60):
        cpt = cord_top * (1 - t) + cord_bot * t + np.array([0.006 * math.sin(t * math.pi), 0, 0])
        th = t * 14 * math.pi + i * 2.094
        pts3.append(cpt + 0.0009 * np.array([0, math.cos(th), 0]) + 0.0009 * np.array([math.sin(th), 0, 0]))
    thread('Llama / cord %s' % k, pts3, 0.00055, ymats[k])

# pompom core + radiating yarn strands, colours in patches (red on top, navy and mustard below)
bm = bmesh.new(); ellipsoid_bm(bm, POM_C, (POM_R * 0.55,) * 3, 24, 12)
me = bpy.data.meshes.new('pompom core'); bm.to_mesh(me); bm.free()
core = link(bpy.data.objects.new('Llama / pompom core', me)); me.materials.append(ymats['blue'])
npom = int(26000 * max(QUALITY, 0.4))
d = rng.normal(size=(npom, 3)); d /= np.linalg.norm(d, axis=1, keepdims=True)
# three colour sectors (red / navy / mustard) in irregular patches, plus some strands mixed in from neighbours
pa, pb = vnoise(d, 2.0, 11), vnoise(d, 2.0, 12)
sector = ((np.arctan2(pb, pa) + math.pi) / (2 * math.pi) * 3).astype(int) % 3
mix = rng.random(npom) < 0.06
sector[mix] = rng.integers(0, 3, mix.sum())
palette = np.array([cols['red'], cols['blue'], cols['yellow']])
pc = palette[sector] * rng.uniform(0.8, 1.15, (npom, 1))
Kp = 6
lens = POM_R * rng.uniform(0.84, 1.06, npom)
pp = np.zeros((npom, Kp, 3))
jit = rng.normal(size=(npom, 3)) * 0.16
curl = rng.normal(size=(npom, 3)) * 0.0006
for k, sk in enumerate(np.linspace(0, 1, Kp)):
    dd = d + jit * sk * sk; dd /= np.linalg.norm(dd, axis=1, keepdims=True)
    pp[:, k] = POM_C + dd * (lens * (0.15 + 0.85 * sk))[:, None] + curl * math.sin(sk * 3.0)
ym = bpy.data.materials.new('Llama v2 / pompom yarn'); ym.use_nodes = True
b = ym.node_tree.nodes.get('Principled BSDF')
ca = ym.node_tree.nodes.new('ShaderNodeAttribute'); ca.attribute_name = 'col'; ca.attribute_type = 'GEOMETRY'
ym.node_tree.links.new(ca.outputs['Color'], b.inputs['Base Color'])
b.inputs['Roughness'].default_value = 0.85
if 'Sheen Weight' in b.inputs: b.inputs['Sheen Weight'].default_value = 0.4
pcol = np.concatenate([pc, np.ones((npom, 1))], 1)
make_curves('Llama / pompom yarn', pp, 0.00030, 0.00020, {'col': (pcol, 'FLOAT_COLOR')}, ym)

# ------------------------------------------------------------------ eyes and ears
eye_ring = mat_principled('Llama v2 / tan felt eye', (0.42, 0.28, 0.17), rough=0.9, sheen=0.4)
eye_dark = mat_principled('Llama v2 / dark felt pupil', (0.07, 0.065, 0.065), rough=0.9, sheen=0.3)
for sgn, EC in ((1, EYE_L), (-1, EYE_R)):
    nrm = (EC - HEAD_C); nrm /= np.linalg.norm(nrm)
    for rad, depth, m in ((0.0046, 0.0012, eye_ring), (0.0024, 0.0019, eye_dark)):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=rad, radius2=rad * 0.9, depth=depth)
        me = bpy.data.meshes.new('eye'); bm.to_mesh(me); bm.free()
        ob = link(bpy.data.objects.new('Llama / felt eye', me)); me.materials.append(m)
        z = Vector(nrm.tolist()); rot = z.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        ob.matrix_world = Matrix.Translation(Vector((EC + nrm * (0.0035 + depth * 0.5)).tolist())) @ rot
ear_mat = mat_principled('Llama v2 / dark grey felt ear', (0.11, 0.105, 0.10), rough=0.95, sheen=0.5)
for sgn in (1, -1):
    bm = bmesh.new()
    # rounded triangle ear, 2 mm thick
    pts2 = [(-0.0088, 0.0), (0.0088, 0.0), (0.0072, 0.016), (0.0021, 0.032), (-0.0021, 0.032), (-0.0072, 0.016)]
    vs = [bm.verts.new((x, -0.001, y)) for x, y in pts2] + [bm.verts.new((x, 0.001, y)) for x, y in pts2]
    bm.faces.new(vs[:6]); bm.faces.new(list(reversed(vs[6:])))
    for i in range(6):
        j = (i + 1) % 6; bm.faces.new([vs[i], vs[j], vs[6 + j], vs[6 + i]])
    me = bpy.data.meshes.new('ear'); bm.to_mesh(me); bm.free()
    ob = link(bpy.data.objects.new('Llama / felt ear', me)); me.materials.append(ear_mat)
    sub = ob.modifiers.new('sub', 'SUBSURF'); sub.levels = 2; sub.render_levels = 2
    base = HEAD_C + np.array([-0.012, sgn * 0.0185, 0.021])
    ob.matrix_world = Matrix.Translation(Vector(base.tolist())) @ Matrix.Rotation(sgn * -0.45, 4, 'X') @ Matrix.Rotation(0.25, 4, 'Y') @ Matrix.Rotation(sgn * 0.5, 4, 'Z')

# ------------------------------------------------------------------ panda fridge magnet ("Framed art")
back = bpy.data.objects.get('Framed art / backing')
pic = bpy.data.objects.get('Framed art / photographed picture')
if back and pic:
    H = 0.128; Wm = H * 0.445; Tm = 0.009
    loc = back.matrix_world.translation.copy()
    base_z = min((back.matrix_world @ Vector(v)).z for v in back.bound_box)
    # rebuild the frame as a thin box facing +X (into the room), standing on the sill
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    me = bpy.data.meshes.new('magnet frame'); bm.to_mesh(me); bm.free()
    frame = link(bpy.data.objects.new('Framed art / wooden magnet frame', me))
    frame.matrix_world = Matrix.Translation(Vector((loc.x, loc.y, base_z + H / 2))) @ Matrix.Diagonal(Vector((Tm, Wm, H, 1)))
    bev = frame.modifiers.new('bevel', 'BEVEL'); bev.width = 0.0009; bev.segments = 2
    for m in back.data.materials:
        frame.data.materials.append(m)
    # front face: the rectified photo of the real magnet (frame border included)
    img = bpy.data.images.load(MAGNET_TEX); img.pack()
    fm2 = bpy.data.materials.new('Framed art / panda magnet photo'); fm2.use_nodes = True
    bsdf = fm2.node_tree.nodes.get('Principled BSDF')
    tex = fm2.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = img
    fm2.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.35   # glazed front
    me = bpy.data.meshes.new('magnet face')
    xf = loc.x + Tm / 2 + 0.0004
    me.from_pydata([(xf, loc.y + Wm / 2, base_z), (xf, loc.y - Wm / 2, base_z), (xf, loc.y - Wm / 2, base_z + H), (xf, loc.y + Wm / 2, base_z + H)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(); 
    for li, (u, v) in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[li].uv = (u, v)
    me.materials.append(fm2)
    link(bpy.data.objects.new('Framed art / panda magnet face', me))
    bpy.data.objects.remove(back, do_unlink=True); bpy.data.objects.remove(pic, do_unlink=True)
    print('magnet rebuilt', Wm, H, flush=True)

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=False)
print('SAVED', OUT_BLEND, flush=True)
