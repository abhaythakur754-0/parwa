# PARWA API Documentation

## Overview

PARWA provides a RESTful API for programmatic access to all platform features. This document covers authentication, available endpoints, request/response formats, and error handling.

## Table of Contents

1. [Authentication](#authentication)
2. [Rate Limiting](#rate-limiting)
3. [API Endpoints](#api-endpoints)
4. [Request/Response Formats](#requestresponse-formats)
5. [Error Codes](#error-codes)
6. [Versioning](#versioning)

---

## Authentication

### Overview

PARWA uses JWT (JSON Web Tokens) for API authentication. All API requests must include a valid access token in the Authorization header.

### Obtaining Tokens

**Login Endpoint:**
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your-password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Using Tokens

Include the access token in all API requests:

```http
GET /api/v1/tickets
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Refreshing Tokens

Access tokens expire after 1 hour. Use the refresh token to obtain a new access token:

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### API Keys

For server-to-server integration, use API keys:

```http
GET /api/v1/tickets
X-API-Key: pk_live_xxxxxxxxxxxxxxxxxxxx
```

API keys can be created and managed in the Settings > API Keys section of the dashboard.

---

## Rate Limiting

### Limits

| Plan | Requests/Minute | Requests/Hour |
|------|-----------------|---------------|
| Mini | 60 | 1,000 |
| Junior | 120 | 5,000 |
| Senior | 300 | 20,000 |

### Headers

Rate limit information is included in response headers:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1647820800
```

### Handling Rate Limits

When rate limited, the API returns a 429 status:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Retry after 60 seconds.",
  "retry_after": 60
}
```

---

## API Endpoints

### Authentication

#### POST /api/v1/auth/login

Authenticate user and obtain tokens.

**Request:**
```json
{
  "email": "string",
  "password": "string"
}
```

**Response:**
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "string",
    "name": "string",
    "role": "string"
  }
}
```

#### POST /api/v1/auth/register

Create a new user account.

**Request:**
```json
{
  "email": "string",
  "password": "string",
  "name": "string",
  "company_name": "string"
}
```

#### POST /api/v1/auth/logout

Invalidate current session.

#### POST /api/v1/auth/password/reset

Request password reset email.

**Request:**
```json
{
  "email": "string"
}
```

---

### Tickets

#### GET /api/v1/tickets

List tickets with pagination and filters.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | int | Page number (default: 1) |
| `limit` | int | Items per page (default: 20, max: 100) |
| `status` | string | Filter by status: open, pending, resolved, closed |
| `priority` | string | Filter by priority: low, medium, high, urgent |
| `assignee_id` | uuid | Filter by assignee |
| `search` | string | Search in subject and body |

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "subject": "string",
      "body": "string",
      "status": "open",
      "priority": "medium",
      "category": "string",
      "assignee": {
        "id": "uuid",
        "name": "string"
      },
      "customer": {
        "id": "uuid",
        "email": "string",
        "name": "string"
      },
      "created_at": "2026-03-22T10:00:00Z",
      "updated_at": "2026-03-22T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

#### GET /api/v1/tickets/{id}

Get a single ticket by ID.

#### POST /api/v1/tickets

Create a new ticket.

**Request:**
```json
{
  "subject": "string",
  "body": "string",
  "priority": "medium",
  "customer_email": "string",
  "customer_name": "string",
  "tags": ["string"]
}
```

#### PUT /api/v1/tickets/{id}

Update a ticket.

#### POST /api/v1/tickets/{id}/reply

Add a reply to a ticket.

**Request:**
```json
{
  "body": "string",
  "is_internal": false
}
```

#### POST /api/v1/tickets/{id}/assign

Assign ticket to an agent.

**Request:**
```json
{
  "assignee_id": "uuid"
}
```

#### POST /api/v1/tickets/{id}/close

Close a ticket with resolution.

**Request:**
```json
{
  "resolution": "string",
  "satisfaction_score": 5
}
```

---

### Approvals

#### GET /api/v1/approvals

List pending approvals.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | pending, approved, denied |
| `type` | string | refund, escalation, action |

#### GET /api/v1/approvals/{id}

Get approval details.

#### POST /api/v1/approvals/{id}/approve

Approve an action.

**Request:**
```json
{
  "notes": "string (optional)"
}
```

**Response:**
```json
{
  "id": "uuid",
  "status": "approved",
  "action_result": {
    "type": "refund",
    "amount": 99.99,
    "transaction_id": "txn_123",
    "executed_at": "2026-03-22T10:00:00Z"
  },
  "audit_log_id": "uuid"
}
```

#### POST /api/v1/approvals/{id}/deny

Deny an action.

**Request:**
```json
{
  "reason": "string (required)"
}
```

#### POST /api/v1/approvals/bulk-approve

Approve multiple items.

**Request:**
```json
{
  "approval_ids": ["uuid", "uuid"]
}
```

---

### Agents

#### GET /api/v1/agents

List all AI agents.

#### GET /api/v1/agents/{id}

Get agent details.

#### POST /api/v1/agents/{id}/pause

Pause an agent.

#### POST /api/v1/agents/{id}/resume

Resume a paused agent.

#### GET /api/v1/agents/{id}/logs

Get agent activity logs.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | datetime | Start of date range |
| `end_date` | datetime | End of date range |
| `level` | string | Log level: info, warning, error |

#### GET /api/v1/agents/{id}/metrics

Get agent performance metrics.

---

### Analytics

#### GET /api/v1/analytics/metrics

Get aggregate metrics.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | date | Start date |
| `end_date` | date | End date |
| `granularity` | string | hour, day, week, month |

**Response:**
```json
{
  "total_tickets": 1500,
  "resolved_tickets": 1200,
  "avg_resolution_time_hours": 4.5,
  "customer_satisfaction": 4.7,
  "first_response_time_minutes": 15,
  "tickets_by_status": {
    "open": 150,
    "pending": 100,
    "resolved": 800,
    "closed": 450
  },
  "tickets_by_priority": {
    "low": 500,
    "medium": 600,
    "high": 300,
    "urgent": 100
  }
}
```

#### GET /api/v1/analytics/chart-data

Get data for charts.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `type` | string | line, bar, pie |
| `metric` | string | tickets, resolution_time, satisfaction |
| `start_date` | date | Start date |
| `end_date` | date | End date |

#### GET /api/v1/analytics/agent-performance

Get agent performance metrics.

#### GET /api/v1/analytics/export

Export analytics data.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `format` | string | csv, pdf, json |
| `start_date` | date | Start date |
| `end_date` | date | End date |

---

### Jarvis AI

#### POST /api/v1/jarvis/command

Send a command to Jarvis (non-streaming).

**Request:**
```json
{
  "command": "string",
  "context": {
    "ticket_id": "uuid (optional)",
    "customer_id": "uuid (optional)"
  }
}
```

**Response:**
```json
{
  "response": "string",
  "actions_taken": [
    {
      "type": "search",
      "query": "string"
    }
  ],
  "suggestions": ["string"],
  "execution_time_ms": 1500
}
```

#### WebSocket /ws/jarvis

Streaming Jarvis interface.

**Connection:**
```javascript
const ws = new WebSocket('wss://api.parwa.ai/ws/jarvis', {
  headers: {
    'Authorization': 'Bearer <token>'
  }
});
```

**Send Command:**
```json
{
  "type": "command",
  "command": "string"
}
```

**Receive Chunks:**
```json
{
  "type": "chunk",
  "content": "string",
  "done": false
}
```

**Final Response:**
```json
{
  "type": "complete",
  "full_response": "string",
  "actions_taken": []
}
```

---

### Webhooks

#### GET /api/v1/webhooks

List configured webhooks.

#### POST /api/v1/webhooks

Create a webhook.

**Request:**
```json
{
  "url": "https://your-server.com/webhook",
  "events": ["ticket.created", "ticket.closed", "approval.required"],
  "secret": "string (optional)"
}
```

#### PUT /api/v1/webhooks/{id}

Update a webhook.

#### DELETE /api/v1/webhooks/{id}

Delete a webhook.

#### POST /api/v1/webhooks/{id}/test

Send test webhook.

---

### Settings

#### GET /api/v1/settings/profile

Get user profile.

#### PUT /api/v1/settings/profile

Update profile.

#### GET /api/v1/settings/notifications

Get notification preferences.

#### PUT /api/v1/settings/notifications

Update notification preferences.

#### POST /api/v1/settings/password

Change password.

**Request:**
```json
{
  "current_password": "string",
  "new_password": "string"
}
```

#### POST /api/v1/settings/2fa/enable

Enable two-factor authentication.

#### POST /api/v1/settings/2fa/disable

Disable two-factor authentication.

---

## Request/Response Formats

### Date/Time Format

All dates are ISO 8601 format: `2026-03-22T10:00:00Z`

### Pagination

List endpoints support cursor or offset pagination:

**Offset Pagination:**
```
GET /api/v1/tickets?page=2&limit=20
```

**Cursor Pagination:**
```
GET /api/v1/tickets?cursor=eyJpZCI6MTUwfQ&limit=20
```

### Filtering

Multiple filters can be combined:

```
GET /api/v1/tickets?status=open&priority=high&assignee_id=uuid
```

### Sorting

Sort by field with direction:

```
GET /api/v1/tickets?sort=created_at&order=desc
```

---

## Error Codes

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (successful delete) |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Invalid or missing token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found |
| 409 | Conflict - Resource already exists |
| 422 | Unprocessable Entity - Validation error |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |

### Error Response Format

```json
{
  "error": "validation_error",
  "message": "Invalid request parameters",
  "details": [
    {
      "field": "email",
      "message": "Invalid email format"
    }
  ],
  "request_id": "req_abc123"
}
```

### Error Codes

| Code | Description |
|------|-------------|
| `validation_error` | Request validation failed |
| `authentication_failed` | Invalid credentials |
| `token_expired` | JWT token expired |
| `insufficient_permissions` | User lacks required role |
| `resource_not_found` | Requested resource doesn't exist |
| `resource_conflict` | Resource already exists |
| `rate_limit_exceeded` | Too many requests |
| `internal_error` | Unexpected server error |

---

## Versioning

### URL Versioning

API version is included in the URL path:

```
/api/v1/tickets
/api/v2/tickets (future)
```

### Version Lifecycle

| Version | Status | Support Until |
|---------|--------|---------------|
| v1 | Current | Active |
| v2 | Planned | - |

### Breaking Changes

Breaking changes will result in a new API version. Non-breaking changes (new fields, new endpoints) are added to existing versions.

### Deprecation Policy

Deprecated endpoints will return a warning header:

```http
Deprecation: true
Sunset: Sat, 01 Jan 2027 00:00:00 GMT
Link: </api/v2/tickets>; rel="successor-version"
```

---

## SDKs and Libraries

### JavaScript/TypeScript

```bash
npm install @parwa/sdk
```

```typescript
import { ParwaClient } from '@parwa/sdk';

const client = new ParwaClient({
  apiKey: 'pk_live_xxx'
});

const tickets = await client.tickets.list({ status: 'open' });
```

### Python

```bash
pip install parwa-sdk
```

```python
from parwa import ParwaClient

client = ParwaClient(api_key='pk_live_xxx')
tickets = client.tickets.list(status='open')
```

### cURL Examples

```bash
# List tickets
curl -H "Authorization: Bearer <token>" \
  https://api.parwa.ai/api/v1/tickets

# Create ticket
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"subject":"Help needed","body":"Description"}' \
  https://api.parwa.ai/api/v1/tickets
```
