<!-- converted from PARWA_Gap_Fix_Roadmap.docx -->


Table of Contents


# 1. Executive Summary
This roadmap documents all critical gaps identified during the comprehensive Technology Verification Audit of the PARWA AI-Powered Customer Support SaaS platform. The audit cross-referenced 6 specification documents, 10 feature spec batches, the Infrastructure Gaps Tracker, and the actual codebase implementation across 92 service files, 74 core modules, 49 API routes, and 43 test files. Phases 1 through 3 (Weeks 1-12) are complete, including the Week 12 Day 27 Security Audit and hardening pass.
The analysis identified 10 gaps that are NOT covered in any planned upcoming phase (Phase 4: Weeks 13-17, Phase 5: Weeks 18-21). These gaps must be resolved before Phase 4 begins because they affect core production functionality, billing integrity, and client trust. Six of these gaps were flagged as CRITICAL FINDINGS in the Technology Verification Report, confirming that the AI intelligence layer and critical infrastructure dependencies contain mock, stub, or severely outdated implementations rather than production-ready code.
The 10 gaps fall into three severity tiers: 6 Critical gaps that directly impact core product functionality (RAG intelligence, framework integrity, billing reliability), 3 High-severity gaps affecting operational quality and billing edge cases, and 1 Medium-severity gap related to infrastructure resilience testing. This roadmap provides a structured 5-day remediation plan to address all 10 gaps before Phase 4 begins.
# 2. Current State and Problem Analysis
## 2.1 Completed Work Summary
The PARWA platform has undergone substantial development across 12 weeks of build effort. Phase 1 (Weeks 1-3) established the complete foundation layer with 24 infrastructure items resolved, including FastAPI application structure, PostgreSQL with Alembic migrations, Redis caching, Celery task queues across 7 queues, Socket.io real-time communication, and comprehensive authentication (JWT, Google OAuth, Phone OTP with Twilio). Phase 2 (Weeks 4-7) built the core business logic: the complete ticket system with 70 features, 3896 tests passing, billing infrastructure with Paddle, onboarding wizard, and approval workflow system.
Phase 3 (Weeks 8-12) tackled the AI Engine build, including the Smart Router with real API calls to Google AI Studio, Cerebras, and Groq, the GSD (Guided Support Dialogue) state engine, 12 AI technique node stubs (Chain of Thought, ReAct, Tree of Thoughts, etc.), technique routing infrastructure with signal extraction and token budget management, and the comprehensive Week 12 Day 27 security audit covering PII detection, prompt injection defense, and financial accuracy validation. The total codebase comprises 217+ Python files, 93 service files, 74 core modules, 49 API routes, and thousands of passing tests.
## 2.2 What the Technology Verification Report Found
Despite the impressive breadth of structural development, the Technology Verification Report revealed a critical disconnect between what the documentation claims the system uses and what the codebase actually implements. The core infrastructure (FastAPI, Celery, Socket.io, PostgreSQL, Redis) is correctly implemented and well-wired. However, three AI frameworks referenced extensively in the documentation are either not used at all or running in severely degraded stub mode. Most critically, the entire RAG (Retrieval-Augmented Generation) pipeline depends on a MockVectorStore that generates random similarity scores, meaning the core AI intelligence pipeline cannot function in production without replacement. All 13 open-source libraries referenced in the project are real, actively maintained projects, but several are present only as package declarations in requirements.txt without actual integration code.
## 2.3 Why These Gaps Were Missed
The gaps exist because the development approach prioritized structural completeness over production-grade AI integration. This is a common pattern in AI product development where the skeleton (APIs, auth, billing, tickets) is solid but the brain (RAG, embeddings, prompt optimization) is the last piece to be fully productionized. The 8-week AI Engine phase (Phase 3) built the architectural framework for these systems but left the actual intelligence layer as mocks and stubs. The roadmap for Weeks 8-12 mentions these features in planning documents, but the actual implementations remain as simulation code rather than real integrations. This roadmap corrects that trajectory by making each gap a concrete, time-boxed remediation task.
# 3. Consolidated Gap Inventory
The following table presents all 10 gaps identified through cross-referencing the Technology Verification Report, Infrastructure Gaps Tracker, Day 27 Production Gaps Analysis, and the Build Roadmap documents. Each gap has been verified against actual codebase inspection to confirm its severity and scope.

## 3.1 Evidence Summary
Each gap has been verified against the actual codebase. The evidence is summarized below to establish the factual basis for remediation priority and effort estimation. This is not speculation; every claim is backed by direct code inspection.
- G-01: vector_search.py line 467 shows get_vector_store() returns MockVectorStore even in production environment. Line 483 says 'For now, return mock with warning.' Embeddings are generated via sha256 hash + Gaussian noise, not by any ML model.
- G-02: langgraph_workflow.py line 294 sets _langgraph_available=False on ImportError. Lines 625-715 show _simulate_preprocessing() uses keyword matching ('refund', 'cancel') and _simulate_core_step() returns hardcoded template: 'Thank you for your message. Regarding your query about...'.
- G-03: smart_router.py (1579 lines) makes real aiohttp HTTP calls to Google/Cerebras/Groq APIs. No import or usage of litellm package exists anywhere in the codebase.
- G-04: dspy_integration.py line 29 sets _DSPY_AVAILABLE=False. Line 142-147 defines StubPrediction returning response='' and confidence=0.0. Line 437-463 shows _stub_execute() returns hardcoded '[Fallback] Processing...' text.
- G-05: requirements.txt line 21 shows brevo-python==1.1.2. PyPI records show v1.x is in legacy mode; v4.0.5 is current with complete API rewrite.
- G-06: requirements.txt contains no paddle-related package. paddle_service.py uses custom httpx calls for Paddle API integration instead of the official SDK.
# 4. Detailed Remediation Plan
This section provides the specific fix strategy for each of the 10 gaps. Each remediation includes the affected files, the approach, key implementation details, acceptance criteria, and estimated effort. The fixes are ordered by dependency chain and severity.
## 4.1 G-01: Replace MockVectorStore with Real pgvector
### Current State
The file shared/knowledge_base/vector_search.py (510 lines) defines an abstract VectorStore interface and a MockVectorStore implementation. The mock stores everything in a Python dict, computes embeddings via sha256 hash + Gaussian noise, and performs cosine similarity in pure Python. The production code path at line 483 explicitly returns MockVectorStore with a warning log. This means the entire RAG pipeline, which is PARWA's core value proposition, is non-functional.
### Fix Strategy
Implement a new PgVectorStore class that inherits from VectorStore and implements all interface methods using real PostgreSQL pgvector operations. The fix requires: (1) Creating pgvector extension enablement in Alembic migration, (2) Writing real embedding generation using the configured LLM provider's embedding API (Google, Cerebras, or OpenAI-compatible endpoint), (3) Implementing cosine similarity search via SQL with proper index creation (IVFFlat or HNSW), (4) Adding metadata filtering for tenant isolation (company_id), document source, and content type, (5) Configuring proper chunk overlap and similarity thresholds, (6) Updating get_vector_store() factory to return PgVectorStore in production.
### Files to Modify
- shared/knowledge_base/vector_search.py: Add PgVectorStore class (new 200+ lines)
- shared/knowledge_base/embedding_generator.py: New file for real embedding API calls
- alembic/versions/xxx_enable_pgvector.py: Migration to CREATE EXTENSION vector
- alembic/versions/xxx_add_vector_indexes.py: IVFFlat/HNSW index creation
- app/core/config.py: Add embedding model configuration settings
- tests/test_pgvector_store.py: Integration tests with real pgvector queries
### Acceptance Criteria
- PgVectorStore returns cosine similarity scores from actual vector proximity, not random numbers
- Embeddings are generated by calling a real embedding API endpoint
- All existing MockVectorStore tests pass unchanged (backward compatibility)
- New integration tests verify search accuracy with sample documents
- Performance baseline: 1000 documents searchable within 50ms
## 4.2 G-02: Integrate Real LangGraph Workflow Engine
### Current State
The file app/core/langgraph_workflow.py (856 lines) imports LangGraph in a try/except block but catches ImportError and sets _langgraph_available=False. All 9 pipeline steps (classify, extract_signals, technique_select, context_compress, generate, quality_gate, context_health, dedup, format) are implemented as simulation methods. Intent classification uses keyword matching ('refund', 'cancel'), and the generate step returns a hardcoded template response. The quality gate always passes with score 0.92.
### Fix Strategy
Replace the simulation mode with a real LangGraph StateGraph implementation. The fix requires: (1) Removing the try/except ImportError guard and making LangGraph a hard dependency, (2) Creating a proper StateGraph with nodes for each pipeline step, (3) Defining state schema using TypedDict with all required fields (query, intent, sentiment, signals, context, response, confidence, metadata), (4) Implementing conditional edges for routing decisions (e.g., confidence-based technique selection), (5) Each node should call the corresponding real service (classification service, RAG service, response generation service), (6) Adding proper error handling with fallback edges, (7) Removing all _simulate_* methods and replacing with real LangGraph node functions.
### Files to Modify
- app/core/langgraph_workflow.py: Complete rewrite (remove simulation, add StateGraph)
- app/core/langgraph_nodes/: New directory with one file per node
- app/core/langgraph_state.py: TypedDict state schema definition
- requirements.txt: Change langgraph>=0.2.0 to langgraph>=1.0.0
- tests/test_langgraph_workflow.py: Integration tests with real StateGraph
### Acceptance Criteria
- _langgraph_available is always True after fix
- A real LangGraph StateGraph is created and executed for each query
- Each node calls actual service functions, not keyword matching
- Conditional edges work based on confidence scores and intent classification
- Error states trigger fallback edges, not hardcoded 0.92 scores
## 4.3 G-03: Integrate LiteLLM for Multi-Model Routing
### Current State
The file app/core/smart_router.py (1579 lines) contains a fully functional multi-model router with real aiohttp HTTP calls to Google AI Studio, Cerebras, and Groq APIs. It handles 10 models, implements retry/fallback chains, tracks provider health, and manages rate limiting. However, it does this through raw HTTP calls rather than using the LiteLLM library. The litellm package is declared in requirements.txt (line 24: litellm>=1.40.0) but is never imported or used anywhere in the codebase.
### Fix Strategy
Integrate LiteLLM as the routing layer in the Smart Router. The fix requires: (1) Replacing raw aiohttp calls with litellm.completion() calls, (2) Leveraging LiteLLM's built-in model routing, fallback, and retry mechanisms instead of custom implementations, (3) Using LiteLLM's provider abstraction to simplify adding new providers (currently adding a provider requires modifying MODEL_REGISTRY and writing custom HTTP call methods), (4) Configuring LiteLLM through environment variables or a config file for model credentials, (5) Keeping the existing ProviderHealthTracker as a PARWA-specific layer on top of LiteLLM's routing, (6) Updating the Technique Router to work through LiteLLM for technique-specific model selection.
### Files to Modify
- app/core/smart_router.py: Replace raw HTTP calls with litellm.completion()
- app/core/config.py: Add LiteLLM configuration settings
- requirements.txt: Pin litellm version (e.g., litellm>=1.40.0,<2.0.0)
- tests/test_smart_router.py: Update tests for LiteLLM integration
- docs/smart_router_config.md: New configuration documentation
### Acceptance Criteria
- All LLM calls go through LiteLLM, no raw aiohttp calls to LLM providers remain
- Adding a new provider requires only adding credentials, not writing HTTP code
- Retry and fallback behavior is preserved through LiteLLM's built-in mechanisms
- Existing test coverage is maintained with updated assertions
## 4.4 G-04: Activate DSPy from Stub Mode
### Current State
The file app/core/dspy_integration.py (735 lines) wraps DSPy in a try/except ImportError guard. When DSPy is not installed (which is the current state), every method falls back to stub behavior: StubModule returns StubPrediction with empty response and zero confidence, StubOptimizer.compile() is a no-op, and _stub_execute() returns hardcoded text with confidence=0.5. The _default_metric always returns 0.5. All prompt optimization, A/B testing, and technique versioning features are non-functional.
### Fix Strategy
Install and integrate DSPy as a real prompt optimization framework. The fix requires: (1) Ensuring dspy-ai package is actually installed and importable, (2) Defining real DSPy Signatures for each AI task (ticket classification, response generation, sentiment analysis), (3) Creating real DSPy Modules that wrap LLM calls through the Smart Router, (4) Configuring DSPy optimizers (BootstrapFewShot, MIPROv2, or BayesianSignatureOptimizer) for automated prompt improvement, (5) Implementing the metric functions for evaluating prompt quality (relevance, accuracy, conciseness), (6) Setting up the compilation pipeline that trains prompts on historical ticket data, (7) Replacing all StubModule/StubPrediction references with real DSPy objects, (8) Creating a DSPy training pipeline endpoint for periodic recompilation.
### Files to Modify
- app/core/dspy_integration.py: Remove stub fallback, integrate real DSPy
- app/core/dspy_signatures.py: New file with DSPy Signature definitions
- app/core/dspy_modules.py: New file with DSPy Module implementations
- app/core/dspy_metrics.py: New file with evaluation metrics
- app/tasks/dspy_training_tasks.py: Celery task for periodic recompilation
- tests/test_dspy_integration.py: Tests with real DSPy compilation
### Acceptance Criteria
- _DSPY_AVAILABLE is True after fix
- DSPy Signatures are defined for at least 3 core tasks
- DSPy compilation produces measurably better prompts than defaults
- StubModule and StubPrediction are no longer used anywhere
- A/B testing infrastructure works through DSPy's versioning system
## 4.5 G-05: Upgrade brevo-python from v1.1.2 to v4.0.5
### Current State
The brevo-python package at version 1.1.2 is from July 2024 and has been superseded by v4.0.5. The v1.x line is officially in legacy mode, receiving only critical security updates with no new features, no bug fixes, and no compatibility updates. The v4.x rewrite includes native async support (critical for PARWA's async FastAPI architecture), improved developer experience with a cleaner API, better error handling with structured exceptions, and updated webhook handling. Email is a critical dependency for OTP verification, notification delivery, and onboarding flows.
### Fix Strategy
Perform a systematic migration from brevo-python v1 to v4. The fix requires: (1) Updating requirements.txt to brevo-python>=4.0.0, (2) Identifying all imports from the old API (from brevo_python import ...) and mapping to new v4 equivalents, (3) Rewriting email_service.py to use the new TransactionalEmailsApi, (4) Updating all email template rendering calls to match the new SendSmtpEmail schema, (5) Testing OTP email delivery, notification emails, and webhook processing with the new SDK, (6) Updating error handling to use v4's structured exception classes, (7) Verifying async compatibility with the new SDK's native async support.
### Files to Modify
- requirements.txt: Update brevo-python==1.1.2 to brevo-python>=4.0.0
- app/services/email_service.py: Rewrite for v4 API
- app/services/notification_service.py: Update email calls
- app/webhooks/brevo_handler.py: Update webhook parsing for v4
- tests/test_email_service.py: Update all email delivery tests
### Acceptance Criteria
- All email sending works through v4 API with no legacy imports
- OTP verification emails deliver within 5 seconds
- Native async support eliminates need for sync wrappers
- All existing email tests pass with updated assertions
## 4.6 G-06: Add Paddle SDK and Migrate from Custom HTTP
### Current State
Paddle is the sole payment processor for PARWA subscriptions, the $1 voice demo, and variant billing. The codebase uses custom HTTP implementations in paddle_service.py instead of the official paddle-python-sdk package. The official SDK provides type-safe API calls with proper request/response models, automatic retry logic with exponential backoff, proper webhook signature verification (critical for security), compliance features for tax handling and subscription management, and structured error handling. Without the SDK, the billing system is more fragile, harder to maintain, and potentially vulnerable to webhook spoofing.
### Fix Strategy
Add the official Paddle SDK and migrate all billing operations. The fix requires: (1) Adding paddle-python-sdk to requirements.txt, (2) Creating a new paddle_client.py that wraps the SDK with PARWA-specific configuration, (3) Migrating subscription creation, update, and cancellation calls from custom HTTP to SDK methods, (4) Implementing proper webhook signature verification using SDK utilities, (5) Migrating the overage billing calculation to use SDK pricing methods, (6) Updating invoice retrieval to use SDK methods, (7) Removing custom HTTP billing code from paddle_service.py, (8) Adding comprehensive error handling for all Paddle SDK exceptions.
### Files to Modify
- requirements.txt: Add paddle-python-sdk
- app/clients/paddle_client.py: New file wrapping Paddle SDK
- app/services/paddle_service.py: Migrate from HTTP to SDK calls
- app/webhooks/paddle_handler.py: Use SDK webhook verification
- app/services/subscription_service.py: Update to use SDK methods
- tests/test_paddle_client.py: New test file for SDK integration
### Acceptance Criteria
- All Paddle API calls go through the official SDK
- Webhook signature verification is implemented and enforced
- No raw HTTP calls to Paddle remain in the codebase
- Error handling covers all Paddle SDK exception types
## 4.7 G-07: Knowledge Base Document Quality Validation
### Current State
The Technology Verification Report identified that even if pgvector is fixed, the quality of RAG depends heavily on document preparation: chunking strategy, metadata extraction, deduplication, and relevance scoring. The current system lacks document quality validation, which means a client uploading 200 messy PDFs could get significantly worse results than expected. There is no mechanism to assess document quality before processing, no chunk overlap configuration, no retrieval relevance feedback loop, and no gradual accuracy improvement metrics. This directly impacts the first impression when clients onboard.
### Fix Strategy
Implement a comprehensive document quality validation pipeline. The fix requires: (1) Creating a document_quality_validator service that assesses uploaded documents before processing, checking for: text extraction success rate, language detection, minimum content length, duplicate content detection, formatting quality (headers, lists, tables), and sensitive data scanning, (2) Implementing configurable chunk strategies (fixed-size with overlap, semantic chunking, paragraph-based), (3) Adding a retrieval relevance feedback mechanism that scores whether retrieved chunks actually answer the query, (4) Creating a quality dashboard metric that tracks RAG accuracy over time, (5) Implementing automatic re-chunking when accuracy drops below threshold.
### Files to Modify
- app/services/document_quality_service.py: New file for quality validation
- app/services/chunking_service.py: New file for configurable chunk strategies
- app/services/retrieval_feedback_service.py: New file for relevance feedback
- app/shared/knowledge_base/vector_search.py: Add feedback integration
- tests/test_document_quality.py: Tests for quality validation pipeline
### Acceptance Criteria
- Documents are validated before processing begins
- Quality scores are displayed in the onboarding dashboard
- Low-quality documents are flagged with specific improvement suggestions
- RAG accuracy metrics are tracked and displayed over time
## 4.8 G-08: Paddle Webhook Ordering and Missed Detection
### Current State
Payment success/failure depends entirely on Paddle webhook delivery. The current implementation handles basic webhook processing but lacks webhook sequence ordering (could process a refund event before the subscription creation event), out-of-order event handling, and missed webhook detection. The Infrastructure Gaps Tracker notes this as a Week 5 gap (BG-07, BG-15) that remains unresolved. A missed webhook could leave a paying client without activated access, or worse, process financial events in the wrong order leading to billing discrepancies.
### Fix Strategy
Implement a robust webhook processing system with ordering guarantees and missed detection. The fix requires: (1) Creating a webhook_sequence_tracker table to record event order and processing status, (2) Implementing a sequence number validation step that rejects out-of-order events and queues them for retry, (3) Creating a missed webhook detection system that periodically queries Paddle's API for recent events and reconciles against local records, (4) Adding an idempotency key store for webhook deduplication, (5) Implementing a webhook recovery Celery task that runs periodically (every 15 minutes) to detect and reprocess missed events, (6) Adding monitoring alerts for webhook processing failures.
### Files to Modify
- app/webhooks/paddle_handler.py: Add sequence validation and ordering
- app/tasks/webhook_recovery.py: New file for missed webhook detection
- app/services/webhook_sequence_service.py: New file for ordering logic
- alembic/versions/xxx_webhook_sequences.py: Migration for sequence tracking
- tests/test_webhook_ordering.py: Tests for out-of-order scenarios
### Acceptance Criteria
- Webhooks are processed in strict sequence order
- Out-of-order events are detected and queued for later processing
- Missed webhooks are detected within 15 minutes
- Idempotency keys prevent duplicate event processing
## 4.9 G-09: Response Quality Benchmarking Suite
### Current State
The current system lacks any mechanism to measure, track, or guarantee AI response quality over time. There are no response versioning records to track how responses change, no A/B testing infrastructure for prompts (DSPy is in stub mode), no consistency benchmarks, and no response quality baselines. Without these, it is impossible to demonstrate improvement to clients or guarantee consistent quality. Clients comparing AI responses across interactions will notice day-to-day variations in behavior, which damages trust.
### Fix Strategy
Implement a comprehensive response quality benchmarking suite. The fix requires: (1) Creating a benchmark dataset of standard queries with expected response categories and quality criteria, (2) Implementing automated evaluation that scores responses on relevance, accuracy, completeness, tone consistency, and safety, (3) Creating a response versioning system that stores each AI response with its metadata (model used, technique applied, confidence score, latency), (4) Building a quality dashboard with trend charts showing accuracy, relevance, and consistency over time, (5) Implementing regression detection that alerts when quality metrics drop below baseline.
### Files to Modify
- app/services/benchmark_service.py: New file for benchmark execution
- app/services/response_quality_service.py: New file for quality scoring
- app/services/response_versioning_service.py: New file for response tracking
- app/tasks/benchmark_tasks.py: Celery task for scheduled benchmarks
- tests/test_benchmark_suite.py: Tests for benchmark accuracy
### Acceptance Criteria
- A benchmark dataset of at least 100 standard queries exists
- Automated benchmarks run daily and track quality metrics over time
- Quality drops trigger alerts when below configurable thresholds
- Response versioning enables comparison across model/technique changes
## 4.10 G-10: Chaos Engineering and Failure Injection
### Current State
The system has never been tested with more than one active tenant simultaneously. There are no documented handling procedures for critical failure scenarios: database failover (PostgreSQL going down mid-conversation), Redis cluster failure (all rate limiting, sessions, and caching stops), LLM provider outage (all three providers going down simultaneously), or deployment rollback during active client sessions. These are black swan events that would affect all clients simultaneously and require documented runbooks.
### Fix Strategy
Implement chaos engineering tests and create emergency runbooks. The fix requires: (1) Creating a chaos testing framework that can simulate: database connection loss, Redis failure, LLM provider timeout, external API failure, and network latency spikes, (2) Writing automated chaos tests that verify graceful degradation for each failure scenario, (3) Creating runbook documents for each failure scenario with step-by-step recovery procedures, (4) Implementing circuit breaker patterns for all external service calls (Paddle, Brevo, Twilio, LLM providers), (5) Adding a system-wide health dashboard that shows degradation status in real-time.
### Files to Modify
- tests/chaos/test_database_failover.py: Simulated DB failure tests
- tests/chaos/test_redis_failure.py: Redis failure graceful degradation
- tests/chaos/test_llm_outage.py: LLM provider cascade failure
- docs/runbooks/ - Emergency response runbooks
- app/core/circuit_breaker.py: Circuit breaker implementation
### Acceptance Criteria
- Chaos tests verify graceful degradation for all failure scenarios
- Runbooks exist for database, Redis, LLM, and deployment failures
- Circuit breakers protect all external API calls
- Health dashboard shows real-time system degradation status
# 5. Implementation Timeline
The 10 gaps are organized into a 5-day remediation sprint. Days are structured by dependency order and severity, with Critical gaps addressed first. Each day includes both implementation work and testing verification.

## 5.1 Daily Breakdown
### Day 1: AI Intelligence Core (G-01 + G-02)
This is the highest-priority day because G-01 (MockVectorStore) directly undermines PARWA's core value proposition. The morning session focuses on replacing MockVectorStore with PgVectorStore, including creating the Alembic migration for pgvector extension, implementing real embedding generation, and writing the cosine similarity search queries. The afternoon session replaces LangGraph simulation mode with a real StateGraph, defining proper state schemas and node functions that call actual services. By end of day, both the RAG pipeline and workflow engine should be calling real code, not mocks.
### Day 2: AI Framework Integration (G-03 + G-04)
Day 2 focuses on making the two most important AI frameworks (LiteLLM and DSPy) actually work instead of being decorative package declarations. The morning session migrates the Smart Router from raw aiohttp calls to LiteLLM's routing layer, which simplifies provider management and enables easier addition of new models. The afternoon session activates DSPy from stub mode, defining real signatures, modules, and compilation pipelines. By end of day, the documentation claims about using LangGraph, LiteLLM, and DSPy will be factually accurate.
### Day 3: Dependencies and Billing (G-05 + G-06)
Day 3 addresses critical infrastructure dependencies. The morning session upgrades brevo-python from v1.1.2 to v4.0.5, which involves API migration for all email-related code. The afternoon session integrates the official Paddle SDK, replacing custom HTTP implementations with type-safe SDK calls and adding webhook signature verification. Both fixes directly impact revenue collection and customer communication reliability.
### Day 4: Quality and Reliability (G-07 + G-08)
Day 4 focuses on client-facing quality improvements. The morning session implements the document quality validation pipeline, ensuring clients get good results from their uploaded knowledge bases. The afternoon session adds webhook ordering and missed detection for Paddle, preventing the scenario where a paying customer does not receive access due to webhook processing errors.
### Day 5: Benchmarking and Resilience (G-09 + G-10)
The final day establishes ongoing quality assurance and resilience testing. The morning session creates the response quality benchmarking suite with automated daily runs and trend tracking. The afternoon session implements the chaos engineering framework and writes emergency runbooks for critical failure scenarios. By end of day, the system will have the infrastructure to continuously monitor and improve AI quality, plus documented procedures for handling catastrophic failures.
# 6. Dependency Graph and Critical Path
The 10 gaps have interdependencies that constrain the implementation order. Understanding these dependencies is essential for the 5-day plan to succeed without blocking.

The critical path runs through G-01 (pgvector) because it is the foundation for both document quality validation (G-07) and benchmarking (G-09). G-03 (LiteLLM) is the critical path for G-04 (DSPy), since DSPy compilation needs proper model routing. The plan addresses these critical path items on Days 1-2, giving maximum buffer for the remaining gaps.
# 7. Risk Analysis and Mitigation
Each remediation carries technical risks that must be acknowledged and planned for. The following analysis identifies the top risks and provides specific mitigation strategies.

# 8. Resource Requirements

The most critical resource requirement is a PostgreSQL instance with the pgvector extension installed and enabled. Without this, G-01 cannot be completed, and the entire RAG pipeline remains non-functional. All other resources should be available from the existing development environment.
# 9. Success Criteria and Verification
The remediation is considered complete when all of the following criteria are met. Each criterion maps to specific acceptance criteria defined in Section 4.
- No MockVectorStore code path is reachable in production environment. All RAG queries execute real pgvector cosine similarity search.
- LangGraph _langgraph_available is True. A real StateGraph executes for every query with actual service calls in each node.
- LiteLLM is the exclusive routing layer for all LLM calls. Zero raw aiohttp HTTP calls to LLM provider endpoints remain.
- DSPy _DSPY_AVAILABLE is True. Real DSPy Signatures, Modules, and compilation pipeline produce optimized prompts.
- brevo-python version is 4.x. All email operations use v4 API with native async support.
- paddle-python-sdk is in requirements.txt. All billing operations use SDK methods with webhook signature verification.
- Document quality validation runs on every upload. Quality scores are tracked and low-quality documents are flagged.
- Webhook ordering is enforced. Missed webhook detection runs every 15 minutes. Zero out-of-order processing incidents.
- Automated quality benchmarks run daily. Trend data shows improvement or stability over 7-day rolling window.
- Chaos tests cover all 5 failure scenarios. Emergency runbooks exist for database, Redis, LLM, and deployment failures.
# 10. Post-Remediation: Phase 4 Handoff
Once all 10 gaps are resolved and verified, the PARWA platform will be ready to proceed with Phase 4 (Weeks 13-17: Channels, Jarvis Command Center, Dashboard, Integrations, Mobile) and Phase 5 (Weeks 18-21: Public Pages, Training Pipeline, Polish, Load Testing). The gap fixes ensure that the foundational AI intelligence layer is production-ready before building the user-facing features that depend on it.
The critical handoff criteria are: (1) RAG pipeline returns real, relevant results from client knowledge bases, (2) AI workflow engine processes queries through real LangGraph state machines, (3) Model routing uses proper abstraction (LiteLLM) for maintainability, (4) Prompt optimization is functional (DSPy) for continuous improvement, (5) Email delivery is reliable and modern (Brevo v4), (6) Billing is secure and robust (Paddle SDK), (7) Document quality is validated before processing, (8) Payment webhooks are processed reliably in correct order, (9) AI quality is measured and tracked over time, and (10) System resilience is tested and documented.
With these 10 gaps closed, the documentation claims will match the codebase reality, and the platform will be on a solid foundation for the feature-rich Phase 4-5 development that follows.
| Technology Verification & Infrastructure Gap Analysis
Version 1.0 | April 2026

CONFIDENTIAL — Internal Use Only |
| --- |
| ID | Gap Description | Severity | Source | Covered in Phase 4/5? |
| --- | --- | --- | --- | --- |
| G-01 | MockVectorStore uses random similarity scores instead of real pgvector cosine similarity. Production path explicitly returns mock. | CRITICAL | Tech Verification 4.1 | No |
| G-02 | LangGraph imported but never executed. All 9 workflow steps use keyword matching and template strings. No real StateGraph created. | CRITICAL | Tech Verification 2.2.1 | No |
| G-03 | LiteLLM declared in requirements.txt but Smart Router uses raw aiohttp calls. No actual LiteLLM routing integration exists. | CRITICAL | Tech Verification 2.2.3 | No |
| G-04 | DSPy running in full stub mode. _DSPY_AVAILABLE=False. All operations return empty responses with confidence=0.5. | CRITICAL | Tech Verification 2.2.2 | No |
| G-05 | brevo-python v1.1.2 severely deprecated (July 2024). v4.0.5 available with native async, better error handling. | HIGH | Tech Verification 4.3 | No |
| G-06 | Paddle SDK not in requirements.txt. Billing uses custom HTTP instead of official paddle-python-sdk. | HIGH | Tech Verification 4.4 | No |
| G-07 | No KB document quality validation. Clients uploading messy PDFs get unpredictable results. | HIGH | Tech Verification 5.1 | No |
| G-08 | Paddle webhook ordering and missed detection. Could process refund before subscription creation. | HIGH | Tech Verification 5.3 | No |
| G-09 | No response quality benchmarking suite. Cannot demonstrate AI improvement or guarantee consistency. | MEDIUM | Tech Verification 5.4 | No |
| G-10 | No chaos engineering or failure injection testing. Emergency scenarios not documented. | MEDIUM | Tech Verification 5.6 | No |
| Day | Gap IDs | Theme | Key Deliverables |
| --- | --- | --- | --- |
| Day 1 | G-01, G-02 | AI Intelligence Core | PgVectorStore with real pgvector; LangGraph StateGraph with real nodes; embedding generation API |
| Day 2 | G-03, G-04 | AI Framework Integration | LiteLLM routing in Smart Router; DSPy compilation pipeline; real prompt optimization |
| Day 3 | G-05, G-06 | Dependencies & Billing | brevo-python v4 migration; Paddle SDK integration; webhook signature verification |
| Day 4 | G-07, G-08 | Quality & Reliability | Document quality validation pipeline; webhook ordering and missed detection system |
| Day 5 | G-09, G-10 | Benchmarking & Resilience | Response quality benchmark suite; chaos engineering framework; emergency runbooks |
| Gap | Depends On | Blocks | Can Parallel With |
| --- | --- | --- | --- |
| G-01 (pgvector) | None | G-07, G-09 | G-02 |
| G-02 (LangGraph) | None | G-09 | G-01 |
| G-03 (LiteLLM) | None | G-04 | G-04 |
| G-04 (DSPy) | G-03 (LiteLLM routing) | G-09 | None |
| G-05 (Brevo v4) | None | None | G-06 |
| G-06 (Paddle SDK) | None | G-08 | G-05 |
| G-07 (Doc Quality) | G-01 (pgvector) | G-09 | G-08 |
| G-08 (Webhook Order) | G-06 (Paddle SDK) | None | G-07 |
| G-09 (Benchmarks) | G-01, G-02, G-04, G-07 | None | G-10 |
| G-10 (Chaos) | None | None | G-09 |
| Risk | Impact | Probability | Mitigation |
| --- | --- | --- | --- |
| pgvector index creation fails on existing data | Blocks G-01 and downstream gaps | Medium | Test on staging copy first; use IVFFlat (faster build) before HNSW; keep MockVectorStore as fallback |
| LangGraph v1 has breaking API changes | G-02 implementation takes longer | Medium | Pin version in requirements.txt; review migration guide before starting |
| LiteLLM routing adds latency overhead | Production response times increase | Low | Benchmark before/after; use LiteLLM's caching layer; keep custom health tracker |
| DSPy compilation requires significant training data | G-04 results below expectations | Medium | Use BootstrapFewShot (data-efficient); start with 50 labeled examples; iterate later |
| Brevo v4 API breaks existing email flows | OTP and notifications stop working | Medium | Test all email flows in staging first; keep v1 rollback plan; deploy during low-traffic window |
| Paddle SDK missing features vs custom HTTP | Some billing operations unsupported | Low | Audit SDK feature completeness first; fall back to custom HTTP for edge cases |
| Chaos tests cause production instability | Accidental service disruption | Low | Run chaos tests only in staging; use feature flags; never run against production |
| Resource | Requirement | Purpose |
| --- | --- | --- |
| Developer Time | 5 days (40 hours) | Implementation of all 10 gap fixes |
| PostgreSQL Instance | With pgvector extension | Real vector similarity search (G-01) |
| LLM API Keys | Google AI Studio + Cerebras + Groq | Embedding generation and DSPy compilation |
| Staging Environment | Full replica of production | Testing all changes before deployment |
| Paddle Sandbox | Test mode API access | Webhook ordering and SDK testing (G-06, G-08) |
| Brevo Test Account | v4 API access | Email delivery verification (G-05) |