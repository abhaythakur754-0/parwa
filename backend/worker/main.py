"""
PARWA Background Worker — Main entry point.

Starts the Celery worker to process background tasks:
- Email notifications
- AI pipeline jobs
- Periodic health checks
- Webhook processing
- Billing tasks
"""

import logging
import sys

logger = logging.getLogger("parwa.worker")


def main():
    """Start the Celery worker."""
    logger.info("PARWA worker starting...")

    try:
        from backend.app.tasks.celery_app import app as celery_app

        # Start Celery worker with concurrency
        celery_app.worker_main(
            argv=[
                "worker",
                "--loglevel=info",
                "--concurrency=2",
                "--max-tasks-per-child=100",
                "--queues=default,ai,email,billing",
            ]
        )
    except ImportError as exc:
        logger.error("Failed to import Celery app: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error("Worker failed to start: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
