# Render training/eval views of the bedroom with Cycles.
# usage: blender -b scene.blend --python bl_render_views.py -- views.json outdir gpu_index stride offset [spp] [backend]
import bpy, sys, json, os, time, math
from mathutils import Matrix, Euler, Vector
argv = sys.argv[sys.argv.index('--') + 1:]
views_path, outdir, gpu_index, stride, offset = argv[0], argv[1], int(argv[2]), int(argv[3]), int(argv[4])
spp = int(argv[5]) if len(argv) > 5 else 256
backend = argv[6] if len(argv) > 6 else 'OPTIX'
cfg = json.load(open(views_path))
views = cfg['views']
os.makedirs(outdir, exist_ok=True)

prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = backend if backend != 'CPU' else 'NONE'
prefs.get_devices()
k = 0
for d in prefs.devices:
    if d.type == backend:
        d.use = (k == gpu_index)
        k += 1
    else:
        d.use = False
print('DEVICES', [(d.name, d.type, d.use) for d in prefs.devices], flush=True)

sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'GPU' if backend != 'CPU' else 'CPU'
cyc = sc.cycles
cyc.samples = spp
cyc.use_adaptive_sampling = True
cyc.adaptive_threshold = float(os.environ.get('ADAPT', cfg.get('noise_threshold', 0.006)))
cyc.adaptive_min_samples = min(64, spp)
cyc.use_denoising = os.environ.get('NO_DENOISE') != '1'   # fur: unbiased noise averages out in training, denoiser smears do not
cyc.denoiser = 'OPENIMAGEDENOISE'
try:
    cyc.denoising_use_gpu = True
except Exception:
    pass
cyc.denoising_prefilter = 'ACCURATE'
cyc.use_animated_seed = False
sc.render.use_persistent_data = True
sc.render.resolution_x = cfg['width']
sc.render.resolution_y = cfg['height']
sc.render.resolution_percentage = 100
sc.render.film_transparent = False
sc.render.use_motion_blur = False
cm = cfg['color']
vs = sc.view_settings
vs.view_transform = cm['view_transform']
vs.look = cm['look']
vs.exposure = cm['exposure']
vs.gamma = 1.0
try:
    vs.use_white_balance = True
    vs.white_balance_temperature = cm['wb_temp']
    vs.white_balance_tint = cm['wb_tint']
except Exception as e:
    print('WB not available', e)
sc.display_settings.display_device = 'sRGB'
vs.use_curve_mapping = False

# glass pass index for depth masking
for o in sc.objects:
    o.pass_index = 0
for name in cfg.get('glass_objects', []):
    if name in bpy.data.objects:
        bpy.data.objects[name].pass_index = 7

vl = sc.view_layers[0] if bpy.context.view_layer is None else bpy.context.view_layer
vl.use_pass_z = True
vl.use_pass_object_index = True

# compositor: image -> composite, depth+index -> EXR via file output
sc.use_nodes = True
tree = sc.node_tree
tree.nodes.clear()
rl = tree.nodes.new('CompositorNodeRLayers')
comp = tree.nodes.new('CompositorNodeComposite')
tree.links.new(rl.outputs['Image'], comp.inputs['Image'])
fo = tree.nodes.new('CompositorNodeOutputFile')
fo.base_path = outdir
fo.format.file_format = 'OPEN_EXR'
fo.format.color_depth = '32'
fo.format.exr_codec = 'ZIP'
fo.file_slots.clear()
fo.file_slots.new('depth_')
fo.file_slots.new('index_')
tree.links.new(rl.outputs['Depth'], fo.inputs[0])
tree.links.new(rl.outputs['IndexOB'], fo.inputs[1])

cam_data = bpy.data.cameras.new('TrainCamData')
cam = bpy.data.objects.new('TrainCam', cam_data)
sc.collection.objects.link(cam)
cam_data.sensor_fit = 'HORIZONTAL'
cam_data.sensor_width = 36.0
cam_data.dof.use_dof = False
cam_data.clip_start = 0.01
cam_data.clip_end = 1000.0
sc.camera = cam
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGB'
sc.render.image_settings.color_depth = '8'

# object-only renders: everything except objects whose name starts with HOLDOUT_KEEP becomes a holdout
# (still lights, shadows and reflects, but shows as transparent), saved as RGBA
for o in sc.objects:
    if os.environ.get('HIDE_PREFIX') and o.name.startswith(os.environ['HIDE_PREFIX']):
        o.hide_render = True
keep = os.environ.get('HOLDOUT_KEEP', '')
hdri = os.environ.get('WORLD_HDRI', '')
if keep and hdri:
    # image-based lighting: only the kept objects exist, lit by a panorama of the room captured at their position
    sc.render.film_transparent = os.environ.get('SHOW_WORLD') != '1'
    sc.render.image_settings.color_mode = 'RGBA'
    for o in sc.objects:
        if not o.name.startswith(keep) and o.type != 'CAMERA':
            o.hide_render = True
    w = bpy.data.worlds.new('room light at object'); w.use_nodes = True
    nt = w.node_tree; bgn = nt.nodes.get('Background')
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
    et = nt.nodes.new('ShaderNodeTexEnvironment'); et.image = bpy.data.images.load(hdri)
    mp.inputs['Rotation'].default_value = (0, 0, math.radians(float(os.environ.get('HDRI_ROT', '0'))))
    nt.links.new(tc.outputs['Generated'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], et.inputs['Vector'])
    nt.links.new(et.outputs['Color'], bgn.inputs['Color']); bgn.inputs['Strength'].default_value = 1.0
    sc.world = w
    print('WORLD_HDRI', hdri, 'rot', os.environ.get('HDRI_ROT', '0'), flush=True)
elif keep:
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = 'RGBA'
    nh = 0
    for o in sc.objects:
        if not o.name.startswith(keep) and o.type in ('MESH', 'CURVE', 'CURVES', 'SURFACE', 'META', 'FONT', 'VOLUME', 'POINTCLOUD'):
            o.is_holdout = True; nh += 1
    print('HOLDOUT objects', nh, 'kept prefix', keep, flush=True)

todo = [v for i, v in enumerate(views) if i % stride == offset]
if os.environ.get('REVERSE') == '1':
    todo = todo[::-1]
print('TODO', len(todo), flush=True)
t0 = time.time()
for n, v in enumerate(todo):
    name = v['name']
    png = os.path.join(outdir, name + '.png')
    if os.path.exists(png) and os.path.exists(os.path.join(outdir, 'depth_%04d.exr' % v['idx'])):
        if os.environ.get('REVERSE') == '1':
            print('meet point reached', flush=True); break
        continue
    # c2w in blender convention (camera looks down -Z, +Y up)
    M = Matrix(v['c2w'])
    cam.matrix_world = M
    cam_data.angle = v['fov_x']
    sc.frame_current = v['idx']
    sc.render.filepath = png
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print('VIEW', n, len(todo), name, '%.1fs' % (time.time() - t), 'total %.0fs' % (time.time() - t0), flush=True)
print('RENDER_DONE', flush=True)
