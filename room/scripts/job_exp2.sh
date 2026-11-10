#!/bin/bash
# round 2: + learning-rate annealing; + stronger depth
set -x
while ! grep -q ENV_DONE /work/jobs/env.log 2>/dev/null || ! grep -q DATA_DONE /work/jobs/data.log 2>/dev/null; do sleep 15; done
. /work/venv/bin/activate
COMMON="--data /work/out/v3 --iters 30000 --refine_stop 0.6 --eval_every 10000 --holdout 50 --sh_reg 0.1 --scene_scale 1.0 --depth_mode log --alpha_w 0.05 --pano /work/out/pano/pano.png --pano_cfg /work/scripts/pano_cfg.json --cap 1000000 --init_pts 500000 --noise_stop 0.6 --reg_stop 0.6 --lr_anneal 0.6 --lr_final 0.1"
(CUDA_VISIBLE_DEVICES=0 python /work/scripts/train_gs.py $COMMON --depth_w 0.03 --out /work/out/e3 > /work/jobs/e3.log 2>&1) &
(CUDA_VISIBLE_DEVICES=1 python /work/scripts/train_gs.py $COMMON --depth_w 0.1 --out /work/out/e4 > /work/jobs/e4.log 2>&1) &
wait
for E in e3 e4; do python /work/scripts/render_splats.py --params /work/out/$E/params.pt --views /work/scripts/views_wall.json /work/scripts/views_check.json --out /work/out/$E/check > /dev/null 2>&1; done
rsync -a --exclude '*.ply' --exclude params.pt /work/out/e3 /work/out/e4 lukas:out/exps/
echo EXP2_DONE
