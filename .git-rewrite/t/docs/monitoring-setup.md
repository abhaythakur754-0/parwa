# PARWA Monitoring Setup Guide

## Overview

This document describes the monitoring and alerting infrastructure for PARWA. The platform uses a comprehensive observability stack with Prometheus for metrics, Grafana for visualization, Loki for logs, and Jaeger for distributed tracing.

## Table of Contents

1. [Prometheus Setup](#prometheus-setup)
2. [Grafana Dashboards](#grafana-dashboards)
3. [Alert Configuration](#alert-configuration)
4. [Log Aggregation](#log-aggregation)
5. [Metric Descriptions](#metric-descriptions)
6. [SLO Definitions](#slo-definitions)

---

## Prometheus Setup

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PROMETHEUS ECOSYSTEM                            │
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐        │
│  │ Prometheus   │────▶│ Alertmanager │────▶│  PagerDuty   │        │
│  │ Server       │     │              │     │  Slack       │        │
│  └──────┬───────┘     └──────────────┘     └──────────────┘        │
│         │                                                            │
│         │ Scrape                                                     │
│         ▼                                                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    KUBERNETES SERVICES                        │   │
│  │                                                               │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │   │
│  │  │Backend  │ │Frontend │ │ Worker  │ │  Redis  │ │Postgres │ │   │
│  │  │:9090    │ │:9113    │ │:9090    │ │:9121    │ │:9187    │ │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

rule_files:
  - /etc/prometheus/rules/*.yml

scrape_configs:
  # Kubernetes service discovery
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
      - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        regex: ([^:]+)(?::\d+)?;(\d+)
        replacement: $1:$2
        target_label: __address__

  # Backend metrics
  - job_name: 'parwa-backend'
    static_configs:
      - targets: ['parwa-backend:9090']

  # Frontend nginx metrics
  - job_name: 'parwa-frontend'
    static_configs:
      - targets: ['parwa-frontend:9113']

  # Redis exporter
  - job_name: 'parwa-redis'
    static_configs:
      - targets: ['parwa-redis:9121']

  # PostgreSQL exporter
  - job_name: 'parwa-postgres'
    static_configs:
      - targets: ['parwa-postgres:9187']
```

### Prometheus Rules

```yaml
# rules/parwa-alerts.yml
groups:
  - name: parwa-alerts
    interval: 30s
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) /
          sum(rate(http_requests_total[5m])) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }}"

      # High latency
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
          ) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High P95 latency"
          description: "P95 latency is {{ $value | humanizeDuration }}"

      # Pod down
      - alert: PodDown
        expr: up{job="parwa-backend"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Pod {{ $labels.instance }} is down"

      # Memory pressure
      - alert: HighMemoryUsage
        expr: |
          container_memory_usage_bytes /
          container_spec_memory_limit_bytes > 0.85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage on {{ $labels.pod }}"

      # Database connections exhausted
      - alert: DatabaseConnectionsHigh
        expr: pg_stat_activity_count > 180
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High database connection count"

      # Redis queue backed up
      - alert: RedisQueueBacklog
        expr: redis_llen{queue="arq:queue"} > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Redis queue backlog is high"
```

---

## Grafana Dashboards

### Main Dashboard

The main PARWA dashboard provides an overview of system health:

```json
{
  "dashboard": {
    "title": "PARWA Overview",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(http_requests_total[5m]))",
            "legendFormat": "Requests/s"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{status=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m]))",
            "legendFormat": "Error Rate"
          }
        ]
      },
      {
        "title": "P95 Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
            "legendFormat": "P95"
          }
        ]
      },
      {
        "title": "Active Users",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(active_sessions_total)",
            "legendFormat": "Active"
          }
        ]
      }
    ]
  }
}
```

### Dashboard Categories

| Dashboard | Purpose | Refresh |
|-----------|---------|---------|
| PARWA Overview | System-wide health | 30s |
| Backend Performance | API performance metrics | 15s |
| Database Health | PostgreSQL metrics | 30s |
| Redis Metrics | Cache and queue status | 30s |
| AI Agent Performance | Jarvis and agent metrics | 1m |
| Business Metrics | Tickets, customers, revenue | 5m |

### Import Dashboards

```bash
# Import via Grafana API
curl -X POST http://grafana:3000/api/dashboards/import \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @dashboard.json

# Or use Grafana provisioning
# /etc/grafana/provisioning/dashboards/
```

---

## Alert Configuration

### Alertmanager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m
  pagerduty_url: https://events.pagerduty.com/v2/enqueue
  slack_api_url: https://slack.com/api/chat.postMessage

route:
  receiver: 'default'
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
    - match:
        severity: warning
      receiver: 'slack'

receivers:
  - name: 'default'
    slack_configs:
      - channel: '#parwa-alerts'
        send_resolved: true

  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: $PAGERDUTY_SERVICE_KEY
        severity: critical

  - name: 'slack'
    slack_configs:
      - channel: '#parwa-alerts'
        send_resolved: true
        title: '{{ .Status | toUpper }}: {{ .CommonAnnotations.summary }}'
        text: '{{ .CommonAnnotations.description }}'
```

### Alert Severities

| Severity | Response Time | Notification | Example |
|----------|---------------|--------------|---------|
| Critical | 15 minutes | PagerDuty + Slack | Service down, data loss |
| Warning | 1 hour | Slack | High latency, resource pressure |
| Info | 24 hours | Slack (low priority) | Non-critical threshold |

### Alert Silencing

For planned maintenance:

```bash
# Silence all alerts for maintenance window
amtool silence add --duration=2h --comment="Scheduled maintenance" alertname=~".*"

# Silence specific alert
amtool silence add --duration=1h --comment="Known issue" alertname=HighLatency
```

---

## Log Aggregation

### Loki Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LOGGING PIPELINE                             │
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐        │
│  │ Promtail     │────▶│ Loki        │────▶│ Grafana      │        │
│  │ (Agent)      │     │ (Storage)    │     │ (Query)      │        │
│  └──────────────┘     └──────────────┘     └──────────────┘        │
│         ▲                                                           │
│         │                                                           │
│  ┌──────┴───────┐                                                   │
│  │  Pod Logs    │                                                   │
│  │  /var/log    │                                                   │
│  └──────────────┘                                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Promtail Configuration

```yaml
# promtail-config.yml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    pipeline_stages:
      - docker: {}
      - match:
          selector: '{app="parwa-backend"}'
          stages:
            - json:
                expressions:
                  level: level
                  message: message
                  timestamp: timestamp
            - labels:
                level:
            - timestamp:
                source: timestamp
                format: RFC3339
```

### Log Query Examples

```logql
# All backend errors
{app="parwa-backend"} |= "error"

# Slow requests
{app="parwa-backend"} | json | duration > 1000

# Authentication events
{app="parwa-backend"} |= "authentication"

# Logs from specific tenant
{app="parwa-backend"} | json | tenant_id = "uuid"

# Error rate over time
sum by (level) (
  count_over_time({app="parwa-backend"} | json | level = "error" [5m])
)
```

### Log Retention

| Log Type | Retention | Storage |
|----------|-----------|---------|
| Application logs | 30 days | Loki |
| Access logs | 90 days | S3 |
| Audit logs | 2 years | PostgreSQL |
| Security logs | 2 years | S3 |

---

## Metric Descriptions

### Application Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total HTTP requests |
| `http_request_duration_seconds` | Histogram | Request latency |
| `http_requests_in_flight` | Gauge | Current active requests |
| `http_response_size_bytes` | Histogram | Response size |

### Business Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `tickets_total` | Counter | Total tickets created |
| `tickets_resolved_total` | Counter | Tickets resolved |
| `active_sessions_total` | Gauge | Active user sessions |
| `jarvis_commands_total` | Counter | Jarvis AI commands |
| `approvals_pending_total` | Gauge | Pending approvals |

### Database Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `pg_stat_activity_count` | Gauge | Active connections |
| `pg_stat_database_tup_returned` | Counter | Rows returned |
| `pg_stat_database_tup_fetched` | Counter | Rows fetched |
| `pg_replication_lag_seconds` | Gauge | Replication lag |

### Redis Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `redis_connected_clients` | Gauge | Connected clients |
| `redis_memory_used_bytes` | Gauge | Memory used |
| `redis_keyspace_keys_total` | Gauge | Total keys |
| `redis_llen` | Gauge | Queue length |

---

## SLO Definitions

### Service Level Objectives

| SLO | Target | Measurement |
|-----|--------|-------------|
| Availability | 99.9% | Uptime per month |
| Latency (P95) | < 500ms | Request duration |
| Error Rate | < 0.1% | 5xx responses |
| Throughput | 1000 req/s | Requests per second |

### SLO Dashboard

```promql
# Availability SLO (30-day window)
1 - (
  sum(rate(http_requests_total{status=~"5.."}[30d])) /
  sum(rate(http_requests_total[30d]))
)

# Latency SLO (percentage meeting target)
sum(rate(http_request_duration_seconds_bucket{le="0.5"}[30d])) /
sum(rate(http_request_duration_seconds_count[30d]))

# Error Budget remaining
(
  (1 - 0.001) - (
    sum(rate(http_requests_total{status=~"5.."}[30d])) /
    sum(rate(http_requests_total[30d]))
  )
) / (1 - 0.001) * 100
```

### Error Budget Policy

| Budget Remaining | Action |
|------------------|--------|
| > 50% | Normal operations |
| 25-50% | Reduce risky deployments |
| 10-25% | Freeze feature releases |
| < 10% | Emergency mode |

### SLI Monitoring

```yaml
# slo-rules.yml
groups:
  - name: slo-alerts
    rules:
      - alert: SLIAvailabilityBreach
        expr: |
          1 - (
            sum(rate(http_requests_total{status=~"5.."}[1h])) /
            sum(rate(http_requests_total[1h]))
          ) < 0.999
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Availability SLO at risk"

      - alert: ErrorBudgetCritical
        expr: error_budget_remaining < 0.1
        labels:
          severity: critical
        annotations:
          summary: "Error budget nearly exhausted"
```

---

## Monitoring Best Practices

### Alerting Principles

1. **Actionable alerts**: Every alert should require human action
2. **Avoid alert fatigue**: Tune thresholds to reduce noise
3. **Context in alerts**: Include debugging information
4. **Escalation paths**: Define clear escalation procedures

### Dashboard Best Practices

1. **Overview first**: High-level health before details
2. **Consistent layout**: Use templates for similar services
3. **Use variables**: Enable filtering by tenant, environment
4. **Document panels**: Add descriptions to complex panels

### Runbooks

Link runbooks in alert annotations:

```yaml
annotations:
  summary: "High error rate detected"
  runbook_url: "https://docs.parwa.ai/runbooks/high-error-rate"
```
