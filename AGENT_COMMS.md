# AGENT_COMMS.md — Week 13 Day 1-6
# Last updated: Manager Agent
# Current status: WEEK 13 TASKS WRITTEN — AWAITING BUILDERS

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 13 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-22

> **Phase: Phase 3 — Variants & Integrations (Agent Lightning + Workers)**
>
> **Week 13 Goals:**
> - Day 1: Data Export + Model Registry (4 files)
> - Day 2: Training Pipeline (4 files)
> - Day 3: Fine Tune + Validation + Monitoring (4 files)
> - Day 4: Background Workers (5 files)
> - Day 5: Remaining Workers + Quality Coach (7 files)
> - Day 6: Tester Agent runs full week validation
>
> **CRITICAL RULES:**
> 1. All 5 days run in PARALLEL — no cross-day dependencies
> 2. Within-day files CAN depend on each other — build in order listed
> 3. No Docker — use mocked sessions in tests
> 4. Build → Unit Test passes → THEN push (ONE push per file)
> 5. Type hints on ALL functions, docstrings on ALL classes/functions
> 6. **Agent Lightning uses Unsloth + Colab FREE tier**
> 7. validate.py: BLOCKS deployment at <90% accuracy
> 8. validate.py: ALLOWS deployment at 91%+ accuracy
> 9. All 8 workers must register with ARQ without errors
> 10. Burst mode: activates instantly, billing updated, auto-expires

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — Data Export + Model Registry
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `agent_lightning/__init__.py`
2. `agent_lightning/data/__init__.py`
3. `agent_lightning/data/export_mistakes.py`
4. `agent_lightning/data/export_approvals.py`
5. `agent_lightning/data/dataset_builder.py`
6. `agent_lightning/deployment/__init__.py`
7. `agent_lightning/deployment/model_registry.py`

### Field 2: What is each file?
1. `agent_lightning/__init__.py` — Module init for Agent Lightning
2. `agent_lightning/data/__init__.py` — Module init for data export
3. `agent_lightning/data/export_mistakes.py` — Export training mistakes from DB
4. `agent_lightning/data/export_approvals.py` — Export approval decisions for training
5. `agent_lightning/data/dataset_builder.py` — Build JSONL dataset from exports
6. `agent_lightning/deployment/__init__.py` — Module init for deployment
7. `agent_lightning/deployment/model_registry.py` — Model version registry

### Field 3: Responsibilities

**agent_lightning/data/export_mistakes.py:**
- `ExportMistakes` class with:
  - `async export(self, company_id: str, limit: int = 100) -> list[dict]` — Export mistakes
  - `async get_negative_rewards(self, company_id: str) -> list[dict]` — Get negative reward records
  - `async get_correction_data(self, interaction_id: str) -> dict` — Get correction data
  - **Test: Mistakes exported in correct format for training**

**agent_lightning/data/export_approvals.py:**
- `ExportApprovals` class with:
  - `async export(self, company_id: str, limit: int = 100) -> list[dict]` — Export approvals
  - `async get_approved_refunds(self, company_id: str) -> list[dict]` — Get approved refunds
  - `async get_rejected_refunds(self, company_id: str) -> list[dict]` — Get rejected refunds
  - **Test: Approvals exported with reasoning**

**agent_lightning/data/dataset_builder.py:**
- `DatasetBuilder` class with:
  - `async build(self, company_id: str) -> str` — Build JSONL dataset
  - `async merge_exports(self, mistakes: list, approvals: list) -> list[dict]` — Merge data
  - `async validate_format(self, dataset: list) -> bool` — Validate JSONL format
  - **CRITICAL: Test: JSONL dataset built correctly with 50+ entries**
  - Returns path to JSONL file

**agent_lightning/deployment/model_registry.py:**
- `ModelRegistry` class with:
  - `async register_model(self, version: str, metrics: dict) -> dict` — Register new model version
  - `async get_current_model(self) -> dict` — Get current deployed model
  - `async list_versions(self, limit: int = 10) -> list[dict]` — List model versions
  - `async set_active(self, version: str) -> dict` — Set active model version
  - **Test: Model version registered correctly**

### Field 4: Depends On
- `backend/models/training_data.py` (Wk3)
- `shared/core_functions/config.py` (Wk1)

### Field 5: Expected Output
- Mistakes exported in correct format
- Approvals exported with reasoning
- JSONL dataset built with 50+ entries
- Model registry tracks versions

### Field 6: Unit Test Files
- `tests/unit/test_agent_lightning_data.py`
  - Test: Mistakes exported in correct format
  - Test: Approvals exported with reasoning
  - Test: JSONL dataset built correctly
  - Test: Model version registered

### Field 7: BDD Scenario
- `docs/bdd_scenarios/agent_lightning_bdd.md` — Training scenarios

### Field 8: Error Handling
- Export errors → log and continue with partial data
- Dataset build errors → raise with clear message
- Registry errors → log and retry

### Field 9: Security Requirements
- Training data company-isolated
- Model versions immutable
- Registry access controlled

### Field 10: Integration Points
- Training data model (Wk3)
- Config (Wk1)

### Field 11: Code Quality
- Type hints on ALL functions
- Docstrings required (Google style)
- PEP 8 compliant
- Max 40 lines per function

### Field 12: GitHub CI Requirements
- pytest pass
- flake8 pass
- black --check pass
- CI green

### Field 13: Pass Criteria
Builder 1 reports DONE when:
- All 7 files built and pushed
- **CRITICAL: JSONL dataset with 50+ entries**
- Model registry working
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — Training Pipeline
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `agent_lightning/training/__init__.py`
2. `agent_lightning/training/trainer.py`
3. `agent_lightning/training/unsloth_optimizer.py`
4. `agent_lightning/deployment/deploy_model.py`
5. `agent_lightning/deployment/rollback.py`

### Field 2: What is each file?
1. `agent_lightning/training/__init__.py` — Module init for training
2. `agent_lightning/training/trainer.py` — Main trainer class (Unsloth + Colab FREE)
3. `agent_lightning/training/unsloth_optimizer.py` — Unsloth optimization for fast training
4. `agent_lightning/deployment/deploy_model.py` — Deploy model to registry
5. `agent_lightning/deployment/rollback.py` — Rollback to previous model version

### Field 3: Responsibilities

**agent_lightning/training/trainer.py:**
- `Trainer` class with:
  - `async train(self, dataset_path: str, config: dict) -> dict` — Run training
  - `async evaluate(self, model_path: str) -> dict` — Evaluate model
  - `get_training_config(self) -> dict` — Get default config
  - **Uses Unsloth + Colab FREE tier for cost-effective training**
  - **Test: Trainer initialises correctly**

**agent_lightning/training/unsloth_optimizer.py:**
- `UnslothOptimizer` class with:
  - `apply_optimizations(self, model_config: dict) -> dict` — Apply Unsloth optimizations
  - `get_memory_footprint(self) -> float` — Get memory usage
  - `optimize_for_colab_free(self) -> dict` — Optimize for Colab FREE tier
  - **Test: Unsloth optimizer applies correctly**

**agent_lightning/deployment/deploy_model.py:**
- `ModelDeployer` class with:
  - `async deploy(self, model_path: str, version: str) -> dict` — Deploy model
  - `async verify_deployment(self, version: str) -> bool` — Verify deployment
  - `async promote_to_production(self, version: str) -> dict` — Promote to production
  - **Test: Model deployed to registry**

**agent_lightning/deployment/rollback.py:**
- `ModelRollback` class with:
  - `async rollback(self, target_version: str) -> dict` — Rollback to version
  - `async get_previous_version(self) -> dict` — Get previous stable version
  - `async verify_rollback(self, version: str) -> bool` — Verify rollback success
  - **Test: Rollback restores previous version**

### Field 4: Depends On
- `shared/core_functions/config.py` (Wk1)
- `agent_lightning/deployment/model_registry.py` (Day 1)

### Field 5: Expected Output
- Trainer initializes with Unsloth config
- Unsloth optimizer applies optimizations
- Model deployment works end-to-end
- Rollback restores previous version

### Field 6: Unit Test Files
- `tests/unit/test_agent_lightning_training.py`
  - Test: Trainer initializes correctly
  - Test: Unsloth optimizer applies
  - Test: Model deployed to registry
  - Test: Rollback restores previous version

### Field 7: BDD Scenario
- `docs/bdd_scenarios/agent_lightning_bdd.md` — Training pipeline scenarios

### Field 8: Error Handling
- Training errors → log and notify
- Deployment errors → rollback automatically
- Rollback errors → alert immediately

### Field 9: Security Requirements
- Model artifacts stored securely
- Deployment requires approval
- Rollback logged in audit trail

### Field 10: Integration Points
- Config (Wk1)
- Model registry (Day 1)

### Field 11: Code Quality
- Type hints on ALL functions
- Docstrings required (Google style)
- PEP 8 compliant
- Max 40 lines per function

### Field 12: GitHub CI Requirements
- pytest pass
- flake8 pass
- black --check pass
- CI green

### Field 13: Pass Criteria
Builder 2 reports DONE when:
- All 5 files built and pushed
- Trainer uses Unsloth + Colab FREE
- Model deployment works
- Rollback works
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — Fine Tune + Validation + Monitoring
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `agent_lightning/training/fine_tune.py`
2. `agent_lightning/training/validate.py`
3. `agent_lightning/monitoring/__init__.py`
4. `agent_lightning/monitoring/drift_detector.py`
5. `agent_lightning/monitoring/accuracy_tracker.py`

### Field 2: What is each file?
1. `agent_lightning/training/fine_tune.py` — Fine-tuning pipeline
2. `agent_lightning/training/validate.py` — Model validation before deployment
3. `agent_lightning/monitoring/__init__.py` — Module init for monitoring
4. `agent_lightning/monitoring/drift_detector.py` — Detect model drift
5. `agent_lightning/monitoring/accuracy_tracker.py` — Track accuracy per category

### Field 3: Responsibilities

**agent_lightning/training/fine_tune.py:**
- `FineTuner` class with:
  - `async fine_tune(self, base_model: str, dataset: str) -> dict` — Run fine-tuning
  - `async get_hyperparameters(self) -> dict` — Get default hyperparameters
  - `async save_checkpoint(self, step: int) -> dict` — Save training checkpoint
  - **Test: Fine-tune runs on test dataset**

**agent_lightning/training/validate.py:**
- `ModelValidator` class with:
  - `async validate(self, model_path: str) -> dict` — Validate model accuracy
  - `async check_accuracy_threshold(self, accuracy: float) -> bool` — **CRITICAL: Check if accuracy >= 90%**
  - `async run_test_suite(self, model_path: str) -> dict` — Run test suite
  - **CRITICAL: BLOCKS deployment at <90% accuracy**
  - **CRITICAL: ALLOWS deployment at 91%+ accuracy**
  - Returns {accuracy, passed, category_scores}

**agent_lightning/monitoring/drift_detector.py:**
- `DriftDetector` class with:
  - `async detect_drift(self, model_version: str) -> dict` — Detect model drift
  - `async compare_distributions(self, baseline: dict, current: dict) -> dict` — Compare distributions
  - `async alert_on_drift(self, drift_score: float) -> dict` — Alert on significant drift
  - **Test: Drift detected after model change**

**agent_lightning/monitoring/accuracy_tracker.py:**
- `AccuracyTracker` class with:
  - `async track(self, model_version: str, metrics: dict) -> dict` — Track accuracy metrics
  - `async get_by_category(self, model_version: str) -> dict` — Get accuracy by category
  - `async get_trend(self, days: int = 30) -> list[dict]` — Get accuracy trend
  - **Test: Accuracy tracked per category**

### Field 4: Depends On
- `agent_lightning/training/trainer.py` (Day 2)
- `agent_lightning/training/unsloth_optimizer.py` (Day 2)
- `agent_lightning/deployment/model_registry.py` (Day 1)

### Field 5: Expected Output
- Fine-tuning pipeline works end-to-end
- Validation blocks deployment at <90% accuracy
- Validation allows deployment at 91%+ accuracy
- Drift detection works
- Accuracy tracked per category

### Field 6: Unit Test Files
- `tests/unit/test_agent_lightning_validation.py`
  - Test: Fine-tune runs on test dataset
  - **Test: BLOCKS deployment at 89% accuracy**
  - **Test: ALLOWS deployment at 91% accuracy**
  - Test: Drift detected after model change
  - Test: Accuracy tracked per category

### Field 7: BDD Scenario
- `docs/bdd_scenarios/agent_lightning_bdd.md` — Validation scenarios

### Field 8: Error Handling
- Fine-tune errors → log and retry
- Validation errors → block deployment
- Drift detection errors → alert and continue

### Field 9: Security Requirements
- Validation results logged
- Drift alerts to admins
- Accuracy data company-isolated

### Field 10: Integration Points
- Trainer (Day 2)
- Unsloth optimizer (Day 2)
- Model registry (Day 1)

### Field 11: Code Quality
- Type hints on ALL functions
- Docstrings required (Google style)
- PEP 8 compliant
- Max 40 lines per function

### Field 12: GitHub CI Requirements
- pytest pass
- flake8 pass
- black --check pass
- CI green

### Field 13: Pass Criteria
Builder 3 reports DONE when:
- All 5 files built and pushed
- **CRITICAL: Validation blocks at <90% accuracy**
- **CRITICAL: Validation allows at 91%+ accuracy**
- Drift detection works
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Background Workers
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `workers/__init__.py`
2. `workers/worker.py`
3. `workers/batch_approval.py`
4. `workers/training_job.py`
5. `workers/cleanup.py`
6. `backend/services/burst_mode.py`

### Field 2: What is each file?
1. `workers/__init__.py` — Module init for workers
2. `workers/worker.py` — Base ARQ worker class
3. `workers/batch_approval.py` — Batch approval processing worker
4. `workers/training_job.py` — Training job worker
5. `workers/cleanup.py` — Cleanup worker for GDPR compliance
6. `backend/services/burst_mode.py` — Burst mode service for traffic spikes

### Field 3: Responsibilities

**workers/worker.py:**
- `BaseWorker` class with:
  - `async start(self) -> None` — Start worker
  - `async register(self) -> dict` — Register with ARQ
  - `async process(self, job: dict) -> dict` — Process job
  - `async stop(self) -> None` — Stop worker gracefully
  - **Test: ARQ worker registers correctly**

**workers/batch_approval.py:**
- `BatchApprovalWorker` class with:
  - `async process_batch(self, approval_ids: list[str]) -> dict` — Process batch of approvals
  - `async get_pending_approvals(self) -> list[dict]` — Get pending approvals
  - `async notify_results(self, results: list[dict]) -> dict` — Notify approval results
  - **Test: Batch processes correctly**

**workers/training_job.py:**
- `TrainingJobWorker` class with:
  - `async run_training(self, job_config: dict) -> dict` — Run training job
  - `async monitor_progress(self, job_id: str) -> dict` — Monitor training progress
  - `async notify_completion(self, job_id: str, result: dict) -> dict` — Notify completion
  - **Test: Training job triggered**

**workers/cleanup.py:**
- `CleanupWorker` class with:
  - `async cleanup_expired_data(self) -> dict` — Cleanup expired data
  - `async anonymize_pii(self, company_id: str) -> dict` — **CRITICAL: Anonymize PII per GDPR**
  - `async archive_old_interactions(self, days: int = 90) -> dict` — Archive old data
  - **Test: Cleanup runs, PII anonymized**

**backend/services/burst_mode.py:**
- `BurstModeService` class with:
  - `async activate(self, company_id: str) -> dict` — **CRITICAL: Activate burst mode instantly**
  - `async deactivate(self, company_id: str) -> dict` — Deactivate burst mode
  - `async update_billing(self, company_id: str) -> dict` — **CRITICAL: Update billing**
  - `async check_auto_expire(self) -> dict` — **CRITICAL: Auto-expire after period**
  - **Test: Burst mode activates instantly, billing updated, auto-expires**

### Field 4: Depends On
- `shared/core_functions/config.py` (Wk1)
- `shared/utils/message_queue.py` (Wk2)
- `backend/services/escalation_service.py` (Wk12)
- `agent_lightning/training/fine_tune.py` (Day 3)
- `shared/compliance/gdpr_engine.py` (Wk7)
- `backend/services/billing_service.py` (Wk4)
- `security/feature_flags.py` (Wk1)

### Field 5: Expected Output
- All workers start and register with ARQ
- Batch approval processes correctly
- Training job runs
- Cleanup anonymizes PII
- Burst mode activates instantly, billing updated, auto-expires

### Field 6: Unit Test Files
- `tests/unit/test_workers.py`
  - Test: ARQ worker registers correctly
  - Test: Batch processes correctly
  - Test: Training job triggered
  - Test: Cleanup runs, PII anonymized
  - Test: Burst mode activates, billing updated, auto-expires

### Field 7: BDD Scenario
- `docs/bdd_scenarios/workers_bdd.md` — Worker scenarios

### Field 8: Error Handling
- Worker errors → log and retry
- Batch errors → continue with remaining items
- Training errors → notify and log
- Cleanup errors → alert and continue
- Burst mode errors → fallback to normal mode

### Field 9: Security Requirements
- Workers authenticated with ARQ
- Batch operations logged
- Training data isolated
- PII anonymization complete
- Burst mode requires auth

### Field 10: Integration Points
- ARQ message queue (Wk2)
- Escalation service (Wk12)
- Training pipeline (Day 3)
- GDPR engine (Wk7)
- Billing service (Wk4)

### Field 11: Code Quality
- Type hints on ALL functions
- Docstrings required (Google style)
- PEP 8 compliant
- Max 40 lines per function

### Field 12: GitHub CI Requirements
- pytest pass
- flake8 pass
- black --check pass
- CI green

### Field 13: Pass Criteria
Builder 4 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: All 8 workers register with ARQ**
- **CRITICAL: Burst mode activates instantly, billing updated**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — Remaining Workers + Quality Coach
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `workers/recall_handler.py`
2. `workers/proactive_outreach.py`
3. `workers/report_generator.py`
4. `workers/kb_indexer.py`
5. `backend/quality_coach/__init__.py`
6. `backend/quality_coach/analyzer.py`
7. `backend/quality_coach/reporter.py`
8. `backend/quality_coach/notifier.py`

### Field 2: What is each file?
1. `workers/recall_handler.py` — Recall handler worker for stopping actions
2. `workers/proactive_outreach.py` — Proactive outreach worker
3. `workers/report_generator.py` — Report generator worker
4. `workers/kb_indexer.py` — Knowledge base indexer worker
5. `backend/quality_coach/__init__.py` — Module init for quality coach
6. `backend/quality_coach/analyzer.py` — Quality analyzer for conversations
7. `backend/quality_coach/reporter.py` — Quality reporter for weekly reports
8. `backend/quality_coach/notifier.py` — Real-time quality alerts

### Field 3: Responsibilities

**workers/recall_handler.py:**
- `RecallHandlerWorker` class with:
  - `async recall_action(self, action_id: str) -> dict` — **CRITICAL: Stop non-money actions**
  - `async verify_recall(self, action_id: str) -> bool` — Verify recall success
  - `async log_recall(self, action_id: str, reason: str) -> dict` — Log recall
  - **Test: Recall stops non-money actions**
  - Cannot recall financial transactions

**workers/proactive_outreach.py:**
- `ProactiveOutreachWorker` class with:
  - `async send_outreach(self, customer_id: str, message: str) -> dict` — Send proactive message
  - `async schedule_followup(self, customer_id: str, delay_hours: int) -> dict` — Schedule follow-up
  - `async get_due_outreach(self) -> list[dict]` — Get due outreach
  - **Test: Outreach sent proactively**

**workers/report_generator.py:**
- `ReportGeneratorWorker` class with:
  - `async generate_report(self, company_id: str, report_type: str) -> dict` — Generate report
  - `async schedule_report(self, company_id: str, schedule: dict) -> dict` — Schedule report
  - `async deliver_report(self, report_id: str) -> dict` — Deliver report
  - **Test: Report generated**

**workers/kb_indexer.py:**
- `KBIndexerWorker` class with:
  - `async index_document(self, doc_id: str) -> dict` — Index document in KB
  - `async reindex_all(self, company_id: str) -> dict` — Reindex all documents
  - `async verify_index(self, doc_id: str) -> bool` — Verify document indexed
  - **Test: KB indexed correctly**

**backend/quality_coach/analyzer.py:**
- `QualityAnalyzer` class with:
  - `async analyze_conversation(self, interaction_id: str) -> dict` — Analyze conversation quality
  - `async score_accuracy(self, interaction: dict) -> float` — Score accuracy (0-100)
  - `async score_empathy(self, interaction: dict) -> float` — Score empathy (0-100)
  - `async score_efficiency(self, interaction: dict) -> float` — Score efficiency (0-100)
  - **CRITICAL: Test: Scores accuracy/empathy/efficiency**
  - Returns {accuracy_score, empathy_score, efficiency_score, overall_score, recommendations}

**backend/quality_coach/reporter.py:**
- `QualityReporter` class with:
  - `async generate_weekly_report(self, company_id: str) -> dict` — Generate weekly quality report
  - `async get_trends(self, company_id: str, days: int = 30) -> dict` — Get quality trends
  - `async compare_periods(self, company_id: str, period1: dict, period2: dict) -> dict` — Compare periods
  - **Test: Weekly report generated**

**backend/quality_coach/notifier.py:**
- `QualityNotifier` class with:
  - `async alert_low_quality(self, interaction_id: str, score: float) -> dict` — Alert on low quality
  - `async notify_manager(self, company_id: str, issue: dict) -> dict` — Notify manager
  - `async setup_alerts(self, company_id: str, thresholds: dict) -> dict` — Setup quality alerts
  - **Test: Real-time alert fires on low quality**

### Field 4: Depends On
- `shared/utils/cache.py` (Wk2)
- `backend/services/notification_service.py` (Wk4)
- `backend/services/analytics_service.py` (Wk4)
- `shared/knowledge_base/rag_pipeline.py` (Wk5)
- `shared/core_functions/config.py` (Wk1)

### Field 5: Expected Output
- Recall stops non-money actions
- Proactive outreach sent
- Reports generated
- KB indexed
- Quality Coach scores conversations
- Weekly reports generated
- Real-time alerts fire

### Field 6: Unit Test Files
- `tests/unit/test_workers_extra.py`
  - Test: Recall stops non-money actions
  - Test: Outreach sent proactively
  - Test: Report generated
  - Test: KB indexed correctly
- `tests/unit/test_quality_coach.py`
  - Test: Scores accuracy/empathy/efficiency
  - Test: Weekly report generated
  - Test: Real-time alert fires

### Field 7: BDD Scenario
- `docs/bdd_scenarios/quality_coach_bdd.md` — Quality Coach scenarios

### Field 8: Error Handling
- Recall errors → log and alert
- Outreach errors → retry with backoff
- Report errors → log and notify
- Indexing errors → retry
- Quality analysis errors → fallback to default scores

### Field 9: Security Requirements
- Recall requires admin auth
- Outreach respects opt-out
- Reports company-isolated
- Quality scores company-isolated

### Field 10: Integration Points
- Cache (Wk2)
- Notification service (Wk4)
- Analytics service (Wk4)
- RAG pipeline (Wk5)

### Field 11: Code Quality
- Type hints on ALL functions
- Docstrings required (Google style)
- PEP 8 compliant
- Max 40 lines per function

### Field 12: GitHub CI Requirements
- pytest pass
- flake8 pass
- black --check pass
- CI green

### Field 13: Pass Criteria
Builder 5 reports DONE when:
- All 8 files built and pushed
- **CRITICAL: All 8 workers registered with ARQ**
- Quality Coach scores conversations
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER → WEEK 13 INSTRUCTIONS (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Run AFTER all Builders 1-5 report DONE**

### Test Command
```bash
pytest tests/e2e/test_agent_lightning.py -v
pytest tests/integration/test_week13_workers.py -v
pytest tests/unit/test_agent_lightning_data.py -v
pytest tests/unit/test_agent_lightning_training.py -v
pytest tests/unit/test_agent_lightning_validation.py -v
pytest tests/unit/test_workers.py -v
pytest tests/unit/test_quality_coach.py -v
```

### Critical Tests to Verify
1. Dataset builder: exports correct JSONL format with 50+ mistakes
2. validate.py: BLOCKS deployment at <90% accuracy
3. validate.py: ALLOWS deployment at 91%+ accuracy
4. New model version registered in model_registry after deployment
5. All 8 workers start and register with ARQ without errors
6. Burst mode: activates instantly, billing updated, auto-expires
7. Quality Coach: scores accuracy/empathy/efficiency correctly

### Week 13 PASS Criteria
- Full Agent Lightning training cycle works end-to-end
- All background workers running
- Quality Coach scoring conversations
- All unit tests pass
- GitHub CI pipeline green

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Status | Files | Tests | Pushed |
|---------|-----|--------|-------|-------|--------|
| Builder 1 | Day 1 | ⏳ PENDING | Data Export + Model Registry (7 files) | - | NO |
| Builder 2 | Day 2 | ⏳ PENDING | Training Pipeline (5 files) | - | NO |
| Builder 3 | Day 3 | ⏳ PENDING | Fine Tune + Validation + Monitoring (5 files) | - | NO |
| Builder 4 | Day 4 | ⏳ PENDING | Background Workers (6 files) | - | NO |
| Builder 5 | Day 5 | ⏳ PENDING | Remaining Workers + Quality Coach (8 files) | - | NO |
| Tester | Day 6 | ⏳ WAITING ALL | Full validation | - | NO |

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS:**

1. All 5 days run in PARALLEL — no cross-day dependencies
2. Within-day dependencies OK — build files in order listed
3. No Docker — mock everything in tests
4. One push per file — only after tests pass
5. Type hints + docstrings required on all functions
6. **Agent Lightning uses Unsloth + Colab FREE tier**
7. **validate.py: BLOCKS deployment at <90% accuracy**
8. **validate.py: ALLOWS deployment at 91%+ accuracy**
9. **All 8 workers must register with ARQ**
10. **Burst mode: activates instantly, billing updated, auto-expires**

---

═══════════════════════════════════════════════════════════════════════════════
## WEEK 13 CRITICAL REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

| Feature | Requirement | Why |
|---------|-------------|-----|
| JSONL Dataset | 50+ entries | Training data quality |
| Accuracy Threshold | 90% minimum | Quality gate |
| Validation | Block at <90% | Prevent bad deployments |
| Validation | Allow at 91%+ | Enable good deployments |
| Workers | All 8 registered | Background processing |
| Burst Mode | Instant activation | Traffic spike handling |
| Burst Mode | Auto-expire | Cost control |
| Quality Coach | 3 scores (accuracy/empathy/efficiency) | Conversation quality |

---

═══════════════════════════════════════════════════════════════════════════════
## EXECUTION ORDER
═══════════════════════════════════════════════════════════════════════════════

```
Week 13 FULLY PARALLEL Execution:

Day 1-5: ALL BUILDERS RUN SIMULTANEOUSLY
├── Builder 1: Data Export + Model Registry (7 files)
├── Builder 2: Training Pipeline (5 files)
├── Builder 3: Fine Tune + Validation + Monitoring (5 files)
├── Builder 4: Background Workers (6 files)
└── Builder 5: Remaining Workers + Quality Coach (8 files)

Day 6: Tester → Full validation → Report PASS/FAIL
```

**ALL Builders can start NOW. No waiting required.**

---

═══════════════════════════════════════════════════════════════════════════════
## WEEK 12 COMPLETE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

**Week 12 — Backend Services**

**Total Files:** 41 files built
**Total Tests:** 215 tests passing

**Key Achievements:**
- Jarvis Commands: pause_refunds in 500ms
- Industry Configs: Ecommerce, SaaS, Healthcare (BAA), Logistics
- Approval Service: Paddle called exactly once after approval
- Escalation Ladder: 4-phase at 24h/48h/72h/96h
- Voice Handler: Answer < 6 seconds
- NLP Provisioner: Natural language commands
- GDPR Compliance: PII anonymized, row preserved
- Agent Lightning: Training cycle tests
- CI GREEN
