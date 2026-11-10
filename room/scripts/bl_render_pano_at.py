# Capture the room's light at the llama: an equirectangular HDR panorama (scene-linear EXR) rendered from the llama's
# position with the llama hidden. Used as image-based lighting for the llama renders, which are far less noisy than
# path-tracing fine fur inside the dim room.
# usage: blender -b scene.blend --python bl_render_pano_at.py -- out.exr gpu x y z [spp] [width] [rot_z_deg]
import bpy, sys, math
argv = sys.argv[sys.argv.index('--') + 1:]
OUT, GPU = argv[0], int(argv[1])
X, Y, Z = float(argv[2]), float(argv[3]), float(argv[4])
SPP = int(argv[5]) if len(argv) > 5 else 1024
WID = int(argv[6]) if len(argv) > 6 else 2048
sc = bpy.context.scene
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'CUDA'; prefs.get_devices()
k = 0
for d in prefs.devices:
    if d.type == 'CUDA':
        d.use = (k == GPU); k += 1
    else:
        d.use = False
sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'
sc.cycles.samples = SPP; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.005
sc.cycles.use_denoising = True; sc.cycles.denoiser = 'OPENIMAGEDENOISE'
sc.render.resolution_x = WID; sc.render.resolution_y = WID // 2; sc.render.resolution_percentage = 100
sc.render.film_transparent = False
sc.use_nodes = False
for o in sc.objects:
    if o.name.startswith('Llama'):
        o.hide_render = True
cd = bpy.data.cameras.new('pano cam'); cd.type = 'PANO'
try:
    cd.panorama_type = 'EQUIRECTANGULAR'
except Exception:
    cd.cycles.panorama_type = 'EQUIRECTANGULAR'
cam = bpy.data.objects.new('pano cam', cd); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (X, Y, Z)
# looking along +X with Z up; the world texture lookup uses the matching rotation (see bl_render_views.py WORLD_HDRI)
cam.rotation_euler = (math.pi / 2, 0, -math.pi / 2)
cd.clip_start = 0.001
sc.render.image_settings.file_format = 'OPEN_EXR'; sc.render.image_settings.color_depth = '32'
sc.render.image_settings.exr_codec = 'ZIP'
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print('PANO_DONE', OUT, flush=True)
