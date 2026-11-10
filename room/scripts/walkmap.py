import numpy as np, cv2, json, base64
d = np.load('work/occ_points.npz')
CELL = 0.02
X0, X1, Y0, Y1 = -1.86, 1.85, -0.84, 2.77   # interior faces (blender XY)
W = int(round((X1 - X0) / CELL)); H = int(round((Y1 - Y0) / CELL))
occ = np.zeros((H, W), np.uint8)   # row = blender y index, col = x index
ignore = ('Architecture', 'Exterior', 'Trim', 'Switch', 'Data outlet', 'Lamp outlet', 'Window outlet', 'Door|')
for k in d.keys():
    top = k.split('>')[-1]
    if top.startswith(ignore) or top == 'Door':
        continue
    p = d[k]
    p = p[(p[:, 2] > 0.06) & (p[:, 2] < 1.95)]
    if len(p) < 3:
        continue
    if p[:, 0].min() < -10 or p[:, 0].max() > 10:
        continue
    ij = np.stack([(p[:, 0] - X0) / CELL, (p[:, 1] - Y0) / CELL], 1)
    hull = cv2.convexHull(ij.astype(np.float32)).astype(np.int32)
    cv2.fillConvexPoly(occ, hull, 1)
free = (1 - occ).astype(np.uint8)
# player radius clearance from walls + furniture
R = 0.20
free[0, :] = free[-1, :] = 0; free[:, 0] = free[:, -1] = 0
k = int(round(R / CELL))
dist = cv2.distanceTransform(free, cv2.DIST_L2, 5) * CELL
walk = (dist >= R).astype(np.uint8)
# keep the largest connected region
n, lab, stats, _ = cv2.connectedComponentsWithStats(walk, 4)
big = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
walk = (lab == big).astype(np.uint8)
print('grid', W, H, 'walkable m2', walk.sum() * CELL * CELL)
np.save('work/walk_blender.npy', walk)
np.save('work/dist_blender.npy', dist)
vis = np.zeros((H, W, 3), np.uint8); vis[occ == 1] = (60, 60, 200); vis[walk == 1] = (80, 200, 80)
cv2.imwrite('work/walkmap_vis.png', cv2.resize(np.flipud(vis), (W * 3, H * 3), interpolation=cv2.INTER_NEAREST))
# three.js coords: X = bx, Z = -by. Grid for three: i along X (same), j along Z: z = -by -> j index from Zmin = -Y1
three = np.flipud(walk)  # row 0 = largest blender y = smallest three z
z0 = -Y1
flat = three.reshape(-1)
runs = []; v = 0; cnt = 0
for b in flat:
    if b == v:
        cnt += 1
        if cnt == 65535:
            runs.append(cnt); runs.append(0); cnt = 0
    else:
        runs.append(cnt); v = b; cnt = 1
runs.append(cnt)
data = base64.b64encode(np.array(runs, '<u2').tobytes()).decode()
json.dump({'origin': [X0, z0], 'cell': CELL, 'width': W, 'height': H, 'data': data}, open('web/public/assets/walkmap.json', 'w'))
print('runs', len(runs))
