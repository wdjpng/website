#!/bin/bash
# Dedicated llama model: object-only close-up renders -> llama splats -> merged into the v4 room models -> SOG
set -x
export CUDA_CACHE_MAXSIZE=4294967296
B=/work/opt/blender-4.5.15-linux-x64/blender
. /work/venv/bin/activate
L=/work/out/llama
NV=${NV:-150}
mkdir -p $L
# same llama as v4 but with the finer pompom yarn (only the llama renders use this file)
[ -f /work/bedroom_v4b.blend ] || $B -b /work/in/cr-3/outputs/bedroom_reconstruction.blend --python /work/scripts/bl_rebuild_llama.py -- /work/bedroom_v4b.blend /work/scripts/magnet_rectified.png 1.0 2>&1 | grep -E "fleece|SAVED|rror"
$B -b /work/bedroom_v4b.blend --python /work/scripts/bl_llama_views.py -- /work/scripts/views_v2.json $L/views.json $NV 3 2>&1 | grep -E "LLAMA_BOX|MAGNET_BOX|probes|views|WROTE|rror" | tee /work/jobs/llama_views.txt
BOX=$(grep LLAMA_BOX /work/jobs/llama_views.txt | awk '{print $2}')
for g in 0 1; do
  HOLDOUT_KEEP=Llama $B -b /work/bedroom_v4b.blend --python /work/scripts/bl_render_views.py -- $L/views.json $L $g 2 $g 128 CUDA 2>&1 | grep --line-buffered -E "HOLDOUT|TODO|VIEW|DONE|rror" > /work/jobs/llama_gpu$g.log &
done
# early peek at the first renders
(sleep 240; mkdir -p /tmp/lpk; cp $L/l000[0-3].png /tmp/lpk/ 2>/dev/null; rsync -a /tmp/lpk/ lukas:out/llama_peek/) &
wait
echo LLAMA_RENDER_DONE
mkdir -p /tmp/lpk2; cp $L/l00[0-1]?.png /tmp/lpk2/; rsync -a /tmp/lpk2/ lukas:out/llama_peek/
# pad the box by 1.5 cm (fleece tips), keep the bottom at the sill
PB=$(python3 -c "b=[float(v) for v in '$BOX'.split(',')]; p=0.015; print(','.join('%.4f'%v for v in [b[0]-p,b[1]-p,max(b[2],0.7425),b[3]+p,b[4]+p,b[5]+p]))")
COMMON="--data $L --iters 25000 --refine_stop 0.6 --eval_every 5000 --holdout 25 --sh_reg 0.1 --scene_scale 0.5 --depth_mode log --depth_w 0.02 --rgba 0.3 --init_scale 0.8 --box=$PB"
(CUDA_VISIBLE_DEVICES=0 python /work/scripts/train_gs.py $COMMON --out /work/out/llama_high --cap 250000 --init_pts 120000 > /work/jobs/llama_high.log 2>&1) &
(CUDA_VISIBLE_DEVICES=1 python /work/scripts/train_gs.py $COMMON --out /work/out/llama_mob --cap 120000 --init_pts 80000 > /work/jobs/llama_mob.log 2>&1) &
wait
echo LLAMA_TRAIN_DONE
rsync -a --exclude params.pt /work/out/llama_high /work/out/llama_mob lukas:out/
# wait for the v4 room models, then merge
while ! grep -q TRAIN_DONE /work/jobs/tr4_high.log 2>/dev/null || ! grep -q TRAIN_DONE /work/jobs/tr4_mob.log 2>/dev/null; do sleep 15; done
for T in high mob; do
  mkdir -p /work/out/tr4m_$T
  python /work/scripts/merge_llama.py /work/out/tr4_$T/splat.ply /work/out/llama_$T/splat.ply $L /work/out/tr4m_$T/splat.ply "$BOX" 0.7445
  python /work/scripts/render_splats.py --params /work/out/tr4m_$T/splat.ply --views /work/scripts/views_check.json --out /work/out/tr4m_$T/check > /dev/null 2>&1
done
bash /work/scripts/pkg_final.sh tr4m_high room-high-v4m 3
bash /work/scripts/pkg_final.sh tr4m_mob room-mobile-v4m 3
rsync -a --exclude splat.ply /work/out/tr4m_high /work/out/tr4m_mob lukas:out/
echo LLAMA_ALL_DONE
