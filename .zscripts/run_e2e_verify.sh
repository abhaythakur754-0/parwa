#!/bin/bash
# E2E regression runner: boot local backend + run 10-check suite + teardown, ONE command
# (sandbox reaps background daemons between shell commands)
set -u
cd /home/z/my-project/backend
rm -f local_test.db
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy 2>/dev/null

# Fresh SQLite file: create the 151-table schema BEFORE booting the API
# (server lifespan's alembic/SQL fallbacks cannot create tables on an empty DB)
DATABASE_URL="sqlite:////home/z/my-project/backend/local_test.db" \
  /home/z/.venv/bin/python -c "
import sys; sys.path.insert(0, '/home/z/my-project/backend')
from database.models import *  # noqa: F401,F403 - register all model classes
from database.base import init_db
init_db()
print('schema created')
" > /tmp/e2e_schema.log 2>&1 || { echo "SCHEMA BOOTSTRAP FAILED"; tail -5 /tmp/e2e_schema.log; exit 3; }

DATABASE_URL="sqlite:////home/z/my-project/backend/local_test.db" \
  setsid /home/z/.venv/bin/python -m uvicorn app.main:app --port 10000 > /tmp/e2e_server.log 2>&1 &
SRV=$!

HEALTHY=0
for i in $(seq 1 45); do
  sleep 2
  CODE=$(curl -s --noproxy '*' -o /dev/null -w "%{http_code}" http://127.0.0.1:10000/health 2>/dev/null)
  if [ "$CODE" = "200" ]; then HEALTHY=1; echo "SERVER HEALTHY after ~$((i*2))s"; break; fi
done

if [ "$HEALTHY" != "1" ]; then
  echo "SERVER FAILED TO BECOME HEALTHY"; tail -20 /tmp/e2e_server.log
  kill $SRV 2>/dev/null; exit 2
fi

cd /home/z/my-project
/home/z/.venv/bin/python scripts/test_local_human_replacement.py > /tmp/e2e_result.log 2>&1
EC=$?
echo "=== E2E RESULT (exit $EC) ==="
grep -E "PASS|FAIL|RESULT" /tmp/e2e_result.log | tail -14

kill $SRV 2>/dev/null
sleep 1
pkill -f "uvicorn app.main:app --port 10000" 2>/dev/null
exit $EC
