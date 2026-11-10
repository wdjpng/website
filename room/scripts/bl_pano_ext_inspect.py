# list Exterior* objects: world-space vertices, uv, material node tree and images (writes images to outdir)
import bpy, sys, os, json
argv = sys.argv[sys.argv.index('--') + 1:]; outdir = argv[0]; os.makedirs(outdir, exist_ok=True)
sc = bpy.context.scene
res = {'world': None, 'objs': []}
w = sc.world
if w and w.use_nodes:
    res['world'] = [(n.type, n.name, [(i.name, list(i.default_value) if hasattr(i.default_value, '__len__') else i.default_value) for i in n.inputs if hasattr(i, 'default_value')]) for n in w.node_tree.nodes]
for o in sc.objects:
    if not o.name.startswith('Exterior'): continue
    d = {'name': o.name, 'type': o.type, 'hide_render': o.hide_render, 'mw': [list(r) for r in o.matrix_world]}
    if o.type == 'MESH':
        me = o.data
        d['verts'] = [list(o.matrix_world @ v.co) for v in me.vertices][:64]
        d['nverts'] = len(me.vertices)
        if me.uv_layers:
            uv = me.uv_layers.active.data
            d['loops'] = [(me.loops[i].vertex_index, list(uv[i].uv)) for i in range(min(64, len(me.loops)))]
        d['mats'] = []
        for s in o.material_slots:
            m = s.material
            if not m: continue
            md = {'name': m.name, 'nodes': []}
            if m.use_nodes:
                for n in m.node_tree.nodes:
                    nd = {'type': n.type, 'name': n.name, 'inputs': {}}
                    for i in n.inputs:
                        if hasattr(i, 'default_value'):
                            v = i.default_value
                            nd['inputs'][i.name] = list(v) if hasattr(v, '__len__') else v
                    if n.type == 'TEX_IMAGE' and n.image:
                        im = n.image; nd['image'] = [im.name, im.filepath, list(im.size), im.colorspace_settings.name]
                        fn = os.path.join(outdir, bpy.path.clean_name(im.name) + '.png')
                        im2 = im.copy(); im2.filepath_raw = fn; im2.file_format = 'PNG'
                        try: im2.save()
                        except Exception as e: print('save fail', e)
                    nd['links'] = [(l.from_node.name, l.from_socket.name, l.to_node.name, l.to_socket.name) for l in m.node_tree.links if l.to_node == n]
                    md['nodes'].append(nd)
            d['mats'].append(md)
    res['objs'].append(d)
json.dump(res, open(os.path.join(outdir, 'ext.json'), 'w'), indent=1, default=str)
print('INSPECT_DONE', [o['name'] for o in res['objs']], flush=True)
