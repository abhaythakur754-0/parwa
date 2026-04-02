"""
PARWA Celery Application (BC-004)

Celery app configuration with Redis broker, task serialization,
and 7 specialized queues for different workloads.

Day 16 additions:
- Dead Letter Queue (DLQ) for permanently failed tasks
- Beat scheduler configuration for periodic tasks
- Celery health check integration

Queues:
- default: General tasks (account export, data cleanup)
- ai_heavy: Heavy AI tasks (embedding generation, batch classification)
- ai_light: Light AI tasks (single classification, sentiment analysis)
- email: Email sending via Brevo (BC-006)
- webhook: Webhook processing (BC-003)
- analytics: Analytics aggregation and reporting
- training: Model training and fine-tuning
- dead_letter: Failed tasks that exhausted all retries (Day 16)
"""

from celery import Celery

# ── Create Celery app (lazy config — settings loaded at runtime) ────

app = Celery("parwa")

# ── Queue definitions ──────────────────────────────────────────────

# All queue names for reference and validation
QUEUE_NAMES = [
    "default",
    "ai_heavy",
    "ai_light",
    "email",
    "webhook",
    "analytics",
    "training",
    "dead_letter",  # Day 16: DLQ for permanently failed tasks
]

# ── Lazy configuration from Settings ──────────────────────────────


class LazySettings:
    """Lazy proxy that reads from PARWA Settings on first access."""

    _settings = None

    def __getattr__(self, name):
        if self._settings is None:
            from backend.app.config import get_settings
            self._settings = get_settings()
        return getattr(self._settings, name)


def _build_config() -> dict:
    """Build Celery configuration dict from PARWA settings."""
    settings = LazySettings()
    return {
        # Broker and results
        "broker_url": settings.CELERY_BROKER_URL,
        "result_backend": settings.CELERY_RESULT_BACKEND,
        # Task execution
        "task_always_eager": settings.CELERY_TASK_ALWAYS_EAGER,
        "task_eager_propagates": settings.CELERY_TASK_EAGER_PROPAGATES,
        "worker_prefetch_multiplier": (
            settings.CELERY_WORKER_PREFETCH_MULTIPLIER
        ),
        "task_acks_late": settings.CELERY_TASK_ACKS_LATE,
        "task_reject_on_worker_lost": (
            settings.CELERY_TASK_REJECT_ON_WORKER_LOST
        ),
        "task_soft_time_limit": settings.CELERY_TASK_SOFT_TIME_LIMIT,
        "task_time_limit": settings.CELERY_TASK_TIME_LIMIT,
        # Serialization
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        # Timezone
        "timezone": "UTC",
        "enable_utc": True,
        # Default queue
        "task_default_queue": "default",
        # Task queues (Day 16: added dead_letter)
        "task_queues": {
            name: {"queue": name}
            for name in QUEUE_NAMES
        },
        # Task routing
        "task_routes": {
            "backend.app.tasks.email.*": {"queue": "email"},
            "backend.app.tasks.webhook.*": {"queue": "webhook"},
            "backend.app.tasks.analytics.*": {"queue": "analytics"},
            "backend.app.tasks.ai.heavy.*": {"queue": "ai_heavy"},
            "backend.app.tasks.ai.light.*": {"queue": "ai_light"},
            "backend.app.tasks.training.*": {"queue": "training"},
        },
        # Day 16: Beat scheduler (periodic tasks)
        "beat_schedule": {
            "cleanup-stale-sessions-daily": {
                "task": "backend.app.tasks.periodic.cleanup_stale_sessions",
                "schedule": 86400.0,  # Every 24 hours
                "kwargs": {},
            },
            "purge-dead-letter-queue-hourly": {
                "task": ("backend.app.tasks.periodic"
                          ".purge_dead_letter_queue"),
                "schedule": 3600.0,  # Every hour
                "kwargs": {},
            },
            "check-webhook-health-every-5min": {
                "task": ("backend.app.tasks.periodic"
                          ".check_webhook_health"),
                "schedule": 300.0,  # Every 5 minutes
                "kwargs": {},
            },
            "flush-audit-queue": {
                "task": ("backend.app.tasks.periodic"
                          ".flush_audit_queue"),
                "schedule": 60.0,  # Every 60 seconds
                "kwargs": {},
            },
            "cleanup-audit-trail": {
                "task": ("backend.app.tasks.periodic"
                          ".cleanup_audit_trail"),
                "schedule": {
                    # Daily at 03:00 UTC
                    "hour": 3,
                    "minute": 0,
                },
                "kwargs": {},
            },
        },
        # Day 16: Task send events for monitoring
        "task_send_sent_event": True,
        "task_track_started": True,
        # Autodiscover
        "imports": [
            "backend.app.tasks.example_tasks",
            "backend.app.tasks.periodic",  # Day 16
            "backend.app.tasks.webhook_tasks",
        ],
    }


# Apply configuration
app.config_from_object(_build_config())

# ── Autodiscover tasks ────────────────────────────────────────────
app.autodiscover_tasks(["backend.app.tasks"])
