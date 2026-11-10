import bpy, collections, math
sc = bpy.context.scene
print("SCENE", sc.name, "engine", sc.render.engine, "frame", sc.frame_current)
print("CM", sc.view_settings.view_transform, sc.view_settings.look, sc.view_settings.exposure, sc.display_settings.display_device)
print("cycles samples", sc.cycles.samples, "world", sc.world.name if sc.world else None)
types = collections.Counter(o.type for o in sc.objects)
print("TYPES", types)
# per-type listing with poly counts
tot = 0
rows = []
dg = bpy.context.evaluated_depsgraph_get()
for o in sc.objects:
    vis = not o.hide_render and o.visible_get() if hasattr(o,'visible_get') else not o.hide_render
    info = ""
    if o.type == 'MESH':
        oe = o.evaluated_get(dg)
        try:
            me = oe.to_mesh()
            n = len(me.loop_triangles) if me.loop_triangles else 0
            me.calc_loop_triangles(); n = len(me.loop_triangles)
            oe.to_mesh_clear()
        except Exception as e:
            n = -1
        info = f"tris={n} mods={[m.type for m in o.modifiers]} mats={[s.material.name if s.material else None for s in o.material_slots][:4]} uv={[u.name for u in o.data.uv_layers]}"
        tot += max(n,0)
    elif o.type == 'LIGHT':
        l = o.data
        info = f"light {l.type} energy={l.energy} color={tuple(round(c,3) for c in l.color)} size={getattr(l,'shadow_soft_size',None)} temp?"
    elif o.type == 'CURVES':
        info = f"curves={len(o.data.curves)} points={len(o.data.points)} mats={[m.name for m in o.data.materials if m]}"
    rows.append((o.type, o.name, o.hide_render, tuple(round(v,3) for v in o.matrix_world.translation), tuple(round(v,3) for v in o.dimensions), o.parent.name if o.parent else None, info))
for r in sorted(rows):
    print("OBJ", *r)
print("TOTAL TRIS", tot)
print("COLLECTIONS")
def walk(c, d=0):
    print("  "*d, c.name, len(c.objects), "hide_render" if c.hide_render else "")
    for ch in c.children: walk(ch, d+1)
walk(sc.collection)
