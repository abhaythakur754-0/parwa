"""
Celery Worker Health Check Server (F6)

HTTP health check server running within the Celery worker process.
Provides endpoints for:
- /health - Overall health status
- /ready - Readiness probe
- /metrics - Prometheus-style metrics

Port: 8001 (configurable via WORKER_HEALTH_PORT env var)

This enables proper health checks in docker-compose and Kubernetes.
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional
import psutil

logger = logging.getLogger("parwa.worker_health")

# Configuration
WORKER_HEALTH_PORT = int(os.getenv("WORKER_HEALTH_PORT", "8001"))
WORKER_HEALTH_HOST = os.getenv("WORKER_HEALTH_HOST", "0.0.0.0")


@dataclass
class WorkerHealthStatus:
    """Health status of the Celery worker."""

    # Core status
    status: str = "healthy"  # healthy, degraded, unhealthy
    uptime_seconds: float = 0.0

    # Celery status
    broker_connected: bool = False
    heartbeat_active: bool = False
    active_tasks: int = 0
    reserved_tasks: int = 0
    queue_depth: int = 0

    # Resource metrics
    memory_usage_mb: float = 0.0
    memory_percent: float = 0.0
    cpu_percent: float = 0.0

    # Task stats
    total_tasks_processed: int = 0
    total_tasks_failed: int = 0
    last_task_completed_at: str = ""

    # Timestamps
    started_at: str = ""
    checked_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class WorkerHealthTracker:
    """Tracks worker health metrics."""

    _instance: Optional["WorkerHealthTracker"] = None

    def __init__(self):
        """Initialize health tracker."""
        self._start_time = time.time()
        self._broker_connected = False
        self._heartbeat_active = False
        self._active_tasks = 0
        self._reserved_tasks = 0
        self._queue_depth = 0
        self._total_tasks_processed = 0
        self._total_tasks_failed = 0
        self._last_task_completed_at = ""

    @classmethod
    def get_instance(cls) -> "WorkerHealthTracker":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_broker_connected(self, connected: bool) -> None:
        """Update broker connection status."""
        self._broker_connected = connected

    def set_heartbeat_active(self, active: bool) -> None:
        """Update heartbeat status."""
        self._heartbeat_active = active

    def set_active_tasks(self, count: int) -> None:
        """Update active task count."""
        self._active_tasks = count

    def set_reserved_tasks(self, count: int) -> None:
        """Update reserved task count."""
        self._reserved_tasks = count

    def set_queue_depth(self, depth: int) -> None:
        """Update queue depth."""
        self._queue_depth = depth

    def record_task_completed(self) -> None:
        """Record a completed task."""
        self._total_tasks_processed += 1
        self._last_task_completed_at = datetime.now(timezone.utc).isoformat()

    def record_task_failed(self) -> None:
        """Record a failed task."""
        self._total_tasks_failed += 1

    def get_status(self) -> WorkerHealthStatus:
        """Get current health status."""
        # Get resource metrics
        process = psutil.Process()
        memory_info = process.memory_info()

        # Determine overall status
        status = "healthy"
        if not self._broker_connected:
            status = "unhealthy"
        elif not self._heartbeat_active:
            status = "degraded"

        return WorkerHealthStatus(
            status=status,
            uptime_seconds=time.time() - self._start_time,
            broker_connected=self._broker_connected,
            heartbeat_active=self._heartbeat_active,
            active_tasks=self._active_tasks,
            reserved_tasks=self._reserved_tasks,
            queue_depth=self._queue_depth,
            memory_usage_mb=memory_info.rss / (1024 * 1024),
            memory_percent=process.memory_percent(),
            cpu_percent=process.cpu_percent(),
            total_tasks_processed=self._total_tasks_processed,
            total_tasks_failed=self._total_tasks_failed,
            last_task_completed_at=self._last_task_completed_at,
            started_at=datetime.fromtimestamp(
                self._start_time, tz=timezone.utc
            ).isoformat(),
            checked_at=datetime.now(timezone.utc).isoformat(),
        )


class WorkerHealthHandler(BaseHTTPRequestHandler):
    """HTTP request handler for worker health endpoints."""

    # Suppress default logging
    def log_message(self, format, *args):
        logger.debug("%s - %s", self.address_string(), format % args)

    def _send_json_response(
            self, data: Dict[str, Any], status: int = 200) -> None:
        """Send JSON response."""
        response = json.dumps(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(response))
        self.end_headers()
        self.wfile.write(response.encode())

    def do_GET(self) -> None:
        """Handle GET requests."""
        tracker = WorkerHealthTracker.get_instance()

        if self.path == "/health":
            status = tracker.get_status()
            http_status = 200 if status.status != "unhealthy" else 503
            self._send_json_response(status.to_dict(), http_status)

        elif self.path == "/ready":
            status = tracker.get_status()
            # Ready if broker connected
            ready = status.broker_connected
            self._send_json_response(
                {"ready": ready, "broker_connected": status.broker_connected},
                200 if ready else 503,
            )

        elif self.path == "/metrics":
            self._send_prometheus_metrics(tracker.get_status())

        elif self.path == "/":
            # Root endpoint
            self._send_json_response({
                "service": "parwa-worker-health",
                "endpoints": ["/health", "/ready", "/metrics"],
            })

        else:
            self._send_json_response({"error": "Not found"}, 404)

    def _send_prometheus_metrics(self, status: WorkerHealthStatus) -> None:
        """Send Prometheus-style metrics."""
        metrics = """# HELP parwa_worker_uptime_seconds Worker uptime in seconds
# TYPE parwa_worker_uptime_seconds gauge
parwa_worker_uptime_seconds {status.uptime_seconds}

# HELP parwa_worker_active_tasks Number of active tasks
# TYPE parwa_worker_active_tasks gauge
parwa_worker_active_tasks {status.active_tasks}

# HELP parwa_worker_queue_depth Queue depth
# TYPE parwa_worker_queue_depth gauge
parwa_worker_queue_depth {status.queue_depth}

# HELP parwa_worker_memory_mb Memory usage in MB
# TYPE parwa_worker_memory_mb gauge
parwa_worker_memory_mb {status.memory_usage_mb}

# HELP parwa_worker_cpu_percent CPU usage percent
# TYPE parwa_worker_cpu_percent gauge
parwa_worker_cpu_percent {status.cpu_percent}

# HELP parwa_worker_tasks_processed_total Total tasks processed
# TYPE parwa_worker_tasks_processed_total counter
parwa_worker_tasks_processed_total {status.total_tasks_processed}

# HELP parwa_worker_tasks_failed_total Total tasks failed
# TYPE parwa_worker_tasks_failed_total counter
parwa_worker_tasks_failed_total {status.total_tasks_failed}

# HELP parwa_worker_broker_connected Broker connection status
# TYPE parwa_worker_broker_connected gauge
parwa_worker_broker_connected {1 if status.broker_connected else 0}

# HELP parwa_worker_heartbeat_active Heartbeat status
# TYPE parwa_worker_heartbeat_active gauge
parwa_worker_heartbeat_active {1 if status.heartbeat_active else 0} """

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", len(metrics))
        self.end_headers()
        self.wfile.write(metrics.encode())


class WorkerHealthServer:
    """
    HTTP health check server for Celery workers.

    Runs in a background thread within the worker process.
    """

    def __init__(self, port: int = WORKER_HEALTH_PORT,
                 host: str = WORKER_HEALTH_HOST):
        """Initialize health server."""
        self._port = port
        self._host = host
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """Start the health server in a background thread."""
        if self._running:
            return

        try:
            self._server = HTTPServer(
                (self._host, self._port), WorkerHealthHandler)
            self._thread = threading.Thread(
                target=self._run_server, daemon=True)
            self._thread.start()
            self._running = True

            logger.info(
                "Worker health server started on http://%s:%d",
                self._host, self._port,
            )

        except OSError as e:
            logger.warning(
                "Failed to start health server on port %d: %s",
                self._port, e,
            )

    def _run_server(self) -> None:
        """Run the HTTP server loop."""
        try:
            self._server.serve_forever()
        except Exception as e:
            logger.error("Health server error: %s", e)
            self._running = False

    def stop(self) -> None:
        """Stop the health server."""
        if self._server:
            self._server.shutdown()
            self._running = False
            logger.info("Worker health server stopped")

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running


# Singleton server instance
_health_server: Optional[WorkerHealthServer] = None


def start_worker_health_server() -> WorkerHealthServer:
    """Start the worker health check server."""
    global _health_server

    if _health_server is None:
        _health_server = WorkerHealthServer()
        _health_server.start()

    return _health_server


def stop_worker_health_server() -> None:
    """Stop the worker health check server."""
    global _health_server

    if _health_server:
        _health_server.stop()
        _health_server = None


def get_worker_health_tracker() -> WorkerHealthTracker:
    """Get the worker health tracker instance."""
    return WorkerHealthTracker.get_instance()
