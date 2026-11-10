# blotch.py img1 [img2 ...] --box x0,y0,x1,y1 : mid-frequency "blotch" energy on a flat wall region
# (std of the image minus a wide blur, after a light blur that removes pixel noise), in 8-bit levels
import sys, numpy as np, cv2
args = [a for a in sys.argv[1:] if not a.startswith('--')]
box = [int(v) for v in [a for a in sys.argv[1:] if a.startswith('--box=')][0][6:].split(',')]
for p in args:
    im = cv2.imread(p).astype(np.float32)
    if im.shape[1] != 1440: im = cv2.resize(im, (1440, 1080), interpolation=cv2.INTER_AREA)
    x0, y0, x1, y1 = box
    r = im[y0:y1, x0:x1]
    fine = cv2.GaussianBlur(r, (0, 0), 3)
    coarse = cv2.GaussianBlur(r, (0, 0), 40)
    band = (fine - coarse)[40:-40, 40:-40]
    print('%-40s blotch %.2f' % (p, band.std()))
