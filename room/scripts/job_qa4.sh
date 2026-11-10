#!/bin/bash
# QA for v4: Cycles ground truth (v4b blend) at the llama check views, and splat renders of the unmerged and merged models
set -x
export CUDA_CACHE_MAXSIZE=4294967296
B=/work/opt/blender-4.5.15-linux-x64/blender
. /work/venv/bin/activate
python3 - <<'PY'
import json
c = json.load(open('/work/scripts/views_check.json'))
v2 = json.load(open('/work/scripts/views_v2.json'))
extra = [v for v in v2['views'] if v['name'] in ('w00003', 'w00011', 'w00676')]
c['views'] = [v for v in c['views'] if v['name'] in ('chk_0', 'chk_1', 'chk_2')] + extra
json.dump(c, open('/work/scripts/views_qa4.json', 'w'))
PY
# GT renders while the models train
$B -b /work/bedroom_v4b.blend --python /work/scripts/bl_render_views.py -- /work/scripts/views_qa4.json /work/out/qa4/gt 0 1 0 128 CUDA 2>&1 | grep -E "VIEW|DONE|rror"
while ! grep -q LLAMA_ALL_DONE /work/jobs/llama3.log 2>/dev/null; do sleep 20; done
for M in tr4_high tr4m_high tr4_mob tr4m_mob; do
  python /work/scripts/render_splats.py --params /work/out/$M/splat.ply --views /work/scripts/views_qa4.json --out /work/out/qa4/$M > /dev/null 2>&1
done
python /work/scripts/render_splats.py --params /work/out/llama_high/splat.ply --views /work/scripts/views_qa4.json --out /work/out/qa4/llama_only > /dev/null 2>&1
rsync -a --exclude '*.exr' /work/out/qa4 lukas:out/
echo QA4_DONE
