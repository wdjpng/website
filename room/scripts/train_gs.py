# Train 3D Gaussian splats on Cycles renders with known cameras (Blender convention), using gsplat.
import argparse, json, math, os, time, glob, random
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

p = argparse.ArgumentParser()
p.add_argument('--data', nargs='+', required=True, help='render dirs containing views.json + pngs + depth exrs')
p.add_argument('--out', required=True)
p.add_argument('--iters', type=int, default=30000)
p.add_argument('--cap', type=int, default=1_500_000)
p.add_argument('--sh', type=int, default=3)
p.add_argument('--depth_w', type=float, default=0.05)
p.add_argument('--init_pts', type=int, default=600_000)
p.add_argument('--scale_down', type=int, default=1)
p.add_argument('--batch', type=int, default=1)
p.add_argument('--eval_every', type=int, default=5000)
p.add_argument('--holdout', type=int, default=50, help='every Nth view held out for eval')
p.add_argument('--strategy', default='mcmc')
p.add_argument('--seed', type=int, default=0)
p.add_argument('--pano', default='', help='exterior panorama png (composited behind the splats)')
p.add_argument('--pano_cfg', default='')
p.add_argument('--max_views', type=int, default=0)
p.add_argument('--scene_scale', type=float, default=2.0)
p.add_argument('--depth_mode', default='inv', choices=['inv', 'log'])
p.add_argument('--alpha_w', type=float, default=0.0, help='push accumulated opacity to 1 on non-glass pixels (solid surfaces)')
p.add_argument('--refine_stop', type=float, default=0.8, help='fraction of iterations after which MCMC stops relocating/adding')
p.add_argument('--opa_reg', type=float, default=0.01)
p.add_argument('--scale_reg', type=float, default=0.01)
p.add_argument('--sh_reg', type=float, default=0.0, help='L2 on higher SH bands (less view-dependent shimmer)')
p.add_argument('--rgba', type=float, default=0.0, help='object-only RGBA renders: weight of the alpha L1 loss (rgb is premultiplied over black)')
p.add_argument('--init_scale', type=float, default=1.2)
p.add_argument('--lr_anneal', type=float, default=1.0, help='from this fraction of training on, decay all non-position learning rates exponentially to --lr_final x')
p.add_argument('--lr_final', type=float, default=0.1)
p.add_argument('--noise_stop', type=float, default=1.0, help='fraction of iterations after which MCMC position noise is switched off')
p.add_argument('--reg_stop', type=float, default=1.0, help='fraction of iterations after which the MCMC opacity/scale regularisers are switched off')
p.add_argument('--box', default='-1.95,-0.95,-0.06,1.95,2.90,2.95', help='keep gaussians inside this box (blender coords)')
args = p.parse_args()
torch.manual_seed(args.seed); np.random.seed(args.seed); random.seed(args.seed)
dev = 'cuda'
os.makedirs(args.out, exist_ok=True)
from gsplat import rasterization
from gsplat.strategy import MCMCStrategy, DefaultStrategy

import OpenEXR

def read_exr_channel(path):
    f = OpenEXR.File(path)
    ch = f.channels()
    k = list(ch.keys())[0]
    a = np.asarray(ch[k].pixels, dtype=np.float32)
    return a if a.ndim == 2 else a[..., 0]

# ---------------- data ----------------
cams = []
for d in args.data:
    cfg = json.load(open(os.path.join(d, 'views.json')))
    W, H = cfg['width'], cfg['height']
    for v in cfg['views']:
        png = os.path.join(d, v['name'] + '.png')
        dep = os.path.join(d, 'depth_%04d.exr' % v['idx'])
        idx = os.path.join(d, 'index_%04d.exr' % v['idx'])
        if not (os.path.exists(png) and os.path.exists(dep)):
            continue
        cams.append(dict(png=png, dep=dep, idx=idx, c2w=np.array(v['c2w'], np.float64), fov_x=v['fov_x'], W=W, H=H, name=v['name']))
if args.max_views:
    cams = cams[:args.max_views]
print('views found', len(cams), flush=True)
ds = args.scale_down
imgs, deps, Ks, viewmats, glass, alphas = [], [], [], [], [], []
t0 = time.time()
import time as _time
for c in list(cams):
    try:
        if _time.time() - os.path.getmtime(c['png']) < 20:
            raise IOError('too fresh')
        im = Image.open(c['png']).convert('RGBA' if args.rgba > 0 else 'RGB')
        im.load()
        _ = read_exr_channel(c['dep'])
    except Exception as e:
        print('skip', c['name'], e, flush=True)
        cams.remove(c)
        continue
    W, H = c['W'] // ds, c['H'] // ds
    if ds > 1:
        im = im.resize((W, H), Image.LANCZOS)
    a_np = np.asarray(im).copy()
    if args.rgba > 0:
        al = a_np[..., 3:4].astype(np.float32) / 255
        alphas.append(torch.from_numpy(a_np[..., 3].copy()))
        a_np = np.round(a_np[..., :3].astype(np.float32) * al).astype(np.uint8)   # premultiplied over black
    imgs.append(torch.from_numpy(a_np))
    dz = read_exr_channel(c['dep'])
    if args.rgba > 0:
        dz = np.where(np.asarray(im)[..., 3] > 250, dz, 0.0)   # depth only where the object fully covers the pixel
    gm = np.zeros(dz.shape, bool)
    if os.path.exists(c['idx']):
        ix = read_exr_channel(c['idx'])
        gm = ix > 6.5
        dz = np.where(gm, 0.0, dz)  # glass: no depth supervision
    if ds > 1:
        gm = gm[::ds, ::ds]
    glass.append(torch.from_numpy(gm))
    if ds > 1:
        dz = dz[::ds, ::ds]
    deps.append(torch.from_numpy(dz.astype(np.float16)))
    fx = (W / 2) / math.tan(c['fov_x'] / 2)
    K = np.array([[fx, 0, W / 2], [0, fx, H / 2], [0, 0, 1]], np.float32)
    Ks.append(K)
    # blender c2w (-Z fwd, +Y up) -> opencv (+Z fwd, -Y up)
    c2w = c['c2w'] @ np.diag([1, -1, -1, 1])
    viewmats.append(np.linalg.inv(c2w).astype(np.float32))
print('loaded in %.0fs' % (time.time() - t0), flush=True)
N = len(imgs)
H, W = imgs[0].shape[:2]
imgs_t = torch.stack(imgs).to(dev)            # uint8 N,H,W,3
deps_t = torch.stack(deps).to(dev)            # f16 N,H,W
glass_t = torch.stack(glass).to(dev)          # bool N,H,W: pixel sees the window glass
alpha_t = torch.stack(alphas).to(dev) if alphas else None   # uint8 N,H,W (rgba mode)
Ks_t = torch.from_numpy(np.stack(Ks)).to(dev)
vm_t = torch.from_numpy(np.stack(viewmats)).to(dev)
# ---------------- exterior panorama background ----------------
bg_t = None
if args.pano:
    pc = json.load(open(args.pano_cfg))
    pano = torch.from_numpy(np.asarray(Image.open(args.pano).convert('RGB')).copy()).to(dev).permute(2, 0, 1)[None].float() / 255
    P0 = torch.tensor(pc['center'], device=dev, dtype=torch.float32)
    R = float(pc.get('radius', 50.0))
    a = math.radians(pc['lon_half_deg']); la0, la1 = math.radians(pc['lat_min_deg']), math.radians(pc['lat_max_deg'])
    fwd = torch.tensor([-1.0, 0, 0], device=dev); left = torch.tensor([0, -1.0, 0], device=dev); upv = torch.tensor([0, 0, 1.0], device=dev)
    yy, xx = torch.meshgrid(torch.arange(H, device=dev) + 0.5, torch.arange(W, device=dev) + 0.5, indexing='ij')
    bgs = []
    for i in range(N):
        K = Ks_t[i]; c2w = torch.linalg.inv(vm_t[i])
        dc = torch.stack([(xx - K[0, 2]) / K[0, 0], (yy - K[1, 2]) / K[1, 1], torch.ones_like(xx)], -1)
        d = dc @ c2w[:3, :3].T
        d = d / d.norm(dim=-1, keepdim=True)
        C = c2w[:3, 3]
        oc = C - P0
        b = (d * oc).sum(-1); c = (oc * oc).sum() - R * R
        t = -b + torch.sqrt(b * b - c)
        q = (C + d * t[..., None] - P0) / R
        phi = torch.atan2((q * left).sum(-1), (q * fwd).sum(-1))
        lat = torch.asin((q * upv).sum(-1).clamp(-1, 1))
        u = (a - phi) / (2 * a); v = (lat - la0) / (la1 - la0)
        grid = torch.stack([2 * u - 1, 1 - 2 * v], -1)[None]
        bg = F.grid_sample(pano, grid, mode='bilinear', padding_mode='border', align_corners=False)[0].permute(1, 2, 0)
        bgs.append((bg * 255).round().byte())
    bg_t = torch.stack(bgs)
    print('backgrounds ready', bg_t.shape, flush=True)
    Image.fromarray(torch.cat([imgs_t[0], bg_t[0]], 1).cpu().numpy()).save(os.path.join(args.out, 'bg_check.jpg'))

box = torch.tensor([float(v) for v in args.box.split(',')], device=dev)
box_lo, box_hi = box[:3], box[3:]

eval_ids = list(range(0, N, args.holdout)) if args.holdout > 0 else []
train_ids = [i for i in range(N) if i not in set(eval_ids)]
print('train', len(train_ids), 'eval', len(eval_ids), 'res', W, H, flush=True)

# ---------------- determine depth convention ----------------
# Cycles depth may be planar (z) or radial; detect using pixel rays: compare a flat wall is unreliable, so
# trust config flag if present; default planar.
DEPTH_RADIAL = os.environ.get('DEPTH_RADIAL', '0') == '1'
ys, xs = torch.meshgrid(torch.arange(H, device=dev), torch.arange(W, device=dev), indexing='ij')

def backproject(i, stride):
    K = Ks_t[i]; c2w = torch.linalg.inv(vm_t[i])
    yy = ys[::stride, ::stride] + 0.5; xx = xs[::stride, ::stride] + 0.5
    d = deps_t[i][::stride, ::stride].float()
    dirs = torch.stack([(xx - K[0, 2]) / K[0, 0], (yy - K[1, 2]) / K[1, 1], torch.ones_like(xx)], -1)
    if DEPTH_RADIAL:
        z = d / dirs.norm(dim=-1)
    else:
        z = d
    pts_c = dirs * z[..., None]
    pts = pts_c @ c2w[:3, :3].T + c2w[:3, 3]
    col = imgs_t[i][::stride, ::stride].float() / 255
    valid = (d > 0.01) & (d < 1e4)
    # footprint size of a pixel at this depth
    foot = z * stride / K[0, 0]
    return pts[valid], col[valid], foot[valid]

# ---------------- init from depth ----------------
P, C, S = [], [], []
per_view = max(1, args.init_pts * 3 // max(1, len(train_ids)))
for i in train_ids:
    pts, col, foot = backproject(i, 4)
    if len(pts) > per_view:
        sel = torch.randperm(len(pts), device=dev)[:per_view]
        pts, col, foot = pts[sel], col[sel], foot[sel]
    P.append(pts); C.append(col); S.append(foot)
P = torch.cat(P); C = torch.cat(C); S = torch.cat(S)
# voxel dedupe with distance-adaptive voxel size
vox = torch.clamp(S * 1.5, min=0.004)
key = torch.floor(P / vox[:, None]).long()
key = key[:, 0] * 73856093 ^ key[:, 1] * 19349663 ^ key[:, 2] * 83492791 ^ torch.floor(torch.log2(vox) * 4).long() * 2654435761
_, first = np.unique(key.cpu().numpy(), return_index=True)
first = torch.from_numpy(first).to(dev)
P, C, S = P[first], C[first], S[first]
inb = ((P >= box_lo) & (P <= box_hi)).all(-1)
P, C, S = P[inb], C[inb], S[inb]
if len(P) > args.init_pts:
    sel = torch.randperm(len(P), device=dev)[:args.init_pts]
    P, C, S = P[sel], C[sel], S[sel]
print('init points', len(P), flush=True)

def rgb2sh(c):
    return (c - 0.5) / 0.28209479177387814

n = len(P)
nsh = (args.sh + 1) ** 2
params = torch.nn.ParameterDict({
    'means': torch.nn.Parameter(P.clone()),
    'scales': torch.nn.Parameter(torch.log(S.clamp(min=1e-4) * args.init_scale)[:, None].repeat(1, 3)),
    'quats': torch.nn.Parameter(F.normalize(torch.randn(n, 4, device=dev), dim=-1)),
    'opacities': torch.nn.Parameter(torch.logit(torch.full((n,), 0.5, device=dev))),
    'sh0': torch.nn.Parameter(rgb2sh(C)[:, None, :].clone()),
    'shN': torch.nn.Parameter(torch.zeros(n, nsh - 1, 3, device=dev)),
}).to(dev)
scene_scale = args.scene_scale
lrs = {'means': 1.6e-4 * scene_scale, 'scales': 5e-3, 'quats': 1e-3, 'opacities': 5e-2, 'sh0': 2.5e-3, 'shN': 2.5e-3 / 20}
optimizers = {k: torch.optim.Adam([{'params': params[k], 'lr': lrs[k], 'name': k}], eps=1e-15, betas=(0.9, 0.999)) for k in params}
means_sched = torch.optim.lr_scheduler.ExponentialLR(optimizers['means'], gamma=0.01 ** (1.0 / args.iters))

if args.strategy == 'mcmc':
    strategy = MCMCStrategy(cap_max=args.cap, refine_start_iter=500, refine_stop_iter=int(args.iters * args.refine_stop), refine_every=100, min_opacity=0.005)
    opa_reg, scale_reg = args.opa_reg, args.scale_reg
else:
    strategy = DefaultStrategy(refine_stop_iter=int(args.iters * 0.6), absgrad=True, grow_grad2d=0.0008, verbose=True)
    opa_reg, scale_reg = 0.0, 0.0
strategy.check_sanity(params, optimizers)
state = strategy.initialize_state(scene_scale=scene_scale) if args.strategy != 'mcmc' else strategy.initialize_state()

# SSIM
def _gauss(ws=11, sigma=1.5):
    g = torch.exp(-((torch.arange(ws) - ws // 2) ** 2) / (2 * sigma ** 2)); g = g / g.sum()
    return (g[:, None] @ g[None, :]).to(dev)
GW = _gauss()[None, None].repeat(3, 1, 1, 1)
def ssim(a, b):  # N,3,H,W
    C1, C2 = 0.01 ** 2, 0.03 ** 2
    mu1 = F.conv2d(a, GW, padding=5, groups=3); mu2 = F.conv2d(b, GW, padding=5, groups=3)
    s1 = F.conv2d(a * a, GW, padding=5, groups=3) - mu1 ** 2
    s2 = F.conv2d(b * b, GW, padding=5, groups=3) - mu2 ** 2
    s12 = F.conv2d(a * b, GW, padding=5, groups=3) - mu1 * mu2
    m = ((2 * mu1 * mu2 + C1) * (2 * s12 + C2)) / ((mu1 ** 2 + mu2 ** 2 + C1) * (s1 + s2 + C2))
    return m.mean()

def render(ids, sh_degree, mode='RGB+ED'):
    colors = torch.cat([params['sh0'], params['shN']], 1)
    out, alpha, info = rasterization(
        means=params['means'], quats=params['quats'], scales=torch.exp(params['scales']),
        opacities=torch.sigmoid(params['opacities']), colors=colors,
        viewmats=vm_t[ids], Ks=Ks_t[ids], width=W, height=H, sh_degree=sh_degree,
        near_plane=0.01, far_plane=1e4, render_mode=mode, packed=False, absgrad=(args.strategy != 'mcmc'),
        rasterize_mode='antialiased')
    return out, alpha, info

def psnr(a, b):
    return -10 * torch.log10(F.mse_loss(a, b))

def _gblur(x, sigma):  # x: 1,C,H,W
    r = int(3 * sigma) + 1
    t = torch.arange(-r, r + 1, device=x.device, dtype=x.dtype)
    k = torch.exp(-t * t / (2 * sigma * sigma)); k = k / k.sum()
    C = x.shape[1]
    x = F.conv2d(F.pad(x, (r, r, 0, 0), mode='replicate'), k.view(1, 1, 1, -1).repeat(C, 1, 1, 1), groups=C)
    return F.conv2d(F.pad(x, (0, 0, r, r), mode='replicate'), k.view(1, 1, -1, 1).repeat(C, 1, 1, 1), groups=C)

def flat_blotch(pred, gt):
    # mid-frequency error on flat, untextured areas (walls, ceiling, doors), in 8-bit levels
    p = pred.permute(2, 0, 1)[None]; g = gt.permute(2, 0, 1)[None]
    ds = 2
    p = F.avg_pool2d(p, ds); g = F.avg_pool2d(g, ds)
    bp = _gblur(p, 1.25) - _gblur(p, 15); bg = _gblur(g, 1.25) - _gblur(g, 15)
    m1 = F.avg_pool2d(g, 9, 1, 4); m2 = F.avg_pool2d(g * g, 9, 1, 4)
    local_std = (m2 - m1 * m1).clamp(min=0).sqrt().mean(1, keepdim=True)
    flat = (local_std < 1.5 / 255) & (g.mean(1, keepdim=True) > 0.08)
    d = (bp - bg).mean(1, keepdim=True)[flat]
    return (d.std().item() * 255 if d.numel() > 1000 else float('nan')), flat.float().mean().item()

def evaluate(step):
    if not eval_ids:
        return
    ps = []; bl = []
    with torch.no_grad():
        for j, i in enumerate(eval_ids):
            out, al, _ = render([i], args.sh, 'RGB')
            pred = out[0]
            if bg_t is not None:
                pred = pred + (1 - al[0]) * torch.where(glass_t[i][..., None], bg_t[i].float() / 255, torch.zeros(1, device=dev))
            pred = pred.clamp(0, 1)
            gt = imgs_t[i].float() / 255
            ps.append(psnr(pred, gt).item())
            b, fr = flat_blotch(pred, gt)
            if fr > 0.05 and b == b:
                bl.append(b)
            if j < 6:
                Image.fromarray(torch.cat([gt, pred], 1).mul(255).byte().cpu().numpy()).save(os.path.join(args.out, f'eval_{step:06d}_{j}.jpg'), quality=90)
    print(f'EVAL step {step} psnr {np.mean(ps):.2f} flat_blotch {np.mean(bl) if bl else float("nan"):.3f} ({len(bl)} views) n={len(params["means"])}', flush=True)

t0 = time.time()
for step in range(args.iters):
    if args.strategy == 'mcmc' and step == int(args.iters * args.noise_stop):
        strategy.noise_lr = 0.0
        print('position noise off at', step, flush=True)
    if args.lr_anneal < 1.0 and step >= int(args.iters * args.lr_anneal):
        fr = (step - args.iters * args.lr_anneal) / max(1.0, args.iters * (1 - args.lr_anneal))
        for k_, o_ in optimizers.items():
            if k_ != 'means':
                for g_ in o_.param_groups:
                    g_['lr'] = lrs[k_] * (args.lr_final ** fr)
    if args.strategy == 'mcmc' and step == int(args.iters * args.reg_stop):
        opa_reg, scale_reg = 0.0, 0.0
        print('opacity/scale regularisers off at', step, flush=True)
    ids = random.sample(train_ids, args.batch)
    shd = min(args.sh, step // 1000)
    out, alpha, info = render(ids, shd)
    rgb = out[..., :3]; dep = out[..., 3]
    if bg_t is not None:
        # exterior panorama behind the window glass, black elsewhere (the viewer only shows the panorama through a portal)
        bgimg = torch.where(glass_t[ids][..., None], bg_t[ids].float() / 255, torch.zeros(1, device=dev))
        rgb = rgb + (1 - alpha) * bgimg
    gt = imgs_t[ids].float() / 255
    l1 = (rgb - gt).abs().mean()
    ss = ssim(rgb.permute(0, 3, 1, 2), gt.permute(0, 3, 1, 2))
    loss = 0.8 * l1 + 0.2 * (1 - ss)
    if args.depth_w > 0:
        gd = deps_t[ids].float()
        m = (gd > 0.01) & (gd < 8.0)
        if m.any():
            if args.depth_mode == 'log':
                # log-depth L1: scale-free, so close-up views cannot dominate
                loss = loss + args.depth_w * (torch.log(dep[m].clamp(min=0.02)) - torch.log(gd[m])).abs().mean()
            else:
                # inverse-depth L1 (robust for near and far)
                loss = loss + args.depth_w * (1.0 / dep[m].clamp(min=0.05) - 1.0 / gd[m]).abs().mean()
    if alpha_t is not None:
        loss = loss + args.rgba * (alpha[..., 0] - alpha_t[ids].float() / 255).abs().mean()
    if args.alpha_w > 0:
        solid = ~glass_t[ids]
        loss = loss + args.alpha_w * (1 - alpha[..., 0])[solid].mean()
    if args.sh_reg > 0:
        loss = loss + args.sh_reg * (params['shN'] ** 2).mean()
    if args.strategy == 'mcmc':
        loss = loss + opa_reg * torch.sigmoid(params['opacities']).mean() + scale_reg * torch.exp(params['scales']).mean()
    strategy.step_pre_backward(params, optimizers, state, step, info)
    loss.backward()
    for o in optimizers.values():
        o.step(); o.zero_grad(set_to_none=True)
    means_sched.step()
    with torch.no_grad():
        params['means'].data.copy_(torch.max(torch.min(params['means'].data, box_hi), box_lo))
    if args.strategy == 'mcmc':
        strategy.step_post_backward(params, optimizers, state, step, info, lr=means_sched.get_last_lr()[0])
    else:
        strategy.step_post_backward(params, optimizers, state, step, info, packed=False)
    if step % 500 == 0:
        print(f'step {step} loss {loss.item():.4f} l1 {l1.item():.4f} ssim {ss.item():.4f} n={len(params["means"])} {time.time() - t0:.0f}s', flush=True)
    if step > 0 and step % args.eval_every == 0:
        evaluate(step)
evaluate(args.iters)

# ---------------- export PLY (standard 3DGS layout) ----------------
def save_ply(path):
    with torch.no_grad():
        m = params['means'].cpu().numpy(); s = params['scales'].cpu().numpy(); q = F.normalize(params['quats'], dim=-1).cpu().numpy()
        o = params['opacities'].cpu().numpy()[:, None]
        dc = params['sh0'].cpu().numpy().reshape(-1, 3)
        rest = params['shN'].transpose(1, 2).reshape(len(m), -1).cpu().numpy()  # channel-major like INRIA
    n = len(m)
    fields = ['x', 'y', 'z', 'nx', 'ny', 'nz', 'f_dc_0', 'f_dc_1', 'f_dc_2'] + [f'f_rest_{i}' for i in range(rest.shape[1])] + ['opacity', 'scale_0', 'scale_1', 'scale_2', 'rot_0', 'rot_1', 'rot_2', 'rot_3']
    data = np.concatenate([m, np.zeros((n, 3)), dc, rest, o, s, q], 1).astype(np.float32)
    with open(path, 'wb') as f:
        f.write(('ply\nformat binary_little_endian 1.0\nelement vertex %d\n' % n).encode())
        for fl in fields:
            f.write(('property float %s\n' % fl).encode())
        f.write(b'end_header\n')
        f.write(data.tobytes())
    print('saved', path, n, flush=True)
save_ply(os.path.join(args.out, 'splat.ply'))
torch.save({k: v.detach().cpu() for k, v in params.items()}, os.path.join(args.out, 'params.pt'))
print('TRAIN_DONE %.0fs' % (time.time() - t0), flush=True)
