#!/bin/bash
# After the llama models are trained: merge them into the v3 room models, package, and render QA views
set -x
. /work/venv/bin/activate
L=/work/out/llama
while ! grep -q LLAMA_TRAIN_DONE /work/jobs/llama3.log 2>/dev/null; do sleep 15; done
pkill -f job_llama.sh; pkill -f job_qa4.sh
BOX=$(grep LLAMA_BOX /work/jobs/llama_views.txt | awk '{print $2}')
MB=$(grep MAGNET_BOX /work/jobs/llama_views.txt | awk '{print $2}')
for T in high mob; do
  mkdir -p /work/out/tr4m_$T
  python /work/scripts/merge_llama.py /work/out/tr3_$T/splat.ply /work/out/llama_$T/splat.ply $L /work/out/tr4m_$T/splat.ply "$BOX" 0.7445 "$MB"
done
python3 - <<'PY'
import json
c = json.load(open('/work/scripts/views_check.json'))
v2 = json.load(open('/work/scripts/views_v2.json'))
extra = [v for v in v2['views'] if v['name'] in ('w00003', 'w00011', 'w00676')]
c['views'] = [v for v in c['views'] if v['name'] in ('chk_0', 'chk_1', 'chk_2')] + extra
json.dump(c, open('/work/out/views_qa4.json', 'w'))
PY
for M in tr3_high tr4m_high tr4m_mob llama_high; do
  python /work/scripts/render_splats.py --params /work/out/$M/splat.ply --views /work/out/views_qa4.json --out /work/out/qa4/$M > /dev/null 2>&1
done
rsync -a --exclude '*.exr' /work/out/qa4 lukas:out/
echo QA_RENDERS_DONE
bash /work/scripts/pkg_final.sh tr4m_high room-high-v4m 3
bash /work/scripts/pkg_final.sh tr4m_mob room-mobile-v4m 3
echo MERGE_ALL_DONE
