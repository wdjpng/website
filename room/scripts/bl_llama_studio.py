# Render the llama alone in neutral "studio" light, close to the user's reference photos (soft daylight, light wall),
# from several angles, to judge its shape and fleece before it goes back into the room.
# usage: blender -b llama.blend --python bl_llama_studio.py -- outdir gpu_index [spp] [res]
import bpy, sys, os, math
from mathutils import Vector
argv = sys.argv[sys.argv.index('--') + 1:]
OUT, GPU = argv[0], int(argv[1])
SPP = int(argv[2]) if len(argv) > 2 else 128
RES = int(argv[3]) if len(argv) > 3 else 720
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
prefs = bpy.context.preferences.addons['cycles'].preferences
sc.render.engine = 'CYCLES'
if GPU >= 0:
    prefs.compute_device_type = 'CUDA'; prefs.get_devices()
    k = 0
    for d in prefs.devices:
        if d.type == 'CUDA':
            d.use = (k == GPU); k += 1
        else:
            d.use = False
    sc.cycles.device = 'GPU'
else:
    sc.cycles.device = 'CPU'
sc.cycles.samples = SPP; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.01
sc.cycles.use_denoising = True; sc.cycles.denoiser = 'OPENIMAGEDENOISE'
sc.render.resolution_x = RES; sc.render.resolution_y = RES; sc.render.resolution_percentage = 100
sc.render.film_transparent = False
vs = sc.view_settings
vs.view_transform = 'AgX'; vs.look = 'None'; vs.exposure = -0.4; vs.gamma = 1.0
try:
    vs.use_white_balance = False
except Exception:
    pass
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
if sc.node_tree:
    sc.use_nodes = False

# only the llama
for o in sc.objects:
    o.hide_render = not o.name.startswith('Llama')
# soft daylight: light-grey world + a big soft key light from the camera's upper left + a white floor
w = bpy.data.worlds.new('studio'); w.use_nodes = True
bg = w.node_tree.nodes.get('Background'); bg.inputs['Color'].default_value = (0.82, 0.82, 0.80, 1); bg.inputs['Strength'].default_value = 0.45
sc.world = w
L = Vector((-1.715, -0.272, 0.875))
key = bpy.data.lights.new('key', 'AREA'); key.size = 0.9; key.energy = 90.0; key.color = (1.0, 0.98, 0.95)
ko = bpy.data.objects.new('studio key', key); sc.collection.objects.link(ko)
ko.location = L + Vector((0.9, 0.6, 0.9)); ko.rotation_euler = (L - ko.location).to_track_quat('-Z', 'Y').to_euler()
pm = bpy.data.meshes.new('floor'); s = 2.0
pm.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
fl = bpy.data.objects.new('studio floor', pm); sc.collection.objects.link(fl); fl.location = (L.x, L.y, 0.742)
fmat = bpy.data.materials.new('floor'); fmat.use_nodes = True
fmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.75, 0.74, 0.72, 1)
fmat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 1.0
pm.materials.append(fmat)

cam_d = bpy.data.cameras.new('studio cam'); cam_d.sensor_width = 36; cam_d.clip_start = 0.01
cam = bpy.data.objects.new('studio cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
HEAD = Vector((-1.662, -0.272, 0.950))
# name, target, azimuth (deg from +X towards +Y), elevation (deg), distance (m), lens (mm)
shots = [
    ('face_left34', HEAD, 40, 8, 0.30, 70),
    ('face_right34', HEAD, -40, 8, 0.30, 70),
    ('head_side', HEAD + Vector((-0.015, 0, 0)), 85, 5, 0.32, 70),
    ('head_back34', HEAD + Vector((-0.02, 0, 0)), 135, 15, 0.34, 70),
    ('front', HEAD + Vector((0, 0, -0.01)), 0, 5, 0.30, 70),
    ('full_34', Vector((-1.72, -0.272, 0.875)), 50, 12, 0.75, 55),
]
only = os.environ.get('SHOTS')
for name, tgt, az, el, dist, lens in shots:
    if only and name not in only.split(','):
        continue
    a, e = math.radians(az), math.radians(el)
    cam.location = tgt + Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))) * dist
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam_d.lens = lens
    sc.render.filepath = os.path.join(OUT, name + '.jpg')
    bpy.ops.render.render(write_still=True)
    print('SHOT', name, flush=True)
print('STUDIO_DONE', flush=True)
