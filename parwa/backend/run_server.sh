#!/bin/bash
cd /home/z/my-project/parwa/backend
source .venv/bin/activate
unset DATABASE_URL
unset ENVIRONMENT
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 10000
