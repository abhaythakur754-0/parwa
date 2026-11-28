# PARWA Security Audit — Working Tracker

**Baseline branch:** `main`  
**Baseline commit:** `f85afaecd011aa37f0970cad4f04cd81a7b5a0ac`  
**Baseline checked:** 2026-11-26  
**Owner workflow:** direct work on `main`; no unnecessary branches.  
**Handoff rule:** after every successful push to `main`, refresh the existing PARWA Library ZIP from that exact commit before continuing.

## Focused production-security schedule — remaining work only

**Rule:** the seven security checks listed under "Previously completed work carried forward" are CLOSED and excluded from this schedule. They are not tasks, they are not included in the estimate, and they must not be repeated absent a concrete regression or security-sensitive code change. Baseline inventory is complete; no separate stage is allocated to re-auditing it.

| Order | Remaining necessary work | What is included (only unresolved/unverified items) | Estimate | Status |
|---|---|---|---:|---|
| 1 | Finish critical authentication and authorization gaps | Verify the full password → MFA challenge → token issuance flow (C-09); confirm dashboard/API authentication, real token validation, admin/platform-admin boundaries, billing endpoint protection, and RAG tenant scoping (C-01, C-02, C-10, C-11, C-12). Fix only confirmed gaps. | 2–3 hours | PENDING |
| 2 | Finish critical secrets, session and infrastructure gaps | Verify production secret fail-closed behavior, refresh-token pepper, MCP token enforcement, CORS fallback, trusted tenant-header handling, OAuth token encryption, PostgreSQL TLS, and whether historical `.env.prod` exposure requires credential rotation (C-04–C-08, C-13–C-15). Do not rework controls already proven effective. | 2–3 hours | PENDING |
| 3 | Close only high-impact remaining attack paths | Check the still-relevant high-risk items: open redirects, email/OTP verification weaknesses, billing/admin middleware coverage, webhook fail-closed/replay behavior, OAuth URL leakage, billing roles, webhook status/retry authorization, HTML injection, API-key disclosure, chat API auth/rate limits, CSRF where cookie auth applies, mock-login remnants, and workflow tenant-IDOR. Existing completed webhook, onboarding, tenant, and Jarvis fixes are credited—not repeated. | 2–3 hours | PENDING |
| 4 | One final verification and sign-off | Run the complete required security regression suite and relevant backend/frontend tests; verify production deployment settings and operational actions (including any required credential rotation); record only genuine residual risks and evidence. | 1–2 hours | PENDING |

**Estimated remaining engineering effort: 7–11 focused hours**, assuming no newly discovered critical vulnerability, external credential-rotation delay, or deployment/provider access blocker. This estimate excludes the seven completed checks and excludes unrelated agent/integration feature work.

### Explicitly out of scope for this focused pass

- Repeating the seven completed checks.
- Re-auditing all 93 historical findings line by line regardless of relevance.
- Low-risk style-only or speculative hardening findings with no meaningful production exploit path; document/defer these.
- Re-running checks solely to create more activity. Re-test only when a concrete code change or regression makes it necessary.

### Completion rule

A task is complete only when the current implementation and its callers are inspected, any real gap is fixed, targeted regression coverage passes, and the relevant CI run for the exact pushed `main` commit is verified. Production sign-off additionally requires deployment/credential checks; a green CI run alone is insufficient. After each push, refresh the existing Library ZIP from that exact commit before proceeding.

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
