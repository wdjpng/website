#!/bin/bash
# package.sh <run_name_high> <run_name_mobile>
set -e
export PATH=~/opt/node-v22.21.0-linux-x64/bin:$PATH
HIGH=$1; MOB=$2
W=~/room/work/pkg; mkdir -p $W
rsync -a lukas:room-stage/out/$HIGH/splat.ply $W/high_raw.ply
rsync -a lukas:room-stage/out/$MOB/splat.ply $W/mobile_raw.ply
. ~/room/.venv/bin/activate
# recentre on the room (Blender coords) so float16 centres keep mm precision; viewer adds the offset back
python ~/room/scripts/ply_offset.py $W/high_raw.ply $W/high.ply 0 -0.965 -1.41
python ~/room/scripts/ply_offset.py $W/mobile_raw.ply $W/mobile.ply 0 -0.965 -1.41
cd ~/room/tools
npx splat-transform -w -g cpu $W/high.ply -N ~/room/web/public/assets/room-high.sog
npx splat-transform -w -g cpu $W/mobile.ply -N -H 2 ~/room/web/public/assets/room-mobile.sog
ls -la ~/room/web/public/assets/
