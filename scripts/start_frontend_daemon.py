#!/usr/bin/env python3
"""True daemon launcher for the PARWA frontend (Next.js dev server)."""
import os, sys, subprocess
from pathlib import Path

PROJECT_DIR = Path("/home/z/my-project/parwa")
LOG_FILE = "/tmp/frontend.log"
PID_FILE = "/tmp/frontend.pid"

if os.fork() > 0: sys.exit(0)
os.setsid()
if os.fork() > 0: sys.exit(0)

env = os.environ.copy()
env["NODE_ENV"] = "development"
env["PORT"] = "3000"

log_fd = os.open(LOG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
os.dup2(log_fd, 1); os.dup2(log_fd, 2); os.close(log_fd)
devnull = os.open("/dev/null", os.O_RDONLY)
os.dup2(devnull, 0); os.close(devnull)

proc = subprocess.Popen(["npm", "run", "dev"], cwd=str(PROJECT_DIR), env=env, close_fds=True)
with open(PID_FILE, "w") as f: f.write(str(proc.pid))
