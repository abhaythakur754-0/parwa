#!/usr/bin/env python
"""
PARWA Celery Worker — Production Entry Point

Starts a Celery worker with all PARWA queues.
This module is the entry point used by worker.Dockerfile:
    CMD ["python", "-m", "backend.worker.main"]

Queues:
    default    — General tasks
    ai_heavy   — Heavy AI workloads (DSPy, LangGraph)
    ai_light   — Light AI workloads (classification, sentiment)
    email      — Email sending (Brevo)
    webhook    — Webhook processing (Paddle, Shopify, Twilio)
    analytics  — Analytics aggregation
    training   — Model training tasks
    knowledge  — Knowledge base tasks (indexing, reindexing, DSPy optimization)
    dead_letter — Failed task quarantine
"""

import os
import sys

# Ensure project root is on Python path
sys.path.insert(
    0, os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)))))

# Set required env vars with safe defaults for container startup
os.environ.setdefault("ENVIRONMENT", "production")


def main():
    """Start the Celery worker with all PARWA queues."""
    from backend.app.tasks.celery_app import app as celery_app

    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        # All 9 PARWA queues
        "--queues=default,ai_heavy,ai_light,email,webhook,analytics,training,knowledge,dead_letter",
        # Prevent memory leaks from long-running tasks
        "--max-tasks-per-child=1000",
    ])


if __name__ == "__main__":
    main()
