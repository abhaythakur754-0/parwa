#!/usr/bin/env python
"""
PARWA Celery Worker — Production Entry Point (Day 16)

Starts a Celery worker with all PARWA queues.

Usage:
    # Default worker (all queues)
    python scripts/run_worker.py

    # Specific queues only
    python scripts/run_worker.py -Q webhook,email

    # With concurrency
    python scripts/run_worker.py -c 4

    # With auto-reload (development)
    python scripts/run_worker.py --autoreload

BC-004: Worker configuration from environment/settings.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set required env vars if not set (development defaults)
os.environ.setdefault("ENVIRONMENT", "development")

if __name__ == "__main__":
    from backend.app.tasks.celery_app import app

    app.worker_main([
        "worker",
        "--loglevel=info",
        "--queues=default,webhook,email,analytics",
        "--max-tasks-per-child=1000",  # Prevent memory leaks
        "--without-heartbeat",  # Let broker handle liveness
    ])
