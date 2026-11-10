# blotch2.py gt.png render.png [render2 ...] --box=x0,y0,x1,y1 : band-passed difference to the ground truth (8-bit levels)
import sys, numpy as np, cv2
args = [a for a in sys.argv[1:] if not a.startswith('--')]
box = [int(v) for v in [a for a in sys.argv[1:] if a.startswith('--box=')][0][6:].split(',')]
gt = cv2.imread(args[0]).astype(np.float32)
def band(im):
    return cv2.GaussianBlur(im, (0, 0), 2.5) - cv2.GaussianBlur(im, (0, 0), 30)
x0, y0, x1, y1 = box
for p in args[1:]:
    im = cv2.imread(p).astype(np.float32)
    if im.shape[:2] != gt.shape[:2]: im = cv2.resize(im, (gt.shape[1], gt.shape[0]), interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(gt, cv2.COLOR_BGR2GRAY); r = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    (dx, dy), _ = cv2.phaseCorrelate(g[y0:y1, x0:x1], r[y0:y1, x0:x1])
    d = band(im)[y0:y1, x0:x1] - band(gt)[y0:y1, x0:x1]
    d = d[40:-40, 40:-40]
    mean_off = (im[y0:y1, x0:x1] - gt[y0:y1, x0:x1]).mean(axis=(0, 1))
    print('%-34s shift (%.1f,%.1f)px  blotch-vs-gt %.2f  mean offset BGR %s' % (p, dx, dy, d.std(), np.round(mean_off, 1)))
