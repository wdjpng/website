#!/bin/bash
# wait for the extra views, then build v5 with the best tested recipe (E4: depth 0.1 + lr anneal + late noise/reg off)
set -x
while ! grep -q UP_DONE /work/jobs/up.log 2>/dev/null; do sleep 15; done
export RECIPE="--iters 36000 --sh_reg 0.1 --depth_w 0.1 --noise_stop 0.6 --reg_stop 0.6 --lr_anneal 0.6 --lr_final 0.1"
bash /work/scripts/job_v5.sh
