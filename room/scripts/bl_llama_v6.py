# Alpaca plush ("llama") on the windowsill, v6: rebuilt from the user's close-up photos.
#  - face: a rounded white needle-felt snout with black stitching (along the top ridge, down the front, mouth line on
#    both sides), the multicolour halter round its base, and small felt eyes right behind the halter; the fleece
#    around the snout and eyes is short, so snout + eyes read as one face
#  - fleece: ~1.1M very fine fibres grouped into wavy locks, frizz and flyaway fibres; Principled Hair (Chiang) with
#    melanin per fibre: white body, cream/beige neck and head, light-brown crown and eye area
#  - dark grey felt ears, pompom on a cord in front of the neck, panda fridge magnet next to it
# usage: blender -b bedroom_reconstruction.blend --python bl_llama_v6.py -- out.blend magnet_tex.png [quality]
import bpy, bmesh, sys, math, numpy as np
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

argv = sys.argv[sys.argv.index('--') + 1:]
OUT_BLEND, MAGNET_TEX = argv[0], argv[1]
QUALITY = float(argv[2]) if len(argv) > 2 else 1.0
rng = np.random.default_rng(11)
sc = bpy.context.scene
coll = sc.collection

old = [o for o in bpy.data.objects if o.name.startswith('Llama')]
for o in old:
    bpy.data.objects.remove(o, do_unlink=True)
print('removed', len(old), 'old llama objects', flush=True)

# ------------------------------------------------------------------ placement (Blender coords, facing +X into the room)
Y0 = -0.272
SILL = 0.742
BODY_C = np.array([-1.752, Y0, SILL + 0.074]); BODY_R = np.array([0.064, 0.054, 0.056])
NECK_A = np.array([-1.712, Y0, 0.842]); NECK_B = np.array([-1.690, Y0, 0.930]); NECK_R = 0.019
HEAD_C = np.array([-1.679, Y0, 0.959]); HEAD_R = 0.030
SN_C = np.array([-1.6365, Y0, 0.9500])          # snout centre
SN_H = np.array([0.0110, 0.0078, 0.0082])       # snout half extents (2.2 x 1.6 x 1.6 cm)
SN_E = (0.55, 0.85, 0.85)                       # superellipsoid exponents (short rounded cylinder, flat-ish front)
HALTER_X = SN_C[0] - 0.0062
EYE_L = np.array([SN_C[0] - 0.0135, Y0 + 0.0150, SN_C[2] + 0.0050])
EYE_R = EYE_L * np.array([1, 0, 1]) + np.array([0, 2 * Y0 - EYE_L[1], 0])
EAR_L = HEAD_C + np.array([-0.010, 0.0185, 0.024]); EAR_R = EAR_L * np.array([1, 0, 1]) + np.array([0, 2 * Y0 - EAR_L[1], 0])

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
    return m

def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

def vnoise(P, freq, seed):
    r = np.random.default_rng(seed); acc = np.zeros(len(P))
    for _ in range(6):
        k = r.normal(size=3); k /= np.linalg.norm(k); ph = r.random() * 6.283
        acc += np.sin(P @ k * freq * (0.7 + 0.6 * r.random()) + ph)
    return acc / 6

def ellipsoid_bm(bm, c, r, segs=48, rings=24):
    m = Matrix.Translation(Vector(c)) @ Matrix.Diagonal(Vector((r[0], r[1], r[2], 1.0)))
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0, matrix=m)

def capsule_bm(bm, a, b, r, n=10):
    for t in np.linspace(0, 1, n):
        ellipsoid_bm(bm, a + (b - a) * t, (r, r, r), 32, 16)

def superellipsoid_mesh(name, c, h, e, segs=64, rings=40):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
    for v in bm.verts:
        p = np.array(v.co[:])
        q = np.sign(p) * np.abs(p) ** np.array(e)
        v.co = Vector((c + q * h).tolist())
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    return me

def snout_dist(P):
    # approximate normalised distance to the snout (1 = on the surface)
    q = np.abs((P - SN_C) / SN_H)
    return (q[:, 0] ** (2 / SN_E[0]) + q[:, 1] ** (2 / SN_E[1]) + q[:, 2] ** (2 / SN_E[2])) ** 0.5

def on_snout(dirs, lift=0.00035):
    # point on the snout surface along each direction from its centre (bisection on the implicit function)
    d = np.array(dirs, float); d /= np.linalg.norm(d, axis=1, keepdims=True)
    lo = np.zeros(len(d)); hi = np.full(len(d), 0.05)
    for _ in range(40):
        mid = (lo + hi) / 2
        inside = snout_dist(SN_C + d * mid[:, None]) < 1
        lo = np.where(inside, mid, lo); hi = np.where(inside, hi, mid)
    p = SN_C + d * lo[:, None]
    # normal from the gradient
    eps = 1e-4
    g = np.stack([(snout_dist(p + np.eye(3)[k] * eps) - snout_dist(p - np.eye(3)[k] * eps)) for k in range(3)], 1)
    g /= np.linalg.norm(g, axis=1, keepdims=True)
    return p + g * lift

# ------------------------------------------------------------------ skin (body, neck, head; the snout is separate felt)
bm = bmesh.new()
ellipsoid_bm(bm, BODY_C, BODY_R)
ellipsoid_bm(bm, BODY_C + np.array([0.034, 0, 0.016]), (0.040, 0.046, 0.046))
ellipsoid_bm(bm, BODY_C + np.array([-0.032, 0, -0.002]), (0.045, 0.050, 0.044))
capsule_bm(bm, NECK_A, NECK_B, NECK_R)
ellipsoid_bm(bm, HEAD_C, (HEAD_R * 1.05, HEAD_R * 0.95, HEAD_R))
ellipsoid_bm(bm, HEAD_C + np.array([0.016, 0, -0.004]), (0.017, 0.016, 0.016))   # cheeks / base of the snout
me = bpy.data.meshes.new('Llama skin'); bm.to_mesh(me); bm.free()
skin = link(bpy.data.objects.new('Llama / skin', me))
rm = skin.modifiers.new('remesh', 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = 0.002
sm = skin.modifiers.new('smooth', 'LAPLACIANSMOOTH'); sm.iterations = 12; sm.lambda_factor = 0.8
dg = bpy.context.evaluated_depsgraph_get()
me2 = bpy.data.meshes.new_from_object(skin.evaluated_get(dg))
skin.modifiers.clear(); old_me = skin.data; skin.data = me2; bpy.data.meshes.remove(old_me)
for p in skin.data.polygons:
    p.use_smooth = True
skin.data.materials.append(mat_principled('Llama v6 / skin under fleece', (0.70, 0.64, 0.55), rough=0.9))
print('skin verts', len(skin.data.vertices), flush=True)

me = skin.data
me.calc_loop_triangles()
V = np.array([v.co[:] for v in me.vertices])
T = np.array([t.vertices[:] for t in me.loop_triangles])
A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
fn = np.cross(B - A, C - A); area = np.linalg.norm(fn, axis=1) * 0.5; fn /= (np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12)
VN = np.zeros_like(V)
for k in range(3):
    np.add.at(VN, T[:, k], fn * area[:, None])
VN /= np.linalg.norm(VN, axis=1, keepdims=True) + 1e-12

def sample(n):
    tri = rng.choice(len(T), n, p=area / area.sum())
    u = rng.random(n); v = rng.random(n); f = u + v > 1; u[f] = 1 - u[f]; v[f] = 1 - v[f]
    w = 1 - u - v
    P = A[tri] * w[:, None] + B[tri] * u[:, None] + C[tri] * v[:, None]
    N = VN[T[tri, 0]] * w[:, None] + VN[T[tri, 1]] * u[:, None] + VN[T[tri, 2]] * v[:, None]
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    return P, N

# ------------------------------------------------------------------ fleece roots and regions
NSTR = int(1400000 * QUALITY)
P, N = sample(NSTR)
keep = (snout_dist(P) > 1.03) & (P[:, 2] > SILL + 0.0005)
P, N = P[keep], N[keep]
n = len(P)
d_head = np.linalg.norm(P - HEAD_C, axis=1)
headness = 1 - smoothstep(HEAD_R * 1.05, HEAD_R * 1.7, d_head)
seg = NECK_B - NECK_A; tt = np.clip(((P - NECK_A) @ seg) / (seg @ seg), 0, 1)
d_neck = np.linalg.norm(P - (NECK_A + tt[:, None] * seg), axis=1)
neckness = (1 - smoothstep(NECK_R * 1.0, NECK_R * 2.0, d_neck)) * (1 - headness)
bodyness = np.clip(1 - headness - neckness, 0, 1)
sd = snout_dist(P)
d_eye = np.minimum(np.linalg.norm(P - EYE_L, axis=1), np.linalg.norm(P - EYE_R, axis=1))
d_ear = np.minimum(np.linalg.norm(P - EAR_L, axis=1), np.linalg.norm(P - EAR_R, axis=1))
face = (1 - smoothstep(1.05, 2.6, sd)) * (P[:, 0] > HEAD_C[0] - 0.006)          # skin round the snout (cheeks)
eyezone = 1 - smoothstep(0.0065, 0.0150, d_eye)

# ---- lengths (m)
L = (rng.uniform(0.040, 0.075, n) * bodyness + rng.uniform(0.019, 0.026, n) * neckness
     + rng.uniform(0.021, 0.028, n) * headness)
L *= 0.22 + 0.78 * (1 - face)                 # short fleece round the snout
L *= 0.18 + 0.82 * (1 - eyezone)              # and round the eyes, so the face reads as one
L *= 0.15 + 0.85 * smoothstep(0.008, 0.024, d_ear)
L *= 1 + (0.22 + 0.18 * bodyness) * vnoise(P, 70, 3)
bottom = smoothstep(SILL + 0.035, SILL + 0.010, P[:, 2])
L *= 1 - 0.5 * bottom

# ---- colour as hair melanin: white body, cream neck, beige head, light-brown crown and eye patches
back = smoothstep(-1.665, -1.705, P[:, 0])
crown = smoothstep(0.955, 0.985, P[:, 2]) * headness
eye_patch = (1 - smoothstep(0.008, 0.022, d_eye)) * (1 - face)
patch = smoothstep(-0.35, 0.25, vnoise(P, 50, 31))          # tan patches on a cream base, like the photos
tanness = np.clip((headness + 0.8 * neckness) * (0.12 + 0.62 * patch + 0.50 * back), 0, 1)   # cream head, tan patches, tan back of head/neck
tanness = np.maximum(tanness, 0.95 * crown)
tanness = np.maximum(tanness, 0.90 * eye_patch)
tanness *= 1 - 0.85 * face
tanness = np.clip(tanness * (0.85 + 0.3 * vnoise(P, 45, 5)), 0, 1)
CREAM = np.array([0.93, 0.91, 0.85]); BEIGE = np.array([0.84, 0.71, 0.45]); BROWN = np.array([0.68, 0.52, 0.28])
t2 = np.clip((tanness - 0.6) / 0.4, 0, 1)
fcol = CREAM[None] * (1 - np.minimum(tanness / 0.6, 1)[:, None]) + BEIGE[None] * np.minimum(tanness / 0.6, 1)[:, None]
fcol = fcol * (1 - t2[:, None]) + BROWN[None] * t2[:, None]
fcol *= rng.uniform(0.94, 1.04, (n, 1))
fcol = np.concatenate([np.clip(fcol, 0, 1), np.ones((n, 1))], 1)

# ---- fibre geometry: locks with a shared wavy path, fibre crimp and frizz, plus flyaways
K = 16
s = np.linspace(0, 1, K)
gravity = np.array([0, 0, -1.0])
# combing direction: away from the face on the head, downwards on the body
away = P - SN_C; away[:, 2] *= 0.3; away /= np.linalg.norm(away, axis=1, keepdims=True)
droop = 0.55 * bodyness + 0.20 * neckness + 0.05 * headness
D0 = N + droop[:, None] * gravity + 0.35 * (headness + face)[:, None] * away
jit = rng.normal(size=(n, 3)); jit -= (jit * N).sum(1, keepdims=True) * N
D0 = D0 + (0.28 - 0.10 * bodyness)[:, None] * jit
D0 /= np.linalg.norm(D0, axis=1, keepdims=True)
side = D0.copy(); side[:, 2] = np.maximum(side[:, 2], 0.05); side /= np.linalg.norm(side, axis=1, keepdims=True)
D0 = D0 * (1 - bottom[:, None]) + side * bottom[:, None]

# tufts: big soft locks on the body (~LOCK_BODY fibres), smaller ones on head and neck. The real fleece reads as a
# cloud of soft tufts with shadowed partings between them, not as an even fuzz.
LOCK_BODY, LOCK_HEAD = 1500, 500
lsize = LOCK_HEAD + (LOCK_BODY - LOCK_HEAD) * bodyness
pw_ = 1 / lsize; nl = int(pw_.sum())
lock_seed = rng.choice(n, nl, replace=False, p=pw_ / pw_.sum())
kd = KDTree(nl)
for i, q in enumerate(P[lock_seed]): kd.insert(q.tolist(), i)
kd.balance()
lid = np.array([kd.find(q.tolist())[1] for q in P])
cnt = np.bincount(lid, minlength=nl).astype(float)
lroot = np.zeros((nl, 3)); np.add.at(lroot, lid, P); lroot /= np.maximum(cnt, 1)[:, None]
# dome-shaped tufts: fibres near the edge of a lock are shorter, so partings open up between the tufts
r2 = ((P - lroot[lid]) ** 2).sum(1)
r2m = np.zeros(nl); np.add.at(r2m, lid, r2); r2m /= np.maximum(cnt, 1)
rel = np.sqrt(r2 / (2 * r2m[lid] + 1e-12))
L *= 1 - (0.28 * bodyness + 0.30 * (1 - bodyness)) * np.clip(rel, 0, 1.3) ** 2 * (1 - np.maximum(face, eyezone))
L *= (rng.uniform(0.78, 1.22, nl))[lid] ** (0.4 + 0.6 * bodyness)        # tufts of uneven length
fl_ = np.zeros((nl, 4)); np.add.at(fl_, lid, fcol); fl_ /= np.maximum(cnt, 1)[:, None]
fcol = 0.4 * fcol + 0.6 * fl_[lid]                   # a tuft shares its colour, like the real tan patches
ldir = np.zeros((nl, 3)); np.add.at(ldir, lid, D0); ldir /= np.linalg.norm(ldir, axis=1, keepdims=True) + 1e-9
ldir = ldir + 0.22 * rng.normal(size=(nl, 3)); ldir /= np.linalg.norm(ldir, axis=1, keepdims=True)
lL = np.zeros(nl); np.add.at(lL, lid, L); lL /= np.maximum(cnt, 1)
la1 = np.cross(ldir, rng.normal(size=(nl, 3))); la1 /= np.linalg.norm(la1, axis=1, keepdims=True)
la2 = np.cross(ldir, la1)
lfreq = rng.uniform(1.0, 1.8, nl); lamp = rng.uniform(0.06, 0.11, nl) * (1 + 0.3 * (lsize[lock_seed] > 1000)); lph = rng.random(nl) * 6.283
ldroop = np.zeros(nl); np.add.at(ldroop, lid, droop); ldroop /= np.maximum(cnt, 1)

flyaway = rng.random(n) < 0.03
Lf = L * np.where(flyaway, rng.uniform(1.0, 1.12, n), 1.0)
clump = np.where(flyaway, 0.0, rng.uniform(0.35, 0.60, n) * (1 - bodyness) + rng.uniform(0.55, 0.80, n) * bodyness)
clump *= 1 - 0.7 * np.maximum(face, eyezone)
# crimp is shared by the fibres of a tuft (same waves, same plane, small per-fibre jitter): that is what makes the real
# locks read as separate wavy staples instead of an even fuzz
coh = np.where(flyaway, 0.0, 0.85)[:, None]
fa1 = np.cross(D0, coh * la1[lid] + (1 - coh) * rng.normal(size=(n, 3)) + 0.25 * rng.normal(size=(n, 3)))
fa1 /= np.linalg.norm(fa1, axis=1, keepdims=True)
fa2 = np.cross(D0, fa1)
lcf = rng.uniform(4.5, 7.0, nl); lcp = rng.random(nl) * 6.283
ffreq = lcf[lid] * (1 + 0.06 * rng.normal(size=n)); fph = lcp[lid] + 0.5 * rng.normal(size=n)
famp = rng.uniform(0.045, 0.07, n) * (1 + 1.0 * flyaway)
pts = np.zeros((n, K, 3), np.float32)
for k, sk in enumerate(s):
    # own path: root + direction bent by gravity, fibre crimp and growing frizz
    bend = (droop * sk * sk)[:, None] * gravity * 0.6
    own = P + (D0 + bend) * (Lf * sk)[:, None]
    crimp = (np.sin(fph + ffreq * sk * 6.283)[:, None] * fa1 + 0.35 * np.cos(fph + ffreq * sk * 6.283)[:, None] * fa2) * (famp * Lf * min(1.0, sk * 4))[:, None]
    frizz = rng.normal(size=(n, 3)) * ((0.010 - 0.003 * bodyness) * sk * sk)[:, None] * Lf[:, None] * (1 + 2 * flyaway)[:, None]
    own = own + crimp + frizz
    # lock path: shared wavy curve
    lbend = (ldroop * sk * sk)[:, None] * gravity * 0.6
    wave = (np.sin(lph + lfreq * sk * 6.283)[:, None] * la1 + 0.6 * np.cos(lph + lfreq * sk * 6.283)[:, None] * la2) * (lamp * lL * min(1.0, sk * 2.5))[:, None]
    lp = lroot[lid] + (ldir[lid] + lbend[lid]) * (lL[lid] * sk)[:, None] + wave[lid]
    # fibres keep their own root and gather towards the lock path along their length (tips tighter)
    # head: gather mid-length, tips splay out (fluffy); body: staples stay together and taper to soft wisps
    w = (clump * min(1.0, sk * 2.0) * (1 - sk * sk * (0.55 - 0.25 * bodyness)))[:, None]
    lp_own = lp + (P - lroot[lid]) * (1 - sk) + crimp * 0.5
    pts[:, k] = own * (1 - w) + lp_own * w
pts[:, :, 2] = np.maximum(pts[:, :, 2], SILL + 0.0012)
pts[:, :, 0] = np.maximum(pts[:, :, 0], -1.858)          # squashed against the window behind it
# keep fibres out of the snout
for k in range(1, K):
    q = pts[:, k].astype(np.float64)
    inside = snout_dist(q) < 1.04
    if inside.any():
        d = q[inside] - SN_C; d /= np.linalg.norm(d, axis=1, keepdims=True)
        pts[inside, k] = on_snout(d, lift=0.0006)

def make_curves(name, points, radius_root, radius_tip, attrs, material):
    cnt_, kk = points.shape[0], points.shape[1]
    hc = bpy.data.hair_curves.new(name)
    hc.add_curves([kk] * cnt_)
    hc.position_data.foreach_set('vector', points.reshape(-1).astype(np.float32))
    rad = np.linspace(radius_root, radius_tip, kk)[None, :].repeat(cnt_, 0).reshape(-1).astype(np.float32)
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

fm = bpy.data.materials.new('Llama v6 / alpaca fleece'); fm.use_nodes = True
nt = fm.node_tree; nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputMaterial')
a_col = nt.nodes.new('ShaderNodeAttribute'); a_col.attribute_name = 'fcol'; a_col.attribute_type = 'GEOMETRY'
FLEECE_MODEL = 'FIBRE'
if FLEECE_MODEL == 'HAIR':
    hb = nt.nodes.new('ShaderNodeBsdfHairPrincipled')
    hb.parametrization = 'COLOR'
    nt.links.new(a_col.outputs['Color'], hb.inputs['Color'])
    for k_, v_ in (('Roughness', 0.30), ('Radial Roughness', 0.40), ('Coat', 0.05), ('IOR', 1.55), ('Random Roughness', 0.25)):
        if k_ in hb.inputs: hb.inputs[k_].default_value = v_
    nt.links.new(hb.outputs['BSDF'], out.inputs['Surface'])
else:
    # matte keratin fibres: mostly diffuse with a soft sheen, a little light passing through the fibre
    pb = nt.nodes.new('ShaderNodeBsdfPrincipled')
    # fibre tips are lighter than the roots (sun-bleached look of the real fleece)
    hi = nt.nodes.new('ShaderNodeHairInfo')
    pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 1.5
    nt.links.new(hi.outputs['Intercept'], pw.inputs[0])
    ml = nt.nodes.new('ShaderNodeMath'); ml.operation = 'MULTIPLY'; ml.inputs[1].default_value = 0.45
    nt.links.new(pw.outputs[0], ml.inputs[0])
    tipc = nt.nodes.new('ShaderNodeMix'); tipc.data_type = 'RGBA'; tipc.inputs['Factor'].default_value = 0.5
    nt.links.new(a_col.outputs['Color'], tipc.inputs['A']); tipc.inputs['B'].default_value = (0.97, 0.96, 0.93, 1)
    mixc = nt.nodes.new('ShaderNodeMix'); mixc.data_type = 'RGBA'
    nt.links.new(ml.outputs[0], mixc.inputs['Factor'])
    nt.links.new(a_col.outputs['Color'], mixc.inputs['A']); nt.links.new(tipc.outputs['Result'], mixc.inputs['B'])
    nt.links.new(mixc.outputs['Result'], pb.inputs['Base Color'])
    pb.inputs['Roughness'].default_value = 0.55
    for k_, v_ in (('Specular IOR Level', 0.35), ('Sheen Weight', 0.25), ('Sheen Roughness', 0.4)):
        if k_ in pb.inputs: pb.inputs[k_].default_value = v_
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent')
    nt.links.new(mixc.outputs['Result'], tr.inputs['Color'])
    mx = nt.nodes.new('ShaderNodeMixShader'); mx.inputs['Fac'].default_value = 0.15
    nt.links.new(pb.outputs['BSDF'], mx.inputs[1]); nt.links.new(tr.outputs['BSDF'], mx.inputs[2])
    nt.links.new(mx.outputs['Shader'], out.inputs['Surface'])
FLEECE_R = (0.000030, 0.000010)
fleece = make_curves('Llama / alpaca fleece', pts, FLEECE_R[0], FLEECE_R[1],
                     {'fcol': (fcol, 'FLOAT_COLOR')}, fm)
print('fleece fibres', n, 'flyaway', int(flyaway.sum()), 'tan>0.5 %.3f' % (tanness > 0.5).mean(), flush=True)

# ------------------------------------------------------------------ felt snout, stitching, halter, cord, pompom
felt_white = mat_principled('Llama v6 / white felt', (0.80, 0.78, 0.74), rough=1.0, sheen=0.3, spec=0.1)
snout = link(bpy.data.objects.new('Llama / felt snout', superellipsoid_mesh('snout', SN_C, SN_H, SN_E)))
snout.data.materials.append(felt_white)

# needle-felt fuzz: short fine fibres standing off the snout surface
nf = int(25000 * max(QUALITY, 0.3))
fd = rng.normal(size=(nf, 3)); fd /= np.linalg.norm(fd, axis=1, keepdims=True)
fd = fd[(fd[:, 0] > -0.75)]
froot = on_snout(fd, lift=0.0)
fnrm = froot - SN_C; fnrm /= np.linalg.norm(fnrm, axis=1, keepdims=True)
fdir = fnrm + rng.normal(size=fnrm.shape) * 0.9; fdir /= np.linalg.norm(fdir, axis=1, keepdims=True)
flen = rng.uniform(0.0006, 0.0022, len(froot))
fpts = np.stack([froot + fdir * (flen * t)[:, None] + rng.normal(size=froot.shape) * 0.00015 * t for t in np.linspace(0, 1, 4)], 1)
fz = mat_principled('Llama v6 / felt fuzz', (0.80, 0.78, 0.74), rough=1.0, sheen=0.5, spec=0.1)
make_curves('Llama / snout felt fuzz', fpts, 0.000012, 0.000006, {}, fz)

def thread(name, pts3, radius, material):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = radius; cu.bevel_resolution = 3; cu.use_fill_caps = True
    sp = cu.splines.new('POLY'); sp.points.add(len(pts3) - 1)
    for i, p in enumerate(pts3):
        sp.points[i].co = (*p, 1)
    cu.materials.append(material)
    return link(bpy.data.objects.new(name, cu))

black_thread = mat_principled('Llama v6 / black thread', (0.012, 0.012, 0.012), rough=0.7, sheen=0.3)
ts = np.linspace(0, 1, 24)
# along the top ridge from just in front of the halter to the front edge, then down the front (the "nose" line)
top = on_snout([np.array([-0.45, 0, 1.0]) * (1 - t) + np.array([0.75, 0, 1.0]) * t for t in ts])
front = on_snout([np.array([1.0, 0, 0.75]) * (1 - t) + np.array([1.0, 0, -0.30]) * t for t in ts])
thread('Llama / stitch nose', np.concatenate([top, front[1:]]), 0.00055, black_thread)
for sgn in (1, -1):
    # mouth line: from the bottom of the nose line round the front corner and back along the side
    mouth = on_snout([np.array([1.0, 0, -0.30]) * (1 - t) + np.array([-0.05, 1.0 * sgn, -0.32]) * t for t in ts])
    thread('Llama / stitch mouth %d' % sgn, mouth, 0.0005, black_thread)

cols = {'red': (0.38, 0.015, 0.02), 'yellow': (0.62, 0.30, 0.02), 'blue': (0.015, 0.025, 0.16), 'black': (0.02, 0.02, 0.025)}
ymats = {k: mat_principled('Llama v6 / yarn ' + k, c, rough=0.85, sheen=0.1) for k, c in cols.items()}
for i, k in enumerate(['red', 'yellow', 'blue', 'black']):
    xr = HALTER_X - i * 0.0011
    ang = np.linspace(0, 2 * math.pi, 64)
    d = np.stack([np.zeros_like(ang), np.cos(ang), np.sin(ang)], 1)
    # project the ring to x = xr: find the cross-section radius of the snout at that x
    q = (xr - SN_C[0]) / SN_H[0]
    sx = max(1e-3, 1 - abs(q) ** (2 / SN_E[0])) ** (SN_E[0] / 2)
    ring = []
    for t in ang:
        c, s_ = math.cos(t), math.sin(t)
        # superellipse cross-section
        ry = SN_H[1] * sx * abs(c) ** SN_E[1] * np.sign(c); rz = SN_H[2] * sx * abs(s_) ** SN_E[2] * np.sign(s_)
        nrm = np.array([0, ry, rz]); nl_ = np.linalg.norm(nrm) + 1e-9
        ring.append((xr, SN_C[1] + ry + 0.0010 * ry / nl_, SN_C[2] + rz + 0.0010 * rz / nl_))
    thread('Llama / halter %s' % k, ring, 0.00058, ymats[k])

POM_R = 0.0135
POM_C = np.array([SN_C[0] - 0.002, Y0 + 0.005, SN_C[2] - 0.033])
cord_top = np.array([HALTER_X - 0.002, Y0, SN_C[2] - SN_H[2] - 0.0006])
cord_bot = POM_C + np.array([-0.002, 0, POM_R * 0.85])
for i, k in enumerate(['red', 'yellow', 'blue']):
    pts3 = []
    for t in np.linspace(0, 1, 70):
        cpt = cord_top * (1 - t) + cord_bot * t + np.array([0.007 * math.sin(t * math.pi), 0, 0])
        th = t * 16 * math.pi + i * 2.094
        pts3.append(cpt + 0.0009 * np.array([0, math.cos(th), 0]) + 0.0009 * np.array([math.sin(th), 0, 0]))
    thread('Llama / cord %s' % k, pts3, 0.0005, ymats[k])
bm = bmesh.new(); ellipsoid_bm(bm, POM_C, (POM_R * 0.55,) * 3, 24, 12)
me = bpy.data.meshes.new('pompom core'); bm.to_mesh(me); bm.free()
link(bpy.data.objects.new('Llama / pompom core', me)).data.materials.append(ymats['blue'])
npom = int(2600 * max(QUALITY, 0.4))
d = rng.normal(size=(npom, 3)); d /= np.linalg.norm(d, axis=1, keepdims=True)
# yarn bundles: neighbouring ends share a colour, blocks like the real one (red on top, navy, mustard underneath)
hb_ = d[:, 2] + 0.55 * vnoise(d, 2.2, 21)
colid = np.where(hb_ > 0.30, 0, np.where(hb_ > -0.25, 1, 2))
blob = vnoise(d, 3.0, 23) > 0.62
colid[blob] = (colid[blob] + 1) % 3
palette = np.array([(0.50, 0.015, 0.018), (0.012, 0.024, 0.15), (0.72, 0.38, 0.02)])   # saturated red, navy, mustard
pc = palette[colid] * rng.uniform(0.85, 1.1, (npom, 1))
Kp = 6
lens = POM_R * rng.uniform(0.85, 1.05, npom)
pp = np.zeros((npom, Kp, 3))
jit = rng.normal(size=(npom, 3)) * 0.22
curl = rng.normal(size=(npom, 3)) * 0.0012
for k, sk in enumerate(np.linspace(0, 1, Kp)):
    dd = d + jit * sk * sk; dd /= np.linalg.norm(dd, axis=1, keepdims=True)
    pp[:, k] = POM_C + dd * (lens * (0.15 + 0.85 * sk))[:, None] + curl * math.sin(sk * 3.0)
ym = bpy.data.materials.new('Llama v6 / pompom yarn'); ym.use_nodes = True
b = ym.node_tree.nodes.get('Principled BSDF')
ca = ym.node_tree.nodes.new('ShaderNodeAttribute'); ca.attribute_name = 'col'; ca.attribute_type = 'GEOMETRY'
ym.node_tree.links.new(ca.outputs['Color'], b.inputs['Base Color'])
b.inputs['Roughness'].default_value = 0.85
if 'Sheen Weight' in b.inputs: b.inputs['Sheen Weight'].default_value = 0.0
make_curves('Llama / pompom yarn', pp, 0.00100, 0.00085, {'col': (np.concatenate([pc, np.ones((npom, 1))], 1), 'FLOAT_COLOR')}, ym)

# ------------------------------------------------------------------ eyes (right behind the halter) and ears
eye_ring = mat_principled('Llama v6 / tan felt eye ring', (0.30, 0.19, 0.11), rough=0.95, sheen=0.3)
eye_dark = mat_principled('Llama v6 / grey felt eye', (0.055, 0.055, 0.06), rough=0.95, sheen=0.3)
for sgn, EC in ((1, EYE_L), (-1, EYE_R)):
    nrm = np.array([0.30, 0.95 * sgn, 0.12]); nrm /= np.linalg.norm(nrm)
    for rad, depth, m in ((0.0046, 0.0016, eye_ring), (0.0031, 0.0024, eye_dark)):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=28, radius1=rad, radius2=rad * 0.85, depth=depth)
        me = bpy.data.meshes.new('eye'); bm.to_mesh(me); bm.free()
        for p in me.polygons: p.use_smooth = True
        ob = link(bpy.data.objects.new('Llama / felt eye', me)); me.materials.append(m)
        rot = Vector(nrm.tolist()).to_track_quat('Z', 'Y').to_matrix().to_4x4()
        ob.matrix_world = Matrix.Translation(Vector((EC + nrm * depth * 0.5).tolist())) @ rot
ear_mat = mat_principled('Llama v6 / dark grey felt ear', (0.11, 0.105, 0.105), rough=1.0, sheen=0.6, spec=0.05)
for sgn, EB in ((1, EAR_L), (-1, EAR_R)):
    bm = bmesh.new()
    pts2 = [(-0.0085, 0.0), (0.0085, 0.0), (0.0086, 0.010), (0.0070, 0.019), (0.0038, 0.025), (-0.0038, 0.025), (-0.0070, 0.019), (-0.0086, 0.010)]
    vs = [bm.verts.new((x, -0.0015 + 0.002 * (1 - (x / 0.009) ** 2), y)) for x, y in pts2] + [bm.verts.new((x, 0.0015 + 0.002 * (1 - (x / 0.009) ** 2), y)) for x, y in pts2]
    m8 = len(pts2)
    bm.faces.new(vs[:m8]); bm.faces.new(list(reversed(vs[m8:])))
    for i in range(m8):
        j = (i + 1) % m8; bm.faces.new([vs[i], vs[j], vs[m8 + j], vs[m8 + i]])
    me = bpy.data.meshes.new('ear'); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    ob = link(bpy.data.objects.new('Llama / felt ear', me)); me.materials.append(ear_mat)
    sub = ob.modifiers.new('sub', 'SUBSURF'); sub.levels = 3; sub.render_levels = 3
    nE = np.array([0.80, 0.55 * sgn, 0.10]); nE /= np.linalg.norm(nE)
    upE = np.array([-0.30, 0.30 * sgn, 1.0]); upE -= (upE @ nE) * nE; upE /= np.linalg.norm(upE)
    wE = np.cross(upE, nE)
    M = Matrix.Identity(4)
    for r_ in range(3):   # smaller, rounder ears that just peek out of the fleece, like the real ones
        M[r_][0], M[r_][1], M[r_][2], M[r_][3] = 0.85 * wE[r_], nE[r_], 0.72 * upE[r_], EB[r_] - 0.002 * upE[r_]
    ob.matrix_world = M
    # felt fuzz on the ear
    ne = int(6000 * max(QUALITY, 0.3))
    u = rng.uniform(-1, 1, ne); h = rng.uniform(0.0, 1.0, ne) ** 0.8
    half = 0.0085 * (1 - h) + 0.0038 * h
    loc = np.stack([u * half, rng.choice([-0.0015, 0.0015], ne) + 0.002 * (1 - u ** 2), h * 0.025], 1)
    Mw = np.array(M)
    roots = (Mw[:3, :3] @ loc.T).T + Mw[:3, 3]
    nloc = np.stack([np.zeros(ne), np.sign(loc[:, 1]), np.zeros(ne)], 1)
    nw = (Mw[:3, :3] @ nloc.T).T
    dirs = nw + rng.normal(size=(ne, 3)) * 0.8; dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    fl = rng.uniform(0.0006, 0.0018, ne)
    epts = np.stack([roots + dirs * (fl * t)[:, None] for t in np.linspace(0, 1, 3)], 1)
    make_curves('Llama / ear felt fuzz %d' % sgn, epts, 0.000014, 0.000007, {}, ear_mat)

# ------------------------------------------------------------------ panda fridge magnet ("Framed art")
back_ = bpy.data.objects.get('Framed art / backing')
pic = bpy.data.objects.get('Framed art / photographed picture')
if back_ and pic:
    H = 0.128; Wm = H * 0.445; Tm = 0.009
    loc = back_.matrix_world.translation.copy()
    base_z = min((back_.matrix_world @ Vector(v)).z for v in back_.bound_box)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    me = bpy.data.meshes.new('magnet frame'); bm.to_mesh(me); bm.free()
    frame = link(bpy.data.objects.new('Framed art / wooden magnet frame', me))
    frame.matrix_world = Matrix.Translation(Vector((loc.x, loc.y, base_z + H / 2))) @ Matrix.Diagonal(Vector((Tm, Wm, H, 1)))
    bev = frame.modifiers.new('bevel', 'BEVEL'); bev.width = 0.0009; bev.segments = 2
    for m in back_.data.materials:
        frame.data.materials.append(m)
    img = bpy.data.images.load(MAGNET_TEX); img.pack()
    fm2 = bpy.data.materials.new('Framed art / panda magnet photo'); fm2.use_nodes = True
    bsdf = fm2.node_tree.nodes.get('Principled BSDF')
    tex = fm2.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = img
    fm2.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.35
    me = bpy.data.meshes.new('magnet face')
    xf = loc.x + Tm / 2 + 0.0004
    me.from_pydata([(xf, loc.y + Wm / 2, base_z), (xf, loc.y - Wm / 2, base_z), (xf, loc.y - Wm / 2, base_z + H), (xf, loc.y + Wm / 2, base_z + H)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for li, (u, v) in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[li].uv = (u, v)
    me.materials.append(fm2)
    link(bpy.data.objects.new('Framed art / panda magnet face', me))
    bpy.data.objects.remove(back_, do_unlink=True); bpy.data.objects.remove(pic, do_unlink=True)
    print('magnet rebuilt', flush=True)

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=False)
print('SAVED', OUT_BLEND, flush=True)
