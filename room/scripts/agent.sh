#!/bin/bash
# GPU-side job agent: polls the server (restricted rsync key) for queued job scripts, runs them, syncs logs back.
mkdir -p /work/jobs /work/scripts /work/done /work/queue
while true; do
  rsync -a lukas:scripts/ /work/scripts/ 2>/dev/null
  rsync -a --delete lukas:queue/ /work/queue/ 2>/dev/null
  for f in /work/queue/*.sh; do
    [ -e "$f" ] || continue
    n=$(basename $f .sh)
    if [ ! -e /work/done/$n ]; then
      touch /work/done/$n
      cp $f /work/jobs/$n.sh
      (cd /work && setsid bash /work/jobs/$n.sh > /work/jobs/$n.log 2>&1 < /dev/null; echo "EXIT $?" >> /work/jobs/$n.log) &
    fi
  done
  nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader > /work/jobs/_gpu.txt 2>&1
  ps aux --sort=-%cpu | head -8 > /work/jobs/_ps.txt
  df -h /work | tail -1 >> /work/jobs/_ps.txt
  date -u > /work/jobs/_heartbeat
  rsync -a /work/jobs/ lukas:jobs/ 2>/dev/null
  sleep 6
done
