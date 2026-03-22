# PARWA Security Hardening Guide

## Overview

This document outlines the security measures implemented in PARWA and provides guidance for maintaining a secure deployment. Security is a core principle of the PARWA platform, with multiple layers of protection from infrastructure to application level.

## Table of Contents

1. [OWASP Compliance Checklist](#owasp-compliance-checklist)
2. [Security Headers](#security-headers)
3. [SSL/TLS Configuration](#ssltls-configuration)
4. [Secret Management](#secret-management)
5. [Access Control](#access-control)
6. [Audit Logging](#audit-logging)

---

## OWASP Compliance Checklist

PARWA addresses all OWASP Top 10 security risks. Below is our compliance checklist.

### A01:2021 - Broken Access Control

| Control | Implementation | Status |
|---------|----------------|--------|
| Role-based access control (RBAC) | Implemented with roles: admin, agent, viewer | ✅ |
| Resource-level authorization | Every endpoint validates user permissions | ✅ |
| Multi-tenant isolation | PostgreSQL Row Level Security (RLS) | ✅ |
| API rate limiting | Redis-based rate limiting per tenant | ✅ |
| Session management | JWT with short expiry + refresh tokens | ✅ |
| Insecure direct object references | UUIDs with authorization checks | ✅ |

**Code Example - Authorization Check:**
```python
from fastapi import Depends, HTTPException
from app.auth import get_current_user, require_role

@router.delete("/api/v1/users/{user_id}")
async def delete_user(
    user_id: UUID,
    user = Depends(get_current_user),
    _ = Depends(require_role("admin"))
):
    # Only admins can delete users
    await users_service.delete(user_id)
```

### A02:2021 - Cryptographic Failures

| Control | Implementation | Status |
|---------|----------------|--------|
| TLS in transit | TLS 1.2+ required, TLS 1.3 preferred | ✅ |
| Encryption at rest | PostgreSQL encryption, S3 SSE | ✅ |
| Password hashing | bcrypt with cost factor 12 | ✅ |
| Sensitive data masking | PII masked in logs and responses | ✅ |
| Key rotation | Automated key rotation every 90 days | ✅ |
| HSTS | Strict-Transport-Security header | ✅ |

**Password Storage:**
```python
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Cost factor
)

# Hash password
hashed = pwd_context.hash(plain_password)

# Verify password
pwd_context.verify(plain_password, hashed)
```

### A03:2021 - Injection

| Control | Implementation | Status |
|---------|----------------|--------|
| SQL injection prevention | SQLAlchemy parameterized queries | ✅ |
| NoSQL injection prevention | No NoSQL databases used | N/A |
| OS command injection | No shell commands in application | ✅ |
| LDAP injection | No LDAP used | N/A |
| Input validation | Pydantic validation on all inputs | ✅ |
| Output encoding | Automatic via templating | ✅ |

**SQL Injection Prevention:**
```python
# Safe: Parameterized query
result = await db.execute(
    select(Ticket).where(Ticket.id == ticket_id)
)

# Safe: SQLAlchemy with filters
result = await db.execute(
    select(Ticket).filter(Ticket.status == status)
)

# NEVER do this:
# db.execute(f"SELECT * FROM tickets WHERE id = '{ticket_id}'")
```

### A04:2021 - Insecure Design

| Control | Implementation | Status |
|---------|----------------|--------|
| Threat modeling | Conducted during design phase | ✅ |
| Secure SDLC | Code review, security testing required | ✅ |
| Multi-tenant architecture | RLS + application-level checks | ✅ |
| Defense in depth | Multiple security layers | ✅ |
| Fail-safe defaults | Default deny access policies | ✅ |
| Human-in-the-loop | Critical actions require approval | ✅ |

### A05:2021 - Security Misconfiguration

| Control | Implementation | Status |
|---------|----------------|--------|
| Hardened container images | Minimal base images, no shell | ✅ |
| No default credentials | All credentials generated | ✅ |
| Security headers | Comprehensive headers configured | ✅ |
| Error handling | No stack traces in production | ✅ |
| Feature flags | Unused features disabled | ✅ |
| Automated hardening | Infrastructure as Code | ✅ |

### A06:2021 - Vulnerable and Outdated Components

| Control | Implementation | Status |
|---------|----------------|--------|
| Dependency scanning | pip-audit, npm audit in CI | ✅ |
| CVE monitoring | Automated scanning in CI/CD | ✅ |
| Container scanning | Trivy scans in build pipeline | ✅ |
| Update policy | Critical patches within 24 hours | ✅ |
| SBOM generation | Software bill of materials | ✅ |

**CI Dependency Check:**
```yaml
# .github/workflows/security.yml
- name: Run pip-audit
  run: pip-audit --ignore-vuln PYSEC-2023-228

- name: Run npm audit
  run: npm audit --audit-level=high

- name: Run Trivy container scan
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.IMAGE }}
    severity: 'CRITICAL,HIGH'
```

### A07:2021 - Identification and Authentication Failures

| Control | Implementation | Status |
|---------|----------------|--------|
| Multi-factor authentication | TOTP-based 2FA supported | ✅ |
| Password policies | Min 12 chars, complexity required | ✅ |
| Account lockout | 5 failed attempts = 15 min lock | ✅ |
| Session timeout | Access token 1hr, Refresh 7 days | ✅ |
| Secure password recovery | Time-limited tokens | ✅ |
| Credential stuffing protection | Rate limiting + CAPTCHA | ✅ |

### A08:2021 - Software and Data Integrity Failures

| Control | Implementation | Status |
|---------|----------------|--------|
| Signed commits | GPG signing required | ✅ |
| CI/CD security | Protected branches, required reviews | ✅ |
| Container signing | Cosign for image signing | ✅ |
| Webhook verification | HMAC signature validation | ✅ |
| Dependency pinning | Exact versions locked | ✅ |

**Webhook Verification:**
```python
import hmac
import hashlib

def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### A09:2021 - Security Logging and Monitoring Failures

| Control | Implementation | Status |
|---------|----------------|--------|
| Centralized logging | Loki + Grafana stack | ✅ |
| Security event logging | All auth events logged | ✅ |
| Anomaly detection | Alerting on suspicious patterns | ✅ |
| Log integrity | Logs stored in immutable storage | ✅ |
| Incident response | Runbooks and escalation paths | ✅ |
| Audit trails | All data changes logged | ✅ |

### A10:2021 - Server-Side Request Forgery (SSRF)

| Control | Implementation | Status |
|---------|----------------|--------|
| URL validation | Allowlist for external URLs | ✅ |
| Network segmentation | Restricted egress traffic | ✅ |
| No direct user URLs | URLs validated before use | ✅ |
| Response validation | Check response before processing | ✅ |

---

## Security Headers

### HTTP Security Headers

All responses include the following security headers:

```nginx
# Strict Transport Security
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

# Content Security Policy
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://api.parwa.ai wss://api.parwa.ai; frame-ancestors 'none';" always;

# X-Frame-Options
add_header X-Frame-Options "SAMEORIGIN" always;

# X-Content-Type-Options
add_header X-Content-Type-Options "nosniff" always;

# X-XSS-Protection
add_header X-XSS-Protection "1; mode=block" always;

# Referrer-Policy
add_header Referrer-Policy "strict-origin-when-cross-origin" always;

# Permissions-Policy
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
```

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.parwa.ai",
        "https://parwa.ai"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Tenant-ID",
        "X-Request-ID"
    ],
    max_age=86400
)
```

---

## SSL/TLS Configuration

### TLS Configuration

```nginx
# Minimum TLS version
ssl_protocols TLSv1.2 TLSv1.3;

# Strong cipher suites
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;

# Server cipher preference
ssl_prefer_server_ciphers off;

# OCSP Stapling
ssl_stapling on;
ssl_stapling_verify on;

# Session caching
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:50m;
ssl_session_tickets off;
```

### Certificate Management

Using cert-manager for automatic certificate provisioning:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: parwa-tls
  namespace: parwa
spec:
  secretName: parwa-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - app.parwa.ai
    - api.parwa.ai
```

---

## Secret Management

### External Secrets Operator

PARWA uses External Secrets Operator for secret management:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: parwa-secrets
  namespace: parwa
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secretsmanager
    kind: SecretStore
  target:
    name: parwa-secrets
    creationPolicy: Owner
  data:
    - secretKey: DATABASE_URL
      remoteRef:
        key: parwa/production
        property: database_url
```

### Secret Rotation Policy

| Secret Type | Rotation Frequency | Automated |
|-------------|-------------------|-----------|
| API Keys | 90 days | Yes |
| Database passwords | 90 days | Yes |
| JWT secrets | 90 days | Yes |
| Encryption keys | 365 days | Yes |

### Best Practices

1. **Never commit secrets to Git**
   ```bash
   # Use .gitignore
   echo ".env" >> .gitignore
   echo "*.key" >> .gitignore
   ```

2. **Use environment variables**
   ```python
   import os
   from pydantic_settings import BaseSettings

   class Settings(BaseSettings):
       database_url: str
       openai_api_key: str

       class Config:
           env_file = ".env"

   settings = Settings()
   ```

3. **Encrypt secrets at rest**
   - Use SOPS for GitOps workflows
   - Use cloud provider KMS

---

## Access Control

### Role-Based Access Control (RBAC)

| Role | Permissions |
|------|-------------|
| `admin` | Full access, user management, billing |
| `agent` | Ticket management, customer interactions |
| `viewer` | Read-only access to assigned resources |

### Implementation

```python
from enum import Enum
from functools import wraps

class Role(str, Enum):
    ADMIN = "admin"
    AGENT = "agent"
    VIEWER = "viewer"

def require_role(*roles: Role):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user=None, **kwargs):
            if user.role not in roles:
                raise HTTPException(
                    status_code=403,
                    detail="Insufficient permissions"
                )
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator
```

### Row Level Security (RLS)

```sql
-- Enable RLS on table
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;

-- Create policy for tenant isolation
CREATE POLICY tenant_isolation ON tickets
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Create policy for role-based access
CREATE POLICY role_access ON tickets
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM users
            WHERE users.id = current_setting('app.current_user')::uuid
            AND users.role IN ('admin', 'agent', 'viewer')
        )
    );
```

---

## Audit Logging

### Audit Events

All sensitive operations are logged with:

- Timestamp
- User ID and tenant ID
- Action type
- Resource affected
- IP address
- User agent
- Before/after values (for updates)

### Implementation

```python
from datetime import datetime
from pydantic import BaseModel
from app.models import AuditLog

class AuditEvent(BaseModel):
    action: str
    resource_type: str
    resource_id: str
    user_id: UUID
    tenant_id: UUID
    ip_address: str
    user_agent: str
    changes: dict = None

async def log_audit_event(event: AuditEvent):
    await AuditLog.create(
        timestamp=datetime.utcnow(),
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        user_id=event.user_id,
        tenant_id=event.tenant_id,
        ip_address=event.ip_address,
        user_agent=event.user_agent,
        changes=event.changes
    )
```

### Audit Log Retention

| Log Type | Retention Period |
|----------|-----------------|
| Authentication events | 2 years |
| Authorization events | 2 years |
| Data access events | 1 year |
| Data modification events | 2 years |
| System events | 90 days |

### Querying Audit Logs

```sql
-- Get all actions by a user
SELECT * FROM audit_logs
WHERE user_id = 'uuid'
ORDER BY timestamp DESC;

-- Get all modifications to a resource
SELECT * FROM audit_logs
WHERE resource_type = 'ticket'
AND resource_id = 'uuid'
AND action IN ('create', 'update', 'delete');

-- Get all failed authentication attempts
SELECT * FROM audit_logs
WHERE action = 'login_failed'
AND timestamp > now() - interval '24 hours';
```

---

## Security Checklist

### Pre-Deployment

- [ ] All environment variables configured
- [ ] Secrets stored in secret manager
- [ ] TLS certificates valid
- [ ] Security headers configured
- [ ] Rate limiting enabled
- [ ] RLS policies applied
- [ ] Audit logging enabled

### Ongoing

- [ ] Regular security scans (weekly)
- [ ] Dependency updates (monthly)
- [ ] Access reviews (quarterly)
- [ ] Penetration testing (annually)
- [ ] Security training (annually)
