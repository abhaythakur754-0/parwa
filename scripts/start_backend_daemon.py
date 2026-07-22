#!/usr/bin/env python3
"""True daemon launcher for the PARWA backend."""
import os, sys, subprocess
from pathlib import Path

BACKEND_DIR = Path("/home/z/my-project/parwa/backend")
VENV_PYTHON = BACKEND_DIR / "venv" / "bin" / "python"
LOG_FILE = "/tmp/backend.log"
PID_FILE = "/tmp/backend.pid"

if os.fork() > 0: sys.exit(0)
os.setsid()
if os.fork() > 0: sys.exit(0)

env = os.environ.copy()
env.pop("DATABASE_URL", None)
env["PYTHONUNBUFFERED"] = "1"

log_fd = os.open(LOG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
os.dup2(log_fd, 1); os.dup2(log_fd, 2); os.close(log_fd)
devnull = os.open("/dev/null", os.O_RDONLY)
os.dup2(devnull, 0); os.close(devnull)

proc = subprocess.Popen(
    [str(VENV_PYTHON), "-m", "uvicorn", "app.main:app",
     "--host", "127.0.0.1", "--port", "8000", "--no-access-log"],
    cwd=str(BACKEND_DIR), env=env, close_fds=True,
)
with open(PID_FILE, "w") as f: f.write(str(proc.pid))
