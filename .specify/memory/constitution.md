# PARWA Constitution — Non-Negotiable Engineering Principles

Ratified: 2026-09-03 · Applies to every feature spec, plan, and task in this repo.
Amendments require a written rationale in the spec that violates them.

## Article I — Honest Systems

The product must never fabricate success. When a dependency is down, slow, or
uncertain, the UI says so and offers a retry. Fake empty lists, fake "all
clear" states, and silent failures are defects of the same severity as data
loss: they destroy the user's trust in every other number we show.

## Article II — Hot Reads Are Cached

Any read endpoint polled by a dashboard (ticket lists, escalation lists,
stats) must be served through the tenant-keyed Redis cache-aside layer with
a short TTL, failing open to the database. PostgreSQL is the source of truth,
not the first hop of every page view.

## Article III — Measure Everything

No performance claim ships without a measurement. Load-test the happy path
and the degraded path (dependency down). Record both numbers in the spec.

## Article IV — The Boring Ladder

Before writing new code, stop at the first rung that holds:
1. Does this need to exist? (YAGNI)
2. Already in this codebase? Reuse it.
3. Stdlib / platform feature does it? Use it.
4. Installed dependency does it? Use it.
5. One line? One line.
6. Only then: the minimum that works.

Never cut validation, error handling, security, or accessibility to climb
down the ladder. The code ends up small because it is necessary, not golfed.

## Article V — Two Pipelines Stay Separate

PARWA pipeline (graph_v2.py, 8 nodes, customer care) and Jarvis pipeline
(graph.py, 3 nodes, admin) never merge responsibilities. See CLAUDE.md P-001.

## Article VI — Simple Language, Business First

Explanations to the CEO use plain business language (CLAUDE.md P-003/P-004).
Every change answers: how does this help us ship the product?
