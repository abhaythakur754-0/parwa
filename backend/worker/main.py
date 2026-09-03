#!/usr/bin/env python
"""
PARWA Celery Worker — Production Entry Point

Starts a Celery worker with all PARWA queues.
This module is the entry point used by worker.Dockerfile:
    CMD ["python", "-m", "backend.worker.main"]

Queues (must match QUEUE_NAMES in app/tasks/celery_app.py):
    parwa_default — General tasks
    ai_heavy      — Heavy AI workloads (DSPy, LangGraph)
    ai_light      — Light AI workloads (classification, sentiment)
    email         — Email sending (Brevo)
    webhook       — Webhook processing (Shopify, Twilio, Brevo)
    analytics     — Analytics aggregation
    training      — Model training tasks
    parwa_dlq     — Dead Letter Queue (failed-task quarantine)
"""

import os
import sys

# Ensure project root is on Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set required env vars with safe defaults for container startup
os.environ.setdefault("ENVIRONMENT", "production")


def main():
    """Start the Celery worker with all PARWA queues."""
    from app.tasks.celery_app import QUEUE_NAMES, app as celery_app

    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        # All queues defined by the app (parwa_default, ai_heavy, ai_light,
        # email, webhook, analytics, training, parwa_dlq) — imported from
        # celery_app so this list can never drift from the broker config.
        f"--queues={','.join(QUEUE_NAMES)}",
        # Prevent memory leaks from long-running tasks
        "--max-tasks-per-child=1000",
        # Let broker handle liveness (reduces noise in logs)
        "--without-heartbeat",
    ])


if __name__ == "__main__":
    main()
