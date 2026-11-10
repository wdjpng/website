#!/bin/bash
# re-render the views that see the llama/magnet with bedroom_v3.blend, then train both models and package them
set -x
export CUDA_CACHE_MAXSIZE=4294967296
B=/work/opt/blender-4.5.15-linux-x64/blender
. /work/venv/bin/activate
rm -rf /work/out/v3 && cp -al /work/out/v2 /work/out/v3
python /work/scripts/select_views.py /work/out/v2 /work/out/views_v3_sel.json
python3 - <<'PY'
import json, os
sel = json.load(open('/work/out/views_v3_sel.json'))
for v in sel['views']:
    for f in (f"{v['name']}.png", 'depth_%04d.exr' % v['idx'], 'index_%04d.exr' % v['idx']):
        p = '/work/out/v3/' + f
        if os.path.exists(p): os.remove(p)
print('cleared', len(sel['views']))
PY
for g in 0 1; do
  $B -b /work/bedroom_v3.blend --python /work/scripts/bl_render_views.py -- /work/out/views_v3_sel.json /work/out/v3 $g 2 $g 128 CUDA 2>&1 | grep --line-buffered -E "TODO|VIEW|DONE|rror" > /work/jobs/v3_gpu$g.log &
done
wait
echo V3_RENDER_DONE
rsync -a /work/out/v3 lukas:out/ &
COMMON="--data /work/out/v3 --iters 30000 --refine_stop 0.6 --eval_every 5000 --holdout 50 --sh_reg 0.1 --scene_scale 1.0 --depth_mode log --depth_w 0.03 --alpha_w 0.05 --pano /work/out/pano/pano.png --pano_cfg /work/scripts/pano_cfg.json"
(CUDA_VISIBLE_DEVICES=0 python /work/scripts/train_gs.py $COMMON --out /work/out/tr3_high --cap 1500000 --init_pts 700000 > /work/jobs/tr3_high.log 2>&1
 CUDA_VISIBLE_DEVICES=0 python /work/scripts/render_splats.py --params /work/out/tr3_high/params.pt --views /work/scripts/views_check.json --out /work/out/tr3_high/check > /dev/null 2>&1
 bash /work/scripts/pkg_final.sh tr3_high room-high-v3 3 >> /work/jobs/tr3_high.log 2>&1
 rsync -a --exclude params.pt /work/out/tr3_high lukas:out/) &
(CUDA_VISIBLE_DEVICES=1 python /work/scripts/train_gs.py $COMMON --out /work/out/tr3_mob --cap 1000000 --init_pts 500000 > /work/jobs/tr3_mob.log 2>&1
 CUDA_VISIBLE_DEVICES=1 python /work/scripts/render_splats.py --params /work/out/tr3_mob/params.pt --views /work/scripts/views_check.json --out /work/out/tr3_mob/check > /dev/null 2>&1
 bash /work/scripts/pkg_final.sh tr3_mob room-mobile-v3 3 >> /work/jobs/tr3_mob.log 2>&1
 rsync -a --exclude params.pt /work/out/tr3_mob lukas:out/) &
wait
echo V3_ALL_DONE
