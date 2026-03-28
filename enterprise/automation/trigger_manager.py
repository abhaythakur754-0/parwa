"""Trigger Manager Module - Week 57, Builder 4"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import logging
import json

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    EVENT = "event"
    MANUAL = "manual"
    THRESHOLD = "threshold"


@dataclass
class Trigger:
    name: str
    trigger_type: TriggerType
    action: Callable
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_fired: Optional[datetime] = None
    fire_count: int = 0


class TriggerManager:
    def __init__(self):
        self._triggers: Dict[str, Trigger] = {}

    def register(self, trigger: Trigger) -> None:
        self._triggers[trigger.name] = trigger

    def unregister(self, name: str) -> bool:
        return self._triggers.pop(name, None) is not None

    def fire(self, name: str, context: Dict = None) -> Any:
        trigger = self._triggers.get(name)
        if not trigger or not trigger.enabled:
            return None

        result = trigger.action(**(context or {}))
        trigger.last_fired = datetime.utcnow()
        trigger.fire_count += 1
        return result

    def enable(self, name: str) -> bool:
        trigger = self._triggers.get(name)
        if trigger:
            trigger.enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        trigger = self._triggers.get(name)
        if trigger:
            trigger.enabled = False
            return True
        return False

    def list_triggers(self) -> List[str]:
        return list(self._triggers.keys())


class WebhookHandler:
    def __init__(self):
        self._endpoints: Dict[str, Callable] = {}
        self._logs: List[Dict] = []

    def register(self, path: str, handler: Callable) -> None:
        self._endpoints[path] = handler

    def handle(self, path: str, payload: Dict, headers: Dict = None) -> Any:
        handler = self._endpoints.get(path)
        if not handler:
            self._logs.append({"path": path, "status": "not_found", "timestamp": datetime.utcnow()})
            return {"error": "Endpoint not found"}

        try:
            result = handler(payload, headers or {})
            self._logs.append({"path": path, "status": "success", "timestamp": datetime.utcnow()})
            return result
        except Exception as e:
            self._logs.append({"path": path, "status": "error", "error": str(e), "timestamp": datetime.utcnow()})
            return {"error": str(e)}

    def get_logs(self, limit: int = 100) -> List[Dict]:
        return self._logs[-limit:]


class Scheduler:
    def __init__(self):
        self._jobs: Dict[str, Dict] = {}

    def schedule(self, job_id: str, job: Callable, interval_seconds: int, start_time: datetime = None) -> None:
        self._jobs[job_id] = {
            "job": job,
            "interval": interval_seconds,
            "next_run": start_time or datetime.utcnow(),
            "runs": 0
        }

    def tick(self) -> List[str]:
        now = datetime.utcnow()
        executed = []

        for job_id, job_data in self._jobs.items():
            if job_data["next_run"] <= now:
                try:
                    job_data["job"]()
                    job_data["runs"] += 1
                    job_data["next_run"] = datetime.utcnow()
                    executed.append(job_id)
                except Exception as e:
                    logger.error(f"Job {job_id} failed: {e}")

        return executed

    def cancel(self, job_id: str) -> bool:
        return self._jobs.pop(job_id, None) is not None

    def list_jobs(self) -> List[str]:
        return list(self._jobs.keys())

    def get_next_run(self, job_id: str) -> Optional[datetime]:
        return self._jobs.get(job_id, {}).get("next_run")
