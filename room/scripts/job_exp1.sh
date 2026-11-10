#!/bin/bash
# wall-quality A/B: baseline recipe vs. late noise/regulariser switch-off (1.0M splats)
set -x
while ! grep -q ENV_DONE /work/jobs/env.log 2>/dev/null || ! grep -q DATA_DONE /work/jobs/data.log 2>/dev/null; do sleep 15; done
. /work/venv/bin/activate
COMMON="--data /work/out/v3 --iters 30000 --refine_stop 0.6 --eval_every 10000 --holdout 50 --sh_reg 0.1 --scene_scale 1.0 --depth_mode log --depth_w 0.03 --alpha_w 0.05 --pano /work/out/pano/pano.png --pano_cfg /work/scripts/pano_cfg.json --cap 1000000 --init_pts 500000"
(CUDA_VISIBLE_DEVICES=0 python /work/scripts/train_gs.py $COMMON --out /work/out/e1 > /work/jobs/e1.log 2>&1) &
(CUDA_VISIBLE_DEVICES=1 python /work/scripts/train_gs.py $COMMON --noise_stop 0.6 --reg_stop 0.6 --out /work/out/e2 > /work/jobs/e2.log 2>&1) &
wait
echo EXP1_DONE
