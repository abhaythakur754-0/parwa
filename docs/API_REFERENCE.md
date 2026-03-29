# PARWA API Reference

## Overview

PARWA is an AI-powered customer support automation platform with three variants:
- **Mini** - Entry-level automation for small businesses
- **PARWA Junior** - Mid-tier with learning capabilities  
- **PARWA High** - Enterprise-grade with advanced analytics

## Base URL

```
Production: https://api.parwa.ai/v1
Staging: https://staging-api.parwa.ai/v1
```

## Authentication

All API requests require authentication via Bearer token:

```http
Authorization: Bearer <your-api-key>
```

## Endpoints

### Tickets

#### List Tickets
```http
GET /tickets
```

Query Parameters:
- `status` (string): Filter by status (open, pending, resolved, closed)
- `priority` (string): Filter by priority (low, medium, high, urgent)
- `limit` (integer): Maximum results (default: 50, max: 200)
- `offset` (integer): Pagination offset

Response:
```json
{
  "tickets": [
    {
      "id": "uuid",
      "subject": "string",
      "status": "string",
      "priority": "string",
      "created_at": "ISO8601"
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

#### Create Ticket
```http
POST /tickets
```

Request Body:
```json
{
  "subject": "string",
  "description": "string",
  "priority": "medium",
  "customer_id": "uuid",
  "channel": "email|chat|voice|sms"
}
```

### Refunds

#### Request Refund
```http
POST /refunds
```

Request Body:
```json
{
  "ticket_id": "uuid",
  "amount": 49.99,
  "currency": "USD",
  "reason": "string"
}
```

Response:
```json
{
  "refund_id": "uuid",
  "status": "pending_approval",
  "requires_approval": true
}
```

#### Approve Refund
```http
POST /refunds/{refund_id}/approve
```

Request Body:
```json
{
  "approved": true,
  "approver_id": "uuid",
  "notes": "string"
}
```

### Knowledge Base

#### Search Knowledge Base
```http
GET /kb/search
```

Query Parameters:
- `q` (string): Search query
- `limit` (integer): Maximum results

Response:
```json
{
  "results": [
    {
      "id": "uuid",
      "title": "string",
      "content": "string",
      "relevance_score": 0.95
    }
  ]
}
```

### Analytics

#### Get Dashboard Metrics
```http
GET /analytics/dashboard
```

Query Parameters:
- `period` (string): Time period (day, week, month, year)
- `client_id` (string): Client identifier (for multi-tenant)

Response:
```json
{
  "tickets_processed": 1234,
  "avg_response_time_ms": 245,
  "resolution_rate": 0.94,
  "customer_satisfaction": 4.5
}
```

## Error Handling

All errors follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

Common Error Codes:
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `429` - Rate Limited
- `500` - Internal Server Error

## Rate Limits

| Tier | Requests/min | Requests/day |
|------|-------------|--------------|
| Mini | 60 | 10,000 |
| PARWA | 300 | 50,000 |
| PARWA High | 1000 | 200,000 |
| Enterprise | Unlimited | Unlimited |

## Webhooks

Configure webhooks to receive real-time notifications:

```json
{
  "event": "ticket.created",
  "timestamp": "2026-03-28T00:00:00Z",
  "data": {
    "ticket_id": "uuid",
    "client_id": "uuid"
  }
}
```

Supported Events:
- `ticket.created`
- `ticket.updated`
- `ticket.resolved`
- `refund.requested`
- `refund.approved`
- `refund.processed`
