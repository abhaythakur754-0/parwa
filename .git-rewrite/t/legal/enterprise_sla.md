# Enterprise Service Level Agreement (SLA)

**PARWA AI Customer Support Platform**

**Version:** 2.0  
**Effective Date:** [Contract Start Date]  
**Last Updated:** March 2026

---

## 1. SERVICE COMMITMENT

PARWA Technologies Inc. ("PARWA") is committed to providing reliable, high-quality AI customer support services to Enterprise clients. This Service Level Agreement ("SLA") defines the service commitments and remedies available to Enterprise clients.

---

## 2. SERVICE AVAILABILITY

### 2.1 Uptime Commitment

PARWA commits to maintaining **99.9%** monthly uptime for Enterprise tier clients.

| Metric | Commitment | Measurement Period |
|--------|------------|-------------------|
| Monthly Uptime | 99.9% | Calendar month |
| Annual Uptime | 99.95% | Contract year |
| Planned Maintenance | Excluded from calculation | - |

### 2.2 Uptime Calculation

```
Uptime % = ((Total Minutes in Month - Downtime Minutes) / Total Minutes in Month) × 100
```

Where:
- **Total Minutes in Month** = Total calendar minutes in the measurement month
- **Downtime Minutes** = Minutes when the Services are unavailable

### 2.3 Service Credits

If PARWA fails to meet the uptime commitment, the Client is entitled to service credits:

| Monthly Uptime | Service Credit |
|----------------|----------------|
| 99.0% - 99.9% | 5% of monthly fee |
| 95.0% - 99.0% | 10% of monthly fee |
| 90.0% - 95.0% | 20% of monthly fee |
| Below 90.0% | 30% of monthly fee |

**Maximum Service Credits:** 30% of monthly fee in any given month.

---

## 3. RESPONSE TIME COMMITMENTS

### 3.1 API Response Time

| Endpoint Type | P50 Latency | P95 Latency | P99 Latency |
|---------------|-------------|-------------|-------------|
| API Endpoints | < 100ms | < 300ms | < 500ms |
| AI Response Generation | < 500ms | < 1000ms | < 2000ms |
| Webhook Delivery | < 200ms | < 500ms | < 1000ms |

### 3.2 Performance Measurement

- Latency measured from request receipt to response delivery
- Measurements exclude network latency beyond PARWA's infrastructure
- Measured across all API endpoints collectively

---

## 4. SUPPORT RESPONSE TIMES

### 4.1 Support Tiers

| Priority | Definition | Response Time | Update Frequency |
|----------|------------|---------------|------------------|
| P1 - Critical | Service completely unavailable | 15 minutes | Every 30 minutes |
| P2 - High | Major feature unavailable | 1 hour | Every 2 hours |
| P3 - Medium | Feature partially impacted | 4 hours | Every 8 hours |
| P4 - Low | Minor issue or question | 24 hours | Every 48 hours |

### 4.2 Support Availability

- **Standard Support:** Business hours (9 AM - 6 PM EST, Monday-Friday)
- **Priority Support:** Extended hours (8 AM - 10 PM EST, Monday-Friday)
- **Enterprise Support:** 24/7/365

---

## 5. DATA SECURITY COMMITMENTS

### 5.1 Encryption Standards

| Data State | Standard | Key Management |
|------------|----------|----------------|
| In Transit | TLS 1.3 | Certificate rotation every 90 days |
| At Rest | AES-256 | Customer-managed keys available |
| Backups | AES-256 | Separate encryption keys |

### 5.2 Security Certifications

PARWA maintains the following certifications:

- SOC 2 Type II (annual)
- GDPR compliance
- CCPA compliance
- HIPAA compliance (for healthcare clients)
- PCI DSS Level 1 (for payment processing)

### 5.3 Security Incident Response

| Incident Severity | Notification Time | Response Time |
|-------------------|-------------------|---------------|
| Critical | 1 hour | 4 hours |
| High | 4 hours | 8 hours |
| Medium | 24 hours | 48 hours |
| Low | 72 hours | 7 days |

---

## 6. DATA BACKUP AND RECOVERY

### 6.1 Backup Schedule

| Data Type | Backup Frequency | Retention | Recovery Point Objective |
|-----------|------------------|-----------|-------------------------|
| Database | Every 1 hour | 30 days | 1 hour |
| File Storage | Every 6 hours | 90 days | 6 hours |
| Configuration | Every 24 hours | 1 year | 24 hours |

### 6.2 Recovery Time Objectives

| Scenario | Recovery Time Objective |
|----------|------------------------|
| Single server failure | 15 minutes |
| Availability zone failure | 1 hour |
| Region failure | 4 hours |
| Complete disaster | 24 hours |

---

## 7. PLANNED MAINTENANCE

### 7.1 Maintenance Windows

- **Standard Window:** Sundays 2:00 AM - 6:00 AM EST
- **Advance Notice:** 72 hours for routine maintenance
- **Emergency Maintenance:** Best effort notice

### 7.2 Maintenance Communication

- Email notification to technical contacts
- Status page updates
- Post-maintenance confirmation

---

## 8. EXCLUSIONS

This SLA does not apply to:

1. Issues caused by Client's use of the Services in violation of the Agreement
2. Issues caused by Client's equipment, software, or third-party services
3. Force majeure events
4. Scheduled maintenance with proper notice
5. Issues arising from Client's failure to maintain required configurations
6. Beta or preview features
7. Third-party service dependencies outside PARWA's control

---

## 9. CLAIMING SERVICE CREDITS

### 9.1 Claim Process

To claim service credits, the Client must:

1. Submit a claim within 30 days of the incident
2. Provide evidence of the service unavailability
3. Include affected time periods and impacted services
4. Submit to: sla@parwa.ai

### 9.2 Credit Application

- Approved credits are applied to the next invoice
- Credits are the sole remedy for SLA violations
- Credits cannot be exchanged for cash

---

## 10. MONITORING AND REPORTING

### 10.1 Availability Dashboard

PARWA provides:

- Real-time status page at status.parwa.ai
- Historical uptime reports
- Performance metrics dashboard

### 10.2 Monthly Reports

Enterprise clients receive:

- Monthly uptime summary
- Performance metrics breakdown
- Support ticket summary
- Security updates

---

## 11. SLA MODIFICATIONS

PARWA may modify this SLA with:

- 30 days' advance notice for improvements
- 90 days' advance notice for any reduction in commitments
- Immediate notice for critical security updates

---

## 12. CONTACT INFORMATION

**Enterprise Support:**  
Email: enterprise-support@parwa.ai  
Phone: [Phone Number]

**SLA Claims:**  
Email: sla@parwa.ai

**Status Page:**  
https://status.parwa.ai

---

## 13. AGREEMENT

By entering into an Enterprise agreement with PARWA, the Client acknowledges and agrees to the terms of this SLA.

---

**PARWA Technologies Inc.**  
*Last Updated: March 2026*
