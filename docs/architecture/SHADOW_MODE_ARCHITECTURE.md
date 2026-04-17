# Shadow Mode Architecture Documentation

> **Part:** Part 11 - Shadow Mode
> **Version:** 1.0.0
> **Last Updated:** April 17, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [4-Layer Decision System](#4-layer-decision-system)
4. [Database Schema](#database-schema)
5. [API Endpoints](#api-endpoints)
6. [Channel Interceptors](#channel-interceptors)
7. [Socket.io Events](#socketio-events)
8. [Stage 0 Onboarding](#stage-0-onboarding)
9. [Dual Control Sync](#dual-control-sync)
10. [Performance Considerations](#performance-considerations)

---

## Overview

Shadow Mode is PARWA's safety system that controls how AI (Jarvis) executes actions. It provides a graduated trust model that allows managers to maintain oversight of AI operations while gradually increasing automation as confidence grows.

### Core Principles

| Principle | Description |
|-----------|-------------|
| **BC-001** | All operations are company-scoped |
| **BC-008** | Never crash the caller - defensive error handling |
| **SM-1** | Dual control is mandatory (UI + Jarvis) |
| **SM-5** | Hard safety floor is non-negotiable |
| **SM-7** | Transparent reasoning (explain WHY) |

### Three Execution Modes

| Mode | Description | Approval Required |
|------|-------------|-------------------|
| **Shadow** | All actions require manager approval | Yes (all) |
| **Supervised** | High-risk actions require approval | Yes (high risk) |
| **Graduated** | Low-risk actions auto-execute, can be undone | No (but undo available) |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                  │
├───────────────┬───────────────┬───────────────┬─────────────────────┤
│   Dashboard   │    Jarvis     │    Mobile     │    Webhook/API      │
│      UI       │     Chat      │     App       │    Integrations     │
└───────┬───────┴───────┬───────┴───────┬───────┴──────────┬──────────┘
        │               │               │                   │
        ▼               ▼               ▼                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      SHADOW MODE SERVICE                             │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                  4-LAYER DECISION ENGINE                     │    │
│  │  Layer 1: Heuristic ─▶ Layer 2: Preference ─▶               │    │
│  │  Layer 3: Historical ─▶ Layer 4: Safety Floor               │    │
│  └─────────────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│    Channels   │   │    Tickets    │   │    Jarvis     │
│  Interceptors │   │   Integration │   │   Commands    │
├───────────────┤   ├───────────────┤   ├───────────────┤
│ Email Shadow  │   │ Ticket Close  │   │ Mode Change   │
│ SMS Shadow    │   │ Ticket Escal. │   │ Preferences   │
│ Voice Shadow  │   │ Resolution    │   │ Approve/Reject│
│ Chat Shadow   │   │ Undo Flow     │   │ Undo Actions  │
└───────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DATABASE LAYER                                  │
├───────────────────┬───────────────────┬─────────────────────────────┤
│   shadow_log      │ shadow_preferences│   companies (system_mode)   │
│   undo_log        │   undo_queue      │   executed_actions          │
└───────────────────┴───────────────────┴─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     REAL-TIME EVENTS                                 │
│                    Socket.io EventEmitter                            │
├─────────────────────────────────────────────────────────────────────┤
│ shadow:action_logged │ shadow:action_approved │ shadow:mode_changed │
│ shadow:action_rejected │ shadow:action_undone │ shadow:preference_changed │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4-Layer Decision System

The heart of Shadow Mode is a 4-layer decision engine that determines whether an action requires approval.

### Layer 1: Heuristic Risk Scoring

Calculates base risk score based on action type and payload.

```python
ACTION_RISK_BASE = {
    "sms_reply": 0.3,       # Low risk
    "email_reply": 0.4,     # Medium-low
    "ticket_close": 0.2,    # Low
    "refund": 0.8,          # High
    "account_delete": 0.95, # Critical
    # ...
}

# Payload adjustments:
# - Refund > $100: +0.1 risk
# - Refund > $500: +0.2 risk
# - Email with refund mention: +0.15 risk
```

### Layer 2: Per-Category Preferences

User-defined preferences override the default mode.

```python
# Stored in shadow_preferences table
{
    "company_id": "acme-corp",
    "action_category": "refund",
    "preferred_mode": "shadow",  # Always require approval
    "set_via": "ui"  # or "jarvis"
}
```

### Layer 3: Historical Pattern Analysis

Analyzes past actions to adjust risk based on patterns.

```python
# If historical avg_risk for action_type > 0.7:
#   → Escalate to supervised mode

# Blends current risk with historical (60/40 weighted average)
blended_score = 0.6 * current_risk + 0.4 * avg_historical
```

### Layer 4: Hard Safety Floor

Certain actions ALWAYS require approval, regardless of other factors.

```python
HARD_SAFETY_ACTIONS = {
    "refund",           # Financial transactions
    "account_delete",   # Destructive operations
    "data_export",      # PII exposure risk
    "password_reset",   # Security sensitive
    "api_key_create",   # Credential issuance
}
```

### Decision Flow

```
                    ┌─────────────────────┐
                    │   Action Request    │
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Stage 0 Check     │──▶ If active: FORCE SHADOW
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  Layer 1: Heuristic │
                    │   Calculate Risk    │
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │ Layer 2: Preference │
                    │   Override?         │──▶ If set: USE PREFERENCE
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │ Layer 3: Historical │
                    │   Pattern Check     │──▶ If avg > 0.7: ESCALATE
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │ Layer 4: Safety     │
                    │   Floor Check       │──▶ If in HARD_SAFETY: FORCE APPROVAL
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Final Decision    │
                    │ mode + risk_score   │
                    └─────────────────────┘
```

---

## Database Schema

### shadow_log

Primary audit trail for all AI actions.

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(36) PK | UUID |
| company_id | VARCHAR(36) FK | Company scope (BC-001) |
| action_type | VARCHAR(50) | Type of action |
| action_payload | JSONB | Full action details |
| jarvis_risk_score | FLOAT | Computed risk (0.0-1.0) |
| mode | VARCHAR(15) | shadow/supervised/graduated |
| manager_decision | VARCHAR(15) | approved/rejected/modified |
| manager_note | TEXT | Optional note |
| resolved_at | TIMESTAMP | When decision made |
| created_at | TIMESTAMP | When logged |

**Indexes:**
- `idx_shadow_log_company` (company_id, created_at DESC)
- `idx_shadow_log_mode` (mode, manager_decision)

### shadow_preferences

Per-category mode preferences.

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(36) PK | UUID |
| company_id | VARCHAR(36) FK | Company scope |
| action_category | VARCHAR(50) | Category name |
| preferred_mode | VARCHAR(15) | shadow/supervised/graduated |
| set_via | VARCHAR(10) | ui/jarvis |
| updated_at | TIMESTAMP | Last change |

**Constraints:**
- `uq_shadow_prefs_company_category` UNIQUE (company_id, action_category)

### Companies Table Extensions

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| system_mode | VARCHAR(15) | 'supervised' | Global mode |
| undo_window_minutes | INT | 30 | Undo time limit |
| risk_threshold_shadow | FLOAT | 0.7 | Force shadow above |
| risk_threshold_auto | FLOAT | 0.3 | Auto-execute below |
| shadow_actions_remaining | INT | NULL | Stage 0 counter |

---

## API Endpoints

### Shadow Mode API (`/api/shadow`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/mode` | Get current mode |
| PUT | `/mode` | Set mode |
| GET | `/preferences` | List preferences |
| PATCH | `/preferences` | Set preference |
| DELETE | `/preferences/{category}` | Delete preference |
| POST | `/evaluate` | What-if simulator |
| GET | `/stats` | Get statistics |
| GET | `/logs` | Paginated log entries |
| GET | `/undo-history` | Undo history |
| POST | `/{id}/approve` | Approve action |
| POST | `/{id}/reject` | Reject action |
| POST | `/{id}/undo` | Undo action |
| POST | `/batch-resolve` | Batch approve/reject |

### Request/Response Examples

#### Evaluate Action Risk

```http
POST /api/shadow/evaluate
Content-Type: application/json

{
    "action_type": "refund",
    "action_payload": {
        "amount": 150.00,
        "customer_id": "cust_123",
        "reason": "Product defect"
    }
}

Response 200:
{
    "mode": "supervised",
    "risk_score": 0.72,
    "reason": "High risk: refund amount exceeds threshold",
    "requires_approval": true,
    "auto_execute": false,
    "layers": {
        "layer1_heuristic": {"score": 0.8, "reason": "Base risk refund: 0.80"},
        "layer2_preference": {"mode": null, "reason": "No per-category preference set"},
        "layer3_historical": {"avg_risk": 0.65, "reason": "Historical avg risk: 0.65"},
        "layer4_safety_floor": {"hard_safety": true, "reason": "Hard safety: ALWAYS requires approval"}
    },
    "company_mode": "supervised"
}
```

#### Set Preference

```http
PATCH /api/shadow/preferences
Content-Type: application/json

{
    "action_category": "email_reply",
    "preferred_mode": "graduated",
    "set_via": "jarvis"
}

Response 200:
{
    "id": "pref_abc123",
    "action_category": "email_reply",
    "preferred_mode": "graduated",
    "set_via": "jarvis",
    "updated_at": "2026-04-17T10:30:00Z"
}
```

---

## Channel Interceptors

Each outbound communication channel passes through shadow evaluation.

### Email Interceptor (`backend/app/interceptors/email_shadow.py`)

```python
def evaluate_email_shadow(company_id: str, email_payload: dict) -> EmailShadowResult:
    """
    Evaluates outbound email for shadow mode.
    
    Flow:
    1. Call shadow_service.evaluate_action_risk("email_reply", payload)
    2. If requires_approval: log to shadow_log, return pending status
    3. If auto_execute: send email + log to undo queue
    """
```

### SMS Interceptor (`backend/app/interceptors/sms_shadow.py`)

```python
def evaluate_sms_shadow(company_id: str, sms_payload: dict) -> SMSShadowResult:
    """
    Evaluates outbound SMS for shadow mode.
    
    SMS has lower base risk (0.3), often auto-executes in graduated mode.
    """
```

### Voice Interceptor (`backend/app/interceptors/voice_shadow.py`)

```python
def evaluate_voice_shadow(company_id: str, voice_payload: dict) -> VoiceShadowResult:
    """
    Evaluates TTS/voice messages.
    
    If shadow: play "please hold" message, alert manager via Socket.io.
    """
```

### Chat Interceptor (`backend/app/interceptors/chat_shadow.py`)

```python
class ChatShadowInterceptor:
    def intercept_outbound_chat(self, company_id: str, message_data: dict) -> dict:
        """
        Intercepts chat widget messages.
        
        If shadow: show typing indicator, queue message, don't send.
        """
```

---

## Socket.io Events

All events are company-scoped and emitted for real-time UI updates.

| Event | Payload | Description |
|-------|---------|-------------|
| `shadow:action_logged` | `{shadow_log_id, action_type, risk_score, mode}` | New action pending |
| `shadow:action_approved` | `{shadow_log_id, action_type, manager_id}` | Manager approved |
| `shadow:action_rejected` | `{shadow_log_id, action_type, manager_id}` | Manager rejected |
| `shadow:action_undone` | `{shadow_log_id, undo_log_id, reason}` | Action undone |
| `shadow:mode_changed` | `{mode, previous_mode, set_via}` | Global mode changed |
| `shadow:preference_changed` | `{action_category, preferred_mode, set_via}` | Preference updated |

### Frontend Integration

```typescript
import { io } from 'socket.io-client';

const socket = io('/shadow', { 
    auth: { company_id: user.company_id } 
});

socket.on('shadow:action_logged', (data) => {
    // Add to approvals queue
    addPendingAction(data);
    showNotification(`New ${data.action_type} requires approval`);
});

socket.on('shadow:mode_changed', (data) => {
    // Update UI mode indicator
    updateModeBadge(data.mode);
});
```

---

## Stage 0 Onboarding

New companies start in Stage 0, where ALL actions require approval.

### Flow

```
┌─────────────────────┐
│  New Company Signs  │
│  shadow_actions_    │
│  remaining = 10     │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Every Action       │
│  FORCED to shadow   │
│  (regardless of     │
│  risk score)        │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Manager Approves   │
│  Counter = 9        │
│  (rejects don't     │
│  decrement)         │
└─────────┬───────────┘
          │
          ▼
     ... repeat ...
          │
          ▼
┌─────────────────────┐
│  Counter = 0        │
│  GRADUATION!        │
│  Auto-switch to     │
│  supervised mode    │
└─────────────────────┘
```

### Implementation

```python
# In evaluate_action_risk()
shadow_remaining = getattr(company, "shadow_actions_remaining", None)
if shadow_remaining is not None and shadow_remaining > 0:
    return {
        "mode": "shadow",
        "requires_approval": True,
        "stage_0": True,
        "shadow_actions_remaining": shadow_remaining,
        # ...
    }
```

### Counter Decrement

```python
# In approve_shadow_action()
if company and company.shadow_actions_remaining > 0:
    company.shadow_actions_remaining -= 1
    if company.shadow_actions_remaining == 0:
        # Graduation!
        company.system_mode = "supervised"
```

---

## Dual Control Sync

Changes made via UI or Jarvis are synchronized in real-time.

### UI → Jarvis Sync

1. User changes preference in Dashboard
2. API calls `set_shadow_preference(set_via="ui")`
3. Socket event emitted: `shadow:preference_changed`
4. Jarvis receives event, updates context
5. Jarvis acknowledges: "I noticed you changed email to graduated mode"

### Jarvis → UI Sync

1. User tells Jarvis: "put refunds in shadow mode"
2. Jarvis calls API: `set_shadow_preference(set_via="jarvis")`
3. Socket event emitted: `shadow:preference_changed`
4. Dashboard receives event, updates UI
5. Toast notification: "Shadow mode updated via Jarvis"

### Implementation

```python
# In set_shadow_preference()
_emit_shadow_event_sync(
    company_id,
    "shadow:preference_changed",
    {
        "action_category": action_category,
        "preferred_mode": preferred_mode,
        "set_via": set_via,
    },
)
```

---

## Performance Considerations

### Database Indexes

```sql
-- Already implemented in models
CREATE INDEX idx_shadow_log_company ON shadow_log (company_id, created_at DESC);
CREATE INDEX idx_shadow_log_mode ON shadow_log (mode, manager_decision);
CREATE INDEX idx_shadow_prefs_company ON shadow_preferences (company_id);
```

### Recommended Optimizations

| Optimization | Status | Notes |
|--------------|--------|-------|
| Redis caching for preferences | Recommended | TTL: 5 minutes |
| Rate limiting on /evaluate | Recommended | 100 req/min per company |
| Table partitioning | Optional | Partition shadow_log by month |

### Caching Strategy

```python
# Pseudo-code for Redis caching
def get_shadow_preferences_cached(company_id: str) -> List[dict]:
    cache_key = f"shadow_prefs:{company_id}"
    
    # Try cache first
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Fetch from DB
    prefs = db.query(ShadowPreference).filter(...).all()
    
    # Cache for 5 minutes
    redis.setex(cache_key, 300, json.dumps(prefs))
    
    return prefs

# Invalidate on change
def set_shadow_preference(...):
    # ... save to DB ...
    redis.delete(f"shadow_prefs:{company_id}")
```

---

## Related Files

| File | Purpose |
|------|---------|
| `backend/app/services/shadow_mode_service.py` | Core service |
| `backend/app/api/shadow.py` | API routes |
| `backend/app/interceptors/*.py` | Channel interceptors |
| `backend/app/services/jarvis_service.py` | Jarvis integration |
| `database/models/shadow_mode.py` | DB models |
| `frontend/lib/shadow-api.ts` | Frontend API client |
| `frontend/components/dashboard/ShadowModeSettings.tsx` | Settings UI |

---

*End of Shadow Mode Architecture Documentation*
