# Graph Report - .  (2026-05-30)

## Corpus Check
- Large corpus: 954 files · ~1,187,488 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 18780 nodes · 43403 edges · 1033 communities detected
- Extraction: 57% EXTRACTED · 43% INFERRED · 0% AMBIGUOUS · INFERRED: 18469 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 18469 · rationale_for: 7387 · contains: 6838 · calls: 5558 · method: 3288 · inherits: 1438 · imports_from: 265 · re_exports: 97 · imports: 63


## Input Scope
- Requested: auto
- Resolved: committed (source: default-auto)
- Included files: 954 · Candidates: 960
- Excluded: 0 untracked · 0 ignored · 4 sensitive · 0 missing committed
- Recommendation: Use --scope all or graphify.yaml inputs.corpus for a knowledge-base folder.

## Graph Freshness
- Built from Git commit: `dc2cecc`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `User` - 1326 edges
2. `TechniqueID` - 643 edges
3. `Company` - 427 edges
4. `SmartRouter` - 404 edges
5. `ClassificationEngine` - 329 edges
6. `TechniqueTier` - 282 edges
7. `QuerySignals` - 257 edges
8. `TechniqueRouter` - 216 edges
9. `AtomicStepType` - 194 edges
10. `NotificationService` - 177 edges

## Surprising Connections (you probably didn't know these)
- `SG-21/SG-22: AI Agent Assignment API Router (BC-014)  Endpoints for managing AI` --uses--> `User`  [INFERRED]
  backend/app/api/ai_agent.py → database/models/core.py
- `Serialize an AIAgentAssignment ORM object to response dict.      NOTE: Company s` --uses--> `User`  [INFERRED]
  backend/app/api/ai_agent.py → database/models/core.py
- `List all agent assignments.      Optionally filter by status (active, inactive,` --uses--> `User`  [INFERRED]
  backend/app/api/ai_agent.py → database/models/core.py
- `SG-21: Task decomposition summary.      Returns total agents, features mapped, t` --uses--> `User`  [INFERRED]
  backend/app/api/ai_agent.py → database/models/core.py
- `Find which agent owns a specific feature.      Returns the agent that owns the f` --uses--> `User`  [INFERRED]
  backend/app/api/ai_agent.py → database/models/core.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (416): BaseModel, AdminClientResponse, AdminClientUpdate, AdminHealthResponse, APIProviderCreate, APIProviderListResponse, APIProviderResponse, APIProviderUpdate (+408 more)

### Community 1 - "Community 1"
Cohesion: 0.01
Nodes (309): AssignmentMethod, PARWA variant tiers controlling assignment complexity., How a ticket was assigned., VariantType, AlertLevel, MetricPoint, SG-19: Real-Time AI Performance Monitoring Service.  Centralised monitoring dash, Single data point with timestamp and labels. (+301 more)

### Community 2 - "Community 2"
Cohesion: 0.02
Nodes (237): batch_extract_signals(), BatchSignalRequest, CLARAEvaluateRequest, evaluate_clara(), extract_signals(), _get_clara(), _get_extractor(), Signal Extraction API Endpoints (SG-13 / F-150)  REST endpoints for signal extra (+229 more)

### Community 3 - "Community 3"
Cohesion: 0.01
Nodes (272): classify_text(), ClassifyRequest, _get_engine(), Classification API Endpoint  POST endpoint to classify ticket text using Classif, Return a safe default classification result (BC-008)., Request body for text classification.      C-12 FIX: company_id is NO LONGER acc, Lazy-load ClassificationEngine (BC-008: never crash)., Classify ticket text into primary + secondary intents.      Uses ClassificationE (+264 more)

### Community 4 - "Community 4"
Cohesion: 0.01
Nodes (196): ABC, _build_response(), ErrorResponse, get_config_store(), get_technique_config(), list_technique_configs(), Per-Tenant Technique Configuration Admin API (SG-17)  Provides REST endpoints fo, Get configuration for a specific technique.          Default: all techniques ena (+188 more)

### Community 5 - "Community 5"
Cohesion: 0.02
Nodes (155): add_affected_customers(), AddAffectedCustomersRequest, analyze_ticket_for_spam(), create_incident(), escalate_ticket(), EscalateRequest, freeze_ticket(), FreezeRequest (+147 more)

### Community 6 - "Community 6"
Cohesion: 0.02
Nodes (133): BaseReactTool, ActionSchema, BaseReactTool, _do_execute(), get_schema(), PARWA ReAct Tool Base Classes  (F-157)  Provides the base framework for ReAct (R, Base class for all ReAct tool adapters.      GAP-004: All execute() calls use as, Execute a tool action with timeout and concurrency limits.          GAP-004: Wra (+125 more)

### Community 7 - "Community 7"
Cohesion: 0.02
Nodes (200): External API Clients  This package contains clients for external services: - pad, PaddleClient, PaddleError, Base exception for Paddle API errors., Verify Paddle webhook signature using HMAC-SHA256.          Paddle Billing API u, Paddle API Client for subscription and billing management.      Usage:         c, Parse and validate a webhook payload.          Args:             payload: Raw re, PARWA subscription variant types.      Values are the canonical (new) lowercase (+192 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (194): ClassificationEngine, KeywordClassifier, Enhanced keyword-based multi-label intent classifier., AI-Powered Multi-Label Intent Classifier (F-062).      Uses Smart Router for AI, ConfidenceScoringEngine, F-059: Confidence Scoring Engine.      Evaluates AI responses across 7 weighted, Initialize the scoring engine with an empty tenant config cache., Get the default signal weights for a variant type.          Args:             va (+186 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (105): AIPipeline, PipelineContext, PipelineResult, process_ai_message(), PARWA AI Processing Pipeline (P2 — End-to-End Intelligence)  Chains all Week 8-1, Retrieve relevant knowledge base chunks and rerank., Generate AI response using selected model and technique., Run 5-stage CLARA quality check on the response.          D5-4 FIX: Pass sentime (+97 more)

### Community 10 - "Community 10"
Cohesion: 0.02
Nodes (126): bulk_assign(), bulk_close(), bulk_priority(), bulk_status_change(), bulk_tags(), execute_bulk_action(), get_bulk_action(), list_bulk_actions() (+118 more)

### Community 11 - "Community 11"
Cohesion: 0.02
Nodes (146): api_key_create(), api_key_list(), api_key_revoke(), api_key_rotate(), Revoke an API key immediately., Convert DB record to APIKeyResponse., List all API keys for the tenant.      G02: require_scope("read") wired — enforc, Create a new API key. (+138 more)

### Community 12 - "Community 12"
Cohesion: 0.02
Nodes (123): Base, APIProvider, ConfidenceScore, GSDSession, GuardrailBlock, GuardrailRule, ModelUsageLog, PromptTemplate (+115 more)

### Community 13 - "Community 13"
Cohesion: 0.03
Nodes (91): _detect_provider(), LLMGateway, LLMResponse, Unified LLM Gateway for AI Techniques (Day 3 - AI Core Security)  Provides a sin, Initialize the LLM gateway.          Args:             provider: Which LLM provi, Ensure the LLM client is initialized. Returns True on success., Initialize LiteLLM client., Initialize z-ai gateway HTTP client. (+83 more)

### Community 14 - "Community 14"
Cohesion: 0.05
Nodes (110): add_tags(), assign_ticket(), bulk_assign(), bulk_status_update(), create_ticket(), delete_ticket(), detect_category(), detect_priority() (+102 more)

### Community 15 - "Community 15"
Cohesion: 0.03
Nodes (89): CompanySetting, EmergencyState, build_cc_system_prompt(), _build_cc_welcome(), _call_ai_provider_fallback(), get_cc_context(), get_cc_history(), get_cc_session() (+81 more)

### Community 16 - "Community 16"
Cohesion: 0.03
Nodes (85): _build_checkpoint_index_key(), _build_checkpoint_key(), _build_lock_key(), _build_state_key(), CheckpointMeta, get_state_serializer(), _json_default(), _new_uuid() (+77 more)

### Community 17 - "Community 17"
Cohesion: 0.07
Nodes (77): BaseTechniqueNode, ChainOfThoughtNode, Chain of Thought — Tier 2 Conditional.      Extends BaseTechniqueNode for integr, _calculate_budget(), CRPConfig, CRPProcessor, CRPResult, estimate_tokens() (+69 more)

### Community 18 - "Community 18"
Cohesion: 0.11
Nodes (110): approve_langgraph_action(), compress_context(), configure_capacity(), execute_workflow(), force_state_transition(), get_capacity_status(), get_context_health(), get_gsd_analytics() (+102 more)

### Community 19 - "Community 19"
Cohesion: 0.05
Nodes (72): Schema for updating a response template., TemplateUpdateSchema, AIAssignmentEngine, Input for AI ticket assignment.      Carries all signals needed for multi-factor, AI-powered ticket assignment with multi-factor scoring.      Orchestrates score-, TicketAssignmentRequest, _build_ai_assign_request(), _circuit_redis_key() (+64 more)

### Community 20 - "Community 20"
Cohesion: 0.17
Nodes (92): cancel_subscription(), CancelResponse, ClientRefundListResponse, ClientRefundProcessRequest, ClientRefundResponse, ClientRefundStatsResponse, CompanyBillingStatusResponse, create_client_refund() (+84 more)

### Community 21 - "Community 21"
Cohesion: 0.03
Nodes (66): close_paddle_client(), get_paddle_client(), PaddleAuthError, PaddleNotFoundError, PaddleRateLimitError, PaddleValidationError, Paddle API Client (BC-002, BG-05)  Implements the official Paddle API for: - Sub, Get or create HTTP client. (+58 more)

### Community 22 - "Community 22"
Cohesion: 0.07
Nodes (104): batch_check_entitlements(), batch_update_capabilities(), BatchCapabilityUpdateItem, BatchCapabilityUpdateRequest, BatchEntitlementCheckRequest, check_entitlement(), create_instance(), create_instance_override() (+96 more)

### Community 23 - "Community 23"
Cohesion: 0.03
Nodes (71): CapacityAlert, CapacityMonitor, QueueItem, Capacity Monitor (F-069) — Workflow execution capacity tracking.  Tracks concurr, Get max concurrent for company+variant.          Uses company-specific override, Set custom capacity limits for a company+variant.          Args:             com, Acquire an execution slot.          If capacity is available, grants a slot imme, Release an execution slot.          After releasing, processes the queue if item (+63 more)

### Community 24 - "Community 24"
Cohesion: 0.04
Nodes (97): Industry, Supported industries for the Variant Engine.      Inherits from str + Enum so it, Variant Service: Config resolution for the Variant Engine.  Given a variant_tier, Serialize to a plain dict for logging/debugging., Single source of truth for variant×industry configuration.      Usage:         s, Initialize the variant service., Resolve full config for a variant_tier + industry combination.          Priority, Resolve config by looking up instance details from DB.          1. Look up insta (+89 more)

### Community 25 - "Community 25"
Cohesion: 0.04
Nodes (66): _compute_query_hash(), ExtractedSignals, Signal Extraction Layer (SG-13)  Extracts 10 real-time signals from each ticket, Output of signal extraction — 10 signals., Serialize to dictionary., Extract all 10 signals from a query.          GAP-007 FIX: Cache key format is, Classify intent from query using keyword matching., Calculate sentiment score using lexicon-based approach.          Returns 0.0 (ve (+58 more)

### Community 26 - "Community 26"
Cohesion: 0.03
Nodes (68): _AgentProfile, AgentScore, AgentWorkload, AssignmentEvent, _build_agent_profiles(), _build_reason(), _channel_bonus(), _compute_confidence() (+60 more)

### Community 27 - "Community 27"
Cohesion: 0.06
Nodes (80): ai_assign_ticket(), AIAssignmentRequestSchema, BatchGenerationItemSchema, BatchGenerationRequestSchema, BrandVoiceCheckProhibitedSchema, BrandVoiceConfigSchema, BrandVoiceValidateSchema, BudgetInitSchema (+72 more)

### Community 28 - "Community 28"
Cohesion: 0.06
Nodes (96): check_email(), _clear_token_cookies(), forgot_password(), get_me(), google_login(), login(), logout(), phone_send_otp() (+88 more)

### Community 29 - "Community 29"
Cohesion: 0.03
Nodes (60): EscalationCooldownError, get_gsd_engine(), get_next_gsd_state(), GSDConfig, GSDEngine, GSDEngineError, InvalidTransitionError, Generate a summary of the current conversation state.          Provides a compre (+52 more)

### Community 30 - "Community 30"
Cohesion: 0.05
Nodes (66): Notification, NotificationLog, NotificationPreference, NotificationPreferenceAudit, Notification Preference Service - User preferences (MF05)  Handles: - Per-user n, Set digest mode settings.                  Args:             user_id: User ID, Audit trail for notification preference changes (S-14)., Check if a user should be notified for an event.                  Args: (+58 more)

### Community 31 - "Community 31"
Cohesion: 0.04
Nodes (64): create_voice_config(), delete_voice_config(), end_voice_call(), _error_response(), get_call_history(), _get_db(), get_voice_call(), get_voice_config() (+56 more)

### Community 32 - "Community 32"
Cohesion: 0.15
Nodes (85): create_digest(), create_template(), delete_template(), DigestSettingsRequest, disable_all_notifications(), enable_all_notifications(), get_preferences(), get_template() (+77 more)

### Community 33 - "Community 33"
Cohesion: 0.04
Nodes (90): acknowledge_alert(), _check_activity_store_critical(), _check_agent_pool(), _check_compound_spike_quality(), _check_drift(), _check_error_rate(), _check_plan_usage(), _check_quality() (+82 more)

### Community 34 - "Community 34"
Cohesion: 0.04
Nodes (63): RAG Retrieval Module (F-064) — Knowledge Base Search (Part 1)  Handles knowledge, Result of a RAG retrieval operation., Knowledge base RAG retrieval engine.      Supports three variant tiers with incr, Retrieve relevant chunks from the knowledge base.          Args:             que, Generate query embedding using EmbeddingService.          Falls back to the stor, Fallback keyword-based search when vector search fails.          BC-008: Gracefu, Expand query with synonyms for better recall.          Returns original query +, Rerank chunks based on query-chunk similarity.          Uses a simple BM25-inspi (+55 more)

### Community 35 - "Community 35"
Cohesion: 0.04
Nodes (63): create_policy(), delete_policy(), get_policy(), get_sla_stats(), get_ticket_sla(), list_approaching_tickets(), list_breached_tickets(), list_policies() (+55 more)

### Community 36 - "Community 36"
Cohesion: 0.06
Nodes (85): PaddleEventType, All Paddle webhook event types., _extract_adjustment_data(), _extract_credit_data(), _extract_customer_data(), _extract_discount_data(), _extract_price_data(), _extract_report_data() (+77 more)

### Community 37 - "Community 37"
Cohesion: 0.06
Nodes (49): CompressionConfig, CompressionInput, ContextCompressor, Configuration for the ContextCompressor., F-086: Context Compression Engine.      Compresses RAG context and conversation, Return cumulative compression statistics., Return the current compressor configuration., Reset all internal state. For testing. (+41 more)

### Community 38 - "Community 38"
Cohesion: 0.04
Nodes (51): CollisionEvent, ContinuityConfig, get_session_continuity_manager(), HandoffRecord, _parse_utc(), Record of a session handoff between agents., Per-company session continuity configuration., Session Continuity & Multi-Agent Collision Detection (SG-10).      Ensures only (+43 more)

### Community 39 - "Community 39"
Cohesion: 0.04
Nodes (80): _get_service(), jarvis_analyze_spam(), jarvis_assign_ticket(), jarvis_auto_assign_ticket(), jarvis_auto_tag_ticket(), jarvis_check_rate_limit(), jarvis_check_ticket_lifecycle(), jarvis_check_usage_limit() (+72 more)

### Community 40 - "Community 40"
Cohesion: 0.05
Nodes (54): check_audit_immutability(), create_erasure_request(), create_retention_policy(), enforce_retention(), execute_erasure_request(), export_customer_data(), _get_company_id(), get_erasure_request() (+46 more)

### Community 41 - "Community 41"
Cohesion: 0.03
Nodes (71): _build_messages(), build_onboarding_system_prompt(), call_llm_with_functions(), _call_openai_with_functions(), _call_zai_with_functions(), _detect_concern(), detect_onboarding_stage(), _detect_topic() (+63 more)

### Community 42 - "Community 42"
Cohesion: 0.04
Nodes (48): CrossVariantInteractionError, Raised when a cross-variant interaction operation cannot proceed.      Inherits, CrossVariantRoutingError, Raised when cross-variant routing cannot proceed.      Inherits from ParwaBaseEr, ParwaBaseError, AuditExportResult, AuditIntegrityReport, AuditLogConfig (+40 more)

### Community 43 - "Community 43"
Cohesion: 0.10
Nodes (57): AgentMetricsResponse, CategoryDistributionResponse, DateRangeParams, get_agent_metrics(), get_analytics_dashboard(), get_category_distribution(), get_company_id_from_user(), get_sla_metrics() (+49 more)

### Community 44 - "Community 44"
Cohesion: 0.07
Nodes (43): CustomerEmailStatus, EmailBounce, EmailDeliverabilityAlert, Email Bounce & Complaint Models — Week 13 Day 3 (F-124)  Tables: - email_bounces, Per-email delivery status tracking.      Aggregates bounce/complaint counts for, Deliverability alert for tenant notification.      Created when bounce rates spi, Individual bounce/complaint event record.      One row per bounce or complaint e, EmailDeliveryEvent (+35 more)

### Community 45 - "Community 45"
Cohesion: 0.06
Nodes (50): check_merge_eligibility(), get_merge_details(), get_merge_history(), merge_tickets(), PARWA Ticket Merge API - F-051 Merge/Unmerge Endpoints (Day 29)  Implements F-05, Unmerge previously merged tickets.          PS26: Unmerge preserves message hist, Get all merge operations involving a ticket.          Returns both merges where, Check if a set of tickets can be merged.          Returns list of any issues tha (+42 more)

### Community 46 - "Community 46"
Cohesion: 0.07
Nodes (51): PaddleReconciliationReport, PaddleWebhookEvent, Paddle webhook event tracking with idempotency.      Tracks every Paddle webhook, Paddle reconciliation report audit trail.      Stores periodic and on-demand rec, PaddleReconciliationService, Paddle Webhook Reconciliation Service (Phase 6: Production Hardening)  Ensures:, Get latest reconciliation report for a company.          Args:             compa, Initialize the reconciliation service.          Args:             db_session: SQ (+43 more)

### Community 47 - "Community 47"
Cohesion: 0.04
Nodes (47): _close_session(), _cosine_similarity(), _create_pg_vector_store(), delete_document(), _embedding_to_pgvector_str(), get_vector_store(), health_check(), _matches_filters() (+39 more)

### Community 48 - "Community 48"
Cohesion: 0.06
Nodes (44): api_delete_document(), api_get_document(), api_kb_stats(), api_list_documents(), api_reindex_document(), api_retry_all_failed(), api_retry_document(), api_upload_document() (+36 more)

### Community 49 - "Community 49"
Cohesion: 0.05
Nodes (40): ChannelDispatcher, Channel Dispatcher — Week 13 Day 2 (F-120)  Routes AI-generated responses to the, Dispatch AI response via email channel., Dispatch AI response via chat channel (Socket.io).          Creates a TicketMess, Dispatch AI response via SMS channel (Week 13 Day 5 stub).          Day 5 will i, Store AI response internally without external channel dispatch.          Used fo, Dispatches AI responses to the correct communication channel.      This is the c, Dispatch an AI response to the ticket's channel.          Args:             comp (+32 more)

### Community 50 - "Community 50"
Cohesion: 0.05
Nodes (65): acknowledge_alert(), add_custom_quick_command(), _ai_message_to_response(), _alert_to_response(), awareness_tick(), _coerce_int(), create_cc_session(), dismiss_alert() (+57 more)

### Community 51 - "Community 51"
Cohesion: 0.09
Nodes (62): CategoryProvidersResponse, connect_provider(), ConnectProviderRequest, ConnectProviderResponse, _decrypt_credentials(), detect_api_key(), DetectKeyRequest, DetectKeyResponse (+54 more)

### Community 52 - "Community 52"
Cohesion: 0.05
Nodes (43): api_create_integration(), api_delete_integration(), api_list_integrations(), api_test_integration(), CreateIntegrationRequest, IntegrationResponse, list_available_integrations(), MessageResponse (+35 more)

### Community 53 - "Community 53"
Cohesion: 0.05
Nodes (42): ABTestConfig, extract_variables(), _now_iso(), PromptTemplate, PromptTemplateService, Create a new custom template for a company.          Args:             company_i, Result of rendering a template with variable substitution., Update an existing template.          If *content* changes, the version is auto- (+34 more)

### Community 54 - "Community 54"
Cohesion: 0.06
Nodes (44): check_variant_retry(), escalate_to_human(), format_message(), get_channel_config(), list_channels(), process_variant_retry(), PARWA Channels API - Channel Configuration Endpoints (Day 30)  Implements F-052:, Test connectivity for a channel configuration. (+36 more)

### Community 55 - "Community 55"
Cohesion: 0.08
Nodes (47): ClassificationResult, ClassificationStatsResponse, classify_text(), classify_ticket(), correct_classification(), CorrectionListResponse, CorrectionRequest, CorrectionResponse (+39 more)

### Community 56 - "Community 56"
Cohesion: 0.05
Nodes (43): _detect_mime_type(), FileMetadata, get_storage_backend(), LocalStorageBackend, PARWA File Storage Core Module  Provides abstract storage backend interface and, Abstract base class for file storage backends.      All operations are scoped by, Factory function to get the configured storage backend.      Reads STORAGE_BACKE, Reset the singleton storage backend instance.      Useful for testing — allows s (+35 more)

### Community 57 - "Community 57"
Cohesion: 0.05
Nodes (39): _get_db(), get_email_thread(), get_inbound_email(), list_email_threads(), list_inbound_emails(), Email Channel API Endpoints (F-121)  Provides admin visibility into inbound emai, List email threads for the tenant.      Returns paginated list of email threads, Get a single email thread by ID.      Returns the email thread record including (+31 more)

### Community 58 - "Community 58"
Cohesion: 0.06
Nodes (56): _apply_crp_compression(), auto_action_node(), billing_resolver_node(), _check_emergency_keywords(), clara_quality_gate_node(), classify_node(), complaint_handler_node(), confidence_assess_node() (+48 more)

### Community 59 - "Community 59"
Cohesion: 0.05
Nodes (30): CircuitBreaker, DegradedResponseDetector, FailoverChainExecutor, FailoverEvent, Model Failover System (F-055): Automatic Provider Fallback Chain.  Detects rate, Build a graceful error response when ALL providers fail.          BC-008: Never, Analyzes LLM responses to detect degraded or broken output.      Checks for:, Check if a response is degraded.          Returns:             (is_degraded, rea (+22 more)

### Community 60 - "Community 60"
Cohesion: 0.06
Nodes (42): Config, create_custom_field(), CustomFieldCreate, CustomFieldDeleteResponse, CustomFieldListResponse, CustomFieldResponse, CustomFieldUpdate, delete_custom_field() (+34 more)

### Community 61 - "Community 61"
Cohesion: 0.07
Nodes (22): _create_redis_client(), _get_redis_url(), RedisHealthTracker — Redis-backed provider health tracking for Smart Router.  St, Redis-backed health tracker for provider+model combinations.      All state is s, Initialise the tracker, attempting a Redis connection., Build the in-memory dict key (matches smart_router convention)., Reset daily counters at midnight UTC (BC-012)., Return (daily_limit, minute_limit) from MODEL_REGISTRY.          Falls back to d (+14 more)

### Community 62 - "Community 62"
Cohesion: 0.08
Nodes (36): AITokenBudget, Per-tenant, per-variant-instance, per-period token     spending limits. Hard-sto, AlertLevel, BudgetCheckResult, BudgetPeriodType, BudgetStatus, _calc_usage_pct(), AI Engine Cost Overrun Protection (SG-35).  Track per-tenant daily/monthly token (+28 more)

### Community 63 - "Community 63"
Cohesion: 0.05
Nodes (37): _clean_tag(), _extract_variables(), from_dict(), _generate_id(), _now(), Response Template Storage Service (F-155)  CRUD operations for response template, Find the best matching template for a given context.          Scoring criteria:, Extract and describe all variables from a template.          For each ``{{variab (+29 more)

### Community 64 - "Community 64"
Cohesion: 0.06
Nodes (33): CapacitySnapshot, ChannelMapping, CrossVariantRouter, EscalationPath, QueuedTicket, Mapping from a channel to its default variant and priority., Validate a routing decision.          Returns ``{             "valid": bool,, Record of a single escalation step between variants. (+25 more)

### Community 65 - "Community 65"
Cohesion: 0.05
Nodes (43): _build_config(), ConfidenceGateGuard, ContentSafetyGuard, GuardrailConfig, GuardrailResult, GuardrailsReport, HallucinationCheckGuard, LengthControlGuard (+35 more)

### Community 66 - "Community 66"
Cohesion: 0.06
Nodes (30): BrevoEmailConnector, get_production_connector(), IntegrationResult, PaddleBillingConnector, ProductionConnector, PARWA Production Integration Connector =======================================, Handle proactive abandoned cart recovery (v6.0 feature).          Per docs: Jarv, Get or create the ProductionConnector singleton. (+22 more)

### Community 67 - "Community 67"
Cohesion: 0.06
Nodes (50): WebhookEvent Model (BC-003, BC-001)  Stores incoming webhook events for idempote, WebhookEvent, _dispatch_celery_task(), get_webhook_event(), mark_webhook_processed(), process_webhook(), Webhook Service (BC-003, BC-001)  Generic webhook processor with idempotency gua, Process an incoming webhook event.      Idempotency: If (provider, event_id) alr (+42 more)

### Community 68 - "Community 68"
Cohesion: 0.05
Nodes (34): _conv_key(), ConversationContext, ConversationSummarizationService, ConversationSummary, _estimate_tokens(), Return summarization statistics for a company., Clear all internal state. Intended for use in tests., Produced summary for a conversation. (+26 more)

### Community 69 - "Community 69"
Cohesion: 0.05
Nodes (51): call_summary(), create_payment(), create_session(), create_ticket(), demo_pack_status(), execute_handoff(), get_history(), get_session() (+43 more)

### Community 70 - "Community 70"
Cohesion: 0.05
Nodes (36): add_document(), delete_document(), get_document(), get_reindex_status(), rag_health_check(), rag_search(), PARWA RAG API Router (Week 9 Day 7)  REST endpoints for RAG retrieval and knowle, Add a document with chunks to the knowledge base.      Body:       - document_id (+28 more)

### Community 71 - "Community 71"
Cohesion: 0.09
Nodes (51): AIAgentAssignment, Tracks which build agent owns which features.     Per-company agent assignments, create_agent(), delete_agent(), find_unassigned_features(), get_agent(), get_agent_by_id(), get_agent_feature_coverage() (+43 more)

### Community 72 - "Community 72"
Cohesion: 0.07
Nodes (33): EmailServer, PARWA MCP — Email Server  Provides email send/receive/query tools for customer c, Handle email_send tool invocation., Handle email_get_history tool invocation., MCP sub-server for email communication., Register email tools., Return the email REST router., FAQServer (+25 more)

### Community 73 - "Community 73"
Cohesion: 0.06
Nodes (37): Config, create_note(), delete_note(), get_note(), list_notes(), NoteCreate, NoteListResponse, NoteResponse (+29 more)

### Community 74 - "Community 74"
Cohesion: 0.05
Nodes (34): BlockedResponse, BlockedResponseManager, _compute_auto_reject_at(), _determine_priority(), _now_utc(), _parse_iso(), Find and auto-reject expired items in the review queue.          Any item whose, Delete old, fully-processed records from the queue.          Removes items that (+26 more)

### Community 75 - "Community 75"
Cohesion: 0.04
Nodes (49): ConnectionInfo, ConversationStage, DemoCallState, DetectionResult, EntrySource, HandoffState, IntegrationActions, IntegrationMetadata (+41 more)

### Community 76 - "Community 76"
Cohesion: 0.04
Nodes (34): get_high_pipeline_steps(), get_mini_pipeline_steps(), get_pro_pipeline_steps(), Code-Orchestrated Router: Python conditional edges for LangGraph.  This is the r, Decide what comes after emergency check.      If emergency detected → skip pipel, Decide what comes after classify.      THE KEY ROUTING DECISION in the Variant E, Decide what comes after extract signals.      Always goes to technique select. S, Decide what comes after technique select.      Pro:  technique_select → generate (+26 more)

### Community 77 - "Community 77"
Cohesion: 0.06
Nodes (29): _format_path_response(), Serialize node to dictionary., Immutable configuration for Tree of Thoughts processing (BC-001).      Attribute, Output of the full Tree of Thoughts pipeline.      Attributes:         domain: C, Serialize result to dictionary for recording in state., Deterministic Tree of Thoughts processor (F-145).      Uses heuristic scoring an, Generate a unique node ID., Classify the query into a ProblemDomain.          Scans the query against compil (+21 more)

### Community 78 - "Community 78"
Cohesion: 0.06
Nodes (33): Config, create_trigger(), delete_trigger(), get_trigger(), get_trigger_executions(), list_triggers(), PARWA Trigger API - Automated Trigger Endpoints (Day 33: MF08)  Endpoints for ma, List triggers with filters. (+25 more)

### Community 79 - "Community 79"
Cohesion: 0.07
Nodes (47): build_awareness_summary(), collect_onboarding_awareness(), _deep_merge(), _default_channel_awareness(), _default_entry_context(), _default_funnel_progress(), _default_sales_state(), _default_variant_awareness() (+39 more)

### Community 80 - "Community 80"
Cohesion: 0.06
Nodes (48): _complete_latest_ticket(), create_action_ticket(), create_payment_session(), _create_ticket(), execute_handoff(), get_call_summary(), _get_default_capacity(), get_handoff_status() (+40 more)

### Community 81 - "Community 81"
Cohesion: 0.08
Nodes (45): assign_session(), AssignSessionRequest, close_session(), create_canned_response(), create_chat_session(), CreateCannedResponseRequest, CreateChatSessionRequest, CSATRatingRequest (+37 more)

### Community 82 - "Community 82"
Cohesion: 0.05
Nodes (34): FormErrors, LoginForm(), LoginFormProps, FormErrors, INDUSTRIES, SignupForm(), SignupFormData, SignupFormProps (+26 more)

### Community 83 - "Community 83"
Cohesion: 0.06
Nodes (39): _do_send_email(), _get_brevo_client(), get_circuit_breaker(), _is_circuit_open(), PARWA Email Service (BC-006, C4)  Brevo email client for sending transactional e, Reset circuit breaker on success for a specific tenant., Record failure and possibly open circuit for a specific tenant., Reset circuit breaker state (for testing).          Args:             company_id (+31 more)

### Community 84 - "Community 84"
Cohesion: 0.07
Nodes (35): AttachmentSchema, Config, create_message(), delete_message(), get_message(), list_attachments(), list_messages(), MessageCreate (+27 more)

### Community 85 - "Community 85"
Cohesion: 0.08
Nodes (33): get_loophole_engine(), LoopholeDetectionEngine, LoopholeMatch, LoopholeReport, _max_risk(), PARWA Loophole Detection Engine  Scans AI responses for 25 loophole categories u, Rule-based loophole detection engine for AI customer care responses.      Scans, Initialize the detection engine.          Compiles regex patterns from the Looph (+25 more)

### Community 86 - "Community 86"
Cohesion: 0.07
Nodes (45): _apply_crp_compression(), auto_action_node(), billing_resolver_node(), _check_emergency_keywords(), clara_quality_gate_node(), classify_node(), complaint_handler_node(), confidence_assess_node() (+37 more)

### Community 87 - "Community 87"
Cohesion: 0.05
Nodes (29): ConfidenceConfig, ConfidenceResult, _jaccard_similarity(), Evaluate PII safety in the response.          Scans the response for PII pattern, Evaluate hallucination risk — inverse of hallucination detection.          Check, Evaluate whether response sentiment matches expected tone.          Performs sim, Evaluate response length efficiency relative to query complexity.          Measu, Evaluate provider/model confidence based on tier and health.          Uses the m (+21 more)

### Community 88 - "Community 88"
Cohesion: 0.06
Nodes (43): buildRAGMetadata(), checkEscalation(), checkGuardrails(), CLARAResult, ClassificationResult, classifyMessage(), COMPLEXITY_INDICATORS, ConfidenceResult (+35 more)

### Community 89 - "Community 89"
Cohesion: 0.07
Nodes (25): HallucinationDetector, HallucinationMatch, HallucinationReport, _is_leap_year(), SG-27: Hallucination Detection Patterns (BC-007, BC-012)  12 hallucination detec, P09: Detect circular reasoning in the response.          Looks for phrases that, Helper: detect repeated phrases (fallback for P09)., P10: Detect source citations that can't be verified.          Flags 'according t (+17 more)

### Community 90 - "Community 90"
Cohesion: 0.05
Nodes (34): AIConfigRequest, AIConfigResponse, IntegrationStepRequest, KnowledgeBaseStepRequest, LegalConsentRequest, LegalConsentResponse, MessageResponse, OnboardingStateResponse (+26 more)

### Community 91 - "Community 91"
Cohesion: 0.07
Nodes (31): AlertCard(), AlertCardProps, CCChatInput(), CCChatInputProps, CCChatMessage(), CCChatMessageProps, formatTimestamp(), renderContent() (+23 more)

### Community 92 - "Community 92"
Cohesion: 0.04
Nodes (44): AlertActionRequest, AlertCategory, AlertListResponse, AlertSeverity, AlertStatus, AwarenessDelta, AwarenessSnapshot, AwarenessState (+36 more)

### Community 93 - "Community 93"
Cohesion: 0.10
Nodes (41): EventCategory, EventType, Represents a registered event type with schema and metadata., Category of a PARWA real-time event., Schema for ticket-scoped events., TicketEventPayload, emit_incident_created(), emit_incident_resolved() (+33 more)

### Community 94 - "Community 94"
Cohesion: 0.08
Nodes (13): CompetitorEntry, EdgeCaseEntry, FAQEntry, IndustryGroup, INTENT_PATTERNS, IntentResult, JarvisAIEngine, KnowledgeBase (+5 more)

### Community 95 - "Community 95"
Cohesion: 0.08
Nodes (30): ActivitySummary, get_activity_summary(), get_assignment_history(), get_sla_events(), get_status_history(), get_timeline(), PARWA Ticket Timeline API - Activity Timeline Endpoints (Day 27)  Implements MF0, Get activity summary for a ticket.      Returns aggregate statistics about ticke (+22 more)

### Community 96 - "Community 96"
Cohesion: 0.10
Nodes (39): _get_mini_parwa_pipeline(), _get_parwa_high_pipeline(), _get_parwa_pipeline(), has_variant_tier_in_context(), health_check(), PipelineResult, process_customer_care_message(), process_customer_care_message_sync() (+31 more)

### Community 97 - "Community 97"
Cohesion: 0.09
Nodes (40): JarvisActivityEvent, Jarvis Activity Store — The "Memory" for Non-Agentic Parts.  This is the SINGLE, The Activity Store - records EVERY action that happens in the system.      This, collect_activity_awareness(), _event_to_dict(), get_control_boundary_summary(), get_recent(), get_summary() (+32 more)

### Community 98 - "Community 98"
Cohesion: 0.11
Nodes (39): buildAuthHeaders(), buildOnboardingSystemPrompt(), buildSystemPrompt(), BULLET_EMOJIS, calculateBillSummary(), callAI(), callProvider(), callZAISDK() (+31 more)

### Community 99 - "Community 99"
Cohesion: 0.08
Nodes (25): PaymentProvider, PaymentProvider, ProviderResult, Base class for all payment providers (Stripe, Paddle, …)., Standardised return type for every provider operation.      Attributes:, Serialise to a plain dict (safe for JSON responses)., Register all imported provider adapters with the ProviderRegistry., PaddleProvider (+17 more)

### Community 100 - "Community 100"
Cohesion: 0.06
Nodes (25): ExpiryResult, F-073: Temp Agent Expiry & Deprovisioning  Auto-deprovisions temporary agents wh, Result of an agent expiry/deprovisioning operation.      Attributes:         age, Result of a ticket reassignment operation.      Attributes:         agent_id: Th, Service for managing temporary agent lifecycle.      Maintains an in-memory regi, Register a new temporary agent with an expiry window.          Args:, Register a permanent agent as eligible for ticket reassignment.          Permane, Check if a temp agent has expired.          Args:             agent_id: Agent to (+17 more)

### Community 101 - "Community 101"
Cohesion: 0.10
Nodes (37): Tracks which instance handled which ticket.     Supports rebalancing, escalation, VariantWorkloadDistribution, ChannelPinnedStrategy, complete_ticket_assignment(), escalate_ticket(), get_all_instance_loads(), get_distribution_history(), get_instance_load() (+29 more)

### Community 102 - "Community 102"
Cohesion: 0.08
Nodes (40): Webhook ordering tracking., WebhookSequence, check_dependencies_met(), cleanup_old_sequences(), get_next_processing_order(), get_or_create_webhook_sequence(), get_pending_events_ordered(), get_stuck_events() (+32 more)

### Community 103 - "Community 103"
Cohesion: 0.06
Nodes (24): LockoutLevel, ProgressiveLockout, RateLimiter, RateLimitResult, PARWA Rate Limiter (BC-011 / BC-012)  Sliding window rate limiting with progress, Check if a request is allowed under the rate limit.          Uses sliding window, Build rate limit key with company_id namespace (BC-001).          Uses SHA-256 h, Remove expired entries from all windows.          L-04 FIX: Prevents unbounded m (+16 more)

### Community 104 - "Community 104"
Cohesion: 0.18
Nodes (41): delete_customer(), get_customer_channels(), get_customer_tickets(), link_channel(), merge_customers(), PARWA Customers API - Customer Management Endpoints (Day 30)  Implements F-070:, List customers with filters and pagination., Update customer fields. (+33 more)

### Community 105 - "Community 105"
Cohesion: 0.07
Nodes (26): build_greeting(), build_intent_response(), build_post_call_summary(), build_resolution(), create_voice_server(), ParwaVoiceConfig, ParwaVoiceResponseBuilder, ParwaVoiceServer (+18 more)

### Community 106 - "Community 106"
Cohesion: 0.06
Nodes (16): EmailProvider, EmailProvider, Base class for all e-mail providers (Brevo, SendGrid, SES, …)., BrevoProvider, PARWA AI — Brevo (formerly Sendinblue) Email Provider  API reference: https://de, Brevo (Sendinblue) email provider adapter., PostmarkProvider, PARWA AI — Postmark Email Provider  API reference: https://postmarkapp.com/devel (+8 more)

### Community 107 - "Community 107"
Cohesion: 0.06
Nodes (30): ClusterConfig, ClusterConfigFrozen, ClusterTicket, _compute_cluster_center(), cosine_similarity(), generate_embedding(), _normalize_tickets(), Semantic Clustering Engine (F-071): Groups similar tickets by embedding similari (+22 more)

### Community 108 - "Community 108"
Cohesion: 0.06
Nodes (22): Agent, Chat Widget Service — Week 13 Day 4 (F-122: Live Chat Widget)  Handles the compl, Get the HMAC secret key for visitor token signing.          Returns:, Auto-assign a session to an available agent.          Uses simple round-robin or, Pick the agent with the fewest active chat sessions.          Args:, Check if widget requires visitor fields that are missing.          Args:, Get widget config (private helper)., List chat sessions with pagination and filters.          Args:             compa (+14 more)

### Community 109 - "Community 109"
Cohesion: 0.08
Nodes (30): AIConfig(), AIConfigProps, STYLE_OPTIONS, TONE_OPTIONS, COMPANY_SIZE_OPTIONS, DetailsForm(), DetailsFormData, DetailsFormProps (+22 more)

### Community 110 - "Community 110"
Cohesion: 0.05
Nodes (41): _get_service_module(), jarvis_accept_legal_consents(), jarvis_activate_ai(), jarvis_calculate_totals(), jarvis_capture_lead(), jarvis_complete_onboarding_step(), jarvis_get_analytics(), jarvis_get_audit_stats() (+33 more)

### Community 111 - "Community 111"
Cohesion: 0.07
Nodes (24): LLMProvider, Supported LLM provider modes., Chat with a fallback text if LLM fails.          Args:             system_prompt, Check if the LLM client is available via gateway., Lightweight LLM client for the Mini Parwa pipeline.      Uses the OpenAI Python, Initialize the Mini LLM client.          Day 3: Now delegates to the unified llm, No-op: gateway handles lazy initialization., Send a chat completion request via the unified llm_gateway.          Day 3: Dele (+16 more)

### Community 112 - "Community 112"
Cohesion: 0.08
Nodes (22): NarrowQueryDetector, F-142: Step-Back Prompting — Tier 2 Conditional  Day 3: LLM integration — LLM-po, Immutable configuration for Step-Back processing (BC-001)., Output of Step-Back processing., Result of narrow query detection., Step-Back Prompting processor (F-142).      Deterministic, heuristic-based (no L, Compile entity reference regex patterns., Detect whether a query is narrow or reasoning is stuck.          Checks in prior (+14 more)

### Community 113 - "Community 113"
Cohesion: 0.10
Nodes (36): ActivityLog, PARWA Activity Log Model — Jarvis Awareness Store for Non-Agentic Parts  This is, Universal activity log for non-agentic awareness.      Every action in the syste, _detect_awareness_flags(), _entry_to_dict(), get_awareness_context(), get_billing_awareness(), get_entity_history() (+28 more)

### Community 114 - "Community 114"
Cohesion: 0.09
Nodes (38): BillingStatusResponse, extract_company_id_from_event(), get_billing_status(), handle_paddle_webhook(), handle_payment_failed_webhook(), handle_payment_succeeded_webhook(), PaddleWebhookPayload, PaymentFailedWebhook (+30 more)

### Community 115 - "Community 115"
Cohesion: 0.07
Nodes (28): check_ooo(), check_sender_ooo_status(), create_ooo_rule(), delete_ooo_rule(), _get_db(), get_ooo_stats(), list_ooo_rules(), OOO Detection API Endpoints — Week 13 Day 3 (F-122)  Provides tenant-level OOO d (+20 more)

### Community 116 - "Community 116"
Cohesion: 0.07
Nodes (21): F-149: Thread of Thought (ThoT) — Tier 2 Conditional AI Reasoning Technique  Day, Immutable configuration for Thread of Thought (BC-001).      Attributes:, Analysis of the reasoning thread continuity.      Attributes:         turn_count, Output of the Thread of Thought pipeline.      Attributes:         thread_analys, Thread of Thought processor (F-149).      Deterministic, heuristic-based (no LLM, Extract and analyze the reasoning thread.          Args:             reasoning_t, Identify the dominant topic domain from a list of text entries.          Returns, Detect the type of topic shift between previous and current topic.          Uses (+13 more)

### Community 117 - "Community 117"
Cohesion: 0.10
Nodes (32): batch_resolve_identities(), get_grandfathered_tickets(), get_match_logs(), get_potential_duplicates(), PARWA Identity API - Identity Resolution Endpoints (Day 30)  Implements F-070: I, Get identity match logs.      Returns history of identity resolution attempts., PS14: Get tickets with grandfathered plan tiers.      Open tickets retain the pl, Resolve multiple identities in batch.      Useful for bulk importing or syncing. (+24 more)

### Community 118 - "Community 118"
Cohesion: 0.06
Nodes (34): build_parwa_high_graph(), ParwaHighPipeline, High Parwa LangGraph Pipeline — Builds and runs the 27-node pipeline.  Pipeline:, Route after GSD state node.      If emergency + escalate state -> skip to format, Route after classify — High goes to smart_enrichment first., Route after smart_enrichment to intent-specific deep enrichment.      If the int, Route after deep enrichment → always extract_signals., Route after reasoning_chain -> always context_enrich. (+26 more)

### Community 119 - "Community 119"
Cohesion: 0.07
Nodes (20): GCPStorageBackend, Generate a signed URL. Returns local path as fallback., Generate a v4 signed URL for a GCS object.          Args:             company_id, Check if a file exists. Uses local filesystem as fallback., Check if a blob exists in Google Cloud Storage.          Returns:             Tr, Get file size in bytes. Uses local filesystem as fallback., Get the size of a blob in Google Cloud Storage.          Returns:             Fi, Google Cloud Storage backend with local filesystem fallback.      When GCP crede (+12 more)

### Community 120 - "Community 120"
Cohesion: 0.08
Nodes (29): _apply_overrides_dataclass(), ConfigVersionEntry, _mini_parwa_defaults(), _parwa_defaults(), _parwa_high_defaults(), Per-Tenant Configuration Management (Week 10 Day 3).  Manages per-company config, Default config for mini_parwa variant., Default config for parwa variant. (+21 more)

### Community 121 - "Community 121"
Cohesion: 0.10
Nodes (20): ChannelType, Available customer channel types., CustomerService, PARWA Customer Service - Customer Management & Channel Linking (Day 30)  Impleme, Get a customer by ID.          Args:             customer_id: Customer ID, Get a customer by email.          Args:             email: Customer email, Get a customer by phone.          Args:             phone: Customer phone, List customers with filters and pagination.          Args:             search: S (+12 more)

### Community 122 - "Community 122"
Cohesion: 0.08
Nodes (28): PaymentFailure, Payment failure audit log., get_payment_failure_service(), PaymentFailureService, Payment Failure Service (F-027, BG-16)  Netflix-style payment failure handling:, Check if company service is stopped due to payment failure.          Args:, Resume service after successful payment.          Called when payment succeeds a, Base exception for payment failure errors. (+20 more)

### Community 123 - "Community 123"
Cohesion: 0.07
Nodes (25): _char_in_ranges(), LanguageDetector, LanguagePipeline, PipelineResult, PipelineStepResult, Check if a character's code point falls within any of the given ranges., Result of a single pipeline step., Result of the full language pipeline. (+17 more)

### Community 124 - "Community 124"
Cohesion: 0.10
Nodes (21): _config_row_to_dict(), Disable shadow mode for a company.          Persists to DB first, then updates R, Determine if a message should be shadow-processed.          Returns (should_shad, Get the active shadow mode config for a company.          Tries Redis first, the, Record a comparison result and check for auto-graduation.          After recordi, Check if auto-graduation criteria are met.          Must be called while holding, Manually promote shadow mode to the next phase.          If target_status is not, Get shadow mode statistics for a company.          Tries DB first; falls back to (+13 more)

### Community 125 - "Community 125"
Cohesion: 0.08
Nodes (23): DependencyGraph, _detect_domain(), _generate_generic_sub_queries(), LeastToMostConfig, LeastToMostProcessor, LeastToMostResult, F-148: Least-to-Most Decomposition — Tier 3 Premium AI Reasoning Technique  Acti, A single sub-query within the decomposition pipeline.      Attributes:         i (+15 more)

### Community 126 - "Community 126"
Cohesion: 0.08
Nodes (25): _describe_failure(), _extract_topic(), _generate_guidance(), _has_rejection_signal(), F-147: Reflexion — Tier 3 Premium AI Reasoning Technique  Self-correction engine, Run the full 5-step Reflexion pipeline.          The pipeline executes:, Execute the Reflexion pipeline.          Implements the 5-step self-correction p, Check if a query contains general rejection signals.      Uses a lightweight heu (+17 more)

### Community 127 - "Community 127"
Cohesion: 0.12
Nodes (32): OAuthAccount, PasswordResetToken, Core Models: companies, users, refresh_tokens, mfa_secrets, backup_codes, api_ke, Stores third-party OAuth provider links for a user.      C-14: The ``access_toke, RefreshToken, UserNotificationPreference, Database models registry., authenticate_user() (+24 more)

### Community 128 - "Community 128"
Cohesion: 0.08
Nodes (35): apply_command_sync(), _apply_command_to_db(), apply_command_to_pipeline_state(), check_jarvis_approval_needed(), _get_redis_async(), _get_redis_sync(), get_variant_aware_command_config(), inject_jarvis_state_into_pipeline() (+27 more)

### Community 129 - "Community 129"
Cohesion: 0.11
Nodes (35): advance_stage(), build_cc_context_from_onboarding(), create_onboarding_session(), deactivate_session(), execute_handoff(), get_current_stage(), get_onboarding_awareness(), get_onboarding_funnel_metrics() (+27 more)

### Community 130 - "Community 130"
Cohesion: 0.07
Nodes (34): BackupCodesCountResponse, BackupCodeUseResponse, create_mfa_session_token(), get_backup_codes_count(), _get_mfa_session_ttl(), get_sessions(), mfa_setup_initiate(), mfa_setup_verify() (+26 more)

### Community 131 - "Community 131"
Cohesion: 0.07
Nodes (32): calculate_pricing(), CalculateRequest, CalculateResponse, _generate_validation_token(), get_industries(), get_variants(), IndustryResponse, PARWA Pricing Router (Day 6)  Endpoints for pricing variants by industry.  All p (+24 more)

### Community 132 - "Community 132"
Cohesion: 0.12
Nodes (26): _ensure_logging(), get_events_since_endpoint(), internal_error_handler(), lifespan(), not_found_handler(), parwa_exception_handler(), PARWA FastAPI Application (BC-012)  Main FastAPI app with: - Health/ready/metric, Ensure logging is configured (safe to call multiple times). (+18 more)

### Community 133 - "Community 133"
Cohesion: 0.06
Nodes (14): slideBackgrounds, SlideData, slides, FooterSection, footerSections, socialLinks, humanSupportItems, parwaItems (+6 more)

### Community 134 - "Community 134"
Cohesion: 0.17
Nodes (32): global_exception_handler(), health_check(), invoke_tool(), lifespan(), list_server_tools(), list_servers(), list_tools(), MCPAuthTokenMiddleware (+24 more)

### Community 135 - "Community 135"
Cohesion: 0.06
Nodes (9): ChannelMeta, ChannelStatus, DashboardHomePage(), getLLMTiers(), LLMTier, SUB_PAGE_MAP, AI_RESPONSES, formatRelativeDate() (+1 more)

### Community 136 - "Community 136"
Cohesion: 0.06
Nodes (30): build_parwa_graph(), ParwaPipeline, Pro Parwa LangGraph Pipeline — Builds and runs the 22-node pipeline.  Pipeline:, Route after classify — Pro goes to smart_enrichment first.      Mini: classify -, Route after smart_enrichment to intent-specific deep enrichment.      If the int, Route after deep enrichment → always extract_signals., Route after reasoning_chain -> always context_enrich., Route after context_enrich -> always generate. (+22 more)

### Community 137 - "Community 137"
Cohesion: 0.07
Nodes (25): _generate_redaction_id(), _generate_token(), get_pii_deredactor(), get_pii_detector(), get_pii_redactor(), PIIDeredactor, PIIRedactionCache, PIIRedactor (+17 more)

### Community 138 - "Community 138"
Cohesion: 0.06
Nodes (29): PARWA SLA Schemas  Pydantic models for SLA (Service Level Agreement) management., Full SLA policy response schema., SLA timer tracking for a specific ticket., SLA breach notification schema., SLA performance statistics., Response after deleting an SLA policy., Summary of a seeded SLA policy., Response after seeding default SLA policies. (+21 more)

### Community 139 - "Community 139"
Cohesion: 0.09
Nodes (21): _categorize_query(), _extract_key_terms(), _get_error_reason(), InversionHypothesis, F-141: Reverse Thinking — Tier 2 Conditional AI Reasoning Technique  Day 3: LLM, Immutable configuration for Reverse Thinking (BC-001).      Attributes:, A single wrong answer hypothesis with its analysis.      Attributes:         hyp, Output of the Reverse Thinking pipeline.      Attributes:         problem_statem (+13 more)

### Community 140 - "Community 140"
Cohesion: 0.09
Nodes (21): _categorize_query(), _normalize_1_to_10(), _normalize_by_lookup(), _normalize_cost(), F-144: Universe of Thoughts (UoT) — Tier 3 Premium AI Reasoning Technique  Day 3, Select the highest-scoring solution.          After evaluation and ranking (desc, Present the selected solution with rationale.          Formats a structured pres, Run the full 5-step Universe of Thoughts pipeline.          Args:             qu (+13 more)

### Community 141 - "Community 141"
Cohesion: 0.08
Nodes (24): Task, _build_dedup_key(), _get_redis_client(), inject_tenant_context(), ParwaBaseTask, ParwaTask, PARWA Task Base Classes (BC-004)  Base task classes that enforce: - company_id a, Safely get request attribute outside task context. (+16 more)

### Community 142 - "Community 142"
Cohesion: 0.06
Nodes (18): _luhn_check(), PIIMatch, Represents a single PII detection match., Detect SSN: 123-45-6789, 123 45 6789., Detect Visa, Mastercard, Amex card numbers., Detect email addresses., Detect US and international phone numbers., Detect IPv4 and IPv6 addresses. (+10 more)

### Community 143 - "Community 143"
Cohesion: 0.06
Nodes (29): AiChunkData, AiConfidenceLowData, AiDraftReadyData, AiThinkingData, ApprovalBulkData, ApprovalPendingData, ApprovalStatusData, ApprovalTimeoutData (+21 more)

### Community 144 - "Community 144"
Cohesion: 0.08
Nodes (27): ActorType, async_log_audit(), AuditAction, AuditEntry, cleanup_old_audit_entries(), create_audit_entry(), export_audit_trail(), get_audit_stats() (+19 more)

### Community 145 - "Community 145"
Cohesion: 0.12
Nodes (23): _agent_selector(), _approval_selector(), get_command_graph(), JarvisCommandGraph, _merge_state_updates(), PARWA Jarvis Command Graph — LangGraph Multi-Agent Graph (Phase 4)  This is the, Route from approval_gate based on approval status.      If the action was auto-a, Merge node output updates into state, properly handling     node_outputs (dict m (+15 more)

### Community 146 - "Community 146"
Cohesion: 0.08
Nodes (19): ColdStartService, get_cold_start_service(), ModelWarmupState, Return current UTC time as ISO-8601 string (BC-012)., Main service for AI Engine cold start management.      Handles:       - Tenant-l, Get warmup status for a tenant. BC-001: company_id is second param., Is the tenant's AI ready for a specific tier?, Is at least LIGHT ready? (+11 more)

### Community 147 - "Community 147"
Cohesion: 0.11
Nodes (20): CRMServer, PARWA MCP — CRM Server  Provides CRM platform integration tools. Supports HubSpo, Return the CRM REST router., Handle crm_get_contact tool invocation., Handle crm_create_note tool invocation., Handle crm_get_deals tool invocation., MCP sub-server for CRM platform integrations., _add_env_info() (+12 more)

### Community 148 - "Community 148"
Cohesion: 0.09
Nodes (29): _get_circuit_breaker_detail(), _get_circuit_breaker_summary(), _get_self_healing_detail(), _get_self_healing_status(), _get_sentry_status(), _get_uptime_seconds(), health_detail_endpoint(), health_endpoint() (+21 more)

### Community 149 - "Community 149"
Cohesion: 0.10
Nodes (29): check_celery(), check_celery_queues(), check_disk_space(), check_external_service(), check_postgresql(), check_redis(), check_socketio(), clear_health_cache() (+21 more)

### Community 150 - "Community 150"
Cohesion: 0.09
Nodes (29): add_tenant_context(), capture_exception(), capture_message(), _combined_before_send(), flush(), _get_sample_rates(), get_sentry_status(), _get_settings() (+21 more)

### Community 151 - "Community 151"
Cohesion: 0.14
Nodes (8): ConnectionState, devError(), devLog(), devWarn(), getAccessToken(), MissedEvent, SocketClient, SocketClientConfig

### Community 152 - "Community 152"
Cohesion: 0.07
Nodes (24): ALL_CATEGORIES, ALL_CHANNELS, ALL_PRIORITIES, ALL_STATUSES, ALL_VARIANTS, CATEGORY_LABELS, CHANNEL_LABELS, MessageSender (+16 more)

### Community 153 - "Community 153"
Cohesion: 0.10
Nodes (28): create_sms_config(), delete_sms_config(), get_consent_status(), _get_db(), get_sms_config(), get_sms_conversation(), get_sms_messages(), list_sms_conversations() (+20 more)

### Community 154 - "Community 154"
Cohesion: 0.09
Nodes (18): _extract_variables(), PromptTemplate, PromptTemplateManager, Per-Intent Prompt Templates (Core Module)  Lightweight prompt template system fo, Extract all ``{{variable}}`` names from template text.      Args:         templa, Replace ``{{var}}`` placeholders with values.      Missing variables are left as, Manages per-intent prompt templates with version tracking.      Features:, Load all 12 built-in intent templates. (+10 more)

### Community 155 - "Community 155"
Cohesion: 0.07
Nodes (22): BatchMigrationResult, _migrate_v1_to_v2(), _migrate_v2_to_v3(), _migrate_v3_to_v4(), _migrate_v4_to_v5(), _migrate_v5_to_v6(), MigrationResult, State Migration Tooling (Week 10 Day 3).  Migrates conversation state between sc (+14 more)

### Community 156 - "Community 156"
Cohesion: 0.09
Nodes (15): IdentityResolutionService, PARWA Identity Resolution Service - Cross-Channel Customer Matching (Day 30)  Im, Match customer by email (exact then fuzzy).          Args:             email: Em, Match customer by phone (exact only).          Args:             phone: Phone nu, Match customer by social media ID via CustomerChannel.          Args:, Match customer by device fingerprint.          Args:             device_id: Devi, Log the resolution attempt.          Args:             email: Input email, Find potential duplicate customers.          Args:             customer_id: Chec (+7 more)

### Community 157 - "Community 157"
Cohesion: 0.22
Nodes (26): AgentMistake, AgentPerformance, Training Models: training_datasets, training_checkpoints, agent_mistakes, agent_, TrainingCheckpoint, TrainingDataset, _build_error_status(), check_mistake_threshold(), cleanup_old_datasets() (+18 more)

### Community 158 - "Community 158"
Cohesion: 0.09
Nodes (24): APIKey, APIKeyScope, APIKeyStatus, base64_urlsafe_encode(), create_api_key(), generate_raw_key(), hash_api_key(), PARWA API Key Management (BC-011)  Secure API key generation, hashing, scope val (+16 more)

### Community 159 - "Community 159"
Cohesion: 0.12
Nodes (26): _check_provider_secret_configured(), _get_company_id_from_payload(), _get_event_id_from_payload(), _get_event_type_from_payload(), _get_max_webhook_age_seconds(), _get_max_webhook_payload_size(), get_webhook_status(), Webhook API Endpoints (BC-003, BC-012)  Generic webhook receiver for multiple pr (+18 more)

### Community 160 - "Community 160"
Cohesion: 0.08
Nodes (27): blacklist_current_token(), blacklist_jti(), create_access_token(), generate_refresh_token(), get_access_token_expiry_seconds(), _get_jwt_algorithm(), get_jwt_previous_keys(), get_token_jti() (+19 more)

### Community 161 - "Community 161"
Cohesion: 0.08
Nodes (8): Sidebar(), SidebarContext, SidebarContextProps, SidebarMenuButton(), sidebarMenuButtonVariants, SidebarRail(), SidebarTrigger(), useSidebar()

### Community 162 - "Community 162"
Cohesion: 0.10
Nodes (19): _categorize_query(), _classify_consensus(), _classify_divergence(), ConsistencyResult, _estimate_answer_confidence(), IndependentAnswer, F-146: Self-Consistency — Tier 3 Premium AI Reasoning Technique  Activates when, Immutable configuration for Self-Consistency (BC-001).      Attributes: (+11 more)

### Community 163 - "Community 163"
Cohesion: 0.09
Nodes (18): AgentStatus, AssignmentStrategy, channel_enum(), ChannelType, deadline_iso(), deterministic_jitter(), is_within_sla(), priority_enum() (+10 more)

### Community 164 - "Community 164"
Cohesion: 0.10
Nodes (17): ClientRefund, PARWA clients refunding THEIR customers.          This is NOT PARWA refunding cl, get_client_refund_service(), Client Refund Service (BG-09)  PARWA clients refunding THEIR customers. This is, Get a refund request by ID.          Args:             company_id: Company UUID, List refund requests for a company.          Args:             company_id: Compa, Mark a refund request as processed.          This is called when the client conf, Mark a refund request as failed.          Args:             company_id: Company (+9 more)

### Community 165 - "Community 165"
Cohesion: 0.08
Nodes (15): get_proration_service(), InvalidProrationPeriodError, Proration Service (BG-04)  Handles proration calculations for subscription varia, Quick estimate of upgrade cost without full proration.          Useful for showi, Special case: Upgrade on first day of billing period.          Full credit for o, Special case: Upgrade on last day of billing period.          No proration neede, Calculate proration given days into a 30-day period.          Convenience method, Validate and normalize variant name. (+7 more)

### Community 166 - "Community 166"
Cohesion: 0.09
Nodes (19): by_allow_list(), by_canary(), by_geography(), by_percentage(), CircuitState, create_migration_engine(), FeatureCategory, MigrationResult (+11 more)

### Community 167 - "Community 167"
Cohesion: 0.09
Nodes (25): clear_tenant_context(), extract_company_id_from_headers(), get_bypass_reason(), get_task_headers(), get_tenant_context(), is_tenant_bypassed(), PARWA Tenant Context (BC-001)  Provides tenant context propagation across: - Asy, Context manager that raises if no tenant context is set.      Yields:         Th (+17 more)

### Community 168 - "Community 168"
Cohesion: 0.08
Nodes (25): _execute_agent_command(), _execute_billing_command(), _execute_knowledge_command(), execute_product_command(), _execute_settings_command(), _execute_shadow_mode_command(), _execute_subscription_command(), _execute_ticket_command() (+17 more)

### Community 169 - "Community 169"
Cohesion: 0.09
Nodes (19): ExecutionMetric, Definition of a DSPy signature., Stub prediction output., Check if DSPy is installed and available.          Returns:             True if, Measure keyword overlap between query intent and response.          Tokenises bo, Check whether expected output fields are present and non-empty.          Looks f, Penalise responses longer than 2× the query length.          Returns 1.0 when th, Check for harmful / PII content in the response.          Returns 0.0 if any blo (+11 more)

### Community 170 - "Community 170"
Cohesion: 0.10
Nodes (13): BillSummaryCard(), BillSummaryCardProps, ChatMessage(), ChatMessageProps, renderInlineContent(), DemoPackCTA(), DemoPackCTAProps, HandoffCard() (+5 more)

### Community 171 - "Community 171"
Cohesion: 0.09
Nodes (14): CircuitBreaker, CircuitState, PARWA Circuit Breaker (BC-012)  Prevents cascading failures by wrapping external, Check if a request can be executed through the circuit.          Returns:, Record a successful request., Record a failed request., Record that a call was attempted (for HALF_OPEN tracking)., Manually reset the circuit breaker to CLOSED state. (+6 more)

### Community 172 - "Community 172"
Cohesion: 0.11
Nodes (16): CarrierAPIConnector, _no_compensation(), _no_delay_result(), _no_tracking_result(), Carrier API Connector — Unified USPS/UPS/FedEx/DHL Interface (Day 3)  Provides a, Unified multi-carrier API connector for shipping tracking.      Provides:, Initialize the carrier API connector with compiled patterns., Pre-compile tracking number patterns for each carrier. (+8 more)

### Community 173 - "Community 173"
Cohesion: 0.11
Nodes (13): IPAllowlistMiddleware, IP Allowlist Middleware (BC-006, BC-012)  ASGI middleware that restricts access, Check if path should skip IP allowlist., Check if client IP is in the allowlist.          Priority:             1. Config, Convert path to a route key for Redis lookup., Get allowlist from Redis., Check if an IP falls within any CIDR range., Send a 403 JSON response (BC-012). (+5 more)

### Community 174 - "Community 174"
Cohesion: 0.17
Nodes (23): APIKeyAuditLog, API Key Audit Log Model (F-019)  Tracks all API key lifecycle events: created, r, APIKey, _create_audit(), create_key(), _generate_raw_key(), list_keys(), _parse_scopes() (+15 more)

### Community 175 - "Community 175"
Cohesion: 0.11
Nodes (23): _build_sentiment_summary(), capture_lead(), _determine_lead_status(), _estimate_monthly_value(), get_all_leads(), get_lead(), get_lead_stats(), get_leads_by_status() (+15 more)

### Community 176 - "Community 176"
Cohesion: 0.11
Nodes (23): admin_health(), create_api_provider(), delete_api_provider(), get_client_detail(), list_api_providers(), list_clients(), PARWA Admin API Router (F06)  Platform admin endpoints for managing clients (com, List all companies (paginated).      Platform admin endpoint. Can filter by name (+15 more)

### Community 177 - "Community 177"
Cohesion: 0.11
Nodes (23): change_password(), get_profile(), get_settings(), get_team(), PARWA Client API Router (F06)  Endpoints for company profile, settings, password, Convert Company ORM object to response dict., Convert User ORM object to TeamMemberResponse dict., Get company profile.      BC-001: Scoped to authenticated user's company. (+15 more)

### Community 178 - "Community 178"
Cohesion: 0.14
Nodes (23): _add_edges(), _add_nodes(), build_parwa_graph(), _fallback_response(), _get_default_checkpointer(), _get_node_function(), invoke_parwa_graph(), _make_validated_node() (+15 more)

### Community 179 - "Community 179"
Cohesion: 0.11
Nodes (12): BaseDomainAgent, Base Domain Agent — Abstract base class for all domain agents.  This is NOT a di, Apply the technique stack to enrich the message context.          Each technique, Lazily import and return a technique function by ID.          Technique modules, Generate the domain agent's response.          Uses the production response_gene, Template-based response generation fallback.          Produces a simple acknowle, Classify a proposed action into an action type category.          Uses the confi, Hook for subclasses to add extra fields to the state update.          Override t (+4 more)

### Community 180 - "Community 180"
Cohesion: 0.11
Nodes (11): Base class for all SMS providers (Twilio, Vonage, …)., SMSProvider, _auto_register(), PARWA AI — Provider Abstraction Layer  This package provides a provider-agnostic, PARWA AI — Twilio SMS Provider  API reference: https://www.twilio.com/docs/sms/a, Twilio SMS provider adapter., TwilioProvider, PARWA AI — Vonage (formerly Nexmo) SMS Provider  API reference: https://develope (+3 more)

### Community 181 - "Community 181"
Cohesion: 0.11
Nodes (13): BaseTool, CustomerLookupTool, KnowledgeBaseSearchTool, OrderStatusCheckTool, PARWA ReAct Tools — Tool Registry for ReAct Technique (P4.3)  Implements the 4 r, Look up customer details including contact info, tier, and status., Search past ticket history for patterns and similar issues., Check the current status of an order. (+5 more)

### Community 182 - "Community 182"
Cohesion: 0.13
Nodes (21): _build_approval_message(), _build_confirmation_message(), check_safety(), clear_all_pending(), _clear_pending_confirmation(), force_approve(), _get_pending_confirmation(), get_pending_status() (+13 more)

### Community 183 - "Community 183"
Cohesion: 0.09
Nodes (23): filter_functions_by_channel(), get_function_categories(), get_function_count_by_category(), get_function_count_by_safety(), get_function_count_by_stage(), get_function_metadata(), get_function_names(), get_functions_by_category() (+15 more)

### Community 184 - "Community 184"
Cohesion: 0.11
Nodes (23): accept_legal_consents(), activate_ai(), complete_first_victory(), complete_step(), get_first_victory_status(), get_knowledge_documents(), get_or_create_session(), get_session_with_lock() (+15 more)

### Community 185 - "Community 185"
Cohesion: 0.13
Nodes (23): batch_update_capabilities(), check_feature_enabled(), get_all_variant_summaries(), get_capability(), get_enabled_features(), get_variant_feature_count(), initialize_variant_matrix(), list_capabilities() (+15 more)

### Community 186 - "Community 186"
Cohesion: 0.13
Nodes (13): CompressionOutput, Compress context for a given company.          Args:             company_id: Ten, Select top-priority chunks until target reached.          Sorts chunks by priori, Keep most recent chunks within budget.          Iterates from the end of the con, Sort by priority, keep high-priority content.          Chunks below the priority, Summarize low-priority chunks, keep high-priority as-is.          High-priority, Extractive for high-priority + abstractive for low-priority.          High-prior, Simple token estimation: approximately 4 chars per token. (+5 more)

### Community 187 - "Community 187"
Cohesion: 0.08
Nodes (13): GracefulEscalationManager, Get escalation details by ID.          Args:             company_id: Tenant comp, List all escalations for a specific ticket.          Includes both active and re, Manually set a cooldown for a specific trigger.          Args:             compa, Get recent notification dispatches for a company.          Returns the most rece, Generate a human-readable escalation notification message.          Produces a f, Register an event listener callback.          The callback will be invoked for e, Remove a previously registered event listener.          Args:             callba (+5 more)

### Community 188 - "Community 188"
Cohesion: 0.08
Nodes (24): build_system_prompt(), detect_stage(), _extract_topics_and_concerns(), _generate_strategic_summary(), _get_default_system_prompt(), _get_friendly_error_message(), _get_limit_message(), _get_recent_history() (+16 more)

### Community 189 - "Community 189"
Cohesion: 0.08
Nodes (23): DemoBillingEstimate, DemoBillingResponse, DemoBillItem, DemoBillSummary, DemoKnowledgeBase, DemoKnowledgeBaseListResponse, DemoKnowledgeBaseUpload, DemoKnowledgeBaseUploadResponse (+15 more)

### Community 190 - "Community 190"
Cohesion: 0.10
Nodes (22): create_socketio_app(), emit_to_session(), emit_to_tenant(), _extract_token_from_qs(), get_connected_count(), get_socketio_server(), get_tenant_room(), PARWA Socket.io Server (BC-005, BC-001, BC-011)  Provides the Socket.io server w (+14 more)

### Community 191 - "Community 191"
Cohesion: 0.17
Nodes (22): BackupCode, MFASecret, MFA TOTP secret (C-14: secret_key is Fernet-encrypted at rest).      The secret_, _generate_backup_codes(), _generate_qr_code_data_url(), get_remaining_backup_codes(), _hash_backup_code(), initiate_mfa_setup() (+14 more)

### Community 192 - "Community 192"
Cohesion: 0.19
Nodes (9): ContextCompressionError, Raised when context compression fails critically.      Inherits from Exception f, Exception, get_usage_tracking_service(), _round_money(), UsageLimitExceededError, UsageTrackingError, UsageTrackingService (+1 more)

### Community 193 - "Community 193"
Cohesion: 0.10
Nodes (18): ParwaBaseTask, AggregateTechniqueMetricsTask, ExecuteTechniqueTask, LogTechniqueExecutionTask, Technique Tasks — Celery tasks for async technique execution and monitoring.  DE, Log technique execution metrics to the database.      Called after each techniqu, Log a technique execution to the database.          Args:             company_id, # TODO: Insert into technique_executions table (Week 10+) (+10 more)

### Community 194 - "Community 194"
Cohesion: 0.09
Nodes (10): BillingCycle, BillingPage(), formatCurrency(), formatDate(), Invoice, InvoiceStatus, MOCK_INVOICES, PLANS (+2 more)

### Community 195 - "Community 195"
Cohesion: 0.09
Nodes (12): DSPyIntegration, Sanitize a path component to prevent path traversal (Day 4).          Only allow, Persist a compiled DSPy module to disk.          Day 4: Path components are vali, Load a previously compiled DSPy module from disk.          Day 4: Path component, DSPy framework integration for PARWA.      Bridges PARWA's ConversationState wit, Define or retrieve a DSPy signature for a task type.          Args:, Bridge PARWA ConversationState to DSPy inputs.          Extracts relevant fields, Get DSPy execution metrics summary.          Returns:             Dictionary wit (+4 more)

### Community 196 - "Community 196"
Cohesion: 0.13
Nodes (7): _is_ai_enabled(), MigrationEngine, Manages gradual rule → AI migration with Redis-backed feature flags.      Usage:, Returns True when val != 'rule'.  None means enabled by default., Low-level flag check (does not consider rollout / circuit / confidence)., Full decision pipeline: flag → circuit → rollout → confidence.          Returns, _redis_key()

### Community 197 - "Community 197"
Cohesion: 0.11
Nodes (12): ProviderHealthTracker, Tracks health and rate limits for all provider+model combinations.      BC-008:, Reset daily counters at midnight UTC (BC-012)., Record a successful API call. Resets consecutive failure count., Check if a provider+model is usable (healthy + under limits)., Get today's usage count for a provider+model., Get remaining daily requests for a provider+model., Check if a provider+model is currently rate limited. (+4 more)

### Community 198 - "Community 198"
Cohesion: 0.17
Nodes (15): EcommerceServer, PARWA MCP — E-Commerce Server  Provides e-commerce platform integration tools. S, Return the e-commerce REST router., Handle ecommerce_get_order tool invocation., Handle ecommerce_search_products tool invocation., Handle ecommerce_get_customer_orders tool invocation., MCP sub-server for e-commerce platform integrations., Register e-commerce tools. (+7 more)

### Community 199 - "Community 199"
Cohesion: 0.09
Nodes (10): AGENTS_PER_PLAN, createDemoSession(), DEMO_INDUSTRIES, DEMO_VARIANTS, demoSessions, demoUsageEvents, generateId(), PLAN_PRICES (+2 more)

### Community 200 - "Community 200"
Cohesion: 0.12
Nodes (21): AgentCreateRequest, AgentUpdateRequest, create_agent(), delete_agent(), get_agent_detail(), get_agent_for_feature(), get_summary(), initialize_default_agents() (+13 more)

### Community 201 - "Community 201"
Cohesion: 0.15
Nodes (21): batch_classify(), BatchClassifyRequest, classify_text(), ClassifyRequest, get_all_mappings(), _get_engine(), get_intent_mapping(), _get_mapper() (+13 more)

### Community 202 - "Community 202"
Cohesion: 0.13
Nodes (21): _check_rate_limit(), emit_ai_event(), emit_approval_event(), emit_event(), emit_notification_event(), emit_system_event(), emit_ticket_event(), _enrich_payload() (+13 more)

### Community 203 - "Community 203"
Cohesion: 0.13
Nodes (21): command_executor_node(), _create_command_record(), _dispatch_command_event(), _execute_action(), _execute_escalation(), _execute_notification(), _execute_quality_recovery(), _execute_reassignment() (+13 more)

### Community 204 - "Community 204"
Cohesion: 0.11
Nodes (21): check_ai_activation_prerequisites(), create_or_update_user_details(), get_onboarding_state(), get_user_details(), _mark_details_completed(), PARWA User Details Service (Week 6 Day 1)  Business logic for post-payment user, Sanitize email input., Get user details for a user.      BC-001: Scoped to company_id.      Args: (+13 more)

### Community 205 - "Community 205"
Cohesion: 0.22
Nodes (7): _build_check_result(), get_variant_limit_service(), _validate_company_id(), _validate_limit_type(), VariantLimitError, VariantLimitExceededError, VariantLimitService

### Community 206 - "Community 206"
Cohesion: 0.15
Nodes (21): IdempotencyKey, Webhook idempotency tracking., check_idempotency_key(), cleanup_expired_idempotency_keys(), _compute_hash(), generate_idempotency_key(), get_idempotency_key_info(), process_with_idempotency() (+13 more)

### Community 207 - "Community 207"
Cohesion: 0.10
Nodes (8): AssignmentEngine, AssignmentEventBus, create_engine(), Assign multiple tickets sequentially., Reset all engine state (useful in tests)., Return capacity info for every agent., Synchronous in-process pub/sub for assignment lifecycle events.      Subscribers, Main engine with caching, capacity management, event bus, and metrics.      Usag

### Community 208 - "Community 208"
Cohesion: 0.12
Nodes (11): ML-score based assignment.      Weighted composite score:         specialty_matc, 0..1 — higher when the agent's specialties match the ticket., 0..1 — higher when the agent has more free capacity., 0..1 — direct mapping from the agent's historical accuracy., 0..jitter_range — random noise for tie-breaking., Small bonus (0..0.05) for senior agents on complex tickets., 0..0.10 bonus when the agent speaks the ticket's language., 1.0 if the agent is authorised for the customer tier, 0.2 otherwise. (+3 more)

### Community 209 - "Community 209"
Cohesion: 0.09
Nodes (12): Mark a deactivation notice as acknowledged by an admin.          BC-001: company, Return all known variant type names., Return the numeric rank of a variant (1, 2, or 3).          Returns 0 for unknow, Return the number of in-flight tickets for a company.          BC-001: company_i, Return all in-flight tickets across all companies that have         a pending tr, Reset a company's effective variant to a specified default.          Useful for, Handles seamless variant transitions while tickets are in-flight.      SG-08 (Up, Remove a ticket from in-flight tracking.          Called when a ticket is closed (+4 more)

### Community 210 - "Community 210"
Cohesion: 0.19
Nodes (15): PARWA MCP — Ticketing Server  Provides support ticket lifecycle tools. Supports, Return the ticketing REST router., Handle ticket_create tool invocation., Handle ticket_get tool invocation., Handle ticket_update_status tool invocation., Handle ticket_search tool invocation., MCP sub-server for support ticket operations., Register ticketing tools. (+7 more)

### Community 211 - "Community 211"
Cohesion: 0.19
Nodes (15): _get_voice_service(), PARWA MCP — Voice Server  Provides voice call tools via Twilio integration. Supp, Return the voice REST router., Handle voice_initiate_call tool invocation.          Wires directly to VoiceChan, Handle voice_get_call_status tool invocation., Get a VoiceChannelService instance connected to the DB.      Returns:         Tu, Handle voice_end_call tool invocation., Handle voice_list_active_calls tool invocation. (+7 more)

### Community 212 - "Community 212"
Cohesion: 0.13
Nodes (18): Store config in Redis cache., Persist config to database.          Stub implementation — to be wired to the OR, Validate tone is a known value., Validate formality level is in range 0.0-1.0., Validate response length preference., Validate emoji usage value., Validate apology style value., Validate escalation tone value. (+10 more)

### Community 213 - "Community 213"
Cohesion: 0.09
Nodes (21): AIConfig, AIResponseStyle, AITone, ApiErrorResponse, ApiResponse, CompanySize, ConsentRecord, ConsentType (+13 more)

### Community 214 - "Community 214"
Cohesion: 0.14
Nodes (20): close_redis(), get_build_key(), get_get_ttl(), All valid Redis key namespaces in PARWA., RedisNamespace, _log_raw_key_access(), namespaced_delete(), namespaced_set() (+12 more)

### Community 215 - "Community 215"
Cohesion: 0.10
Nodes (11): CircuitBreakerManager, Central manager for all circuit breakers.      Manages circuit breakers for ALL, Remove a circuit breaker.          Args:             name: Unique identifier for, Check if the dependency is available (circuit closed or half-open).          Ret, Record a successful call to a dependency.          Args:             name: Depen, Record a failed call to a dependency.          Args:             name: Dependenc, Get current circuit state for a dependency.          Returns CLOSED if the break, Manually open a circuit (for maintenance).          Returns True if the breaker (+3 more)

### Community 216 - "Community 216"
Cohesion: 0.10
Nodes (12): CLARAResult, _filter_phone_false_positives(), Run full 5-stage CLARA pipeline.          GAP-002: Pipeline-level timeout wraps, Run all stages sequentially with per-stage timeout., Run a single stage with timeout (GAP-002 FIX)., Validate response structure., Validate logical consistency.          D6-GAP-02 FIX: Uses context dict for addi, Validate brand voice compliance.          GAP-018 FIX: If brand voice is NOT cus (+4 more)

### Community 217 - "Community 217"
Cohesion: 0.15
Nodes (16): ApiKeyInputCard(), ApiKeyInputCardProps, CardStage, DetectionResult, TestResult, ConnectionErrorCard(), ConnectionErrorCardProps, DEFAULT_FIXES (+8 more)

### Community 218 - "Community 218"
Cohesion: 0.12
Nodes (19): _classify_error(), get_dlq_entries(), get_dlq_stats(), GraphExecutionDLQ, _persist_to_db(), persist_to_dlq(), _persist_to_redis(), PARWA LangGraph Dead Letter Queue (DB-backed)  Persists failed graph executions (+11 more)

### Community 219 - "Community 219"
Cohesion: 0.10
Nodes (19): PARWA LangGraph Conditional Edge Functions  These functions are used as conditio, Route after Control System approval decision.      approved / auto_approved → DS, Route after guardrails check.      If guardrails_passed is True → channel_delive, Route to the channel-specific delivery agent.      Respects variant_tier channel, Determine whether to run DSPy prompt optimization.      DSPy optimization is:, Determine whether context compression should run.      Context compression runs, Check emergency state before processing.      If AI is globally paused → state_u, After a channel-specific agent completes, go to state_update     for persistence (+11 more)

### Community 220 - "Community 220"
Cohesion: 0.11
Nodes (16): build_mini_parwa_graph(), MiniParwaPipeline, Mini Parwa LangGraph Pipeline — Builds and runs the 10-node pipeline.  Pipeline:, Route after CLARA quality gate.      For Mini: always proceed to format (no retr, Build the Mini Parwa LangGraph StateGraph.      Creates the graph with all 10 no, Mini Parwa pipeline — runs the 10-node LangGraph pipeline.      Connected Framew, Initialize the pipeline by building the graph., Invoke the LangGraph pipeline with the given state.          Args:             s (+8 more)

### Community 221 - "Community 221"
Cohesion: 0.13
Nodes (19): apply_filters(), build_paginated_response(), FilterParams, _is_sqlite(), paginate_query(), paginate_query_v2(), PaginatedResponse, parse_sort() (+11 more)

### Community 222 - "Community 222"
Cohesion: 0.12
Nodes (19): build_key(), cleanup_namespace(), get_namespace_metrics(), get_ttl(), namespaced_cache_delete(), namespaced_cache_get(), namespaced_cache_set(), parse_key() (+11 more)

### Community 223 - "Community 223"
Cohesion: 0.12
Nodes (18): add_message_to_context(), build_conversation_summary(), _calculate_duration(), ConversationContext, create_conversation(), get_conversation_context(), get_conversation_history(), PARWA Conversation Service (Week 9 — Conversation Management)  Manages conversat (+10 more)

### Community 224 - "Community 224"
Cohesion: 0.14
Nodes (19): _apply_routing_overrides(), _empty_result(), _inject_awareness_fields(), _inject_command_context(), _inject_emergency_controls(), jarvis_awareness_injector_node(), PARWA Jarvis Awareness Injector Node (Phase 4)  A LangGraph node that can be add, Read the bridge state from Redis (synchronous, using fallback).      Since this (+11 more)

### Community 225 - "Community 225"
Cohesion: 0.14
Nodes (19): _extract_attachments(), _extract_inbound_email_data(), handle_bounce(), handle_brevo_event(), handle_complaint(), handle_delivered(), handle_inbound_email(), Brevo Webhook Handler (BC-003, BC-006)  Handles Brevo webhook events: - inbound_ (+11 more)

### Community 226 - "Community 226"
Cohesion: 0.14
Nodes (19): _extract_sms_data(), _extract_voice_data(), handle_sms_incoming(), handle_twilio_event(), handle_voice_call_ended(), handle_voice_call_started(), Twilio Webhook Handler (BC-003, GAP 1.5)  Handles Twilio SMS and voice webhooks:, Validate SMS data has required fields.      Returns:         Error message if va (+11 more)

### Community 227 - "Community 227"
Cohesion: 0.13
Nodes (12): BillSummaryCard(), BillSummaryCardProps, PaymentCard(), PaymentCardProps, ErrorBanner(), ErrorBannerProps, Props, OnboardingJarvisInput() (+4 more)

### Community 228 - "Community 228"
Cohesion: 0.14
Nodes (12): _is_terminal_status(), LifecycleSnapshot, Mark a lifecycle as successfully completed.          Moves the lifecycle to COMP, Mark a lifecycle as failed.          Moves the lifecycle to FAILED status, recor, List all active (non-terminal) lifecycles for a company.          Args:, Get aggregated lifecycle statistics for a company.          Computes totals, suc, Point-in-time snapshot of a lifecycle.      Immutable view of a lifecycle's stat, Build a LifecycleSnapshot from a lifecycle data dict.          Computes complete (+4 more)

### Community 229 - "Community 229"
Cohesion: 0.17
Nodes (7): MigrationEvent, MigrationPlanner, Immutable record of a migration lifecycle event., Plans and executes staged rollouts for a feature.      Stages     ------     1., Move to the next rollout stage and return the new config., Disable AI and reset stage index., Freeze at the current stage but keep AI enabled.

### Community 230 - "Community 230"
Cohesion: 0.12
Nodes (11): _estimate_tokens(), _is_technique_boosted(), Get allowed tiers for a variant type (SG-03).          Unknown variant types def, Pick the tier for a given atomic step.          Respects variant gating: if reco, Pick primary model + list of fallbacks for a tier.          Models within a tier, Check if a model's provider is healthy and under rate limits., Find next available model in the same tier., Degrade to the next lower available tier. (+3 more)

### Community 231 - "Community 231"
Cohesion: 0.18
Nodes (13): DemoBillCard(), DemoBillCardProps, DemoIndustryPicker(), DemoIndustryPickerProps, DemoKnowledgeBasePanel(), DemoKnowledgeBasePanelProps, DemoPackFlow(), DemoStep (+5 more)

### Community 232 - "Community 232"
Cohesion: 0.11
Nodes (14): BillingState, BillingUsage, Invoice, PaymentMethod, TIER_PRICES, useBillingStore, DEFAULT_USAGE, FeatureMap (+6 more)

### Community 233 - "Community 233"
Cohesion: 0.13
Nodes (10): Check BC-006 rate limit for visitor messages.          Args:             session, Create a system event message in a session.          Args:             session_i, Emit a Socket.io event for real-time updates (BC-005).          Gracefully handl, Get a chat session with company_id isolation (BC-001).          Args:, Assign an agent to a chat session.          Emits a Socket.io event for real-tim, Close a chat session.          Sets status to 'closed' and records the close tim, Send a message in a chat session.          Validates rate limits (BC-006), creat, Emit a typing indicator via Socket.io (BC-005).          Args:             sessi (+2 more)

### Community 234 - "Community 234"
Cohesion: 0.10
Nodes (16): alert, assertive, banner, btn, charts, { container }, dismissBtn, iconSpan (+8 more)

### Community 235 - "Community 235"
Cohesion: 0.10
Nodes (19): AgentMetrics, AgentMetricsResponse, CategoryDistribution, CategoryDistributionResponse, ChannelConfig, ChannelInfo, ChannelType, DashboardData (+11 more)

### Community 236 - "Community 236"
Cohesion: 0.15
Nodes (13): CSRFSecurityMiddleware, _extract_cookie(), generate_csrf_token(), _is_cookie_auth_path(), _parse_trusted_origins(), CSRF Protection Middleware (H-04, BC-008)  Pure ASGI middleware that provides CS, Check if CSRF middleware is enabled., Process a single ASGI HTTP request through CSRF checks. (+5 more)

### Community 237 - "Community 237"
Cohesion: 0.14
Nodes (11): get_zai_client(), PARWA Jarvis ZAI SDK Client  The LLM brain behind Jarvis's multi-agent command l, ZAI SDK client for Jarvis agent LLM calls.      This is the brain behind every J, Lazy-initialize the ZAI SDK synchronously. Returns True if available.          T, Async SDK initialization — called from chat_async when needed.          JV-01 FI, Async: Ask the LLM a question from an agent and get a structured response., Synchronous wrapper for chat_async.          Uses asyncio.run() or ThreadPoolExe, Parse the LLM response into a structured dict.          The LLM should return JS (+3 more)

### Community 238 - "Community 238"
Cohesion: 0.16
Nodes (14): PARWA Onboarding Jarvis — Agentic Multi-Agent System  The Onboarding Jarvis is b, get_onboarding_graph(), OnboardingJarvisGraph, PARWA Onboarding Jarvis LangGraph — Multi-Agent Graph  Wires the Onboarding Rout, Determine which specialist agent to route to.          Reads the router_decision, Try to import a node function, return None if unavailable.          Used for nod, Get or create the singleton Onboarding Jarvis graph.      Returns:         Compi, Convenience function to run the Onboarding Jarvis graph from a message.      Thi (+6 more)

### Community 239 - "Community 239"
Cohesion: 0.13
Nodes (10): PARWA Ticket Service - Core CRUD Business Logic (Day 26)  Implements F-046: Tick, Get a single ticket by ID.          Args:             ticket_id: Ticket ID, List tickets with filters and pagination.          Args:             status: Fil, Delete a ticket (soft delete by default).          PS12: Soft delete preserves m, Assign a ticket to an agent.          Args:             ticket_id: Ticket ID, Core ticket CRUD operations with production situation handlers., Add tags to a ticket.          Args:             ticket_id: Ticket ID, Remove a tag from a ticket.          Args:             ticket_id: Ticket ID (+2 more)

### Community 240 - "Community 240"
Cohesion: 0.13
Nodes (10): DocumentChunker, PARWA Document Chunker  Splits documents into chunks for embedding and retrieval, Split markdown text by headers first, then by size.          Markdown documents, Estimate the number of chunks without actually splitting.          Args:, Remove HTML tags and decode common entities., Find a paragraph break near *end* to avoid splitting mid-paragraph.          Loo, Split markdown text on ## and ### headers.          Returns:             List of, Build metadata dict for a chunk. (+2 more)

### Community 241 - "Community 241"
Cohesion: 0.14
Nodes (11): List features that will be restricted in a downgrade.          Computes the set, Clear cache entries for features no longer available after downgrade.          S, Check if a variant transition is valid.          Validates:           - Both var, Roll back a transition that has not yet been fully applied.          Only ACTIVE, Create a transition record that represents a failed validation.          Uses RO, Audit record for a variant upgrade or downgrade event.      Captures the full co, Serialise transition record to a plain dict., Start the upgrade process for a company (SG-08).          Steps:           1. Va (+3 more)

### Community 242 - "Community 242"
Cohesion: 0.11
Nodes (13): CannedResponse, ChatWidgetConfig, ChatWidgetMessage, ChatWidgetSession, Chat Widget Models — Week 13 Day 4 (F-122: Live Chat Widget)  Tables: - ChatWidg, Serialize chat session for API responses., Message within a chat widget session.      Supports multiple roles (visitor, age, Serialize chat message for API responses. (+5 more)

### Community 243 - "Community 243"
Cohesion: 0.21
Nodes (13): KBServer, PARWA MCP — Knowledge Base Server  Provides knowledge base document query tools., Return the KB REST router., Handle kb_search tool invocation., Handle kb_get_document tool invocation., Handle kb_list_bases tool invocation., MCP sub-server for knowledge base document queries., KBDocument (+5 more)

### Community 244 - "Community 244"
Cohesion: 0.13
Nodes (17): apiClient, authApi, del(), get(), integrationsApi, knowledgeApi, onboardingApi, patch() (+9 more)

### Community 245 - "Community 245"
Cohesion: 0.16
Nodes (14): sendEmail(), buildCreatedEmail(), buildEscalatedEmail(), buildInProgressEmail(), buildResolvedEmail(), escapeHtml(), NotificationPayload, NotificationResult (+6 more)

### Community 246 - "Community 246"
Cohesion: 0.11
Nodes (8): Create a new notification template.                  Args:             event_typ, Delete template (soft delete for system templates)., Preview rendered template with sample data.                  Args:             t, Restore a previous version as active., Validate that template only uses valid variables., Render template with data.          H-16 FIX: All values are HTML-escaped to pre, Generate sample data for preview., Seed default templates for all event types.

### Community 247 - "Community 247"
Cohesion: 0.16
Nodes (17): _build_audit_trail(), _decompose_problem(), _generate_k_solutions_fallback(), _generate_k_solutions_llm(), maker_validator_node(), MAKER Validator Node — Group 6: K-Solution Validator for ALL Tiers  THE CRITICAL, Fallback K-solution generation when LLM is unavailable.      Creates K variation, Score a single candidate solution for confidence.      Uses the production scori (+9 more)

### Community 248 - "Community 248"
Cohesion: 0.12
Nodes (17): _count_fields(), create_initial_state(), get_total_field_count(), _max_float(), _merge_dicts(), _merge_lists(), ParwaGraphState — Shared State for the Multi-Agent LangGraph System  This TypedD, Count fields per group for documentation/validation. (+9 more)

### Community 249 - "Community 249"
Cohesion: 0.11
Nodes (10): Mini Parwa — Cheapest tier of the Parwa Variant Engine.  Pipeline: pii_check ->, MiniParwaTicketService, Mini Parwa Ticket Service — Ticket creation and solving service.  Provides conve, Re-run pipeline for an existing ticket.          BC-001: company_id is second pa, Just classify a query — no generation.          BC-001: company_id is first para, Get a stored ticket by ID.          BC-001: company_id is second parameter for v, Ticket creation and solving service for Mini Parwa.      Manages tickets in-memo, List all tickets for a company.          BC-001: company_id is first parameter. (+2 more)

### Community 250 - "Community 250"
Cohesion: 0.12
Nodes (14): CapacityAlert, get_transition_reason(), get_valid_transitions(), Shared GSD Module — Reusable GSD utilities for PARWA (F-053)  Provides: - GSD st, Record a state transition for a ticket.          Args:             company_id: T, A single recorded state transition., Suggest recovery actions when a ticket appears stuck.          Detects stuck sta, Duration spent in a specific state. (+6 more)

### Community 251 - "Community 251"
Cohesion: 0.18
Nodes (16): BusinessEmailOTP, Business Email OTP Model (Week 6 Day 10-11)  Stores OTP codes for business email, OTP codes for business email verification.          Flow:     1. User enters bus, check_business_email_verified(), _generate_otp(), _hash_otp(), _is_valid_business_email(), PARWA Business Email OTP Service (Week 6 Day 10-11)  Handles sending and verifyi (+8 more)

### Community 252 - "Community 252"
Cohesion: 0.11
Nodes (17): change_password(), get_company_profile(), get_company_settings(), get_team_members(), PARWA Company Service (F06)  Business logic for company profile, settings, team, Get company settings, auto-creating with defaults if needed.      BC-001: Filter, Update company settings.      Lists (prohibited_phrases, pii_patterns, custom_re, Change a user's password.      Verifies current password with bcrypt, hashes new (+9 more)

### Community 253 - "Community 253"
Cohesion: 0.14
Nodes (11): _get_db_session(), get_shadow_mode_service(), _parse_iso_to_datetime(), Shadow Mode Service: SHADOW→SUPERVISED→GRADUATED progression.  Implements the sa, Record a human review decision for a shadow mode result.          verdict must b, Get comparison history for a company.          Tries DB first; falls back to in-, Get or create the ShadowModeService singleton., Persist a config dict to the ShadowModeConfig DB table.          If a row with t (+3 more)

### Community 254 - "Community 254"
Cohesion: 0.16
Nodes (11): InjectionDefenseService, Orchestration + persistence layer for prompt injection defense.      Bridges syn, Initialize the service with a detector instance., Get recent injection attempts for a tenant.          BC-001: Scoped by company_i, Get injection statistics for a tenant.          BC-001: Scoped by company_id., Add a custom block pattern to a tenant's blocklist.          Patterns are stored, Remove a pattern from a tenant's blocklist.          BC-001: Scoped by company_i, Get all patterns in a tenant's blocklist.          BC-001: Scoped by company_id. (+3 more)

### Community 255 - "Community 255"
Cohesion: 0.14
Nodes (12): _provider_key(), ProviderState, Per-provider healing state within a variant., Get the healing state for a specific provider+model., Manually re-enable a disabled provider., Manually disable a provider., Record an external provider status update., Complete healing state for one variant within a company. (+4 more)

### Community 256 - "Community 256"
Cohesion: 0.20
Nodes (12): MonitoringStatusRequest, MonitoringStatusResponse, Request for system monitoring status., Response with monitoring status., MonitoringServer, PARWA MCP — Monitoring Server  Provides system health monitoring and alerting to, Return the monitoring REST router., Handle monitoring_get_status tool invocation. (+4 more)

### Community 257 - "Community 257"
Cohesion: 0.19
Nodes (12): Request to check SLA status., Response with SLA status., SLACheckRequest, SLACheckResponse, MCPServerBase, PARWA MCP — SLA Server  Provides SLA (Service Level Agreement) management tools., Handle sla_check tool invocation., Handle sla_get_policies tool invocation. (+4 more)

### Community 258 - "Community 258"
Cohesion: 0.19
Nodes (9): industries, Industry, IndustryKey, IndustrySelectorProps, QuantitySelectorProps, SelectedVariant, TotalSummaryProps, VariantCardProps (+1 more)

### Community 259 - "Community 259"
Cohesion: 0.11
Nodes (18): PaddleAdjustmentData, PaddleCreditData, PaddleCustomerData, PaddleDiscountData, PaddleEventData, PaddlePriceData, PaddleReportData, PaddleSubscriptionData (+10 more)

### Community 260 - "Community 260"
Cohesion: 0.12
Nodes (17): constant_time_compare(), decrypt_data(), derive_key(), encrypt_data(), generate_api_key(), generate_token(), hash_password(), PARWA Security Utilities (BC-011)  Password hashing (bcrypt cost factor 12) and (+9 more)

### Community 261 - "Community 261"
Cohesion: 0.13
Nodes (8): formatDate(), formatRelativeDate(), PRIORITY_COLORS, STATUS_COLORS, TicketCard(), TicketDetailPanel(), TicketRow(), VARIANT_COLORS

### Community 262 - "Community 262"
Cohesion: 0.11
Nodes (17): billingTickets, found, heavyTicket, heavyTickets, lightTicket, lightTickets, mediumTickets, msg (+9 more)

### Community 263 - "Community 263"
Cohesion: 0.11
Nodes (17): BillItem, BillSummaryData, ConversationStage, DemoCallData, DemoCallState, HandoffCardData, MessageType, OnboardingMessage (+9 more)

### Community 264 - "Community 264"
Cohesion: 0.13
Nodes (12): PARWA AI — Per-Provider Webhook Signature Verification  Provides a pluggable ver, Verify Shopify webhook signature (HMAC-SHA256).      Shopify sends the signature, Verify Twilio webhook signature.      Twilio signs the URL + sorted POST params, Verify Brevo webhook by IP allowlist.      Brevo doesn't use HMAC — they use IP-, Generic fallback verifier for custom/unregistered providers.      Attempts:, Register all built-in webhook verifiers., register(), _register_defaults() (+4 more)

### Community 265 - "Community 265"
Cohesion: 0.16
Nodes (9): ActivityCaptureMiddleware, PARWA Activity Capture Middleware  Automatically captures HTTP requests as Activ, Middleware that captures HTTP requests as ActivityLog entries.      This middlew, Capture a request as an ActivityLog entry.          This is a synchronous method, Determine the activity category from the route path., Determine the specific action from path and method., Determine the importance of this activity., Extract entity_type and entity_id from the URL path. (+1 more)

### Community 266 - "Community 266"
Cohesion: 0.15
Nodes (12): build_error_response(), ErrorHandlerMiddleware, get_correlation_id(), PARWA Error Handler Middleware (BC-012)  Provides: 1. Correlation ID generation, Handle Starlette HTTPException with structured JSON.          Converts Starlette, Handle unexpected exceptions.          Log stack trace internally, return generi, Build a structured error response (BC-012 format).      Utility function for bui, Convert HTTP status code to PARWA error code string.      Maps common status cod (+4 more)

### Community 267 - "Community 267"
Cohesion: 0.14
Nodes (15): AnalyticsEvent, _count_items(), get_funnel_metrics(), get_metrics(), get_recent_events(), get_sentiment_metrics(), PARWA Analytics Service (Week 9 — Event Tracking & Metrics)  Tracks user interac, Get aggregated analytics metrics.      Args:         company_id: Filter by compa (+7 more)

### Community 268 - "Community 268"
Cohesion: 0.12
Nodes (9): SMS Channel Service — Week 13 Day 5 (F-123: SMS Channel)  Handles the complete S, Update SMS delivery status from Twilio callback.          Args:             comp, List SMS conversations with pagination and filters.          Args:             c, Get messages for an SMS conversation.          Args:             conversation_id, Service for processing SMS messages and managing SMS conversations.      All met, Manually opt out a phone number from SMS.          BC-010: TCPA compliance — sup, Manually opt in a phone number back to SMS.          BC-010: TCPA compliance — s, Get TCPA consent status for a phone number.          Args:             company_i (+1 more)

### Community 269 - "Community 269"
Cohesion: 0.13
Nodes (12): _extract_chunks(), _generate_embedding(), process_knowledge_document(), PARWA Knowledge Document Processing Tasks  Celery tasks for asynchronous knowled, Reprocess all failed documents for a company.      GAP 6 FIX: Bulk retry mechani, Extract text chunks from document content.      In production, this would:     1, Generate vector embedding for text using the EmbeddingService.      Delegates to, Context manager for ensuring tenant isolation in async tasks.      GAP 2 FIX: Us (+4 more)

### Community 270 - "Community 270"
Cohesion: 0.15
Nodes (10): Check if enough time has elapsed to try half-open., Check if the dependency is available (circuit closed or half-open)., Record a successful call., Record a failed call., Manually open a circuit (for maintenance)., Manually close a circuit (for recovery)., Handle state transition with bookkeeping., Individual circuit breaker for one dependency.      State transitions:         C (+2 more)

### Community 271 - "Community 271"
Cohesion: 0.14
Nodes (10): DistributionResult, FailoverEvent, Select an instance using weighted round-robin.          Builds a weighted candid, Pick the instance with the lowest effective load.          Considers both active, Reroute a ticket from a failed/overloaded instance to another.          Selects, Outcome of a distribution (routing) decision.      Attributes:         instance_, Serialise to dictionary for API responses., Record of a failover event for analytics.      Attributes:         ticket_id: (+2 more)

### Community 272 - "Community 272"
Cohesion: 0.17
Nodes (5): CircuitBreaker, CircuitBreakerState, Per-feature circuit-breaker bookkeeping., Standard circuit-breaker pattern per feature key.      Transitions     ---------, True when the circuit allows traffic (CLOSED or HALF_OPEN).

### Community 273 - "Community 273"
Cohesion: 0.13
Nodes (10): HealingRule, Get the healing action audit trail for a company., Get currently active healing processes., AI Self-Healing Engine (SG-20).      Monitors AI engine health and autonomously, Clear all healing state and history. For testing., Create built-in healing rules., Set custom healing rules for a company., Enable or disable a specific healing rule. (+2 more)

### Community 274 - "Community 274"
Cohesion: 0.12
Nodes (17): AdjustmentCreatedEvent, AdjustmentUpdatedEvent, CreditCreatedEvent, CreditUpdatedEvent, CustomerDeletedEvent, DiscountCreatedEvent, PaddleEvent, PriceCreatedEvent (+9 more)

### Community 275 - "Community 275"
Cohesion: 0.15
Nodes (9): Anomaly, Check if error rate exceeds threshold for a service.          Returns Anomaly if, Check if response time exceeds threshold for a service.          Returns Anomaly, Check if resource usage exceeds threshold.          Args:             resource:, Check circuit breaker states and flag stale open circuits.          Returns list, Run all anomaly checks.          Returns list of all detected anomalies., Infer the appropriate healing action for a service., Run full health check and attempt self-healing for any issues found.          Re (+1 more)

### Community 277 - "Community 277"
Cohesion: 0.12
Nodes (16): CallDirection, CallHistoryParams, CallHistoryResponse, CallStatus, CreateVoiceConfigRequest, InitiateCallRequest, InitiateCallResponse, ListCallsParams (+8 more)

### Community 278 - "Community 278"
Cohesion: 0.13
Nodes (11): _classify_scope(), GSTConfig, GSTOption, GSTProcessor, Immutable configuration for GST processing (BC-001).      Attributes:         co, A single option generated for the strategic decision.      Attributes:         o, Serialize option to dictionary., Deterministic Guided Sequential Thinking processor (F-143).      Uses pattern ma (+3 more)

### Community 279 - "Community 279"
Cohesion: 0.13
Nodes (15): get_company_id(), get_current_company(), get_current_user(), get_tenant_context(), optional_user(), PARWA Auth Dependencies (BC-011)  FastAPI dependencies for route-level authentic, Factory dependency that checks user role.      Usage:         @router.get("/admi, Dependency that requires platform admin access.      Platform admins can manage (+7 more)

### Community 280 - "Community 280"
Cohesion: 0.18
Nodes (14): CircuitState, Circuit Breaker Manager (Phase 6: Production Hardening)  Manages circuit breaker, Circuit breaker states., Self-Healing Periodic Tasks (Phase 6: Production Hardening)  Scheduled tasks exe, Run anomaly detection and log results.      Lightweight check that only detects, Check circuit breaker states and reset stale ones.      Finds circuit breakers t, Run an async coroutine from a sync Celery task.      Handles both cases: already, Clean up stale Redis locks.      Finds Redis lock keys that have no TTL (potenti (+6 more)

### Community 281 - "Community 281"
Cohesion: 0.13
Nodes (15): ActivityEventPayload, AIEventPayload, ApprovalEventPayload, get_event_registry(), NotificationEventPayload, PARWA Event Type Registry (BC-005)  Defines all event types used in the PARWA re, Get the singleton EventRegistry instance., Reset the registry singleton (for testing only). (+7 more)

### Community 282 - "Community 282"
Cohesion: 0.17
Nodes (15): _check_fifty_mistake_rule(), _persist_gsd_state(), _push_jarvis_feed(), State Update Node — Group 11: Final State Persistence  Runs at the END of every, Persist the GSD (Guided Support Dialogue) state to database.      Uses the produ, Create or update the support ticket for this conversation.      If ticket_id is, Push state summary to Jarvis Command Center awareness feed.      Allows Jarvis t, Increment metrics counters for this tenant and flow.      Tracks conversation co (+7 more)

### Community 283 - "Community 283"
Cohesion: 0.13
Nodes (9): ParwaHighTicketService, High Parwa Ticket Service — Ticket creation and solving service.  Provides conve, Re-run pipeline for an existing ticket.          BC-001: company_id is second pa, Just classify a query — no generation.          BC-001: company_id is first para, Get a stored ticket by ID.          BC-001: company_id is second parameter for v, Ticket creation and solving service for High Parwa.      Manages tickets in-memo, List all tickets for a company.          BC-001: company_id is first parameter., Initialize the ticket service. (+1 more)

### Community 284 - "Community 284"
Cohesion: 0.13
Nodes (9): ParwaTicketService, Pro Parwa Ticket Service — Ticket creation and solving service.  Provides conven, Re-run pipeline for an existing ticket.          BC-001: company_id is second pa, Just classify a query — no generation.          BC-001: company_id is first para, Ticket creation and solving service for Pro Parwa.      Manages tickets in-memor, Get a stored ticket by ID.          BC-001: company_id is second parameter for v, List all tickets for a company.          BC-001: company_id is first parameter., Initialize the ticket service. (+1 more)

### Community 285 - "Community 285"
Cohesion: 0.15
Nodes (15): get_tier_metadata(), industry_label_to_enum(), Variant Tier Mapper: Maps onboarding variant selections to pipeline tiers.  The, Map a frontend variant_id to a backend pipeline tier.      Args:         variant, Map a frontend variant display name to a backend pipeline tier.      Handles nam, Map a frontend industry label to the backend enum value.      Handles various ca, Map a backend pipeline tier to a frontend variant_id.      Args:         tier: B, Resolve the highest variant tier from onboarding context data.      Priority: (+7 more)

### Community 286 - "Community 286"
Cohesion: 0.13
Nodes (8): _deterministic_pseudo_embedding(), generate_embedding_sync(), PARWA Embedding Service (F-082) — Day 0 Prerequisite P1+P2  Generates vector emb, Generate a deterministic pseudo-embedding using SHA-256 hash.          Last-reso, Lazily load API key from settings (BC-008 safe)., Generate an embedding for a single text string.          Uses Google AI Studio t, Generate embeddings for multiple texts in a single API call.          Uses Googl, Generate a single embedding synchronously using Google AI Studio.      Standalon

### Community 287 - "Community 287"
Cohesion: 0.13
Nodes (9): PromptTemplate, Per-Intent Prompt Templates (SG-25)  48 specialized prompt templates organized b, Single prompt template for an intent × response_type combination., Get few-shot examples for the template., Get output schema for the template., Get tone instructions based on intent and response type., Determine which variants can use this template., Build a single template for intent × response_type. (+1 more)

### Community 288 - "Community 288"
Cohesion: 0.17
Nodes (15): apply_command_feedback(), apply_command_feedback_sync(), _generate_feedback_id(), get_feedback_history(), _map_command_to_pipeline_updates(), PARWA Jarvis Pipeline Feedback Handler (Phase 4)  Handles the feedback loop from, Synchronous wrapper for apply_command_feedback.      Used by the command graph's, Map a Jarvis command result to ParwaGraphState field updates.      This is where (+7 more)

### Community 289 - "Community 289"
Cohesion: 0.17
Nodes (15): build_event_payload(), dispatch_alert_event(), dispatch_event(), dispatch_state_event(), dispatch_tick_event(), get_redis_channel(), PARWA Jarvis Event Dispatcher (Phase 2.4)  Dispatches real-time events when the, Dispatch an alert-related event.      Args:         company_id: Company ID for B (+7 more)

### Community 290 - "Community 290"
Cohesion: 0.14
Nodes (15): get_function_categories(), get_function_count_by_safety(), get_function_definitions(), get_function_metadata(), get_function_names(), get_functions_by_category(), get_safety_level(), PARWA Jarvis Function Registry — LLM Function Calling Definitions  The complete (+7 more)

### Community 291 - "Community 291"
Cohesion: 0.13
Nodes (15): _exec_call_action(), _exec_demo_action(), _exec_guide_action(), _exec_noop(), _exec_sell_action(), _execute_action(), onboarding_executor_node(), PARWA Onboarding Executor Node  The Executor Node takes the specialist agent's d (+7 more)

### Community 292 - "Community 292"
Cohesion: 0.17
Nodes (15): _extract_customer_data(), _extract_order_data(), handle_customer_created(), handle_order_created(), handle_shopify_event(), Shopify Webhook Handler (BC-003, GAP 1.5)  Handles Shopify webhook events: - ord, Validate that required fields exist in extracted data.      Returns:         Err, Handle Shopify orders.create event.      Args:         event: Full event dict wi (+7 more)

### Community 293 - "Community 293"
Cohesion: 0.13
Nodes (10): EscalationConfig, _higher_severity(), Check if company-level rate limit has been reached.          Counts escalations, Per-company escalation configuration.      Controls global escalation behaviour, Return the higher of two severity values., Get escalation configuration for a company.          Falls back to a default Esc, Get all active (enabled) escalation rules sorted by priority.          Args:, Check if escalation should trigger given an EscalationContext.          Evaluate (+2 more)

### Community 294 - "Community 294"
Cohesion: 0.17
Nodes (9): FrustrationDetector, Detects frustration beyond simple lexicon matching.      Uses patterns: ALL CAPS, Return frustration score from 0 to 100., Score based on frustration word presence (0-50 pts).          G9-GAP-03 FIX: Use, Detect ALL CAPS words (0-10 pts)., Score exclamation mark density (0-15 pts)., Detect repeated words (0-10 pts)., Score question mark density (0-10 pts). (+1 more)

### Community 295 - "Community 295"
Cohesion: 0.20
Nodes (10): Result of a voice pipeline step., Core voice demo pipeline — session lifecycle, voice I/O, paywall.      Thread-sa, Get session by id, returning None if missing or expired., Full voice input pipeline: STT → AI → response., Generate TTS audio for a text response., STT placeholder — simulates transcription., AI pipeline placeholder — simulates intent + response generation., TTS placeholder — simulates speech synthesis. (+2 more)

### Community 296 - "Community 296"
Cohesion: 0.16
Nodes (13): CostBudget, DashboardPage(), FetchState, formatCurrency(), formatHours(), formatNumber(), formatPercent(), Icons (+5 more)

### Community 297 - "Community 297"
Cohesion: 0.23
Nodes (13): buildProtectedHeader(), getSecret(), getSigningKey(), getVerificationKey(), JWT_ALGORITHM, JWTPayload, loadRSAPrivateKey(), loadRSAPublicKey() (+5 more)

### Community 298 - "Community 298"
Cohesion: 0.13
Nodes (12): ALERT_TYPE_COLORS, HEALTH_STATUS_COLORS, HEALTH_STATUS_DOT_COLORS, HEALTH_STATUS_LABELS, HealthStatus, QueueMetrics, SERVICE_LABELS, ServiceHealth (+4 more)

### Community 299 - "Community 299"
Cohesion: 0.23
Nodes (11): AnalyticsQueryRequest, AnalyticsQueryResponse, Request for analytics data., Response with analytics data., AnalyticsServer, PARWA MCP — Analytics Server  Provides analytics and reporting tools. Exposes cu, Handle analytics_query tool invocation., Handle analytics_get_dashboard tool invocation. (+3 more)

### Community 300 - "Community 300"
Cohesion: 0.23
Nodes (11): ComplianceCheckRequest, ComplianceCheckResponse, Request to run a compliance check., Response from a compliance check., ComplianceServer, PARWA MCP — Compliance Server  Provides compliance checking and data governance, Handle compliance_check tool invocation., Handle compliance_scan_pii tool invocation. (+3 more)

### Community 301 - "Community 301"
Cohesion: 0.23
Nodes (11): NotificationSendRequest, NotificationSendResponse, Request to send a notification., Response from sending a notification., NotificationServer, PARWA MCP — Notification Server  Provides notification delivery tools. Supports, Handle notification_send tool invocation., Handle notification_get_preferences tool invocation. (+3 more)

### Community 302 - "Community 302"
Cohesion: 0.14
Nodes (11): BrandVoiceConfig, _now_utc(), Generate dynamic response guidelines based on brand voice         and customer s, Get a default brand voice config for an industry.          Args:             ind, Retrieve config from Redis cache., Retrieve config from database.          Stub implementation — to be wired to the, Return current UTC datetime., Get brand voice config for a company.          Resolution order:           1. Re (+3 more)

### Community 303 - "Community 303"
Cohesion: 0.13
Nodes (16): add_custom_quick_command(), _handler_add_agents(), _handler_call_customer(), _handler_check_system_health(), _handler_disable_last_rule(), _handler_show_errors(), Add a custom quick command preset for this tenant.      Custom presets are store, Remove a custom quick command preset.      Only custom commands (added via add_c (+8 more)

### Community 304 - "Community 304"
Cohesion: 0.17
Nodes (7): RateLimitService, Advanced rate limit service with per-endpoint-category limits.      In-memory fa, Classify a request path into an endpoint category., Fetch Redis TIME and compute offset for sync use.          F-018: Use Redis serv, Extract identifier based on category scope., Extract phone number from request body for per-phone rate limiting., Extract client IP using the shared get_client_ip utility.          H-06: Uses th

### Community 305 - "Community 305"
Cohesion: 0.13
Nodes (8): Look up an SMS message by Twilio MessageSid.          BC-003: Idempotency check., Check inbound rate limit to prevent SMS spam/flood.          Args:             c, Send SMS via Twilio API.          Args:             config: SMS channel config w, Schedule an auto-reply message via Celery.          Args:             company_id, Send opt-in confirmation message.          Args:             company_id: Tenant, Decrypt a credential value (BC-011).          Args:             encrypted: Encry, Process an inbound SMS from Twilio webhook.          Full pipeline:         1. L, Parse comma-separated keyword string to lowercase list.          Args:

### Community 308 - "Community 308"
Cohesion: 0.13
Nodes (15): AuthContextType, AuthResponse, AuthState, EmailCheckResponse, ForgotPasswordRequest, GoogleAuthRequest, LoginRequest, MessageResponse (+7 more)

### Community 309 - "Community 309"
Cohesion: 0.15
Nodes (9): IntentResult, AI-Powered Multi-Label Intent Classification Engine (F-062)  Classifies ticket t, Classify text into primary + secondary intents using keywords., Classify text into primary + secondary intents.          GAP-008 FIX: Empty/whit, Use Smart Router for AI-powered classification., Parse Smart Router response into IntentResult., GAP-008: Return safe default for empty/invalid input., Output of intent classification. (+1 more)

### Community 310 - "Community 310"
Cohesion: 0.15
Nodes (11): parse(), parse_brevo(), parse_generic(), parse_paddle(), PARWA AI — Generic Webhook Parser Registry  Provides a pluggable parser system f, Generic fallback parser for custom/unregistered providers.      Attempts common, Register all built-in webhook parsers., Parse Paddle webhook payload. (+3 more)

### Community 311 - "Community 311"
Cohesion: 0.15
Nodes (10): get_voice_demo_engine(), Voice Demo System (F-008)  Gated $1 paywall for voice AI demo experience.  Visit, A single voice demo session with paywall state., Create a new demo session (requires payment before activation)., Return the module-level ``VoiceDemoEngine`` singleton., Reset the singleton (used in tests)., reset_voice_demo_engine(), _valid_email() (+2 more)

### Community 312 - "Community 312"
Cohesion: 0.24
Nodes (14): VerificationToken, create_verification_token(), _generate_token(), _hash_token(), PARWA Verification Service (F-012)  Business logic for email verification flow., Verify an email using a token.      F-012: Validates token exists, not expired,, Resend a verification email.      F-012: Rate limited to 3 per email per hour., Send verification email after registration.      Called by register_user in auth (+6 more)

### Community 313 - "Community 313"
Cohesion: 0.13
Nodes (8): LoadAwareDistributor, Retrieve recent failover events for a company.          Args:             compan, Get detailed information about a single instance.          Args:             com, Get all sticky sessions pinned to a specific instance.          Args:, Reset the round-robin counter for a company+variant combination.          Useful, Remove all data for a company (useful for cleanup / testing).          Removes a, Distributes workload across multiple instances of the same variant.      Impleme, Remove an instance from the registry and clean up its state.          Clears all

### Community 314 - "Community 314"
Cohesion: 0.16
Nodes (6): FeatureFlagBackend, InMemoryFeatureFlagBackend, Pluggable backend for feature-flag reads / writes., Redis-backed implementation., In-process dict-backed implementation (for tests / single-node)., RedisFeatureFlagBackend

### Community 315 - "Community 315"
Cohesion: 0.14
Nodes (8): BaseAssigner, HybridAssigner, Abstract base for all ticket assignment strategies.      Subclasses must impleme, Deterministic round-robin assignment with priority-aware escalation.      Behavi, Return a shallow copy of the internal assignment log., Clear round-robin counters and the log., Score-based first; falls back to rule-based when the best score     drops below, RuleBasedAssigner

### Community 316 - "Community 316"
Cohesion: 0.13
Nodes (10): SMS Channel Models — Week 13 Day 5 (F-123: SMS Channel)  Tables: - SMSMessage: I, Serialize SMS message for API responses., SMS conversation thread mapping.      Maps a unique phone number pair (customer, Serialize SMS conversation for API responses., Per-company Twilio SMS configuration.      Stores encrypted Twilio credentials a, Serialize SMS config for API responses (no secrets).          H-17 FIX: twilio_a, SMS message tracking record.      One row per SMS message (inbound or outbound), SMSChannelConfig (+2 more)

### Community 317 - "Community 317"
Cohesion: 0.13
Nodes (10): Voice Channel Models — Voice Call API  Tables: - VoiceCall: Tracks every voice c, Serialize voice call for API responses., Voice conversation thread mapping.      Maps a unique phone number pair (custome, Serialize voice conversation for API responses., Per-company Twilio voice configuration.      Stores encrypted Twilio credentials, Serialize voice config for API responses (no secrets).          H-17 FIX: twilio, Voice call tracking record.      One row per voice call (inbound or outbound) wi, VoiceCall (+2 more)

### Community 318 - "Community 318"
Cohesion: 0.17
Nodes (13): Action, ActionType, actionTypes, addToRemoveQueue(), dispatch(), genId(), listeners, memoryState (+5 more)

### Community 319 - "Community 319"
Cohesion: 0.23
Nodes (10): ChatServer, PARWA MCP — Chat Server  Provides live chat messaging tools. Supports multi-chan, Handle chat_send_message tool invocation., Handle chat_get_conversation tool invocation., MCP sub-server for chat communication channels., Return the chat REST router., ChatMessageRequest, ChatMessageResponse (+2 more)

### Community 320 - "Community 320"
Cohesion: 0.14
Nodes (6): ACCEPTED_TYPES, DocStatus, formatFileSize(), KnowledgeDocument, KnowledgePage(), MOCK_DOCUMENTS

### Community 321 - "Community 321"
Cohesion: 0.23
Nodes (10): RAGServer, PARWA MCP — RAG Server  Provides Retrieval-Augmented Generation query tools. Rou, Handle rag_query tool invocation.          Placeholder: returns mock chunks. In, Handle rag_rerank tool invocation., MCP sub-server for RAG (Retrieval-Augmented Generation) queries., Return the RAG REST router., RAGQueryRequest, RAGQueryResult (+2 more)

### Community 322 - "Community 322"
Cohesion: 0.17
Nodes (10): ComparisonTable(), ComparisonTableProps, EnableShadowModeDialog(), EnableShadowModeDialogProps, variantOptions, ShadowModeMetricsGrid(), ShadowModeMetricsGridProps, phaseConfig (+2 more)

### Community 323 - "Community 323"
Cohesion: 0.20
Nodes (13): check_email_status(), get_bounce_digest(), get_bounce_stats(), _get_db(), list_bounces(), Bounce & Complaint API Endpoints — Week 13 Day 3 (F-124)  Provides tenant-level, Get bounce and complaint statistics for the tenant.      R-01: Now requires JWT, Get deliverability digest for the tenant.      R-01: Now requires JWT authentica (+5 more)

### Community 324 - "Community 324"
Cohesion: 0.20
Nodes (13): create_chat_session(), _error_response(), get_chat_health(), get_chat_history(), PARWA Jarvis Chat API Router — The Natural Language Interface  This is the API t, Check the health of the Jarvis chat system.      Returns status, available funct, Send a message to Jarvis and get a natural response.      This is the main inter, Get paginated chat history for a session.      Returns messages in chronological (+5 more)

### Community 325 - "Community 325"
Cohesion: 0.16
Nodes (13): clear_tenant_context(), get_tenant_context(), is_tenant_bypassed(), CROSS-17: Set PostgreSQL RLS tenant context on connection checkout.  This module, Register SQLAlchemy event hooks for RLS tenant context.      Call **once** when, Set the current tenant ID for this thread.      In the main application, prefer, Get the current tenant ID for this thread.      First tries ``app.core.tenant_co, Clear the current tenant context. (+5 more)

### Community 326 - "Community 326"
Cohesion: 0.20
Nodes (13): _build_technique_stack(), _fallback_classify_intent(), _fallback_estimate_complexity(), _fallback_extract_signals(), Router Agent Node — Group 3 (Third node in the pipeline)  Classifies the user's, Heuristic complexity estimation based on message length,     sentence count, and, Select the LLM model tier based on complexity, sentiment,     and variant_tier., Build the ordered technique stack based on variant_tier access,     intent, and (+5 more)

### Community 327 - "Community 327"
Cohesion: 0.19
Nodes (10): BaseDomainAgent, complaint_agent_node(), ComplaintAgent, is_available_for_tier(), Complaint Agent Node — Group 4 Domain Agent (Complaints / Dissatisfaction / Nega, Classify the complaint type and severity.          Analyzes the message, sentime, Determine the appropriate service recovery action.          Based on complaint s, Add complaint-specific fields to the state update.          Extends the base sta (+2 more)

### Community 328 - "Community 328"
Cohesion: 0.16
Nodes (9): escalation_agent_node(), EscalationAgent, Escalation Agent Node — Group 5 Domain Agent (Escalation / Human handoff)  Speci, Add escalation-specific fields to the state update.          Ensures proposed_ac, Retrieve graceful escalation context from the         app.core.graceful_escalati, Template-based escalation response fallback.          Produces an empathetic esc, Escalation Agent Node — LangGraph agent node.      Handles escalation requests,, Escalation Domain Agent — handles escalation to human agents,     manager reques (+1 more)

### Community 329 - "Community 329"
Cohesion: 0.20
Nodes (13): _check_brand_voice(), _check_guardrails_engine(), _check_hallucination(), _check_loopholes(), _check_prompt_injection(), guardrails_node(), Guardrails Node — Group 9: Safety & Compliance Checks  Implements multi-layer sa, Run hallucination detection on the response.      Checks for fabricated informat (+5 more)

### Community 330 - "Community 330"
Cohesion: 0.19
Nodes (12): _normalize_path(), PARWA Prometheus Metrics Registry (Day 21, BC-012)  Provides a lightweight Prome, Record an observed value., Record an HTTP request metric.      Path is normalized to prevent cardinality ex, Record a Celery task execution metric.      Args:         task_name: Name of the, Record a database query duration.      Args:         duration: Query duration in, Record a Redis command metric.      Args:         command: Redis command type (G, Normalize a URL path to prevent metric cardinality explosion.      Replaces UUID (+4 more)

### Community 331 - "Community 331"
Cohesion: 0.15
Nodes (13): _get_brevo_ips(), HMAC Signature Verification (BC-011, BC-003)  Provides webhook signature verific, Verify Twilio webhook signature (RFC 5849).      Twilio concatenates the URL and, Verify Shopify webhook HMAC-SHA256 signature.      Shopify signs webhook payload, Verify client IP is in Brevo allowlist.      Brevo uses IP allowlisting instead, Verify webhook timestamp is fresh (within 5 minutes).      Rejects webhooks whos, Get Brevo IP ranges from environment or defaults.      L-06 FIX: Makes Brevo IP, Verify Paddle webhook HMAC-SHA256 signature.      Paddle signs webhook payloads (+5 more)

### Community 332 - "Community 332"
Cohesion: 0.19
Nodes (11): _add_casual_touches(), _expand_contractions(), _normalize_text(), _normalize_word(), ProhibitedWordCheck, PARWA Brand Voice Configuration Service (Week 9, Day 8).  Per-company brand voic, Normalize text to catch l33t-speak and emoji variants.      Steps:       1. Lowe, Apply brand voice to a response text.          Applies:           1. Greeting te (+3 more)

### Community 333 - "Community 333"
Cohesion: 0.18
Nodes (13): _generate_email(), generate_fake_requests(), get_available_categories(), get_template_count(), _map_category(), _pick_unique_name(), PARWA Fake Request Generator — Simulated Customer Support Requests  Generates re, Generate realistic fake customer support requests.      These are NOT real custo (+5 more)

### Community 334 - "Community 334"
Cohesion: 0.15
Nodes (13): _analyze_state_for_suggestions(), generate_co_pilot_suggestion(), _handler_escalate_urgent(), _handler_export_report(), _handler_show_ticket_details(), prune_old_commands(), PARWA Jarvis Command Service (Phase 3 — The Command Layer)  The service that mak, Generate a co-pilot suggestion based on current awareness state.      When a use (+5 more)

### Community 335 - "Community 335"
Cohesion: 0.19
Nodes (13): get_proactive_message_content(), inject_proactive_alert(), inject_tick_summary(), rate_limit_check(), PARWA Jarvis Proactive Alert Injector (Phase 2.4)  The bridge that makes Jarvis, Inject a proactive alert as a message into the CC chat session.      This is the, Inject all eligible alerts from a tick into the CC chat.      Called after run_a, Check if a proactive injection is rate-limited.      Args:         session_conte (+5 more)

### Community 336 - "Community 336"
Cohesion: 0.20
Nodes (13): awareness_agent_node(), _detect_concerns(), _detect_intent(), _detect_sentiment(), _detect_stage_transition(), _detect_topics(), PARWA Onboarding Awareness Agent Node  The Awareness Agent enriches the onboardi, Detect concerns from user message. (+5 more)

### Community 337 - "Community 337"
Cohesion: 0.18
Nodes (5): RateLimitResult, PARWA Advanced Rate Limit Service (F-018)  Per-endpoint-category rate limiting w, Result of a rate limit check., Check if a request is allowed under rate limits.          F-018: Uses Redis TIME, Reset lockout and failure count.

### Community 338 - "Community 338"
Cohesion: 0.14
Nodes (13): check_all_usage_warnings(), daily_overage_charge(), invoice_sync(), process_all_overages(), PARWA Billing Tasks (Day 22, Day 23, BC-004, BC-002)  Celery tasks for billing o, Process overages for all active companies.      This is the main task called by, Sync invoices from Paddle billing provider.      F-023: Invoice History      Thi, Check subscription status and plan limits.      This task verifies the subscript (+5 more)

### Community 339 - "Community 339"
Cohesion: 0.15
Nodes (13): dispatch_event(), get_handler(), get_registered_providers(), get_supported_event_types(), Webhook Provider Handler Registry (BC-003, GAP 1.5)  Central registry for webhoo, Check if an event type is supported for a provider.      Args:         provider:, Get supported event types for a provider.      Args:         provider: Provider, Get all providers with registered handlers.      Returns:         List of provid (+5 more)

### Community 340 - "Community 340"
Cohesion: 0.14
Nodes (8): CallLifecycleManager, Get past lifecycle snapshots for a company, optionally         filtered by ticke, Register a callback for lifecycle events.          The callback will be invoked, Remove a previously registered lifecycle event listener.          Args:, Clear all data for a company (lifecycles, config, history).          Removes all, Execution Lifecycle Management for AI agent calls.      Tracks the full lifecycl, Initialize the lifecycle manager with empty state., Set per-company lifecycle configuration.          Overrides any previously set c

### Community 341 - "Community 341"
Cohesion: 0.18
Nodes (8): End-to-end optimized response via the DSPy pipeline.          Steps:         1., Stub DSPy module for fallback when DSPy is not installed., Create a DSPy module for a task type.          Args:             task_type: Task, Execute a DSPy module with given inputs.          Falls back to stub execution i, Bridge DSPy output back to PARWA ConversationState.          Maps DSPy output fi, Record an execution metric., _stub_execute(), StubModule

### Community 342 - "Community 342"
Cohesion: 0.16
Nodes (8): _now_utc(), Mark an escalation as resolved.          Updates the escalation status to 'resol, Dismiss an escalation as not needed.          Marks the escalation as resolved w, Reassign an escalation to a different agent or team.          Args:, Log a notification dispatch event.          Appends a notification entry to the, Emit an event to all registered listeners.          Each listener is called with, Return current UTC timestamp as ISO-8601 string (BC-012)., Mark an escalation as acknowledged.          Updates the escalation status to 'a

### Community 343 - "Community 343"
Cohesion: 0.18
Nodes (8): _count_failures(), Determine whether failures exceed the variant threshold         and human handof, Build a comprehensive error context dict from all recorded         failures for, Get the effective degradation config for a company+variant.          Checks for, Get the current degradation configuration for a company         and variant as a, Get a comprehensive summary of a pipeline's state.          Useful for logging,, Build actionable recommendations based on pipeline state.          Provides guid, Count the number of real failures (excluding SKIPPED).      Only FAILED, TIMEOUT

### Community 344 - "Community 344"
Cohesion: 0.19
Nodes (9): DashboardHeader(), DashboardHeaderProps, DateRangeSelector(), DateRangeSelectorProps, PresetRange, presetRanges, MakeCallDialog(), MakeCallDialogProps (+1 more)

### Community 345 - "Community 345"
Cohesion: 0.14
Nodes (10): Approval, APPROVAL_STATUS_COLORS, APPROVAL_STATUS_LABELS, APPROVAL_TYPE_COLORS, APPROVAL_TYPE_LABELS, ApprovalState, ApprovalStatus, ApprovalType (+2 more)

### Community 346 - "Community 346"
Cohesion: 0.21
Nodes (10): extractToken(), getSecret(), getVerificationKey(), JWT_ALGORITHM, loadRSAPublicKey(), requireAuth(), VerifiedUser, verifyAuth() (+2 more)

### Community 347 - "Community 347"
Cohesion: 0.27
Nodes (13): apiCall(), createOrResumeSession(), createPayment(), executeHandoff(), getDemoPackStatus(), getHistory(), getSession(), purchaseDemoPack() (+5 more)

### Community 348 - "Community 348"
Cohesion: 0.22
Nodes (5): APIKeyAuthMiddleware, Check if DB-backed validation is available., Validate key against database.          M-07: Uses a short-lived session via con, Fallback: in-memory key lookup., Middleware that authenticates requests via API key.      - Extracts API key from

### Community 349 - "Community 349"
Cohesion: 0.18
Nodes (10): BENCHMARKS, fmtMoney(), fmtNum(), getRecommendedModel(), INDUSTRIES, ModelComparison, PARWA_MODELS, ParwaModel (+2 more)

### Community 350 - "Community 350"
Cohesion: 0.15
Nodes (14): cancel_command(), _dispatch_handler(), execute_command(), _get_command(), _merge_metadata(), Cancel a command that is in received/parsing/parsed status.      Only commands t, Dispatch a parsed command to the appropriate handler.      Each handler is indep, Merge new data into existing metadata JSON.      Args:         existing_json: Cu (+6 more)

### Community 351 - "Community 351"
Cohesion: 0.14
Nodes (14): build_context_aware_welcome(), check_message_limit(), create_or_resume_session(), _get_default_welcome(), get_demo_pack_status(), _maybe_reset_daily_counter(), Check and enforce message limits.      Returns:         Tuple of (limit, remaini, Reset daily counter if date has changed. (+6 more)

### Community 352 - "Community 352"
Cohesion: 0.19
Nodes (12): CarouselApi, CarouselContent(), CarouselContext, CarouselContextProps, CarouselItem(), CarouselNext(), CarouselOptions, CarouselPlugin (+4 more)

### Community 353 - "Community 353"
Cohesion: 0.19
Nodes (7): AgentCard(), cardHover, containerVariants, formatLastActive(), itemVariants, tierBadgeStyle(), tierLabel()

### Community 354 - "Community 354"
Cohesion: 0.24
Nodes (9): _accuracy_score(), _conciseness_score(), DSPyConfig, DSPy Framework Integration (F-061)  Provides DSPy module wrappers for PARWA tech, Evaluate a DSPy module against a test set.          Runs the *module* on each te, Composite metric for DSPy optimization.          Evaluates relevance, accuracy,, Per-tenant DSPy configuration., _relevance_score() (+1 more)

### Community 355 - "Community 355"
Cohesion: 0.21
Nodes (9): is_available_for_tier(), Refund Agent Node — Group 4 Domain Agent (Refund / Returns / Cancellations)  Spe, Look up order details using the order_tool.          Uses app.core.react_tools.o, Check refund eligibility based on order details and policy.          Applies the, Add refund-specific fields to the state update.          Extends the base state, Refund Agent Node — LangGraph agent node.      Handles refund processing, return, Refund Domain Agent — handles refund processing, returns,     and cancellation r, refund_agent_node() (+1 more)

### Community 356 - "Community 356"
Cohesion: 0.26
Nodes (10): create_from_config(), create_with_credentials(), get(), list_by_category(), _load_credentials(), _normalise_category(), ProviderRegistry, PARWA AI — Provider Registry & Factory  The registry keeps a global mapping of ` (+2 more)

### Community 357 - "Community 357"
Cohesion: 0.22
Nodes (10): _check_limit(), _decode_company_id_from_jwt(), _extract_company_id(), _get_limit_type(), PARWA Variant Check Middleware (BC-001 / BC-007)  Pure ASGI middleware that enfo, Process a single ASGI HTTP request through the middleware., Pure ASGI middleware for variant resource-limit enforcement.      Inspects every, Wrap an ASGI *app* with variant-limit checking.          Args:             app: (+2 more)

### Community 358 - "Community 358"
Cohesion: 0.15
Nodes (12): Config, CreditDeletedEvent, CustomerCreatedEvent, CustomerUpdatedEvent, PaddleSubscriptionItem, PaddleTransactionDetails, Paddle Webhook Event Schemas  Pydantic models for all Paddle webhook events (25+, Transaction details from Paddle. (+4 more)

### Community 359 - "Community 359"
Cohesion: 0.21
Nodes (9): _check_body(), _check_headers(), _check_subject(), _extract_return_date(), _match_pattern(), OOO Detection Service — Week 13 Day 3 (F-122)  Detects Out-of-Office (OOO) auto-, Check sender's OOO profile for frequency-based detection.          If the same s, Detect if an email is an Out-of-Office auto-response.          Checks in order: (+1 more)

### Community 360 - "Community 360"
Cohesion: 0.17
Nodes (6): BaseSettings, get_settings(), MCPSettings, PARWA MCP Server Configuration  Loads MCP-specific configuration from environmen, Get MCP settings singleton., MCP Server settings loaded from environment variables.

### Community 361 - "Community 361"
Cohesion: 0.18
Nodes (7): CrossVariantInteractionService, Check for all active (unresolved) conflicts for a customer.          Returns a l, Manages cross-variant interactions for multi-variant companies.      Provides th, Retrieve the confidence history for a ticket.          BC-001: company_id is fir, Build the canonical storage key for a handoff., Retrieve the handoff context for a ticket and target variant.          Returns t, Mark that the target variant has received and processed         the handoff cont

### Community 362 - "Community 362"
Cohesion: 0.18
Nodes (7): EventRegistry, Registry of all event types. Singleton via get_event_registry()., Register a new event type. Raises ValueError if duplicate., Get all event types in a category., Get all registered event types., Get all registered event type strings., Register all core PARWA event types (22 events).

### Community 363 - "Community 363"
Cohesion: 0.15
Nodes (8): DistributionStats, List all registered instances for a company.          Args:             company_, Load overview across all instances for a company.          Returns a summary dic, Dynamically adjust instance weights based on current load.          Algorithm:, Get routing statistics for a company.          Includes sticky session hit rate,, Aggregated routing statistics for a company.      Tracks how many times each rou, Serialise to dictionary for API responses., _utc_now_iso()

### Community 364 - "Community 364"
Cohesion: 0.18
Nodes (7): _build_litellm_model_name(), Execute LLM call via LiteLLM with retry + fallback (sync).          BC-001: comp, Make a synchronous LLM call via LiteLLM.          Uses LiteLLM's unified API whi, Make an async LLM call via LiteLLM.          BC-007: All AI interaction through, Get API key for a provider from environment variables or Settings.          Chec, Call the appropriate LLM provider API.          Sync wrapper -- runs async call, Execute an LLM API call using the routing decision.          Handles retry + fal

### Community 365 - "Community 365"
Cohesion: 0.19
Nodes (9): ChatHeader(), ChatHeaderProps, STAGE_LABELS, ChatInput(), ChatInputProps, ErrorBanner(), ErrorBannerProps, JarvisChat() (+1 more)

### Community 366 - "Community 366"
Cohesion: 0.17
Nodes (12): cancellationPoints, ChannelInfo, commonFeaturesByVariant, hexToRgba(), industries, Industry, IndustryConfig, ModelsPage() (+4 more)

### Community 367 - "Community 367"
Cohesion: 0.19
Nodes (10): BENCHMARKS, fmtMoney(), fmtNum(), getRecommendedModel(), INDUSTRIES, ModelComparison, PARWA_MODELS, ParwaModel (+2 more)

### Community 369 - "Community 369"
Cohesion: 0.15
Nodes (12): ComparisonHistoryResponse, DisableShadowModeRequest, EnableShadowModeRequest, HumanReviewRequest, HumanVerdict, PromoteShadowModeRequest, ShadowComparison, ShadowModeApiResponse (+4 more)

### Community 370 - "Community 370"
Cohesion: 0.23
Nodes (11): cleanup_old_events(), _event_key(), get_buffer_stats(), get_events_since(), PARWA Event Buffer (BC-005, BC-001)  Provides a Redis-based event buffer for Soc, Fetch events from the buffer since a given timestamp.      Used by the reconnect, Remove events older than 24 hours from the buffer.      BC-005: Event buffer ret, Get statistics about the event buffer for a tenant.      Useful for monitoring a (+3 more)

### Community 371 - "Community 371"
Cohesion: 0.17
Nodes (11): get_industry_prompt(), get_industry_tone(), get_industry_tools(), map_onboarding_industry_to_enum(), Industry Enum: Defines the industries the Variant Engine supports.  Each industr, Validate and convert a string to an Industry enum.      Args:         industry:, Get the system prompt prefix for an industry.      Falls back to GENERAL if the, Get the available tools for an industry.      Falls back to GENERAL tools if the (+3 more)

### Community 372 - "Community 372"
Cohesion: 0.20
Nodes (11): _create_memory_checkpointer(), _create_postgres_checkpointer(), get_checkpointer(), get_thread_id(), PARWA LangGraph Checkpointer — State Persistence  Provides PostgresSaver-based c, Create a MemorySaver checkpointer (development/testing only).      State is stor, Reset the singleton checkpointer instance.      Used for testing or when databas, Generate a thread ID for LangGraph checkpoint scoping.      Thread IDs are tenan (+3 more)

### Community 373 - "Community 373"
Cohesion: 0.23
Nodes (8): faq_agent_node(), FAQAgent, FAQ Agent Node — Group 4 Domain Agent (FAQ / General queries)  Specialized domai, Retrieve relevant documents from the RAG knowledge base.          Uses the produ, Add RAG-specific fields to the state update.          Extends the base state upd, FAQ Agent Node — LangGraph agent node.      Handles general inquiries, FAQ looku, FAQ Domain Agent — handles general queries, FAQs, greetings,     and knowledge-b, Override run() to retrieve RAG docs BEFORE generating response.          FIX for

### Community 374 - "Community 374"
Cohesion: 0.21
Nodes (8): Technical Agent Node — Group 4 Domain Agent (Technical Support / Troubleshooting, Check current system status and known incidents.          Uses app.core.react_to, Generate structured troubleshooting steps for the issue.          Uses app.core., Add technical-specific fields to the state update.          Extends the base sta, Technical Agent Node — LangGraph agent node.      Handles technical support, tro, Technical Domain Agent — handles technical support, troubleshooting,     and bug, technical_agent_node(), TechnicalAgent

### Community 375 - "Community 375"
Cohesion: 0.21
Nodes (8): billing_agent_node(), BillingAgent, Billing Agent Node — Group 4 Domain Agent (Billing / Payments / Invoices / Subsc, Look up billing information using the billing_tool.          Uses app.core.react, Verify payment methods on file for the customer.          Checks payment method, Add billing-specific fields to the state update.          Extends the base state, Billing Agent Node — LangGraph agent node.      Handles billing inquiries, payme, Billing Domain Agent — handles billing inquiries, payment issues,     invoice re

### Community 376 - "Community 376"
Cohesion: 0.23
Nodes (11): is_transient_error(), llm_call_with_retry(), LLM call retry with exponential backoff for LangGraph nodes.  All 19 LangGraph n, Classify whether an exception is transient (retryable).      Transient errors in, Call an LLM function with exponential backoff retry.      Only retries on transi, Convenience wrapper around retry_llm_call for LLM API calls.      Semantically i, Synchronous LLM call with exponential backoff retry.      LG-01 Fix: All 19 Lang, Synchronous convenience wrapper for LLM API calls with retry.      Semantically (+3 more)

### Community 377 - "Community 377"
Cohesion: 0.17
Nodes (1): SG-07: Load-Aware Distribution (Week 10 Day 4)  Distributes workload across mult

### Community 378 - "Community 378"
Cohesion: 0.23
Nodes (11): get_all_variant_info(), get_variant_limits(), get_variant_price(), is_upgrade(), normalize_variant_name(), PARWA Pricing Configuration — SINGLE SOURCE OF TRUTH ═══════════════════════════, Get the price for a variant and billing cycle.      Args:         variant:, Normalize a variant name to its canonical form.      Maps old names to new: (+3 more)

### Community 379 - "Community 379"
Cohesion: 0.21
Nodes (7): _call_google_async(), _call_openai_compatible_async(), RateLimitError, Smart Router (F-054): MAKER-Aware 3-Tier LLM Routing via Free Providers.  Select, Execute LLM call via LiteLLM with retry + fallback (async).          BC-001: com, Raised when a provider returns HTTP 429 rate limit.      Carries provider/model, Async version of execute_llm_call for MAKER concurrent execution.          Runs

### Community 380 - "Community 380"
Cohesion: 0.21
Nodes (11): approval_gate_node(), _create_approval_request(), _persist_approval_request(), process_approval_response(), PARWA Jarvis Approval Gate Node (Phase 4)  A LangGraph node for human-in-the-loo, Create a structured approval request for the UI.      This builds the approval r, Create a concise summary of the agent decision for the approval UI.      Args:, Persist the approval request to DB for audit trail.      Args:         request: (+3 more)

### Community 381 - "Community 381"
Cohesion: 0.23
Nodes (11): _interpret_query(), pipeline_query_agent_node(), PARWA Jarvis Pipeline Query Agent Node (Phase 4)  A specialist agent that can QU, Read the current pipeline state from Redis bridge.      Falls back to DB if Redi, Read awareness data from DB (fallback for missing awareness_snapshot).      Args, Interpret the user's query against the current pipeline state.      Uses ZAI SDK, Rule-based query interpretation when ZAI SDK is unavailable.      Uses keyword m, Query the variant LangGraph pipeline for real-time status.      This is how Jarv (+3 more)

### Community 382 - "Community 382"
Cohesion: 0.23
Nodes (11): build_context_knowledge(), get_edge_case_response(), load_all_knowledge(), PARWA Jarvis Knowledge Service (Week 9 — Knowledge Integration)  Loads and searc, Convenience: Search and return a formatted string for AI prompt injection., Assembles a comprehensive knowledge section based on the session context., Get specialized response for edge cases (competitors, legal, etc)., Load all JSON files into memory at startup/first call. (+3 more)

### Community 383 - "Community 383"
Cohesion: 0.23
Nodes (11): _build_llm_prompt(), _build_router_context(), onboarding_router_node(), PARWA Onboarding Router Agent Node  The FIRST node in the onboarding agent graph, Fast rule-based routing using keyword/regex matching.      Returns a dict with a, Build the context dict for the LLM., Build the LLM prompt for routing., Validate and normalize the LLM routing result. (+3 more)

### Community 384 - "Community 384"
Cohesion: 0.23
Nodes (11): _build_salesman_context(), _detect_concerns(), _llm_salesman(), PARWA Onboarding Salesman Agent Node  The Salesman Agent demonstrates value by s, Use ZAI SDK LLM for intelligent sales response., Build context for salesman LLM call., Detect new concerns from the user message., Rule-based fallback for salesman responses.      Handles the 7 most common objec (+3 more)

### Community 385 - "Community 385"
Cohesion: 0.17
Nodes (11): calculate_totals(), get_cheapest_variant(), get_popular_variant(), get_variant_by_id(), PARWA Pricing Service (Day 6)  Business logic for pricing calculations and varia, Get a specific variant by industry and ID.      Args:         industry: Industry, Validate variant selections for an industry.      Args:         industry: Indust, Calculate pricing totals from validated selections.      Args:         validated (+3 more)

### Community 386 - "Community 386"
Cohesion: 0.24
Nodes (11): classify_ticket(), generate_response(), _parse_json_response(), PARWA AI Tasks (Day 22, BC-004)  Celery tasks for AI operations: - classify_tick, Classify a support ticket using AI.      CL-02 FIX: Calls the LLM gateway to cla, Generate AI response for a support ticket.      CL-02 FIX: Calls the LLM gateway, Score confidence of an AI-generated response.      CL-02 FIX: Calls the LLM gate, Run LLM gateway call synchronously (for Celery worker context).      CL-02 FIX: (+3 more)

### Community 387 - "Community 387"
Cohesion: 0.17
Nodes (11): process_brevo_webhook(), process_paddle_webhook(), process_shopify_webhook(), process_twilio_webhook(), process_webhook_event(), Webhook Celery Tasks (BC-003, BC-004, BC-001)  Async webhook processing tasks di, Process Twilio SMS/voice webhook event.      Args:         company_id: Tenant co, Process Brevo inbound email webhook event.      Args:         company_id: Tenant (+3 more)

### Community 388 - "Community 388"
Cohesion: 0.21
Nodes (7): _now_utc(), Dispatch a lifecycle event to all registered listeners.          Each listener i, Find the most recent StageExecution for a given stage.          Searches the lif, Return current UTC timestamp as ISO-8601 string (BC-012)., Mark a pipeline stage as completed successfully.          Updates the most recen, Mark a pipeline stage as failed, optionally scheduling retry.          If the st, Cancel an active lifecycle.          Moves the lifecycle to CANCELLED status, re

### Community 389 - "Community 389"
Cohesion: 0.18
Nodes (7): LifecycleConfig, Per-company lifecycle configuration.      Controls timeout, retry behaviour, log, Check if a lifecycle has exceeded its configured timeout.          Computes the, Return the ordered list of pipeline stages for a variant.          Args:, Check timeout for a lifecycle (called under lock).          Args:             lc, Get lifecycle configuration for a company with defaults.          If no custom c, Initialize a new lifecycle for a ticket and return its ID.          Creates a ne

### Community 390 - "Community 390"
Cohesion: 0.17
Nodes (9): _duration_ms(), _parse_iso(), Get the duration of a specific stage execution in         milliseconds., Get the total duration of a lifecycle in milliseconds.          For completed li, Get a rich summary dict for a single lifecycle.          Includes lifecycle meta, Parse an ISO-8601 timestamp string into a datetime.      Handles both ``Z`` suff, Calculate the duration in milliseconds between two ISO timestamps.      Args:, Serialize a StageExecution to a plain dictionary.      Args:         se: StageEx (+1 more)

### Community 391 - "Community 391"
Cohesion: 0.17
Nodes (9): ConflictCheckResult, ConflictResult, Register a variant's response and check for conflicts.          Tracks all respo, Find existing responses that conflict with the new one.          A conflict exis, Map a conflict severity to a resolution strategy.          - LOW → ``NO_ACTION``, A single response registered in the multi-variant conflict     tracker.      Att, Immediate result when a new response is registered.      Indicates whether the r, Full representation of a detected multi-variant conflict.      Attributes: (+1 more)

### Community 392 - "Community 392"
Cohesion: 0.17
Nodes (6): GaugeMetric, Set the gauge to a specific value., Increment a labeled gauge., Build a stable key from label dict., Render as Prometheus text format., Prometheus gauge: value can go up or down.      Attributes:         name: Metric

### Community 393 - "Community 393"
Cohesion: 0.20
Nodes (7): PartialFailureHandler, Clear all internal state. For testing only., Clear all state for a specific company.          Removes custom configs, result, SG-32: Partial Pipeline Failure Handler.      Manages graceful degradation when, Initialize the handler with default templates and configs.          Loads per-va, Register all built-in fallback templates.          Includes base templates for a, Build a reduced pipeline by removing failed stages.          Takes the original

### Community 394 - "Community 394"
Cohesion: 0.20
Nodes (11): cache_delete(), cache_get(), cache_set(), get_redis(), make_key(), namespaced_get(), Get or create the Redis connection pool singleton.      Uses connection pooling, Get a cached value by tenant-scoped key.      Args:         company_id: Tenant i (+3 more)

### Community 395 - "Community 395"
Cohesion: 0.18
Nodes (7): HealingAction, Check a single healing rule and return action if triggered., Detect if error rate has spiked compared to previous window.          Returns th, Detect if P90 latency has spiked.          Returns (baseline_avg, current_p90) i, Create a disable-provider healing action., Record of a healing action taken by the engine., Get the most recent action for a specific rule.

### Community 396 - "Community 396"
Cohesion: 0.20
Nodes (5): CapacityManager, Release a capacity slot for *agent_id* (call when ticket is resolved)., Tracks real-time agent capacity and enforces limits.      Used by the ``Assignme, Atomically increment load if capacity allows.  Returns True on success., Atomically decrement load (floor = 0).

### Community 397 - "Community 397"
Cohesion: 0.18
Nodes (6): Get all deactivation notices for a company.          Includes both acknowledged, List all transition records for a company.          Returns transitions in chron, List all in-progress (ACTIVE or PENDING) transitions.          BC-001: company_i, Return the current effective variant for a company.          If no transition ha, Get a summary of all transitions and current state for a company.          Retur, List all tracked in-flight tickets for a company.          BC-001: company_id is

### Community 398 - "Community 398"
Cohesion: 0.20
Nodes (7): Handles the $1 demo paywall via token-based verification.      In production thi, Verify that *payment_token* matches the expected HMAC., Coerce *value* to Decimal or return None (BC-002, BC-008)., Immutable configuration for the voice demo system., _safe_decimal(), VoiceDemoConfig, VoiceDemoPayment

### Community 399 - "Community 399"
Cohesion: 0.17
Nodes (7): OOODetectionLog, OOODetectionRule, OOOSenderProfile, OOO Detection Models — Week 13 Day 3 (F-122)  Tables: - ooo_detection_rules: Cus, Per-sender OOO tracking.      Tracks how many times a sender has triggered OOO d, Custom OOO detection rule.      Tenants can define custom patterns to detect OOO, Structured log of OOO detection events.      Every OOO detection (header/subject

### Community 400 - "Community 400"
Cohesion: 0.17
Nodes (7): ConnectionStatus, Integration, IntegrationTestResult, ProviderCategory, ProviderInfo, UseIntegrationsReturn, WebhookConfig

### Community 401 - "Community 401"
Cohesion: 0.17
Nodes (12): _call_ai_provider(), _call_google_api(), _call_single_provider(), _determine_message_type(), _get_stage_fallback(), Call AI provider for response generation.      Routes to Cerebras, Groq, or Goog, Try AI providers in order: Cerebras → Groq → Google. Returns content or None., Call a single AI provider and return the response content. (+4 more)

### Community 402 - "Community 402"
Cohesion: 0.18
Nodes (8): get_self_healing_service(), Get recent healing actions taken.          Args:             limit: Maximum numb, Get healing metrics for monitoring.          Returns stats about healing checks,, Get current self-healing service status.          Returns a summary suitable for, Get the singleton SelfHealingService instance., Proactive self-healing service.      Runs periodically (via Celery task) and:, Address queue buildup.          Logs the issue and optionally increases worker c, SelfHealingService

### Community 403 - "Community 403"
Cohesion: 0.17
Nodes (6): Get conversation by phone number pair.          Args:             company_id: Te, Check BC-006 outbound rate limit.          Args:             company_id: Tenant, Send an outbound SMS message via Twilio.          Validates rate limits (BC-006), Get an SMS conversation with company_id isolation.          Args:             co, Normalize a phone number to E.164 format.          Strips spaces, dashes, parens, Find existing conversation or create new one.          Thread by unique phone nu

### Community 404 - "Community 404"
Cohesion: 0.20
Nodes (11): format_duration(), from_iso(), is_expired(), PARWA Date/Time Utilities (BC-012)  All datetime operations use timezone-aware U, Return current UTC time as timezone-aware datetime.      Always use this instead, Convert a datetime to ISO 8601 string.      If dt is None, uses current UTC time, Parse an ISO 8601 string to a timezone-aware datetime.      Returns None if pars, Format a duration in seconds to human-readable string.      Examples: 0.5s -> '5 (+3 more)

### Community 405 - "Community 405"
Cohesion: 0.17
Nodes (11): is_valid_email(), is_valid_phone(), is_valid_url(), is_valid_uuid(), PARWA Input Validators  Validates common input formats: email, phone (E.164), UU, Sanitize a string for safe storage.      Strips leading/trailing whitespace, col, Validate email format.      Checks basic RFC 5322 compliance (simplified).     R, Validate phone number in E.164 international format.      E.164 format: starts w (+3 more)

### Community 407 - "Community 407"
Cohesion: 0.23
Nodes (9): FormControl(), FormDescription(), FormFieldContext, FormFieldContextValue, FormItemContext, FormItemContextValue, FormLabel(), FormMessage() (+1 more)

### Community 408 - "Community 408"
Cohesion: 0.18
Nodes (1): PARWA AI — Provider Abstraction Layer: Base Classes & Protocols  Defines the cor

### Community 409 - "Community 409"
Cohesion: 0.20
Nodes (4): MailgunProvider, PARWA AI — Mailgun Email Provider  API reference: https://documentation.mailgun., Mailgun email provider adapter., Return the correct API base URL depending on region.

### Community 410 - "Community 410"
Cohesion: 0.18
Nodes (10): calculate_analytics_task(), process_webhook_task(), PARWA Example Tasks (BC-004)  Skeleton tasks to verify Celery infrastructure wor, Calculate analytics for a company (skeleton).      Args:         company_id: Ten, # TODO: Implement actual analytics calculation, Send welcome email to a new user (BC-006 skeleton).      Args:         company_i, # TODO: Implement actual email sending (BC-006), Process an incoming webhook event (BC-003 skeleton).      Args:         company_ (+2 more)

### Community 411 - "Community 411"
Cohesion: 0.18
Nodes (6): MetricsRegistry, Thread-safe Prometheus metrics registry.      All metrics are registered here an, Get or create a counter metric., Get or create a gauge metric., Render all registered metrics as Prometheus text format., Clear all metrics (used in tests).

### Community 412 - "Community 412"
Cohesion: 0.18
Nodes (7): InFlightTicket, Tracks a ticket that is currently being processed by the AI agent.      Captures, Serialise ticket tracking state to a plain dict., Register a new in-flight ticket with its current variant.          If a transiti, Resolve the effective variant for a company.          If a recent transition has, Called at the start of each turn to determine effective variant.          SG-08, _utc_now_timestamp()

### Community 413 - "Community 413"
Cohesion: 0.18
Nodes (7): EmailThread, InboundEmail, Email Channel Models: inbound_emails, email_threads.  Week 13 Day 1 (F-121: Emai, Maps email threads (Message-ID chains) to tickets.      When an email comes in w, Serialize email thread for API responses., Raw inbound email storage for audit trail.      Every email received via Brevo i, Serialize inbound email for API responses.

### Community 414 - "Community 414"
Cohesion: 0.18
Nodes (1): FetchState

### Community 415 - "Community 415"
Cohesion: 0.22
Nodes (7): ChatWindow(), ChatWindowProps, getWelcomeMessage(), INDUSTRY_LABELS, RoiContext, SUGGESTIONS, TypingIndicator()

### Community 416 - "Community 416"
Cohesion: 0.18
Nodes (10): Agent, AGENT_STATUS_COLORS, AGENT_STATUS_LABELS, AGENT_TYPE_COLORS, AGENT_TYPE_LABELS, AgentMetrics, AgentsState, AgentStatus (+2 more)

### Community 417 - "Community 417"
Cohesion: 0.33
Nodes (9): apiFetch(), calculateBillEstimate(), createDemoPayment(), createDemoSession(), getDemoBilling(), getDemoSession(), getDemoUsage(), listKnowledgeBases() (+1 more)

### Community 418 - "Community 418"
Cohesion: 0.18
Nodes (9): Notification, NOTIFICATION_CATEGORY_LABELS, NOTIFICATION_TYPE_COLORS, NOTIFICATION_TYPE_LABELS, NotificationCategory, NotificationState, NotificationType, PRIORITY_LABELS (+1 more)

### Community 419 - "Community 419"
Cohesion: 0.20
Nodes (10): NamedTuple, get_next_offset(), get_total_pages(), PaginationParams, parse_pagination(), PARWA Pagination Utilities  Provides safe pagination parameter parsing with maxi, Validated pagination parameters., Parse and validate pagination parameters.      Enforces maximum page size and of (+2 more)

### Community 420 - "Community 420"
Cohesion: 0.18
Nodes (9): AGENT_TYPES, AgentFormData, AgentType, tierColors, tierSelectedColors, typeColors, typeSelectedColors, VARIANT_TIERS (+1 more)

### Community 421 - "Community 421"
Cohesion: 0.18
Nodes (6): HealingResult, Reset a circuit breaker that's been open too long.          Forces the circuit b, Switch LLM provider to fallback.          Records failure in circuit breaker man, Result of a self-healing action., Clean up Redis locks held too long.          Scans for locks with the configured, Pre-populate critical caches.          Warms up frequently accessed cache entrie

### Community 422 - "Community 422"
Cohesion: 0.22
Nodes (7): ChartConfig, ChartContext, ChartContextProps, ChartLegendContent(), ChartTooltipContent(), THEMES, useChart()

### Community 427 - "Community 427"
Cohesion: 0.20
Nodes (9): Shared Email Utility Functions — Week 13 Day 2  Common helpers used across outbo, Strip HTML tags and return plain text.      Collapses whitespace and trims leadi, Safely run an async coroutine from a synchronous context.      If a running even, Basic email address validation.      Checks for the presence of '@', a domain wi, Sanitize an email subject line.      Strips control characters, collapses whites, run_async_coro(), sanitize_subject(), strip_html() (+1 more)

### Community 428 - "Community 428"
Cohesion: 0.27
Nodes (9): _apply_ner_redaction(), _apply_tenant_rules(), _fallback_redact(), pii_redaction_node(), PII Redaction Node — Group 1 (First node in the pipeline)  Scans the incoming me, Apply NER (Named Entity Recognition) based PII detection.      Uses the producti, Apply tenant-specific PII rules for custom patterns.      Loads tenant-specific, PII Redaction Node — LangGraph agent node.      Detects and redacts personally i (+1 more)

### Community 429 - "Community 429"
Cohesion: 0.27
Nodes (9): _analyze_sentiment_trend(), empathy_engine_node(), _escalate_legal_threat(), _fallback_sentiment_analysis(), Empathy Engine Node — Group 2 (Second node in the pipeline)  Analyzes the PII-re, Analyze sentiment trend across conversation history.      Loads the last N messa, Escalate legal threats for High tier tenants.      When a legal threat is detect, Empathy Engine Node — LangGraph agent node.      Analyzes the PII-redacted messa (+1 more)

### Community 430 - "Community 430"
Cohesion: 0.27
Nodes (9): _apply_dspy_optimization(), dspy_optimizer_node(), DSPy Optimizer Node — Group 8: Prompt Optimization  Applies DSPy-based prompt op, Re-generate the response using the DSPy-optimized prompt.      This is the FIX f, Determine whether DSPy should be applied for this request.      Tier rules:, DSPy Optimizer Node — Prompt optimization for improved response quality.      Ap, Apply DSPy prompt optimization.      Uses the production dspy_integration module, _regenerate_with_optimized_prompt() (+1 more)

### Community 431 - "Community 431"
Cohesion: 0.27
Nodes (9): _apply_brand_voice(), _dispatch_email(), email_agent_node(), Email Agent Node — Group 10: Email Channel Delivery  Delivers the agent response, Render the response text into an HTML email body.      Uses the production email, Dispatch the email via the channel dispatcher.      Uses the production channel_, Email Agent Node — Delivers response via the email channel.      Applies brand v, Apply brand voice template to the response text.      Uses the production brand_ (+1 more)

### Community 432 - "Community 432"
Cohesion: 0.27
Nodes (9): _dispatch_sms(), _format_sms_content(), SMS Agent Node — Group 10: SMS Channel Delivery  Delivers the agent response via, Dispatch the SMS via the channel dispatcher.      Uses the production channel_di, SMS Agent Node — Delivers response via the SMS channel.      Truncates the respo, Truncate the response text to SMS-appropriate length.      Mini tier uses standa, Format the response text for SMS delivery.      Strips HTML tags, normalizes whi, sms_agent_node() (+1 more)

### Community 433 - "Community 433"
Cohesion: 0.27
Nodes (9): _convert_to_voice_format(), _initiate_voice_call(), Voice Agent Node — Group 10: Voice Channel Delivery (Pro + High Only)  Delivers, Wrap the voice text in SSML for TTS engines.      Pro tier gets basic SSML (paus, Initiate a voice call via the call lifecycle module.      Uses the production ca, Voice Agent Node — Delivers response via the voice channel.      Converts the ag, Convert response text to a voice-friendly format.      Voice communication requi, voice_agent_node() (+1 more)

### Community 434 - "Community 434"
Cohesion: 0.22
Nodes (9): get_all_validated_fields(), get_field_constraints(), ParwaGraphState Validators — State Transition Validation & Sanitization  This mo, Validate a partial state update dict against known constraints.      Checks only, Sanitize a partial state update dict by correcting invalid values     to safe de, Get constraint information for a validated field.      Args:         field_name:, Get constraint information for all validated fields.      Returns:         Dict, sanitize_state_update() (+1 more)

### Community 435 - "Community 435"
Cohesion: 0.20
Nodes (8): SG-36: Tenant-Specific Prompt Injection Defense (BC-011, BC-007, BC-010)  Multi-, Strip zero-width chars, normalize unicode, collapse whitespace.      Args:, Calculate Shannon entropy of a string.      High entropy suggests encoded or ran, Truncate query for safe storage in database.      Args:         query: Raw query, Layer 2: Detect unusual query characteristics.          Checks:         - Query, sanitize_query(), _shannon_entropy(), _truncate_preview()

### Community 436 - "Community 436"
Cohesion: 0.20
Nodes (9): EmotionType, Sentiment Analysis / Empathy Engine (F-063)  Analyzes customer messages to produ, Valid emotion types for classification., Valid urgency levels., Valid tone recommendations., Conversation sentiment trend., ToneRecommendation, TrendDirection (+1 more)

### Community 437 - "Community 437"
Cohesion: 0.20
Nodes (9): create_command_state_from_alert(), create_command_state_from_nl(), _merge_dicts(), _merge_lists(), PARWA Jarvis Command State — LangGraph State for the Multi-Agent Command Layer, Create initial command state from an awareness alert.      This is how Jarvis go, Create initial command state from a user's natural language input.      This is, Reducer: merge new dict into existing (new keys override). (+1 more)

### Community 438 - "Community 438"
Cohesion: 0.27
Nodes (9): _build_router_context(), command_router_node(), PARWA Jarvis Command Router Agent Node  The FIRST node in the command graph. Whe, Build the context dict for the LLM., Route an awareness alert using ZAI SDK., Route a user NL command. Try regex first, then LLM., Route an alert or user command to the appropriate agent.      Decision Process:, _route_alert() (+1 more)

### Community 439 - "Community 439"
Cohesion: 0.27
Nodes (9): _build_call_context(), call_agent_node(), _llm_call(), PARWA Onboarding Call Agent Node  The Call Agent handles voice call demo booking, Use ZAI SDK LLM for intelligent call handling response., Build context for the call LLM call., Rule-based fallback for call agent responses.      Handles the voice call demo f, Handle voice call demo booking and execution.      Decision Process:       1. De (+1 more)

### Community 440 - "Community 440"
Cohesion: 0.27
Nodes (9): _build_demo_context(), demo_agent_node(), _llm_demo(), PARWA Onboarding Demo Agent Node  The Demo Agent roleplays as the ACTUAL AI agen, Use ZAI SDK LLM for intelligent demo response., Build context for the demo LLM call., Rule-based fallback for demo responses.      Provides scripted but realistic dem, Demonstrate how the hired Jarvis would handle a real support scenario.      Deci (+1 more)

### Community 441 - "Community 441"
Cohesion: 0.27
Nodes (9): _build_guide_context(), guide_agent_node(), _llm_guide(), PARWA Onboarding Guide Agent Node  The Guide Agent walks potential clients throu, Use ZAI SDK LLM for intelligent guide response., Build context for the guide LLM call., Rule-based fallback for guide responses.      Provides scripted but contextual r, Guide the user through PARWA's features naturally.      Decision Process: (+1 more)

### Community 442 - "Community 442"
Cohesion: 0.27
Nodes (9): _hash_code(), PARWA Phone OTP Service (C5: Phone OTP Login)  Handles sending and verifying pho, Verify a phone OTP code.      Looks up by phone + company_id + verified=False +, Send OTP via Twilio SMS.      Uses the locally generated OTP code (not Twilio Ve, Hash an OTP code using SHA-256., Send an OTP code to the given phone number.      Validates phone format, generat, send_otp(), _send_via_twilio() (+1 more)

### Community 443 - "Community 443"
Cohesion: 0.22
Nodes (9): list_sessions(), _mask_ip(), PARWA Session Service (F-017)  Business logic for session management. - List act, Revoke all sessions except the current one.      F-017: Keeps the current sessio, Mask the last octet of an IP address., List all active sessions for a user.      F-017: Returns session details with ma, Revoke a specific session.      F-017: Cannot revoke own current session.      A, revoke_other_sessions() (+1 more)

### Community 444 - "Community 444"
Cohesion: 0.20
Nodes (9): cleanup_stale_injection_logs(), PARWA AI Engine Celery Tasks (Week 8 Day 1-2, BC-004)  Background tasks for AI E, Reset used_tokens to 0 for all daily budgets.      Resets the alert_sent flag so, Cold start warmup for tenant activation or variant upgrade.      Pre-warms commo, Delete prompt_injection_attempts older than N days.      Runs daily at 04:00 UTC, Periodic workload rebalancer across variant instances.      If company_id provid, rebalance_workload(), reset_daily_budgets() (+1 more)

### Community 445 - "Community 445"
Cohesion: 0.20
Nodes (9): celery_health_check(), get_active_workers(), PARWA Celery Health Check (Day 16, BC-004, BC-012)  Provides Celery broker conne, Get active Celery worker count and queue stats.      Runs the sync check in a th, Synchronous Celery broker connectivity check.      Returns:         Dict with 's, Check Celery broker (Redis) connectivity and responsiveness.      Runs the sync, Synchronous Celery worker count check.      Returns:         Dict with 'worker_c, _sync_celery_health_check() (+1 more)

### Community 446 - "Community 446"
Cohesion: 0.20
Nodes (9): prune_awareness_data(), PARWA Jarvis Awareness Celery Tasks (Phase 2.4)  Celery tasks that make the awar, Run a single awareness tick for one CC session.      This is the per-session tas, Trigger an on_change awareness tick.      Called when a monitored field changes, Periodic cleanup of old awareness snapshots and expired alerts.      Runs every, Dispatch awareness tick tasks for all active CC sessions.      This is the Celer, run_awareness_tick_single(), run_awareness_ticks_all() (+1 more)

### Community 447 - "Community 447"
Cohesion: 0.20
Nodes (3): SentryErrorBoundary, SentryErrorBoundaryProps, SentryErrorBoundaryState

### Community 448 - "Community 448"
Cohesion: 0.20
Nodes (7): ConfidenceEscalationResult, ConfidenceHistoryEntry, Single entry in a ticket's confidence history.      Tracks the confidence score,, Result of evaluating whether a response should be escalated     based on its con, Return the next higher variant in the escalation chain.          Returns ``None`, Record a confidence history entry for a ticket.          Thread-safe.  Used inte, Evaluate whether a variant's response should be escalated         based on its c

### Community 449 - "Community 449"
Cohesion: 0.20
Nodes (9): _context_to_dict(), EscalationRecord, _generate_id(), _is_vip(), Record of an escalation event.      Tracks the full lifecycle of an escalation f, Generate a unique escalation ID using UUID4., Check if a customer tier qualifies as VIP., Serialize an EscalationContext to a dictionary. (+1 more)

### Community 450 - "Community 450"
Cohesion: 0.22
Nodes (6): BlockedResponseManager, Manages blocked AI responses for approval workflow.      Logs blocked responses, Log a blocked response for approval workflow.          Args:             company, Get a paginated list of blocked responses.          Args:             company_id, Get guardrail blocking statistics for a tenant.          Args:             compa, Increment stats counters in Redis.          Uses a single hash per tenant to tra

### Community 451 - "Community 451"
Cohesion: 0.20
Nodes (6): CounterMetric, Prometheus counter: monotonically increasing value.      Attributes:         nam, Increment the counter by value (must be >= 0)., Increment a labeled counter., Build a stable key from label dict., Render as Prometheus text format.

### Community 452 - "Community 452"
Cohesion: 0.20
Nodes (6): HistogramMetric, Prometheus histogram: tracks distribution of values.      Uses pre-defined bucke, Initialize bucket counts to 0., Build a stable key from label dict., Render as Prometheus text format., Get or create a histogram metric.

### Community 453 - "Community 453"
Cohesion: 0.20
Nodes (8): _count_all_non_success(), _get_critical_ratio(), PipelineResultRecord, Record the final outcome of a pipeline run.          Creates a PipelineResultRec, Record of a pipeline's final outcome for analytics.      Attributes:         com, Get the critical degradation ratio for a variant., Count all non-success statuses including DEGRADED and SKIPPED., Assess the overall degradation level for a pipeline run.          Compares the n

### Community 454 - "Community 454"
Cohesion: 0.20
Nodes (7): _now_utc(), Get aggregated failure statistics for a company.          Returns per-stage fail, Return current UTC timestamp as ISO-8601 string (BC-012)., Record a stage failure in the pipeline context.          Appends a StageFailure, Append a failure stat entry for company-level analytics., Record of a single stage failure within a pipeline run.      Attributes:, StageFailure

### Community 455 - "Community 455"
Cohesion: 0.20
Nodes (5): Find the best matching fallback template for an intent.          Selection proce, Score a fallback template for relevance to the current         pipeline state., Generate a best-effort response using available signals         and fallback tem, Enrich a fallback template with available signal data.          Performs simple, Attempt to generate a response from available signal data         without a temp

### Community 456 - "Community 456"
Cohesion: 0.20
Nodes (7): _classify_pattern_type(), InjectionMatch, Map rule_id prefix to human-readable pattern type.      Args:         rule_id: R, Layer 1: Match against 25+ known injection signatures.          Organized by cat, Layer 3: Check rate of suspicious queries per tenant/user.          Uses pre-fet, Layer 4: Check query against per-tenant custom block patterns.          Admin-co, Describes a single detected injection pattern.

### Community 457 - "Community 457"
Cohesion: 0.20
Nodes (6): get_severity_weights(), Return severity → weight mapping for scoring.      Higher weight = more dangerou, Determine the action based on all detected matches.          Decision logic:, Log injection attempt to DB and update Redis rate limit.          BC-001: compan, Log an injection attempt to the database.          Writes to prompt_injection_at, Increment the injection rate limit counter in Redis.          Uses a sliding win

### Community 458 - "Community 458"
Cohesion: 0.27
Nodes (7): hash_query(), InjectionScanResult, Run all detection layers on a query.          Args:             query: The user, Internal scan with all layers.          Layers run in sequence; first critical m, Scan a query and persist the result if injection detected.          Fetches Redi, Full result from a prompt injection scan., SHA-256 hash of the query for deduplication.      Normalizes whitespace before h

### Community 459 - "Community 459"
Cohesion: 0.20
Nodes (7): ActionItemFormatter, BoldFormatter, create_default_registry(), 8. Remove excessive bold/italic formatting., 14. Extract and format action items from responses., Register a formatter with a name.          Args:             name: Unique name f, Create a FormatterRegistry with all 15 formatters registered.

### Community 460 - "Community 460"
Cohesion: 0.20
Nodes (6): 1. Truncate response to model's max token limit.      Uses approximate 4 chars p, 12. Add/validate sign-offs based on brand voice., Get a formatter by name.          Args:             name: Formatter name., Get default formatter list for a variant type.          Args:             varian, SignatureFormatter, TokenLimitFormatter

### Community 461 - "Community 461"
Cohesion: 0.20
Nodes (2): MigrationEventBus, In-process pub/sub for migration events.

### Community 462 - "Community 462"
Cohesion: 0.20
Nodes (8): _floor_threshold(), _now_utc(), Get global health across all companies (admin view)., Record of a confidence threshold adjustment., Return current UTC timestamp as ISO string., Get the minimum floor threshold for a variant., Check if confidence has dropped and threshold should lower.          Returns (ne, ThresholdAdjustment

### Community 463 - "Community 463"
Cohesion: 0.24
Nodes (7): _compute_history_hash(), _compute_query_hash(), Output of sentiment analysis (F-063)., Serialize to dictionary for caching., Analyze customer message for sentiment signals.          Args:             query, BC-008: Return safe default for empty/invalid input., SentimentResult

### Community 464 - "Community 464"
Cohesion: 0.22
Nodes (7): ModelConfig, ProviderUsage, Tracks usage and health for a single provider+model combination., Get or create ProviderUsage for a registry key., Record a 429 rate limit response. Sets cooldown timer.          Respects Retry-A, Record a failed API call. Marks unhealthy after threshold., Full configuration for a single model in the registry.

### Community 465 - "Community 465"
Cohesion: 0.20
Nodes (4): AssignmentResult, Outcome of a single ticket assignment., Filter and sort agents for rule-based eligibility., Return the agent with the lowest current_load (ties broken by last_assigned).

### Community 466 - "Community 466"
Cohesion: 0.29
Nodes (6): analyticsApi, generateMockCategories(), generateMockDashboard(), generateMockSLA(), generateMockSummary(), generateMockTrends()

### Community 467 - "Community 467"
Cohesion: 0.24
Nodes (6): ALLOWED_REDIRECT_PREFIXES, COOKIE_OPTIONS, fullyDecodeUri(), getSafeRedirect(), isSafeRedirect(), REFRESH_COOKIE_OPTIONS

### Community 468 - "Community 468"
Cohesion: 0.20
Nodes (8): commonFeatures, industries, Industry, IndustryConfig, trustIndicators, uniqueFeatures, VariantData, VariantId

### Community 469 - "Community 469"
Cohesion: 0.22
Nodes (10): _build_unknown_command(), _extract_parameters(), _fuzzy_match_command(), _generate_suggestion(), parse_natural_language_command(), Build a structured result for an unrecognized command., Try fuzzy keyword matching when regex patterns fail.      Looks for individual k, Extract structured parameters from the NL input.      For example, "add 5 agents (+2 more)

### Community 470 - "Community 470"
Cohesion: 0.20
Nodes (10): _execute_undo_action(), _handler_pause_ai(), _handler_pause_refunds(), _handler_resume_ai(), _handler_resume_refunds(), Handler: pause_ai — Pause all AI agent activity.      Updates the session contex, Handler: resume_ai — Resume AI agent activity., Handler: pause_refunds — Pause automated refund processing. (+2 more)

### Community 471 - "Community 471"
Cohesion: 0.20
Nodes (5): Update preference for a specific event type.                  Args:, Update multiple preferences at once.                  Args:             user_id:, Disable all notifications for a user.                  Returns count of preferen, Enable all notifications for a user with default settings.                  Retu, Copy preferences from one user to another.                  Returns count of pre

### Community 472 - "Community 472"
Cohesion: 0.27
Nodes (4): Get configuration for an endpoint category., Get current time with Redis offset applied (G01)., Record a failure and return backoff seconds.          G01: Uses Redis time offse, Check if identifier is currently locked out.          G01: Uses Redis time offse

### Community 473 - "Community 473"
Cohesion: 0.22
Nodes (5): Encrypt a credential value at rest (BC-011).          In test environment, retur, Get SMS channel config for a company.          Args:             company_id: Ten, Create SMS channel config for a company.          Encrypts Twilio auth token (BC, Update SMS channel config (partial update).          Args:             company_i, Delete SMS channel config for a company.          Args:             company_id:

### Community 474 - "Community 474"
Cohesion: 0.20
Nodes (5): BL05: Check rate limit for ticket creation.          .. note::             This, PS07: Check if account is suspended.          Raises:             AuthorizationE, Validate customer exists and belongs to company.          Args:             cust, PS01: Check out-of-plan scope.          Args:             category: Ticket categ, Create a new ticket with production situation handlers.          PS01: Out-of-pl

### Community 476 - "Community 476"
Cohesion: 0.22
Nodes (2): NavigationMenuTrigger(), navigationMenuTriggerStyle

### Community 477 - "Community 477"
Cohesion: 0.20
Nodes (9): Toast, ToastAction, ToastActionElement, ToastClose, ToastDescription, ToastProps, ToastTitle, toastVariants (+1 more)

### Community 478 - "Community 478"
Cohesion: 0.28
Nodes (7): _extract_feature_id(), _get_company_variant_type(), PARWA AI Entitlement Middleware (Week 8, SG-05 / BC-011)  Intercepts requests to, Get the company's highest active variant type.      Queries variant_instances fo, Extract feature_id from the request path.      Examples:         /api/ai/router/, Check if the path should skip entitlement checks., _should_skip()

### Community 479 - "Community 479"
Cohesion: 0.25
Nodes (7): _build_config(), _enforce_max_payload_size(), LazySettings, PARWA Celery Application (BC-004)  Celery app configuration with Redis broker, t, Lazy proxy that reads from PARWA Settings on first access., Build Celery configuration dict from PARWA settings., Reject task publication if payload exceeds MAX_TASK_PAYLOAD_BYTES.

### Community 480 - "Community 480"
Cohesion: 0.39
Nodes (8): callCerebras(), callGoogleAI(), callGroq(), callZAI(), ChatMessage, getAIResponse(), getZAI(), POST()

### Community 481 - "Community 481"
Cohesion: 0.22
Nodes (6): BaseFormatter, CitationFormatter, 3. Format citations [1], [2] with source links., 11. Clean up excessive whitespace, blank lines., Abstract base class for all response formatters., WhitespaceFormatter

### Community 482 - "Community 482"
Cohesion: 0.31
Nodes (5): LengthFormatter, 5. Condense/expand based on preferences (concise/standard/detailed)., Determine length preference from context., Remove filler phrases and redundant sentences., Add transition phrases for more detailed responses.

### Community 483 - "Community 483"
Cohesion: 0.22
Nodes (6): ConversationTrendAnalyzer, Scores urgency level from 0-100, maps to discrete levels., Return urgency level string.          Maps numeric score to: low (0-30), medium, Analyzes conversation history for sentiment trajectory., Determine conversation trend: improving, stable, worsening.          Analyzes th, UrgencyScorer

### Community 484 - "Community 484"
Cohesion: 0.22
Nodes (7): JarvisAwarenessSnapshot, JarvisCommand, JarvisProactiveAlert, Jarvis Customer Care Models: post-onboarding persistence.  3 tables that persist, Full audit log of every command Jarvis receives and executes.      Maps to GROUP, Proactive alerts generated by the Awareness Engine.      Unlike JarvisMessage (w, Periodic snapshot of the 21-field GROUP 14 awareness state.      The Awareness E

### Community 485 - "Community 485"
Cohesion: 0.22
Nodes (7): Technique Models: technique_configurations, technique_executions, technique_vers, Versioned technique implementations with A/B test metadata.     Managed via DSPy, Per-tenant technique enable/disable settings.     Tier 1 techniques (CLARA, CRP,, Logs every technique activation with token usage, latency,     and fallback trac, TechniqueConfiguration, TechniqueExecution, TechniqueVersion

### Community 486 - "Community 486"
Cohesion: 0.22
Nodes (7): CallDirection, CallStatus, CallStore, CallStoreActions, CallStoreState, useCallStore, VoiceCallItem

### Community 487 - "Community 487"
Cohesion: 0.22
Nodes (4): ChannelConfig, ChannelInfo, ChannelTestResult, UpdateChannelConfigPayload

### Community 488 - "Community 488"
Cohesion: 0.22
Nodes (7): ccAlertApi, ccAwarenessApi, ccCommandApi, ccContextApi, ccDebugApi, ccMessageApi, ccSessionApi

### Community 489 - "Community 489"
Cohesion: 0.31
Nodes (8): AGENTS_PER_PLAN, calculateBillSummary(), DEMO_VARIANTS, generateId(), GET(), PLAN_PRICES, POST(), sessions

### Community 490 - "Community 490"
Cohesion: 0.22
Nodes (5): customFallback, dismissBtn, onDismiss, { rerender }, retryBtn

### Community 491 - "Community 491"
Cohesion: 0.22
Nodes (1): PaginationLinkProps

### Community 493 - "Community 493"
Cohesion: 0.22
Nodes (8): active, alert, api, maintenanceAlert, mockData, state, store, unhealthy

### Community 494 - "Community 494"
Cohesion: 0.25
Nodes (7): get_features(), get_industries(), get_public_stats(), Public API Endpoints  Public endpoints for landing page data (no authentication, Get feature highlights for landing page carousel.          Returns the 5 slides, Get public statistics for landing page.          Note: These are representative, Get available industry options.          Only 4 industries are supported:     -

### Community 495 - "Community 495"
Cohesion: 0.25
Nodes (7): _add_env_info(), configure_logging(), get_logger(), PARWA Structured Logger (BC-012)  Uses structlog for JSON-formatted structured l, Add environment info to log events.      Replaces structlog.processors.add_env_i, Configure structlog based on environment., Get a bound structlog logger with module name.

### Community 496 - "Community 496"
Cohesion: 0.25
Nodes (7): append_audit_entry(), create_initial_state(), get_step_output(), ParwaGraphState: Unified State Object for the Variant Engine.  A single TypedDic, Create a fresh ParwaGraphState with all fields initialized.      This is the ONL, Safely get a previous step's output from state.      Args:         state: Curren, Create an audit log entry to return from a node.      Since audit_log uses opera

### Community 497 - "Community 497"
Cohesion: 0.32
Nodes (7): _from_asgi_scope(), _from_starlette_request(), get_client_ip(), PARWA — Shared Client IP Extraction Utility  Centralises IP extraction logic so, Extract the real client IP from a Starlette Request or ASGI scope.      Paramete, Resolve IP from a Starlette :class:`Request`., Resolve IP from a raw ASGI scope dict.

### Community 498 - "Community 498"
Cohesion: 0.25
Nodes (7): PARWA API Key Authentication Middleware (F-019)  Authenticates requests using AP, Dependency that checks API key scope (BC-011).      Only enforces scope when req, Check if request has BOTH write AND approval scopes.      G03: Financial approva, FastAPI dependency for G03: financial approval dual-scope.      Enforces that th, require_financial_approval(), require_financial_approval_dep(), require_scope()

### Community 499 - "Community 499"
Cohesion: 0.25
Nodes (7): create_onboarding_state(), _merge_dicts(), _merge_lists(), PARWA Onboarding Jarvis State — LangGraph State for the Onboarding Agent Graph, Create initial onboarding state from a user message.      This is how every turn, Reducer: merge new dict into existing (new keys override)., Reducer: append new items to existing list.

### Community 500 - "Community 500"
Cohesion: 0.29
Nodes (6): _compute_relevance_score(), _escape_like(), PARWA Knowledge Retriever  Retrieves relevant document chunks from the knowledge, Escape SQL LIKE wildcards in *term*., Compute a naive relevance score (0-1) based on word overlap.      This is a plac, Search knowledge base for chunks matching *query*.          Placeholder implemen

### Community 501 - "Community 501"
Cohesion: 0.25
Nodes (7): aggregate_metrics(), calculate_roi(), drift_detection(), PARWA Analytics Tasks (Day 22, BC-004, BC-007)  Celery tasks for analytics opera, Detect AI model performance drift., Aggregate metrics for a given period., Calculate ROI for the company over the given period.          This task:     1.

### Community 502 - "Community 502"
Cohesion: 0.25
Nodes (7): approval_reminder(), approval_timeout_check(), batch_process(), PARWA Approval Tasks (Day 22, BC-004, BC-009)  Celery tasks for approval workflo, Process batch approval actions., Check for timed-out approvals and auto-reject., Send reminders for pending approvals.

### Community 503 - "Community 503"
Cohesion: 0.32
Nodes (7): process_dlq_retry(), DLQ Retry Tasks — Periodic retry of failed graph executions from the Dead Letter, Attempt to retry a single DLQ entry by re-invoking the graph.          This is a, Main entry point for the DLQ retry periodic task.          Scans for eligible en, Scan DLQ for entries eligible for retry.          Eligibility criteria:       -, retry_eligible_dlq_entries(), run_dlq_retry_scan()

### Community 504 - "Community 504"
Cohesion: 0.25
Nodes (7): audit_redis_keys_task(), cleanup_expired_keys_task(), cleanup_orphaned_keys_task(), PARWA Redis Cleanup Tasks (Phase 6: Production Hardening)  Periodic Celery tasks, Apply default TTLs to keys that are missing them.      Scans all Redis keys and, Remove keys that don't match any known pattern.      CAUTION: This task can DELE, Run a full Redis key audit and log results.      Scans all Redis keys and report

### Community 505 - "Community 505"
Cohesion: 0.25
Nodes (7): cleanup_expired_sms_conversations(), process_sms_inbound_task(), SMS Celery Tasks — Week 13 Day 5 (F-123: SMS Channel)  Async tasks for SMS chann, Process an inbound SMS message asynchronously.      Dispatched from the Twilio w, Clean up expired SMS conversations.      Marks conversations with no activity fo, Send an auto-reply SMS after a configured delay.      Runs as a Celery task so t, schedule_sms_auto_reply()

### Community 506 - "Community 506"
Cohesion: 0.25
Nodes (3): ErrorBoundary, ErrorBoundaryProps, ErrorBoundaryState

### Community 507 - "Community 507"
Cohesion: 0.25
Nodes (6): AlertCondition, ErrorMetrics, Error tracking metrics., An anomalous condition detected by the monitoring service., Get error tracking metrics., Detect and return anomalous conditions.          Checks:         - Error rate >

### Community 508 - "Community 508"
Cohesion: 0.25
Nodes (6): BlockedResponseMetrics, DashboardSnapshot, Blocked response queue metrics., Complete dashboard data for one company., Get blocked response queue metrics., Get complete dashboard data in one call.

### Community 509 - "Community 509"
Cohesion: 0.25
Nodes (6): LatencyStats, _percentile(), Calculate percentile from sorted values., Get latency statistics for a given scope and time window., Aggregated latency statistics., Get a list of numeric field values from filtered records.

### Community 510 - "Community 510"
Cohesion: 0.25
Nodes (6): _parse_iso(), Parse an ISO timestamp string, returning None on failure., Return the Unix timestamp cutoff for a time window., Get metrics broken down by variant type., Get records filtered by company, provider, model, and window., _window_cutoff()

### Community 511 - "Community 511"
Cohesion: 0.25
Nodes (6): _is_valid_stage(), Record of a single stage execution within a lifecycle.      Captures timing, out, Check if a stage name is valid for a given variant.      Args:         stage:, Mark a pipeline stage as started within a lifecycle.          Validates the stag, Skip a pipeline stage within a lifecycle.          Records the skip with an opti, StageExecution

### Community 512 - "Community 512"
Cohesion: 0.25
Nodes (5): Return the tier rank of a variant (0 = lowest, 2 = highest).          Used to de, Assess the severity of a conflict between responses.          Uses a simple heur, Resolve a detected multi-variant conflict.          Applies the specified resolu, Result of resolving a multi-variant conflict.      Attributes:         resolved:, ResolutionResult

### Community 513 - "Community 513"
Cohesion: 0.25
Nodes (6): HandoffContext, HandoffResult, Full context bundle transferred during a same-ticket handoff.      Contains ever, Result of initiating a same-ticket handoff.      Attributes:         success: Wh, Initiate a handoff from one variant to another for a ticket.          Creates a, Return all pending (unacknowledged) handoffs for a company.          Each result

### Community 514 - "Community 514"
Cohesion: 0.25
Nodes (4): Remove a sticky session pin.          Args:             company_id:   Tenant ide, Remove old sticky sessions that have exceeded their TTL or age.          This is, Get or create distribution stats for a company., Mark an instance as healthy, unhealthy, overloaded, etc.          When an instan

### Community 515 - "Community 515"
Cohesion: 0.25
Nodes (6): DegradationConfig, _get_variant_config(), Customize degradation settings for a company's variant.          Merges the prov, Per-variant degradation settings.      Controls how aggressively the system degr, Retrieve degradation config for a variant with safe fallback., Update the error context dict with information from the         latest failure.

### Community 516 - "Community 516"
Cohesion: 0.25
Nodes (8): audit_all_keys(), fix_missing_ttls(), identify_namespace(), Identify which RedisNamespace a key belongs to.      Works with both old (parwa:, Full audit of all Redis keys.      Returns:         - total_key_count: Total num, Apply default TTLs to keys that are missing them.      Scans all keys and applie, Run a startup audit and log results.      Called during application startup to i, startup_audit()

### Community 517 - "Community 517"
Cohesion: 0.25
Nodes (6): _default_threshold(), Get per-variant health summary., Get the current (possibly adjusted) threshold for a variant., Health summary for one variant., Get the default confidence threshold for a variant., VariantHealthSummary

### Community 518 - "Community 518"
Cohesion: 0.32
Nodes (5): Get the first LIGHT model as ultimate fallback., Result of the Smart Router's routing decision for one atomic step., MAIN METHOD -- route one atomic step to a model.          BC-001: company_id is, Route multiple steps for a MAKER chain.          Returns a RoutingDecision for e, RoutingDecision

### Community 519 - "Community 519"
Cohesion: 0.25
Nodes (5): Full capability profile for a specific variant type.      Defines the technique, Serialise capabilities to a plain dict for persistence., Initialize the handler with variant capabilities, registries, and locks., Build capability profiles for all three variant types.          Each variant has, VariantCapabilities

### Community 520 - "Community 520"
Cohesion: 0.25
Nodes (3): AgentPerformanceTable(), AgentPerformanceTableProps, columnHelper

### Community 521 - "Community 521"
Cohesion: 0.25
Nodes (4): DashboardLayoutProps, DashboardSidebarProps, Icons, NavItem

### Community 522 - "Community 522"
Cohesion: 0.32
Nodes (7): _create_session_fks(), downgrade(), _drop_orphan_fks(), CROSS-16: Fix orphan FK references to non-existent sessions table.  The sessions, Drop orphan session_id FK constraints from affected tables.      Uses batch_alte, Re-create session_id FK constraints (used by downgrade).      No try/except need, upgrade()

### Community 523 - "Community 523"
Cohesion: 0.32
Nodes (7): _disable_rls_for_table(), downgrade(), _enable_rls_for_table(), 022_enable_rls: PostgreSQL Row-Level Security on all tenant-scoped tables.  CROS, Enable RLS and create tenant-isolation policies on *table*., Drop all tenant policies and disable RLS on *table*., upgrade()

### Community 524 - "Community 524"
Cohesion: 0.32
Nodes (5): formatDate(), formatRelativeDate(), PRIORITY_COLORS, STATUS_COLORS, TicketDetailPage()

### Community 525 - "Community 525"
Cohesion: 0.25
Nodes (6): AUTH_METHODS, AuthMethod, CustomApiBuilderProps, CustomApiConfig, HTTP_METHODS, HttpMethod

### Community 526 - "Community 526"
Cohesion: 0.25
Nodes (6): PROVIDER_EVENTS, SUPPORTED_PROVIDERS, WebhookConfig, WebhookConfiguratorProps, WebhookLog, WebhookStatus

### Community 528 - "Community 528"
Cohesion: 0.29
Nodes (2): NotificationItem(), timeAgo()

### Community 529 - "Community 529"
Cohesion: 0.25
Nodes (5): ACCEPTED_EXTENSIONS, ACCEPTED_MIMES, ACCEPTED_TYPES, KnowledgeBaseStepProps, LocalUpload

### Community 530 - "Community 530"
Cohesion: 0.25
Nodes (3): SocketContext, SocketContextValue, SocketProviderProps

### Community 531 - "Community 531"
Cohesion: 0.29
Nodes (4): Create an assignment rule.          Args:             name: Rule name, Update an assignment rule.          Args:             rule_id: Rule ID, Validate rule conditions.          Args:             conditions: Conditions to v, Validate rule action.          Args:             action: Action to validate

### Community 532 - "Community 532"
Cohesion: 0.25
Nodes (5): Remove config from Redis cache., Remove config from database.          Stub implementation — to be wired to the O, BC-001: company_id is required and non-empty., Delete a brand voice config for a company.          Removes from in-memory store, _validate_company_id()

### Community 533 - "Community 533"
Cohesion: 0.25
Nodes (7): _count_sentences(), _estimate_formality(), Result of validating a response against brand voice rules., Validate a response against brand voice rules.          Checks:           1. Pro, Count sentences in text using common delimiters., Estimate formality level of text on a 0.0-1.0 scale.      Heuristics:       - Co, ValidationResult

### Community 534 - "Community 534"
Cohesion: 0.25
Nodes (8): complete_ticket(), get_ticket(), jarvis_get_ticket(), Get a single action ticket with result., Update ticket status., Mark ticket completed with result data., Get a single ticket by ID., update_ticket_status()

### Community 535 - "Community 535"
Cohesion: 0.25
Nodes (4): AnomalyDetector, Detects system anomalies based on metrics.      Checks:     - Error rate per ser, Record an error for a service., Reset all anomaly tracking state (for testing).

### Community 536 - "Community 536"
Cohesion: 0.25
Nodes (4): Link SMS conversation to a ticket.          If the conversation already has a ti, Add an SMS message to an existing ticket.          Args:             company_id:, Find a customer by phone number.          Args:             company_id: Tenant c, Emit a Socket.io event for real-time SMS notifications (BC-005).          Args:

### Community 537 - "Community 537"
Cohesion: 0.25
Nodes (4): Update ticket fields.          Args:             ticket_id: Ticket ID, Validate status transition is allowed.          Args:             from_status: C, Record status change in history.          Args:             ticket_id: Ticket ID, Bulk update ticket status.          Args:             ticket_ids: List of ticket

### Community 538 - "Community 538"
Cohesion: 0.25
Nodes (5): { authApi }, consoleSpy, localStorageMock, mockAuthResponse, mockUser

### Community 541 - "Community 541"
Cohesion: 0.25
Nodes (7): executePromise, fn, onError, onRetry, onSuccess, { result }, retryIf

### Community 542 - "Community 542"
Cohesion: 0.29
Nodes (4): Shipping Intelligence Engine — Multi-Carrier Integration + Proactive Delay Notif, Simulate multi-carrier API integration to get shipping data.          Day 3 Enha, Async version of query_carrier_data using CarrierAPIConnector.          BC-001:, _simulated_carrier_data()

### Community 543 - "Community 543"
Cohesion: 0.29
Nodes (3): CodeBlockFormatter, Model-Specific Response Formatters (SG-26)  15 response formatters that normaliz, 6. Format code blocks with language tags and syntax.

### Community 544 - "Community 544"
Cohesion: 0.29
Nodes (5): PaginatedResponseSchema, PaginationRequest, PARWA Pagination Schemas (API Layer)  Pydantic models for paginated request/resp, Standard JSON envelope for every paginated API response.      This is the **seri, Query-parameter model for paginated list endpoints.      Consumers pass ``offset

### Community 545 - "Community 545"
Cohesion: 0.33
Nodes (4): AuthContext, AuthProviderProps, getCookie(), readUserData()

### Community 546 - "Community 546"
Cohesion: 0.33
Nodes (5): CircuitBreakerConfig, get_circuit_breaker_manager(), Register a new circuit breaker.          If a breaker with the same name already, Configuration for a single circuit breaker.      Attributes:         failure_thr, Get the singleton CircuitBreakerManager instance.      Registers default depende

### Community 547 - "Community 547"
Cohesion: 0.29
Nodes (3): AssignmentEvent, Immutable record of an assignment event., Assign a single ticket and emit lifecycle events.

### Community 548 - "Community 548"
Cohesion: 0.33
Nodes (4): _now_utc(), Activate a session after payment verification., End an active demo session and return a summary., Must be called while holding ``self._lock``.

### Community 549 - "Community 549"
Cohesion: 0.29
Nodes (5): DataRetentionPolicy, ErasureRequest, GDPR & Data Lifecycle Models: erasure_requests, data_retention_policies.  BC-001, Tracks GDPR right-to-erasure requests and their execution status.      BC-010: E, Data retention policies per company and data category.      Enforces GDPR_RETENT

### Community 550 - "Community 550"
Cohesion: 0.29
Nodes (5): Shadow Mode Models: Tables for the SHADOW→SUPERVISED→GRADUATED pipeline.  Tables, Comparison result between live and shadow variant responses.      Each row repre, Per-company shadow mode configuration.      Controls which variant is being "sha, ShadowModeConfig, ShadowModeResult

### Community 551 - "Community 551"
Cohesion: 0.33
Nodes (6): AIStreamingState, StreamingMessage, useAIStreamingStore, useChatStream(), UseChatStreamOptions, UseChatStreamReturn

### Community 552 - "Community 552"
Cohesion: 0.29
Nodes (4): DEFAULT_DEMO_CALL_STATE, DEFAULT_HANDOFF_STATE, DEFAULT_OTP_STATE, DEFAULT_PAYMENT_STATE

### Community 553 - "Community 553"
Cohesion: 0.29
Nodes (3): ChatErrorBoundary, ChatErrorBoundaryProps, ChatErrorBoundaryState

### Community 554 - "Community 554"
Cohesion: 0.29
Nodes (4): MFASetupData, MFAState, MFAStatus, useMFAStore

### Community 555 - "Community 555"
Cohesion: 0.29
Nodes (5): COMPANY_SIZE_OPTIONS, DetailsFormData, detailsFormSchema, INDUSTRY_OPTIONS, WelcomeStepProps

### Community 556 - "Community 556"
Cohesion: 0.29
Nodes (5): Protocol, Protocol that every webhook parser must satisfy.      A parser receives the raw, WebhookParser, Protocol that every webhook verifier must satisfy.      Returns True if the sign, WebhookVerifier

### Community 557 - "Community 557"
Cohesion: 0.29
Nodes (6): authCtx, jwtFile, loginPage, registerRoute, result, signupPage

### Community 558 - "Community 558"
Cohesion: 0.29
Nodes (6): button, closeButtons, { container }, form, input, inputs

### Community 559 - "Community 559"
Cohesion: 0.29
Nodes (3): { AgentPresenceBadge }, { CollisionBanner }, { TypingIndicator }

### Community 560 - "Community 560"
Cohesion: 0.29
Nodes (4): firstBtn, lastBtn, onEscape, secondBtn

### Community 561 - "Community 561"
Cohesion: 0.29
Nodes (6): after, before, features, fetchPromise, fetchTierPromise, state

### Community 562 - "Community 562"
Cohesion: 0.60
Nodes (5): create_customer(), _customer_to_response(), get_customer(), list_customers(), update_customer()

### Community 563 - "Community 563"
Cohesion: 0.40
Nodes (5): ApiKeyDetector, detect(), detect_category(), PARWA AI — API Key Auto-Detection  Examines an API key string and attempts to de, Stateless utility that matches an API key against known patterns.

### Community 564 - "Community 564"
Cohesion: 0.33
Nodes (5): billing_failure_callback(), PARWA Task Error Callbacks (CL-04 FIX)  Provides error callback functions that c, Error callback for SLA tasks.      CL-04 FIX: When an SLA task permanently fails, Error callback for billing tasks.      CL-04 FIX: When a billing task permanentl, sla_failure_callback()

### Community 565 - "Community 565"
Cohesion: 0.33
Nodes (5): cleanup_event_buffer_task(), fanout_event_task(), PARWA Event Tasks (BC-004, BC-005)  Celery tasks for asynchronous event emission, Periodic cleanup of old events from the event buffer.      BC-005: Event buffer, Fan-out an event to a tenant's connected clients.      Uses async event emission

### Community 566 - "Community 566"
Cohesion: 0.33
Nodes (5): execute_command_async(), prune_command_history(), PARWA Jarvis Command Celery Tasks (Phase 3 Command Layer)  Celery tasks that ena, Periodic cleanup of old command records.      Runs every 6 hours via Celery Beat, Execute a command asynchronously via Celery.      Used for commands that may tak

### Community 567 - "Community 567"
Cohesion: 0.33
Nodes (5): _confidence_bucket(), ConfidenceDistribution, Map a confidence score to its bucket label., Get confidence score distribution for a time window., Confidence score distribution across buckets.

### Community 568 - "Community 568"
Cohesion: 0.33
Nodes (5): GuardrailLayerBreakdown, GuardrailStats, Aggregated guardrail statistics., Get guardrail pass/block/flag statistics., Per-layer guardrail statistics.

### Community 569 - "Community 569"
Cohesion: 0.33
Nodes (4): ProviderComparison, Side-by-side provider comparison., Compare providers side by side., Get unique providers seen in a time window.

### Community 570 - "Community 570"
Cohesion: 0.33
Nodes (5): _estimate_tokens(), _now_utc(), Return current UTC timestamp as ISO string., Estimate token count from text (rough: ~4 chars per token)., Record a complete query lifecycle for monitoring.          This is the master re

### Community 571 - "Community 571"
Cohesion: 0.33
Nodes (3): Get the current lifecycle data as a snapshot dict.          Returns a point-in-t, Check if a lifecycle is currently running (not terminal).          Args:, Retrieve a lifecycle by ID and verify company ownership.          Args:

### Community 572 - "Community 572"
Cohesion: 0.33
Nodes (3): Get circuit breaker status for monitoring., Get states of all circuit breakers.          Returns a dict mapping dependency n, Get Prometheus-compatible metrics for all circuit breakers.          Returns a d

### Community 573 - "Community 573"
Cohesion: 0.33
Nodes (4): Reset the circuit breaker to CLOSED state., Reset all circuit breakers (useful for testing)., Reset the singleton manager (for testing only)., reset_circuit_breaker_manager()

### Community 574 - "Community 574"
Cohesion: 0.33
Nodes (3): Validate payload against schema. Returns cleaned payload., Get event type by string, or None if not found., Validate event type and payload. Returns cleaned payload.

### Community 575 - "Community 575"
Cohesion: 0.33
Nodes (4): EscalationRule, Rule defining when and how to escalate.      Each rule maps a trigger type to co, Initialize the escalation manager with default rules and state.          Sets up, Register all built-in default escalation rules.          Covers the 10 standard

### Community 576 - "Community 576"
Cohesion: 0.33
Nodes (3): List all active (non-resolved) escalations for a company.          Returns recor, Filter escalations by severity level.          Returns all active escalations ma, Auto-resolve escalations that have exceeded the auto-resolve threshold.

### Community 577 - "Community 577"
Cohesion: 0.33
Nodes (4): _parse_iso(), Check if a cooldown is active for a specific trigger.          Automatically cle, Generate escalation analytics for a company.          Computes aggregate statist, Parse an ISO-8601 timestamp string to a datetime object.

### Community 578 - "Community 578"
Cohesion: 0.33
Nodes (4): InstanceInfo, Serialise to dictionary for API responses., Register a new variant instance for load-aware distribution.          If an inst, Runtime information about a single variant instance.      Attributes:         in

### Community 579 - "Community 579"
Cohesion: 0.33
Nodes (3): Find which instance a session key is pinned to.          Returns ``None`` if no, Update last_used to now, refreshing the session., Attempt to route via an existing sticky session.          Checks ticket_id first

### Community 580 - "Community 580"
Cohesion: 0.33
Nodes (4): Pin a session key (ticket_id or customer_id) to an instance.          Future cal, Internal sticky session registration (caller must hold lock)., Maps a session key to a specific instance.      Attributes:         session_key:, StickySession

### Community 581 - "Community 581"
Cohesion: 0.33
Nodes (4): FormattingResult, Result of applying one or more formatters., Serialize to dictionary., Apply multiple formatters in sequence.          Args:             response: Text

### Community 582 - "Community 582"
Cohesion: 0.33
Nodes (2): MigrationAuditLogger, Persistent audit trail for migration state changes.      Each entry is a JSON-se

### Community 583 - "Community 583"
Cohesion: 0.33
Nodes (5): _parse_iso(), Parse an ISO timestamp string, returning None on failure., Return seconds elapsed since a timestamp, or infinity if invalid., Attempt to recover a disabled/failing provider., _seconds_since()

### Community 584 - "Community 584"
Cohesion: 0.33
Nodes (3): Get healing rules for a company. Returns defaults if none set., Record a query result and check if healing is needed.          This is the main, Run all healing checks and return actions taken.

### Community 585 - "Community 585"
Cohesion: 0.40
Nodes (4): EmpathySignalDetector, Detects specific empathy signals in customer messages., Return list of detected empathy signal types., Detect if this is a repeated contact (similar messages in history).

### Community 586 - "Community 586"
Cohesion: 0.33
Nodes (5): AgentProfile, create_agents(), Generate *n* dummy agents (handy for demos / tests)., Serialise to plain dict (useful for JSON APIs / caching)., Immutable view of a support agent at a point in time.

### Community 587 - "Community 587"
Cohesion: 0.33
Nodes (4): create_tickets(), Generate *n* dummy tickets., Rich context for an inbound ticket., TicketContext

### Community 588 - "Community 588"
Cohesion: 0.33
Nodes (4): DeactivationNotice, Create and store a deactivation notice for an admin panel.          The notice l, Notification shown in the admin panel when features are disabled.      Lists whi, Serialise deactivation notice to a plain dict.

### Community 589 - "Community 589"
Cohesion: 0.33
Nodes (3): Get the current capabilities for a ticket's effective variant.          Looks up, Get the list of allowed techniques for a ticket's effective variant.          BC, Check if a specific technique is available for a ticket.          Returns True i

### Community 590 - "Community 590"
Cohesion: 0.33
Nodes (5): _generate_session_id(), PaymentIntent, Lightweight payment intent (Paddle checkout token)., Create a payment intent for the voice demo.          Returns a ``PaymentIntent``, Deterministic-ish session id derived from email + timestamp.

### Community 591 - "Community 591"
Cohesion: 0.33
Nodes (4): CallDetailPanel(), CallDetailPanelProps, statusColors, variantLabels

### Community 592 - "Community 592"
Cohesion: 0.33
Nodes (5): CallHistoryRow(), CallHistoryRowProps, statusBadgeConfig, variantColors, variantLabels

### Community 593 - "Community 593"
Cohesion: 0.33
Nodes (3): CategoryChart(), CategoryChartProps, COLORS

### Community 594 - "Community 594"
Cohesion: 0.33
Nodes (4): KPICard(), KPICardProps, trendColors, variantStyles

### Community 595 - "Community 595"
Cohesion: 0.33
Nodes (3): ResponseTimeChart(), ResponseTimeChartProps, SAMPLE_BUCKETS

### Community 596 - "Community 596"
Cohesion: 0.33
Nodes (5): downgrade(), 013_email_verification_settings: Email verification settings & tokens  Revision, Create email verification settings table., Drop email verification settings table., upgrade()

### Community 597 - "Community 597"
Cohesion: 0.33
Nodes (5): downgrade(), 014_email_verification: Email verification tokens & flow  Revision ID: 014_email, Create email verification tokens table., Drop email verification tokens table., upgrade()

### Community 598 - "Community 598"
Cohesion: 0.33
Nodes (5): downgrade(), Add business_email_otps table  Week 6 Day 10-11: Business Email OTP Verification, Create business_email_otps table., Drop business_email_otps table., upgrade()

### Community 599 - "Community 599"
Cohesion: 0.33
Nodes (3): User Details Model: Post-payment details collection  Week 6 Day 1: Collect user, Post-payment user details for onboarding.      Created after successful Paddle p, UserDetails

### Community 600 - "Community 600"
Cohesion: 0.33
Nodes (2): UseCollisionDetectionOptions, UseCollisionDetectionReturn

### Community 601 - "Community 601"
Cohesion: 0.33
Nodes (1): UsePresenceReturn

### Community 602 - "Community 602"
Cohesion: 0.33
Nodes (3): TypingUser, UseTypingIndicatorOptions, UseTypingIndicatorReturn

### Community 603 - "Community 603"
Cohesion: 0.33
Nodes (5): CATEGORY_LABELS, FALLBACK_SUGGESTIONS, IndustrySuggestion, IndustrySuggestionCard(), IndustrySuggestionCardProps

### Community 604 - "Community 604"
Cohesion: 0.33
Nodes (4): GSDStep, GSDStepType, JarvisTerminalFeedProps, STEP_CONFIG

### Community 605 - "Community 605"
Cohesion: 0.33
Nodes (1): PipelineInsightCardProps

### Community 606 - "Community 606"
Cohesion: 0.33
Nodes (3): AppState, Page, useAppStore

### Community 607 - "Community 607"
Cohesion: 0.33
Nodes (4): expiryTimers, TypingState, TypingUser, useTypingStore

### Community 608 - "Community 608"
Cohesion: 0.33
Nodes (4): AISetupStepProps, Prerequisite, STYLE_OPTIONS, TONE_OPTIONS

### Community 609 - "Community 609"
Cohesion: 0.33
Nodes (4): CATEGORIES, INTEGRATION_PROVIDERS, IntegrationProvider, IntegrationStepProps

### Community 610 - "Community 610"
Cohesion: 0.33
Nodes (3): Upload and store an attachment.          Args:             ticket_id: Ticket ID, Get MIME type from extension when magic is not available.                  Args:, Validate a file attachment.          BL06: Checks extension whitelist, size limi

### Community 611 - "Community 611"
Cohesion: 0.33
Nodes (6): _command_to_dict(), get_command_by_id(), get_command_history(), Get paginated command history for a session.      Returns commands in reverse ch, Get a single command by ID with full audit details.      Args:         db: SQLAl, Convert a JarvisCommand ORM instance to a dict for API response.      Args:

### Community 612 - "Community 612"
Cohesion: 0.33
Nodes (6): execute_quick_command(), get_quick_commands(), _infer_target(), Execute a quick command preset by ID.      Quick commands skip NL parsing — they, Infer the command target from the action name.      Args:         action: The ma, Get quick command presets for a session (default + product + custom).      Retur

### Community 614 - "Community 614"
Cohesion: 0.33
Nodes (3): Record a success for a service., Attempt Redis reconnection.          Tries to re-establish Redis connection with, Reset database connection pool.          Disposes the current SQLAlchemy engine

### Community 615 - "Community 615"
Cohesion: 0.33
Nodes (4): Get current shadow mode status for a company.          Tries Redis first, then D, Current shadow mode status for a company., Serialize to dict for API responses., ShadowModeStatus

### Community 616 - "Community 616"
Cohesion: 0.33
Nodes (3): Set ticket tags (replace all existing).          Args:             ticket_id: Ti, Clean and validate tags.          Args:             tags: Raw tags list, Add tags to a ticket.          Args:             ticket_id: Ticket ID

### Community 617 - "Community 617"
Cohesion: 0.47
Nodes (5): ApiKey, getInitials(), getPasswordStrength(), NotificationSettings, SettingsPage()

### Community 618 - "Community 618"
Cohesion: 0.47
Nodes (5): callLLM(), generateFallbackResponse(), POST(), SolveRequest, VARIANT_CONFIG

### Community 619 - "Community 619"
Cohesion: 0.33
Nodes (3): tierDescriptions, tierNames, VariantInstance

### Community 620 - "Community 620"
Cohesion: 0.33
Nodes (5): event, handler, input, spy, { unmount }

### Community 621 - "Community 621"
Cohesion: 0.33
Nodes (4): found, mockData, pending, store

### Community 622 - "Community 622"
Cohesion: 0.33
Nodes (5): found, mockData, notif, store, systemNotifs

### Community 623 - "Community 623"
Cohesion: 0.40
Nodes (3): PARWA Request Logger Middleware (BC-012)  Logs every request with: method, path,, Record dashboard activity to the Activity Store for Jarvis awareness.      This, _record_dashboard_activity()

### Community 624 - "Community 624"
Cohesion: 0.40
Nodes (3): _extract_company_id_from_jwt(), PARWA Tenant Middleware (BC-001)  Extracts company_id from JWT token and ensures, Extract company_id from JWT Authorization header.      This is a fallback for wh

### Community 625 - "Community 625"
Cohesion: 0.40
Nodes (1): ChannelMeta

### Community 626 - "Community 626"
Cohesion: 0.40
Nodes (2): ChatWidgetProps, Message

### Community 627 - "Community 627"
Cohesion: 0.40
Nodes (3): AgentPresenceBadgeProps, statusColors, statusLabels

### Community 629 - "Community 629"
Cohesion: 0.40
Nodes (1): LockedFeatureProps

### Community 630 - "Community 630"
Cohesion: 0.40
Nodes (3): Stub optimizer for fallback., Optimize a DSPy module with an optimizer.          Args:             module: DSP, StubOptimizer

### Community 631 - "Community 631"
Cohesion: 0.40
Nodes (3): Reset token counters for all instances of a company if the UTC day changed., Update live load metrics for an instance.          Args:             company_id:, _utc_today_str()

### Community 632 - "Community 632"
Cohesion: 0.40
Nodes (4): ActiveCallCard(), ActiveCallCardProps, statusConfig, variantColors

### Community 633 - "Community 633"
Cohesion: 0.40
Nodes (4): ChannelCard(), ChannelCardProps, channelCategoryColors, channelIcons

### Community 634 - "Community 634"
Cohesion: 0.40
Nodes (2): TrendChart(), TrendChartProps

### Community 635 - "Community 635"
Cohesion: 0.40
Nodes (3): BookDemoModalProps, INDUSTRIES, TIME_SLOTS

### Community 636 - "Community 636"
Cohesion: 0.40
Nodes (3): DEFAULT_STATE, UseDemoVariantReturn, UseDemoVariantState

### Community 637 - "Community 637"
Cohesion: 0.40
Nodes (2): FOCUSABLE_SELECTORS, FocusTrapOptions

### Community 638 - "Community 638"
Cohesion: 0.40
Nodes (4): ActionTicketCard(), ActionTicketCardProps, STATUS_CONFIG, TYPE_LABELS

### Community 639 - "Community 639"
Cohesion: 0.40
Nodes (3): CardStage, DemoCallCard(), DemoCallCardProps

### Community 640 - "Community 640"
Cohesion: 0.40
Nodes (4): CATEGORY_CONFIG, ProviderInfo, ProviderSelectorCard(), ProviderSelectorCardProps

### Community 641 - "Community 641"
Cohesion: 0.40
Nodes (4): CollisionAction, CollisionState, CollisionUser, useCollisionStore

### Community 642 - "Community 642"
Cohesion: 0.40
Nodes (4): AgentPresence, AgentStatus, PresenceState, usePresenceStore

### Community 645 - "Community 645"
Cohesion: 0.50
Nodes (2): Alert(), alertVariants

### Community 650 - "Community 650"
Cohesion: 0.40
Nodes (4): agent, agentsPromise, fetchPromise, total

### Community 651 - "Community 651"
Cohesion: 0.40
Nodes (3): agent, mockFetch, online

### Community 652 - "Community 652"
Cohesion: 0.50
Nodes (1): Alembic environment configuration.  Imports all models so autogenerate detects t

### Community 653 - "Community 653"
Cohesion: 0.50
Nodes (2): inter, metadata

### Community 655 - "Community 655"
Cohesion: 0.50
Nodes (3): Async DB Helper (S-08 fix)  Provides utilities to run synchronous SQLAlchemy ope, Run a synchronous DB function in a thread pool.      Moves the entire DB operati, run_sync_db()

### Community 656 - "Community 656"
Cohesion: 0.50
Nodes (3): PARWA Email Template Renderer (BC-006)  Renders Jinja2 email templates for trans, Render a Jinja2 email template with context.      Args:         template_name: T, render_email_template()

### Community 657 - "Community 657"
Cohesion: 0.50
Nodes (3): HMAC Verification Utility (BC-003, BC-011)  DEPRECATED: This module is a thin wr, Generic HMAC verification with constant-time comparison.      Delegates to verif, verify_hmac_signature()

### Community 658 - "Community 658"
Cohesion: 0.50
Nodes (3): channel_delivery_node(), Channel Delivery Node — Group 10: Channel Dispatch Routing  Routes the agent res, Channel Delivery Node — Routes response to the appropriate delivery channel.

### Community 659 - "Community 659"
Cohesion: 0.50
Nodes (3): get_rate_limiter(), PARWA Rate Limit Middleware (BC-012 / F-018)  Enhanced middleware using per-endp, Get the shared rate limit service (compat wrapper).

### Community 660 - "Community 660"
Cohesion: 0.50
Nodes (3): escalation_agent_node(), PARWA Jarvis Escalation Agent Node  Handles situations where tickets or issues n, Escalation agent: decides how to escalate critical issues.      Uses ZAI SDK to

### Community 661 - "Community 661"
Cohesion: 0.50
Nodes (3): notification_agent_node(), PARWA Jarvis Notification Agent Node  Handles proactive notifications to users., Notification agent: crafts and sends proactive notifications.      Uses ZAI SDK

### Community 662 - "Community 662"
Cohesion: 0.50
Nodes (3): quality_recovery_agent_node(), PARWA Jarvis Quality Recovery Agent Node  Handles quality score drops and model, Quality Recovery agent: recovers from quality drops.      Uses ZAI SDK to analyz

### Community 663 - "Community 663"
Cohesion: 0.50
Nodes (3): PARWA Jarvis Reassignment Agent Node  Handles ticket load balancing and agent re, Reassignment agent: balances ticket load across agents.      Uses ZAI SDK to ana, reassignment_agent_node()

### Community 664 - "Community 664"
Cohesion: 0.50
Nodes (3): PARWA Jarvis SLA Protection Agent Node  Prevents SLA breaches by identifying at-, SLA Protection agent: prevents SLA breaches.      Uses ZAI SDK to analyze at-ris, sla_protection_agent_node()

### Community 665 - "Community 665"
Cohesion: 0.50
Nodes (3): process_paddle_webhook(), Example Webhook Task (Week 5 placeholder)  Paddle webhook processing task. Logs, Process a Paddle webhook event.      This is a placeholder implementation that l

### Community 666 - "Community 666"
Cohesion: 0.50
Nodes (1): Politeness

### Community 667 - "Community 667"
Cohesion: 0.50
Nodes (3): Token usage metrics (estimated from text length)., Get estimated token usage statistics., TokenUsageMetrics

### Community 668 - "Community 668"
Cohesion: 0.50
Nodes (3): CustomerInteractionSummary, Return a comprehensive summary of a customer's recent         interactions acros, Summary of a customer's recent interactions across all variants     and channels

### Community 669 - "Community 669"
Cohesion: 0.50
Nodes (3): Set a labeled gauge value., Update database pool size gauge.      Args:         used: Number of connections, update_db_pool()

### Community 670 - "Community 670"
Cohesion: 0.50
Nodes (3): FallbackTemplate, Fallback response template for a specific intent.      When AI cannot generate a, Register a custom fallback template for a company.          Custom templates are

### Community 671 - "Community 671"
Cohesion: 0.50
Nodes (2): Internal safe scan with Redis + DB integration., Fetch rate limit count and tenant blocklist from Redis.          BC-012: Redis f

### Community 672 - "Community 672"
Cohesion: 0.50
Nodes (4): Check if a Redis key follows the tenant-scoped pattern.      Valid keys must mat, Safely get a Redis key with tenant validation.      Validates that the key follo, safe_get(), validate_tenant_key()

### Community 673 - "Community 673"
Cohesion: 0.50
Nodes (4): Filter a list of keys to only include those matching the current tenant.      Re, Safely get multiple Redis keys with tenant validation.      Filters keys through, safe_mget(), validate_tenant_keys()

### Community 674 - "Community 674"
Cohesion: 0.50
Nodes (2): MigrationConfig, Per-tenant, per-feature migration configuration.

### Community 675 - "Community 675"
Cohesion: 0.50
Nodes (3): EmotionClassifier, Classifies text into one of 6 emotion types., Classify emotion and return breakdown scores.          Returns (primary_emotion,

### Community 676 - "Community 676"
Cohesion: 0.50
Nodes (3): Recommends response tone based on frustration + emotion., Recommend response tone.          Rules:         - De-escalation: frustration >=, ToneAdvisor

### Community 677 - "Community 677"
Cohesion: 0.50
Nodes (2): Get time spent in a specific state for a ticket.          Calculates duration fr, Get GSD analytics for a company.          Includes state distribution, average d

### Community 678 - "Community 678"
Cohesion: 0.50
Nodes (2): Get the full capability profile for a specific variant type.          Returns mi, Compare two variants' capabilities side by side.          Returns a dict with co

### Community 679 - "Community 679"
Cohesion: 0.50
Nodes (3): DemoSummary, Summary of a completed voice demo session., Get a summary for any session (active or completed).

### Community 680 - "Community 680"
Cohesion: 0.50
Nodes (3): Result of a refund attempt., Attempt a refund (placeholder — always succeeds in demo mode).          In produ, RefundResult

### Community 681 - "Community 681"
Cohesion: 0.67
Nodes (3): formatMinutes(), SLAChart(), SLAChartProps

### Community 682 - "Community 682"
Cohesion: 0.50
Nodes (1): SystemHealthMonitor()

### Community 683 - "Community 683"
Cohesion: 0.50
Nodes (2): VoiceConfigCard(), VoiceConfigCardProps

### Community 684 - "Community 684"
Cohesion: 0.50
Nodes (2): WelcomeCard(), WelcomeCardProps

### Community 685 - "Community 685"
Cohesion: 0.50
Nodes (1): 001_initial_schema: Core tables (companies, users, api_keys, sessions, etc.)  Re

### Community 686 - "Community 686"
Cohesion: 0.50
Nodes (1): 002_ticketing_tables: Tickets, TicketMessages, Customers, Channels + Week 4 tabl

### Community 687 - "Community 687"
Cohesion: 0.50
Nodes (1): 003_ai_pipeline_tables: api_providers, service_configs, gsd_sessions, confidence

### Community 688 - "Community 688"
Cohesion: 0.50
Nodes (1): 004_integration_tables: integrations, connectors, MCP, DB connections, etc.  Rev

### Community 689 - "Community 689"
Cohesion: 0.50
Nodes (1): 005_audit_billing_tables: audit_trail, webhook_events, rate_limit_events, api_ke

### Community 690 - "Community 690"
Cohesion: 0.50
Nodes (1): 006_analytics_onboarding_tables: metric_aggregates, roi_snapshots, drift_reports

### Community 691 - "Community 691"
Cohesion: 0.50
Nodes (1): 007_remaining_gap_tables: approval_queues, auto_approve_rules, executed_actions,

### Community 692 - "Community 692"
Cohesion: 0.50
Nodes (1): 008_technique_tables: technique_configurations, technique_executions, technique_

### Community 693 - "Community 693"
Cohesion: 0.50
Nodes (1): Billing Extended Tables Migration (009)  Creates 8 new tables for extended billi

### Community 694 - "Community 694"
Cohesion: 0.50
Nodes (1): 010_onboarding_extended: user_details table + extend onboarding_sessions  Revisi

### Community 695 - "Community 695"
Cohesion: 0.50
Nodes (1): 011_phase3_variant_engine: 9 tables for Phase 3 AI Engine  Revision ID: 011 Revi

### Community 696 - "Community 696"
Cohesion: 0.50
Nodes (1): 012_jarvis_system: Jarvis onboarding chat system  Revision ID: 012 Revises: 011

### Community 697 - "Community 697"
Cohesion: 0.50
Nodes (1): 013_some_migration: Stub migration bridging 012 to 014  Revision ID: 013_some_mi

### Community 698 - "Community 698"
Cohesion: 0.50
Nodes (1): Alembic migration 016: Email channel tables.  Week 13 Day 1 (F-121: Email Inboun

### Community 699 - "Community 699"
Cohesion: 0.50
Nodes (1): Week 13 Day 2: Outbound email tracking table  Revision ID: 017_outbound_email Re

### Community 700 - "Community 700"
Cohesion: 0.50
Nodes (1): Week 13 Day 3: Email delivery events table  Revision ID: 018_email_delivery_even

### Community 701 - "Community 701"
Cohesion: 0.50
Nodes (1): Week 13 Day 3: OOO detection tables and email bounces tables  Revision ID: 019_o

### Community 702 - "Community 702"
Cohesion: 0.50
Nodes (1): 020_jarvis_cc_tables: Jarvis Customer Care persistence  Revision ID: 020 Revises

### Community 703 - "Community 703"
Cohesion: 0.50
Nodes (1): 023_paddle_reconciliation: Paddle webhook reconciliation tables  Revision ID: 02

### Community 704 - "Community 704"
Cohesion: 0.50
Nodes (1): Shadow Mode tables for Phase 4 Feature Completion.  Creates:   - shadow_mode_con

### Community 705 - "Community 705"
Cohesion: 0.50
Nodes (1): Add scheduled_change_type, scheduled_change_variant, metadata_json to subscripti

### Community 706 - "Community 706"
Cohesion: 0.50
Nodes (1): Production indexes and constraints  Revision ID: 025 Revises: 024 Create Date: 2

### Community 707 - "Community 707"
Cohesion: 0.50
Nodes (1): Activity Store full awareness coverage  Add new event categories for shadow_mode

### Community 708 - "Community 708"
Cohesion: 0.50
Nodes (1): Voice channel tables.  Creates:   - voice_calls: Voice call tracking with Twilio

### Community 709 - "Community 709"
Cohesion: 0.50
Nodes (1): Create activity_log table for Jarvis non-agentic awareness  Revision ID: 027 Rev

### Community 710 - "Community 710"
Cohesion: 0.50
Nodes (2): Detect billing anomalies by comparing against expected patterns.          Args:, Generate recommendation based on anomaly types.

### Community 711 - "Community 711"
Cohesion: 0.50
Nodes (2): Classify the billing dispute type and assess auto-resolution eligibility., Return default dispute classification.

### Community 712 - "Community 712"
Cohesion: 0.50
Nodes (2): Initialize the billing intelligence engine., Pre-compile regex patterns for performance.

### Community 713 - "Community 713"
Cohesion: 0.50
Nodes (2): Initialize the churn retention engine., Pre-compile regex patterns for performance.

### Community 714 - "Community 714"
Cohesion: 0.50
Nodes (2): Score churn risk based on multiple signals.          Args:             query: Cu, Return default low-risk churn assessment.

### Community 715 - "Community 715"
Cohesion: 0.50
Nodes (2): Select optimal retention offers using ToT-branching logic.          Generates mu, Generate prompt addition for LLM retention context.

### Community 716 - "Community 716"
Cohesion: 0.50
Nodes (2): Generate a win-back automation sequence for post-cancellation.          Args:, Map a churn reason to the best win-back offer.

### Community 717 - "Community 717"
Cohesion: 0.50
Nodes (2): Initialize the EI engine., Pre-compile regex patterns for performance.

### Community 718 - "Community 718"
Cohesion: 0.50
Nodes (2): Build a multi-dimensional emotion profile from the customer query.          Args, Return a default neutral emotion profile.

### Community 719 - "Community 719"
Cohesion: 0.50
Nodes (2): Initialize the shipping intelligence engine., Pre-compile regex patterns for performance.

### Community 720 - "Community 720"
Cohesion: 0.50
Nodes (2): Classify the type of shipping issue from the customer query.          Args:, Return default no-issue result.

### Community 721 - "Community 721"
Cohesion: 0.50
Nodes (2): Assess shipping delay and generate proactive notification.          Args:, Return default no-delay result.

### Community 722 - "Community 722"
Cohesion: 0.50
Nodes (2): Initialize the tech diagnostics engine., Pre-compile regex patterns for performance.

### Community 723 - "Community 723"
Cohesion: 0.50
Nodes (2): Detect if the query matches a known issue in the knowledge base.          Args:, Return default no-known-issue result.

### Community 724 - "Community 724"
Cohesion: 0.50
Nodes (2): Generate step-by-step diagnostic guidance for the customer.          Args:, Generate diagnostic context prompt for the LLM.

### Community 725 - "Community 725"
Cohesion: 0.50
Nodes (2): Score the escalation severity of a technical issue.          Multi-factor scorin, Return default low severity result.

### Community 726 - "Community 726"
Cohesion: 0.50
Nodes (1): Step

### Community 727 - "Community 727"
Cohesion: 0.83
Nodes (3): generateOTP(), getOTPEmailHTML(), POST()

### Community 728 - "Community 728"
Cohesion: 0.67
Nodes (3): KeyboardShortcutDef, useKeyboardShortcut(), useKeyboardShortcuts()

### Community 729 - "Community 729"
Cohesion: 0.50
Nodes (2): PollingOptions, PollingState

### Community 730 - "Community 730"
Cohesion: 0.50
Nodes (2): RetryOptions, RetryState

### Community 731 - "Community 731"
Cohesion: 0.50
Nodes (2): PaymentCard(), PaymentCardProps

### Community 733 - "Community 733"
Cohesion: 0.50
Nodes (2): MATRIX_ROWS, MatrixRow

### Community 734 - "Community 734"
Cohesion: 0.50
Nodes (1): TOAST_BG

### Community 735 - "Community 735"
Cohesion: 0.50
Nodes (2): CONSENT_CARDS, LegalConsentStepProps

### Community 736 - "Community 736"
Cohesion: 0.83
Nodes (3): GET(), POST(), proxyToBackend()

### Community 737 - "Community 737"
Cohesion: 0.50
Nodes (2): trustBadges, variantData

### Community 738 - "Community 738"
Cohesion: 0.50
Nodes (2): ProfilePage(), UserProfile

### Community 739 - "Community 739"
Cohesion: 0.50
Nodes (4): Verify Paddle webhook signature (HMAC-SHA256).      Paddle sends the signature i, Verify HMAC-SHA256 signature from a request header.      Computes HMAC-SHA256 of, verify_hmac_sha256(), verify_paddle()

### Community 740 - "Community 740"
Cohesion: 0.50
Nodes (2): Get routing rules for a category.          Args:             category: Category, Validate that category requirements are met.          Args:             category

### Community 741 - "Community 741"
Cohesion: 0.50
Nodes (2): Get all notification preferences for a user.                  Returns preference, Get digest settings from user metadata.

### Community 742 - "Community 742"
Cohesion: 0.50
Nodes (2): Check Celery queue depths for anomalies., Check if queue depth exceeds threshold.          Args:             queue: Queue

### Community 743 - "Community 743"
Cohesion: 0.50
Nodes (2): Record a healing action in the audit trail., Attempt to heal a specific anomaly.          Routes to the appropriate healing m

### Community 744 - "Community 744"
Cohesion: 0.50
Nodes (2): Suggest tags based on text content.          Args:             text: Text to ana, Generate automatic tags from text content.          Args:             text: Text

### Community 745 - "Community 745"
Cohesion: 0.50
Nodes (2): PS05: Check for duplicate tickets.          Args:             customer_id: Custo, Calculate similarity between two strings.          Simple Jaccard similarity on

### Community 746 - "Community 746"
Cohesion: 0.50
Nodes (3): { container }, lockElement, upgradeLink

### Community 751 - "Community 751"
Cohesion: 0.50
Nodes (1): ToggleGroupContext

### Community 752 - "Community 752"
Cohesion: 0.50
Nodes (3): fetchTierSpy, fetchUsageSpy, { result }

### Community 753 - "Community 753"
Cohesion: 0.50
Nodes (3): billingPromise, changePromise, fetchPromise

### Community 754 - "Community 754"
Cohesion: 0.50
Nodes (3): collisions, editors, users

### Community 755 - "Community 755"
Cohesion: 0.67
Nodes (1): Mini LLM Client — Lightweight LLM wrapper for Mini Parwa nodes.  Day 3 (AI Core)

### Community 756 - "Community 756"
Cohesion: 0.67
Nodes (1): PARWA Security utilities package.

### Community 758 - "Community 758"
Cohesion: 0.67
Nodes (1): prisma

### Community 759 - "Community 759"
Cohesion: 0.67
Nodes (1): CallsDashboardPage()

### Community 760 - "Community 760"
Cohesion: 0.67
Nodes (1): UserMenuProps

### Community 761 - "Community 761"
Cohesion: 0.67
Nodes (1): CollisionBannerProps

### Community 762 - "Community 762"
Cohesion: 0.67
Nodes (1): DemoBannerProps

### Community 763 - "Community 763"
Cohesion: 0.67
Nodes (1): SkipLinkProps

### Community 764 - "Community 764"
Cohesion: 0.67
Nodes (1): TypingIndicatorProps

### Community 765 - "Community 765"
Cohesion: 0.67
Nodes (2): DisambiguationFormatter, 13. Add 'Did you mean?' suggestions for ambiguous queries.      This formatter i

### Community 766 - "Community 766"
Cohesion: 0.67
Nodes (2): EmojiFormatter, 10. Strip/normalize emojis based on formality level.

### Community 767 - "Community 767"
Cohesion: 0.67
Nodes (2): EscalationFormatter, 15. Format escalation notices with priority and context.

### Community 768 - "Community 768"
Cohesion: 0.67
Nodes (2): LinkFormatter, 9. Validate and format URLs.

### Community 769 - "Community 769"
Cohesion: 0.67
Nodes (2): ListFormatter, 7. Normalize bullet/numbered lists.

### Community 770 - "Community 770"
Cohesion: 0.67
Nodes (2): MarkdownFormatter, 2. Normalize markdown — fix broken lists, headers, links.

### Community 771 - "Community 771"
Cohesion: 0.67
Nodes (2): 4. Adjust tone (professional/friendly/casual).      Applies light transformation, ToneFormatter

### Community 773 - "Community 773"
Cohesion: 0.67
Nodes (1): NetworkStatus

### Community 774 - "Community 774"
Cohesion: 0.67
Nodes (1): UseShadowModeReturn

### Community 775 - "Community 775"
Cohesion: 0.67
Nodes (1): UseSocketReturn

### Community 776 - "Community 776"
Cohesion: 0.67
Nodes (1): UseVariantReturn

### Community 778 - "Community 778"
Cohesion: 0.67
Nodes (1): BillSummaryProps

### Community 779 - "Community 779"
Cohesion: 0.67
Nodes (2): MessageCounter(), MessageCounterProps

### Community 780 - "Community 780"
Cohesion: 0.67
Nodes (2): OtpVerificationCard(), OtpVerificationCardProps

### Community 781 - "Community 781"
Cohesion: 0.67
Nodes (2): PackExpiredCard(), PackExpiredCardProps

### Community 783 - "Community 783"
Cohesion: 0.67
Nodes (2): PostCallSummaryCard(), PostCallSummaryCardProps

### Community 785 - "Community 785"
Cohesion: 0.67
Nodes (1): DogfoodingBannerProps

### Community 786 - "Community 786"
Cohesion: 0.67
Nodes (1): shadowModeApi

### Community 787 - "Community 787"
Cohesion: 0.67
Nodes (1): voiceApi

### Community 788 - "Community 788"
Cohesion: 0.67
Nodes (1): MonitoringMetric

### Community 789 - "Community 789"
Cohesion: 0.67
Nodes (1): FirstVictoryCelebrationProps

### Community 791 - "Community 791"
Cohesion: 1.00
Nodes (2): POST(), sanitizeEmailContent()

### Community 793 - "Community 793"
Cohesion: 0.67
Nodes (1): phaseSteps

### Community 794 - "Community 794"
Cohesion: 0.67
Nodes (1): VerifyState

### Community 795 - "Community 795"
Cohesion: 1.00
Nodes (2): Badge(), badgeVariants

### Community 796 - "Community 796"
Cohesion: 1.00
Nodes (2): Button(), buttonVariants

### Community 800 - "Community 800"
Cohesion: 1.00
Nodes (2): Toggle(), toggleVariants

### Community 801 - "Community 801"
Cohesion: 0.67
Nodes (2): { result }, { unmount }

### Community 802 - "Community 802"
Cohesion: 0.67
Nodes (2): pages, user

### Community 803 - "Community 803"
Cohesion: 0.67
Nodes (1): mockFetch

### Community 805 - "Community 805"
Cohesion: 1.00
Nodes (1): PARWA API Routes  All FastAPI routers are registered in backend/app/main.py dire

### Community 811 - "Community 811"
Cohesion: 1.00
Nodes (1): High Parwa -- Highest tier of the Parwa Variant Engine (22-node pipeline).  Pipe

### Community 812 - "Community 812"
Cohesion: 1.00
Nodes (1): Pro Parwa — Growth tier of the Parwa Variant Engine (17-node pipeline).  Pipelin

### Community 813 - "Community 813"
Cohesion: 1.00
Nodes (1): CLARA RAG package — Advanced retrieval with HyDE, Multi-Query, and LLM Reranking

### Community 814 - "Community 814"
Cohesion: 1.00
Nodes (1): PARWA Security Headers Middleware.  Adds security headers to all responses per B

### Community 815 - "Community 815"
Cohesion: 1.00
Nodes (1): DEPRECATED: This service has been removed from the production codebase. It had z

### Community 816 - "Community 816"
Cohesion: 1.00
Nodes (1): Notification Template Service - Template management (MF05)  Handles: - CRUD oper

### Community 817 - "Community 817"
Cohesion: 1.00
Nodes (1): DEPRECATED: This service has been removed from the production codebase. It had z

### Community 818 - "Community 818"
Cohesion: 1.00
Nodes (1): DEPRECATED: This service has been removed from the production codebase. It had z

### Community 819 - "Community 819"
Cohesion: 1.00
Nodes (1): PARWA Shared Module  Shared utilities and cross-cutting concerns used across mul

### Community 820 - "Community 820"
Cohesion: 1.00
Nodes (1): PARWA webhook tasks package.

### Community 825 - "Community 825"
Cohesion: 1.00
Nodes (1): Record that a call was attempted (for HALF_OPEN tracking).

### Community 826 - "Community 826"
Cohesion: 1.00
Nodes (1): Return approximate byte size of payload when JSON-serialized.

### Community 828 - "Community 828"
Cohesion: 1.00
Nodes (1): Generate retention negotiation strategy with acceptance likelihood.          Arg

### Community 829 - "Community 829"
Cohesion: 1.00
Nodes (1): Assess if sentiment requires escalation beyond standard handling.          Args:

### Community 830 - "Community 830"
Cohesion: 1.00
Nodes (1): Generate de-escalation prompt additions for the LLM.          Args:

### Community 831 - "Community 831"
Cohesion: 1.00
Nodes (1): Get automated recovery actions to execute.          Args:             emotion_pr

### Community 832 - "Community 832"
Cohesion: 1.00
Nodes (1): Generate deep complaint resolution with strategy and confidence.          Args:

### Community 833 - "Community 833"
Cohesion: 1.00
Nodes (1): Select the appropriate service recovery playbook based on emotion profile.

### Community 834 - "Community 834"
Cohesion: 1.00
Nodes (1): Detect tracking numbers in the customer query.          Args:             query:

### Community 835 - "Community 835"
Cohesion: 1.00
Nodes (1): Get automated shipping resolution actions.          Args:             shipping_i

### Community 836 - "Community 836"
Cohesion: 1.00
Nodes (1): Generate shipping context prompt addition for the LLM.          Args:

### Community 837 - "Community 837"
Cohesion: 1.00
Nodes (1): Generate proactive delay notification for the customer.          Args:

### Community 838 - "Community 838"
Cohesion: 1.00
Nodes (1): Get automated tech support actions.          Args:             known_issue: Outp

### Community 839 - "Community 839"
Cohesion: 1.00
Nodes (1): Generate comprehensive diagnostic result summary.          Args:             que

### Community 840 - "Community 840"
Cohesion: 1.00
Nodes (1): Make escalation decision based on severity, known issues, and customer tier.

### Community 846 - "Community 846"
Cohesion: 1.00
Nodes (1): globalForPrisma

### Community 848 - "Community 848"
Cohesion: 1.00
Nodes (1): PARWA MCP Server package  Model Context Protocol server for external AI tool int

### Community 858 - "Community 858"
Cohesion: 1.00
Nodes (2): parse_shopify(), Parse Shopify webhook payload.

### Community 859 - "Community 859"
Cohesion: 1.00
Nodes (2): parse_twilio(), Parse Twilio webhook payload.

### Community 860 - "Community 860"
Cohesion: 1.00
Nodes (2): Central registry for webhook parsers.      Structure::          {             "p, WebhookParserRegistry

### Community 861 - "Community 861"
Cohesion: 1.00
Nodes (2): Central registry for webhook signature verifiers.      Usage::          WebhookV, WebhookVerifierRegistry

### Community 865 - "Community 865"
Cohesion: 1.00
Nodes (2): NotificationListItem, Single notification item in list response.

### Community 866 - "Community 866"
Cohesion: 1.00
Nodes (2): NotificationPreferenceUpdate, Schema for updating user notification preferences.

### Community 867 - "Community 867"
Cohesion: 1.00
Nodes (2): NotificationSendRequest, Schema for manually sending a notification.

### Community 868 - "Community 868"
Cohesion: 1.00
Nodes (2): NotificationSendResponse, Schema for notification send result.

### Community 869 - "Community 869"
Cohesion: 1.00
Nodes (2): NotificationTemplateCreate, Schema for creating a notification template.

### Community 870 - "Community 870"
Cohesion: 1.00
Nodes (2): NotificationTemplateResponse, Schema for notification template response.

### Community 871 - "Community 871"
Cohesion: 1.00
Nodes (2): NotificationTemplateUpdate, Schema for updating a notification template.

### Community 872 - "Community 872"
Cohesion: 1.00
Nodes (2): Single template item in list response., TemplateListItem

### Community 873 - "Community 873"
Cohesion: 1.00
Nodes (2): DiscountDeletedEvent, discount.deleted event.

### Community 874 - "Community 874"
Cohesion: 1.00
Nodes (2): DiscountUpdatedEvent, discount.updated event.

### Community 875 - "Community 875"
Cohesion: 1.00
Nodes (2): subscription.created event., SubscriptionCreatedEvent

### Community 876 - "Community 876"
Cohesion: 1.00
Nodes (2): subscription.updated event., SubscriptionUpdatedEvent

### Community 877 - "Community 877"
Cohesion: 1.00
Nodes (2): subscription.activated event., SubscriptionActivatedEvent

### Community 878 - "Community 878"
Cohesion: 1.00
Nodes (2): subscription.canceled event., SubscriptionCanceledEvent

### Community 879 - "Community 879"
Cohesion: 1.00
Nodes (2): subscription.past_due event., SubscriptionPastDueEvent

### Community 880 - "Community 880"
Cohesion: 1.00
Nodes (2): subscription.paused event., SubscriptionPausedEvent

### Community 881 - "Community 881"
Cohesion: 1.00
Nodes (2): subscription.resumed event., SubscriptionResumedEvent

### Community 882 - "Community 882"
Cohesion: 1.00
Nodes (2): transaction.completed event., TransactionCompletedEvent

### Community 883 - "Community 883"
Cohesion: 1.00
Nodes (2): transaction.paid event., TransactionPaidEvent

### Community 884 - "Community 884"
Cohesion: 1.00
Nodes (2): transaction.payment_failed event., TransactionPaymentFailedEvent

### Community 885 - "Community 885"
Cohesion: 1.00
Nodes (2): transaction.canceled event., TransactionCanceledEvent

### Community 886 - "Community 886"
Cohesion: 1.00
Nodes (2): transaction.updated event., TransactionUpdatedEvent

### Community 887 - "Community 887"
Cohesion: 1.00
Nodes (2): report.created event., ReportCreatedEvent

### Community 888 - "Community 888"
Cohesion: 1.00
Nodes (2): report.updated event., ReportUpdatedEvent

### Community 889 - "Community 889"
Cohesion: 1.00
Nodes (2): _clear_service_cache(), Clear all cached services (useful for testing).

### Community 890 - "Community 890"
Cohesion: 1.00
Nodes (2): get_entry_context(), Parse URL params into context_json for entry routing.

### Community 891 - "Community 891"
Cohesion: 1.00
Nodes (2): prune_session_context(), Context Hygiene: Removes transient data while preserving core strategic value.

### Community 892 - "Community 892"
Cohesion: 1.00
Nodes (1): Get active template for event type and channel.

### Community 893 - "Community 893"
Cohesion: 1.00
Nodes (1): Get valid variables for an event type.

### Community 894 - "Community 894"
Cohesion: 1.00
Nodes (1): Get all versions of a template.

### Community 895 - "Community 895"
Cohesion: 1.00
Nodes (1): List templates with filters.                  Args:             event_type: Filt

### Community 896 - "Community 896"
Cohesion: 1.00
Nodes (1): Apply proration credit and create audit record.          This records the prorat

### Community 897 - "Community 897"
Cohesion: 1.00
Nodes (1): Calculate effective date for downgrade.          Downgrades are always effective

### Community 898 - "Community 898"
Cohesion: 1.00
Nodes (1): Get proration audit history for a company.          Args:             company_id

### Community 904 - "Community 904"
Cohesion: 1.00
Nodes (1): dashboardLink

### Community 917 - "Community 917"
Cohesion: 1.00
Nodes (1): mockFetch

### Community 923 - "Community 923"
Cohesion: 1.00
Nodes (1): Standardize carrier-specific tracking data to unified format.

### Community 924 - "Community 924"
Cohesion: 1.00
Nodes (1): Return result for unrecognized tracking number.

### Community 925 - "Community 925"
Cohesion: 1.00
Nodes (1): Return result when no tracking data is available.

### Community 926 - "Community 926"
Cohesion: 1.00
Nodes (1): Return result when no delay is detected.

### Community 927 - "Community 927"
Cohesion: 1.00
Nodes (1): Return result when no compensation is eligible.

### Community 928 - "Community 928"
Cohesion: 1.00
Nodes (1): Get current state, checking for automatic transitions.

### Community 929 - "Community 929"
Cohesion: 1.00
Nodes (1): D6-GAP-03: Filter out false positive phone number matches.          Removes matc

### Community 930 - "Community 930"
Cohesion: 1.00
Nodes (1): GAP-018: Sensible defaults for new tenants.

### Community 931 - "Community 931"
Cohesion: 1.00
Nodes (1): True if tenant has explicitly configured custom brand rules.          Considers:

### Community 932 - "Community 932"
Cohesion: 1.00
Nodes (1): Get or create the singleton engine instance.          Returns:             The s

### Community 933 - "Community 933"
Cohesion: 1.00
Nodes (1): Get the default compression level for a variant.          mini_parwa -> NONE

### Community 934 - "Community 934"
Cohesion: 1.00
Nodes (1): Get the default health thresholds for a variant.

### Community 935 - "Community 935"
Cohesion: 1.00
Nodes (1): Build a canonical dict key for a conversation.

### Community 936 - "Community 936"
Cohesion: 1.00
Nodes (1): Run a single handler with timeout enforcement.          Since we cannot easily i

### Community 937 - "Community 937"
Cohesion: 1.00
Nodes (1): Unique string identifier for this handler.

### Community 938 - "Community 938"
Cohesion: 1.00
Nodes (1): Integer priority (lower = runs first).

### Community 939 - "Community 939"
Cohesion: 1.00
Nodes (1): Return True if this handler can handle the given query.          Args:

### Community 940 - "Community 940"
Cohesion: 1.00
Nodes (1): Process the query and return a result.          Args:             query: The use

### Community 941 - "Community 941"
Cohesion: 1.00
Nodes (1): Mask PII value for safe logging.          Args:             value: The raw PII v

### Community 942 - "Community 942"
Cohesion: 1.00
Nodes (1): Dispatch to the appropriate guard check method.          Args:             guard

### Community 943 - "Community 943"
Cohesion: 1.00
Nodes (1): Convert severity to comparable ordinal value.

### Community 944 - "Community 944"
Cohesion: 1.00
Nodes (1): Check if a year is a leap year.

### Community 945 - "Community 945"
Cohesion: 1.00
Nodes (1): Extract factual claim sentences from text.          Returns sentences that conta

### Community 946 - "Community 946"
Cohesion: 1.00
Nodes (1): Quick check if gateway has credentials configured.

### Community 947 - "Community 947"
Cohesion: 1.00
Nodes (1): Maximum concurrent tickets this instance can handle.

### Community 948 - "Community 948"
Cohesion: 1.00
Nodes (1): Daily token budget share for this instance.

### Community 949 - "Community 949"
Cohesion: 1.00
Nodes (1): Current load as a percentage of max capacity.

### Community 950 - "Community 950"
Cohesion: 1.00
Nodes (1): Combined load score factoring in active tickets and queue.          Queued ticke

### Community 951 - "Community 951"
Cohesion: 1.00
Nodes (1): Remaining slots before hitting max concurrent.

### Community 952 - "Community 952"
Cohesion: 1.00
Nodes (1): Whether this instance should receive new traffic.

### Community 953 - "Community 953"
Cohesion: 1.00
Nodes (1): Whether the instance exceeds the overload threshold.

### Community 954 - "Community 954"
Cohesion: 1.00
Nodes (1): Check whether this session has exceeded its TTL.

### Community 955 - "Community 955"
Cohesion: 1.00
Nodes (1): Seconds since creation.

### Community 956 - "Community 956"
Cohesion: 1.00
Nodes (1): Percentage of distributions served by sticky sessions.

### Community 957 - "Community 957"
Cohesion: 1.00
Nodes (1): Return the current UTC time as an ISO-8601 string (BC-012).

### Community 958 - "Community 958"
Cohesion: 1.00
Nodes (1): Return the current UTC date as a YYYY-MM-DD string for token tracking.

### Community 959 - "Community 959"
Cohesion: 1.00
Nodes (1): Build a greeting message based on variant tier and industry.

### Community 960 - "Community 960"
Cohesion: 1.00
Nodes (1): Build a response for a detected customer intent.

### Community 961 - "Community 961"
Cohesion: 1.00
Nodes (1): Build a resolution/summary message based on variant tier and outcome.

### Community 962 - "Community 962"
Cohesion: 1.00
Nodes (1): Build a post-call summary for SMS/voice delivery.

### Community 963 - "Community 963"
Cohesion: 1.00
Nodes (1): Apply a dict of overrides to a dataclass instance.          Only applies keys th

### Community 964 - "Community 964"
Cohesion: 1.00
Nodes (1): Luhn algorithm for credit card validation.

### Community 965 - "Community 965"
Cohesion: 1.00
Nodes (1): Check which integrations are available.

### Community 966 - "Community 966"
Cohesion: 1.00
Nodes (1): Build the Redis hash key: health:{provider}:{model_id}.

### Community 967 - "Community 967"
Cohesion: 1.00
Nodes (1): Return the unique name of this formatter.

### Community 968 - "Community 968"
Cohesion: 1.00
Nodes (1): Format the response text.          Args:             response: The text to forma

### Community 969 - "Community 969"
Cohesion: 1.00
Nodes (1): Hash-based deterministic rollout.  Returns True for *rollout_pct*         fracti

### Community 970 - "Community 970"
Cohesion: 1.00
Nodes (1): Return the current clustering configuration.

### Community 971 - "Community 971"
Cohesion: 1.00
Nodes (1): Normalize various ticket formats to TicketInput objects.          Accepts:

### Community 972 - "Community 972"
Cohesion: 1.00
Nodes (1): Compute the centroid of ticket embeddings in a cluster.          Args:

### Community 973 - "Community 973"
Cohesion: 1.00
Nodes (1): Compute deterministic SHA-256 hash for cache key.

### Community 974 - "Community 974"
Cohesion: 1.00
Nodes (1): Compute hash from conversation_history for cache key (G9-GAP-02).          Retur

### Community 975 - "Community 975"
Cohesion: 1.00
Nodes (1): Return list of valid target states for a current state.          Args:

### Community 976 - "Community 976"
Cohesion: 1.00
Nodes (1): Explain why a transition is valid or invalid.          Args:             current

### Community 977 - "Community 977"
Cohesion: 1.00
Nodes (1): Rough token estimate per atomic step.

### Community 978 - "Community 978"
Cohesion: 1.00
Nodes (1): Check if this step's intelligence comes from a technique, not model.

### Community 979 - "Community 979"
Cohesion: 1.00
Nodes (1): Build the LiteLLM model name from provider and model_id.          LiteLLM uses f

### Community 980 - "Community 980"
Cohesion: 1.00
Nodes (1): Call Google AI Studio API (async).

### Community 981 - "Community 981"
Cohesion: 1.00
Nodes (1): Call OpenAI-compatible API -- Cerebras or Groq (async).

### Community 982 - "Community 982"
Cohesion: 1.00
Nodes (1): Create a rollback function that removes fields.          Args:             targe

### Community 983 - "Community 983"
Cohesion: 1.00
Nodes (1): Rollback v5->v4: convert gsd_state back to int.

### Community 984 - "Community 984"
Cohesion: 1.00
Nodes (1): Upload a file to storage.          Args:             company_id: Tenant ID (BC-0

### Community 985 - "Community 985"
Cohesion: 1.00
Nodes (1): Download a file from storage.          Args:             company_id: Tenant ID (

### Community 986 - "Community 986"
Cohesion: 1.00
Nodes (1): Delete a file from storage.          Args:             company_id: Tenant ID (BC

### Community 987 - "Community 987"
Cohesion: 1.00
Nodes (1): List files in a company's storage namespace.          Args:             company_

### Community 988 - "Community 988"
Cohesion: 1.00
Nodes (1): Generate a signed URL for direct file access.          Args:             company

### Community 989 - "Community 989"
Cohesion: 1.00
Nodes (1): Check if a file exists in storage.          Args:             company_id: Tenant

### Community 990 - "Community 990"
Cohesion: 1.00
Nodes (1): Get the size of a file in bytes.          Args:             company_id: Tenant I

### Community 991 - "Community 991"
Cohesion: 1.00
Nodes (1): Return available techniques based on tenant plan.

### Community 992 - "Community 992"
Cohesion: 1.00
Nodes (1): Validate that an ID is a non-empty string.

### Community 993 - "Community 993"
Cohesion: 1.00
Nodes (1): Validate that a name is a non-empty string.

### Community 994 - "Community 994"
Cohesion: 1.00
Nodes (1): Check if the agent's access has expired.

### Community 995 - "Community 995"
Cohesion: 1.00
Nodes (1): Seconds remaining until expiry. Negative if already expired.

### Community 996 - "Community 996"
Cohesion: 1.00
Nodes (1): Remaining concurrent slots.

### Community 997 - "Community 997"
Cohesion: 1.00
Nodes (1): 0..1 fraction of capacity consumed.

### Community 998 - "Community 998"
Cohesion: 1.00
Nodes (1): Agent is online *and* has at least one free slot.

### Community 999 - "Community 999"
Cohesion: 1.00
Nodes (1): Normalised bag-of-words from subject + tags.

### Community 1000 - "Community 1000"
Cohesion: 1.00
Nodes (1): Assign *ticket* to the single best agent from *agents*.

### Community 1001 - "Community 1001"
Cohesion: 1.00
Nodes (1): Assign multiple tickets.  Order of results matches *tickets*.

### Community 1002 - "Community 1002"
Cohesion: 1.00
Nodes (1): Return the current UTC time as an ISO-8601 string (BC-012).

### Community 1003 - "Community 1003"
Cohesion: 1.00
Nodes (1): Return the current UTC time as a Unix timestamp.

### Community 1004 - "Community 1004"
Cohesion: 1.00
Nodes (1): Price in USD (BC-002: always Decimal).

### Community 1005 - "Community 1005"
Cohesion: 1.00
Nodes (1): Fallback simulated carrier data when connector is unavailable.

### Community 1006 - "Community 1006"
Cohesion: 1.00
Nodes (1): Check if the vector store is healthy.

### Community 1007 - "Community 1007"
Cohesion: 1.00
Nodes (1): Compute cosine similarity between two vectors.

### Community 1008 - "Community 1008"
Cohesion: 1.00
Nodes (1): Add a document's chunks to the vector store.

### Community 1009 - "Community 1009"
Cohesion: 1.00
Nodes (1): Delete a document from the vector store.

### Community 1010 - "Community 1010"
Cohesion: 1.00
Nodes (1): Parse CORS_ORIGINS into a list.          C-05 FIX: Never returns ["*"]. If no or

### Community 1011 - "Community 1011"
Cohesion: 1.00
Nodes (1): Normalize DATABASE_URL for SQLAlchemy compatibility.

### Community 1012 - "Community 1012"
Cohesion: 1.00
Nodes (1): C-04 FIX: MCP_AUTH_TOKEN is required in production.

### Community 1013 - "Community 1013"
Cohesion: 1.00
Nodes (1): Also validate MCP_AUTH_TOKEN when ENVIRONMENT is set to production.

### Community 1017 - "Community 1017"
Cohesion: 1.00
Nodes (1): Check if path is a cookie-based auth endpoint.

### Community 1018 - "Community 1018"
Cohesion: 1.00
Nodes (1): Extract a named cookie value from a Cookie header.

### Community 1019 - "Community 1019"
Cohesion: 1.00
Nodes (1): Generate a new CSRF token.          The token is a random nonce combined with an

### Community 1020 - "Community 1020"
Cohesion: 1.00
Nodes (1): Validate a CSRF token.          Checks:             1. Token format (nonce:times

### Community 1021 - "Community 1021"
Cohesion: 1.00
Nodes (1): Validate that the CSRF cookie matches the header token.          The header toke

### Community 1022 - "Community 1022"
Cohesion: 1.00
Nodes (1): Wrap the ASGI send callable to inject CSP header         and CSRF cookie (H-19).

### Community 1023 - "Community 1023"
Cohesion: 1.00
Nodes (1): Send a 403 JSON response (BC-012).

### Community 1024 - "Community 1024"
Cohesion: 1.00
Nodes (1): Return *True* if *path* should bypass the limit check.          Matches against

### Community 1025 - "Community 1025"
Cohesion: 1.00
Nodes (1): Map a request *path* to a variant-limit type.          Only POST routes listed i

### Community 1026 - "Community 1026"
Cohesion: 1.00
Nodes (1): Extract ``company_id`` from the ASGI *scope*.          SECURITY: Only extracts c

### Community 1027 - "Community 1027"
Cohesion: 1.00
Nodes (1): Decode ``company_id`` claim from a JWT token without verification.          This

### Community 1028 - "Community 1028"
Cohesion: 1.00
Nodes (1): Check variant resource limits via ``VariantLimitService``.          For ``ticket

### Community 1029 - "Community 1029"
Cohesion: 1.00
Nodes (1): Check if this agent is available for the given variant tier.          Refund age

### Community 1030 - "Community 1030"
Cohesion: 1.00
Nodes (1): Check if this agent is available for the given variant tier.          Complaint

### Community 1031 - "Community 1031"
Cohesion: 1.00
Nodes (1): Verify that the supplied credentials can reach the provider.          Should set

### Community 1032 - "Community 1032"
Cohesion: 1.00
Nodes (1): Validate credential dict structure *without* making a network call.          Che

### Community 1033 - "Community 1033"
Cohesion: 1.00
Nodes (1): Return a list of field specifications for the credential form.          Each ite

### Community 1034 - "Community 1034"
Cohesion: 1.00
Nodes (1): Return a list of capability tokens this provider supports.          Examples: ``

### Community 1035 - "Community 1035"
Cohesion: 1.00
Nodes (1): Send an e-mail.          Args:             to:      Recipient e-mail address.

### Community 1036 - "Community 1036"
Cohesion: 1.00
Nodes (1): Send an SMS message.          Args:             to:      Recipient phone number

### Community 1037 - "Community 1037"
Cohesion: 1.00
Nodes (1): Retrieve a subscription by its provider-specific ID.          Returns:

### Community 1038 - "Community 1038"
Cohesion: 1.00
Nodes (1): Create a successful result.

### Community 1039 - "Community 1039"
Cohesion: 1.00
Nodes (1): Create a failure result.

### Community 1040 - "Community 1040"
Cohesion: 1.00
Nodes (1): Register a parser for a given provider name.          Args:             provider

### Community 1041 - "Community 1041"
Cohesion: 1.00
Nodes (1): Parse a webhook payload using the registered parser.          Falls back to ``pa

### Community 1042 - "Community 1042"
Cohesion: 1.00
Nodes (1): Return the parser for a provider, or None if not registered.

### Community 1043 - "Community 1043"
Cohesion: 1.00
Nodes (1): Return all registered provider names.

### Community 1044 - "Community 1044"
Cohesion: 1.00
Nodes (1): Check if a provider has a registered parser.

### Community 1045 - "Community 1045"
Cohesion: 1.00
Nodes (1): Register a verifier for a provider.          Args:             provider:  Unique

### Community 1046 - "Community 1046"
Cohesion: 1.00
Nodes (1): Verify a webhook request using the registered verifier.          Falls back to `

### Community 1047 - "Community 1047"
Cohesion: 1.00
Nodes (1): Return the verifier for a provider, or None.

### Community 1048 - "Community 1048"
Cohesion: 1.00
Nodes (1): Return all registered provider names with verifiers.

### Community 1049 - "Community 1049"
Cohesion: 1.00
Nodes (1): Check if a provider has a registered verifier.

### Community 1050 - "Community 1050"
Cohesion: 1.00
Nodes (1): Unique tool identifier used by the LLM and registry.

### Community 1051 - "Community 1051"
Cohesion: 1.00
Nodes (1): Human-readable description of what the tool does.

### Community 1052 - "Community 1052"
Cohesion: 1.00
Nodes (1): List of action names this tool supports.

### Community 1053 - "Community 1053"
Cohesion: 1.00
Nodes (1): Subclass-specific execution logic.          Implementations should validate *act

### Community 1054 - "Community 1054"
Cohesion: 1.00
Nodes (1): Return the full JSON Schema descriptor for this tool.

### Community 1055 - "Community 1055"
Cohesion: 1.00
Nodes (1): L02: uppercase, lowercase, digit, special char.

### Community 1056 - "Community 1056"
Cohesion: 1.00
Nodes (1): Ensure new_password and confirm_new_password are identical.

### Community 1057 - "Community 1057"
Cohesion: 1.00
Nodes (1): L01: confirm_password must match password.

### Community 1058 - "Community 1058"
Cohesion: 1.00
Nodes (1): BC-011: Min 8 chars + uppercase + lowercase + digit         + special char (L02)

### Community 1059 - "Community 1059"
Cohesion: 1.00
Nodes (1): Validate that required params are present for the action type.

### Community 1060 - "Community 1060"
Cohesion: 1.00
Nodes (1): Require at least one of email or phone.

### Community 1061 - "Community 1061"
Cohesion: 1.00
Nodes (1): Require at least one identifier to match.

### Community 1062 - "Community 1062"
Cohesion: 1.00
Nodes (1): Same strength rules as Day 7 registration.

### Community 1063 - "Community 1063"
Cohesion: 1.00
Nodes (1): Confirm password must match.

### Community 1064 - "Community 1064"
Cohesion: 1.00
Nodes (1): Clamp offset/limit to hard security limits.          Enforces ``MAX_OFFSET`` and

### Community 1065 - "Community 1065"
Cohesion: 1.00
Nodes (1): Validate that minutes fields are positive integers if provided.

### Community 1066 - "Community 1066"
Cohesion: 1.00
Nodes (1): Normalize any naive datetimes to UTC-aware to avoid subtraction errors.

### Community 1067 - "Community 1067"
Cohesion: 1.00
Nodes (1): Calculate remaining time in seconds until resolution deadline.

### Community 1068 - "Community 1068"
Cohesion: 1.00
Nodes (1): Check if SLA is approaching breach (75% threshold).

### Community 1069 - "Community 1069"
Cohesion: 1.00
Nodes (1): Validate that minutes fields are positive integers.

### Community 1070 - "Community 1070"
Cohesion: 1.00
Nodes (1): Check if message was sent by agent.

### Community 1071 - "Community 1071"
Cohesion: 1.00
Nodes (1): Check if message was sent by AI.

### Community 1072 - "Community 1072"
Cohesion: 1.00
Nodes (1): Validate that file size is positive.

### Community 1073 - "Community 1073"
Cohesion: 1.00
Nodes (1): Validate that content is not empty or whitespace only.

### Community 1074 - "Community 1074"
Cohesion: 1.00
Nodes (1): Validate that content is not empty if provided.

### Community 1075 - "Community 1075"
Cohesion: 1.00
Nodes (1): Check if message was sent by customer.

### Community 1076 - "Community 1076"
Cohesion: 1.00
Nodes (1): Validate priority is one of the allowed values.

### Community 1077 - "Community 1077"
Cohesion: 1.00
Nodes (1): Validate category is one of the allowed values if provided.

### Community 1078 - "Community 1078"
Cohesion: 1.00
Nodes (1): Validate priority is one of the allowed values if provided.

### Community 1079 - "Community 1079"
Cohesion: 1.00
Nodes (1): Validate category is one of the allowed values if provided.

### Community 1080 - "Community 1080"
Cohesion: 1.00
Nodes (1): Validate status is one of the allowed values if provided.

### Community 1081 - "Community 1081"
Cohesion: 1.00
Nodes (1): Compute derived fields based on status and timestamps.

### Community 1082 - "Community 1082"
Cohesion: 1.00
Nodes (1): Format a timedelta as a human-readable string.

### Community 1083 - "Community 1083"
Cohesion: 1.00
Nodes (1): Compute total pages based on total and page_size.

### Community 1084 - "Community 1084"
Cohesion: 1.00
Nodes (1): Validate all statuses are valid.

### Community 1085 - "Community 1085"
Cohesion: 1.00
Nodes (1): Validate all priorities are valid.

### Community 1086 - "Community 1086"
Cohesion: 1.00
Nodes (1): Validate all categories are valid.

### Community 1087 - "Community 1087"
Cohesion: 1.00
Nodes (1): Validate date_from is before date_to.

### Community 1088 - "Community 1088"
Cohesion: 1.00
Nodes (1): Validate status is one of the allowed values.

### Community 1089 - "Community 1089"
Cohesion: 1.00
Nodes (1): Validate assignee type is one of the allowed values.

### Community 1090 - "Community 1090"
Cohesion: 1.00
Nodes (1): Validate status is one of the allowed values.

### Community 1091 - "Community 1091"
Cohesion: 1.00
Nodes (1): Validate ticket IDs are unique and non-empty.

### Community 1092 - "Community 1092"
Cohesion: 1.00
Nodes (1): Validate assignee type is one of the allowed values.

### Community 1093 - "Community 1093"
Cohesion: 1.00
Nodes (1): Validate ticket IDs are unique and non-empty.

### Community 1094 - "Community 1094"
Cohesion: 1.00
Nodes (1): Get current circuit state, checking for timeout transitions.

### Community 1096 - "Community 1096"
Cohesion: 1.00
Nodes (1): Expand common contractions for formal tone.

### Community 1097 - "Community 1097"
Cohesion: 1.00
Nodes (1): Add casual touches for very informal tone.

### Community 1098 - "Community 1098"
Cohesion: 1.00
Nodes (1): Number of tenants with breaker state.

### Community 1099 - "Community 1099"
Cohesion: 1.00
Nodes (1): Safely parse a JSON text field.

### Community 1100 - "Community 1100"
Cohesion: 1.00
Nodes (1): Deserialise from a plain dict.

### Community 1101 - "Community 1101"
Cohesion: 1.00
Nodes (1): Access the anomaly detector for recording metrics.

### Community 1102 - "Community 1102"
Cohesion: 1.00
Nodes (1): Safely obtain a SQLAlchemy SessionLocal session.          Returns a session inst

### Community 1103 - "Community 1103"
Cohesion: 1.00
Nodes (1): Convert a ShadowModeConfig ORM row to the internal config dict.

### Community 1104 - "Community 1104"
Cohesion: 1.00
Nodes (1): Convert a ShadowModeResult ORM row to a comparison dict.

### Community 1105 - "Community 1105"
Cohesion: 1.00
Nodes (1): Parse an ISO-8601 string to a UTC datetime.          Returns None if *val* is No

### Community 1106 - "Community 1106"
Cohesion: 1.00
Nodes (1): Return current UTC time as ISO-8601 string (BC-012).

### Community 1107 - "Community 1107"
Cohesion: 1.00
Nodes (1): Hash a message for deduplication.

### Community 1108 - "Community 1108"
Cohesion: 1.00
Nodes (1): Run an async coroutine from synchronous context (BC-008).          Bridges the g

### Community 1109 - "Community 1109"
Cohesion: 1.00
Nodes (1): PS04: Validate if a ticket can be reopened.

### Community 1110 - "Community 1110"
Cohesion: 1.00
Nodes (1): PS02/PS03: Validate if a ticket can be escalated to human.

### Community 1111 - "Community 1111"
Cohesion: 1.00
Nodes (1): PS07: Validate if a ticket can be frozen.

### Community 1112 - "Community 1112"
Cohesion: 1.00
Nodes (1): PS07: Validate if a ticket can be thawed.

### Community 1113 - "Community 1113"
Cohesion: 1.00
Nodes (1): PS15: Validate if a ticket can be marked as spam.

### Community 1114 - "Community 1114"
Cohesion: 1.00
Nodes (1): PS04: Check if ticket should auto-escalate due to multiple reopens.

### Community 1119 - "Community 1119"
Cohesion: 1.00
Nodes (1): Estimate token count (~4 chars per token).

### Community 1120 - "Community 1120"
Cohesion: 1.00
Nodes (1): Split text into sentences on period, exclamation, question.

### Community 1121 - "Community 1121"
Cohesion: 1.00
Nodes (1): Join sentences with proper spacing.

### Community 1122 - "Community 1122"
Cohesion: 1.00
Nodes (1): Normalize a sentence to a set of lowercase words.

### Community 1123 - "Community 1123"
Cohesion: 1.00
Nodes (1): Check if a word is in the reserved phrases list.          Reserved words (e.g. r

### Community 1124 - "Community 1124"
Cohesion: 1.00
Nodes (1): Check if a sentence is redundant with any previous one.

### Community 1125 - "Community 1125"
Cohesion: 1.00
Nodes (1): Calculate token budget based on complexity level.

### Community 1126 - "Community 1126"
Cohesion: 1.00
Nodes (1): Unique tool identifier used by the LLM and registry.

### Community 1127 - "Community 1127"
Cohesion: 1.00
Nodes (1): Human-readable description of what the tool does.

### Community 1128 - "Community 1128"
Cohesion: 1.00
Nodes (1): JSON Schema for tool parameters. Override in subclasses.

### Community 1129 - "Community 1129"
Cohesion: 1.00
Nodes (1): Execute the tool scoped to *company_id*.          Returns a dict with ``"success

## Knowledge Gaps
- **5220 isolated node(s):** `PARWA API Routes  All FastAPI routers are registered in backend/app/main.py dire`, `List invoices for the company.      Args:         page: Page number (1-indexed)`, `PARWA Health API Routes (Day 21, BC-012)  Provides /health, /ready, /health/deta`, `Get application uptime in seconds.`, `Convert SubsystemHealth to JSON-safe dict.` (+5215 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 377`** (1 nodes): `SG-07: Load-Aware Distribution (Week 10 Day 4)  Distributes workload across mult`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 408`** (1 nodes): `PARWA AI — Provider Abstraction Layer: Base Classes & Protocols  Defines the cor`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 414`** (1 nodes): `FetchState`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 461`** (2 nodes): `MigrationEventBus`, `In-process pub/sub for migration events.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 476`** (2 nodes): `NavigationMenuTrigger()`, `navigationMenuTriggerStyle`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 491`** (1 nodes): `PaginationLinkProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 528`** (2 nodes): `NotificationItem()`, `timeAgo()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 582`** (2 nodes): `MigrationAuditLogger`, `Persistent audit trail for migration state changes.      Each entry is a JSON-se`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 600`** (2 nodes): `UseCollisionDetectionOptions`, `UseCollisionDetectionReturn`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 601`** (1 nodes): `UsePresenceReturn`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 605`** (1 nodes): `PipelineInsightCardProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 625`** (1 nodes): `ChannelMeta`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 626`** (2 nodes): `ChatWidgetProps`, `Message`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 629`** (1 nodes): `LockedFeatureProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 634`** (2 nodes): `TrendChart()`, `TrendChartProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 637`** (2 nodes): `FOCUSABLE_SELECTORS`, `FocusTrapOptions`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 645`** (2 nodes): `Alert()`, `alertVariants`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 652`** (1 nodes): `Alembic environment configuration.  Imports all models so autogenerate detects t`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 653`** (2 nodes): `inter`, `metadata`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 666`** (1 nodes): `Politeness`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 671`** (2 nodes): `Internal safe scan with Redis + DB integration.`, `Fetch rate limit count and tenant blocklist from Redis.          BC-012: Redis f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 674`** (2 nodes): `MigrationConfig`, `Per-tenant, per-feature migration configuration.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 677`** (2 nodes): `Get time spent in a specific state for a ticket.          Calculates duration fr`, `Get GSD analytics for a company.          Includes state distribution, average d`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 678`** (2 nodes): `Get the full capability profile for a specific variant type.          Returns mi`, `Compare two variants' capabilities side by side.          Returns a dict with co`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 682`** (1 nodes): `SystemHealthMonitor()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 683`** (2 nodes): `VoiceConfigCard()`, `VoiceConfigCardProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 684`** (2 nodes): `WelcomeCard()`, `WelcomeCardProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 685`** (1 nodes): `001_initial_schema: Core tables (companies, users, api_keys, sessions, etc.)  Re`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 686`** (1 nodes): `002_ticketing_tables: Tickets, TicketMessages, Customers, Channels + Week 4 tabl`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 687`** (1 nodes): `003_ai_pipeline_tables: api_providers, service_configs, gsd_sessions, confidence`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 688`** (1 nodes): `004_integration_tables: integrations, connectors, MCP, DB connections, etc.  Rev`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 689`** (1 nodes): `005_audit_billing_tables: audit_trail, webhook_events, rate_limit_events, api_ke`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 690`** (1 nodes): `006_analytics_onboarding_tables: metric_aggregates, roi_snapshots, drift_reports`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 691`** (1 nodes): `007_remaining_gap_tables: approval_queues, auto_approve_rules, executed_actions,`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 692`** (1 nodes): `008_technique_tables: technique_configurations, technique_executions, technique_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 693`** (1 nodes): `Billing Extended Tables Migration (009)  Creates 8 new tables for extended billi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 694`** (1 nodes): `010_onboarding_extended: user_details table + extend onboarding_sessions  Revisi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 695`** (1 nodes): `011_phase3_variant_engine: 9 tables for Phase 3 AI Engine  Revision ID: 011 Revi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 696`** (1 nodes): `012_jarvis_system: Jarvis onboarding chat system  Revision ID: 012 Revises: 011`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 697`** (1 nodes): `013_some_migration: Stub migration bridging 012 to 014  Revision ID: 013_some_mi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 698`** (1 nodes): `Alembic migration 016: Email channel tables.  Week 13 Day 1 (F-121: Email Inboun`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 699`** (1 nodes): `Week 13 Day 2: Outbound email tracking table  Revision ID: 017_outbound_email Re`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 700`** (1 nodes): `Week 13 Day 3: Email delivery events table  Revision ID: 018_email_delivery_even`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 701`** (1 nodes): `Week 13 Day 3: OOO detection tables and email bounces tables  Revision ID: 019_o`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 702`** (1 nodes): `020_jarvis_cc_tables: Jarvis Customer Care persistence  Revision ID: 020 Revises`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 703`** (1 nodes): `023_paddle_reconciliation: Paddle webhook reconciliation tables  Revision ID: 02`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 704`** (1 nodes): `Shadow Mode tables for Phase 4 Feature Completion.  Creates:   - shadow_mode_con`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 705`** (1 nodes): `Add scheduled_change_type, scheduled_change_variant, metadata_json to subscripti`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 706`** (1 nodes): `Production indexes and constraints  Revision ID: 025 Revises: 024 Create Date: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 707`** (1 nodes): `Activity Store full awareness coverage  Add new event categories for shadow_mode`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 708`** (1 nodes): `Voice channel tables.  Creates:   - voice_calls: Voice call tracking with Twilio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 709`** (1 nodes): `Create activity_log table for Jarvis non-agentic awareness  Revision ID: 027 Rev`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 710`** (2 nodes): `Detect billing anomalies by comparing against expected patterns.          Args:`, `Generate recommendation based on anomaly types.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 711`** (2 nodes): `Classify the billing dispute type and assess auto-resolution eligibility.`, `Return default dispute classification.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 712`** (2 nodes): `Initialize the billing intelligence engine.`, `Pre-compile regex patterns for performance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 713`** (2 nodes): `Initialize the churn retention engine.`, `Pre-compile regex patterns for performance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 714`** (2 nodes): `Score churn risk based on multiple signals.          Args:             query: Cu`, `Return default low-risk churn assessment.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 715`** (2 nodes): `Select optimal retention offers using ToT-branching logic.          Generates mu`, `Generate prompt addition for LLM retention context.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 716`** (2 nodes): `Generate a win-back automation sequence for post-cancellation.          Args:`, `Map a churn reason to the best win-back offer.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 717`** (2 nodes): `Initialize the EI engine.`, `Pre-compile regex patterns for performance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 718`** (2 nodes): `Build a multi-dimensional emotion profile from the customer query.          Args`, `Return a default neutral emotion profile.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 719`** (2 nodes): `Initialize the shipping intelligence engine.`, `Pre-compile regex patterns for performance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 720`** (2 nodes): `Classify the type of shipping issue from the customer query.          Args:`, `Return default no-issue result.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 721`** (2 nodes): `Assess shipping delay and generate proactive notification.          Args:`, `Return default no-delay result.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 722`** (2 nodes): `Initialize the tech diagnostics engine.`, `Pre-compile regex patterns for performance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 723`** (2 nodes): `Detect if the query matches a known issue in the knowledge base.          Args:`, `Return default no-known-issue result.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 724`** (2 nodes): `Generate step-by-step diagnostic guidance for the customer.          Args:`, `Generate diagnostic context prompt for the LLM.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 725`** (2 nodes): `Score the escalation severity of a technical issue.          Multi-factor scorin`, `Return default low severity result.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 726`** (1 nodes): `Step`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 729`** (2 nodes): `PollingOptions`, `PollingState`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 730`** (2 nodes): `RetryOptions`, `RetryState`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 731`** (2 nodes): `PaymentCard()`, `PaymentCardProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 733`** (2 nodes): `MATRIX_ROWS`, `MatrixRow`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 734`** (1 nodes): `TOAST_BG`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 735`** (2 nodes): `CONSENT_CARDS`, `LegalConsentStepProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 737`** (2 nodes): `trustBadges`, `variantData`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 738`** (2 nodes): `ProfilePage()`, `UserProfile`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 740`** (2 nodes): `Get routing rules for a category.          Args:             category: Category`, `Validate that category requirements are met.          Args:             category`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 741`** (2 nodes): `Get all notification preferences for a user.                  Returns preference`, `Get digest settings from user metadata.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 742`** (2 nodes): `Check Celery queue depths for anomalies.`, `Check if queue depth exceeds threshold.          Args:             queue: Queue`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 743`** (2 nodes): `Record a healing action in the audit trail.`, `Attempt to heal a specific anomaly.          Routes to the appropriate healing m`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 744`** (2 nodes): `Suggest tags based on text content.          Args:             text: Text to ana`, `Generate automatic tags from text content.          Args:             text: Text`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 745`** (2 nodes): `PS05: Check for duplicate tickets.          Args:             customer_id: Custo`, `Calculate similarity between two strings.          Simple Jaccard similarity on`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 751`** (1 nodes): `ToggleGroupContext`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 755`** (1 nodes): `Mini LLM Client — Lightweight LLM wrapper for Mini Parwa nodes.  Day 3 (AI Core)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 756`** (1 nodes): `PARWA Security utilities package.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 758`** (1 nodes): `prisma`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 759`** (1 nodes): `CallsDashboardPage()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 760`** (1 nodes): `UserMenuProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 761`** (1 nodes): `CollisionBannerProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 762`** (1 nodes): `DemoBannerProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 763`** (1 nodes): `SkipLinkProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 764`** (1 nodes): `TypingIndicatorProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 765`** (2 nodes): `DisambiguationFormatter`, `13. Add 'Did you mean?' suggestions for ambiguous queries.      This formatter i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 766`** (2 nodes): `EmojiFormatter`, `10. Strip/normalize emojis based on formality level.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 767`** (2 nodes): `EscalationFormatter`, `15. Format escalation notices with priority and context.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 768`** (2 nodes): `LinkFormatter`, `9. Validate and format URLs.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 769`** (2 nodes): `ListFormatter`, `7. Normalize bullet/numbered lists.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 770`** (2 nodes): `MarkdownFormatter`, `2. Normalize markdown — fix broken lists, headers, links.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 771`** (2 nodes): `4. Adjust tone (professional/friendly/casual).      Applies light transformation`, `ToneFormatter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 773`** (1 nodes): `NetworkStatus`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 774`** (1 nodes): `UseShadowModeReturn`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 775`** (1 nodes): `UseSocketReturn`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 776`** (1 nodes): `UseVariantReturn`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 778`** (1 nodes): `BillSummaryProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 779`** (2 nodes): `MessageCounter()`, `MessageCounterProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 780`** (2 nodes): `OtpVerificationCard()`, `OtpVerificationCardProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 781`** (2 nodes): `PackExpiredCard()`, `PackExpiredCardProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 783`** (2 nodes): `PostCallSummaryCard()`, `PostCallSummaryCardProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 785`** (1 nodes): `DogfoodingBannerProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 786`** (1 nodes): `shadowModeApi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 787`** (1 nodes): `voiceApi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 788`** (1 nodes): `MonitoringMetric`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 789`** (1 nodes): `FirstVictoryCelebrationProps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 791`** (2 nodes): `POST()`, `sanitizeEmailContent()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 793`** (1 nodes): `phaseSteps`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 794`** (1 nodes): `VerifyState`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 795`** (2 nodes): `Badge()`, `badgeVariants`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 796`** (2 nodes): `Button()`, `buttonVariants`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 800`** (2 nodes): `Toggle()`, `toggleVariants`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 801`** (2 nodes): `{ result }`, `{ unmount }`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 802`** (2 nodes): `pages`, `user`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 803`** (1 nodes): `mockFetch`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 805`** (1 nodes): `PARWA API Routes  All FastAPI routers are registered in backend/app/main.py dire`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 811`** (1 nodes): `High Parwa -- Highest tier of the Parwa Variant Engine (22-node pipeline).  Pipe`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 812`** (1 nodes): `Pro Parwa — Growth tier of the Parwa Variant Engine (17-node pipeline).  Pipelin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 813`** (1 nodes): `CLARA RAG package — Advanced retrieval with HyDE, Multi-Query, and LLM Reranking`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 814`** (1 nodes): `PARWA Security Headers Middleware.  Adds security headers to all responses per B`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 815`** (1 nodes): `DEPRECATED: This service has been removed from the production codebase. It had z`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 816`** (1 nodes): `Notification Template Service - Template management (MF05)  Handles: - CRUD oper`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 817`** (1 nodes): `DEPRECATED: This service has been removed from the production codebase. It had z`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 818`** (1 nodes): `DEPRECATED: This service has been removed from the production codebase. It had z`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 819`** (1 nodes): `PARWA Shared Module  Shared utilities and cross-cutting concerns used across mul`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 820`** (1 nodes): `PARWA webhook tasks package.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 825`** (1 nodes): `Record that a call was attempted (for HALF_OPEN tracking).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 826`** (1 nodes): `Return approximate byte size of payload when JSON-serialized.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 828`** (1 nodes): `Generate retention negotiation strategy with acceptance likelihood.          Arg`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 829`** (1 nodes): `Assess if sentiment requires escalation beyond standard handling.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 830`** (1 nodes): `Generate de-escalation prompt additions for the LLM.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 831`** (1 nodes): `Get automated recovery actions to execute.          Args:             emotion_pr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 832`** (1 nodes): `Generate deep complaint resolution with strategy and confidence.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 833`** (1 nodes): `Select the appropriate service recovery playbook based on emotion profile.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 834`** (1 nodes): `Detect tracking numbers in the customer query.          Args:             query:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 835`** (1 nodes): `Get automated shipping resolution actions.          Args:             shipping_i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 836`** (1 nodes): `Generate shipping context prompt addition for the LLM.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 837`** (1 nodes): `Generate proactive delay notification for the customer.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 838`** (1 nodes): `Get automated tech support actions.          Args:             known_issue: Outp`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 839`** (1 nodes): `Generate comprehensive diagnostic result summary.          Args:             que`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 840`** (1 nodes): `Make escalation decision based on severity, known issues, and customer tier.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 846`** (1 nodes): `globalForPrisma`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 848`** (1 nodes): `PARWA MCP Server package  Model Context Protocol server for external AI tool int`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 858`** (2 nodes): `parse_shopify()`, `Parse Shopify webhook payload.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 859`** (2 nodes): `parse_twilio()`, `Parse Twilio webhook payload.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 860`** (2 nodes): `Central registry for webhook parsers.      Structure::          {             "p`, `WebhookParserRegistry`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 861`** (2 nodes): `Central registry for webhook signature verifiers.      Usage::          WebhookV`, `WebhookVerifierRegistry`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 865`** (2 nodes): `NotificationListItem`, `Single notification item in list response.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 866`** (2 nodes): `NotificationPreferenceUpdate`, `Schema for updating user notification preferences.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 867`** (2 nodes): `NotificationSendRequest`, `Schema for manually sending a notification.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 868`** (2 nodes): `NotificationSendResponse`, `Schema for notification send result.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 869`** (2 nodes): `NotificationTemplateCreate`, `Schema for creating a notification template.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 870`** (2 nodes): `NotificationTemplateResponse`, `Schema for notification template response.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 871`** (2 nodes): `NotificationTemplateUpdate`, `Schema for updating a notification template.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 872`** (2 nodes): `Single template item in list response.`, `TemplateListItem`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 873`** (2 nodes): `DiscountDeletedEvent`, `discount.deleted event.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 874`** (2 nodes): `DiscountUpdatedEvent`, `discount.updated event.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 875`** (2 nodes): `subscription.created event.`, `SubscriptionCreatedEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 876`** (2 nodes): `subscription.updated event.`, `SubscriptionUpdatedEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 877`** (2 nodes): `subscription.activated event.`, `SubscriptionActivatedEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 878`** (2 nodes): `subscription.canceled event.`, `SubscriptionCanceledEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 879`** (2 nodes): `subscription.past_due event.`, `SubscriptionPastDueEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 880`** (2 nodes): `subscription.paused event.`, `SubscriptionPausedEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 881`** (2 nodes): `subscription.resumed event.`, `SubscriptionResumedEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 882`** (2 nodes): `transaction.completed event.`, `TransactionCompletedEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 883`** (2 nodes): `transaction.paid event.`, `TransactionPaidEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 884`** (2 nodes): `transaction.payment_failed event.`, `TransactionPaymentFailedEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 885`** (2 nodes): `transaction.canceled event.`, `TransactionCanceledEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 886`** (2 nodes): `transaction.updated event.`, `TransactionUpdatedEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 887`** (2 nodes): `report.created event.`, `ReportCreatedEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 888`** (2 nodes): `report.updated event.`, `ReportUpdatedEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 889`** (2 nodes): `_clear_service_cache()`, `Clear all cached services (useful for testing).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 890`** (2 nodes): `get_entry_context()`, `Parse URL params into context_json for entry routing.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 891`** (2 nodes): `prune_session_context()`, `Context Hygiene: Removes transient data while preserving core strategic value.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 892`** (1 nodes): `Get active template for event type and channel.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 893`** (1 nodes): `Get valid variables for an event type.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 894`** (1 nodes): `Get all versions of a template.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 895`** (1 nodes): `List templates with filters.                  Args:             event_type: Filt`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 896`** (1 nodes): `Apply proration credit and create audit record.          This records the prorat`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 897`** (1 nodes): `Calculate effective date for downgrade.          Downgrades are always effective`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 898`** (1 nodes): `Get proration audit history for a company.          Args:             company_id`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 904`** (1 nodes): `dashboardLink`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 917`** (1 nodes): `mockFetch`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 923`** (1 nodes): `Standardize carrier-specific tracking data to unified format.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 924`** (1 nodes): `Return result for unrecognized tracking number.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 925`** (1 nodes): `Return result when no tracking data is available.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 926`** (1 nodes): `Return result when no delay is detected.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 927`** (1 nodes): `Return result when no compensation is eligible.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 928`** (1 nodes): `Get current state, checking for automatic transitions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 929`** (1 nodes): `D6-GAP-03: Filter out false positive phone number matches.          Removes matc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 930`** (1 nodes): `GAP-018: Sensible defaults for new tenants.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 931`** (1 nodes): `True if tenant has explicitly configured custom brand rules.          Considers:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 932`** (1 nodes): `Get or create the singleton engine instance.          Returns:             The s`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 933`** (1 nodes): `Get the default compression level for a variant.          mini_parwa -> NONE`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 934`** (1 nodes): `Get the default health thresholds for a variant.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 935`** (1 nodes): `Build a canonical dict key for a conversation.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 936`** (1 nodes): `Run a single handler with timeout enforcement.          Since we cannot easily i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 937`** (1 nodes): `Unique string identifier for this handler.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 938`** (1 nodes): `Integer priority (lower = runs first).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 939`** (1 nodes): `Return True if this handler can handle the given query.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 940`** (1 nodes): `Process the query and return a result.          Args:             query: The use`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 941`** (1 nodes): `Mask PII value for safe logging.          Args:             value: The raw PII v`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 942`** (1 nodes): `Dispatch to the appropriate guard check method.          Args:             guard`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 943`** (1 nodes): `Convert severity to comparable ordinal value.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 944`** (1 nodes): `Check if a year is a leap year.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 945`** (1 nodes): `Extract factual claim sentences from text.          Returns sentences that conta`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 946`** (1 nodes): `Quick check if gateway has credentials configured.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 947`** (1 nodes): `Maximum concurrent tickets this instance can handle.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 948`** (1 nodes): `Daily token budget share for this instance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 949`** (1 nodes): `Current load as a percentage of max capacity.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 950`** (1 nodes): `Combined load score factoring in active tickets and queue.          Queued ticke`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 951`** (1 nodes): `Remaining slots before hitting max concurrent.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 952`** (1 nodes): `Whether this instance should receive new traffic.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 953`** (1 nodes): `Whether the instance exceeds the overload threshold.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 954`** (1 nodes): `Check whether this session has exceeded its TTL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 955`** (1 nodes): `Seconds since creation.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 956`** (1 nodes): `Percentage of distributions served by sticky sessions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 957`** (1 nodes): `Return the current UTC time as an ISO-8601 string (BC-012).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 958`** (1 nodes): `Return the current UTC date as a YYYY-MM-DD string for token tracking.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 959`** (1 nodes): `Build a greeting message based on variant tier and industry.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 960`** (1 nodes): `Build a response for a detected customer intent.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 961`** (1 nodes): `Build a resolution/summary message based on variant tier and outcome.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 962`** (1 nodes): `Build a post-call summary for SMS/voice delivery.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 963`** (1 nodes): `Apply a dict of overrides to a dataclass instance.          Only applies keys th`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 964`** (1 nodes): `Luhn algorithm for credit card validation.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 965`** (1 nodes): `Check which integrations are available.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 966`** (1 nodes): `Build the Redis hash key: health:{provider}:{model_id}.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 967`** (1 nodes): `Return the unique name of this formatter.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 968`** (1 nodes): `Format the response text.          Args:             response: The text to forma`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 969`** (1 nodes): `Hash-based deterministic rollout.  Returns True for *rollout_pct*         fracti`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 970`** (1 nodes): `Return the current clustering configuration.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 971`** (1 nodes): `Normalize various ticket formats to TicketInput objects.          Accepts:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 972`** (1 nodes): `Compute the centroid of ticket embeddings in a cluster.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 973`** (1 nodes): `Compute deterministic SHA-256 hash for cache key.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 974`** (1 nodes): `Compute hash from conversation_history for cache key (G9-GAP-02).          Retur`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 975`** (1 nodes): `Return list of valid target states for a current state.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 976`** (1 nodes): `Explain why a transition is valid or invalid.          Args:             current`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 977`** (1 nodes): `Rough token estimate per atomic step.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 978`** (1 nodes): `Check if this step's intelligence comes from a technique, not model.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 979`** (1 nodes): `Build the LiteLLM model name from provider and model_id.          LiteLLM uses f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 980`** (1 nodes): `Call Google AI Studio API (async).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 981`** (1 nodes): `Call OpenAI-compatible API -- Cerebras or Groq (async).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 982`** (1 nodes): `Create a rollback function that removes fields.          Args:             targe`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 983`** (1 nodes): `Rollback v5->v4: convert gsd_state back to int.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 984`** (1 nodes): `Upload a file to storage.          Args:             company_id: Tenant ID (BC-0`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 985`** (1 nodes): `Download a file from storage.          Args:             company_id: Tenant ID (`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 986`** (1 nodes): `Delete a file from storage.          Args:             company_id: Tenant ID (BC`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 987`** (1 nodes): `List files in a company's storage namespace.          Args:             company_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 988`** (1 nodes): `Generate a signed URL for direct file access.          Args:             company`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 989`** (1 nodes): `Check if a file exists in storage.          Args:             company_id: Tenant`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 990`** (1 nodes): `Get the size of a file in bytes.          Args:             company_id: Tenant I`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 991`** (1 nodes): `Return available techniques based on tenant plan.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 992`** (1 nodes): `Validate that an ID is a non-empty string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 993`** (1 nodes): `Validate that a name is a non-empty string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 994`** (1 nodes): `Check if the agent's access has expired.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 995`** (1 nodes): `Seconds remaining until expiry. Negative if already expired.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 996`** (1 nodes): `Remaining concurrent slots.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 997`** (1 nodes): `0..1 fraction of capacity consumed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 998`** (1 nodes): `Agent is online *and* has at least one free slot.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 999`** (1 nodes): `Normalised bag-of-words from subject + tags.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1000`** (1 nodes): `Assign *ticket* to the single best agent from *agents*.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1001`** (1 nodes): `Assign multiple tickets.  Order of results matches *tickets*.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1002`** (1 nodes): `Return the current UTC time as an ISO-8601 string (BC-012).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1003`** (1 nodes): `Return the current UTC time as a Unix timestamp.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1004`** (1 nodes): `Price in USD (BC-002: always Decimal).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1005`** (1 nodes): `Fallback simulated carrier data when connector is unavailable.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1006`** (1 nodes): `Check if the vector store is healthy.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1007`** (1 nodes): `Compute cosine similarity between two vectors.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1008`** (1 nodes): `Add a document's chunks to the vector store.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1009`** (1 nodes): `Delete a document from the vector store.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1010`** (1 nodes): `Parse CORS_ORIGINS into a list.          C-05 FIX: Never returns ["*"]. If no or`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1011`** (1 nodes): `Normalize DATABASE_URL for SQLAlchemy compatibility.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1012`** (1 nodes): `C-04 FIX: MCP_AUTH_TOKEN is required in production.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1013`** (1 nodes): `Also validate MCP_AUTH_TOKEN when ENVIRONMENT is set to production.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1017`** (1 nodes): `Check if path is a cookie-based auth endpoint.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1018`** (1 nodes): `Extract a named cookie value from a Cookie header.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1019`** (1 nodes): `Generate a new CSRF token.          The token is a random nonce combined with an`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1020`** (1 nodes): `Validate a CSRF token.          Checks:             1. Token format (nonce:times`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1021`** (1 nodes): `Validate that the CSRF cookie matches the header token.          The header toke`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1022`** (1 nodes): `Wrap the ASGI send callable to inject CSP header         and CSRF cookie (H-19).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1023`** (1 nodes): `Send a 403 JSON response (BC-012).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1024`** (1 nodes): `Return *True* if *path* should bypass the limit check.          Matches against`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1025`** (1 nodes): `Map a request *path* to a variant-limit type.          Only POST routes listed i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1026`** (1 nodes): `Extract ``company_id`` from the ASGI *scope*.          SECURITY: Only extracts c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1027`** (1 nodes): `Decode ``company_id`` claim from a JWT token without verification.          This`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1028`** (1 nodes): `Check variant resource limits via ``VariantLimitService``.          For ``ticket`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1029`** (1 nodes): `Check if this agent is available for the given variant tier.          Refund age`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1030`** (1 nodes): `Check if this agent is available for the given variant tier.          Complaint`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1031`** (1 nodes): `Verify that the supplied credentials can reach the provider.          Should set`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1032`** (1 nodes): `Validate credential dict structure *without* making a network call.          Che`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1033`** (1 nodes): `Return a list of field specifications for the credential form.          Each ite`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1034`** (1 nodes): `Return a list of capability tokens this provider supports.          Examples: ```
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1035`** (1 nodes): `Send an e-mail.          Args:             to:      Recipient e-mail address.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1036`** (1 nodes): `Send an SMS message.          Args:             to:      Recipient phone number`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1037`** (1 nodes): `Retrieve a subscription by its provider-specific ID.          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1038`** (1 nodes): `Create a successful result.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1039`** (1 nodes): `Create a failure result.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1040`** (1 nodes): `Register a parser for a given provider name.          Args:             provider`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1041`** (1 nodes): `Parse a webhook payload using the registered parser.          Falls back to ``pa`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1042`** (1 nodes): `Return the parser for a provider, or None if not registered.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1043`** (1 nodes): `Return all registered provider names.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1044`** (1 nodes): `Check if a provider has a registered parser.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1045`** (1 nodes): `Register a verifier for a provider.          Args:             provider:  Unique`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1046`** (1 nodes): `Verify a webhook request using the registered verifier.          Falls back to ``
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1047`** (1 nodes): `Return the verifier for a provider, or None.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1048`** (1 nodes): `Return all registered provider names with verifiers.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1049`** (1 nodes): `Check if a provider has a registered verifier.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1050`** (1 nodes): `Unique tool identifier used by the LLM and registry.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1051`** (1 nodes): `Human-readable description of what the tool does.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1052`** (1 nodes): `List of action names this tool supports.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1053`** (1 nodes): `Subclass-specific execution logic.          Implementations should validate *act`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1054`** (1 nodes): `Return the full JSON Schema descriptor for this tool.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1055`** (1 nodes): `L02: uppercase, lowercase, digit, special char.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1056`** (1 nodes): `Ensure new_password and confirm_new_password are identical.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1057`** (1 nodes): `L01: confirm_password must match password.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1058`** (1 nodes): `BC-011: Min 8 chars + uppercase + lowercase + digit         + special char (L02)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1059`** (1 nodes): `Validate that required params are present for the action type.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1060`** (1 nodes): `Require at least one of email or phone.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1061`** (1 nodes): `Require at least one identifier to match.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1062`** (1 nodes): `Same strength rules as Day 7 registration.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1063`** (1 nodes): `Confirm password must match.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1064`** (1 nodes): `Clamp offset/limit to hard security limits.          Enforces ``MAX_OFFSET`` and`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1065`** (1 nodes): `Validate that minutes fields are positive integers if provided.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1066`** (1 nodes): `Normalize any naive datetimes to UTC-aware to avoid subtraction errors.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1067`** (1 nodes): `Calculate remaining time in seconds until resolution deadline.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1068`** (1 nodes): `Check if SLA is approaching breach (75% threshold).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1069`** (1 nodes): `Validate that minutes fields are positive integers.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1070`** (1 nodes): `Check if message was sent by agent.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1071`** (1 nodes): `Check if message was sent by AI.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1072`** (1 nodes): `Validate that file size is positive.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1073`** (1 nodes): `Validate that content is not empty or whitespace only.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1074`** (1 nodes): `Validate that content is not empty if provided.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1075`** (1 nodes): `Check if message was sent by customer.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1076`** (1 nodes): `Validate priority is one of the allowed values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1077`** (1 nodes): `Validate category is one of the allowed values if provided.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1078`** (1 nodes): `Validate priority is one of the allowed values if provided.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1079`** (1 nodes): `Validate category is one of the allowed values if provided.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1080`** (1 nodes): `Validate status is one of the allowed values if provided.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1081`** (1 nodes): `Compute derived fields based on status and timestamps.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1082`** (1 nodes): `Format a timedelta as a human-readable string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1083`** (1 nodes): `Compute total pages based on total and page_size.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1084`** (1 nodes): `Validate all statuses are valid.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1085`** (1 nodes): `Validate all priorities are valid.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1086`** (1 nodes): `Validate all categories are valid.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1087`** (1 nodes): `Validate date_from is before date_to.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1088`** (1 nodes): `Validate status is one of the allowed values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1089`** (1 nodes): `Validate assignee type is one of the allowed values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1090`** (1 nodes): `Validate status is one of the allowed values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1091`** (1 nodes): `Validate ticket IDs are unique and non-empty.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1092`** (1 nodes): `Validate assignee type is one of the allowed values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1093`** (1 nodes): `Validate ticket IDs are unique and non-empty.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1094`** (1 nodes): `Get current circuit state, checking for timeout transitions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1096`** (1 nodes): `Expand common contractions for formal tone.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1097`** (1 nodes): `Add casual touches for very informal tone.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1098`** (1 nodes): `Number of tenants with breaker state.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1099`** (1 nodes): `Safely parse a JSON text field.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1100`** (1 nodes): `Deserialise from a plain dict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1101`** (1 nodes): `Access the anomaly detector for recording metrics.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1102`** (1 nodes): `Safely obtain a SQLAlchemy SessionLocal session.          Returns a session inst`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1103`** (1 nodes): `Convert a ShadowModeConfig ORM row to the internal config dict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1104`** (1 nodes): `Convert a ShadowModeResult ORM row to a comparison dict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1105`** (1 nodes): `Parse an ISO-8601 string to a UTC datetime.          Returns None if *val* is No`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1106`** (1 nodes): `Return current UTC time as ISO-8601 string (BC-012).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1107`** (1 nodes): `Hash a message for deduplication.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1108`** (1 nodes): `Run an async coroutine from synchronous context (BC-008).          Bridges the g`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1109`** (1 nodes): `PS04: Validate if a ticket can be reopened.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1110`** (1 nodes): `PS02/PS03: Validate if a ticket can be escalated to human.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1111`** (1 nodes): `PS07: Validate if a ticket can be frozen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1112`** (1 nodes): `PS07: Validate if a ticket can be thawed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1113`** (1 nodes): `PS15: Validate if a ticket can be marked as spam.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1114`** (1 nodes): `PS04: Check if ticket should auto-escalate due to multiple reopens.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1119`** (1 nodes): `Estimate token count (~4 chars per token).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1120`** (1 nodes): `Split text into sentences on period, exclamation, question.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1121`** (1 nodes): `Join sentences with proper spacing.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1122`** (1 nodes): `Normalize a sentence to a set of lowercase words.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1123`** (1 nodes): `Check if a word is in the reserved phrases list.          Reserved words (e.g. r`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1124`** (1 nodes): `Check if a sentence is redundant with any previous one.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1125`** (1 nodes): `Calculate token budget based on complexity level.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1126`** (1 nodes): `Unique tool identifier used by the LLM and registry.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1127`** (1 nodes): `Human-readable description of what the tool does.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1128`** (1 nodes): `JSON Schema for tool parameters. Override in subclasses.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 1129`** (1 nodes): `Execute the tool scoped to *company_id*.          Returns a dict with ``"success`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `User` connect `Community 3` to `Community 127`, `Community 12`, `Community 176`, `Community 200`, `Community 201`, `Community 22`, `Community 11`, `Community 28`, `Community 20`, `Community 114`, `Community 323`, `Community 54`, `Community 81`, `Community 177`, `Community 60`, `Community 104`, `Community 279`, `Community 57`, `Community 40`, `Community 117`, `Community 52`, `Community 69`, `Community 50`, `Community 324`, `Community 51`, `Community 48`, `Community 130`, `Community 32`, `Community 115`, `Community 70`, `Community 27`, `Community 19`, `Community 2`, `Community 35`, `Community 153`, `Community 43`, `Community 10`, `Community 55`, `Community 5`, `Community 45`, `Community 84`, `Community 73`, `Community 95`, `Community 14`, `Community 78`, `Community 31`, `Community 159`, `Community 18`, `Community 132`, `Community 26`, `Community 531`, `Community 252`, `Community 191`, `Community 30`, `Community 741`, `Community 471`, `Community 122`, `Community 204`, `Community 312`?**
  _High betweenness centrality (0.204) - this node is a cross-community bridge._
- **Why does `TechniqueID` connect `Community 4` to `Community 1`, `Community 8`, `Community 25`, `Community 13`, `Community 17`, `Community 278`, `Community 125`, `Community 126`, `Community 139`, `Community 162`, `Community 112`, `Community 116`, `Community 77`, `Community 140`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `Company` connect `Community 7` to `Community 127`, `Community 12`, `Community 176`, `Community 28`, `Community 114`, `Community 81`, `Community 177`, `Community 279`, `Community 252`, `Community 20`, `Community 15`, `Community 30`, `Community 46`, `Community 122`, `Community 5`, `Community 239`, `Community 474`, `Community 537`, `Community 745`, `Community 192`, `Community 204`, `Community 205`, `Community 338`, `Community 67`, `Community 102`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Are the 1324 inferred relationships involving `User` (e.g. with `PARWA Admin API Router (F06)  Platform admin endpoints for managing clients (com` and `Serialize company with user count for admin responses.`) actually correct?**
  _`User` has 1324 INFERRED edges - model-reasoned connections that need verification._
- **Are the 640 inferred relationships involving `TechniqueID` (e.g. with `TechniqueConfigResponse` and `TechniqueConfigListResponse`) actually correct?**
  _`TechniqueID` has 640 INFERRED edges - model-reasoned connections that need verification._
- **Are the 425 inferred relationships involving `Company` (e.g. with `PARWA Admin API Router (F06)  Platform admin endpoints for managing clients (com` and `Serialize company with user count for admin responses.`) actually correct?**
  _`Company` has 425 INFERRED edges - model-reasoned connections that need verification._
- **What connects `PARWA API Routes  All FastAPI routers are registered in backend/app/main.py dire`, `List invoices for the company.      Args:         page: Page number (1-indexed)`, `PARWA Health API Routes (Day 21, BC-012)  Provides /health, /ready, /health/deta` to the rest of the system?**
  _5220 weakly-connected nodes found - possible documentation gaps or missing edges._