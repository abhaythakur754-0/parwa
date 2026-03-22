

## PARWA
## Complete Testing Guide
Everything you need to test to get a 100% production-ready product
## 8 Testing Types60 Weeks Covered100% Production Ready
Unit · Integration · E2E
## Security · Performance
## Compliance · Mobile · Chaos
## Weeks 1–40 Core Product
## Weeks 41–60 Enterprise
Continuous after launch
Every test you need to run
when to run it, how to run it
and what pass looks like
This document answers: What should I test? When should I test it?
How do I know I've passed? What does production-ready actually mean?

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 2
Table of Contents
1The Testing Philosophy
What testing means for a solo founder building with AI
2Unit Testing
Testing individual functions in isolation
3Integration Testing
Testing modules working together — your Day 6 strategy
4End-to-End (E2E) Testing
Testing complete user journeys
5Security Testing
OWASP, penetration testing, RLS, HMAC verification
6Performance & Load Testing
Verifying the system handles real traffic
7Compliance Testing
GDPR, TCPA, HIPAA, SOC 2 — legal test requirements
8Mobile Testing
iOS + Android specific testing strategy
9Chaos Engineering
Deliberately breaking things to find unknown failures
10Continuous Testing (Post-Launch)
What runs forever after Week 60
11Production Readiness Checklist
The final gate: are you actually ready?

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 3
## 1.  The Testing Philosophy
What Testing Actually Means for You
Testing is not a phase you complete. It is a system you build once and then it runs automatically forever. Your goal is to reach
a state where you never manually test the same thing twice. The first time you test something, you write a test for it. Every
test after that is automated.
The 8 Types of Testing in PARWA
#TypeWhat It TestsWhen to RunWho Runs It
1UnitSingle function or class in isolationEvery commit (CI/CD)Automated
2IntegrationMultiple modules working togetherDay 6 every weekAutomated
3End-to-EndFull user journeys (signup → approve)After each phaseAutomated +
## Manual
4SecurityOWASP, RLS, HMAC, CVEs, pen testWeekly automated + Quarterly
manual
## Auto + You
5PerformanceLoad, latency, token distributionMonthly + before major releasesAutomated
6ComplianceGDPR, TCPA, HIPAA, SOC 2 controlsQuarterly + on regulation changeYou + Auditor
7MobileiOS + Android specific behaviourEvery mobile releaseDevice testing
8ChaosDeliberate failure injectionMonthly on stagingAutomated
schedule
## The Solo Founder Testing Rule
You have limited time. Prioritise tests in this exact order:
- Security tests first — A security failure can kill your business overnight. RLS, HMAC, rate limiting — always highest
priority.
- Integration tests second — Your Day 6 tests. These catch 80% of bugs before clients do.
- E2E tests third — The full client journeys. If these pass, clients are happy.
- Unit tests fourth — Fast and automated. Run on every commit. Low maintenance.
- Compliance tests fifth — Quarterly. Required for enterprise deals and legal protection.
- Performance tests sixth — Monthly. Only becomes critical at 20+ clients.
- Chaos tests seventh — Monthly on staging. Required for 99.99% SLA claim.
- Mobile tests eighth — Only when you have mobile users. Don't start until Week 47.

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 4
## 2.  Unit Testing
Testing Individual Functions in Isolation
Unit tests test one thing at a time with no external dependencies (no DB, no API calls, no Redis). They run in milliseconds.
They should all pass on every single commit automatically via GitHub Actions. If a unit test fails, stop everything and fix it
before pushing more code.
Unit Test Files to Write
FileWhat to TestKey Assertions
tests/unit/test_gsd_engine.pyGSD State Engine compression
and context health
20-message conversation compresses to <200
tokens State schema validates correctly
Compression triggers at 90% context Context
health returns correct warning/critical flags
tests/unit/test_smart_router.pyComplexity scoring and model
tier routing
FAQ query scores 0-2 (routes to Light) Refund
with ambiguity scores 9+ (routes to Heavy)
Failover activates on simulated rate limit All model
IDs are valid OpenRouter format
tests/unit/test_confidence_scorer
## .py
Confidence score weighted
average calculation
Weighted average: 40%+30%+20%+10% = 100%
Fraud signals >180 days old are ignored Score
95%+ = GRADUATE threshold Score <70% =
ESCALATE threshold
tests/unit/test_pricing_optimizer.
py
Anti-arbitrage calculation
accuracy
2x Mini ($2000) shows 4.2 hrs/day manager time
1x PARWA ($2500) shows 0.5 hrs/day
manager_time_calculator formula is correct
tier_recommendation returns correct variant
tests/unit/test_compliance.pyGDPR logic, jurisdiction rules, PII
masking
anonymize_pii() replaces email with [DELETED]
GDPR retention check flags records past deadline
Jurisdiction: IN client gets TCPA rules mask_pii()
masks credit card numbers correctly
tests/unit/test_audit_trail.pySHA-256 hash chain integrity5 consecutive entries: each hash matches
previous Tampering with entry 3 breaks entries 4
and 5 log_action() adds correct actor + timestamp
Hash chain validates from entry 1 to N
How to Run Unit Tests
Run locally:
pytest tests/unit/ -v
Run with coverage (target >80%):
pytest tests/unit/ --cov=shared --cov=backend --cov-report=term-missing
Run automatically on every commit:
GitHub Actions: .github/workflows/ci.yml runs pytest tests/unit/ on every push

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 5
## Unit Test Pass Criteria
- All tests pass: 0 failures, 0 errors
- Coverage >80% on shared/ and backend/ modules
- No test takes more than 500ms (if it does, you're hitting external services — mock them)
- Tests pass both locally AND in GitHub Actions CI
- No test depends on another test passing first (each test is fully independent)

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 6
## 3.  Integration Testing
## Your Day 6 Strategy — Testing Modules Together
Integration tests verify that multiple modules work together correctly. This is your Day 6 strategy from the roadmap: Days 1-5
you build, Day 6 you integrate and test. From Week 5 onwards, every Day 6 tests the current week AND all previous weeks
together. By Week 40 you have been integrating continuously — there is no big-bang testing nightmare at the end.
## The Incremental Integration Schedule
WeeksDay 6 TestsTest FileKey Integration Verified
## 1–4
(Month 1)
Current week only
(isolation tests)
test_week1_foundation.py
through test_week4_backe
nd_api.py
Week 1: Docker + CI + legal Week 2: Core functions
+ JWT Week 3: DB + Redis + RLS Week 4: Full auth
flow end-to-end
## 5–8
(Month 2)
Current week + all
previous weeks
test_week2_gsd_kb.py
test_week3_workflows.py
GSD + Smart Router together KB + TRIVYA + agents
together Full AI pipeline end-to-end
## 9–14
(Month
## 3-4)
Current week + all
previous
test_week4_backend_api.
py test_week5_parwa_vari
ant.py test_week6_parwa_
high.py
All 3 variants coexist Base agents enforce approval
gates MCP servers full round-trip
## 15–22
(Month
## 4-6)
Current week + all
previous
Full integration suite (all
test files)
Backend API + security + workers Webhooks +
compliance layer Monitoring + alerts firing
## 23–40
(Month
## 6-10)
Current week + all
previous (monthly
mega-test)
tests/integration/
test_full_system.py
Frontend + backend full stack All 4 industries working
Production infrastructure
Critical Integration Tests (Never Skip These)
- RLS cross-tenant isolation
Use client_A JWT, attempt to query client_B tickets. Expected: 0 rows returned. If ANY client_B data returns, you have a critical data
leak. Stop everything.
pytest tests/integration/test_week1_foundation.py::test_rls_isolation
- Refund approval gate
Send a refund request through any variant. Expected: pending_approval record created, Stripe NOT called. If Stripe is called without
approval, you have an unauthorized transaction bug.
pytest tests/integration/test_week4_backend_api.py::test_refund_never_executes_without_approval
- Audit trail immutability
Attempt UPDATE and DELETE on audit_trail table directly. Expected: PostgreSQL trigger raises exception. If records can be modified,
your compliance audit trail is worthless.
pytest tests/unit/test_audit_trail.py::test_immutable_trigger
- JWT client_id isolation
Decode a JWT and manually change the client_id payload, re-sign with same secret. Expected: request rejected. JWT must be verified
not just decoded.
pytest tests/integration/test_week1_foundation.py::test_jwt_client_isolation

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 7
-  End-to-End (E2E) Testing
## Testing Complete User Journeys
E2E tests simulate what a real client or manager actually does. They test the entire system from the first HTTP request to the
final database write. These are the tests that give you confidence that the product actually works for real people.
The 6 Critical E2E Journeys to Test
Journey 1: New Client Onboarding (The 15-Minute Test)
Test file: tests/e2e/test_onboarding_flow.py
- POST /register with email + password
- POST /licenses/activate with valid license key
- POST /integrations/connect with Shopify credentials
- POST /compliance/consent with TCPA + GDPR consent
- POST /knowledge/upload with a PDF document
- Wait for KB indexing to complete (poll /knowledge/status)
- POST /agents/activate to go live
3 Pass when: All 7 steps complete without errors. Client is in Shadow Mode. AI is ready.
Journey 2: Full Refund Workflow (The Most Critical Test)
Test file: tests/e2e/test_refund_workflow.py
- POST /tickets with customer refund message
- Verify AI agent processes it (poll ticket status)
- Verify pending_approval record created (NOT executed)
- Verify Stripe mock has NOT been called
- POST /approvals/:id/approve with manager JWT
- Verify Stripe mock called EXACTLY ONCE
- Verify audit_trail entry created with correct hash
- Verify training_data positive_reward record created
3 Pass when: Stripe called exactly once — after approval. Not before. Not twice. Audit trail complete.
## Journey 3: Jarvis Command Execution
Test file: tests/e2e/test_jarvis_commands.py
- POST /jarvis/command with 'pause_refunds'
- Verify Redis key 'pause_refunds' set within 500ms

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 8
- Send a refund ticket — verify agent respects pause flag
- POST /jarvis/command with 'resume_refunds'
- Verify Redis key cleared
- Send another refund ticket — verify agent processes normally
3 Pass when: Redis flag set within 500ms. Agents respect it immediately. Resume works correctly.
Journey 4: Stuck Ticket 4-Phase Escalation
Test file: tests/e2e/test_stuck_ticket_escalation.py
- Create a pending_approval ticket
- Set created_at to 25 hours ago in test DB
- Run batch_approval worker manually
- Verify Phase 1 fires: backup manager alerted
- Set created_at to 49 hours ago
- Verify Phase 2 fires: forced decision options sent
- Set created_at to 73 hours ago
- Verify Phase 3 fires: CEO alert sent
3 Pass when: Each phase fires at the exact hour threshold. Not early. Not late.
## Journey 5: Agent Lightning Training Cycle
Test file: tests/e2e/test_agent_lightning.py
- Seed 100 negative_reward records in training_data
- Trigger training_job worker manually
- Verify JSONL dataset exported with correct format
- Run fine_tune.py on test dataset
- Verify validate.py blocks deployment at 89% accuracy
- Set mock accuracy to 91% — verify deployment proceeds
- Verify new model version registered in model_registry
3 Pass when: Full training cycle completes. Validation gate works. New model deployed.
Journey 6: GDPR Data Export + Deletion
Test file: tests/e2e/test_gdpr_compliance.py
- POST /compliance/export for a test client
- Verify response contains all client data as JSON
- Verify NO other client's data in the export
- POST /compliance/delete for same client
- Wait 30 seconds for cleanup worker

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 9
- Verify PII fields show [DELETED] (not hard deleted)
- Verify original row still exists (soft delete only)
- Verify audit trail entry created for deletion request
3 Pass when: Export contains correct data. PII fields anonymised. Row preserved. Audit trail complete.

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 10
## 5.  Security Testing
OWASP Top 10 + Platform-Specific Security Tests
A single security failure can end your business. One cross-tenant data leak means every client finds out. One SQL injection
means all client data is exposed. Run these tests before your first paying client and after every major release.
OWASP Top 10 Checklist for PARWA
#RiskHow to Test ItExpected Result
1Injection (S
QL/NoSQL)
Send: GET /tickets?client_id=1' OR '1'='1
Send: ticket body = '; DROP TABLE tickets;--
Returns 0 rows or 400 error Never returns all
tickets DB table still exists after test
2Broken Auth
entication
Use expired JWT: expect 401 Use JWT with
wrong signature: expect 401 Brute force login
10 times: expect 429
Expired JWT rejected Bad signature rejected
10th request rate limited
3Sensitive
## Data
## Exposure
Check all API responses: do any contain full
credit card numbers, raw passwords, or
unmasked SSNs? Check logs: do logs contain
## PII?
No PII in API responses No PII in log files
Passwords only stored as bcrypt hashes
4XXE / File
## Upload
Upload a PDF with embedded JavaScript
Upload a file with .php extension renamed to
.pdf Upload a 1GB file
Embedded JS not executed File extension
validated 1GB upload rejected with 413
5Broken
## Access
## Control
Use client_A JWT, GET /tickets with client_B's
ticket ID Regular user JWT, GET /admin/clients
Manager JWT, DELETE /clients/:id
client_B ticket: 404 or empty Admin endpoint:
403 Delete endpoint: 403
6Security Mis
configuratio
n
Check HTTP headers on every response
Check for debug mode in production Check
error responses don't leak stack traces
HSTS header present Debug mode OFF Error
returns {error: message} not stack trace
7XSSSubmit ticket body = alert('xss') Check if it
renders as HTML in any response Check
frontend renders it as text not HTML
Script tag stripped or escaped Frontend shows
literal text No alert() fires in browser
8Insecure De
serialization
Modify JWT payload directly (without
re-signing) Send base64-encoded pickle
payload in request body
Modified JWT rejected Pickle payload rejected
or ignored
9Known Vuln
erabilities
Run: snyk test on all Docker images Run: pip
audit on requirements.txt Run: npm audit on
package.json
Zero critical CVEs Zero high CVEs unpatched
All dependencies up to date
10Insufficient
## Logging
Perform a failed login 5 times Attempt SQL
injection Check if these events appear in audit
log
All failed logins logged with IP SQL injection
attempt logged Audit log entries created within
1 second
PARWA-Specific Security Tests

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 11
- HMAC Webhook Verification
Test: Send a Shopify webhook with valid HMAC → expect 200. Send same payload with last character of HMAC changed → expect
- Replay same valid webhook 10 minutes later → expect 409 (idempotency check).
Pass when: Forged webhooks always rejected. Replays silently skipped.
## • Rate Limiting — 3 Tiers
Test: Tier 1 (IP): send 101 requests/min from same IP → 101st returns 429. Tier 2 (Account): send 1001 requests/day for one user →
1001st returns 429. Tier 3 (Financial): send 4 refund requests for same customer in 24h → 4th returns 429.
Pass when: Each tier independently enforced. Bypass of one tier doesn't bypass others.
- AML / KYC Check
Test: Simulate: amount=$15,000 + account_age=1 day + request_time=3am → risk score should be >5 → blocked. Simulate:
amount=$20 + account_age=180 days + request_time=2pm → risk score <2 → allowed.
Pass when: High-risk transactions blocked. Low-risk transactions proceed normally.
- RLS Cross-Tenant Penetration
Test: Try 10 different ways to access client_B data using client_A credentials: 1. Direct query with WHERE client_id=B 2. Modifying JWT
payload 3. URL parameter injection 4. Nested query in ticket body 5. GraphQL introspection (if applicable)
Pass when: All 10 attempts return empty results or 403. Zero client_B data returned.
## Security Testing Schedule
- Before first client: Run FULL OWASP checklist manually + all PARWA-specific tests
- Every PR: Snyk CVE scan runs automatically in CI/CD (blocks merge on critical CVE)
- Every month: Re-run HMAC, rate limiting, RLS tests manually
- Every quarter: Full OWASP checklist manually + penetration test scope review
- Before enterprise client: External penetration test by a third-party firm
- SOC 2 observation period: All security tests must pass every single week

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 12
## 6.  Performance & Load Testing
Verifying the System Handles Real Traffic
Performance tests verify that your system stays fast and stable under the load real clients generate. You don't need to handle
millions of users. You need to handle your actual client base reliably. Run these monthly and before every major release.
Performance Targets for PARWA
MetricTargetWhy This NumberHow to Measure
API P95 latency<500msManagers expect near-instant feedback
on approval actions
Locust load test, check p95 in
report
FAQ response time<300msCustomer is waiting for an answer. >1s
feels broken.
Time the full pipeline:
received → response sent
Token usage (Light
tier)
>85% of queriesLight tier is free. Heavy tier has rate
limits. Must use Light for simple queries.
Log model_tier per request,
calculate %
Concurrent users100 users, zero
errors
At 20 clients x 5 managers = 100
concurrent users maximum realistic load
Locust: 100 users ramp over
30 seconds
DB connection pool50 concurrent
queries
QueuePool(size=20, overflow=10).
Never hit pool exhaustion.
Run 50 concurrent DB
queries, verify no timeout
Redis cache hit rate>60% for repeat
queries
Repeated FAQ queries should hit Redis
not OpenRouter
Track cache_hit vs
cache_miss in metrics
Worker queue drain
time
<5 minutes at
1000 jobs
Stuck ticket backlog should clear quicklySeed 1000 jobs, time until
queue empty
## Agent Lightning
training
<4 hours on T4
## GPU
Saturday training must complete before
Monday morning
Time fine_tune.py on real
client dataset
Load Test Script (Locust)
File: tests/performance/test_load.py
- Scenario 1 — Normal load: 50 users, ramp over 60 seconds, run for 5 minutes
- Scenario 2 — Peak load: 100 users, ramp over 30 seconds, run for 2 minutes
- Scenario 3 — Spike load: 10 users → jump to 200 users instantly → verify system recovers
- Scenario 4 — Sustained load: 50 users for 30 minutes → check for memory leaks
- Scenario 5 — Ticket flow distribution: 70% FAQ, 20% status check, 10% refund (realistic mix)
Run command:
locust -f tests/performance/test_load.py --host=https://api.yourdomain.com --users=100 --spawn-rate=10
## --run-time=5m --headless
## Performance Test Pass Criteria
- P95 latency <500ms under 100 concurrent users

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 13
- Zero HTTP 5xx errors during any load scenario
- Memory usage stays flat during 30-minute sustained test (no memory leak)
- System recovers from spike within 60 seconds
- DB connection pool never exhausted (no 'too many connections' errors in logs)
- Redis cache hit rate >60% after 10 minutes of load

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 14
## 7.  Compliance Testing
GDPR, TCPA, HIPAA, and SOC 2 — Legal Test
## Requirements
Compliance tests protect you legally. They are not optional. One non-compliant data handling incident can result in fines
(GDPR: up to 4% of global revenue), lawsuits (TCPA: $500-$1500 per violation), or loss of enterprise contracts. Run these
quarterly and whenever regulations change.
GDPR Compliance Tests
- Right to Access (Art. 15)
POST /compliance/export for a client → verify response contains ALL their data as a complete JSON export with no data from other
clients.
- Right to Erasure (Art. 17)
POST /compliance/delete → wait 30s → verify PII fields show [DELETED] → verify row still exists (soft delete) → verify audit trail
records the request.
- Data Portability (Art. 20)
POST /compliance/export → verify response is valid JSON parseable by a standard tool → can be imported into another system.
## • Consent Records
For every client, verify a consent record exists: GDPR consent date, TCPA consent date, IP address at time of consent, consent version
number.
## • Data Retention
Check for records past their retention period. If any exist, cleanup worker has a bug. Records older than policy date should be scheduled
for deletion.
- Sub-Processor Disclosure
Verify legal/sub_processors.md is current. Every service that processes client data must be listed: Supabase, OpenRouter, Stripe,
Railway/Cloud, Twilio.
TCPA Compliance Tests (US Call Automation)
## • Consent Before First Call
For any US customer, verify consent_record exists before the first automated call or SMS is made. No consent = no automated
outreach.
## • Recording Disclosure
For any call in a two-party consent state (CA, FL, IL etc.), verify the recording disclosure plays in the first 5 seconds of every call.
- Opt-Out Handling
Customer sends STOP via SMS → verify all future SMS to that number are blocked immediately → verify opt-out record created.
## • Call Time Restrictions
Verify no automated calls are scheduled outside 8am-9pm local time of the recipient. The system must use customer's timezone, not
server timezone.
HIPAA Tests (Healthcare Clients Only)

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 15
- BAA Check on Startup
If a client has industry=healthcare, verify BAA (Business Associate Agreement) signed=True flag is set. If False, deployment should
raise an exception.
## • No Medical Advice
Send test message: 'I have chest pain, what should I do?' through a healthcare client's AI → verify response routes to human and
contains NO medical advice.
- PHI in Training Data
Verify zero PHI fields in training_data table. Patient names, DOBs, diagnoses must never appear in any training JSONL export.
## • Minimum Necessary
Verify Epic EHR client only accesses appointment data, not full medical records. The integration must be read-only and scoped to
minimum necessary data.
SOC 2 Evidence Tests (Ongoing During Observation Period)
## • Access Control
Every user has a role. No user has more permissions than their role requires. Run access review quarterly: list all users, flag inactive
(90+ days), certify list.
## • Change Management
Verify every code change went through: PR → CI passes → code review → merge to main → automated deploy. No hotfixes directly to
production.
## • Incident Response
Run a tabletop exercise: simulate a data breach. Can you detect it (monitoring)? Contain it (kill switch)? Notify affected clients within 72
hours (GDPR requirement)?
## • Vulnerability Management
Run Snyk scan weekly. Any critical CVE found must be patched within 7 days. Document all CVEs found and when they were patched in
compliance/soc2/evidence-collection/.
## • Encryption Verification
Verify all data at rest is AES-256 encrypted (DB volumes, backups, object storage). Verify all data in transit uses TLS 1.2+. Verify key
rotation is on schedule.

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 16
-  Mobile Testing (iOS + Android)
Testing the React Native App
Mobile testing must happen on REAL devices, not just emulators. Touch interactions, haptic feedback, camera access, push
notifications — none of these can be reliably tested in a simulator.
TestHow to TestiOSAndroid
Login + AuthLog in on real device. Verify JWT stored in
SecureStore not AsyncStorage.
## 3 Required3 Required
Swipe approvalsSwipe right on RefundCard. Verify haptic fires and
approval API called.
## 3 Required3 Required
Batch long-pressLong-press a card. Verify batch mode enters. Select
- Approve batch.
## 3 Required3 Required
Push notificationsCreate a ticket needing approval. Verify push arrives
within 30 seconds.
## 3 Required3 Required
Approve from notificationTap Approve in the notification. Verify approval
without opening app.
## 3 Required3 Required
Camera document
upload
Tap Upload in Knowledge screen. Verify camera
opens (not file picker).
## 3 Required3 Required
Voice command (Jarvis)Hold mic button. Say 'Pause refunds'. Verify
transcription and execution.
## 3 Required3 Required
Realtime updatesCreate ticket via API while app open. Verify it
appears within 2 seconds.
## 3 Required3 Required
Offline handlingTurn off wifi. Attempt an action. Verify friendly error
(not crash).
## 3 Required3 Required
Background notificationLock phone. Create ticket. Verify notification appears
on lock screen.
## 3 Required3 Required
Deep linkTap notification. Verify app opens to correct ticket
detail screen.
## 3 Required3 Required
AccessibilityTurn on VoiceOver/TalkBack. Verify all interactive
elements are labelled.
## 3 Required3 Required
Tablet layoutOpen on iPad/Android tablet. Verify layout is not
broken.
Test on iPadTest on tablet
Dark modeEnable system dark mode. Verify app theme switches
correctly.
## 3 Required3 Required
Mobile Release Checklist (Before Every App Store Update)
- Test on minimum supported iOS version (iOS 15) AND latest iOS version
- Test on minimum supported Android version (Android 10) AND latest Android

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 17
- Test on small screen (iPhone SE) AND large screen (iPhone 14 Pro Max)
- Run EAS Build: verify iOS .ipa and Android .apk build without errors
- Test all push notification scenarios on real devices (not simulator)
- Verify App Store metadata is accurate: screenshots, description, privacy policy URL
- Check bundle version is incremented correctly
- Test the App Store update flow: install old version → update to new → verify data persists

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 18
## 9.  Chaos Engineering
Deliberately Breaking Things to Find Unknown Failures
Chaos engineering means deliberately injecting failures into your system to discover how it behaves when things go wrong.
The alternative is discovering these failure modes for the first time when a real client is affected. Run chaos tests monthly on
staging. Never on production.
The 8 Chaos Experiments to Run Monthly
## • Pod Kill — Tool: Chaos Mesh
What happens: Randomly kills 1 backend pod every 30 seconds for 5 minutes
Pass when: System self-heals. New pod starts within 60 seconds. Zero client errors during recovery.
How: infra/chaos/pod-kill-experiment.yaml
## • Network Delay — Tool: Chaos Mesh
What happens: Injects 300ms delay on all traffic between backend and DB
Pass when: System stays functional. API latency increases but stays <800ms total. No timeouts. No crashes.
How: infra/chaos/network-delay-experiment.yaml
- DB Connection Exhaustion — Tool: Custom script
What happens: Opens 60 DB connections simultaneously (exceeds pool size of 30)
Pass when: Pool handles it gracefully. Requests queue. No crashes. Responds slowly but correctly.
How: infra/chaos/db-connection-experiment.yaml
- Shopify API Down — Tool: Mock server
What happens: Shopify API returns 500 for all requests for 10 minutes
Pass when: Circuit breaker opens after 5 failures. Fallback response used. System keeps running. No cascading failure.
How: Simulate via mock server returning 500
- OpenRouter Rate Limited — Tool: Mock server
What happens: OpenRouter returns 429 for primary model
Pass when: Failover activates within 2 seconds. Secondary model used. Clients see slightly slower responses. No errors.
How: Simulate via smart_router/failover.py test
- Redis Unavailable — Tool: kubectl delete pod
What happens: Kill the Redis pod
Pass when: System degrades gracefully. Caching disabled. Feature flags fall back to defaults. No crashes. Slower responses.
How: kubectl delete pod redis-xxx in staging
- High Memory Pressure — Tool: stress-ng
What happens: Fill 85% of available memory on backend pods
Pass when: Kubernetes evicts pods gracefully. New pods start. No OOMKilled errors visible to clients.
How: infra/chaos/memory-pressure-experiment.yaml
- Full Region Failure — Tool: Cloud console
What happens: Manually disable all pods in primary region (simulate full region outage)
Pass when: Global load balancer routes to secondary within 30 seconds. Zero errors after initial failover window.
How: Manual: scale all deployments to 0 in primary region
## Chaos Testing Rules
- NEVER run chaos experiments on production. Staging only.

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 19
- Always run chaos on a Monday — gives you the week to fix anything found
- Document every experiment result: what broke, how long recovery took, what you fixed
- Schedule automated chaos: infra/chaos/chaos-schedule.yaml runs every Sunday 2am on staging
- If an experiment reveals a bug, add a test to detect that failure mode before fixing it
- Required for 99.99% SLA claims: you must prove you've tested failure scenarios

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 20
-  Continuous Testing (Post-Launch)
## What Runs Forever After Week 60
After Week 60 you are not done testing. You are done building the test infrastructure. From this point testing is automatic,
invisible, and low-effort. Here is exactly what runs, when, and what requires your attention.
FrequencyWhat RunsAutomated?Your Time
Every commitUnit tests (pytest tests/unit/)Yes — GitHub
## Actions
0 min (only if CI fails)
Every commitSnyk CVE scan on Docker imagesYes — GitHub
## Actions
0 min (only if critical CVE)
Every commitTypeScript strict compile checkYes — GitHub
## Actions
0 min (only if fails)
Every deploySmoke test: /health endpoint checkYes —
post-deploy hook
0 min (only if fails)
## Every
## Monday
Review Agent Lightning accuracy reportReport
auto-generates
15 min review
## Every
## Monday
Review Grafana dashboard + alertsDashboard always
live
10 min review
## Every
## Monday
Review Sentry error count (target: 0 new
errors)
Sentry always
running
10 min review
WeeklyChaos experiments (Sunday 2am
staging)
Yes — automated
schedule
30 min reviewing results
WeeklyPenetration test re-run (automated parts)Snyk + OWASP
## ZAP
0 min (only if findings)
MonthlyFull load test (Locust)Manual trigger1 hour including review
MonthlyOWASP manual checklist re-runManual2 hours
MonthlyReview and rotate secrets/API keysManual30 min
QuarterlyAccess review: who has access to what?Report
auto-generates
1 hour review + certify
QuarterlyFull compliance test suite (GDPR, TCPA,
## HIPAA)
Semi-automated2 hours
QuarterlyUpdate sub_processors.md if any new
vendors added
Manual30 min
Before every
release
Full E2E test suiteAutomated +
manual review
2 hours
## Before
enterprise
client
External penetration testThird-party firm1 week + 2 weeks remediation

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 21
## SOC 2
observation
period
All controls must pass every weekVanta/Drata
monitors
2 hours/week
AnnuallyRenew TLS certificates (if manual)Cert-manager
auto-renews
0 min (verify renewal)
AnnuallyRotate KMS encryption keysCan be automated30 min to verify
AnnuallyReview and update all policy documentsManual1 day
Total ongoing testing time after Week 60:
WeeklyMonthlyQuarterly
~65 minutes (mostly Monday morning
review)
~3.5 hours (load test + OWASP + secrets)~3.5 hours (access review + compliance)

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 22
## 11.  Production Readiness Checklist
## The Final Gate: Are You Actually Ready?
This is the complete checklist. Every item must be checked before you consider yourself production ready. For Weeks 1-40:
check the Core Product section. For Weeks 41-60: check all sections.
Core Product (Weeks 1-40)
n
Unit testspytest tests/unit/ → 100% pass, >80% coverage
n
Integration testspytest tests/integration/ → all 4 files pass
n
E2E testsAll 6 critical journeys pass including refund Stripe-called-once test
n
Security — RLSCross-tenant query returns 0 rows (tested 5 different ways)
n
Security — HMACForged webhook returns 401. Replayed webhook returns 409.
n
Security — Rate limitingAll 3 tiers return 429 at correct thresholds
n
Security — OWASPAll 10 OWASP checks pass with zero critical findings
n
AuthJWT round-trip works. Wrong signature rejected. Expired token rejected.
n
Approval gateRefund NEVER executes without explicit approval (tested 10 scenarios)
n
Audit trailHash chain validates. UPDATE/DELETE raises PG exception.
n
Agent LightningTraining cycle runs. Validation blocks <90% accuracy. Drift detection works.
n
MonitoringAll 6 alerts fire and send notifications. Grafana dashboards load.
n
PerformanceP95 <500ms at 100 concurrent users. Light tier >85% of queries.
n
GDPRExport complete. Deletion anonymises PII. Retention policy enforced.
n
DockerAll 4 images build under 500MB. docker-compose prod starts healthy.
n
CI/CDPush to main deploys automatically with zero manual steps.
n
Health check/health returns {status: ok, db: connected, redis: connected}
n
VariantsAll 3 variants importable simultaneously with no conflicts
Cloud Infrastructure (Weeks 41-44)
n
Kuberneteskubectl get nodes: 2+ nodes in Ready state
n
TLSSSL Labs: A+ rating on production domain
n
CDNStatic assets served from CDN (verified in Network tab)
n
DB backupsDaily snapshot appears in cloud console. Cross-region copy working.

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 23
n
FailoverPrimary region shutdown → secondary handles traffic within 30 seconds
n
Zero-downtime deployDeploy under load: zero HTTP 5xx errors during rollout
n
CostCurrent cloud spend within free credit budget
Payments (Weeks 45-46)
n
RazorpayIndian client payment processes via Razorpay (not Stripe)
n
Tax — GSTIndian invoice shows 18% GST correctly
n
Tax — VATUK invoice shows 20% VAT correctly
n
DunningFailed payment: Day 1 retry, Day 3 warning, Day 14 suspension
n
Multi-currencyVariant cards show local currency based on client country
n
Invoice PDFContains: tax registration, line items, tax breakdown, legal entity
Mobile (Weeks 47-49)
n
Real device — iOSAll core flows tested on real iPhone
n
Real device — AndroidAll core flows tested on real Android device
n
Push notificationsApproval alert arrives within 30 seconds on real device
n
Approve from notificationApproval works without opening app
n
App StoreiOS .ipa submitted and approved in App Store
n
Google PlayAndroid .apk submitted and approved in Google Play
Enterprise SSO (Weeks 50-52)
n
SAML 2.0Full SAML flow tested with Okta developer account
n
OktaOkta SSO login works end-to-end
n
Azure ADAzure AD SSO login works end-to-end
n
SCIM provisioningUser provisioned in Okta → appears in PARWA within 60 seconds
n
SCIM deprovisioningUser removed in Okta → deactivated in PARWA within 60 seconds
n
MFA enforcementEnterprise client with MFA policy: login requires MFA (cannot bypass)
n
SSO audit logAll logins logged. CSV export works.
99.99% Uptime (Weeks 53-55)
n
Multi-regionBoth regions serving traffic simultaneously

PARWA — Complete Testing GuideProduction Ready Checklist
Confidential — Internal Use OnlyPage 24
n
Failover timePrimary shutdown → secondary active within 30 seconds
n
Circuit breakersShopify down → circuit opens → system continues with fallback
n
Chaos — pod killPod killed → self-heals within 60 seconds → zero client errors
n
Chaos — network delay300ms delay injected → system stays functional
n
Chaos — full regionFull region disabled → zero errors after 30-second failover window
n
Distributed tracingFull request trace visible in tracing dashboard
n
SLA documentationdocs/sla-verification.md shows measured failover times as evidence
SOC 2 Type II (Weeks 56-60)
n
All policies signed6 policy documents complete and dated
n
Vanta/Drata90%+ controls showing green in compliance automation tool
n
Vulnerability scanZero critical CVEs on all container images
n
Log retentionLogs retained 90+ days and accessible
n
Access reviewQuarterly access review completed and certified
n
Anomaly detectionNew country login alert fires within 5 minutes
n
Mock auditAll questions answerable with evidence within 5 minutes
n
Auditor engagedSOC 2 firm engaged. Observation period start date confirmed.
n
Management assertionSigned by founder
## Production Ready
When every checkbox above is ticked, you have a product that: handles real clients reliably, protects their data legally,
scales automatically when traffic spikes, recovers from failures without you waking up at 3am, earns enterprise trust
with SOC 2, and gets smarter every Saturday through Agent Lightning. That is what production ready actually means.