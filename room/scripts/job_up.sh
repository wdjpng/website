#!/bin/bash
# extra training views looking level-to-up (ceiling, upper walls, doors), rendered with the current scene
set -x
export CUDA_CACHE_MAXSIZE=4294967296
B=/work/opt/blender-4.5.15-linux-x64/blender
while ! grep -q DATA_DONE /work/jobs/data.log 2>/dev/null; do sleep 10; done
[ -f /work/bedroom_v4b.blend ] || rsync -a lukas:out/bedroom_v4b.blend /work/
mkdir -p /work/out/v5x && cp /work/scripts/views_up.json /work/out/v5x/views.json
for g in 0 1; do
  $B -b /work/bedroom_v4b.blend --python /work/scripts/bl_render_views.py -- /work/out/v5x/views.json /work/out/v5x $g 2 $g 128 CUDA 2>&1 | grep --line-buffered -E "TODO|VIEW|DONE|rror" > /work/jobs/up_gpu$g.log &
done
wait
ls /work/out/v5x/*.png | wc -l
echo UP_DONE
