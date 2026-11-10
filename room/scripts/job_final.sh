#!/bin/bash
# wait for the extra views and the depth-weight test, pick the depth weight, then build v5
set -x
while ! grep -q UP_DONE /work/jobs/up.log 2>/dev/null || ! grep -q EXP3_DONE /work/jobs/exp3.log 2>/dev/null; do sleep 15; done
DW=$(python3 - <<'PY'
import re
def last(p):
    l = [x for x in open(p) if x.startswith('EVAL step 30000')][-1]
    return float(re.search(r'psnr ([\d.]+)', l).group(1)), float(re.search(r'flat_blotch ([\d.]+)', l).group(1))
p4, b4 = last('/work/jobs/e4.log'); p5, b5 = last('/work/jobs/e5.log')
print('0.2' if (p5 >= p4 - 0.05 and b5 <= b4) else '0.1')
PY
)
echo "depth weight $DW"
export RECIPE="--iters 36000 --sh_reg 0.1 --depth_w $DW --noise_stop 0.6 --reg_stop 0.6 --lr_anneal 0.6 --lr_final 0.1"
bash /work/scripts/job_v5.sh
