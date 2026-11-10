import bpy
for o in bpy.context.scene.objects:
    if o.name.startswith(('Llama', 'Framed art', 'Badge')) or 'llama' in o.name.lower():
        mats = [s.material.name for s in o.material_slots if s.material] if hasattr(o, 'material_slots') else []
        print('OBJ', o.type, repr(o.name), 'parent', o.parent.name if o.parent else None, 'loc', tuple(round(v, 4) for v in o.matrix_world.translation), 'dims', tuple(round(v, 4) for v in o.dimensions), 'mods', [m.type for m in getattr(o, 'modifiers', [])], 'mats', mats)
for m in bpy.data.materials:
    if 'Llama' in m.name or 'Framed' in m.name or 'art' in m.name.lower():
        print('MAT', m.name, [n.bl_idname + ':' + (n.image.name if getattr(n, 'image', None) else '') for n in m.node_tree.nodes] if m.use_nodes else '')
