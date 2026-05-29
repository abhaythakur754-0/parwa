#!/usr/bin/env python3
"""Daemon script to start the PARWA backend as a proper background process."""
import os
import sys
import time

def main():
    # Set environment variables
    os.environ["PYTHONPATH"] = "/home/z/my-project/parwa:/home/z/my-project/parwa/backend"
    os.environ["ENVIRONMENT"] = "development"
    os.environ["DATABASE_URL"] = "sqlite:////home/z/my-project/parwa/db/custom.db"
    os.environ["SECRET_KEY"] = "test_secret_key_for_integration_testing_12345"
    os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_integration_testing_12345"
    os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"
    os.environ["PRICING_SIGNING_KEY"] = "test_pricing_signing_key_1234567890"
    os.environ["REDIS_URL"] = ""
    os.environ["REFRESH_TOKEN_PEPPER"] = "test_refresh_pepper_for_integration_testing"
    os.environ["CSRF_TRUSTED_ORIGINS"] = "http://localhost:3000,http://127.0.0.1:3000"
    os.environ["CORS_ORIGINS"] = '["http://localhost:3000"]'
    os.environ["FRONTEND_URL"] = "http://localhost:3000"

    # Double-fork to properly daemonize
    pid = os.fork()
    if pid > 0:
        # Parent: wait for child to set up, then exit
        time.sleep(2)
        sys.exit(0)

    # First child: become session leader
    os.setsid()

    pid2 = os.fork()
    if pid2 > 0:
        sys.exit(0)

    # Second child: the actual daemon
    # Redirect stdio
    sys.stdout.flush()
    sys.stderr.flush()
    log_file = open("/tmp/parwa_backend.log", "w")
    os.dup2(log_file.fileno(), 1)
    os.dup2(log_file.fileno(), 2)

    # Write PID file
    with open("/tmp/parwa_backend.pid", "w") as f:
        f.write(str(os.getpid()))

    # Change to project directory
    os.chdir("/home/z/my-project/parwa")

    # Create database tables if they don't exist
    try:
        sys.path.insert(0, "/home/z/my-project/parwa")
        sys.path.insert(0, "/home/z/my-project/parwa/backend")
        from database.base import Base
        from sqlalchemy import create_engine
        engine = create_engine(os.environ["DATABASE_URL"])
        Base.metadata.create_all(bind=engine)
        print(f"Database tables created/verified at {os.environ['DATABASE_URL']}")
    except Exception as e:
        print(f"Warning: Could not create tables: {e}")

    # Exec uvicorn
    os.execvp(sys.executable, [
        sys.executable, "-m", "uvicorn",
        "backend.app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--log-level", "error"
    ])

if __name__ == "__main__":
    main()
