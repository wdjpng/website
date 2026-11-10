# print the world bounding box of all Llama* objects: LLAMA_BOX x0,y0,z0,x1,y1,z1
import bpy, numpy as np
from mathutils import Vector
lo = np.array([1e9] * 3); hi = -lo
for o in bpy.context.scene.objects:
    if o.name.startswith('Llama'):
        for c in o.bound_box:
            w = np.array(o.matrix_world @ Vector(c)); lo = np.minimum(lo, w); hi = np.maximum(hi, w)
print('LLAMA_BOX', ','.join('%.4f' % v for v in list(lo) + list(hi)), flush=True)
