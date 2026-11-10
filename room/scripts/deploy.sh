#!/bin/bash
# build the viewer and publish it to https://munzel.com/room/
set -e
export PATH=~/opt/node-v22.21.0-linux-x64/bin:$PATH
cd ~/room/web
rm -rf dist && npx vite build
# drop test assets
rm -f dist/assets/test.spz dist/assets/trtest*.ply dist/assets/trtest*.sog
python3 - <<'PY'
import json, os, hashlib
p = 'dist/assets/room.json'; m = json.load(open(p))
for k in list(m['splats']):
    f = 'dist/assets/' + m['splats'][k]['file']
    if not os.path.exists(f):
        del m['splats'][k]; continue
    m['splats'][k]['bytes'] = os.path.getsize(f)
    h = hashlib.sha1(open(f, 'rb').read()).hexdigest()[:10]
    m['splats'][k]['file'] = m['splats'][k]['file'] + '?v=' + h
json.dump(m, open(p, 'w'))
print(m['splats'])
PY
rsync -av --delete dist/ lukas:/var/www/html/room/
echo DEPLOYED
