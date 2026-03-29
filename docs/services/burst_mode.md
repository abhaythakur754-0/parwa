# Burst Mode Service

## Overview

The Burst Mode Service manages high-volume period handling with automatic scaling, rate limiting, and resource optimization. It ensures system stability during traffic spikes.

**Location:** `services/burst_mode.py`

## Features

- **Automatic Burst Detection**: Monitor request rates and detect spikes
- **Dynamic Scaling Coordination**: Trigger scaling actions based on load
- **Rate Limiting with Backpressure**: Control request flow during high load
- **Resource Pool Management**: Manage concurrent request limits
- **Graceful Degradation**: Handle critical load scenarios
- **Recovery Handling**: Smooth transition back to normal operation

## Status Levels

| Status | RPM Range | Description |
|--------|-----------|-------------|
| `normal` | < 100 | Normal operation |
| `elevated` | 100-300 | Increased load detected |
| `burst` | 300-500 | High traffic period |
| `critical` | > 500 or high errors | System under stress |
| `recovery` | N/A | Transitioning from burst |

## API Reference

### Classes

#### `BurstModeConfig`

Configuration for Burst Mode Manager.

```python
class BurstModeConfig(BaseModel):
    # Thresholds (requests per minute)
    normal_threshold_rpm: int = 100       # Normal → Elevated
    elevated_threshold_rpm: int = 300     # Elevated → Burst
    burst_threshold_rpm: int = 500        # Burst → Critical
    critical_threshold_rpm: int = 1000    # Critical threshold
    
    # Timing
    burst_detection_window_seconds: int = 60    # Detection window
    burst_cooldown_seconds: int = 300           # Cooldown before recovery
    recovery_window_seconds: int = 180          # Recovery evaluation window
    
    # Scaling
    max_concurrent_requests: int = 100      # Normal max concurrent
    burst_max_concurrent: int = 200         # Burst max concurrent
    critical_max_concurrent: int = 50       # Critical max (reduced)
    
    # Queue
    queue_max_size: int = 1000              # Max queued requests
    queue_timeout_seconds: int = 30         # Queue wait timeout
    
    # Features
    enable_auto_scaling: bool = True        # Enable auto scaling
    enable_graceful_degradation: bool = True # Enable degradation
    enable_queue_backpressure: bool = True  # Enable backpressure
```

#### `BurstStatus`

Enum for burst status levels.

```python
class BurstStatus(str, Enum):
    NORMAL = "normal"        # Normal operation
    ELEVATED = "elevated"    # Increased load
    BURST = "burst"          # High traffic
    CRITICAL = "critical"    # System under stress
    RECOVERY = "recovery"    # Recovering from burst
```

#### `ScalingAction`

Enum for scaling actions.

```python
class ScalingAction(str, Enum):
    NONE = "none"                       # No action needed
    SCALE_UP = "scale_up"               # Scale up resources
    SCALE_DOWN = "scale_down"           # Scale down resources
    ENABLE_THROTTLING = "enable_throttling"   # Enable throttling
    DISABLE_THROTTLING = "disable_throttling" # Disable throttling
    QUEUE_REQUESTS = "queue_requests"   # Queue incoming requests
    REJECT_REQUESTS = "reject_requests" # Reject low-priority requests
```

#### `BurstEvent`

Record of a burst event.

```python
@dataclass
class BurstEvent:
    event_id: str                      # Unique event ID
    started_at: datetime               # When burst started
    ended_at: Optional[datetime]       # When burst ended
    peak_rpm: int                      # Peak requests per minute
    duration_seconds: float            # Total duration
    status_changes: List[Dict]         # Status change history
    actions_taken: List[str]           # Actions taken
    metrics_before: Optional[Dict]     # Metrics before burst
    metrics_after: Optional[Dict]      # Metrics after burst
```

### Main Class: `BurstModeManager`

#### Initialization

```python
from services.burst_mode import (
    BurstModeManager,
    BurstModeConfig,
    BurstStatus,
)

manager = BurstModeManager(
    config=BurstModeConfig(
        normal_threshold_rpm=100,
        burst_threshold_rpm=500,
    ),
    scaling_handlers={
        "on_scale_up": my_scale_up_handler,
        "on_scale_down": my_scale_down_handler,
    }
)
```

#### Methods

##### `check_request()`

Check if a request should be accepted.

```python
status = await manager.check_request(
    request_id="req_123",      # Required: Unique request ID
    company_id="company_123",  # Optional: Company identifier
    priority=0                 # Optional: Priority (higher = important)
)

if status == BurstStatus.CRITICAL:
    # Handle rejection for low-priority requests
    return {"error": "System busy, try again later"}
```

**Returns:** `BurstStatus`

##### `acquire_slot()`

Acquire a processing slot for a request.

```python
acquired = await manager.acquire_slot(
    request_id="req_123",
    timeout=30.0  # Max seconds to wait
)

if acquired:
    try:
        # Process request
        result = await process_request()
    finally:
        manager.release_slot("req_123")
else:
    # Timeout - too many concurrent requests
    return {"error": "Request timeout"}
```

**Returns:** `bool` - True if slot acquired

##### `release_slot()`

Release a processing slot.

```python
manager.release_slot(request_id="req_123")
```

##### `record_metrics()`

Record request metrics for burst detection.

```python
await manager.record_metrics({
    "request_count": 150,              # Number of requests
    "avg_response_time_ms": 250.0,     # Average response time
    "error_rate": 0.02,                # Error rate (0.0 - 1.0)
    "queue_depth": 10,                 # Current queue depth
    "active_workers": 5,               # Number of active workers
})
```

##### `get_current_status()`

Get current burst status.

```python
status = manager.get_current_status()
# Returns: BurstStatus.NORMAL, BurstStatus.BURST, etc.
```

##### `get_status_duration()`

Get duration of current status in seconds.

```python
duration = manager.get_status_duration()
# Returns: 120.5 (seconds)
```

##### `get_metrics_summary()`

Get summary of current metrics.

```python
summary = manager.get_metrics_summary()
# Returns:
# {
#     "current_status": "burst",
#     "status_since": "2024-01-15T10:00:00Z",
#     "status_duration_seconds": 120.5,
#     "current_rpm": 450,
#     "error_rate": 0.02,
#     "active_requests": 150,
#     "max_concurrent": 200,
#     "queue_depth": 25,
# }
```

##### `get_burst_history()`

Get history of burst events.

```python
history = manager.get_burst_history(limit=10)
# Returns:
# [
#     {
#         "event_id": "burst_abc123",
#         "started_at": "2024-01-15T10:00:00Z",
#         "ended_at": "2024-01-15T10:15:00Z",
#         "peak_rpm": 650,
#         "duration_seconds": 900,
#         "actions_taken": ["scale_up", "enable_throttling"],
#     },
#     ...
# ]
```

##### `register_scaling_handler()`

Register a handler for a scaling action.

```python
async def on_scale_up(event: dict):
    # Scale up resources
    await kubernetes.scale_deployment("api", replicas=5)

manager.register_scaling_handler(
    ScalingAction.SCALE_UP,
    on_scale_up
)
```

##### `force_status()`

Force a specific status (for testing or maintenance).

```python
await manager.force_status(
    status=BurstStatus.BURST,
    reason="Load testing"
)
```

##### `get_stats()`

Get comprehensive statistics.

```python
stats = manager.get_stats()
```

##### `get_config()`

Get current configuration.

```python
config = manager.get_config()
```

## Configuration Options

### Thresholds

| Option | Default | Description |
|--------|---------|-------------|
| `normal_threshold_rpm` | 100 | RPM threshold for normal → elevated |
| `elevated_threshold_rpm` | 300 | RPM threshold for elevated → burst |
| `burst_threshold_rpm` | 500 | RPM threshold for burst → critical |
| `critical_threshold_rpm` | 1000 | Critical RPM threshold |

### Timing

| Option | Default | Description |
|--------|---------|-------------|
| `burst_detection_window_seconds` | 60 | Window for RPM calculation |
| `burst_cooldown_seconds` | 300 | Cooldown before recovery |
| `recovery_window_seconds` | 180 | Recovery evaluation window |

### Concurrency

| Option | Default | Description |
|--------|---------|-------------|
| `max_concurrent_requests` | 100 | Max concurrent in normal mode |
| `burst_max_concurrent` | 200 | Max concurrent in burst mode |
| `critical_max_concurrent` | 50 | Max concurrent in critical mode |

### Queue

| Option | Default | Description |
|--------|---------|-------------|
| `queue_max_size` | 1000 | Maximum queued requests |
| `queue_timeout_seconds` | 30 | Max wait time in queue |

## Usage Examples

### Basic Usage

```python
from services.burst_mode import BurstModeManager, BurstStatus

manager = BurstModeManager()

async def handle_request(request_id: str):
    # Check if request should be accepted
    status = await manager.check_request(request_id)
    
    if status == BurstStatus.CRITICAL:
        # System under stress - reject
        return {"error": "Service temporarily unavailable"}
    
    # Acquire processing slot
    if not await manager.acquire_slot(request_id):
        return {"error": "Request timeout - too many concurrent requests"}
    
    try:
        # Process the request
        result = await process_request(request_id)
        
        # Record metrics
        await manager.record_metrics({
            "request_count": 1,
            "avg_response_time_ms": result.response_time,
        })
        
        return result
    finally:
        manager.release_slot(request_id)
```

### With Scaling Handlers

```python
from services.burst_mode import BurstModeManager, ScalingAction

async def scale_up_handler(event: dict):
    """Handle scale up event."""
    print(f"Scaling up! Current RPM: {event['rpm']}")
    await kubernetes.scale("api-server", replicas=10)
    await alerting.notify("Burst mode activated")

async def scale_down_handler(event: dict):
    """Handle scale down event."""
    print(f"Scaling down. Current RPM: {event['rpm']}")
    await kubernetes.scale("api-server", replicas=3)

async def enable_throttling_handler(event: dict):
    """Handle throttling enable event."""
    print("Enabling request throttling")
    await rate_limiter.set_limit(100)  # 100 req/s

async def disable_throttling_handler(event: dict):
    """Handle throttling disable event."""
    print("Disabling request throttling")
    await rate_limiter.set_limit(1000)  # 1000 req/s

manager = BurstModeManager(
    scaling_handlers={
        "on_scale_up": scale_up_handler,
        "on_scale_down": scale_down_handler,
        "on_enable_throttling": enable_throttling_handler,
        "on_disable_throttling": disable_throttling_handler,
    }
)
```

### Monitoring Burst Status

```python
import asyncio

async def monitor_burst_status(manager: BurstModeManager):
    """Background task to monitor burst status."""
    while True:
        summary = manager.get_metrics_summary()
        
        if summary["current_status"] != "normal":
            print(f"⚠️ Status: {summary['current_status']}")
            print(f"  RPM: {summary['current_rpm']}")
            print(f"  Active: {summary['active_requests']}/{summary['max_concurrent']}")
            print(f"  Queue: {summary['queue_depth']}")
        
        await asyncio.sleep(10)
```

### Priority-Based Request Handling

```python
async def handle_request_with_priority(request, manager):
    """Handle requests with priority-based admission."""
    priority = get_request_priority(request)  # 0-100
    request_id = request.id
    
    # Check if request should be accepted
    status = await manager.check_request(
        request_id=request_id,
        priority=priority
    )
    
    if status == BurstStatus.CRITICAL and priority < 50:
        # Reject low-priority during critical load
        return {
            "status": "rejected",
            "reason": "low_priority_during_critical",
            "retry_after": 60
        }
    
    # Process normally
    return await process_request(request)
```

### Graceful Degradation

```python
async def handle_with_degradation(request, manager):
    """Handle request with graceful degradation."""
    status = manager.get_current_status()
    
    if status == BurstStatus.CRITICAL:
        # Minimal processing during critical load
        return await minimal_response(request)
    
    elif status == BurstStatus.BURST:
        # Reduced features during burst
        return await reduced_response(request)
    
    elif status == BurstStatus.ELEVATED:
        # Slightly reduced features
        return await standard_response(request)
    
    else:
        # Full features in normal mode
        return await full_response(request)
```

### Background Metrics Collection

```python
async def collect_metrics(manager: BurstModeManager):
    """Collect and report metrics periodically."""
    while True:
        # Collect system metrics
        metrics = {
            "request_count": await get_request_count(),
            "avg_response_time_ms": await get_avg_response_time(),
            "error_rate": await get_error_rate(),
            "queue_depth": manager._request_queue.qsize(),
            "active_workers": len(manager._active_requests),
        }
        
        await manager.record_metrics(metrics)
        await asyncio.sleep(5)
```

## Status Transitions

```
                    ┌─────────────────────────────────────┐
                    │                                     │
                    ▼                                     │
┌─────────┐    ┌─────────┐    ┌───────┐    ┌──────────┐  │
│ NORMAL  │───▶│ELEVATED │───▶│ BURST │───▶│ CRITICAL │  │
└─────────┘    └─────────┘    └───────┘    └──────────┘  │
     ▲                              │              │      │
     │                              │              │      │
     └──────────────────────────────┴──────────────┘      │
                    RECOVERY                               │
                    └──────────────────────────────────────┘
```

### Transition Triggers

| From | To | Trigger |
|------|-----|---------|
| Normal | Elevated | RPM > 100 |
| Elevated | Burst | RPM > 300 |
| Burst | Critical | RPM > 500 or error rate > 50% |
| Critical | Recovery | RPM < 500 and error rate < 50% |
| Burst | Recovery | RPM < 300 |
| Elevated | Normal | RPM < 100 |
| Recovery | Normal | RPM < 100 for recovery window |

## Best Practices

1. **Monitor regularly**: Check status frequently during operation
2. **Use priorities**: Mark important requests with higher priority
3. **Implement handlers**: Register scaling handlers for automatic response
4. **Set appropriate thresholds**: Match thresholds to your system capacity
5. **Handle rejections gracefully**: Return proper error responses
6. **Record metrics**: Feed metrics back into the system
7. **Plan for recovery**: Implement smooth transition back to normal

## Integration Points

- **API Gateway**: Request admission control
- **Kubernetes**: Pod scaling coordination
- **Rate Limiter**: Throttling integration
- **Alerting**: Notification on status changes
- **Monitoring**: Prometheus metrics export
