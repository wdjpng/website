#!/bin/bash
# room light probe at the llama + alignment check of the panorama as world lighting
set -x
B=/work/opt/blender-4.5.15-linux-x64/blender; export CUDA_CACHE_MAXSIZE=4294967296
TAG=${1:-e}
$B -b /work/llama_$TAG.blend --python /work/scripts/bl_render_pano_at.py -- /work/out/pano_llama.exr 0 -1.715 -0.272 0.89 1024 2048 2>&1 | grep -E "PANO|rror"
mkdir -p /work/out/hdri_chk
HIDE_PREFIX=Llama $B -b /work/llama_$TAG.blend --python /work/scripts/bl_render_views.py -- /work/out/views_t6.json /work/out/hdri_chk/room 1 1 0 64 CUDA 2>&1 | grep -E "VIEW|rror" &
for R in 0 90 180 270; do
  SHOW_WORLD=1 WORLD_HDRI=/work/out/pano_llama.exr HDRI_ROT=$R HOLDOUT_KEEP=NothingMatches $B -b /work/llama_$TAG.blend --python /work/scripts/bl_render_views.py -- /work/out/views_t6.json /work/out/hdri_chk/rot$R 0 1 0 32 CUDA 2>&1 | grep -E "VIEW|WORLD|rror"
done
wait
rsync -a --exclude "*.exr" /work/out/hdri_chk lukas:out/
echo HDRI_DONE
