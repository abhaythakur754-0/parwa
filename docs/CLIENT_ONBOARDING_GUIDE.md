# PARWA Client Onboarding Guide

## Overview

This guide walks through the process of onboarding a new client to PARWA.

## Pre-Onboarding Checklist

- [ ] Client contract signed
- [ ] Subscription tier selected (Mini/Junior/High)
- [ ] Integration requirements documented
- [ ] Admin users identified
- [ ] Data residency region confirmed

## Onboarding Steps

### Step 1: Create Client Configuration

```python
from clients import ClientConfig

config = ClientConfig(
    client_id="client_051",
    company_name="Acme Corp",
    variant="parwa_high",
    industry="ecommerce",
    region="us-east-1",
    features={
        "voice": True,
        "video": True,
        "analytics": True
    }
)
```

### Step 2: Initialize Database Schema

```bash
# Create client-specific schema
python -m clients.init_client --client-id client_051
```

### Step 3: Configure Integrations

#### Email Integration
```json
{
  "type": "email",
  "provider": "sendgrid",
  "api_key": "encrypted_key",
  "webhook_url": "https://api.parwa.ai/webhooks/email/client_051"
}
```

#### Chat Integration
```json
{
  "type": "chat",
  "provider": "intercom",
  "app_id": "xxx",
  "api_key": "encrypted_key"
}
```

### Step 4: Upload Knowledge Base

1. **Prepare Documents**
   - FAQ document (PDF/DOCX)
   - Product documentation
   - Company policies

2. **Upload via API**
   ```bash
   curl -X POST https://api.parwa.ai/kb/upload \
     -H "Authorization: Bearer <token>" \
     -F "file=@knowledge_base.pdf"
   ```

3. **Verify Ingestion**
   ```bash
   curl https://api.parwa.ai/kb/status?client_id=client_051
   ```

### Step 5: Configure Refund Rules

```json
{
  "auto_approve_limit": 25.00,
  "requires_approval_above": 25.00,
  "max_refund_amount": 500.00,
  "refund_policy_days": 30
}
```

### Step 6: Set Up Escalation Rules

```json
{
  "escalation_ladder": [
    {"hours": 24, "level": "tier1_support"},
    {"hours": 48, "level": "tier2_support"},
    {"hours": 72, "level": "manager"},
    {"hours": 96, "level": "director"}
  ]
}
```

### Step 7: Create Admin Users

```bash
curl -X POST https://api.parwa.ai/users \
  -H "Authorization: Bearer <token>" \
  -d '{
    "email": "admin@acme.com",
    "role": "admin",
    "client_id": "client_051"
  }'
```

### Step 8: Test Integration

Run the integration test suite:
```bash
pytest tests/clients/test_client_051.py -v
```

### Step 9: Enable Shadow Mode

Shadow mode processes tickets without sending responses:
```bash
curl -X POST https://api.parwa.ai/clients/client_051/shadow-mode \
  -d '{"enabled": true}'
```

### Step 10: Go Live

After validation:
```bash
curl -X POST https://api.parwa.ai/clients/client_051/activate
```

## Post-Onboarding

### Monitoring Setup
- Configure alerts for the client
- Set up custom dashboards
- Schedule health checks

### Training
- Schedule admin training session
- Provide documentation links
- Set up support channel

### Documentation
- Record integration specifics
- Document custom configurations
- Save API credentials securely
