#!/usr/bin/env python3
"""
PARWA Backend Server Daemon
Runs the backend as a persistent process with a PID file.
"""
import os
import sys
import signal
import time

# Change to backend directory
os.chdir('/home/z/my-project/parwa/backend')

# Activate venv
venv_path = '/home/z/my-project/parwa/backend/venv/bin/activate_this.py'
if os.path.exists(venv_path):
    exec(open(venv_path).read(), {'__file__': venv_path})

# Write PID file
pid_file = '/tmp/parwa_backend.pid'
with open(pid_file, 'w') as f:
    f.write(str(os.getpid()))

print(f"PARWA Backend starting on port 8000 (PID: {os.getpid()})", flush=True)

# Import and run uvicorn
import uvicorn

# Signal handler for graceful shutdown
def shutdown(signum, frame):
    print("Shutting down...", flush=True)
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

uvicorn.run(
    'app.main:app',
    host='0.0.0.0',
    port=8000,
    log_level='debug',
)
