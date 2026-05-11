#!/usr/bin/env python
"""
PARWA Celery Beat Scheduler — Production Entry Point (Day 16)

Starts the Celery Beat scheduler for periodic tasks.

Periodic tasks:
- cleanup_stale_sessions: Every 24 hours
- purge_dead_letter_queue: Every 1 hour
- check_webhook_health: Every 5 minutes

Usage:
    python scripts/run_beat.py

BC-004: Beat schedule configured in celery_app.py.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ENVIRONMENT", "development")

if __name__ == "__main__":
    from backend.app.tasks.celery_app import app

    app.worker_main([
        "beat",
        "--loglevel=info",
        "--scheduler=celery.beat:PersistentScheduler",
    ])
