# PARWA Ticket Management API Documentation

## Overview

The PARWA Ticket Management system provides a comprehensive set of APIs for managing customer support tickets, agent assignments, SLA tracking, and real-time updates.

---

## Table of Contents

1. [Ticket Operations](#ticket-operations)
2. [Assignment System](#assignment-system)
3. [SLA Management](#sla-management)
4. [Real-time Updates](#real-time-updates)
5. [Export Operations](#export-operations)
6. [Customer Identity](#customer-identity)

---

## Ticket Operations

### List Tickets

```http
GET /api/tickets
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status[]` | string[] | Filter by status (open, in_progress, resolved, closed) |
| `priority[]` | string[] | Filter by priority (critical, high, medium, low) |
| `category[]` | string[] | Filter by category |
| `channel` | string | Filter by channel (email, chat, sms, voice) |
| `assigned_to` | string | Filter by agent ID |
| `customer_id` | string | Filter by customer ID |
| `search` | string | Search in subject and content |
| `page` | int | Page number (default: 1) |
| `page_size` | int | Items per page (default: 25, max: 100) |
| `sort_by` | string | Sort field (created_at, updated_at, priority) |
| `sort_order` | string | Sort order (asc, desc) |

**Response:**

```json
{
  "items": [
    {
      "id": "ticket-uuid",
      "subject": "Cannot login to my account",
      "status": "open",
      "priority": "high",
      "channel": "email",
      "created_at": "2026-04-18T10:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 25,
  "pages": 6
}
```

### Get Ticket Details

```http
GET /api/tickets/{ticket_id}
```

**Response:**

```json
{
  "id": "ticket-uuid",
  "subject": "Cannot login to my account",
  "status": "open",
  "priority": "high",
  "category": "tech_support",
  "channel": "email",
  "tags": ["urgent", "login-issue"],
  "agent_id": null,
  "sla_breached": false,
  "created_at": "2026-04-18T10:00:00Z"
}
```

### Update Ticket

```http
PUT /api/tickets/{ticket_id}
```

**Body:**

```json
{
  "subject": "Updated subject",
  "priority": "critical",
  "tags": ["urgent", "escalated"]
}
```

### Update Status

```http
PATCH /api/tickets/{ticket_id}/status
```

**Body:**

```json
{
  "status": "in_progress",
  "reason": "Agent is working on the issue"
}
```

---

## Assignment System

### Get Assignment Suggestions

```http
GET /api/tickets/{ticket_id}/suggest-assignee
```

**Response:**

```json
{
  "suggestions": [
    {
      "agent_id": "agent-1",
      "agent_name": "John Smith",
      "score": 0.85,
      "raw_score": 97.75,
      "score_breakdown": {
        "expertise": {
          "raw": 36,
          "max": 40,
          "percentage": 90
        },
        "workload": {
          "raw": 24,
          "max": 30,
          "percentage": 80,
          "current_tickets": 3
        },
        "performance": {
          "raw": 17,
          "max": 20,
          "percentage": 85
        },
        "response_time": {
          "raw": 13.5,
          "max": 15,
          "percentage": 90
        },
        "availability": {
          "raw": 7,
          "max": 10,
          "percentage": 70
        }
      },
      "is_recommended": true
    }
  ],
  "algorithm_version": "2.0"
}
```

### Assign Ticket

```http
POST /api/tickets/{ticket_id}/assign
```

**Body:**

```json
{
  "assignee_id": "agent-1",
  "assignee_type": "human",
  "reason": "Best match for tech support"
}
```

### Bulk Assign

```http
POST /api/tickets/bulk/assign
```

**Body:**

```json
{
  "ticket_ids": ["ticket-1", "ticket-2", "ticket-3"],
  "assignee_id": "agent-1",
  "assignee_type": "human"
}
```

---

## SLA Management

### SLA Status

The SLA system automatically tracks:
- First response time
- Resolution time
- Breach alerts

**SLA Timer Component Props:**

```typescript
interface SLATimerProps {
  deadline: string;          // ISO timestamp
  isBreached: boolean;       // Already breached
  isApproaching: boolean;    // Within warning threshold
  variant: 'full' | 'badge' | 'progress';
}
```

**Status Colors:**
- 🟢 Green: > 50% time remaining
- 🟡 Yellow: 25-50% time remaining
- 🔴 Red: < 25% time remaining or breached

---

## Real-time Updates

### WebSocket Events

Connect to: `ws://localhost:8000/ws`

**Subscribe to Events:**

```javascript
socket.emit('event:subscribe', { events: ['*'] });
```

**Ticket Events:**

| Event | Description |
|-------|-------------|
| `ticket:new` | New ticket created |
| `ticket:status_changed` | Status updated |
| `ticket:assigned` | Agent assigned |
| `ticket:resolved` | Ticket resolved |
| `ticket:escalated` | Ticket escalated |
| `ticket:merged` | Tickets merged |
| `message:new` | New message added |
| `note:added` | Internal note added |

**Event Payload:**

```json
{
  "event_id": "event-uuid",
  "event_type": "ticket:new",
  "ticket_id": "ticket-uuid",
  "ticket_subject": "Cannot login",
  "actor_id": "user-uuid",
  "actor_name": "John Smith",
  "actor_type": "human",
  "timestamp": "2026-04-18T10:00:00Z"
}
```

### Presence Events

| Event | Description |
|-------|-------------|
| `presence:get` | Request agent presence |
| `presence:update` | Presence changed |
| `ticket:subscribe` | Subscribe to ticket updates |

---

## Export Operations

### Export Tickets

```http
POST /api/tickets/export
```

**Body:**

```json
{
  "format": "csv",
  "ticket_ids": ["ticket-1", "ticket-2"],
  "filters": {
    "status": ["open", "in_progress"],
    "date_range": {
      "start": "2026-04-01",
      "end": "2026-04-18"
    }
  },
  "fields": ["id", "subject", "status", "priority", "created_at"]
}
```

**Response:**

```json
{
  "export_id": "export-uuid",
  "status": "processing",
  "download_url": null
}
```

### Get Export Status

```http
GET /api/tickets/export/{export_id}
```

**Response:**

```json
{
  "export_id": "export-uuid",
  "status": "completed",
  "download_url": "/api/tickets/export/export-uuid/download"
}
```

---

## Customer Identity

### Get Customer Identity

```http
GET /api/customers/{customer_id}/identity
```

**Response:**

```json
{
  "customer_id": "customer-uuid",
  "identities": [
    {
      "channel": "email",
      "identifier": "john@example.com",
      "verified": true
    },
    {
      "channel": "phone",
      "identifier": "+1234567890",
      "verified": false
    }
  ],
  "merge_candidates": [
    {
      "customer_id": "potential-match-uuid",
      "match_score": 0.92,
      "matching_fields": ["email", "name"]
    }
  ]
}
```

### Merge Customers

```http
POST /api/customers/merge
```

**Body:**

```json
{
  "primary_customer_id": "customer-1",
  "secondary_customer_ids": ["customer-2", "customer-3"],
  "reason": "Duplicate customer records"
}
```

---

## Error Handling

All API errors follow this format:

```json
{
  "error": {
    "code": "TICKET_NOT_FOUND",
    "message": "Ticket with ID 'ticket-uuid' not found",
    "details": {}
  }
}
```

**Common Error Codes:**

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `TICKET_NOT_FOUND` | 404 | Ticket does not exist |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `VALIDATION_ERROR` | 400 | Invalid request data |
| `SLA_BREACH` | 422 | SLA already breached |

---

## Rate Limiting

| Endpoint Type | Rate Limit |
|--------------|------------|
| List/Search | 60 requests/minute |
| Read Operations | 120 requests/minute |
| Write Operations | 30 requests/minute |
| Export | 5 requests/minute |

---

## SDK Usage

### React Hook

```typescript
import { useTicketRealtime } from '@/components/dashboard/tickets';

function TicketPage() {
  const {
    recentEvents,
    newTicketCount,
    isConnected,
    acknowledge,
  } = useTicketRealtime();

  // Handle new events
  useEffect(() => {
    if (newTicketCount > 0) {
      showNotification(`${newTicketCount} new tickets`);
    }
  }, [newTicketCount]);

  return <div>...</div>;
}
```

### API Client

```typescript
import { ticketsApi } from '@/lib/tickets-api';

// List tickets
const { items, total } = await ticketsApi.list({
  status: ['open'],
  priority: ['high', 'critical'],
  page: 1,
});

// Assign ticket
await ticketsApi.assign('ticket-id', {
  assignee_id: 'agent-id',
  assignee_type: 'human',
});
```

---

## Changelog

### v2.0.0 (April 2026)
- Added AI assignment scoring with 5-factor algorithm
- Real-time WebSocket updates
- Customer identity matching
- Ticket merge functionality
- Export operations

### v1.0.0 (January 2026)
- Initial release
- Basic CRUD operations
- Simple assignment
