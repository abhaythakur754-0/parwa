# PARWA Security Audit — Working Tracker

**Baseline branch:** `main`  
**Baseline commit:** `f85afaecd011aa37f0970cad4f04cd81a7b5a0ac`  
**Baseline checked:** 2026-11-26  
**Owner workflow:** direct work on `main`; no unnecessary branches.  
**Handoff rule:** after every successful push to `main`, refresh the existing PARWA Library ZIP from that exact commit before continuing.

## Focused production-security schedule

**Purpose:** complete only the security work necessary to establish a defensible production baseline. Do not spend time exhaustively re-auditing low-risk historical findings or repeating already completed checks. Historical findings are used as leads, not as a mandatory 93-item checklist.

| Stage | Essential scope | Estimate | Status |
|---|---|---:|---|
| 1 | Reconcile the seven user-confirmed completed checks and existing critical fixes; verify current baseline and identify genuine gaps | 1–2 hours | COMPLETE / carry-forward verification only |
| 2 | Authentication, MFA, authorization, admin privilege boundaries and tenant isolation | 2–3 hours | IN PROGRESS |
| 3 | Secrets, token/session protection, sensitive APIs and fail-closed production configuration | 2–3 hours | NOT STARTED |
| 4 | Webhook authenticity/replay protection, integration permissions, rate limits and essential browser/API protections (including CSRF/CORS/security headers where applicable) | 2–3 hours | NOT STARTED |
| 5 | Run required security regression tests; verify deployment/security settings; document unresolved risks and evidence-based sign-off | 2–3 hours | NOT STARTED |

**Estimated focused engineering effort: 9–14 hours.** This is a planning estimate, not a completion guarantee; confirmed vulnerabilities, external provider dependencies, or CI/deployment failures may extend it.

### Scope control

- **Must fix before production:** cross-tenant access, authentication/MFA bypass, unauthorized actions or privilege escalation, exposed secrets, unprotected sensitive endpoints, forged/replayed webhooks, and unsafe integration permissions.
- **Verify proportionately:** rate limiting, CSRF/CORS, security headers, TLS, Redis and other deployment controls according to the actual exposed deployment paths.
- **Defer/document:** low-risk style or hardening observations that do not create a meaningful exploitable production risk, plus stale or non-applicable historical findings.
- Do not count a historical report item as currently open without checking the current code and its callers. Do not mark an item fixed based only on a related commit.
- The seven completed checks remain credited; do not repeat them unless a relevant code change or regression gives a concrete reason.
- Stage 5 must include evidence from CI and production configuration review. A green CI run alone is not production sign-off.

## Stage 1 — Baseline and reconciliation

### Repository and CI baseline

- Current `main` at baseline: `f85afaecd011aa37f0970cad4f04cd81a7b5a0ac`.
- Latest CI Pipeline run checked: [run 45792673874](https://github.com/abhaythakur754-0/parwa/actions/runs/45792673874).
- Result: `test-backend`, `test-frontend`, and `Package verified source snapshot` all completed successfully.
- Existing `security_audit_report.md` is dated 2026-05-08 and records **15 Critical, 22 High, 39 Medium, 17 Low (93 historical findings)**. These are historical counts, not a verified current-open count.
- The historical report explicitly excludes Jarvis Control System and Onboarding. Those areas therefore require explicit coverage in the current audit; they are not implicitly cleared by the old report.
- The current CI workflow has a dedicated deterministic security-test step covering outbound webhook URL validation, production security configuration, security headers, and voice recording policy. It also runs broader unit/integration suites. CI green is not a substitute for full production verification.
- Local test execution was not available through the connected GitHub interface in this audit session. No claim is made that tests were run locally.

### Previously completed work carried forward — do not redo

The user has confirmed these seven security checks as already completed. Preserve this progress and verify only where a later change could have affected it:

1. Chat-widget visitor impersonation and cross-tenant protections.
2. Onboarding OTP activation-bypass fix.
3. Sensitive-route middleware exemption fixes.
4. Token revocation checks.
5. Inactive-account authentication checks.
6. Regression tests for those fixes.
7. Docker Redis security check and deployment checklist.

Additional recent security commits already on `main` at the baseline include:

- `514b747` — scope onboarding awareness to authenticated tenant.
- `43bb3b3` — tenant isolation for technique configuration.
- `e785f99` — prevent spoofed Brevo webhook IP checks.
- `f9a958d` — reject future-dated webhook replays.
- `0430dd1` — add required security regression suite.
- `d8182b1`, `70eed45`, `a3c9165` — Jarvis CC admin restriction, session ownership, and command-role enforcement.
- `5ffc3ac` — enforce tenant voice-recording policy.
- `f85afae` — restrict voice configuration changes to admins.

These commits are inventory evidence, not automatic proof that every related historical finding is fully closed.

### Initial verification notes for severity stages

- Production configuration currently contains fail-closed validation for important production secrets. Historical C-06 must be checked against its exact tests and all relevant secret validators before closure.
- Current MFA routes use a temporary MFA session-token flow rather than requiring an ordinary authenticated JWT at the initial MFA step; historical C-09 requires current-flow verification rather than blindly repeating the old fix.
- A potential separate MFA hardening gap was observed: Redis errors appear to permit in-memory pending-session fallback. Confirm exact production behavior and add failure-path regression tests if still present. This is not yet classified as a confirmed exploitable bypass.
- Current security-header middleware and outbound URL validation implementations exist; the corresponding historical findings must be checked against actual callers and regression tests.
- The recent Jarvis and voice commits expand coverage beyond the old audit's stated exclusions.

### Stage 1 outcome

**Stage 1 is complete:** the baseline commit, CI result, historical finding counts, previously completed checks, recent security commits, and audit scope gap are recorded. Severity stages 2–5 will now perform the detailed current-code classification and remediation. No historical finding is counted as currently open without revalidation.

## Stage 2 — Critical findings (in progress)

- **MFA temporary-session storage outage behavior:** confirmed code contradicted its own comment: process-local fallback was used even in production if Redis storage or retrieval failed. Updated `backend/app/api/mfa.py` to fail closed with HTTP 503 when creating a pre-auth MFA session cannot be stored in Redis, and to reject retrieval during Redis failure in production. Non-production fallback remains available.
- Added `backend/tests/unit/test_mfa_session_storage_security.py` with three regression guards for production store failure, production read failure, and non-production fallback preservation. Added it to the required CI Security Regression Suite so the focused checks cannot silently be skipped.
- Local targeted test: `PYTHONPATH=backend python -m pytest backend/tests/unit/test_mfa_session_storage_security.py -q --tb=short --noconftest` — **3 passed** in the isolated source snapshot. The normal repository conftest path was not used because this container lacks the repository's full dependency environment; the focused tests themselves require only the installed pytest runtime.
- Historical C-09 is not yet signed off: the code has a dedicated pre-auth temporary-session route, but the entire password → MFA challenge → token issuance path still needs end-to-end verification.

## Required workflow for every finding

1. Locate the current implementation on `main` and inspect its callers.
2. Classify it as `FIXED & VERIFIED`, `FIXED — VERIFY REGRESSION`, `PARTIAL`, `OPEN`, `STALE / NOT APPLICABLE`, or `EXTERNAL / OPERATIONAL`.
3. Do not redo completed work; only add missing verification or address regressions.
4. For open findings, make the smallest complete fix and add targeted regression coverage.
5. Run local tests when a real local environment is available; otherwise state the limitation and rely on the appropriate CI verification without claiming local execution.
6. Push directly to `main` only after checks are satisfactory; never create an unnecessary branch.
7. Verify the GitHub Actions run for the exact pushed SHA.
8. Refresh the existing Library ZIP from that exact `main` SHA before starting the next work item.
9. Update this tracker and the audit report with commit and test evidence.

## Post-agent/integration merge rule

When the separate agent/integration work is merged, do not restart this audit. Run the full security regression suite and re-review only security-sensitive changed areas (especially OAuth, tenant isolation, webhook verification/replay, CRM permissions, credential storage, and action authorization), then complete the final production verification stage.
