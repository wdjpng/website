#!/bin/bash
# compare.sh <quality> <outdir> [baseurl]: browser screenshots at the eval camera poses, side by side with Cycles renders
Q=$1; OUT=$2; BASE=${3:-http://127.0.0.1:5173/}
S=${BROWSER_SESSION:-local-927568e58092}
mkdir -p $OUT
. ~/room/.venv/bin/activate
python3 - "$Q" "$OUT" "$BASE" "$S" <<'PY'
import json, subprocess, sys, time
q, out, base, S = sys.argv[1:5]
poses = json.load(open('/home/muenzel_lukas/room/work/eval_poses.json'))
for name, p in poses.items():
    import os
    if not os.path.exists(f'/home/muenzel_lukas/room/work/eval/{name}.png'):
        continue
    W, H = p['W'] // 2, p['H'] // 2
    subprocess.run(['agent-browser', '--session', S, 'set', 'viewport', str(W), str(H)], capture_output=True)
    subprocess.run(['agent-browser', '--session', S, 'open', f"{base}?q={q}&pr=2&debugpose={p['pose']}"], capture_output=True)
    for _ in range(60):
        r = subprocess.run(['agent-browser', '--session', S, 'eval', 'document.getElementById("loader").classList.contains("done")'], capture_output=True, text=True)
        if 'true' in r.stdout: break
        time.sleep(2)
    time.sleep(4)
    subprocess.run(['agent-browser', '--session', S, 'screenshot', f'{out}/{name}_web.png'], capture_output=True)
    print('shot', name, flush=True)
PY
python3 - "$OUT" <<'PY'
import sys, glob, os
from PIL import Image
out = sys.argv[1]
for f in sorted(glob.glob(out + '/*_web.png')):
    name = os.path.basename(f)[:-8]
    a = Image.open(f'/home/muenzel_lukas/room/work/eval/{name}.png').convert('RGB')
    b = Image.open(f).convert('RGB').resize(a.size, Image.LANCZOS)
    s = Image.new('RGB', (a.width * 2 + 16, a.height), (20, 20, 20)); s.paste(a, (0, 0)); s.paste(b, (a.width + 16, 0))
    s.save(f'{out}/{name}_cmp.jpg', quality=90)
    print('cmp', name)
PY
