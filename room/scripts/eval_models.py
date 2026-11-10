# Compare trained models on the same held-out views (every 50th of the full view set), with panorama compositing.
import sys, os, json, math, numpy as np, torch, torch.nn.functional as F
from PIL import Image
from gsplat import rasterization
import OpenEXR
data = '/work/out/main'
cfg = json.load(open(f'{data}/views.json'))
W, H = cfg['width'], cfg['height']
views = [v for v in cfg['views'] if os.path.exists(f"{data}/{v['name']}.png")][::50]
pc = json.load(open('/work/scripts/pano_cfg.json'))
pano = torch.from_numpy(np.asarray(Image.open('/work/out/pano/pano.png').convert('RGB')).copy()).cuda().permute(2, 0, 1)[None].float() / 255
P0 = torch.tensor(pc['center']).cuda(); R = pc['radius']
a = math.radians(pc['lon_half_deg']); la0, la1 = math.radians(pc['lat_min_deg']), math.radians(pc['lat_max_deg'])
fwd = torch.tensor([-1.0, 0, 0]).cuda(); left = torch.tensor([0, -1.0, 0]).cuda(); upv = torch.tensor([0, 0, 1.0]).cuda()
yy, xx = torch.meshgrid(torch.arange(H).cuda() + 0.5, torch.arange(W).cuda() + 0.5, indexing='ij')
def rd(p):
    ch = OpenEXR.File(p).channels(); a_ = np.asarray(list(ch.values())[0].pixels, np.float32); return a_[..., 0] if a_.ndim == 3 else a_
models = {n: {k: v.cuda() for k, v in torch.load(f'/work/out/{n}/params.pt').items()} for n in sys.argv[1:]}
res = {n: [] for n in models}
for j, v in enumerate(views):
    gt = torch.from_numpy(np.asarray(Image.open(f"{data}/{v['name']}.png").convert('RGB')).copy()).cuda().float() / 255
    glass = torch.from_numpy(rd(f"{data}/index_%04d.exr" % v['idx']) > 6.5).cuda()
    fx = (W / 2) / math.tan(v['fov_x'] / 2)
    K = torch.tensor([[fx, 0, W / 2], [0, fx, H / 2], [0, 0, 1]]).float().cuda()
    c2w = torch.tensor(np.array(v['c2w']) @ np.diag([1, -1, -1, 1])).float().cuda()
    dc = torch.stack([(xx - W / 2) / fx, (yy - H / 2) / fx, torch.ones_like(xx)], -1)
    d = dc @ c2w[:3, :3].T; d = d / d.norm(dim=-1, keepdim=True)
    C = c2w[:3, 3]; oc = C - P0; b = (d * oc).sum(-1); c = (oc * oc).sum() - R * R
    q = (C + d * (-b + torch.sqrt(b * b - c))[..., None] - P0) / R
    phi = torch.atan2((q * left).sum(-1), (q * fwd).sum(-1)); lat = torch.asin((q * upv).sum(-1).clamp(-1, 1))
    grid = torch.stack([2 * (a - phi) / (2 * a) - 1, 1 - 2 * (lat - la0) / (la1 - la0)], -1)[None]
    bg = F.grid_sample(pano, grid, align_corners=False)[0].permute(1, 2, 0)
    bg = torch.where(glass[..., None], bg, torch.zeros(1).cuda())
    vm = torch.linalg.inv(c2w)[None]
    crops = []
    for n, P in models.items():
        with torch.no_grad():
            out, al, _ = rasterization(P['means'], F.normalize(P['quats'], dim=-1), torch.exp(P['scales']), torch.sigmoid(P['opacities']),
                                       torch.cat([P['sh0'], P['shN']], 1), vm, K[None], W, H, sh_degree=3, rasterize_mode='antialiased')
        pred = (out[0] + (1 - al[0]) * bg).clamp(0, 1)
        mse = F.mse_loss(pred, gt).item(); res[n].append(-10 * math.log10(mse))
        crops.append(pred)
    if j < 4:
        Image.fromarray((torch.cat([gt] + crops, 1) * 255).byte().cpu().numpy()).save(f'/work/out/evalcmp_{j}.jpg', quality=92)
for n in res:
    print('MODEL', n, 'psnr %.2f' % np.mean(res[n]), 'n=%d' % len(models[n]['means']), flush=True)
