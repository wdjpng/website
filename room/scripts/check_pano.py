import json, math, numpy as np, sys
from PIL import Image
import torch, torch.nn.functional as F
pc = json.load(open('/home/muenzel_lukas/room/scripts/pano_cfg.json'))
d = sys.argv[1]
pano = torch.from_numpy(np.asarray(Image.open(f'{d}/pano.png').convert('RGB')).copy()).permute(2,0,1)[None].float()/255
P0 = torch.tensor(pc['center']); R = float(pc.get('radius', 50.0))
a = math.radians(pc['lon_half_deg']); la0, la1 = math.radians(pc['lat_min_deg']), math.radians(pc['lat_max_deg'])
fwd = torch.tensor([-1.0,0,0]); left = torch.tensor([0,-1.0,0]); upv = torch.tensor([0,0,1.0])
W, H = pc['check_w'], pc['check_h']
for i, v in enumerate(pc['checks']):
    c2w = torch.tensor(v['c2w'], dtype=torch.float32)
    f = (W/2)/math.tan(v['fov_x']/2)
    yy, xx = torch.meshgrid(torch.arange(H)+0.5, torch.arange(W)+0.5, indexing='ij')
    dc = torch.stack([(xx-W/2)/f, -(yy-H/2)/f, -torch.ones_like(xx)], -1)  # blender camera coords
    dd = dc @ c2w[:3,:3].T; dd = dd/dd.norm(dim=-1, keepdim=True)
    C = c2w[:3,3]; oc = C - P0
    b = (dd*oc).sum(-1); c = (oc*oc).sum() - R*R
    t = -b + torch.sqrt(b*b - c)
    q = (C + dd*t[...,None] - P0)/R
    phi = torch.atan2((q*left).sum(-1), (q*fwd).sum(-1)); lat = torch.asin((q*upv).sum(-1).clamp(-1,1))
    u = (a-phi)/(2*a); vv = (lat-la0)/(la1-la0)
    grid = torch.stack([2*u-1, 1-2*vv], -1)[None]
    img = F.grid_sample(pano, grid, mode='bilinear', padding_mode='border', align_corners=False)[0].permute(1,2,0)
    ref = torch.from_numpy(np.asarray(Image.open(f'{d}/check_{i}.png').convert('RGB')).copy()).float()/255
    err = (img-ref).abs().mean().item()
    print('check', i, 'mean abs err', round(err, 4))
    Image.fromarray((torch.cat([ref, img], 1)*255).byte().numpy()).save(f'{d}/cmp_{i}.jpg')
