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
| 1 | Finish critical authentication and authorization gaps | Verify the full password → MFA challenge → token issuance flow (C-09); confirm dashboard/API authentication, real token validation, admin/platform-admin boundaries, billing endpoint protection, and RAG tenant scoping (C-01, C-02, C-10, C-11, C-12). Fix only confirmed gaps. | 2–3 hours | COMPLETE |
| 2 | Finish critical secrets, session and infrastructure gaps | Verify production secret fail-closed behavior, refresh-token pepper, MCP token enforcement, CORS fallback, trusted tenant-header handling, OAuth token encryption, PostgreSQL TLS, and whether historical `.env.prod` exposure requires credential rotation (C-04–C-08, C-13–C-15). Do not rework controls already proven effective. | 2–3 hours | IN PROGRESS — fixes added; CI pending |
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
- **C-09 implementation closed:** password login and Google OAuth for existing MFA-enrolled accounts now return a Redis-backed pre-auth challenge without issuing access/refresh tokens; both Next.js login routes preserve that challenge; TOTP and backup-code verification are tenant-bound and issue the standard bounded token pair only after successful proof; the Next.js MFA proxy writes the resulting tokens to HttpOnly cookies.
- Added `backend/tests/unit/test_mfa_login_enforcement_security.py` and updated the existing MFA client tests for the challenge token and correct endpoints. The focused workflow runs the two backend security contract files plus the MFA store and login integration tests. Both focused jobs passed in run [46104331563](https://github.com/abhaythakur754-0/parwa/actions/runs/46104331563) for commit `8673f264e1e79f4366c49df9a155abc5a5043aee`.
- The dedicated workflow now packages the exact tested source snapshot as an artifact after both focused jobs pass. `ci.yml` ignores changes limited to these MFA security paths so unrelated full-suite work is not repeated; changes outside those paths continue to use the normal CI pipeline.
- **Residual verification boundary:** this closes the code-path defect and its focused regression contracts; production provider/Redis end-to-end smoke testing and the remaining Stage 1 authorization findings are still part of final production sign-off.

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

### Stage 2 — Current-code findings and remediation (2026-11-28)

- **C-04 — MCP token enforcement: FIXED; hardening added.** `mcp_server/main.py` applies Bearer authentication to all MCP routes except health/root, uses constant-time comparison, and blocks requests when the production token is absent. The separate `MCPSettings` validator previously checked only presence; it now also rejects placeholders and values shorter than 32 characters in production.
- **C-05 — CORS wildcard fallback: FIXED; explicit wildcard rejected.** Backend and MCP configuration now reject `*` because credentialed CORS is enabled. Backend fallback remains an explicit frontend origin (or localhost on settings failure); MCP fallback remains an empty allowlist.
- **C-06 — production secrets: FIXED & VERIFIED by existing tests.** Production validators cover application/JWT/encryption secrets, MCP token, Redis credentials, and pricing signing key. Existing production-security tests cover missing, weak, and placeholder values; this pass adds MCP-specific coverage.
- **C-07 — historical `.env.prod`: STALE / NOT FOUND IN ACCESSIBLE HISTORY.** No `.env.prod` file is present in the current recursive `main` tree (only `.env.prod.example`), and GitHub's path-specific history for root `.env.prod` returned no commits. This cannot rule out exposure through another repository, fork, branch, or rewritten history. Rotate any real secrets if operators know they were committed or disclosed.
- **C-08 — trusted tenant header: FIXED for the reported header path.** `VariantCheckMiddleware` explicitly ignores `X-Company-ID` and reads the company claim from the Bearer token instead. It decodes that claim without signature verification for variant-limit lookup only; protected route authentication must remain the authorization source.
- **C-13 — PostgreSQL TLS: remediation added.** The database URL helper previously appended `sslmode=require` only when no `sslmode` parameter existed, allowing `sslmode=disable` or `prefer` to downgrade transport. It now forces `require` unless the configured mode is `require`, `verify-ca`, or `verify-full`. Focused tests cover absent, disabled, prefer, and verified modes.
- **C-14 — OAuth token encryption: PARTIAL / DATA MIGRATION OPERATIONAL.** New integration credentials and Google OAuth access/refresh tokens are Fernet-encrypted before persistence. Legacy plaintext JSON is still supported and migrated only when read, so untouched database rows may remain plaintext. A production inventory and one-time migration are required before claiming all historical data is encrypted.
- **C-15 — refresh-token pepper: FIXED & VERIFIED by current configuration.** Production settings reject missing, placeholder, or shorter-than-32-character pepper values; refresh-token hashes use that pepper. The `jwt_auth.py` fail-open warning is stale wording because production settings validation now fails when the pepper is missing. Confirm the deployed `.env.prod`/secret store actually supplies `REFRESH_TOKEN_PEPPER` at final sign-off.

**Stage 2 regression additions:** production-security tests now cover backend/MCP wildcard CORS rejection, strong production MCP token requirements, and PostgreSQL SSL-mode downgrade prevention. Local execution was not performed through the available GitHub interface; CI verification is required before closing Stage 2.
- **C-05 — broad credentialed preview-origin pattern removed:** the backend allowed arbitrary Vercel subdomains through a regex while credentialed CORS was enabled. Preview origins must now be explicitly listed in CORS_ORIGINS.
- **C-06 — placeholder-validation gap:** production templates use long CHANGE_ME_ values. The placeholder detector now rejects underscore/space variants, and tests exercise actual template values.
- **C-08 — variant quota identity hardened:** VariantCheckMiddleware previously decoded company_id from an unverified JWT payload before TenantMiddleware ran. It now runs after TenantMiddleware and reads only the verified request.state.company_id set by tenant/API-key authentication. It never accepts the client X-Company-ID header or unverified token claims.
- **C-04 / C-15 — Kubernetes production secret wiring:** added REFRESH_TOKEN_PEPPER and MCP_AUTH_TOKEN to the secret template and wired required values into backend, worker, and MCP deployments. Worker also receives JWT_SECRET_KEY and DATA_ENCRYPTION_KEY because it loads backend application settings. Operators must replace all CHANGE_ME_ placeholders before deployment.
- **C-15 — Compose production template:** added the required refresh-token pepper to .env.prod.example; backend and worker consume .env.prod through env_file.

- **C-13 — exporter downgrade corrected:** the PostgreSQL exporter bypasses the application SQLAlchemy URL helper, so its Compose connection had remained explicitly set to `sslmode=disable`. It now requests TLS with `sslmode=require`. The PostgreSQL server's TLS listener/certificate and deployed connection must still be confirmed in the target environment.
- **C-14 — controlled legacy migration added:** added an explicit dry-run-first script for all OAuthAccount token fields and Integration credential rows. It aborts on unreadable/corrupt values and only persists changes with an explicit `--apply`; it has not been run against production data.
