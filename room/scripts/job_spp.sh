#!/bin/bash
# Is the Cycles ground truth itself blotchy on walls? Render two wall views at 128 spp (as in training) and at
# 1024 spp with a tight adaptive threshold, and compare.
set -x
export CUDA_CACHE_MAXSIZE=4294967296
B=/work/opt/blender-4.5.15-linux-x64/blender
rsync -a lukas:out/bedroom_v3.blend /work/
python3 - <<'PY'
import json
c = json.load(open('/work/scripts/views_v2.json'))
c['views'] = [v for v in c['views'] if v['name'] in ('w00310', 'w00089')]
json.dump(c, open('/work/out/views_spp.json', 'w'))
c['noise_threshold'] = 0.001
json.dump(c, open('/work/out/views_spp_hi.json', 'w'))
PY
$B -b /work/bedroom_v3.blend --python /work/scripts/bl_render_views.py -- /work/out/views_spp.json /work/out/spp128 0 1 0 128 CUDA 2>&1 | grep -E "VIEW|rror"
$B -b /work/bedroom_v3.blend --python /work/scripts/bl_render_views.py -- /work/out/views_spp_hi.json /work/out/spp1024 0 1 0 1024 CUDA 2>&1 | grep -E "VIEW|rror"
rsync -a --exclude '*.exr' /work/out/spp128 /work/out/spp1024 lukas:out/
echo SPP_DONE
