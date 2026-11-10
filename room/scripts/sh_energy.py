import sys, torch
for p in sys.argv[1:]:
    P = torch.load(p)
    shN = P['shN']; op = torch.sigmoid(P['opacities'])
    e = (shN ** 2).sum(dim=(1, 2)).sqrt()
    w = op / op.sum()
    print(p, 'n', len(e), 'mean |shN| (opacity-weighted) %.4f' % (e * w).sum().item(), 'median %.4f' % e.median().item())
