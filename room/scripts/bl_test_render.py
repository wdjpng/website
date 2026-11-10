import bpy, sys, time, json
argv = sys.argv[sys.argv.index('--')+1:]
backend, cam, res, spp, out = argv[0], argv[1], int(argv[2]), int(argv[3]), argv[4]
gpu_index = int(argv[5]) if len(argv) > 5 else -1
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = backend
prefs.get_devices()
n=0
for d in prefs.devices:
    use = d.type == backend and (gpu_index < 0 or n == gpu_index)
    if d.type == backend: n += 1
    d.use = use
print('DEVICES', [(d.name, d.type, d.use) for d in prefs.devices])
sc = bpy.context.scene
sc.cycles.device = 'GPU'
sc.camera = bpy.data.objects[cam]
sc.render.resolution_x = res
sc.render.resolution_y = res*3//4
sc.render.resolution_percentage = 100
sc.cycles.samples = spp
sc.cycles.adaptive_min_samples = min(32, spp)
sc.cycles.use_denoising = True
sc.render.use_persistent_data = True
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = out
t = time.time()
bpy.ops.render.render(write_still=True)
print('RENDER_TIME', time.time() - t)
t = time.time()
bpy.ops.render.render(write_still=True)
print('RENDER_TIME2', time.time() - t)
