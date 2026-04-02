# PARWA Feature Specs — Batch 8: Analytics, Communications & Integrations

> **21 HIGH-priority features** across Agent Training (F-100–F-103), Analytics (F-109–F-119), Communications (F-123, F-125), Integrations (F-132–F-138), Billing (F-072), and Approval (F-085).
>
> **Stack:** Next.js · FastAPI · PostgreSQL + pgvector · Redis · Paddle · Brevo · Twilio · Celery · Socket.io · LiteLLM/OpenRouter

---

# F-100: Agent Lightning Training Loop

## Overview
Rapid training pipeline that takes a new AI agent from baseline to production-ready using domain-specific ticket data combined with transfer learning from PARWA's foundation model. The pipeline automates data selection, fine-tuning configuration, evaluation, and deployment into a single orchestrated workflow.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/agents/{agent_id}/train` | POST | `agent_id`, `dataset_id`, `base_model`, `epochs`, `learning_rate` | `{ run_id, status: "queued", estimated_time }` |
| `/api/training/runs/{run_id}` | GET | `run_id` | `{ status, progress_pct, epoch, metrics, logs }` |
| `/api/training/runs/{run_id}/cancel` | POST | `run_id` | `{ status: "cancelled" }` |

## DB Tables
- **`training_runs`** — `id`, `company_id`, `agent_id`, `dataset_id`, `base_model`, `status` (queued/running/completed/failed/cancelled), `progress_pct`, `epochs_completed`, `metrics` (JSONB), `checkpoint_path`, `started_at`, `completed_at`, `created_at`
- **`training_datasets`** — `id`, `company_id`, `agent_id`, `sample_count`, `format`, `s3_path`, `created_at`

## BC Rules
- **BC-004** (Background Jobs): Training orchestration runs as a Celery task with `company_id` as first param, `max_retries=3`, `soft_time_limit=3600`, DLQ for failures.
- **BC-007** (AI Model Interaction): Transfer learning uses Smart Router tier selection; base model chosen from `api_providers` table; PII redaction on all training data.
- **BC-001** (Multi-Tenant Isolation): All training runs and datasets scoped by `company_id`; no cross-tenant data leakage in training pipeline.
- **BC-012** (Error Handling): Training failure triggers DLQ + ops alert with run_id, agent_id, error stack.

## Edge Cases
1. GPU instance (Colab/RunPod) becomes unavailable mid-training — checkpoint at last completed epoch is preserved and run resumes on next available instance.
2. Training dataset is too small (< 50 samples) — pipeline rejects with clear error and recommends waiting for more ticket data.
3. Base model API key expires during training — Smart Router failover to next available base model; if all fail, run is paused and queued for retry.
4. Concurrent training runs on same agent — second run is rejected with HTTP 409; only one active training run per agent allowed.

## Acceptance
- [ ] A new agent can go from "created" to "training complete" status via the API with a valid dataset in under 60 minutes.
- [ ] Training progress is observable via GET endpoint with real-time progress percentage and epoch-level metrics.
- [ ] Failed training runs are routed to DLQ with ops alert; checkpoint from last successful epoch is preserved.
- [ ] Training data is PII-redacted before any data leaves PARWA infrastructure to the GPU provider.

---

# F-101: 50-Mistake Threshold Trigger

## Overview
Automatic training activation mechanism that fires when an AI agent accumulates exactly 50 mistake reports. Per BC-007 rule 10, this threshold is LOCKED and cannot be modified by any admin. The trigger packages error context, invokes dataset preparation (F-103), and initiates the Lightning Training Loop (F-100).

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/agents/{agent_id}/mistakes/threshold` | GET | `agent_id` | `{ current_count, threshold: 50, triggered: bool }` |
| *(Internal Celery task)* `check_mistake_threshold` | — | `company_id`, `agent_id` | Evaluates after each mistake report |

## DB Tables
- **`agent_mistakes`** — `id`, `company_id`, `agent_id`, `ticket_id`, `mistake_type`, `original_response` (TEXT), `correct_response` (TEXT), `reported_by`, `created_at`
- **`training_runs`** — (see F-100) — auto-created with `trigger="auto_threshold"` when threshold hit

## BC Rules
- **BC-007** rule 10 (LOCKED at 50 mistakes): Hard-coded constant `MISTAKE_THRESHOLD = 50`; no DB config, no env var, no admin override. If anyone modifies this value, CI must fail.
- **BC-004** (Background Jobs): Threshold check runs as a Celery task after each mistake report with `company_id` as first param.
- **BC-009** (Approval Workflow): Auto-training trigger creates an approval record logged in `audit_trail` before execution.
- **BC-012** (Error Handling): If dataset prep or training initiation fails, error is logged and a retry is scheduled within 1 hour.

## Edge Cases
1. Mistake reports arrive in rapid succession (burst) — threshold is checked atomically; no double-trigger even with concurrent requests.
2. Agent is already in training when threshold is hit — second trigger is deferred until current run completes; count continues accumulating.
3. Mistake reports span a long time period (e.g., 50 mistakes over 6 months) — still triggers; staleness warning added to training dataset metadata.
4. All 50 mistakes are from the same category (e.g., refund policy) — dataset is flagged as potentially skewed; training still proceeds but with diversity warning.

## Acceptance
- [ ] The 50th mistake report on any agent immediately queues a training run and removes the agent from active model rotation.
- [ ] The threshold value is immutable — no API endpoint, admin panel, or config can change it.
- [ ] A notification (in-app + email via Brevo) is sent to the account owner when the threshold is triggered.
- [ ] Mistake count resets to 0 only after a successful training run deployment (F-105).

---

# F-102: Training Run Execution (LOCAL)

## Overview
Orchestrates the actual training computation on external GPU infrastructure (Google Colab Pro or RunPod), managing data transfer, training loop execution, checkpointing, and result retrieval. PARWA's backend acts as the coordinator while the heavy computation runs on the GPU provider.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/training/runs/{run_id}/start` | POST | `run_id`, `provider` (colab/runpod) | `{ status: "provisioning", instance_id }` |
| `/api/training/runs/{run_id}/logs` | GET | `run_id`, `since` | `{ logs: [], last_line }` |
| `/api/training/providers/status` | GET | — | `{ providers: [{ name, available, queue_depth, cost_per_hr }] }` |

## DB Tables
- **`training_runs`** — (see F-100) — adds columns: `provider` (colab/runpod), `instance_id`, `gpu_type`, `cost_usd` DECIMAL(10,2), `provisioning_at`, `log_s3_path`
- **`training_checkpoints`** — `id`, `run_id`, `company_id`, `epoch`, `loss`, `accuracy`, `s3_path`, `created_at`

## BC Rules
- **BC-004** (Background Jobs): Training orchestration is a long-running Celery task (`soft_time_limit=3600`, `time_limit=3660`). GPU provisioning, data transfer, and monitoring each run as subtasks.
- **BC-001** (Multi-Tenant Isolation): Training data transferred to GPU provider is scoped per `company_id`; separate S3 prefixes per tenant; no shared training volumes.
- **BC-007** (AI Model Interaction): Base model selection via Smart Router; PII redaction on all training data before transfer.
- **BC-002** (Financial Actions): GPU costs tracked per run in `cost_usd` (DECIMAL); logged in `audit_trail` for cost visibility.
- **BC-012** (Error Handling): GPU instance timeout, OOM, or crash triggers checkpoint recovery and retry on new instance.

## Edge Cases
1. Colab session disconnects mid-training — last checkpoint is saved; run auto-restarts from checkpoint on new session within 5 minutes.
2. RunPod API is rate-limited during provisioning — exponential backoff (60s, 300s, 900s) before failing.
3. Training data exceeds GPU memory — automatic batch size reduction and gradient accumulation fallback.
4. S3 upload of training data fails — Celery retry with exponential backoff; DLQ after 3 failures.

## Acceptance
- [ ] Training can be initiated on both Colab and RunPod with automatic provider selection based on availability and cost.
- [ ] Checkpoints are saved every epoch and persist even if the GPU instance crashes.
- [ ] Real-time training logs are streamable to the dashboard via the logs endpoint.
- [ ] Total GPU cost per run is tracked and displayed in the ROI Dashboard (F-113).

---

# F-103: Training Dataset Preparation

## Overview
Automated pipeline that cleans, deduplicates, formats, and validates training data extracted from ticket histories and error logs. Transforms raw conversation data into structured fine-tuning datasets (instruction-input-output format) suitable for LLM fine-tuning, ensuring quality and diversity.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/training/datasets/prepare` | POST | `agent_id`, `source` (mistakes/all_tickets/custom), `min_samples` | `{ dataset_id, sample_count, stats }` |
| `/api/training/datasets/{id}` | GET | `id` | `{ id, sample_count, categories, quality_score, preview: [] }` |
| `/api/training/datasets/{id}/export` | GET | `id`, `format` (jsonl/parquet) | `{ download_url }` |

## DB Tables
- **`training_datasets`** — `id`, `company_id`, `agent_id`, `source`, `sample_count`, `format`, `quality_score` FLOAT, `category_distribution` (JSONB), `s3_path`, `created_at`
- **`training_samples`** — `id`, `dataset_id`, `company_id`, `ticket_id`, `instruction` TEXT, `input` TEXT, `output` TEXT, `category`, `quality_flag`, `created_at`

## BC Rules
- **BC-004** (Background Jobs): Dataset preparation is a Celery task with `company_id` first param, `max_retries=3`, `soft_time_limit=600`.
- **BC-007** (AI Model Interaction): Quality scoring uses Smart Router (Light tier) to evaluate sample pairs; PII redaction applied before data enters training pipeline.
- **BC-010** (Data Lifecycle): PII is stripped from training samples before storage; original ticket data is never exposed in datasets. GDPR retention applies.
- **BC-001** (Multi-Tenant Isolation): All samples scoped by `company_id`; no cross-tenant data mixing.

## Edge Cases
1. All tickets in date range have the same intent (e.g., all refund requests) — dataset flagged as low-diversity; warning shown but preparation proceeds.
2. Raw ticket data contains multilingual content — language detection runs; non-English samples are tagged but included if above minimum quality threshold.
3. A ticket has no successful AI resolution to use as training output — sample skipped; logged in preparation stats as "excluded_no_resolution".
4. Dataset preparation takes longer than 10 minutes — progress is streamed via Socket.io; user can cancel and get partial results.

## Acceptance
- [ ] Dataset preparation from "mistakes" source produces valid JSONL with instruction/input/output format for all 50+ mistake samples.
- [ ] PII is fully redacted from all training samples — no emails, phone numbers, or credit cards in exported datasets.
- [ ] Quality score is calculated for each sample; samples below 0.3 threshold are excluded with reason logged.
- [ ] Deduplication removes near-identical samples (similarity > 0.95) before export.

---

# F-109: Analytics Overview Dashboard

## Overview
The primary analytics hub providing a unified view of ticket volume, resolution rates, AI vs. human split, customer satisfaction, and trend indicators. Serves as the container for all analytics sub-widgets and the entry point for data-driven decision-making.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/analytics/overview` | GET | `range` (24h/7d/30d/90d/custom), `from`, `to` | `{ tickets_total, ai_resolved_pct, human_resolved_pct, csat_avg, resolution_time_avg, escalation_rate, trends }` |
| `/api/analytics/overview/realtime` | GET | — | `{ active_tickets, queue_depth, agents_online }` |

## DB Tables
- **`tickets`** — `id`, `company_id`, `status`, `channel`, `resolution_source` (ai/human), `resolved_at`, `created_at`, `csat_score`
- **`analytics_cache`** — `id`, `company_id`, `metric_key`, `range_key`, `value` (JSONB), `computed_at` (indexed for cache invalidation)

## BC Rules
- **BC-001** (Multi-Tenant Isolation): All analytics queries scoped by `company_id`; cached results per-tenant.
- **BC-005** (Real-Time): Realtime metrics pushed via Socket.io to `tenant_{company_id}` room; event buffer for disconnected clients.
- **BC-012** (Error Handling): If analytics query exceeds 5s timeout, return cached data with `stale: true` flag rather than failing.

## Edge Cases
1. New tenant with zero ticket history — dashboard shows empty state with onboarding prompt rather than zeros.
2. Date range spans a plan change — analytics show unified view but annotate the plan change point on trend charts.
3. Analytics cache is stale (> 5 minutes) — background refresh triggered; stale indicator shown to user.
4. Very high ticket volume tenant (> 1M tickets) — queries use pre-aggregated materialized views with daily refresh.

## Acceptance
- [ ] Dashboard loads in under 2 seconds for tenants with up to 100K tickets in the selected range.
- [ ] All metrics are filterable by date range (preset buttons + custom date picker).
- [ ] Real-time metrics update within 3 seconds of new ticket events via Socket.io.
- [ ] Dashboard gracefully handles zero-data state with helpful empty-state messaging.

---

# F-111: Key Metrics Cards

## Overview
Summary KPI cards displaying the most critical operational metrics at a glance: total tickets, auto-resolved percentage, average resolution time, CSAT score, average AI confidence, and approval queue depth. Each card includes trend sparklines and comparison to previous period.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/analytics/metrics` | GET | `range`, `compare_to` (prev_period/same_last_year) | `{ metrics: [{ key, label, value, unit, change_pct, sparkline: [] }] }` |

## DB Tables
- **`analytics_cache`** — (see F-109) — stores pre-computed metric snapshots keyed by `(company_id, metric_key, range_key)`
- **`tickets`** — aggregated via COUNT, AVG for each metric calculation

## BC Rules
- **BC-001** (Multi-Tenant Isolation): Metrics computed per `company_id` using scoped aggregate queries.
- **BC-005** (Real-Time): Metric deltas pushed via Socket.io when new tickets are resolved or approval queue changes.
- **BC-012** (Error Handling): Missing metric data returns `null` value with `status: "insufficient_data"` rather than 0.

## Edge Cases
1. Period comparison has no data for previous period — change_pct shows "N/A" instead of infinite percentage.
2. CSAT score has very few responses (< 5) — metric card shows confidence interval indicator (low sample size).
3. Sparkline data has gaps (e.g., no tickets on weekends) — gaps interpolated with dotted line rather than connecting across.
4. Agent has been active for less than 24 hours — comparison period defaults to "since activation" rather than standard ranges.

## Acceptance
- [ ] All 6 metric cards render with values, trend arrows (up/down/neutral), and percentage change from previous period.
- [ ] Sparklines show at least 30 data points for 30-day range with smooth rendering.
- [ ] Clicking any metric card navigates to the detailed drill-down view for that metric.
- [ ] Metrics refresh automatically when the time range selector (F-110) changes.

---

# F-112: Trend Charts

## Overview
Interactive line and bar charts displaying metric trends over time — ticket volume by channel, resolution rate progression, confidence evolution, and escalation frequency. Supports zoom, pan, hover tooltips, and drill-down from overview to daily granularity.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/analytics/trends` | GET | `metric` (volume/resolution/confidence/escalation), `granularity` (hourly/daily/weekly), `range`, `channel` (optional) | `{ data_points: [{ timestamp, value, breakdown: {} }] }` |
| `/api/analytics/trends/export` | GET | `metric`, `range`, `format` (csv/pdf) | `{ download_url }` |

## DB Tables
- **`analytics_time_series`** — `id`, `company_id`, `metric_key`, `granularity`, `timestamp` (TIMESTAMPTZ), `value` DECIMAL(10,2), `breakdown` (JSONB — by channel/intent), `created_at`

## BC Rules
- **BC-001** (Multi-Tenant Isolation): Time-series data scoped by `company_id`; materialized views rebuilt per-tenant.
- **BC-005** (Real-Time): New data points appended in real-time via Socket.io for hourly granularity within last 24h.
- **BC-012** (Error Handling): Chart queries exceeding 10s return partial data with `truncated: true`; async full-refresh queued.

## Edge Cases
1. Selected range has no data (brand new tenant) — chart area shows "No data available" with prompt to select a different range.
2. Granularity switch from daily to hourly for a 90-day range — auto-switches to daily with tooltip explaining hourly limited to 7-day view.
3. Multiple channels selected — stacked area chart for volume; line overlay for resolution rate with per-channel legend.
4. Chart renders on mobile — responsive layout; swipe to pan, pinch to zoom; simplified tooltip on touch.

## Acceptance
- [ ] Charts render in under 1 second for 30-day daily granularity with 4 concurrent metrics.
- [ ] Hover/click on any data point shows detailed tooltip with exact values, breakdown, and comparison.
- [ ] Users can zoom into specific date ranges within the chart and drill down to hourly granularity.
- [ ] Chart data can be exported as CSV or PDF report via the export button.

---

# F-113: ROI Dashboard

## Overview
Financial impact dashboard calculating AI automation cost savings versus estimated human-agent costs. Displays per-period and cumulative savings, cost per AI-resolved ticket, human cost avoidance, and projected annual savings based on current trends.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/analytics/roi` | GET | `range`, `human_cost_per_ticket` (optional override) | `{ ai_resolved_count, ai_cost, human_equivalent_cost, savings, savings_pct, projected_annual }` |
| `/api/analytics/roi/breakdown` | GET | `range` | `{ by_channel: {}, by_intent: {}, agent_costs: [] }` |

## DB Tables
- **`roi_snapshots`** — `id`, `company_id`, `period_start`, `period_end`, `ai_resolved_count`, `ai_cost` DECIMAL(10,2), `human_equivalent_cost` DECIMAL(10,2), `savings` DECIMAL(10,2), `created_at`
- **`agent_cost_tracking`** — `id`, `company_id`, `agent_id`, `month`, `paddle_subscription` DECIMAL(10,2), `training_cost` DECIMAL(10,2), `total_cost` DECIMAL(10,2)

## BC Rules
- **BC-002** (Financial Actions): All monetary values use DECIMAL(10,2); no float arithmetic. Human cost per ticket defaults to $12.50 but is configurable per-tenant.
- **BC-001** (Multi-Tenant Isolation): ROI calculations strictly scoped by `company_id`; no cross-tenant cost aggregation.
- **BC-005** (Real-Time): Savings counter updates in real-time via Socket.io when tickets are AI-resolved.

## Edge Cases
1. Tenant has no AI-resolved tickets yet — ROI shows $0 savings with projected savings based on industry benchmarks.
2. Human cost per ticket is overridden to an unrealistically low value — system warns if savings appear negative; minimum floor of $1.00 enforced.
3. Agent training costs spike in a single month (multiple retraining runs) — ROI shows annotated spike with tooltip explaining training investment.
4. Plan change during the selected period — ROI calculates blended rate; annotations mark the change point.

## Acceptance
- [ ] ROI dashboard shows positive savings for any tenant with > 100 AI-resolved tickets at default human cost of $12.50/ticket.
- [ ] Cumulative savings counter animates (count-up) on dashboard load.
- [ ] Breakdown by channel and intent is available for deeper cost analysis.
- [ ] Projected annual savings extrapolates from current 30-day trend with confidence interval.

---

# F-115: Confidence Trend Chart

## Overview
Dedicated analytics chart tracking AI confidence score distribution and trends over time with anomaly highlighting. When confidence drops below configured thresholds, data points are visually flagged and optionally trigger drift detection reports (F-116).

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/analytics/confidence-trend` | GET | `range`, `granularity`, `agent_id` (optional) | `{ data_points: [{ timestamp, avg_confidence, p10, p25, p50, p75, p90, anomaly: bool }], threshold_config }` |
| `/api/analytics/confidence-trend/thresholds` | PUT | `agent_id`, `warning_threshold`, `critical_threshold` | `{ updated: true }` |

## DB Tables
- **`confidence_snapshots`** — `id`, `company_id`, `agent_id`, `ticket_id`, `confidence_score` FLOAT, `component_scores` (JSONB — retrieval, intent, sentiment, history), `anomaly_flag` BOOL, `created_at`
- **`confidence_thresholds`** — `id`, `company_id`, `agent_id`, `warning_threshold` FLOAT DEFAULT 60, `critical_threshold` FLOAT DEFAULT 40, `updated_at`

## BC Rules
- **BC-007** (AI Model Interaction): Confidence scores sourced from F-059 (Confidence Scoring System); thresholds stored per-company per-agent in DB (BC-007 rule 9).
- **BC-004** (Background Jobs): Anomaly detection runs as a scheduled Celery task (daily) comparing rolling 7-day average to 30-day baseline.
- **BC-001** (Multi-Tenant Isolation): Confidence data scoped by `company_id`; thresholds configurable per-tenant.

## Edge Cases
1. Agent is newly created with very few data points — chart shows "Building baseline..." message; anomaly detection disabled until 100+ data points.
2. Confidence scores are bimodal (high for FAQ, low for complex) — distribution histogram shows dual peaks; percentile bands accurately reflect distribution.
3. All data points are above threshold — anomaly section shows "No anomalies detected" with green indicator.
4. Threshold is set too aggressively (< 20) — system warns that this may cause excessive false positive anomaly flags.

## Acceptance
- [ ] Chart renders confidence trend with percentile bands (P10–P90) and configurable warning/critical threshold lines.
- [ ] Anomalous data points are visually highlighted with click-through to the specific tickets causing the dip.
- [ ] Thresholds are configurable per agent via the PUT endpoint; changes take effect immediately.
- [ ] Daily anomaly detection identifies sustained drops (> 15% below 7-day rolling average) and flags them.

---

# F-116: Drift Detection Report

## Overview
Automated report detecting AI performance drift by analyzing increasing error rates, shifting confidence distributions, changing resolution patterns, and topic distribution shifts. Bridges analytics and the training loop by triggering alerts and recommending retraining when drift exceeds thresholds.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/analytics/drift` | GET | `agent_id`, `period` (7d/30d/90d) | `{ drift_detected: bool, drift_score: 0-100, dimensions: { confidence, errors, topics, resolution }, recommendation }` |
| `/api/analytics/drift/history` | GET | `agent_id`, `range` | `{ reports: [{ date, drift_score, actions_taken }] }` |

## DB Tables
- **`drift_reports`** — `id`, `company_id`, `agent_id`, `drift_score` FLOAT (0-100), `confidence_drift` FLOAT, `error_rate_drift` FLOAT, `topic_shift_score` FLOAT, `recommendation` TEXT, `action_taken` TEXT, `report_period_start`, `report_period_end`, `created_at`

## BC Rules
- **BC-007** (AI Model Interaction): Drift analysis uses the Smart Router to analyze sample responses; feeds into DSPy Prompt Optimization (F-061) and Time-Based Fallback Training (F-106).
- **BC-004** (Background Jobs): Drift detection runs as a scheduled Celery task (daily) with `company_id` first param; `max_retries=3`.
- **BC-012** (Error Handling): Drift report generation failure is logged but does not block other scheduled tasks; last successful report is used.

## Edge Cases
1. Drift detected but agent is already in training — report notes "retraining in progress" and suppresses duplicate retraining recommendation.
2. Tenant changes their product/knowledge base significantly — topic shift score spikes; drift report recommends manual review before retraining.
3. Drift score is borderline (45-55) — report shows "monitoring" status with recommendation to watch for 3 consecutive days before action.
4. Multiple agents have drift simultaneously — indicates potential systemic issue (model provider degradation); ops team alerted.

## Acceptance
- [ ] Daily drift report is generated for each active agent with scores across all four dimensions (confidence, errors, topics, resolution).
- [ ] Drift score > 70 triggers an in-app alert and email notification to the account owner.
- [ ] Drift report includes a natural-language recommendation (e.g., "Retrain recommended: error rate increased 23% over 14 days").
- [ ] Drift history is queryable for trend analysis of model stability over time.

---

# F-119: Post-Interaction QA Rating

## Overview
Automated quality assurance scoring system that evaluates every AI-resolved ticket on accuracy, tone, completeness, and compliance. QA scores feed into analytics (F-109), training data preparation (F-103), and the Quality Coach Reports (F-118), creating a continuous quality improvement loop.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/qa/scores` | GET | `agent_id`, `range`, `min_score` (filter) | `{ scores: [{ ticket_id, overall, accuracy, tone, completeness, compliance }] }` |
| `/api/qa/scores/{ticket_id}` | GET | `ticket_id` | `{ overall, dimensions: {}, feedback, flagged: bool }` |
| *(Internal Celery task)* `score_ticket_qa` | — | `company_id`, `ticket_id` | Writes QA score after ticket resolution |

## DB Tables
- **`qa_scores`** — `id`, `company_id`, `ticket_id`, `agent_id`, `overall_score` FLOAT (0-100), `accuracy_score` FLOAT, `tone_score` FLOAT, `completeness_score` FLOAT, `compliance_score` FLOAT, `feedback` TEXT, `flagged` BOOL DEFAULT false, `created_at`

## BC Rules
- **BC-007** (AI Model Interaction): QA scoring uses Smart Router (Light tier) to evaluate responses; the QA prompt is version-controlled.
- **BC-004** (Background Jobs): QA scoring runs as a Celery task immediately after ticket resolution; `company_id` first param; `max_retries=3`.
- **BC-001** (Multi-Tenant Isolation): QA scores scoped by `company_id`; no cross-tenant quality comparisons exposed.

## Edge Cases
1. Ticket resolution contains a refund action — compliance score is weighted higher; refund amount verified against policy.
2. AI response is in a non-English language — QA scoring prompt adapts to the detected language; tone evaluation is culture-aware.
3. Ticket was human-overridden (AI response edited by agent) — QA score compares original AI response and final human-edited version; delta shows AI quality gap.
4. QA model returns inconsistent scores for similar tickets — scoring prompt is flagged for DSPy optimization (F-061).

## Acceptance
- [ ] Every AI-resolved ticket receives a QA score within 30 seconds of resolution.
- [ ] QA scores have four dimension sub-scores (accuracy, tone, completeness, compliance) plus an overall weighted score.
- [ ] Tickets with QA score < 40 are automatically flagged for review and added to the training dataset (F-103).
- [ ] Average QA score per agent is visible in Agent Performance Metrics (F-098).

---

# F-123: Email Rate Limiting (5/thread/24h)

## Overview
Enforces a maximum of 5 outbound automated emails per conversation thread per 24-hour period per customer email address. This is a hard safety cap preventing email loops and spam behavior, as mandated by BC-006 rule 2, and operates as a final backstop after OOO detection.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/email/rate-limit/check` | GET | `thread_id`, `recipient_email` | `{ count_24h, remaining, allowed: bool }` |
| *(Internal — called before every outbound email)* | — | `thread_id`, `recipient_email` | Raises `RateLimitExceeded` if >= 5 |

## DB Tables
- **`email_logs`** — `id`, `company_id`, `thread_id`, `recipient`, `template_used`, `status`, `related_entity_type`, `related_entity_id`, `created_at`
- **`email_rate_limits`** — `id`, `company_id`, `thread_id`, `recipient`, `count_24h` INT, `window_start` TIMESTAMPTZ, `blocked` BOOL DEFAULT false

## BC Rules
- **BC-006** rule 2 (5 replies/thread/24h): Hard limit, non-configurable. Counter resets on 24-hour rolling window.
- **BC-006** rule 3 (5 emails/customer/hour): Additional per-customer hourly limit enforced alongside thread limit.
- **BC-012** (Error Handling): Rate limit exceeded does not throw an error to the customer; it silently suppresses and logs the suppression event.
- **BC-004** (Background Jobs): Window reset runs as a Celery beat task (hourly) to clean expired rate limit records.

## Edge Cases
1. Customer sends 10 messages in 1 hour — only 5 responses sent; 6th onward silently suppressed with log entry.
2. Thread ID is null (new conversation from email with no thread match) — rate limit tracked by recipient email + "new_thread" sentinel.
3. Multiple agents try to respond to same thread simultaneously — rate limit check is atomic (SELECT FOR UPDATE); only one response sent.
4. Rate limit is hit during an active conversation — Socket.io notification sent to the assigned agent: "Email rate limit reached for this thread. Consider switching to chat."

## Acceptance
- [ ] The 6th automated email attempt to the same thread within 24 hours is suppressed and logged.
- [ ] Rate limit status is queryable via the check endpoint before attempting to send.
- [ ] The 24-hour window is rolling (not fixed daily reset) — based on timestamps of actual sent emails.
- [ ] Agents receive a real-time notification (Socket.io + in-app) when email rate limit is reached on an active thread.

---

# F-125: Chat Widget (Live on Landing + Dashboard)

## Overview
Dual-purpose embeddable chat widget serving as the customer-facing live demo on the public landing page and the internal agent co-pilot chat within the authenticated dashboard. The widget shares a common UI shell but connects to different backends based on context.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/chat/send` | POST | `message`, `context` (landing/dashboard), `session_id`, `ticket_id` (optional) | `{ response, confidence, sources[] }` |
| `/api/chat/history` | GET | `session_id` | `{ messages: [{ role, content, timestamp }] }` |
| `/api/chat/widget/config` | GET | `context` (landing/dashboard) | `{ widget_id, theme, position, greeting, capabilities }` |

## DB Tables
- **`chat_sessions`** — `id`, `company_id` (nullable for landing), `context` (landing/dashboard), `visitor_id`, `session_data` (JSONB), `created_at`, `last_active_at`
- **`chat_messages`** — `id`, `session_id`, `role` (user/assistant/system), `content` TEXT, `confidence_score` FLOAT, `sources` (JSONB), `created_at`

## BC Rules
- **BC-005** (Real-Time): Chat messages streamed via Socket.io; typing indicators; partial response streaming.
- **BC-001** (Multi-Tenant Isolation): Dashboard chat scoped by `company_id`; landing chat uses a shared anonymous context with no tenant data access.
- **BC-011** (Authentication & Security): Landing widget is unauthenticated but rate-limited (10 msgs/visitor); dashboard widget requires valid JWT.
- **BC-007** (AI Model Interaction): Responses routed through Smart Router; PII redacted before LLM call; Guardrails check on all outputs.

## Edge Cases
1. Landing page visitor asks tenant-specific questions — widget responds with generic PARWA information; never exposes any tenant data.
2. Dashboard chat is opened for a specific ticket — conversation context is pre-loaded with ticket history for contextual responses.
3. Chat session exceeds 50 messages — context compression (F-067) triggered automatically; older messages summarized.
4. Widget fails to connect Socket.io — graceful degradation to polling (GET /history every 3s); full streaming restored on reconnect.

## Acceptance
- [ ] Landing chat widget loads in under 2 seconds and responds to first message in under 5 seconds.
- [ ] Dashboard chat widget shows contextual ticket information when opened from a ticket detail view.
- [ ] Chat responses stream token-by-token via Socket.io with typing indicator.
- [ ] Widget is embeddable via a single `<script>` tag with tenant-specific configuration.

---

# F-132: Custom REST API Connector

## Overview
User-configurable REST integration builder allowing tenants to define custom API connections with arbitrary endpoints, authentication methods (API key, OAuth2, Basic Auth, Bearer), request/response mapping, and test connectivity validation — all without code deployment.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/integrations/rest` | POST | `name`, `base_url`, `auth_type`, `auth_config`, `endpoints[]` | `{ connector_id, status: "configured" }` |
| `/api/integrations/rest/{id}` | PUT | `id`, `updates` | `{ connector_id, status: "updated" }` |
| `/api/integrations/rest/{id}/test` | POST | `id`, `endpoint_key` | `{ success, response_time_ms, sample_response, errors[] }` |
| `/api/integrations/rest/{id}` | DELETE | `id` | `{ status: "deleted" }` |

## DB Tables
- **`rest_connectors`** — `id`, `company_id`, `name`, `base_url`, `auth_type` (api_key/oauth2/basic/bearer), `auth_config` (JSONB — encrypted), `endpoints` (JSONB), `status` (active/disabled), `last_test_at`, `last_test_result` (JSONB), `created_at`, `updated_at`
- **`connector_usage_logs`** — `id`, `connector_id`, `company_id`, `endpoint_path`, `method`, `status_code`, `response_time_ms`, `error_message`, `created_at`

## BC Rules
- **BC-003** (Webhook Handling): Outbound REST calls log request/response in `connector_usage_logs`; failed calls follow retry pattern.
- **BC-011** (Authentication & Security): Auth credentials (API keys, OAuth tokens) encrypted at rest (AES-256) and never returned in API responses; only masked values shown.
- **BC-001** (Multi-Tenant Isolation): Connectors scoped by `company_id`; no cross-tenant connector access.
- **BC-012** (Error Handling): Test connectivity has a 10s timeout; failed tests return descriptive error messages.

## Edge Cases
1. OAuth2 token expires — system attempts automatic refresh; if refresh fails, connector marked as "auth_expired" and notification sent.
2. Base URL changes — all endpoints re-tested automatically; failed endpoints disabled with warning.
3. Connector endpoint returns unexpected schema — response mapping falls back to raw JSON; error logged.
4. Tenant deletes a connector that is actively referenced by an agent workflow — deletion blocked with reference list shown.

## Acceptance
- [ ] User can configure a REST connector with API key auth and test connectivity in under 2 minutes.
- [ ] Encrypted auth credentials are stored securely and never exposed in API responses or logs.
- [ ] Test connectivity returns response time, status code, and sample response body.
- [ ] Connector status is visible in the Integration Health Monitor (F-137).

---

# F-134: Webhook Integration (Incoming)

## Overview
HTTP POST receiver that validates incoming webhook signatures, transforms payloads using configurable mapping rules, and routes events to PARWA workflows. Supports custom signature verification algorithms and flexible payload transformation pipelines.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/integrations/webhooks/incoming/{connector_id}` | POST | Raw body + headers (from external provider) | `{ status: "accepted" }` (async processing) |
| `/api/integrations/webhooks/config` | POST | `name`, `signature_type`, `signature_header`, `secret`, `payload_mapping` (JSONB) | `{ webhook_id, endpoint_url }` |
| `/api/integrations/webhooks/{id}/logs` | GET | `id`, `status` (success/failed) | `{ logs: [{ event_id, received_at, processing_status, error }] }` |

## DB Tables
- **`webhook_integrations`** — `id`, `company_id`, `name`, `signature_type` (hmac_sha256/custom/none), `signature_header`, `secret` (encrypted), `payload_mapping` (JSONB), `target_workflow`, `endpoint_path` (auto-generated), `status` (active/disabled), `created_at`
- **`webhook_events`** — `id`, `company_id`, `integration_id`, `event_id` (from provider), `event_type`, `payload` (JSONB), `status` (pending/processing/completed/failed), `created_at`, `processed_at`, `error_message`

## BC Rules
- **BC-003** (Webhook Handling): HMAC signature verification before processing; idempotency via `event_id` UNIQUE constraint; async processing via Celery; response within 3 seconds.
- **BC-011** (Authentication & Security): Webhook secrets encrypted at rest; signature verification uses constant-time comparison.
- **BC-001** (Multi-Tenant Isolation): Webhook endpoint paths include `connector_id` to enforce tenant scoping.
- **BC-004** (Background Jobs): Processing runs as Celery task with `company_id` first param; `max_retries=3` with exponential backoff.

## Edge Cases
1. External provider sends duplicate webhook (same event_id) — idempotency check returns 200 with `already_processed`.
2. Signature verification fails — request rejected with HTTP 403; attempt logged in `webhook_events` with status=failed.
3. Payload transformation fails (mapping error) — event stored as `failed`; error details returned in logs endpoint.
4. External provider sends extremely large payload (> 5MB) — rejected with HTTP 413; logged as failed.

## Acceptance
- [ ] Webhook endpoint validates HMAC-SHA256 signatures using constant-time comparison.
- [ ] Duplicate events are idempotently handled — no side effect on second delivery.
- [ ] Processing is asynchronous — HTTP 200 returned within 3 seconds regardless of processing complexity.
- [ ] All webhook events are logged with full payload, status, and error details for auditing.

---

# F-135: MCP Integration

## Overview
Model Context Protocol (MCP) support enabling PARWA AI agents to use external tools via standardized MCP server connections. Agents can dynamically discover available tools, invoke them with structured parameters, and incorporate results into their reasoning pipeline.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/integrations/mcp` | POST | `name`, `server_url`, `auth_config`, `tool_filter[]` | `{ mcp_id, tools_discovered: [] }` |
| `/api/integrations/mcp/{id}/tools` | GET | `id` | `{ tools: [{ name, description, parameters }] }` |
| `/api/integrations/mcp/{id}/invoke` | POST | `id`, `tool_name`, `parameters` | `{ result, latency_ms }` |
| `/api/integrations/mcp/{id}` | DELETE | `id` | `{ status: "disconnected" }` |

## DB Tables
- **`mcp_connections`** — `id`, `company_id`, `name`, `server_url`, `auth_type`, `auth_config` (JSONB — encrypted), `tool_filter` (JSONB), `status` (connected/disconnected/error), `last_heartbeat`, `discovered_tools` (JSONB), `created_at`
- **`mcp_invocation_logs`** — `id`, `connection_id`, `company_id`, `tool_name`, `parameters` (JSONB), `result` (JSONB), `latency_ms`, `error_message`, `created_at`

## BC Rules
- **BC-007** (AI Model Interaction): MCP tool results feed into the Smart Router as additional context; tool invocation is part of the GSD state machine.
- **BC-003** (Webhook Handling): MCP server heartbeat monitoring follows webhook-style verification and retry patterns.
- **BC-001** (Multi-Tenant Isolation): MCP connections scoped by `company_id`; agents can only invoke tools from their tenant's connections.
- **BC-012** (Error Handling): MCP tool invocation timeout is 30 seconds; failures trigger circuit breaker (F-139).

## Edge Cases
1. MCP server goes offline mid-conversation — agent gracefully falls back to available tools; user notified of tool unavailability.
2. MCP tool returns unexpected data format — Smart Router wraps raw result in standardized envelope; parsing error logged.
3. Tool invocation exceeds rate limits of the external MCP server — backoff applied; tool temporarily marked as throttled.
4. Agent references a tool that was deleted — invocation fails gracefully with "Tool not available" message; no conversation break.

## Acceptance
- [ ] PARWA can connect to a standards-compliant MCP server and discover available tools automatically.
- [ ] Agents can invoke MCP tools with structured parameters and incorporate results into customer responses.
- [ ] MCP connection status is monitored and displayed in the Integration Health Monitor (F-137).
- [ ] Tool invocation latency is tracked and logged for performance analysis.

---

# F-136: Database Connection Integration

## Overview
Secure database connector supporting PostgreSQL, MySQL, MongoDB, and Redis for real-time order lookups, inventory checks, and customer data retrieval during AI conversations. Connections are read-only by default with configurable query templates.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/integrations/db` | POST | `name`, `db_type` (postgres/mysql/mongo/redis), `connection_string` (encrypted), `query_templates[]` | `{ connector_id, status: "connected", tables_discovered: [] }` |
| `/api/integrations/db/{id}/query` | POST | `id`, `template_key`, `params` | `{ rows: [], row_count, query_time_ms }` |
| `/api/integrations/db/{id}/test` | POST | `id` | `{ success, latency_ms, version }` |
| `/api/integrations/db/{id}` | DELETE | `id` | `{ status: "disconnected" }` |

## DB Tables
- **`db_connections`** — `id`, `company_id`, `name`, `db_type`, `connection_config` (JSONB — encrypted), `query_templates` (JSONB), `readonly` BOOL DEFAULT true, `status` (connected/disconnected/error), `max_query_time_ms` INT DEFAULT 5000, `last_test_at`, `created_at`
- **`db_query_logs`** — `id`, `connector_id`, `company_id`, `template_key`, `params` (JSONB), `row_count`, `query_time_ms`, `error_message`, `created_at`

## BC Rules
- **BC-011** (Authentication & Security): Connection strings encrypted at rest (AES-256); credentials never logged. Read-only enforced by default; write access requires explicit approval.
- **BC-001** (Multi-Tenant Isolation): Each tenant's DB connector is isolated; no cross-tenant query execution.
- **BC-003** (Webhook Handling): Connection health checks follow retry/circuit breaker patterns.
- **BC-012** (Error Handling): Query timeout enforced at 5 seconds (configurable); failed queries logged but never crash the system.

## Edge Cases
1. External database is unreachable — connection marked as "error"; circuit breaker activates; agent uses cached data if available.
2. Query returns extremely large result set (> 1000 rows) — result is paginated; only first 100 rows returned with "more available" indicator.
3. Query template has SQL injection attempt — parameterized queries only; literal SQL execution blocked; attempt logged and flagged.
4. Connection pool is exhausted — new queries queued; oldest idle connections recycled; overflow rejected with 503.

## Acceptance
- [ ] User can configure a PostgreSQL connection and test connectivity within the integration builder.
- [ ] Query templates support parameterized inputs — raw SQL execution is blocked.
- [ ] All queries are read-only by default; write access requires explicit admin approval.
- [ ] Query latency is tracked and visible in the Integration Health Monitor (F-137).

---

# F-137: Integration Health Monitor

## Overview
Real-time dashboard monitoring all configured integrations with per-connector status, last sync timestamp, error rates, latency metrics, and auto-alerting. Serves as the single pane of glass for integration operations and feeds into the System Status Panel (F-088).

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/integrations/health` | GET | — | `{ integrations: [{ id, name, type, status, last_sync, error_rate, avg_latency_ms, uptime_pct }] }` |
| `/api/integrations/health/{id}` | GET | `id` | `{ ...detailed health, recent_errors: [], latency_history: [] }` |
| `/api/integrations/health/alerts` | GET | `severity` (warning/critical) | `{ alerts: [{ integration_id, message, timestamp, acknowledged }] }` |
| `/api/integrations/health/{id}/acknowledge` | POST | `id` | `{ acknowledged: true }` |

## DB Tables
- **`integration_health`** — `id`, `company_id`, `integration_id`, `integration_type` (rest/webhook/mcp/db/prebuilt), `status` (healthy/degraded/down/unknown), `last_check_at`, `last_success_at`, `error_count_24h`, `avg_latency_ms`, `uptime_pct` FLOAT, `created_at`, `updated_at`
- **`integration_alerts`** — `id`, `company_id`, `integration_id`, `severity` (warning/critical), `message`, `acknowledged` BOOL DEFAULT false, `created_at`, `acknowledged_at`

## BC Rules
- **BC-012** (Error Handling): Health checks run on Celery beat (every 60s); consecutive failures trigger alerts at warning (3 failures) and critical (5 failures) thresholds.
- **BC-005** (Real-Time): Health status changes pushed via Socket.io to `tenant_{company_id}` room in real-time.
- **BC-001** (Multi-Tenant Isolation): Health data scoped by `company_id`; each tenant sees only their own integrations.
- **BC-004** (Background Jobs): Health check tasks accept `company_id` first param; DLQ for persistent failures.

## Edge Cases
1. All integrations go down simultaneously — critical system alert sent to ops team; Trust Preservation Protocol (F-094) activated.
2. Health check itself fails (e.g., Celery worker down) — "monitoring degraded" status shown; last known good state displayed.
3. Integration flaps between healthy and degraded — alert suppression for 10 minutes after acknowledgment to prevent alert fatigue.
4. Tenant has no integrations configured — health monitor shows "No integrations configured" with link to integration setup (F-030).

## Acceptance
- [ ] Health monitor displays status for all integration types (REST, webhook, MCP, DB, pre-built) in a unified view.
- [ ] Status transitions (healthy → degraded → down) trigger real-time Socket.io updates to all connected dashboard clients.
- [ ] Alerts are generated at configurable thresholds and can be acknowledged to suppress notifications.
- [ ] Historical health data (latency, uptime) is queryable for the last 30 days.

---

# F-138: Outgoing Webhooks

## Overview
Event delivery system that sends webhook notifications from PARWA to external systems when specified actions occur (ticket resolved, refund issued, customer created, etc.). Implements retry logic with exponential backoff, delivery tracking, and configurable payload templates.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/webhooks/outgoing` | POST | `name`, `url`, `events[]`, `secret`, `payload_template` (JSONB), `headers` (JSONB) | `{ webhook_id, status: "active" }` |
| `/api/webhooks/outgoing/{id}` | PUT | `id`, `updates` | `{ webhook_id, status: "updated" }` |
| `/api/webhooks/outgoing/{id}/deliveries` | GET | `id`, `status` (success/failed/pending) | `{ deliveries: [{ id, event_type, status, attempts, last_attempt_at, response_code }] }` |
| `/api/webhooks/outgoing/{id}/replay` | POST | `id`, `delivery_id` | `{ status: "replayed" }` |

## DB Tables
- **`outgoing_webhooks`** — `id`, `company_id`, `name`, `url`, `events` (JSONB array of event types), `secret` (encrypted), `payload_template` (JSONB), `custom_headers` (JSONB), `status` (active/paused), `retry_count` INT DEFAULT 3, `timeout_ms` INT DEFAULT 10000, `created_at`
- **`webhook_deliveries`** — `id`, `company_id`, `webhook_id`, `event_type`, `payload` (JSONB), `target_url`, `status` (pending/success/failed), `attempts` INT DEFAULT 0, `last_response_code`, `last_error`, `next_retry_at`, `created_at`, `completed_at`

## BC Rules
- **BC-003** (Webhook Handling): HMAC-SHA256 signature on all outgoing payloads; delivery attempts logged with full request/response; retry with exponential backoff (60s, 300s, 900s).
- **BC-004** (Background Jobs): Delivery runs as Celery task with `company_id` first param; `max_retries` matches webhook config; DLQ for permanent failures.
- **BC-011** (Authentication & Security): Webhook secrets encrypted at rest; target URLs validated for HTTPS only (no HTTP).
- **BC-012** (Error Handling): Delivery timeout at 10 seconds; consecutive failures after all retries marked as permanent failure with ops alert.

## Edge Cases
1. Target endpoint returns HTTP 5xx — retry with exponential backoff up to configured max; 4xx errors are NOT retried (client error).
2. Target endpoint is slow (> 10s timeout) — connection terminated; logged as timeout; retry scheduled.
3. Webhook secret is rotated — new signature applies to all future deliveries; existing pending deliveries use old secret until retry.
4. Tenant creates a webhook with a self-referencing URL (pointing to PARWA) — URL validation blocks PARWA's own domains to prevent infinite loops.

## Acceptance
- [ ] Outgoing webhook is delivered within 5 seconds of the triggering event with HMAC-SHA256 signature.
- [ ] Failed deliveries retry with exponential backoff (60s, 300s, 900s); 4xx errors are not retried.
- [ ] Delivery history is queryable showing all attempts, response codes, and error messages.
- [ ] Admin can replay a failed delivery manually via the replay endpoint.

---

# F-072: Subscription Change Proration

## Overview
Calculates and applies prorated charges or credits when subscriptions are upgraded, downgraded, or cancelled mid-cycle. Delegates core proration math to Paddle's API while handling local entitlement updates, agent deprovisioning scheduling, and notification flows.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/billing/subscription/proration-preview` | GET | `new_plan_id`, `effective_date` (optional) | `{ current_plan, new_plan, prorated_charge, prorated_credit, net_amount, effective_date }` |
| *(Internal — triggered by F-021 subscription change)* | — | `company_id`, `old_plan_id`, `new_plan_id` | Calls Paddle proration API + updates local state |

## DB Tables
- **`subscriptions`** — `id`, `company_id`, `paddle_subscription_id`, `plan_id`, `status` (active/paused/cancelled), `current_period_start`, `current_period_end`, `created_at`
- **`proration_records`** — `id`, `company_id`, `subscription_id`, `old_plan_id`, `new_plan_id`, `prorated_charge` DECIMAL(10,2), `prorated_credit` DECIMAL(10,2), `net_amount` DECIMAL(10,2), `effective_date`, `paddle_transaction_id`, `created_at`
- **`audit_trail`** — (see BC-002) — logs all proration calculations

## BC Rules
- **BC-002** (Financial Actions): All amounts as DECIMAL(10,2); atomic DB transactions; Paddle API failure triggers rollback; audit trail logged.
- **BC-002** rule 10: Subscription changes MUST delegate proration to Paddle's API. Local DB only stores the result.
- **BC-004** (Background Jobs): Agent deprovisioning on downgrade scheduled via Celery with appropriate delay (end of billing period).
- **BC-001** (Multi-Tenant Isolation): Proration records scoped by `company_id`; no cross-tenant subscription operations.

## Edge Cases
1. Downgrade from High to Starter with 5 active agents — 3 excess agents flagged for deprovisioning; Celery task scheduled for end of billing period.
2. Mid-cycle plan change followed immediately by cancellation — Paddle handles stacking of proration credit and cancellation; PARWA reflects final state.
3. Paddle API timeout during proration — DB transaction rolled back; user sees "Retry" button; no partial state left.
4. Annual subscriber downgrades to monthly — proration preview clearly shows credit for unused annual months.

## Acceptance
- [ ] Proration preview accurately calculates net charge/credit before plan change confirmation.
- [ ] Proration is delegated to Paddle API; local DB stores the result for display and audit purposes.
- [ ] Agent deprovisioning on downgrade is scheduled via Celery and executes at the correct time.
- [ ] All proration calculations are logged in the audit trail with amounts, plans, and Paddle transaction IDs.

---

# F-085: Voice Confirmation (Mobile)

## Overview
Mobile-first approval flow allowing supervisors to approve or reject pending tickets via voice commands. The system reads a TTS summary of the ticket and proposed action, then listens for a voice command ("approve" / "reject" / "skip") to execute the corresponding action.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/approval/voice/{ticket_id}/summary` | GET | `ticket_id` | `{ audio_url, text_summary, proposed_action, confidence_score }` |
| `/api/approval/voice/{ticket_id}/confirm` | POST | `ticket_id`, `voice_command` (approve/reject/skip), `audio_duration_ms` | `{ status: "approved/rejected/skipped", ticket_id }` |

## DB Tables
- **`voice_approval_logs`** — `id`, `company_id`, `ticket_id`, `user_id`, `text_summary`, `voice_command`, `confidence` FLOAT, `audio_duration_ms`, `created_at`
- **`approval_records`** — (see BC-009) — updated with `action_source: "voice"` when voice confirmation used

## BC Rules
- **BC-009** (Approval Workflow): Voice confirmation creates a full approval record with `action_source: "voice"`; undo system (F-084) works identically for voice-approved actions.
- **BC-005** (Real-Time): Approval result pushed via Socket.io to update all connected dashboard clients immediately.
- **BC-007** (AI Model Interaction): STT (Speech-to-Text) via Smart Router (Light tier); voice command validation uses keyword matching with confidence threshold (0.8).
- **BC-011** (Authentication & Security): Voice endpoint requires JWT authentication; device fingerprint logged; replay attacks prevented via nonce in TTS audio URL.

## Edge Cases
1. Ambient noise causes false "approve" — STT confidence below 0.8 threshold; system re-prompts "I didn't catch that. Please say approve, reject, or skip."
2. Supervisor says "reject" but meant "approve" — 3-second undo window after confirmation; voice log stores audio for dispute resolution.
3. TTS summary is too long (> 30 seconds) — summary auto-truncated to key facts (customer, intent, proposed action, confidence).
4. Voice command is in a language other than English — STT model auto-detects language; commands supported in English, Spanish, French, German.

## Acceptance
- [ ] Supervisor can listen to a TTS ticket summary and respond with a voice command to approve, reject, or skip.
- [ ] Voice commands are validated with > 0.8 STT confidence; low-confidence inputs are re-prompted.
- [ ] Voice-approved actions are logged with audio duration, command text, and user identity in the approval record.
- [ ] Approval result is immediately reflected across all connected dashboard clients via Socket.io.
