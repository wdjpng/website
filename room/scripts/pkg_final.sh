#!/bin/bash
# runs on the GPU node: package trained splats into SOG files for the web viewer
set -e
export PATH=/work/opt/node-v22.21.0-linux-x64/bin:$PATH XDG_RUNTIME_DIR=/tmp
. /work/venv/bin/activate
mkdir -p /work/pkg /work/pkg_out
RUN=$1; NAME=$2; SH=${3:-3}
python /work/scripts/ply_offset.py /work/out/$RUN/splat.ply /work/pkg/$NAME.off.ply 0 -0.965 -1.41
if [ "$SH" != "3" ]; then python /work/scripts/ply_sh.py /work/pkg/$NAME.off.ply /work/pkg/$NAME.ply $SH; else mv /work/pkg/$NAME.off.ply /work/pkg/$NAME.ply; fi
cd /work/tools && npx splat-transform -w -g 0 /work/pkg/$NAME.ply -N /work/pkg_out/$NAME.sog 2>&1 | tail -3
rsync -a /work/pkg_out/$NAME.sog lukas:out/pkg/
echo PKG_DONE $NAME
