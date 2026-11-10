# ply_offset.py in.ply out.ply dx dy dz : translate a 3DGS PLY (binary little endian, float props)
import sys, numpy as np
src, dst = sys.argv[1], sys.argv[2]
off = np.array([float(v) for v in sys.argv[3:6]], np.float32)
with open(src, 'rb') as f:
    header = b''
    while True:
        line = f.readline(); header += line
        if line.strip() == b'end_header': break
    props = [l.split()[-1].decode() for l in header.split(b'\n') if l.startswith(b'property')]
    n = int([l for l in header.split(b'\n') if l.startswith(b'element vertex')][0].split()[-1])
    data = np.frombuffer(f.read(), np.float32).reshape(n, len(props)).copy()
for i, k in enumerate('xyz'):
    data[:, props.index(k)] += off[i]
with open(dst, 'wb') as f:
    f.write(header); f.write(data.tobytes())
print('wrote', dst, n)
