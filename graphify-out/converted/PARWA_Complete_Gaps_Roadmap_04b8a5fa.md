<!-- converted from PARWA_Complete_Gaps_Roadmap.docx -->


Table of Contents
(Right-click on the table of contents above and select 'Update Field' to refresh page numbers after opening in Word.)


# 1. Executive Summary
This document serves as the single authoritative roadmap for fixing all identified gaps in the Parwa AI Customer Care SaaS codebase. It consolidates findings from four independent audit sessions conducted over the past weeks, including a comprehensive security audit, an AI feature integrity audit, a billing and infrastructure audit, and a code-level stub detection analysis. All previously created roadmaps (the 8-day security roadmap, 3-day variant engine roadmap, and various weekly sprint plans) are superseded and replaced by this document.
The total gap count stands at 120+ issues organized across four major categories. The security audit alone uncovered 93 findings (15 CRITICAL, 22 HIGH, 39 MEDIUM, 17 LOW) that block any production deployment. The AI integrity audit revealed that all 12 advertised AI reasoning techniques (Chain of Thought, Tree of Thought, ReAct, Reflexion, Self-Consistency, Universe of Thought, Grapheme State Tracking, Least-to-Most, CRP, Step-Back, Reverse Thinking, and their variants) are implemented as pure regex and template matching with zero LLM API calls. The DSPy integration uses a StubModule that always returns fallback values, and the Agent Lightning training system returns zero samples and null training job IDs. The CLARA RAG system is a scoring wrapper with no actual HyDE, Multi-Query, or Contextual Compression implementation. The MAKER Framework is a set of pass-through LangGraph nodes with none of the advertised 6-24 LLM calls per query.
This 10-day roadmap prioritizes work into a logical progression: critical security vulnerabilities are addressed first (Days 1-2) to establish a baseline production safety, followed by the complete rebuild of the AI reasoning layer (Days 3-4) to make the product's core value proposition real, then remaining security issues and incomplete features (Days 5-7), infrastructure and production readiness (Days 8-9), and finally comprehensive testing and documentation (Day 10). Each day includes a specific list of gaps to fix, files to modify or create, acceptance criteria, and estimated effort in hours.

# 2. Complete Gap Inventory
## 2.1 Category A: Security Gaps (93 Items)
The security audit examined every security-relevant file across the entire Parwa codebase, including Backend (FastAPI), Frontend (Next.js), Dashboard, MCP Server, Database, and Infrastructure layers. The system demonstrates strong security architecture in several areas, particularly tenant isolation via SQLAlchemy events, constant-time HMAC comparisons, bcrypt password hashing with cost 12, progressive account lockout, HTTP-only cookies on the backend, path traversal prevention, and webhook input sanitization. However, the audit uncovered 15 CRITICAL vulnerabilities that must be resolved before any production deployment, 22 HIGH findings that create significant attack surface, 39 MEDIUM findings that weaken the overall security posture, and 17 LOW findings representing best-practice improvements.
## 2.2 Category B: Fake/Stub AI Features (28 Items)
The AI integrity audit is arguably the most damaging finding for the Parwa product. The core value proposition of Parwa is its AI-powered customer care capabilities, yet the vast majority of the AI intelligence layer is completely fabricated. All 12 advertised AI reasoning techniques are implemented as simple regex pattern matchers or template string formatters. None of them make a single LLM API call. This means the product's primary differentiator, its ability to reason through complex customer queries using advanced AI techniques, does not exist in any functional form.
## 2.3 Category C: Incomplete Real Features (12 Items)
Not everything in the codebase is fake. Several subsystems have genuine implementations that are partially working but incomplete. The GSD (Goal-State Decomposition) State Engine has a real state machine implementation but is missing critical transition handlers. The Smart Router genuinely routes between 11 configured LLM models (including Cerebras, Groq, and Google direct connections), but lacks proper fallback validation. The LangGraph workflow correctly compiles a 19-node StateGraph, though many of those nodes are stubs or thin wrappers. The AI Pipeline has 13 stages implemented, but the quality of intermediate stage outputs is unvalidated.

# 3. The 10-Day Fix-All Roadmap
The following 10-day plan organizes all 120+ gaps into a logical execution sequence. Each day builds on the previous day's work. Days 1-2 establish the minimum security baseline required for any deployment. Days 3-4 rebuild the core AI intelligence layer to make the product's primary value proposition real. Days 5-7 address remaining security issues and complete partially-implemented features. Days 8-9 focus on infrastructure hardening and production readiness. Day 10 is dedicated to comprehensive testing and documentation.
## 3.1 Day 1: Critical Security - Auth & Access Control
Theme: Eliminate all authentication and access control vulnerabilities that allow unauthorized access to tenant data, AI resources, and admin functions. This is the single most important day because without proper auth, nothing else matters.
Estimated Effort: 10-12 hours
Files to Modify: 14 core files across frontend, backend, and dashboard
### Day 1.1: Frontend Auth Overhaul (4 hours)
[C-02] Frontend Auth Tokens Are NOT Real JWTs (CRITICAL) - Replace parwa_at_<uuid> tokens with proper JWT signing using jose or jsonwebtoken. Tokens must include claims: sub, company_id, role, exp, iat. Frontend login and register routes must call backend to sign tokens, not generate random UUIDs. Files: src/app/api/auth/login/route.ts, register/route.ts.
[C-03] Auth Tokens in localStorage - XSS-Stealable (CRITICAL) - Migrate from localStorage to httpOnly secure cookies. The backend already sets cookies correctly, but the frontend ignores them entirely. Refactor all auth state to use cookie-based sessions. Remove all localStorage.setItem calls for tokens. Files: src/app/(auth)/login/page.tsx, signup/page.tsx.
[H-03] Registration Bypasses Email Verification (HIGH) - Fix register route that creates users with is_verified: true by default. New users must start with is_verified: false and only become verified after clicking the email confirmation link. File: src/app/api/auth/register/route.ts.
[H-02] OTP Comparison NOT Timing-Safe (HIGH) - Replace JavaScript !== comparison with crypto.timingSafeEqual for OTP verification. Both verify-otp and reset-password routes are vulnerable to timing attacks. Files: src/app/api/auth/verify-otp/route.ts, reset-password/route.ts.
[M-20] No Password Complexity Requirements (MEDIUM) - Enforce minimum password requirements: 8+ chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char. Apply to both registration and password reset flows. Files: register/route.ts, reset-password/route.ts.
### Day 1.2: Backend Auth & Admin Access (4 hours)
[C-01] Dashboard API Routes Have ZERO Authentication (CRITICAL) - Add authentication middleware to all dashboard API routes (send-email, send-sms, ticket-solve, analytics, channel-status). Every endpoint must verify the Authorization header or session cookie. Without this, anyone on the internet can send emails, SMS, and invoke AI resolution using your API keys. Files: dashboard/src/app/api/**/*.ts.
[C-09] MFA Login Verification Requires JWT - Unreachable (CRITICAL) - The /mfa/verify endpoint has get_current_user dependency which requires a JWT, but during login the user doesn't have one yet. Implement a temporary MFA session token that's created when MFA is initiated and verified in the /mfa/verify endpoint. File: backend/app/api/mfa.py.
[C-10] Admin Endpoints Use require_roles(owner) Not Platform Admin (CRITICAL) - Any company owner can access ALL other companies' data through admin endpoints. Add a platform_admin boolean flag to the User model and create a require_platform_admin dependency. Replace all require_roles('owner') calls in admin.py with the new dependency. File: backend/app/api/admin.py, backend/app/api/deps.py.
[C-11] Billing Status Endpoint Completely Unauthenticated (CRITICAL) - Add authentication to the get_billing_status endpoint. Anyone can currently query any company's billing status by guessing company IDs. File: backend/app/api/billing_webhooks.py.
[C-12] RAG Search Cross-Tenant Knowledge Base Access (CRITICAL) - Remove the body.get('company_id', company_id) pattern that allows users to override their JWT-derived company_id. Force all RAG operations to use the authenticated user's company_id only. File: backend/app/api/rag.py (lines 79, 129, 223).
### Day 1.3: MCP Server & Chat Widget Auth (2-3 hours)
[C-04] MCP Server Auth Token Never Enforced (CRITICAL) - The MCP_AUTH_TOKEN is configured but never checked in any endpoint. Add a middleware or decorator that validates this token on every incoming request to all 14 MCP sub-servers. File: mcp_server/main.py.
[H-14] Chat Widget company_id Not Validated (HIGH) - The chat widget session creation accepts any client-supplied company_id without verifying it exists or is active. Add a database lookup to validate the company_id before creating a session. File: backend/app/api/chat_widget.py.
[H-18] Chat API Completely Unauthenticated (HIGH) - The frontend chat API route proxies directly to LLM APIs with no authentication. Anyone can burn your API credits. Add auth verification before proxying. File: src/app/api/chat/route.ts.
### Day 1 Acceptance Criteria
All 15 CRITICAL auth findings are resolved. Dashboard endpoints reject unauthenticated requests with 401. Frontend uses JWT tokens signed by the backend with proper claims. MFA flow completes end-to-end. Admin endpoints verify platform_admin flag. RAG operations are scoped to authenticated tenant only. MCP server requires valid auth token on every request. Chat widget validates company_id against the database.
## 3.2 Day 2: Critical Security - Data Protection & Infrastructure
Theme: Fix all remaining CRITICAL vulnerabilities related to secrets management, cross-tenant data leaks, encryption, and infrastructure exposure. After Day 2, no CRITICAL vulnerabilities should remain.
Estimated Effort: 10-12 hours
Dependencies: Day 1 (auth layer must be working for tenant isolation fixes)
### Day 2.1: Secrets & CORS (3 hours)
[C-05] CORS Wildcard + Credentials = Complete CORS Bypass (CRITICAL) - Remove the fallback to ['*'] when CORS_ORIGINS is empty. In production, CORS must require explicit origin configuration. If no origins are configured, block all cross-origin requests rather than allowing all. File: backend/app/main.py (lines 299-315).
[C-06] Weak Secret Defaults Only Warn Never Block (CRITICAL) - Change config.py validators from warnings.warn() to raising ValueError in production. If SECRET_KEY, JWT_SECRET_KEY, or DATA_ENCRYPTION_KEY still contain dev defaults when ENVIRONMENT=production, the application must refuse to start. File: backend/app/config.py (lines 26, 51, 95).
[C-07] .env.prod Committed to Git (CRITICAL) - Remove .env.prod from git tracking entirely. Add it to .gitignore. Run git rm --cached .env.prod. Add a pre-commit hook that prevents committing any .env files. The production infrastructure topology should not be in version control.
[C-15] Insecure Default Refresh Token Pepper (CRITICAL) - Remove the fallback default for REFRESH_TOKEN_PEPPER. If the environment variable is not set, raise an error on startup. A known pepper combined with a database leak enables forged refresh tokens for every user. File: backend/app/core/auth.py (lines 29-31).
### Day 2.2: Cross-Tenant Isolation & Data Protection (4 hours)
[C-08] Client-Controlled X-Company-ID Header Trusted (CRITICAL) - Remove the variant_check.py code that trusts the X-Company-ID header from the client. The TenantMiddleware correctly avoids client-controlled headers, but variant_check.py violates this principle. Always derive company_id from the JWT token. File: backend/app/middleware/variant_check.py (lines 208-211).
[C-13] No Database SSL/TLS for PostgreSQL (CRITICAL) - Add connect_args={'sslmode': 'require'} to all PostgreSQL connection configurations. Database traffic currently flows unencrypted, enabling MITM attacks to read, modify, or inject SQL queries. File: database/base.py (lines 60-65).
[C-14] Sensitive OAuth Tokens Stored in Plaintext (CRITICAL) - Encrypt Google OAuth access_token and refresh_token columns using the DATA_ENCRYPTION_KEY with AES-256-GCM. Implement encrypt/decrypt helpers and apply them at the ORM level using SQLAlchemy hybrids or event listeners. File: database/models/core.py (lines 330-332).
[H-05] Tenant Middleware Skips /api/billing/ and /api/admin/ (HIGH) - Remove billing and admin from the PUBLIC_PREFIXES exclusion list in the tenant middleware. Every new endpoint added to these paths without explicit company_id checks creates a cross-tenant data leak. Either enforce tenant isolation in middleware or add explicit per-endpoint checks. File: backend/app/middleware/tenant.py (lines 42-55).
[H-22] Workflow Path Parameter Overrides JWT company_id (IDOR) (HIGH) - Remove the path parameter company_id override in workflow endpoints. The authenticated user from Company A can currently query Company B's workflows by supplying a different company_id in the URL. File: backend/app/api/workflow.py (lines 880-886).
### Day 2.3: Infrastructure Security (3 hours)
[H-09] Pricing Signing Key Hardcoded in Source (HIGH) - Move PRICING_SIGNING_KEY to an environment variable. Anyone with repo access can currently forge pricing tokens. File: backend/app/api/pricing.py (line 662).
[H-10] No Redis Authentication Enforcement (HIGH) - Add REDIS_PASSWORD configuration and require it in production. Currently any network process can read/write all tenant data in Redis. Update redis.py to use password auth. File: backend/app/core/redis.py (lines 291-300).
[H-11] MD5 Used for File Integrity (HIGH) - Replace all MD5 file integrity checks with SHA-256. MD5 is cryptographically broken and file integrity checks can be bypassed. Files: backend/app/core/storage.py (lines 438, 795, 888, 898).
[M-10] No jti Claim on JWTs (MEDIUM) - Add a jti (JWT ID) claim to all issued tokens to enable individual token revocation and blacklist support. File: backend/app/core/auth.py (line 63).
[M-12] SHA-256 for API Key Hashing Too Fast (MEDIUM) - Replace SHA-256 API key hashing with bcrypt or argon2id. If the database is leaked, SHA-256 allows fast brute-force of API keys. File: security/api_keys.py (line 180).
### Day 2 Acceptance Criteria
Zero CRITICAL vulnerabilities remain. CORS never falls back to wildcard. Production startup fails with clear error if any secret still uses dev defaults. .env.prod is removed from git. X-Company-ID header is never trusted. PostgreSQL connections use SSL. OAuth tokens are encrypted at rest. Billing and admin endpoints enforce tenant isolation. Redis requires password auth. File integrity uses SHA-256.
## 3.3 Day 3: AI Rebuild - Core LLM Integration
Theme: Rebuild all 12 AI reasoning techniques from scratch to use real LLM API calls. This is the most impactful day for the product because the core value proposition (AI-powered reasoning) is currently 100% fake. After Day 3, every AI technique will make real LLM calls through the Smart Router.
Estimated Effort: 12-14 hours
Dependencies: Days 1-2 (security must be stable before adding real LLM calls)
### Day 3.1: Foundation - LLM Client Abstraction (3 hours)
Before rebuilding individual techniques, we need a shared LLM client abstraction that all techniques will use. This client should route through the existing Smart Router (which already has 11 models configured) and handle retries, timeouts, token counting, and error handling consistently.
[AI-F01] Create shared LLM technique client (CRITICAL) - Build backend/app/core/techniques/llm_client.py that wraps the Smart Router with technique-specific helper methods: generate(prompt, system_prompt, temperature, max_tokens), generate_chain(messages[]), generate_with_examples(prompt, examples[]). This client must support structured output parsing, token budget tracking, and automatic model fallback. All 12 techniques will use this client instead of making direct API calls.
[AI-F02] Create technique base class with LLM integration (CRITICAL) - Refactor backend/app/core/techniques/base.py to include an execute_with_llm() method that uses the new LLM client. The base class should enforce that every technique either calls an LLM or raises NotImplementedError. Add abstract methods: build_prompt(context), parse_response(llm_output), validate_output(parsed). Files: backend/app/core/techniques/base.py.
### Day 3.2: Rebuild Primary Reasoning Techniques (6 hours)
[AI-01] Chain of Thought - Real Implementation (CRITICAL) - Replace regex matching with actual LLM calls that generate step-by-step reasoning. Implementation: (1) Build a CoT prompt template that instructs the LLM to think step-by-step, (2) Send the customer query + context through the LLM client with temperature=0.3, (3) Parse the LLM's chain-of-thought output, (4) Extract the final answer from the reasoning chain, (5) Track token usage for billing. File: backend/app/core/techniques/chain_of_thought.py.
[AI-02] Tree of Thought - Real Implementation (CRITICAL) - Implement actual multi-branch exploration using the LLM. For each reasoning step: (1) Generate 3-5 thought branches using the LLM, (2) Evaluate each branch for promise using a separate LLM call, (3) Prune low-scoring branches, (4) Continue exploring top branches for 2-3 depth levels, (5) Select the highest-scoring path as the final answer. This genuinely uses multiple LLM calls per query. File: backend/app/core/techniques/tree_of_thoughts.py.
[AI-03] ReAct - Real Implementation (CRITICAL) - Implement the Reasoning + Action loop: (1) LLM generates a thought and selects an action from available tools, (2) Execute the action (query knowledge base, check order status, look up customer info), (3) Feed the observation back to the LLM, (4) Loop until the LLM outputs a final answer. Integrate with existing react_tools (billing_tool, order_tool, ticket_tool, crm_tool). File: backend/app/core/techniques/react.py.
[AI-04] Reflexion - Real Implementation (CRITICAL) - Implement self-evaluation and retry: (1) Generate initial response using the LLM, (2) Ask the LLM to evaluate its own response against the query, (3) If the evaluation score is below threshold, ask the LLM to reflect on what went wrong and generate an improved response, (4) Repeat up to 3 cycles or until quality threshold is met. Track improvement across cycles. File: backend/app/core/techniques/reflexion.py.
[AI-05] Self-Consistency - Real Implementation (CRITICAL) - Implement majority voting: (1) Generate N=5 independent responses using the same prompt but different temperature settings (0.3, 0.5, 0.7, 0.9, 1.0), (2) Parse each response to extract the core answer/recommendation, (3) Count frequency of each unique answer, (4) Return the most common answer with confidence score. File: backend/app/core/techniques/self_consistency.py.
### Day 3.3: Rebuild Secondary Reasoning Techniques (3 hours)
[AI-06] Universe of Thought - Real Implementation (HIGH) - Implement multi-perspective analysis: Generate responses from 3 different system prompt perspectives (e.g., customer advocate, company policy expert, practical problem-solver), then synthesize a final answer that incorporates insights from all perspectives. Each perspective requires a separate LLM call.
[AI-08] Least-to-Most - Real Implementation (HIGH) - Implement decomposition: (1) Ask the LLM to decompose the complex query into 2-4 simpler sub-questions, (2) Solve each sub-question sequentially using the LLM with accumulated context, (3) Synthesize the final answer from all sub-question answers.
[AI-10] Step-Back - Real Implementation (MEDIUM) - Implement abstract reasoning: (1) First LLM call generates a high-level abstraction of the problem, (2) Second LLM call reasons about the abstracted problem, (3) Third LLM call applies the abstract reasoning back to the specific customer query.
[AI-11] Reverse Thinking - Real Implementation (MEDIUM) - Implement backward reasoning: (1) First LLM call hypothesizes what the ideal resolution would look like, (2) Second LLM call works backwards from the ideal state to identify what steps are needed, (3) Third LLM call validates the plan against the actual customer situation.
### Day 3 Acceptance Criteria
Chain of Thought, Tree of Thought, ReAct, Reflexion, and Self-Consistency all make real LLM API calls. Each technique accepts a context object (customer query, conversation history, knowledge base results) and returns a structured response with the technique's output, token usage, and latency metrics. The shared LLM client successfully routes through the Smart Router. Unit tests confirm that zero techniques use regex or template-only responses. Token usage is tracked and billable.
## 3.4 Day 4: AI Rebuild - Frameworks & RAG
Theme: Rebuild the CLARA RAG system, MAKER Framework, DSPy integration, and Agent Lightning training. These are the higher-level AI systems that compose the individual techniques into a complete customer care pipeline.
Estimated Effort: 12-14 hours
Dependencies: Day 3 (individual techniques must be working)
### Day 4.1: CLARA RAG Rebuild (4 hours)
[AI-14] CLARA RAG - Implement Real Advanced Retrieval (CRITICAL) - Replace the simple scoring wrapper with actual advanced RAG capabilities. Implement three key features: (1) HyDE (Hypothetical Document Embedding) - generate a hypothetical answer using the LLM, embed it, and use it for retrieval, (2) Multi-Query Retrieval - generate 3 alternative phrasings of the query using the LLM and retrieve documents for all of them, (3) Contextual Compression - use the LLM to extract only the relevant portions from each retrieved document. Files: backend/app/core/clara_quality_gate.py, backend/app/core/rag_retrieval.py.
[AI-14b] RAG Re-ranking with LLM (HIGH) - Implement LLM-based re-ranking: after initial retrieval, pass each document + query pair to the LLM and ask it to score relevance on a 1-10 scale. Sort by score and use top-K for context generation. This replaces the current simple scoring wrapper. File: backend/app/core/rag_reranking.py.
### Day 4.2: MAKER Framework Rebuild (4 hours)
[AI-15] MAKER Framework - Implement Real Multi-LLM Pipeline (CRITICAL) - Replace pass-through LangGraph nodes with actual multi-LLM processing. The MAKER Framework should make 6-24 LLM calls per query depending on complexity. Implement the full pipeline: Map the query to agent types, Analyze sentiment and urgency, Knowledge retrieval via CLARA RAG, Evaluate response quality, Refine and improve the response. Each of these steps must make real LLM calls. Files: backend/app/core/langgraph/nodes/11_maker_validator.py, backend/app/core/langgraph/graph.py.
[AI-15b] MAKER Quality Validation Node (HIGH) - The validator node (node 11 in the LangGraph graph) currently passes everything through. Implement real quality validation: (1) Check response factual consistency against knowledge base, (2) Verify response addresses all parts of the customer query, (3) Score response helpfulness using the LLM, (4) If score below threshold, route back for regeneration. File: backend/app/core/langgraph/nodes/11_maker_validator.py.
### Day 4.3: DSPy Integration Rebuild (2 hours)
[AI-12] DSPy Integration - Real Implementation (CRITICAL) - Replace the StubModule with actual DSPy integration. Implement: (1) A DSPy Signature for customer care responses (input: query + context -> output: response), (2) A DSPy Module that chains CoT + ReAct techniques, (3) DSPy Teleprompt optimization that fine-tunes the prompt based on example quality, (4) Remove the try/except import guard that silently falls back to the stub. File: backend/app/core/dspy_integration.py.
### Day 4.4: Agent Lightning Training Rebuild (2 hours)
[AI-13] Agent Lightning - Real Training Pipeline (CRITICAL) - Replace the stub training system with actual functionality. Implement: (1) prepare_dataset must load real conversation logs from the database and format them as training examples, (2) schedule_training must submit actual fine-tuning jobs to the configured LLM provider (OpenAI, Cerebras, or Groq), (3) Monitor training job status via provider APIs, (4) On completion, update the model configuration to use the fine-tuned model. File: backend/app/tasks/training_tasks.py.
### Day 4.5: Remaining Techniques + 3-Tier Hybrid (2 hours)
[AI-07] GST - Grapheme State Tracking Rebuild (MEDIUM) - Replace regex with actual state tracking that maintains a graph of conversation states and uses the LLM to predict the next state transition. Track customer intent progression across the conversation.
[AI-09] CRP - Cognitive Refinement Process Rebuild (MEDIUM) - Implement a real iterative refinement loop: generate initial response, ask LLM to identify weaknesses, refine specific weaknesses, and repeat until the response meets quality criteria.
[AI-16] 3-Tier Hybrid Optimization - Real Implementation (HIGH) - Now that individual techniques are real, implement the 3-tier optimization engine: Tier 1 (Mini) uses the fastest single technique, Tier 2 (Pro) uses the best single technique based on intent classification, Tier 3 (High) uses MAKER multi-technique composition. The optimization must actually route to different technique strategies based on tier. Files: backend/app/core/technique_router.py, backend/app/core/variant_tier_mapper.py.
### Day 4 Acceptance Criteria
CLARA RAG performs real HyDE generation, multi-query retrieval, and contextual compression. The MAKER Framework makes 6+ LLM calls per query through its pipeline. DSPy integration uses actual DSPy Signatures and Modules (no more StubModule). Agent Lightning can load real conversation data and submit training jobs. The 3-Tier Hybrid system routes to genuinely different AI strategies per tier. End-to-end test: a customer query goes through the full pipeline with real LLM calls at every step.
## 3.5 Day 5: Security HIGH - Middleware, Webhooks & CSRF
Theme: Address the 22 HIGH severity security findings, focusing on middleware inconsistencies, webhook replay protection, CSRF, rate limiting, and remaining access control issues.
Estimated Effort: 10-12 hours
Dependencies: Day 2 (infrastructure must be secured first)
### Day 5.1: Middleware & Access Control (3 hours)
[H-01] Open Redirect on Login Page (HIGH) - Validate the redirect query parameter against a whitelist of allowed paths. Reject any redirect URL that doesn't start with '/' or isn't in the allowed list. File: src/app/(auth)/login/page.tsx (line 28).
[H-04] Missing Content-Security-Policy Header (HIGH) - Add a comprehensive CSP header to the security headers middleware. Policy should include: default-src 'self', script-src 'self' 'nonce-{random}', style-src 'self' 'unsafe-inline' for Tailwind, img-src 'self' data: https:, connect-src 'self' https://api.cerebras.ai https://api.groq.com. File: backend/app/middleware/security_headers.py.
[H-06] IP Extraction Inconsistency Across Middleware (HIGH) - Standardize IP extraction across all middleware using TRUSTED_PROXY_COUNT. Create a shared get_client_ip() utility that respects the proxy chain depth setting. Apply to ip_allowlist.py, request_logger.py, and rate_limit.py. Files: backend/app/middleware/ip_allowlist.py, request_logger.py, rate_limit.py.
[H-13] No Role Restrictions on Billing Endpoints (HIGH) - Add role checks to all billing endpoints. Only users with 'owner' or 'admin' roles should be able to cancel subscriptions, process refunds, or modify billing details. File: backend/app/api/billing.py.
[H-21] No App-Level Rate Limiting on Auth Endpoints (HIGH) - Add application-level rate limiting on all /api/auth/* routes. Login: 5 attempts per minute per email, Register: 3 per minute per IP, OTP: 10 per minute per phone, Password Reset: 3 per hour per email. Implement using Redis sliding window. File: backend/app/middleware/rate_limit.py.
### Day 5.2: Webhook Security (3 hours)
[H-07] Webhook Signature Verification Disabled When Secret Unset (HIGH) - Change the logic from 'if webhook_secret and not verify' to 'if not webhook_secret: reject request'. Missing webhook secrets should block the request, not silently accept all payloads. File: backend/app/api/billing_webhooks.py (line 166).
[H-08] No Webhook Replay/Timestamp Protection (HIGH) - Add timestamp validation to all webhook handlers (Paddle, Twilio, Brevo, Shopify). Reject any webhook with a timestamp older than 5 minutes. Store processed webhook IDs in Redis with TTL to prevent replay. Files: backend/app/webhooks/paddle_handler.py, twilio_handler.py, brevo_handler.py, shopify_handler.py.
[H-15] Webhook Status/Retry Endpoints Have No Authentication (HIGH) - Add authentication to webhook management endpoints. Only authenticated admin users should be able to query webhook events or trigger retries. File: backend/app/api/webhooks.py (lines 438-519).
[H-20] Dashboard Mock Login Accepts ANY Credentials (HIGH) - Remove or disable the mock login endpoint in production. If needed for development, gate it behind ENVIRONMENT != 'production'. File: dashboard/src/app/api/auth/login/route.ts.
### Day 5.3: CSRF, XSS & Additional HIGH (3-4 hours)
[H-19] No CSRF Protection on State-Changing Endpoints (HIGH) - Implement CSRF token generation and validation for all POST/PUT/DELETE routes. Generate tokens server-side, store in httpOnly cookies, and validate on every state-changing request. For API routes using Bearer tokens, this is less critical but should still be enforced for cookie-based auth.
[H-12] Google OAuth ID Token in URL Query Parameter (HIGH) - Move Google OAuth token exchange to use POST body instead of URL query parameter. The token currently appears in server logs, proxy logs, and browser history. File: backend/app/services/auth_service.py (lines 712-714).
[H-16] HTML Injection in Email Notification Templates (HIGH) - Sanitize all customer names and AI responses before interpolating into HTML email templates. Use a proper HTML escaping library (bleach or markupsafe). File: dashboard/src/lib/notifications.ts (lines 109-114).
[H-17] Channel Status Leaks Partial API Keys (HIGH) - Remove the first 8 chars of Brevo API key and first 6 of Twilio SID from the channel status response. Return only masked indicators (e.g., 'configured' / 'not configured') without any key fragments. File: dashboard/src/app/api/channel-status/route.ts (line 14).
### Day 5 Acceptance Criteria
All 22 HIGH severity findings are resolved. CSP header is active and blocks inline script injection. IP extraction is consistent across all middleware. Webhook handlers reject replayed requests older than 5 minutes. Missing webhook secrets cause request rejection. Billing endpoints require owner/admin role. Auth endpoints have per-endpoint rate limiting. CSRF tokens are validated on all state-changing routes.
## 3.6 Day 6: Security MEDIUM + Incomplete Features
Theme: Fix MEDIUM severity security issues and complete partially-implemented features. This day bridges the gap between security hardening and feature completeness.
Estimated Effort: 10-12 hours
### Day 6.1: Security MEDIUM - Input Validation & Data Handling (5 hours)
[M-01] User Role Leaked in Error Details (MEDIUM) - Remove user_role from AuthorizationError details. Return only generic 'access denied' without revealing the user's actual role. File: backend/app/api/deps.py (line 130).
[M-02] Double Body Parsing (MEDIUM) - Remove the double parsing in identity.py where both a Pydantic model and raw JSON body are parsed from the same request. Use only the Pydantic model. File: backend/app/api/identity.py (line 43).
[M-04] Weak Email Validation (MEDIUM) - Replace simple '@' check with proper RFC 5322 email validation. Use email-validator Python package. File: backend/app/api/verification.py (line 40).
[M-05] Rate Limiter Fail-Open (MEDIUM) - Change rate limiter to fail-closed: when Redis is down, block requests rather than allowing all. Log the failure clearly. File: backend/app/middleware/rate_limit.py (line 87).
[M-08] Events API Missing Auth Dependency (MEDIUM) - Add explicit auth dependency to the events API endpoint instead of relying solely on middleware-set company_id. File: backend/app/main.py (line 426).
[M-11] Missing Cache-Control on Auth Responses (MEDIUM) - Add Cache-Control: no-store, no-cache, must-revalidate to all authentication response headers. Prevents proxy caching of tokens. File: backend/app/middleware/security_headers.py.
[M-13] Mass Assignment via setattr in Admin (MEDIUM) - Replace the setattr-based user update in admin.py with explicit field assignment from a whitelist of allowed fields. File: backend/app/api/admin.py (line 198).
[M-14] ai_engine Endpoints Use body: dict Without Validation (MEDIUM) - Add Pydantic models for all ai_engine endpoints that currently accept raw dict bodies. This prevents mass assignment and ensures type safety. File: backend/app/api/ai_engine.py.
[M-16] SMS Webhook No Signature Verification (MEDIUM) - Add Twilio request signature verification to the SMS status callback endpoint. Currently unprotected. File: backend/app/api/sms_channel.py (line 741).
[M-33] SQL Injection via ILIKE Wildcards (MEDIUM) - Escape % and _ characters in search queries before passing to ILIKE operations. Files: backend/app/api/admin.py (line 117), tickets.py (line 150).
[M-35] No Role Restriction on Notifications Send (MEDIUM) - Add role check to the notification send endpoint. Any user should not be able to send notifications to arbitrary recipients. File: backend/app/api/notifications.py (line 180).
### Day 6.2: Complete Incomplete Features (5 hours)
[IC-01] Voice Server - Replace Keyword Matching with LLM (HIGH) - Replace the keyword-based intent detection in parwa_voice_server.py (line 444) with real LLM-based intent classification. Use the Smart Router to send transcribed speech to an LLM that classifies intent and generates responses. Maintain the existing Twilio call handling infrastructure. File: backend/app/core/parwa_voice_server.py.
[IC-02] Sentiment Analysis - Replace Keywords with NLP (MEDIUM) - Replace the likely keyword-based sentiment analysis with real NLP. Use the LLM to analyze customer message sentiment with structured output (sentiment_score, emotion_labels, urgency_level). File: backend/app/core/sentiment_engine.py.
[IC-03] Confidence Scoring - Connect Real Data Sources (MEDIUM) - Wire up the existing confidence scoring formula to real data sources: technique execution metrics, LLM response quality scores, knowledge base retrieval relevance, and conversation context completeness. The formula exists but input variables are never populated. File: backend/app/core/confidence_scoring_engine.py.
[IC-09] PII Redaction - Add NER-Based Detection (HIGH) - Extend PII redaction beyond regex patterns to include NER-based detection for person names, addresses, and custom entity types. Use the LLM for ambiguous cases where regex patterns may miss or over-match. File: backend/app/core/pii_redaction_engine.py.
[IC-11] Hallucination Detector - Implement Real Detection (HIGH) - Implement actual hallucination detection: (1) Cross-check AI responses against knowledge base facts, (2) Verify numerical claims and order details against real data, (3) Flag responses where the AI states something not in the knowledge base or conversation context. File: backend/app/core/hallucination_detector.py.
### Day 6 Acceptance Criteria
All targeted MEDIUM security issues are resolved. Input validation uses proper libraries (email-validator, bleach). Rate limiter fails closed on Redis failure. SQL wildcards are properly escaped. Voice server uses real LLM intent classification instead of keyword matching. Sentiment analysis produces structured NLP output. Confidence scoring receives real input data. PII redaction uses NER for entity detection. Hallucination detector cross-checks responses against facts.
## 3.7 Day 7: Frontend + Dashboard + MCP Security
Theme: Complete all remaining security issues across the Next.js frontend, Dashboard application, and MCP Server. This ensures that every external-facing component of the system is properly secured.
Estimated Effort: 10-12 hours
### Day 7.1: Dashboard Security Overhaul (4 hours)
[D-01] Dashboard Send-SMS Hardcoded Phone Number (HIGH) - Fix the notification service that sends SMS to +1234567890 instead of the actual customer phone number. The hardcoded number appears in dashboard/src/lib/notifications.ts (line 92). Route SMS through the backend API which has access to real customer data.
[D-02] Dashboard Analytics Returns Mock Data (MEDIUM) - Connect dashboard analytics to real backend APIs. The current analytics-api.ts (line 226) silently returns mock data, making the dashboard appear functional when it's showing fake numbers. Implement real API calls to the backend analytics endpoints.
[D-03] Dashboard Email Content Passed Directly to Brevo (MEDIUM) - Route email sending through the backend API instead of calling Brevo directly from the dashboard frontend. The current implementation in send-email/route.ts sends arbitrary HTML content with no sanitization. Backend already has Brevo integration with proper templating.
[M-29] Analytics Silently Returns Mock Data (MEDIUM) - The analytics API returns mock/fake data without any indication to the user. Either connect to real data sources or clearly label the data as 'demo data' in the UI. File: dashboard/src/lib/analytics-api.ts (line 226).
### Day 7.2: MCP Server Security (3 hours)
[M-23] MCP CORS Wildcard Fallback (MEDIUM) - Fix the MCP server CORS configuration that falls back to ['*'] on exception. This must never happen in production. File: mcp_server/main.py (line 202).
[M-24] Dev Docker Exposes All Ports to 0.0.0.0 (MEDIUM) - Restrict Docker port bindings in development to localhost only (127.0.0.1) for database (5432), Redis (6379), and internal services. Only the backend API (8000) and frontend (3000) should be externally accessible. File: docker-compose.yml.
[M-25] Redis No Password in Dev Mode (MEDIUM) - Add a default Redis password even in development mode. Update docker-compose.yml to set REDIS_PASSWORD and pass it to both the Redis service and the backend configuration. File: docker-compose.yml (line 29).
[M-38] Google AI Key Passed in URL (MEDIUM) - Move the Google AI API key from the URL query parameter to a request header in the chat API route. The key currently appears in browser history, server logs, and proxy logs. File: src/app/api/chat/route.ts (line 66).
### Day 7.3: Remaining MEDIUM Security (3 hours)
[M-03] Batch Endpoint No Auth-Based Rate Limit (MEDIUM) - Add per-user rate limiting for the batch identity endpoint that currently allows 100 identities per request with only a global rate limit. File: backend/app/api/identity.py (line 161).
[M-06] API Key Auth Pass-Through When No Header (MEDIUM) - When no API key header is present, the auth middleware should return 401 instead of passing through. Add explicit rejection. File: backend/app/middleware/api_key_auth.py (line 46).
[M-07] DB Session Per Request in Middleware (MEDIUM) - Move database session creation from middleware to the FastAPI dependency injection system to prevent connection pool exhaustion. Files: backend/app/middleware/api_key_auth.py (line 154), ai_entitlement.py (line 212).
[M-15] Chat Widget Manual Body Parsing (MEDIUM) - Add Pydantic models to all chat widget endpoints that currently parse request bodies manually. Prevents type confusion and mass assignment. File: backend/app/api/chat_widget.py.
[M-17] Exception Leaks Internal Details (MEDIUM) - Replace str(e) exception messages with generic error messages in the knowledge base API. Internal exception details should only be logged, never returned to clients. File: backend/app/api/knowledge_base.py (line 370).
[M-19] Visitor Token Verification Silently Passes (MEDIUM) - Fix the chat widget visitor token verification that passes on exception instead of rejecting. If verification fails, the request should be rejected with 401. File: backend/app/api/chat_widget.py (line 402).
[M-21] CSP Allows unsafe-inline/unsafe-eval (MEDIUM) - Remove unsafe-inline and unsafe-eval from the nginx CSP configuration. Use nonce-based script loading instead. File: infra/docker/nginx.conf (line 112).
[M-26] No Security Headers on Next.js API Routes (MEDIUM) - Add security headers (X-Content-Type-Options, X-Frame-Options, HSTS, CSP) directly to Next.js API routes. Currently these headers are only set by nginx in production, leaving development and direct API access unprotected. Files: src/app/api/**.
[M-27] User Enumeration via check-email (MEDIUM) - Remove the distinct response for existing vs non-existing emails in the check-email endpoint. Return the same generic response regardless. Add rate limiting. File: src/app/api/auth/check-email/route.ts.
[M-28] Email Content Passed Directly to Brevo (MEDIUM) - Sanitize email content before passing to Brevo API. The current implementation in send-email/route.ts allows arbitrary HTML, creating a phishing vector. File: dashboard/src/app/api/send-email/route.ts (line 16).
[M-32] Celery No Task Payload Size Limits (MEDIUM) - Add max payload size validation to Celery task definitions. Reject tasks with payloads larger than 1MB to prevent memory exhaustion. File: backend/app/tasks/celery_app.py (line 62).
[M-37] send-sms Hardcoded Phone Number (MEDIUM) - Fix SMS notifications to use the actual customer phone number instead of the hardcoded +1234567890. File: dashboard/src/lib/notifications.ts (line 92).
### Day 7 Acceptance Criteria
Dashboard uses backend APIs for all operations instead of direct provider calls. Analytics display real data from the backend. MCP server has proper CORS configuration. Dev Docker bindings restricted to localhost. All remaining MEDIUM security findings are resolved. Next.js API routes have security headers. No user enumeration vectors remain.
## 3.8 Day 8: AI Pipeline + LangGraph Completion
Theme: Complete the LangGraph workflow by making all stub nodes functional, connecting the real AI techniques into the pipeline, and validating end-to-end AI processing quality.
Estimated Effort: 10-12 hours
Dependencies: Day 4 (AI techniques and frameworks must be working)
### Day 8.1: LangGraph Node Completion (6 hours)
The LangGraph workflow has 19 nodes, but many are stubs or thin wrappers that don't perform meaningful processing. Each node needs to be evaluated and either connected to a real implementation or replaced with proper logic.
[LG-01] Node 02 - Empathy Engine (HIGH) - Implement real empathy detection and response modulation. Use the LLM to analyze customer emotional state and adjust response tone accordingly. Currently a pass-through wrapper. File: backend/app/core/langgraph/nodes/02_empathy_engine.py.
[LG-02] Node 04 - Base Domain Agent (HIGH) - Connect to the real knowledge base and LLM for domain-specific responses. The base agent should use CLARA RAG for retrieval and the appropriate AI technique for response generation. File: backend/app/core/langgraph/nodes/04_base_domain_agent.py.
[LG-03] Node 05 - FAQ Agent (MEDIUM) - Implement FAQ matching that uses embedding similarity (not just keyword matching) against the FAQ knowledge base. Fall back to LLM-generated responses when no FAQ match is found. File: backend/app/core/langgraph/nodes/05_faq_agent.py.
[LG-04] Node 12 - Control System (HIGH) - Implement the Jarvis Control System node that monitors AI response quality and can override or escalate. This is the guardrail node that should check: response accuracy, policy compliance, tone appropriateness, and PII leakage. File: backend/app/core/langgraph/nodes/12_control_system.py.
[LG-05] Node 13 - DSPy Optimizer (MEDIUM) - Connect to the rebuilt DSPy integration from Day 4. This node should run DSPy optimization on the current query type and update technique selection based on historical performance. File: backend/app/core/langgraph/nodes/13_dspy_optimizer.py.
[LG-06] Node 14 - Guardrails (HIGH) - Implement real output guardrails: block harmful content, enforce brand voice guidelines, check for off-topic responses, verify response length constraints. File: backend/app/core/langgraph/nodes/14_guardrails.py.
[LG-07] Node 15 - Channel Delivery (MEDIUM) - Implement channel-specific response formatting: truncate for SMS (160 chars), format HTML for email, add TTS markup for voice, include quick-reply buttons for chat. File: backend/app/core/langgraph/nodes/15_channel_delivery.py.
### Day 8.2: Specialized Agent Nodes (4 hours)
[LG-08] Node 06 - Refund Agent (MEDIUM) - Connect to real payment provider (Paddle) API for refund processing. Agent should verify refund eligibility, calculate amounts, and initiate refunds through the billing system. File: backend/app/core/langgraph/nodes/06_refund_agent.py.
[LG-09] Node 07 - Technical Agent (MEDIUM) - Implement technical support with real diagnostic capabilities: check service health, search knowledge base for known issues, guide through troubleshooting steps. Use ReAct technique with diagnostic tools. File: backend/app/core/langgraph/nodes/07_technical_agent.py.
[LG-10] Node 08 - Billing Agent (MEDIUM) - Connect to real billing system. Agent should handle: subscription queries, invoice lookups, payment troubleshooting, plan changes, and credit applications through the Paddle integration. File: backend/app/core/langgraph/nodes/08_billing_agent.py.
[LG-11] Node 09 - Complaint Agent (HIGH) - Implement complaint handling with emotional intelligence. Use sentiment analysis to detect frustration levels, apply service recovery playbooks, and escalate to human agents when the complaint severity exceeds the AI confidence threshold. File: backend/app/core/langgraph/nodes/09_complaint_agent.py.
[LG-12] Node 10 - Escalation Agent (MEDIUM) - Implement proper escalation logic: determine when to escalate based on topic, sentiment, and confidence. Route to the correct human agent queue with full context transfer. File: backend/app/core/langgraph/nodes/10_escalation_agent.py.
### Day 8 Acceptance Criteria
All 19 LangGraph nodes perform real processing (no pass-through stubs). The empathy engine adjusts response tone based on detected emotion. Domain agents use CLARA RAG for knowledge retrieval. Guardrails block harmful and off-topic responses. Channel delivery formats responses correctly for each channel. Specialized agents (refund, billing, technical, complaint) connect to real backend services. End-to-end test: a customer complaint flows through the full 19-node pipeline with real LLM calls at each relevant node.
## 3.9 Day 9: Infrastructure + Production Hardening
Theme: Harden the infrastructure for production deployment, including remaining LOW severity findings, production configuration, monitoring, and performance optimization.
Estimated Effort: 8-10 hours
### Day 9.1: Remaining LOW Severity Findings (3 hours)
[L-01] HS256 Instead of RS256 for JWTs (LOW) - Migrate JWT signing from HS256 (symmetric) to RS256 (asymmetric). This allows the frontend to verify tokens without sharing the signing key. Generate RSA key pair and configure both backend signing and frontend verification. File: backend/app/core/auth.py (line 24).
[L-02] No jti for Token Blacklist (LOW) - Already partially addressed in Day 2 (M-10). Complete the implementation by adding a Redis-backed token blacklist that checks jti claims on every authenticated request. Implement cleanup of expired blacklist entries.
[L-04] Stale Rate Limit Entries Not Cleaned (LOW) - Add a periodic cleanup task that removes expired rate limit entries from Redis. Use a Celery beat task running every 6 hours. File: security/rate_limiter.py (line 131).
[L-05] Circuit Breaker Not Thread-Safe (LOW) - Add threading.Lock to the circuit breaker state machine to prevent race conditions in concurrent environments. File: security/circuit_breaker.py.
[L-09] Login Endpoint Is Synchronous (LOW) - Convert the login endpoint from synchronous to async. Database lookups during authentication should use async session to prevent blocking the event loop. File: backend/app/api/auth.py (line 134).
[L-11] No File Magic-Byte Validation (LOW) - Add magic-byte (file signature) validation for uploaded files. Don't trust the Content-Type header alone. Validate that PNG files start with 0x89504E47, PDF with 0x25504446, etc. File: backend/app/core/storage.py (line 1111).
[L-12] No JWT Key Rotation Mechanism (LOW) - Implement a JWT key rotation mechanism that supports multiple active signing keys and graceful key rotation without invalidating existing sessions. Store key metadata in Redis with version numbers.
### Day 9.2: Production Configuration (3 hours)
[INF-01] Production Docker Security Review (HIGH) - Review and fix all Docker configurations: (1) Ensure all production containers run as non-root users, (2) Remove unnecessary system packages, (3) Set resource limits (CPU, memory) on all containers, (4) Enable read-only root filesystem where possible, (5) Configure health checks for all services. Files: infra/docker/*.Dockerfile, docker-compose.yml.
[INF-02] Environment Variable Audit (HIGH) - Create a comprehensive .env.production.template with all required variables, descriptions, and examples. Ensure no hardcoded values in any source file. Add startup validation that checks all required env vars are set. File: backend/app/config.py.
[INF-03] Database Migration Verification (MEDIUM) - Verify all Alembic migrations run cleanly on a fresh database. Ensure no data loss during forward migrations. Test rollback procedures for each migration. File: database/alembic/versions/.
[INF-04] SSL/TLS Certificate Configuration (MEDIUM) - Verify TLS configuration: TLSv1.2+ only, strong cipher suites, OCSP stapling enabled, HSTS headers with preload. Test certificate chain completeness. Files: infra/docker/nginx.conf.
[INF-05] Backup and Recovery Procedures (MEDIUM) - Document and implement automated PostgreSQL backup: daily full backups, hourly WAL archiving, point-in-time recovery capability. Test backup restoration procedure. Create runbook for disaster recovery.
### Day 9.3: Monitoring and Performance (2-3 hours)
[MON-01] AI Pipeline Performance Monitoring (HIGH) - Implement metrics tracking for the AI pipeline: per-technique latency, token usage per request, LLM error rates, Smart Router fallback frequency. Export metrics to Prometheus or a time-series database. File: backend/app/core/ai_monitoring_service.py.
[MON-02] Application Performance Monitoring (MEDIUM) - Add APM instrumentation: request latency tracking, slow query detection (queries >500ms), memory usage monitoring, connection pool utilization. Set up alerts for degraded performance. Files: backend/app/core/health.py, backend/app/core/metrics.py.
[MON-03] Error Tracking and Alerting (MEDIUM) - Implement structured error logging with Sentry or equivalent. Configure alerts for: unhandled exceptions, authentication failures, payment processing errors, LLM API failures, webhook processing failures. Files: backend/app/logger.py.
[IC-12] Self-Healing Engine - Real Implementation (MEDIUM) - Implement actual self-healing capabilities: (1) Detect LLM API failures and automatically retry with fallback model, (2) Detect database connection issues and trigger reconnection, (3) Monitor queue depths and scale worker processes. File: backend/app/core/self_healing_engine.py.
### Day 9 Acceptance Criteria
All 17 LOW severity findings are resolved. Production Docker containers run as non-root with resource limits. Environment variables are validated on startup. Database migrations are verified. TLS configuration passes SSL Labs test. Automated backups run hourly/daily. AI pipeline metrics are tracked and visible in a monitoring dashboard. Error tracking captures all unhandled exceptions. Self-healing engine automatically recovers from common failure modes.
## 3.10 Day 10: Full Regression Testing + Documentation
Theme: Run comprehensive testing across the entire codebase, fix any regressions introduced during the 10-day fix, and update all documentation to reflect the real (non-fake) capabilities of the system.
Estimated Effort: 8-10 hours
Dependencies: All prior days (Days 1-9)
### Day 10.1: Security Regression Testing (3 hours)
Run the complete security test suite against the updated codebase to verify all 93 security fixes are effective and no regressions were introduced. This includes running the existing test files (test_production_readiness.py, test_day7_gaps.py, test_all_gaps_d6_d7.py, etc.) and creating new targeted tests for each CRITICAL and HIGH fix.
[TEST-01] Run All Existing Security Tests (HIGH) - Execute the full test suite: pytest backend/app/tests/ with coverage reporting. Fix any failing tests. Ensure test coverage is at least 80% for all modified files. Run both unit tests and integration tests.
[TEST-02] CRITICAL Finding Verification Tests (HIGH) - Write targeted tests that specifically verify each of the 15 CRITICAL findings is resolved. For example: test that dashboard endpoints return 401 without auth, test that RAG cannot access cross-tenant data, test that MFA flow completes end-to-end. Create new test file: backend/app/tests/test_10day_critical_verification.py.
[TEST-03] AI Technique Integration Tests (HIGH) - Write tests that verify each of the 12 AI techniques makes real LLM calls. Mock the LLM responses for deterministic testing but verify the call structure, prompt format, and response parsing. Test error handling (LLM timeout, rate limit, invalid response). Create: backend/app/tests/test_10day_ai_techniques.py.
[TEST-04] End-to-End Pipeline Test (HIGH) - Create a comprehensive end-to-end test that sends a customer query through the full pipeline: PII redaction, classification, technique selection, LLM processing, quality validation, guardrails, channel formatting, and delivery. Verify real LLM calls are made at each stage. Create: backend/app/tests/test_10day_e2e_pipeline.py.
### Day 10.2: Performance and Load Testing (2 hours)
[TEST-05] Load Testing Under Concurrent Requests (MEDIUM) - Run load tests simulating 100 concurrent customer conversations. Verify: no connection pool exhaustion, no memory leaks, consistent response times under load, proper rate limiting, graceful degradation when LLM APIs are slow. Document performance baselines.
[TEST-06] Failover and Recovery Testing (MEDIUM) - Test failure scenarios: (1) Kill Redis and verify fail-closed rate limiting, (2) Kill PostgreSQL and verify proper error handling, (3) Simulate LLM API failures and verify Smart Router fallback works, (4) Simulate webhook delivery failures and verify retry logic. Document recovery times.
### Day 10.3: Documentation Update (3 hours)
[DOC-01] Update Architecture Document (HIGH) - Update PARWA_Architecture_Design_Document.md to reflect the real AI architecture. Remove claims about techniques that were previously fake. Document the actual LLM integration architecture, the real CLARA RAG capabilities, and the MAKER Framework's actual pipeline stages.
[DOC-02] Remove Fake Feature Claims from Marketing Docs (CRITICAL) - Audit all documents in /documents/ and /docs/ directories. Remove or update any claims about AI capabilities that were not actually implemented. Specifically update: PARWA_AI_Technique_Framework.md, PARWA_Context_Bible.md, JARVIS_SPECIFICATION.md, and PARWA_SRS_Software_Requirements_Specification.md. The documentation must accurately describe what the system actually does, not what was aspirational.
[DOC-03] API Documentation Update (MEDIUM) - Regenerate OpenAPI/Swagger documentation to reflect all auth changes, new endpoints, and modified request/response schemas. Ensure all security-related headers and authentication methods are properly documented. Test that the generated docs match the actual API behavior.
[DOC-04] Deployment Runbook (MEDIUM) - Create a production deployment runbook that includes: environment setup, database migration procedure, Docker deployment steps, SSL certificate installation, monitoring configuration, and rollback procedures. Include troubleshooting guides for common issues.
### Day 10 Acceptance Criteria
All existing tests pass with no regressions. New security verification tests confirm all 93 findings are resolved. AI technique tests confirm real LLM integration for all 12 techniques. End-to-end pipeline test passes with real LLM calls. Load test shows stable performance under 100 concurrent conversations. All documentation accurately describes the system's real capabilities. No fake feature claims remain in any document.

# 4. Appendix: Gap-to-Day Mapping
The following table provides a complete mapping of every gap to its assigned day, enabling progress tracking and dependency verification during execution.

# 5. Risk Assessment and Mitigation
Executing a 10-day intensive fix-all roadmap carries several risks that must be actively managed. The primary risk is scope creep: each fix may reveal additional issues that weren't initially visible. To mitigate this, each day has clear acceptance criteria and a strict scope boundary. If a fix takes longer than estimated, the daily standup should decide whether to extend the day's work into the next day's buffer time or defer the item.
The second major risk is AI technique implementation quality. Rebuilding 12 AI techniques to use real LLM calls requires careful prompt engineering and testing. Poorly implemented techniques could produce worse results than the current template-based approach. To mitigate this, each technique implementation includes structured output parsing and quality validation. The Day 10 regression tests will catch any quality regressions.
The third risk is dependency chain failures. If Day 1 (auth) takes longer than expected, it delays Day 3 (AI rebuild) because real LLM calls need proper auth to be secure. The mitigation is to implement auth fixes in priority order: the most critical items (C-01 dashboard auth, C-02 JWT tokens) should be completed first, allowing AI rebuild to begin even if some lower-priority auth fixes are still in progress.
The fourth risk is the documentation update on Day 10. Currently, the marketing and technical documents describe features that don't actually exist (or are fake). Updating these documents to accurately describe the real system may require significant rewriting. The mitigation is to start documentation updates in parallel during Days 3-8, as each component is completed, rather than leaving it all for Day 10.

# 6. Success Metrics
The roadmap will be considered successful when the following metrics are achieved at the end of Day 10: Zero CRITICAL vulnerabilities remain in the codebase. Zero HIGH vulnerabilities remain unaddressed. At minimum 80% of MEDIUM findings are resolved. All 12 AI techniques make real LLM API calls with measurable quality metrics. The CLARA RAG system performs HyDE, multi-query retrieval, and contextual compression. The MAKER Framework executes a genuine multi-LLM pipeline. All LangGraph nodes perform real processing. The system can handle 100 concurrent conversations without degradation. All documentation accurately describes real system capabilities. The full test suite passes with no regressions and minimum 80% code coverage on modified files.
| PARWA Comprehensive 10-Day Fix-All Roadmap
Security, AI Integrity, and Feature Completion

Project: Parwa AI Customer Care SaaS
Total Gaps: 120+ | Scope: Full Codebase
Version: 2.0 | May 2026
Replaces: All Previous Roadmaps (8-Day, 3-Day, Week Plans) |
| --- |
| Severity | Count | Production Impact | Primary Areas |
| --- | --- | --- | --- |
| CRITICAL | 15 | BLOCKS deployment | Auth, Access Control, Data Protection, CORS, Secrets |
| HIGH | 22 | Blocks public launch | Middleware, Webhooks, CSRF, Rate Limiting, IDOR |
| MEDIUM | 39 | Should fix pre-launch | Input Validation, Logging, Encryption, Docker |
| LOW | 17 | Best practices | Algorithm choices, Deprecation, Headers |
| TOTAL | 93 | - | All layers |
| ID | Component | Claimed | Reality | Impact |
| --- | --- | --- | --- | --- |
| AI-01 | Chain of Thought | LLM step-by-step reasoning | Regex: /step\s*\d|first.*then.*finally/i | Core feature fake |
| AI-02 | Tree of Thought | Multi-branch LLM exploration | Template: 'Considering multiple approaches...' | Core feature fake |
| AI-03 | ReAct | LLM reasoning + action loop | Template: 'Thought: ... Action: ...' with no LLM | Core feature fake |
| AI-04 | Reflexion | Self-evaluation + retry | Template: 'Reflection: ... Improved answer...' | Core feature fake |
| AI-05 | Self-Consistency | Multiple LLM samplings + vote | Returns first template match, no sampling | Core feature fake |
| AI-06 | Universe of Thought | Multi-perspective analysis | Template: 'From multiple perspectives...' | Core feature fake |
| AI-07 | GST | Grapheme state tracking | Regex pattern matcher only | Core feature fake |
| AI-08 | Least-to-Most | Decomposition + sequential solve | Template: 'Breaking down...' | Core feature fake |
| AI-09 | CRP | Cognitive refinement process | Template with no refinement loop | Core feature fake |
| AI-10 | Step-Back | Abstract reasoning then detail | Template: 'Looking at the bigger picture...' | Core feature fake |
| AI-11 | Reverse Thinking | Work backwards from answer | Template: 'Working backwards...' | Core feature fake |
| AI-12 | DSPy Integration | DSPy optimization pipeline | StubModule returns [Fallback], try/except import | Integration fake |
| AI-13 | Agent Lightning | AI model training service | samples_count:0, training_job_id:None | Training fake |
| AI-14 | CLARA RAG | Advanced RAG with HyDE/Multi-Query | Simple scoring wrapper, no advanced retrieval | RAG exaggerated |
| AI-15 | MAKER Framework | 6-24 LLM calls per query | Pass-through LangGraph nodes | Framework fake |
| AI-16 | 3-Tier Hybrid | Technique optimization engine | Cannot optimize fake techniques | Architecture fake |
| ID | Component | What Works | What's Missing | Priority |
| --- | --- | --- | --- | --- |
| IC-01 | Voice Server | Twilio call handling works | AI is keyword matching (line 444), not LLM | HIGH |
| IC-02 | Sentiment Analysis | Basic sentiment detection | Likely keyword-based, no NLP model | MEDIUM |
| IC-03 | Confidence Scoring | Formula/math exists | Input data never populated from real signals | MEDIUM |
| IC-04 | Semantic Clustering | Algorithm implemented | Embedding source unclear, may not work end-to-end | MEDIUM |
| IC-05 | GSD State Engine | State machine compiles | Missing critical transition handlers | HIGH |
| IC-06 | Smart Router | 11 models configured | Missing fallback validation and monitoring | MEDIUM |
| IC-07 | LangGraph Workflow | 19 nodes compile | Many nodes are stubs or thin wrappers | HIGH |
| IC-08 | AI Pipeline | 13 stages connected | Intermediate outputs unvalidated | MEDIUM |
| IC-09 | PII Redaction | Partial working | Missing NER-based detection for names/addresses | HIGH |
| IC-10 | Conversation Summary | Template exists | No real LLM summarization | MEDIUM |
| IC-11 | Hallucination Detector | Framework present | No actual detection logic | HIGH |
| IC-12 | Self-Healing Engine | Basic retry loop | No real self-diagnosis or auto-repair | MEDIUM |
| Day | Theme | Gap Count | Est. Hours | Dependencies |
| --- | --- | --- | --- | --- |
| Day 1 | Critical Security: Auth & Access Control | 18 | 10-12 | None |
| Day 2 | Critical Security: Data Protection & Infra | 16 | 10-12 | Day 1 |
| Day 3 | AI Rebuild: Core LLM Integration | 14 | 12-14 | Day 1-2 |
| Day 4 | AI Rebuild: Frameworks & RAG | 14 | 12-14 | Day 3 |
| Day 5 | Security HIGH: Middleware & Webhooks | 15 | 10-12 | Day 2 |
| Day 6 | Security MED + Incomplete Features | 18 | 10-12 | Day 5 |
| Day 7 | Frontend + Dashboard + MCP Security | 16 | 10-12 | Day 5 |
| Day 8 | AI Pipeline + LangGraph Completion | 12 | 10-12 | Day 4 |
| Day 9 | Infrastructure + Production Hardening | 14 | 8-10 | Day 7 |
| Day 10 | Full Regression Testing + Docs | 10 | 8-10 | All prior |
| TOTAL | - | 147 (with overlap) | 100-120 | - |
| Day | Gap IDs | Category | Total |
| --- | --- | --- | --- |
| Day 1 | C-01, C-02, C-03, C-04, C-09, C-10, C-11, C-12, H-02, H-03, H-14, H-18, M-20, D-01 | Auth & Access | 14 |
| Day 2 | C-05, C-06, C-07, C-08, C-13, C-14, C-15, H-05, H-09, H-10, H-11, H-22, M-10, M-12 | Data & Infra | 14 |
| Day 3 | AI-01 to AI-11, AI-F01, AI-F02 | AI Core Rebuild | 13 |
| Day 4 | AI-12, AI-13, AI-14, AI-15, AI-16, AI-07, AI-09 | AI Frameworks | 7 |
| Day 5 | H-01, H-04, H-06, H-07, H-08, H-12, H-13, H-15, H-16, H-17, H-19, H-20, H-21 | Security HIGH | 13 |
| Day 6 | M-01 to M-05, M-08, M-11, M-13, M-14, M-16, M-33, M-35, IC-01, IC-02, IC-03, IC-09, IC-11 | Sec MED + Features | 16 |
| Day 7 | D-01 to D-03, M-03, M-06, M-07, M-15, M-17, M-19, M-21, M-23 to M-29, M-32, M-37, M-38 | Frontend + MCP | 18 |
| Day 8 | LG-01 to LG-12, IC-04, IC-05, IC-06, IC-08, IC-10 | AI Pipeline | 18 |
| Day 9 | L-01 to L-05, L-09, L-11, L-12, INF-01 to INF-05, MON-01 to MON-03, IC-07, IC-12 | Infra + Prod | 20 |
| Day 10 | TEST-01 to TEST-06, DOC-01 to DOC-04 | Testing + Docs | 10 |