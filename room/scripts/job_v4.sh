#!/bin/bash
# re-render the views that see the llama/magnet with bedroom_v4.blend, then train both models and package them
set -x
export CUDA_CACHE_MAXSIZE=4294967296
B=/work/opt/blender-4.5.15-linux-x64/blender
. /work/venv/bin/activate
rm -rf /work/out/v4 && cp -al /work/out/v2 /work/out/v4
$B -b /work/in/cr-3/outputs/bedroom_reconstruction.blend --python /work/scripts/bl_rebuild_llama.py -- /work/bedroom_v4.blend /work/scripts/magnet_rectified.png 1.0 2>&1 | grep -E 'fleece|SAVED|rror'
python3 - <<'PY'
import json, os
sel = json.load(open('/work/out/views_v3_sel.json'))
for v in sel['views']:
    for f in (f"{v['name']}.png", 'depth_%04d.exr' % v['idx'], 'index_%04d.exr' % v['idx']):
        p = '/work/out/v4/' + f
        if os.path.exists(p): os.remove(p)
print('cleared', len(sel['views']))
PY
for g in 0 1; do
  $B -b /work/bedroom_v4.blend --python /work/scripts/bl_render_views.py -- /work/out/views_v3_sel.json /work/out/v4 $g 2 $g 128 CUDA 2>&1 | grep --line-buffered -E "TODO|VIEW|DONE|rror" > /work/jobs/v4_gpu$g.log &
done
wait
echo V4_RENDER_DONE
: renders stay on the GPU node, the server disk is nearly full
COMMON="--data /work/out/v4 --iters 30000 --refine_stop 0.6 --eval_every 5000 --holdout 50 --sh_reg 0.1 --scene_scale 1.0 --depth_mode log --depth_w 0.03 --alpha_w 0.05 --pano /work/out/pano/pano.png --pano_cfg /work/scripts/pano_cfg.json"
(CUDA_VISIBLE_DEVICES=0 python /work/scripts/train_gs.py $COMMON --out /work/out/tr4_high --cap 1500000 --init_pts 700000 > /work/jobs/tr4_high.log 2>&1
 CUDA_VISIBLE_DEVICES=0 python /work/scripts/render_splats.py --params /work/out/tr4_high/params.pt --views /work/scripts/views_check.json --out /work/out/tr4_high/check > /dev/null 2>&1
 bash /work/scripts/pkg_final.sh tr4_high room-high-v4 3 >> /work/jobs/tr4_high.log 2>&1
 rsync -a --exclude params.pt /work/out/tr4_high lukas:out/) &
(CUDA_VISIBLE_DEVICES=1 python /work/scripts/train_gs.py $COMMON --out /work/out/tr4_mob --cap 1000000 --init_pts 500000 > /work/jobs/tr4_mob.log 2>&1
 CUDA_VISIBLE_DEVICES=1 python /work/scripts/render_splats.py --params /work/out/tr4_mob/params.pt --views /work/scripts/views_check.json --out /work/out/tr4_mob/check > /dev/null 2>&1
 bash /work/scripts/pkg_final.sh tr4_mob room-mobile-v4 3 >> /work/jobs/tr4_mob.log 2>&1
 rsync -a --exclude params.pt /work/out/tr4_mob lukas:out/) &
wait
echo V4_ALL_DONE
