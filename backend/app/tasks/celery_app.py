"""
PARWA Celery Application (BC-004)

Celery app configuration with Redis broker, task serialization,
and 7 specialized queues for different workloads.

Day 16 additions:
- Dead Letter Queue (DLQ) for permanently failed tasks
- Beat scheduler configuration for periodic tasks
- Celery health check integration

M-32 FIX:
- Task payload size limit (1 MB max)
- Worker memory and task count limits

Task ID 6 FIX:
- Proper DLQ routing with Celery Queue/Exchange objects
- task_default_queue renamed to parwa_default
- parwa_dlq queue with no consumers (inspection only)
- task_acks_late + task_reject_on_worker_lost route failed tasks to DLQ

Queues:
- parwa_default: General tasks (account export, data cleanup)
- ai_heavy: Heavy AI tasks (embedding generation, batch classification)
- ai_light: Light AI tasks (single classification, sentiment analysis)
- email: Email sending via Brevo (BC-006)
- webhook: Webhook processing (BC-003)
- analytics: Analytics aggregation and reporting
- training: Model training and fine-tuning
- parwa_dlq: Dead Letter Queue for failed tasks (no consumers, inspection only)
"""

import logging
import json

from celery import Celery
from kombu import Queue, Exchange
from celery.signals import before_task_publish

# M-32: Maximum allowed task payload size in bytes (1 MB)
MAX_TASK_PAYLOAD_BYTES = 1 * 1024 * 1024

logger = logging.getLogger("celery_app")

# ── Create Celery app (lazy config — settings loaded at runtime) ────

app = Celery("parwa")

# ── Queue definitions ──────────────────────────────────────────────

# All queue names for reference and validation
QUEUE_NAMES = [
    "parwa_default",
    "ai_heavy",
    "ai_light",
    "email",
    "webhook",
    "analytics",
    "training",
    "parwa_dlq",  # Dead Letter Queue for permanently failed tasks (no consumers)
]

# ── Exchange definitions ──────────────────────────────────────────

# Default exchange — all tasks route through here
_default_exchange = Exchange("parwa_default", type="direct")

# DLQ exchange — no consumers; messages here are for inspection only
_dlq_exchange = Exchange("parwa_dlq", type="direct")

# ── Queue objects with routing keys ──────────────────────────────

TASK_QUEUES = (
    Queue(
        "parwa_default",
        exchange=_default_exchange,
        routing_key="parwa_default",
        queue_arguments={"x-dead-letter-exchange": "parwa_dlq"},
    ),
    Queue(
        "ai_heavy",
        exchange=Exchange("ai_heavy", type="direct"),
        routing_key="ai_heavy",
        queue_arguments={"x-dead-letter-exchange": "parwa_dlq"},
    ),
    Queue(
        "ai_light",
        exchange=Exchange("ai_light", type="direct"),
        routing_key="ai_light",
        queue_arguments={"x-dead-letter-exchange": "parwa_dlq"},
    ),
    Queue(
        "email",
        exchange=Exchange("email", type="direct"),
        routing_key="email",
        queue_arguments={"x-dead-letter-exchange": "parwa_dlq"},
    ),
    Queue(
        "webhook",
        exchange=Exchange("webhook", type="direct"),
        routing_key="webhook",
        queue_arguments={"x-dead-letter-exchange": "parwa_dlq"},
    ),
    Queue(
        "analytics",
        exchange=Exchange("analytics", type="direct"),
        routing_key="analytics",
        queue_arguments={"x-dead-letter-exchange": "parwa_dlq"},
    ),
    Queue(
        "training",
        exchange=Exchange("training", type="direct"),
        routing_key="training",
        queue_arguments={"x-dead-letter-exchange": "parwa_dlq"},
    ),
    # DLQ: no consumers, inspection only. Failed tasks land here via
    # x-dead-letter-exchange when task_acks_late=True and
    # task_reject_on_worker_lost=True.
    Queue(
        "parwa_dlq",
        exchange=_dlq_exchange,
        routing_key="parwa_dlq",
    ),
)

# ── Lazy configuration from Settings ──────────────────────────────


class LazySettings:
    """Lazy proxy that reads from PARWA Settings on first access."""

    _settings = None

    def __getattr__(self, name):
        if self._settings is None:
            from app.config import get_settings
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
        # CRITICAL for DLQ: acks_late + reject_on_worker_lost
        # When both are True, a task that fails or whose worker dies
        # is rejected and routed to the DLQ via x-dead-letter-exchange.
        "task_acks_late": True,
        "task_reject_on_worker_lost": True,
        "task_soft_time_limit": settings.CELERY_TASK_SOFT_TIME_LIMIT,
        "task_time_limit": settings.CELERY_TASK_TIME_LIMIT,
        # M-32 FIX: Limit task payload size to 1 MB to prevent oversized payloads
        # that can overwhelm workers or be used for denial-of-service attacks.
        "worker_max_tasks_per_child": 1000,
        "worker_max_memory_per_child": 200_000,  # 200MB per worker
        # Serialization
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        # Timezone
        "timezone": "UTC",
        "enable_utc": True,
        # Default queue — renamed to parwa_default for namespace clarity
        "task_default_queue": "parwa_default",
        "task_default_exchange": "parwa_default",
        "task_default_routing_key": "parwa_default",
        # Task queues — proper Queue objects with DLQ routing
        "task_queues": TASK_QUEUES,
        # Task routing
        "task_routes": {
            "app.tasks.email.*": {"queue": "email"},
            "app.tasks.email_channel.*": {"queue": "email"},
            "app.tasks.webhook.*": {"queue": "webhook"},
            "app.tasks.analytics.*": {"queue": "analytics"},
            "app.tasks.ai.heavy.*": {"queue": "ai_heavy"},
            "app.tasks.ai.light.*": {"queue": "ai_light"},
            "app.tasks.training.*": {"queue": "training"},
            # Phase 2.4: Jarvis Awareness Engine task routing
            "app.tasks.jarvis_awareness_tasks.*": {"queue": "parwa_default"},
            # Catch-all: route any unmatched tasks to default
            "app.tasks.*": {"queue": "parwa_default"},
        },
        # Day 16: Beat scheduler (periodic tasks)
        "beat_schedule": {
            "cleanup-stale-sessions-daily": {
                "task": "app.tasks.periodic.cleanup_stale_sessions",
                "schedule": 86400.0,  # Every 24 hours
                "kwargs": {},
            },
            "purge-dead-letter-queue-hourly": {
                "task": ("app.tasks.periodic"
                          ".purge_dead_letter_queue"),
                "schedule": 3600.0,  # Every hour
                "kwargs": {},
            },
            "check-webhook-health-every-5min": {
                "task": ("app.tasks.periodic"
                          ".check_webhook_health"),
                "schedule": 300.0,  # Every 5 minutes
                "kwargs": {},
            },
            "flush-audit-queue": {
                "task": ("app.tasks.periodic"
                          ".flush_audit_queue"),
                "schedule": 60.0,  # Every 60 seconds
                "kwargs": {},
            },
            "cleanup-audit-trail": {
                "task": ("app.tasks.periodic"
                          ".cleanup_audit_trail"),
                "schedule": {
                    # Daily at 03:00 UTC
                    "hour": 3,
                    "minute": 0,
                },
                "kwargs": {},
            },
            # Day 22: New Beat schedule entries
            "approval-timeout-check-every-15min": {
                "task": ("app.tasks.periodic"
                          ".approval_timeout_check"),
                "schedule": 900.0,
                "kwargs": {},
            },
            "approval-reminder-every-30min": {
                "task": ("app.tasks.periodic"
                          ".approval_reminder_dispatch"),
                "schedule": 1800.0,
                "kwargs": {},
            },
            "daily-overage-charge-02utc": {
                "task": ("app.tasks.periodic"
                          ".daily_overage_charge"),
                "schedule": {"hour": 2, "minute": 0},
                "kwargs": {},
            },
            "drift-detection-daily-03utc": {
                "task": ("app.tasks.periodic"
                          ".drift_detection_analysis"),
                "schedule": {"hour": 3, "minute": 30},
                "kwargs": {},
            },
            "metric-aggregation-every-5min": {
                "task": ("app.tasks.periodic"
                          ".metric_aggregation"),
                "schedule": 300.0,
                "kwargs": {},
            },
            "training-mistake-check-hourly": {
                "task": ("app.tasks.periodic"
                          ".training_mistake_check"),
                "schedule": 3600.0,
                "kwargs": {},
            },
            # Week 8: AI Engine beat schedule entries
            "ai-rebalance-workload-60s": {
                "task": ("app.tasks.ai_engine_tasks"
                          ".rebalance_workload"),
                "schedule": 60.0,
                "kwargs": {},
            },
            "ai-reset-daily-budgets-midnight": {
                "task": ("app.tasks.ai_engine_tasks"
                          ".reset_daily_budgets"),
                "schedule": {"hour": 0, "minute": 0},
                "kwargs": {},
            },
            "ai-cleanup-injection-logs-daily": {
                "task": ("app.tasks.ai_engine_tasks"
                          ".cleanup_stale_injection_logs"),
                "schedule": {"hour": 4, "minute": 0},
                "kwargs": {"days": 90},
            },
            # Week 13 Day 3: Email channel beat schedule entries
            "cleanup-expired-ooo-profiles-hourly": {
                "task": ("app.tasks.periodic"
                          ".cleanup_expired_ooo_profiles"),
                "schedule": 3600.0,  # Every hour
                "kwargs": {},
            },
            "retry-soft-bounces-every-2h": {
                "task": ("app.tasks.periodic"
                          ".retry_soft_bounces"),
                "schedule": 7200.0,  # Every 2 hours
                "kwargs": {},
            },
            # Phase 2.4: Jarvis Awareness Engine beat schedule
            "jarvis-awareness-tick-30s": {
                "task": ("app.tasks.jarvis_awareness_tasks"
                          ".run_awareness_ticks_all"),
                "schedule": 30.0,  # Every 30 seconds
                "kwargs": {},
            },
            "jarvis-awareness-prune-6h": {
                "task": ("app.tasks.jarvis_awareness_tasks"
                          ".prune_awareness_data"),
                "schedule": 21600.0,  # Every 6 hours
                "kwargs": {},
            },
            # CROSS-6: Token blacklist safety-net cleanup (hourly)
            "cleanup-token-blacklist-hourly": {
                "task": ("app.tasks.periodic"
                          ".cleanup_token_blacklist"),
                "schedule": 3600.0,  # Every hour
                "kwargs": {},
            },
            # Phase 6: Redis Key Namespace Audit & Cleanup
            "redis-audit-hourly": {
                "task": ("app.tasks.redis_cleanup_tasks"
                          ".audit_redis_keys_task"),
                "schedule": 3600.0,  # Every hour
                "kwargs": {},
            },
            "redis-fix-ttls-daily-0315utc": {
                "task": ("app.tasks.redis_cleanup_tasks"
                          ".cleanup_expired_keys_task"),
                "schedule": {"hour": 3, "minute": 15},
                "kwargs": {"dry_run": False},
            },
            "redis-cleanup-orphans-weekly": {
                "task": ("app.tasks.redis_cleanup_tasks"
                          ".cleanup_orphaned_keys_task"),
                "schedule": 604800.0,  # Weekly
                "kwargs": {"dry_run": True},
            },
            # Billing reconciliation and maintenance tasks
            "billing-reconcile-all-companies-daily-05utc": {
                "task": ("app.tasks.billing_tasks"
                          ".reconcile_all_companies"),
                "schedule": {"hour": 5, "minute": 0},
                "kwargs": {},
            },
            "billing-process-dead-letter-queue-6h": {
                "task": ("app.tasks.billing_tasks"
                          ".process_dead_letter_queue"),
                "schedule": 21600.0,  # Every 6 hours
                "kwargs": {},
            },
            "billing-cleanup-old-webhook-events-daily-07utc": {
                "task": ("app.tasks.billing_tasks"
                          ".cleanup_old_webhook_events"),
                "schedule": {"hour": 7, "minute": 0},
                "kwargs": {},
            },
        },
        # Day 16: Task send events for monitoring
        "task_send_sent_event": True,
        "task_track_started": True,
        # Autodiscover
        "imports": [
            "app.tasks.example_tasks",
            "app.tasks.periodic",
            "app.tasks.webhook_tasks",
            # Day 22: New task modules
            "app.tasks.email_tasks",
            "app.tasks.analytics_tasks",
            "app.tasks.ai_tasks",
            "app.tasks.training_tasks",
            "app.tasks.approval_tasks",
            "app.tasks.billing_tasks",
            # Week 8: AI Engine task module
            "app.tasks.ai_engine_tasks",
            # Week 13 Day 3: Email channel task module
            "app.tasks.email_channel_tasks",
            # Phase 2.4: Jarvis Awareness Engine tasks
            "app.tasks.jarvis_awareness_tasks",
            # Phase 6: Redis Key Namespace Audit & Cleanup
            "app.tasks.redis_cleanup_tasks",
            # Missing task modules — SLA, self-healing, Jarvis commands,
            # ticket lifecycle, tickets, notifications, knowledge,
            # reconciliation, usage, payment failure, events, SMS,
            # workflow, and health check
            "app.tasks.sla_tasks",
            "app.tasks.self_healing_tasks",
            "app.tasks.jarvis_command_tasks",
            "app.tasks.ticket_lifecycle_tasks",
            "app.tasks.ticket_tasks",
            "app.tasks.notification_tasks",
            "app.tasks.knowledge_tasks",
            "app.tasks.reconciliation_tasks",
            "app.tasks.usage_tasks",
            "app.tasks.payment_failure_tasks",
            "app.tasks.event_tasks",
            "app.tasks.sms_tasks",
            "app.tasks.workflow_tasks",
            "app.tasks.celery_health",
        ],
    }


# M-32 FIX: Pre-dispatch hook that rejects oversized task payloads.
# This prevents workers from being overwhelmed by large payloads that
# could cause memory exhaustion or denial-of-service attacks.
@before_task_publish.connect
def _enforce_max_payload_size(sender=None, headers=None, body=None, **kwargs):
    """Reject task publication if payload exceeds MAX_TASK_PAYLOAD_BYTES."""
    try:
        if body:
            payload_bytes = len(json.dumps(body) if not isinstance(body, (str, bytes)) else body)
            if payload_bytes > MAX_TASK_PAYLOAD_BYTES:
                logger.warning(
                    "task_payload_rejected_oversized task=%s payload_bytes=%s max_bytes=%s",
                    sender, payload_bytes, MAX_TASK_PAYLOAD_BYTES,
                )
                # Return False to prevent the task from being published
                return False
    except Exception as exc:
        logger.error(
            "payload_size_check_failed task=%s error=%s",
            sender, str(exc),
        )
    # Return None (or omit return) to allow normal dispatch


# Apply configuration
app.config_from_object(_build_config())

# ── Autodiscover tasks ────────────────────────────────────────────
app.autodiscover_tasks(["app.tasks"])
