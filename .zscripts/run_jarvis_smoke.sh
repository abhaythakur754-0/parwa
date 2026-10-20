#!/bin/bash
# Jarvis CLI live-wiring smoke test: boot backend + register user + run executor test, ONE command
set -u
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy 2>/dev/null

cd /home/z/my-project/backend
if [ ! -f local_smoke.db ]; then
  DATABASE_URL="sqlite:////home/z/my-project/backend/local_smoke.db" \
    /home/z/.venv/bin/python -c "
import sys; sys.path.insert(0, '/home/z/my-project/backend')
from database.models import *  # noqa: F401,F403
from database.base import init_db
init_db()
print('schema ok')
" || { echo "SCHEMA FAIL"; exit 3; }
fi

DATABASE_URL="sqlite:////home/z/my-project/backend/local_smoke.db" \
  setsid /home/z/.venv/bin/python -m uvicorn app.main:app --port 10000 > /tmp/jarvis_smoke_server.log 2>&1 &
SRV=$!

for i in $(seq 1 45); do
  sleep 2
  CODE=$(curl -s --noproxy '*' -o /dev/null -w "%{http_code}" http://127.0.0.1:10000/health 2>/dev/null)
  [ "$CODE" = "200" ] && echo "SERVER HEALTHY (~$((i*2))s)" && break
done
[ "$CODE" = "200" ] || { echo "SERVER NOT HEALTHY"; tail -10 /tmp/jarvis_smoke_server.log; kill $SRV 2>/dev/null; exit 2; }

RUN=$(date +%s)
REG=$(curl -s --noproxy '*' -X POST http://127.0.0.1:10000/api/auth/register \
  -H "Content-Type: application/json" -H "Origin: http://localhost:3000" \
  -d "{\"email\":\"jarvis-${RUN}@localtest.parwa\",\"password\":\"JarvisSmoke#2026x\",\"confirm_password\":\"JarvisSmoke#2026x\",\"full_name\":\"Jarvis Smoke\",\"company_name\":\"Jarvis Smoke ${RUN}\",\"industry\":\"ecommerce\"}")
TOKEN=$(echo "$REG" | python3 -c "
import json,sys
d=json.load(sys.stdin); t=d.get('tokens') or {}
print(d.get('access_token') or d.get('token') or t.get('access_token') or t.get('token') or '')" 2>/dev/null)
if [ -z "$TOKEN" ]; then
  LOGIN=$(curl -s --noproxy '*' -X POST http://127.0.0.1:10000/api/auth/login \
    -H "Content-Type: application/json" -H "Origin: http://localhost:3000" \
    -d "{\"email\":\"jarvis-${RUN}@localtest.parwa\",\"password\":\"JarvisSmoke#2026x\"}")
  TOKEN=$(echo "$LOGIN" | python3 -c "
import json,sys
d=json.load(sys.stdin); t=d.get('tokens') or {}
print(d.get('access_token') or d.get('token') or t.get('access_token') or t.get('token') or '')" 2>/dev/null)
fi
[ -n "$TOKEN" ] || { echo "NO TOKEN"; echo "$REG" | head -c 300; kill $SRV 2>/dev/null; exit 4; }
echo "TOKEN OK (${#TOKEN} chars)"

cd /home/z/my-project
PARWA_API_URL=http://127.0.0.1:10000 PARWA_API_TOKEN="$TOKEN" PARWA_ORIGIN=http://localhost:3000 \
  node jarvis-cli/live_test.mjs
EC=$?

kill $SRV 2>/dev/null; sleep 1; pkill -f "uvicorn app.main:app --port 10000" 2>/dev/null
exit $EC
