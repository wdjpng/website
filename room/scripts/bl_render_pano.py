# Render the view outside the window as a partial equirectangular panorama (exterior only, no glass),
# plus perspective check views. usage: blender -b scene.blend --python bl_render_pano.py -- cfg.json outdir gpu spp
import bpy, sys, json, os, math
from mathutils import Matrix, Vector
argv = sys.argv[sys.argv.index('--') + 1:]
cfg = json.load(open(argv[0])); outdir = argv[1]; gpu_index = int(argv[2]); spp = int(argv[3])
# optional overrides after the 4 positional args, as key=value: lon_half_deg, lat_min_deg, lat_max_deg, pano_w, pano_h,
# checks (0 = skip the perspective check views). e.g. ... -- cfg.json out 0 512 lat_min_deg=-89.99 lat_max_deg=89.99 pano_h=3686 checks=0
do_checks = True
for kv in argv[4:]:
    k, v = kv.split('=', 1)
    if k == 'checks':
        do_checks = v != '0'
    elif k in ('pano_w', 'pano_h'):
        cfg[k] = int(v)
    elif k in ('lon_half_deg', 'lat_min_deg', 'lat_max_deg'):
        cfg[k] = float(v)
    else:
        raise SystemExit('unknown option ' + k)
print('PANO_CFG', cfg['lon_half_deg'], cfg['lat_min_deg'], cfg['lat_max_deg'], cfg['pano_w'], cfg['pano_h'], flush=True)
os.makedirs(outdir, exist_ok=True)
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'CUDA'
prefs.get_devices()
k = 0
for d in prefs.devices:
    if d.type == 'CUDA':
        d.use = (k == gpu_index); k += 1
    else:
        d.use = False
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'
sc.cycles.samples = spp; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.005
sc.cycles.use_denoising = True; sc.cycles.denoiser = 'OPENIMAGEDENOISE'
sc.render.use_persistent_data = True
cm = cfg['color']; vs = sc.view_settings
vs.view_transform = cm['view_transform']; vs.look = cm['look']; vs.exposure = cm['exposure']; vs.gamma = 1.0
vs.use_white_balance = True; vs.white_balance_temperature = cm['wb_temp']; vs.white_balance_tint = cm['wb_tint']
vs.use_curve_mapping = False
sc.use_nodes = False
sc.render.film_transparent = False
# hide everything that is not exterior from camera rays (keeps light transport otherwise identical)
hidden = 0
for o in sc.objects:
    if o.type in ('MESH', 'CURVE', 'CURVES', 'FONT', 'META', 'SURFACE', 'POINTCLOUD', 'VOLUME') and not o.name.startswith('Exterior'):
        o.visible_camera = False; hidden += 1
print('hidden from camera', hidden, flush=True)
cam_data = bpy.data.cameras.new('PanoCam'); cam = bpy.data.objects.new('PanoCam', cam_data)
sc.collection.objects.link(cam); sc.camera = cam
cam_data.clip_start = 0.01; cam_data.clip_end = 5000
P0 = Vector(cfg['center'])
# camera looking along world -X, up = world +Z: columns right, up, back
fwd = Vector((-1, 0, 0)); up = Vector((0, 0, 1)); right = fwd.cross(up)
M = Matrix.Identity(4)
for i in range(3):
    M[i][0] = right[i]; M[i][1] = up[i]; M[i][2] = -fwd[i]; M[i][3] = P0[i]
cam.matrix_world = M
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'; sc.render.image_settings.color_depth = '8'
# 1) panorama
cam_data.type = 'PANO'
try:
    cam_data.panorama_type = 'EQUIRECTANGULAR'
except Exception:
    cam_data.cycles.panorama_type = 'EQUIRECTANGULAR'
a = math.radians(cfg['lon_half_deg'])
for tgt, val in (('longitude_min', -a), ('longitude_max', a), ('latitude_min', math.radians(cfg['lat_min_deg'])), ('latitude_max', math.radians(cfg['lat_max_deg']))):
    if hasattr(cam_data, tgt):
        setattr(cam_data, tgt, val)
    else:
        setattr(cam_data.cycles, tgt, val)
sc.render.resolution_x, sc.render.resolution_y = cfg['pano_w'], cfg['pano_h']
sc.render.resolution_percentage = 100
sc.render.filepath = os.path.join(outdir, 'pano.png')
bpy.ops.render.render(write_still=True)
print('PANO_DONE', flush=True)
# 2) perspective check views (exterior only)
if not do_checks:
    sys.exit(0)
cam_data.type = 'PERSP'; cam_data.sensor_fit = 'HORIZONTAL'; cam_data.sensor_width = 36
sc.cycles.samples = 128
for i, v in enumerate(cfg['checks']):
    cam.matrix_world = Matrix(v['c2w']); cam_data.angle = v['fov_x']
    sc.render.resolution_x, sc.render.resolution_y = cfg['check_w'], cfg['check_h']
    sc.render.filepath = os.path.join(outdir, 'check_%d.png' % i)
    bpy.ops.render.render(write_still=True)
print('CHECKS_DONE', flush=True)
