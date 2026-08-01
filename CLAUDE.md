# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Use Graphify Before Coding

**Understand the codebase before you change it.**

Before writing or modifying any code in this project:
- Run `graphify query "<what you need>" --graph graphify-out/graph.json` to understand how the code connects.
- Run `graphify explain "<node>" --graph graphify-out/graph.json` to understand a specific module and its neighbors.
- Run `graphify affected "<file>" --depth 3 --graph graphify-out/graph.json` to find what your change might break.
- Never assume you know the structure — query the graph first. The codebase is large and interconnected.
- If Graphify reveals dependencies or connections you didn't expect, stop and adjust your plan.

**Why:** This project has 68K+ nodes and 97K+ edges. Guessing how things connect leads to broken code. Graphify's graph already maps every function, class, and import — use it.

## 6. PARWA-Specific Rules

**P-001: Two Agent Pipelines Exist**
- PARWA Pipeline (graph_v2.py): 8-node customer-care pipeline. This is the MAIN product pipeline.
- Jarvis Pipeline (graph.py): 3-node admin pipeline (Sense → Evaluate → Notify). This handles admin commands, monitoring, and notifications.
- These are SEPARATE graphs. Do not mix them.

**P-002: Variant Tiers Are Real Product Lines**
- PARWA Growth ($2,999/mo) and PARWA High ($3,999/mo).
- Mini PARWA was removed on 2026-07-26 — only 2 tiers remain.
- All tiers use the SAME 8-node pipeline. Node 2 (Smart Route) handles tier-based routing internally.
- Never create separate pipeline files per tier — the V2 unified pipeline replaced the old 3-pipeline system.
- Legacy "mini"/"starter"/"mini_parwa" strings auto-upgrade to "parwa" via normalize_variant_name() — existing Mini subscribers get Parwa features for free at runtime.
- Financial guardrails differ by tier: parwa has $500 refund / $200 credit limits; high has unlimited.

**P-003: Simple Language**
- The CEO is non-technical. Explain everything in plain business language.
- No jargon, no code snippets in explanations. Use analogies.

**P-004: Business First**
- Always connect technical decisions to business impact (revenue, customer experience, shipping speed).
- Every code change should answer: "How does this help us ship the product?"

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
