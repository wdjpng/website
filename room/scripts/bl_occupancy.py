# Export world-space XY points of geometry between ankle and head height, per object, for the walk map.
import bpy, numpy as np, json
dg = bpy.context.evaluated_depsgraph_get()
out = {}
skip_prefix = ('Architecture', 'Exterior', 'Floor', 'Rug', 'Ceiling', 'Blind', 'Window', 'Trim', 'Wall', 'Entry door', 'Door beside bed', 'Switch', 'Window outlet', 'Lamp outlet', 'Data outlet', 'Door')
for inst in dg.object_instances:
    o = inst.object
    if o.type not in ('MESH', 'CURVE', 'CURVES', 'FONT'):
        continue
    name = (inst.parent.name + '>' if inst.is_instance and inst.parent else '') + o.name
    mw = np.array(inst.matrix_world)
    if o.type == 'CURVES':
        pts = np.array([p.position for p in o.data.points]) if len(o.data.points) < 50000 else None
        if pts is None:
            arr = np.zeros(len(o.data.points)*3, dtype=np.float32)
            o.data.attributes['position'].data.foreach_get('vector', arr)
            pts = arr.reshape(-1, 3)
    else:
        try:
            me = o.to_mesh()
        except Exception:
            continue
        if me is None:
            continue
        arr = np.zeros(len(me.vertices)*3, dtype=np.float32)
        me.vertices.foreach_get('co', arr)
        pts = arr.reshape(-1, 3)
        o.to_mesh_clear()
    if len(pts) == 0:
        continue
    pts = pts @ mw[:3, :3].T + mw[:3, 3]
    if pts.shape[0] > 20000:
        pts = pts[np.random.default_rng(0).choice(pts.shape[0], 20000, replace=False)]
    sel = (pts[:, 2] > 0.035) & (pts[:, 2] < 1.95)
    if sel.sum() == 0:
        continue
    out[name] = pts[sel].astype(np.float32)
np.savez_compressed('/home/muenzel_lukas/room/work/occ_points.npz', **{k.replace('/', '|'): v for k, v in out.items()})
print('OBJECTS', len(out))
