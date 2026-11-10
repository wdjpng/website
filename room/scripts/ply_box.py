# ply_box.py in.ply out.ply x0 y0 z0 x1 y1 z1 : keep gaussians whose centre lies in the box
import sys, numpy as np
src, dst = sys.argv[1], sys.argv[2]
lo = np.array([float(v) for v in sys.argv[3:6]]); hi = np.array([float(v) for v in sys.argv[6:9]])
with open(src, 'rb') as f:
    header = b''
    while True:
        line = f.readline(); header += line
        if line.strip() == b'end_header': break
    props = [l.split()[-1].decode() for l in header.split(b'\n') if l.startswith(b'property')]
    n = int([l for l in header.split(b'\n') if l.startswith(b'element vertex')][0].split()[-1])
    data = np.frombuffer(f.read(), np.float32).reshape(n, len(props))
xyz = data[:, [props.index('x'), props.index('y'), props.index('z')]]
keep = np.all((xyz >= lo) & (xyz <= hi), 1)
out = data[keep]
header = header.replace(b'element vertex %d' % n, b'element vertex %d' % len(out))
with open(dst, 'wb') as f:
    f.write(header); f.write(out.tobytes())
print('kept', len(out), 'of', n)
