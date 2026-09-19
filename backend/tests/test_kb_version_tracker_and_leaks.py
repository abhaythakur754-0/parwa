"""
KB version tracker + leak stripper — tests for the 2026-09-19 live bugs.

Live manual test (ticket TKT-BD11B5C1, 2-chunk KB doc with "SUPPORT
HOURS 24/7"): Node 3 retrieved BOTH chunks ("RAG: 2 docs"), then
VersionTracker.Remove deleted BOTH ("removed 2 superseded docs") and
the AI answered with ZERO knowledge. Root cause: every chunk of
"tenant_kb:<doc-uuid>" shares the SAME source string, so chunk 2 was
treated as a newer "version" superseding chunk 1 — and removal by
source string wiped the whole document.

Same live ticket leaked workflow chatter to the customer: the reply
opened with "Here's the **slightly refined** version of your response…"
and closed with "**QUALITY: 10/10**".

Run: cd backend && ../venv/bin/python -m pytest tests/test_kb_version_tracker_and_leaks.py -v
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

# ── Pre-import: Stub out langgraph (same pattern as test_parwa_v2_unit) ──
if "langgraph" not in sys.modules:
    sys.modules["langgraph"] = MagicMock()
    sys.modules["langgraph.graph"] = MagicMock()
    sys.modules["langgraph.graph"].END = "__end__"
    sys.modules["langgraph.graph"].StateGraph = MagicMock

from app.core.email_utils import strip_meta_headers  # noqa: E402
from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import (  # noqa: E402
    _version_tracker,
)


def _remove_superseded(documents):
    """Mirror of the node_3 removal step (source-string based)."""
    vt = _version_tracker(documents)
    return (
        [d for d in documents if d.get("source", "") not in vt["superseded"]],
        vt,
    )


# ── 1. VersionTracker: chunks of one document must survive ──────────


def test_two_chunks_same_source_never_supersede():
    """THE regression: both chunks of one tenant doc share one source."""
    docs = [
        {"content": "SUPPORT HOURS 24/7 …", "source": "tenant_kb:2b210105-7774"},
        {"content": "PASSWORD RESET …", "source": "tenant_kb:2b210105-7774"},
    ]
    kept, vt = _remove_superseded(docs)
    assert len(kept) == 2, "chunks of one document are siblings, not versions"
    assert vt["superseded"] == []
    assert vt["has_superseded"] is False


def test_multiple_distinct_tenant_docs_all_survive():
    """Several KB articles (different uuids, no _v suffix) — all kept."""
    docs = [
        {"content": "a", "source": "tenant_kb:doc-aaa"},
        {"content": "b", "source": "tenant_kb:doc-bbb"},
        {"content": "c", "source": "tenant_kb:doc-ccc"},
    ]
    kept, vt = _remove_superseded(docs)
    assert len(kept) == 3
    assert vt["superseded"] == []


def test_explicit_v2_supersedes_v1_and_v2_chunks_survive():
    """Real versioning still works: policy_v2 wins, policy_v1 goes —
    and ALL chunks of the winning version survive."""
    docs = [
        {"content": "hours v1", "source": "policy_v1"},
        {"content": "hours v2 part 1", "source": "policy_v2"},
        {"content": "hours v2 part 2", "source": "policy_v2"},
    ]
    kept, vt = _remove_superseded(docs)
    sources = {d["source"] for d in kept}
    assert sources == {"policy_v2"}, "old version removed, new version fully kept"
    assert len(kept) == 2
    assert vt["superseded"] == ["policy_v1"]
    assert vt["active_versions"]["policy"] == "policy_v2"


def test_mixed_chunks_and_versions():
    """v1 (1 chunk) + v2 (2 chunks) + unrelated doc → only v1 source dies."""
    docs = [
        {"content": "old", "source": "kb:doc-old_v1"},
        {"content": "new1", "source": "kb:doc-old_v2"},
        {"content": "new2", "source": "kb:doc-old_v2"},
        {"content": "other", "source": "kb:doc-other"},
    ]
    kept, vt = _remove_superseded(docs)
    assert {d["source"] for d in kept} == {"kb:doc-old_v2", "kb:doc-other"}
    assert vt["superseded"] == ["kb:doc-old_v1"]


# ── 2. strip_meta_headers: the 2026-09-19 leak variants ─────────────


LIVE_LEAK = """Here’s the **slightly refined** version of your response while preserving its strength—minor tweaks for clarity, warmth, and proactive guidance:

---
**Hello [Customer's Name],**

Thank you for reaching out about the issue you experienced on **Sunday night**.

**Next Steps for Resolution**
To help you promptly, please share the exact error message.

Best regards,
**Customer Support Team**
---

---
**QUALITY: 10/10**"""


def test_live_refined_preamble_and_quality_tail_stripped():
    cleaned = strip_meta_headers(LIVE_LEAK)
    assert "slightly refined" not in cleaned.lower()
    assert "quality: 10/10" not in cleaned.lower()
    assert "here’s the" not in cleaned.lower()
    # the real reply body must survive untouched
    assert "Hello [Customer's Name]," in cleaned
    assert "Best regards," in cleaned
    assert "please share the exact error message" in cleaned
    assert cleaned.startswith("**Hello") or cleaned.startswith("Hello")


def test_plain_reply_untouched():
    reply = "Hi Alex!\n\nOur support team is available 24 hours a day, 7 days a week.\n\nBest regards,\nSupport"
    assert strip_meta_headers(reply) == reply


def test_old_improved_response_header_still_stripped():
    text = "**IMPROVED RESPONSE:**\nThank you for contacting us."
    assert strip_meta_headers(text) == "Thank you for contacting us."


def test_quality_tail_alone_removed():
    text = "Your refund was processed.\n\n**QUALITY: 9/10**"
    assert strip_meta_headers(text) == "Your refund was processed."


def test_quality_score_variant_removed():
    text = "We are available 24/7.\nQUALITY SCORE: 10/10"
    assert strip_meta_headers(text) == "We are available 24/7."


def test_genuine_content_mentioning_quality_is_kept():
    """A real sentence with 'quality' that is NOT a self-rating tail
    must survive — the stripper only kills score-style tail lines."""
    text = "We care about quality of service.\n\nBest regards,\nSupport"
    assert strip_meta_headers(text) == text


# ── 3. Small-KB coverage top-up (BM25 blind spot) ───────────────────


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *_a, **_k):
        return _FakeResult(self._rows)

    def close(self):
        pass


def _patch_db_raises(monkeypatch, boom):
    import sys
    import types
    fake_module = types.ModuleType("database.base")
    fake_module.SessionLocal = boom
    monkeypatch.setitem(sys.modules, "database.base", fake_module)


def _patch_db(monkeypatch, rows):
    import sys
    import types
    fake_module = types.ModuleType("database.base")
    fake_module.SessionLocal = lambda: _FakeDB(rows)
    monkeypatch.setitem(sys.modules, "database.base", fake_module)


def test_topup_adds_chunk_bm25_missed(monkeypatch):
    """THE live bug: BM25 matched only the refund chunk (via 'questions');
    the hours chunk scored 0 and was dropped. Top-up must restore it."""
    from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import (
        _ensure_small_kb_coverage,
    )

    refund_chunk = ("# SpeedTest Co Support Policies PASSWORD RESET ... REFUND POLICY ...",
                    "eb0009cf-f73d-4fac")
    hours_chunk = ("SUPPORT HOURS Our support team is available 24 hours a day, 7 days a week.",
                   "3b55946f-0038-4c3e")
    _patch_db(monkeypatch, [refund_chunk, hours_chunk])

    result = [{"content": refund_chunk[0], "source": f"tenant_kb:{refund_chunk[1]}", "section": "C"}]
    topped = _ensure_small_kb_coverage(result, "tenant_1")

    assert len(topped) == 2
    assert topped[1]["source"] == f"tenant_kb:{hours_chunk[1]}"
    assert "24 hours a day" in topped[1]["content"]


def test_topup_skips_when_already_at_target(monkeypatch):
    from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import (
        _ensure_small_kb_coverage,
    )

    def _boom():
        raise AssertionError("DB must not be touched when result is at target")

    _patch_db_raises(monkeypatch, _boom)
    result = [{"content": f"doc {i}", "source": f"tenant_kb:d{i}"} for i in range(5)]
    assert _ensure_small_kb_coverage(result, "tenant_1") == result


def test_topup_survives_db_error(monkeypatch):
    from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import (
        _ensure_small_kb_coverage,
    )

    def _boom():
        raise RuntimeError("db down")

    _patch_db_raises(monkeypatch, _boom)
    result = [{"content": "matched chunk", "source": "tenant_kb:d1"}]
    assert _ensure_small_kb_coverage(result, "tenant_1") == result


def test_topup_no_tenant_id(monkeypatch):
    from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import (
        _ensure_small_kb_coverage,
    )

    def _boom():
        raise AssertionError("DB must not be touched without tenant_id")

    _patch_db_raises(monkeypatch, _boom)
    result = [{"content": "x", "source": "s"}]
    assert _ensure_small_kb_coverage(result, "") == result


def test_topup_dedupes_by_content(monkeypatch):
    from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import (
        _ensure_small_kb_coverage,
    )

    same = "SUPPORT HOURS available 24/7"
    _patch_db(monkeypatch, [(same, "doc-1"), (same, "doc-1")])
    result = [{"content": same, "source": "tenant_kb:doc-1"}]
    assert len(_ensure_small_kb_coverage(result, "tenant_1")) == 1
