import numpy as np, cv2
from PIL import Image
P0 = np.array([-0.5, 0.3, 1.6]); PPD = 20.48; LATMAX = 75 + 307 / 20.48; W, H = 4096, 3686
def pix_of_point(X, Y, Z):
    dx, dy, dz = X - P0[0], Y - P0[1], Z - P0[2]
    lon = np.degrees(np.arctan2(-dy, -dx)); lat = np.degrees(np.arctan2(dz, np.hypot(dx, dy)))
    return (100 - lon) * PPD - 0.5, (LATMAX - lat) * PPD - 0.5
def dirs():
    c = np.arange(W) + 0.5; r = np.arange(H) + 0.5
    lon = np.radians(100 - c / PPD)[None, :]; lat = np.radians(LATMAX - r / PPD)[:, None]
    return -np.cos(lat) * np.cos(lon), -np.cos(lat) * np.sin(lon), np.sin(lat) * np.ones_like(lon)
def sample_plane_x(img, X0, y0, y1, z0, z1, ppm):
    ys = y0 + (np.arange(int((y1 - y0) * ppm)) + 0.5) / ppm; zs = z1 - (np.arange(int((z1 - z0) * ppm)) + 0.5) / ppm
    Y, Z = np.meshgrid(ys, zs)
    mx, my = pix_of_point(X0, Y, Z)
    return cv2.remap(img, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
