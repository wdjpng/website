# ply_sh.py in.ply out.ply degree : drop higher SH bands from an INRIA-layout 3DGS PLY
import sys, numpy as np
src, dst, deg = sys.argv[1], sys.argv[2], int(sys.argv[3])
with open(src, 'rb') as f:
    header = b''
    while True:
        line = f.readline(); header += line
        if line.strip() == b'end_header': break
    props = [l.split()[-1].decode() for l in header.split(b'\n') if l.startswith(b'property')]
    n = int([l for l in header.split(b'\n') if l.startswith(b'element vertex')][0].split()[-1])
    data = np.frombuffer(f.read(), np.float32).reshape(n, len(props))
rest = [p for p in props if p.startswith('f_rest_')]
per = len(rest) // 3
keep_per = (deg + 1) ** 2 - 1
cols, names = [], []
ri = 0
for p in props:
    if p.startswith('f_rest_'):
        continue
    cols.append(props.index(p)); names.append(p)
    if p == 'f_dc_2':
        for c in range(3):
            for k in range(keep_per):
                cols.append(props.index('f_rest_%d' % (c * per + k))); names.append('f_rest_%d' % ri); ri += 1
out = np.ascontiguousarray(data[:, cols])
with open(dst, 'wb') as f:
    f.write(('ply\nformat binary_little_endian 1.0\nelement vertex %d\n' % n).encode())
    for nm in names: f.write(('property float %s\n' % nm).encode())
    f.write(b'end_header\n'); f.write(out.tobytes())
print('wrote', dst, n, 'props', len(names))
