#!/bin/bash
# Publish the walkable room to https://munzel.com/room/.
# It is not part of the Jekyll build (`room` is in _config.yml exclude:), so publish.sh never touches it.
#   bash room/deploy.sh            upload dist/ as it is (the committed live build)
#   bash room/deploy.sh --build    rebuild dist/ from web/ first (needs Node 20+)
set -e
R="$(cd "$(dirname "$0")" && pwd)"
if [ "$1" = "--build" ]; then
  cd "$R/web"
  [ -d node_modules ] || npm ci
  rm -rf dist && npx vite build
  # cache-busting: room.json points at the splat files with ?v=<content hash>
  python3 - <<'PY'
import json, os, hashlib
p = 'dist/assets/room.json'; m = json.load(open(p))
for k in list(m['splats']):
    f = 'dist/assets/' + m['splats'][k]['file']
    if not os.path.exists(f):
        del m['splats'][k]; continue
    m['splats'][k]['bytes'] = os.path.getsize(f)
    m['splats'][k]['file'] += '?v=' + hashlib.sha1(open(f, 'rb').read()).hexdigest()[:10]
json.dump(m, open(p, 'w'))
PY
  rm -rf "$R/dist" && cp -R dist "$R/dist" && rm -rf dist
fi
rsync -av --delete "$R/dist/" lukas:/var/www/html/room/
echo "published https://munzel.com/room/"
