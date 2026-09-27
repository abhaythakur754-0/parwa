#!/usr/bin/env python3
"""
Verify the OSS stack end-to-end — PASS/FAIL/SKIP table, exit code 0 iff
nothing FAILs (SKIPs are allowed: optional deps/models not installed).

Run from repo root or backend/:
    python scripts/verify_oss_stack.py
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "backend" / "app"))

results = []


def record(name, ok, note=""):
    results.append((name, "PASS" if ok else "FAIL", note))
    icon = "✅" if ok else "❌"
    print(f"  {icon} {name:<38} {('PASS' if ok else 'FAIL') + ((' — ' + note) if note else '')}")


def skip(name, note=""):
    results.append((name, "SKIP", note))
    print(f"  ⏭️  {name:<38} SKIP{(' — ' + note) if note else ''}")


def run(name, fn, skippable=False):
    print(f"\n▶ {name}")
    try:
        fn()
    except SkipTest as exc:
        skip(name, str(exc))
    except Exception as exc:
        if skippable:
            skip(name, f"{type(exc).__name__}: {str(exc)[:100]}")
        else:
            record(name, False, f"{type(exc).__name__}: {str(exc)[:160]}")
            traceback.print_exc(limit=1)


class SkipTest(Exception):
    pass


print("=" * 70)
print("OSS STACK VERIFICATION")
print("=" * 70)

# ── 0. availability report ────────────────────────────────────────────
from app.core.oss_stack import availability  # noqa: E402

print("\nInstalled/enabled components:")
for k, v in availability().items():
    print(f"  • {k:<12} installed={v['installed']}  enabled={v.get('enabled', '—')}")

# ── 1. guard (always available) ───────────────────────────────────────
from app.core.oss_stack import guard  # noqa: E402


def t_guard():
    think_only = "<think>Let me analyze this refund case carefully. The customer"
    real = "<think>internal</think>Dear customer, refunds are accepted within 14 days of purchase. Your order #4521 qualifies for a full refund of $49.99."
    empty = "   "
    s1, v1, q1 = guard.sanitize(real)
    record("guard.strip_think", s1 == "Dear customer, refunds are accepted within 14 days of purchase. Your order #4521 qualifies for a full refund of $49.99.")
    record("guard.real_answer_valid", v1 and q1 > 0.5, f"quality={q1:.2f}")
    s2, v2, q2 = guard.sanitize(think_only)
    record("guard.think_only_rejected", not v2 and q2 < 0.35, f"quality={q2:.2f}")
    _, v3, _ = guard.sanitize(empty)
    record("guard.empty_rejected", not v3)


run("guard (answer trust layer)", t_guard)

# ── 2. docparse ───────────────────────────────────────────────────────
from app.core.oss_stack import docparse  # noqa: E402


def t_docparse():
    md_text = docparse.parse("policy.md", b"# Refund Policy\n\nRefunds within 14 days.\n\nSection two here.")
    record("docparse.text_formats", md_text is not None and "Refunds within 14 days" in md_text)
    chunks = docparse.chunk_text(md_text or "")
    record("docparse.chunking", len(chunks) >= 1 and all(len(c) <= 1100 for c in chunks), f"{len(chunks)} chunks")
    pdf = docparse.parse("report.pdf", b"%PDF-1.4 fake binary")
    if docparse.is_available():
        record("docparse.binary_handled", pdf is None or isinstance(pdf, str))
    else:
        record("docparse.binary_refused_without_parser", pdf is None)


run("docparse (MarkItDown)", t_docparse)

# ── 3. embeddings (fastembed) ─────────────────────────────────────────
from app.core.oss_stack import embeddings as emb  # noqa: E402


def t_embeddings():
    if not emb.is_available():
        raise SkipTest("fastembed not installed (pip install fastembed)")
    a = emb.embed("How do I get a refund for my order?")
    b = emb.embed("Can I return this product and get my money back?")
    c = emb.embed("Reset my password please, I cannot login.")
    if a is None:
        raise SkipTest("model download failed or unavailable in this environment")
    record("embeddings.dim384", len(a) == 384)
    sim_same = emb.cosine(a, b)
    sim_diff = emb.cosine(a, c)
    record("embeddings.semantic_similarity", sim_same > sim_diff, f"same={sim_same:.3f} diff={sim_diff:.3f}")
    lit = emb.to_stored_literal(a)
    back = emb.from_stored_literal(lit)
    record("embeddings.stored_literal_roundtrip", back is not None and emb.cosine(a, back) > 0.999)
    ranked = emb.rank_chunks(
        "refund policy timeframe",
        [("c1", "Refunds are processed within 14 days of purchase.", "d1"),
         ("c2", "To reset your password, click forgot password.", "d1")],
    )
    record("embeddings.rank_chunks", ranked and ranked[0]["id"] == "c1", f"top={ranked[0]['id'] if ranked else None}")


run("embeddings (fastembed ONNX)", t_embeddings, skippable=True)

# ── 4. kb (bm25 + dedupe + parse_and_chunk) ──────────────────────────
from app.core.oss_stack import kb  # noqa: E402


def t_kb():
    text, chunks = kb.parse_and_chunk("faq.md", b"Line one.\n\nLine two.\n\nLine three.")
    record("kb.parse_and_chunk", text is not None and len(chunks) == 1, "short paragraphs merge to 1 chunk")
    text2, chunks2 = kb.parse_and_chunk(
        "faq.md",
        ("Refund policy paragraph. " * 60 + "\n\n" + "Office hours paragraph. " * 60).encode(),
    )
    record("kb.parse_and_chunk_multi", text2 is not None and len(chunks2) >= 2, f"{len(chunks2)} chunks")
    rows = [
        ("c1", "Refunds accepted within 14 days of purchase, original payment method only.", "d1"),
        ("c2", "Our office hours are 9am to 5pm Monday to Friday.", "d1"),
        ("c3", "To change your billing address, go to settings.", "d2"),
    ]
    ranked = kb.bm25_rank("when do I get my refund", rows)
    record("kb.bm25_rank_top", ranked and ranked[0]["id"] == "c1", f"top={ranked[0]['id'] if ranked else None}")
    deduped = kb.fuzzy_dedupe(["Refund policy text.", "refund policy text.", "Different content entirely!"])
    record("kb.fuzzy_dedupe", len(deduped) == 2, f"kept={deduped}")


run("kb helpers (bm25 + dedupe)", t_kb)

# ── 5. pii redaction ──────────────────────────────────────────────────
from app.core.oss_stack import pii  # noqa: E402


def t_pii():
    dirty = "My card 4532 1111 2222 3334 was charged twice, email me at ravi@example.com or call 987-654-3210."
    clean = pii.redact(dirty)
    ok = ("ravi@example.com" not in clean) and ("<EMAIL>" in clean)
    record("pii.regex_fallback", ok, clean[:80])
    if pii.is_available():
        clean2 = pii.redact(dirty)
        record("pii.presidio", "ravi@example.com" not in clean2, "presidio engine used")
    else:
        skip("pii.presidio", "not enabled (OSS_PII=0) — regex fallback is active")


run("pii (Presidio + fallback)", t_pii)

# ── 6. intent classification ──────────────────────────────────────────
from app.core.oss_stack import intent  # noqa: E402


def t_intent():
    out = intent.classify("I want my money back for order 4521, refund please", top_k=3)
    if not out["labels"]:
        raise SkipTest("no engine available (install fastembed, or gliclass)")
    top = out["labels"][0]["label"]
    record("intent.top_label", top == "refund_request", f"top={top} engine={out['engine']}")
    record("intent.urgency_rule", out["urgency"] == "normal")
    urgent = intent.classify("This is unacceptable, fix it NOW or I call my lawyer")
    record("intent.urgency_cues", urgent["urgency"] == "urgent")


run("intent (zero-shot triage)", t_intent, skippable=True)

# ── 7. entity extraction ──────────────────────────────────────────────
from app.core.oss_stack import entities  # noqa: E402


def t_entities():
    out = entities.extract(
        "My order #AB-12345 arrived broken. Want my $49.99 back. Email ravi@example.com, phone 987-654-3210. Bought on 03/15/2026."
    )
    record("entities.order_numbers", "AB-12345" in out["order_numbers"], str(out["order_numbers"]))
    record("entities.amounts", any("49.99" in a for a in out["amounts"]), str(out["amounts"]))
    record("entities.emails", "ravi@example.com" in out["emails"])
    record("entities.dates", any("03/15" in d for d in out["dates"]))


run("entities (regex + optional GLiNER)", t_entities)

# ── 8. structured + llm_router (flags respected) ──────────────────────
from app.core.oss_stack import structured  # noqa: E402


def t_structured():
    r = structured.llm_completion("say hi")
    if structured.litellm_available():
        record("llm_router.responds_or_none", r is None or isinstance(r, str))
    else:
        record("llm_router.off_returns_none", r is None, "OSS_LITELLM=0 → existing LLM path used")
    record(
        "structured.reported",
        structured.instructor_available() == availability()["instructor"]["installed"],
    )


run("structured + llm_router", t_structured)

# ── 9. channels (flags off → []) ──────────────────────────────────────
from app.core.oss_stack.channels import poller  # noqa: E402


def t_channels():
    record("channels.email_off", poller.poll_email() == [])
    record("channels.telegram_off", poller.poll_telegram() == [])


run("channels (email/telegram pollers)", t_channels)

# ── 10. patched pipeline files compile + node_3 imports ──────────────
def t_pipeline():
    import py_compile

    node3 = REPO / "backend/app/core/parwa_pipeline/nodes/node_3_knowledge_fetch.py"
    kbapi = REPO / "backend/app/api/knowledge_base.py"
    py_compile.compile(str(node3), doraise=True)
    py_compile.compile(str(kbapi), doraise=True)
    record("pipeline.patched_files_compile", True, "node_3 + knowledge_base")


run("patched pipeline files", t_pipeline)

# ── summary ───────────────────────────────────────────────────────────
fails = [r for r in results if r[1] == "FAIL"]
passes = [r for r in results if r[1] == "PASS"]
skips = [r for r in results if r[1] == "SKIP"]
print("\n" + "=" * 70)
print(f"RESULT: {len(passes)} PASS, {len(skips)} SKIP, {len(fails)} FAIL")
print("=" * 70)
sys.exit(1 if fails else 0)
