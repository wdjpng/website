#!/bin/bash
# v6 llama into the room: object-only renders of the new llama (blend from job_studio.sh), llama splat models,
# merge into the v5 room model (carving out the old llama too), QA renders, SOG packages
# usage: bash job_llama6.sh TAG
set -x
TAG=$1
export CUDA_CACHE_MAXSIZE=4294967296
B=/work/opt/blender-4.5.15-linux-x64/blender
. /work/venv/bin/activate
L=/work/out/llama6_$TAG
mkdir -p $L /work/out/llama_old
rsync -a lukas:out/llama_renders/ /work/out/llama_old/
cp /work/out/llama_old/views.json $L/views.json
for g in 0 1; do
  WORLD_HDRI=/work/out/pano_llama.exr HDRI_ROT=0 ADAPT=0.004 HOLDOUT_KEEP=Llama $B -b /work/llama_$TAG.blend --python /work/scripts/bl_render_views.py -- $L/views.json $L $g 2 $g 160 CUDA 2>&1 | grep --line-buffered -E "HOLDOUT|TODO|VIEW|DONE|rror" > /work/jobs/l6_gpu$g.log &
done
wait
echo LLAMA6_RENDER_DONE
mkdir -p /tmp/l6pk && cp $L/l000?.png /tmp/l6pk/ && rsync -a /tmp/l6pk/ lukas:out/llama6_peek_$TAG/
BOX=$($B -b /work/llama_$TAG.blend --python /work/scripts/bl_llama_bbox.py 2>&1 | grep LLAMA_BOX | awk '{print $2}')
echo "llama box $BOX"
PB=$(python3 -c "b=[float(v) for v in '$BOX'.split(',')]; p=0.015; print(','.join('%.4f'%v for v in [b[0]-p,b[1]-p,max(b[2],0.7425),b[3]+p,b[4]+p,b[5]+p]))")
COMMON="--data $L --iters 25000 --refine_stop 0.6 --eval_every 5000 --holdout 25 --sh_reg 0.1 --scene_scale 0.5 --depth_mode log --depth_w 0.02 --rgba 0.3 --init_scale 0.8 --noise_stop 0.6 --reg_stop 0.6 --lr_anneal 0.6 --lr_final 0.1 --box=$PB"
(CUDA_VISIBLE_DEVICES=0 python /work/scripts/train_gs.py $COMMON --out /work/out/l6_high_$TAG --cap 250000 --init_pts 120000 > /work/jobs/l6_high.log 2>&1) &
(CUDA_VISIBLE_DEVICES=1 python /work/scripts/train_gs.py $COMMON --out /work/out/l6_mob_$TAG --cap 120000 --init_pts 80000 > /work/jobs/l6_mob.log 2>&1) &
wait
MB="-1.6967,-0.4315,0.7466,-1.6873,-0.3745,0.8746"
for T in high mob; do
  mkdir -p /work/out/r6_$T
  EXTRA_CARVE=/work/out/llama_old python /work/scripts/merge_llama.py /work/out/tr5_mob/splat.ply /work/out/l6_${T}_$TAG/splat.ply $L /work/out/r6_$T/splat.ply "$BOX" 0.7445 "$MB"
  python /work/scripts/render_splats.py --params /work/out/r6_$T/splat.ply --views /work/scripts/views_check.json --out /work/out/r6_$T/check > /dev/null 2>&1
done
python /work/scripts/render_splats.py --params /work/out/l6_high_$TAG/splat.ply --views /work/scripts/views_check.json --out /work/out/r6_llamaonly/check > /dev/null 2>&1
rsync -a --exclude '*.ply' --exclude params.pt /work/out/r6_high /work/out/r6_mob /work/out/r6_llamaonly lukas:out/
rsync -a --exclude params.pt --exclude '*.ply' /work/out/l6_high_$TAG /work/out/l6_mob_$TAG lukas:out/
bash /work/scripts/pkg_final.sh r6_high room-high-v6 3
bash /work/scripts/pkg_final.sh r6_mob room-mobile-v6 3
echo LLAMA6_ALL_DONE
