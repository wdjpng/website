#!/bin/bash
# shots.sh <quality> <outdir> <baseurl> <poses.json> : browser screenshots at given poses (debugpose)
Q=$1; OUT=$2; BASE=$3; POSES=$4
S=${BROWSER_SESSION}
mkdir -p $OUT
python3 - "$Q" "$OUT" "$BASE" "$S" "$POSES" <<'PY'
import json, subprocess, sys, time
q, out, base, S, posef = sys.argv[1:6]
poses = json.load(open(posef))
def ab(*a, t=60):
    try:
        return subprocess.run(['agent-browser', '--session', S] + list(a), capture_output=True, text=True, timeout=t).stdout
    except subprocess.TimeoutExpired:
        return ''
for name, p in poses.items():
    W, H = p['W'] // 2, p['H'] // 2
    ab('set', 'viewport', str(W), str(H))
    ab('open', f"{base}?q={q}&pr=2&debugpose={p['pose']}", t=120)
    for _ in range(60):
        if 'true' in ab('eval', 'document.getElementById("loader").classList.contains("done")', t=30): break
        time.sleep(3)
    time.sleep(6)
    ab('screenshot', f'{out}/{name}.png', t=120)
    print('shot', name, flush=True)
PY
