#!/bin/bash
# build the llama (bl_llama_v6.py) at full quality and render the studio comparison shots
# usage: bash job_studio.sh TAG [QUALITY] [SPP]
set -x
TAG=$1; Q=${2:-1.0}; SPP=${3:-128}
export CUDA_CACHE_MAXSIZE=4294967296
B=/work/opt/blender-4.5.15-linux-x64/blender
while [ ! -x $B ]; do sleep 10; done
$B -b /work/in/cr-3/outputs/bedroom_reconstruction.blend --python /work/scripts/bl_llama_v6.py -- /work/llama_$TAG.blend /work/scripts/magnet_rectified.png $Q 2>&1 | grep -E "fleece|SAVED|rror|Traceback"
SHOTS=face_left34,head_side,full_34 $B -b /work/llama_$TAG.blend --python /work/scripts/bl_llama_studio.py -- /work/out/studio_$TAG 0 $SPP 720 2>&1 | grep -E "SHOT|rror" &
SHOTS=face_right34,head_back34,front $B -b /work/llama_$TAG.blend --python /work/scripts/bl_llama_studio.py -- /work/out/studio_$TAG 1 $SPP 720 2>&1 | grep -E "SHOT|rror" &
wait
rsync -a /work/out/studio_$TAG lukas:out/
echo STUDIO_DONE $TAG
