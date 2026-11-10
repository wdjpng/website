#!/bin/bash
# round 3: depth weight 0.2 (E4 used 0.1)
set -x
while ! grep -q EXP2_DONE /work/jobs/exp2.log 2>/dev/null; do sleep 15; done
. /work/venv/bin/activate
COMMON="--data /work/out/v3 --iters 30000 --refine_stop 0.6 --eval_every 10000 --holdout 50 --sh_reg 0.1 --scene_scale 1.0 --depth_mode log --alpha_w 0.05 --pano /work/out/pano/pano.png --pano_cfg /work/scripts/pano_cfg.json --cap 1000000 --init_pts 500000 --noise_stop 0.6 --reg_stop 0.6 --lr_anneal 0.6 --lr_final 0.1"
CUDA_VISIBLE_DEVICES=1 python /work/scripts/train_gs.py $COMMON --depth_w 0.2 --out /work/out/e5 > /work/jobs/e5.log 2>&1
python /work/scripts/render_splats.py --params /work/out/e5/params.pt --views /work/scripts/views_wall.json /work/scripts/views_check.json --out /work/out/e5/check > /dev/null 2>&1
rsync -a --exclude '*.ply' --exclude params.pt /work/out/e5 lukas:out/exps/
echo EXP3_DONE
