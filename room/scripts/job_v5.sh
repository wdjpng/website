#!/bin/bash
# v5: retrain both room models with the cleaner-wall recipe ($RECIPE), merge the llama detail models, package
# usage: RECIPE="..." bash job_v5.sh
set -x
. /work/venv/bin/activate
L=/work/out/llama
COMMON="--data /work/out/v3 /work/out/v5x --refine_stop 0.6 --eval_every 10000 --holdout 50 --scene_scale 1.0 --depth_mode log --alpha_w 0.05 --pano /work/out/pano/pano.png --pano_cfg /work/scripts/pano_cfg.json $RECIPE"
(CUDA_VISIBLE_DEVICES=0 python /work/scripts/train_gs.py $COMMON --out /work/out/tr5_high --cap 1500000 --init_pts 700000 > /work/jobs/tr5_high.log 2>&1) &
(CUDA_VISIBLE_DEVICES=1 python /work/scripts/train_gs.py $COMMON --out /work/out/tr5_mob --cap 1000000 --init_pts 500000 > /work/jobs/tr5_mob.log 2>&1) &
wait
BOX="-1.8735,-0.3740,0.7424,-1.6219,-0.1716,1.0097"
MB="-1.6967,-0.4315,0.7466,-1.6873,-0.3745,0.8746"
for T in high mob; do
  mkdir -p /work/out/tr5m_$T
  python /work/scripts/merge_llama.py /work/out/tr5_$T/splat.ply /work/out/llama_$T/splat.ply $L /work/out/tr5m_$T/splat.ply "$BOX" 0.7445 "$MB"
  python /work/scripts/render_splats.py --params /work/out/tr5m_$T/splat.ply --views /work/scripts/views_check.json /work/scripts/views_wall.json --out /work/out/tr5m_$T/check > /dev/null 2>&1
done
rsync -a --exclude '*.ply' --exclude params.pt /work/out/tr5_high /work/out/tr5_mob /work/out/tr5m_high /work/out/tr5m_mob lukas:out/
bash /work/scripts/pkg_final.sh tr5m_high room-high-v5 3
bash /work/scripts/pkg_final.sh tr5m_mob room-mobile-v5 3
echo V5_ALL_DONE
