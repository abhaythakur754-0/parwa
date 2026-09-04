# Spec: 002 — Ponytail Adoption (code quality for new hires)

**Status:** Shipped 2026-09-03
**Source:** github.com/DietrichGebert/ponytail (MIT) — "makes your AI agent think
like the laziest senior dev in the room": ~54% less code, ~20% cheaper, ~27%
faster on real repo benchmarks, 100% safety guards kept.
**Constitution:** Article IV encodes the ponytail ladder.

## Problem

The CEO's requirement: when we hire developers, they must be able to
understand the codebase. Over-engineered, bloated AI-generated code is the
enemy of that. spec-kit governs WHAT we build; ponytail governs HOW LITTLE
we build. They compose: spec 001 made reads honest and fast; spec 002 makes
future diffs small and boring.

## Shipped

- `AGENTS.md` at repo root — always-on ruleset (the ladder + bug-fix-root-cause
  + never-cut-validation rules). Every agent that reads AGENTS.md (Claude Code,
  Codex, Cursor, Gemini, Jules, Amp, …) inherits it.
- `.claude/skills/ponytail*/SKILL.md` — 6 skills vendored verbatim:
  ponytail (lite/full/ultra), ponytail-review, ponytail-audit, ponytail-debt,
  ponytail-gain, ponytail-help.
- `CLAUDE.md` §7 — pointer so Claude sessions load the ruleset.
- spec-kit `speckit-*` skills already present alongside (adopted in spec 001).

## Ponytail-audit of the hot paths (one-shot, ranked)

Audit scope: ticket/escalation/proxy hot paths + previously flagged dead
candidates. Per the skill's boundary: lists findings, applies nothing
today except verified-zero-risk items (none qualified).

1. `native:` `uuid` npm package used as `v4 as uuid` in 4+ stores
   (ticket-store, system-health-store, notification-store, approval-store).
   `crypto.randomUUID()` is native in all target runtimes. Swap is churn
   without behavior change — bundle it with the next touch of each store.
2. `delete:` `backend/app/core/parwa_graph_state.py` (legacy V1 pipeline
   state) — zero PROD importers, but 4 test files import it; needs the
   tests deleted/rewritten in the same PR. Not zero-risk today.
3. `shrink:` `SyncErrorState` and `EmptyState` in tickets/page.tsx share
   skeleton. Two instances with different semantics — merging now would be
   an abstraction with the same number of call sites it saves. Revisit at
   the third instance.

## False positives worth recording (audit discipline)

- `src/components/onboarding/IntegrationStep.tsx` was flagged "unused" in an
  earlier session's notes — ACTUALLY imported by dashboard/integrations/page.tsx
  (power-user catalog). Alive. Do not delete.
- Every onboarding component is imported (directly or relatively by the
  wizard). The folder is 100% live code.

## Verification

- Vendored files byte-identical to upstream `main` (fetched 2026-09-03).
- tsc 80 errors = baseline; jest 177F/557P identical to baseline (both
  pre-existing; nothing in this spec touches runtime code).
