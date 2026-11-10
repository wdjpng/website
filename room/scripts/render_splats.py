# Render trained splats (params.pt) from cameras in a views.json (Blender convention c2w + fov_x).
import argparse, json, math, os
import numpy as np, torch, torch.nn.functional as F
from PIL import Image
from gsplat import rasterization
p = argparse.ArgumentParser()
p.add_argument('--params', required=True)
p.add_argument('--views', required=True, nargs='+')
p.add_argument('--out', required=True)
p.add_argument('--sh', type=int, default=3)
args = p.parse_args()
os.makedirs(args.out, exist_ok=True)
def load_ply(path):
    with open(path, 'rb') as f:
        header = b''
        while True:
            line = f.readline(); header += line
            if line.strip() == b'end_header': break
        props = [l.split()[-1].decode() for l in header.split(b'\n') if l.startswith(b'property')]
        n = int([l for l in header.split(b'\n') if l.startswith(b'element vertex')][0].split()[-1])
        d = np.frombuffer(f.read(), np.float32).reshape(n, len(props))
    col = lambda names: torch.from_numpy(d[:, [props.index(x) for x in names]].copy())
    rest = sorted([x for x in props if x.startswith('f_rest_')], key=lambda x: int(x.split('_')[-1]))
    shN = col(rest).reshape(n, 3, -1).transpose(1, 2) if rest else torch.zeros(n, 0, 3)
    return {'means': col(['x', 'y', 'z']), 'scales': col(['scale_0', 'scale_1', 'scale_2']), 'quats': col(['rot_0', 'rot_1', 'rot_2', 'rot_3']),
            'opacities': col(['opacity'])[:, 0], 'sh0': col(['f_dc_0', 'f_dc_1', 'f_dc_2'])[:, None, :], 'shN': shN}
P = load_ply(args.params) if args.params.endswith('.ply') else torch.load(args.params)
P = {k: v.cuda() for k, v in P.items()}
colors = torch.cat([P['sh0'], P['shN']], 1)
for vf in args.views:
    cfg = json.load(open(vf))
    W, H = cfg['width'], cfg['height']
    for v in cfg['views']:
        fx = (W / 2) / math.tan(v['fov_x'] / 2)
        K = torch.tensor([[fx, 0, W / 2], [0, fx, H / 2], [0, 0, 1]], dtype=torch.float32, device='cuda')[None]
        c2w = np.array(v['c2w']) @ np.diag([1, -1, -1, 1])
        vm = torch.from_numpy(np.linalg.inv(c2w).astype(np.float32)).cuda()[None]
        with torch.no_grad():
            out, _, _ = rasterization(P['means'], F.normalize(P['quats'], dim=-1), torch.exp(P['scales']), torch.sigmoid(P['opacities']), colors,
                                      vm, K, W, H, sh_degree=args.sh, near_plane=0.01, far_plane=1e4, rasterize_mode='antialiased')
        img = out[0].clamp(0, 1).mul(255).byte().cpu().numpy()
        Image.fromarray(img).save(os.path.join(args.out, v['name'] + '.png'))
        print('rendered', v['name'], flush=True)
