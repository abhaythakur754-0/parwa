#!/bin/bash
LOG=/home/z/my-project/.watch/push_status.log
echo "$(date -u +%H:%M:%S) watcher v3 started (4 commits, every 60s, max 2h)" > $LOG
cd /home/z/my-project
for i in $(seq 1 120); do
  if ! timeout 20 git ls-remote https://github.com/abhaythakur754-0/parwa.git main >/dev/null 2>&1; then
    echo "$(date -u +%H:%M:%S) repo PRIVATE detected - pushing" >> $LOG
    rm -rf /home/z/my-project/.watch/push-wt
    git worktree add /home/z/my-project/.watch/push-wt fb3aa7d >> $LOG 2>&1 || { echo "WORKTREE FAIL" >> $LOG; exit 1; }
    cd /home/z/my-project/.watch/push-wt
    for C in 8064f33 72f891b 82a2ab0 98e6060; do
      git cherry-pick $C >> $LOG 2>&1 || { echo "CHERRY-PICK FAIL: $C" >> $LOG; exit 1; }
    done
    HEADHASH=$(git rev-parse --short HEAD)
    git grep -q "sg_fbde45884a601f06d4d10a6d9300eb546223c2784ca66f0b" HEAD -- backend/app/core/superglue_client.py || { echo "SANITY FAIL: sg token" >> $LOG; exit 1; }
    git grep -q "bld_16983ffb226ec89575dea48c5b6ee245cc56ebb649ae04b5" HEAD -- backend/app/core/remote_builder_client.py || { echo "SANITY FAIL: bld key" >> $LOG; exit 1; }
    git grep -q "p11668uhxhd1-d.space-z.ai" HEAD -- backend/app/core/remote_builder_client.py || { echo "SANITY FAIL: builder URL" >> $LOG; exit 1; }
    echo "sanity OK: all credentials + new URL present in $HEADHASH" >> $LOG
    if git push https://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@github.com/abhaythakur754-0/parwa.git HEAD:main >> $LOG 2>&1; then
      REMOTE=$(timeout 20 git ls-remote https://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@github.com/abhaythakur754-0/parwa.git main 2>/dev/null | cut -c1-7)
      echo "PUSHED $HEADHASH remote_main=$REMOTE - DONE" >> $LOG
    else
      echo "PUSH FAILED" >> $LOG
    fi
    exit 0
  fi
  echo "$(date -u +%H:%M:%S) attempt $i/120: still public" >> $LOG
  sleep 60
done
echo "WATCHER EXHAUSTED (2h) - still public" >> $LOG
