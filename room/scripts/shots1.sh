#!/bin/bash
# shots1.sh <quality> <outdir> <baseurl> <poses.json> : browser screenshots at given poses, viewport = W x H at pixel ratio 1
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
    ab('set', 'viewport', str(p['W']), str(p['H']))
    ab('open', f"{base}?q={q}&pr=1&debugpose={p['pose']}", t=180)
    for _ in range(100):
        if 'true' in ab('eval', 'document.getElementById("loader").classList.contains("done")', t=30): break
        time.sleep(3)
    time.sleep(8)
    ab('eval', 'document.getElementById("hud").hidden=true; document.getElementById("hint") && (document.getElementById("hint").style.display="none")', t=30)
    time.sleep(2)
    ab('screenshot', f'{out}/{name}.png', t=180)
    print('shot', name, flush=True)
PY
