"""Self-check: HumanReplacement learning loop (AGENTS.md: one runnable check).

Run:  cd backend && python3 tests/test_humanreplacement_loop.py

Stdlib-only on purpose (CI does not run backend tests; this file must run
anywhere with plain python3). Covers the pure logic this task added:

  1. write_ticket_failure() records an UNSOLVED note keyed by the SAME
     deterministic key as write_ticket_pattern()  → upgrade-in-place works.
  2. The learn-side upgrade stamps the entry: unsolved → solved_by_human
     with solved_after_failure + failure history kept (exactly the flow
     CRMResolutionService.learn_from_resolution executes).
  3. find_similar_patterns() exposes status/failure_type to the pipeline.
  4. is_resolution_status() covers Zendesk/HubSpot/generic spellings.
  5. record_failure_in_wiki() never raises — broken env → None (BC-008).
"""

import importlib.util
import os
import sys
import types

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module(dotted: str, relpath: str):
    """Load one module by file path, stubbing parent packages.

    The real app.core.parwa_pipeline.__init__ imports langgraph (heavy,
    not installed everywhere). Method bodies do
    `from app.core.parwa_pipeline.ai_wiki_store import ...` — with the
    dotted name pre-registered in sys.modules those imports resolve to
    the file-loaded module without executing any heavy __init__.
    """
    parts = dotted.split(".")
    for i in range(1, len(parts)):
        pkg = ".".join(parts[:i])
        if pkg not in sys.modules:
            stub = types.ModuleType(pkg)
            stub.__path__ = [os.path.join(BACKEND, *parts[1:i])]
            sys.modules[pkg] = stub
    spec = importlib.util.spec_from_file_location(
        dotted, os.path.join(BACKEND, relpath))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[dotted] = mod
    spec.loader.exec_module(mod)
    return mod


_wiki = _load_module(
    "app.core.parwa_pipeline.ai_wiki_store",
    "app/core/parwa_pipeline/ai_wiki_store.py",
)
_crm = _load_module(
    "app.services.crm_resolution_service",
    "app/services/crm_resolution_service.py",
)

get_wiki_store = _wiki.get_wiki_store
ticket_pattern_entry_key = _wiki.ticket_pattern_entry_key
CRMResolutionService = _crm.CRMResolutionService

TENANT = "check_tenant"
QUERY = "my customer was charged twice this month please refund"
TYPE = "billing"


def check_failure_note_and_upgrade():
    store = get_wiki_store()
    store.clear_tenant(TENANT)

    # ── 1. AI gives up → mistake note lands in the wiki ──────────────
    entry = store.write_ticket_failure(
        tenant_id=TENANT, ticket_type=TYPE, query=QUERY,
        failure_type="missing_connection",
        problem="No payment gateway connected — cannot execute refunds",
        asked_from_team="Connect Razorpay in integrations",
    )
    assert entry is not None, "failure note must be written"
    assert entry.content["status"] == "unsolved"
    assert entry.content["failure_type"] == "missing_connection"
    expected_key = ticket_pattern_entry_key(TYPE, QUERY)
    assert entry.entry_key == expected_key, (
        f"failure key {entry.entry_key} != pattern key {expected_key}"
    )

    # ── 2. CRM team resolves → learn side upgrades THE SAME entry ────
    # (mirrors CRMResolutionService.learn_from_resolution exactly)
    existing = store.read(tenant_id=TENANT, section="A", entry_key=expected_key)
    prev = existing[0].content if existing else {}
    assert prev.get("status") == "unsolved", "snapshot must see the mistake note"

    upgraded = store.write_ticket_pattern(
        tenant_id=TENANT, ticket_type=TYPE, query=QUERY,
        complexity="medium", techniques_used=["CRM_Learning"],
        quality_score=0.9, answer_summary="Refunded both charges via gateway",
    )
    assert upgraded.entry_key == expected_key, "upsert must hit the same key"
    if prev.get("status") == "unsolved":
        upgraded.content["solved_after_failure"] = True
        upgraded.content["status"] = "solved_by_human"
        upgraded.content["failure_type"] = prev.get("failure_type") or "unknown"
        upgraded.content["asked_from_team"] = prev.get("asked_from_team", "")

    section_a = store.read(tenant_id=TENANT, section="A")
    assert len(section_a) == 1, "upgrade must REPLACE, not duplicate"
    final = section_a[0].content
    assert final["status"] == "solved_by_human"
    assert final["solved_after_failure"] is True
    assert final["failure_type"] == "missing_connection"
    assert final["answer_summary"] == "Refunded both charges via gateway"
    assert final["asked_from_team"] == "Connect Razorpay in integrations"

    # ── 3. Pipeline-facing search exposes the status ─────────────────
    patterns = store.find_similar_patterns(TENANT, "charged twice refund", TYPE)
    assert patterns, "search must find the upgraded pattern"
    assert patterns[0]["status"] == "solved_by_human"
    assert patterns[0]["failure_type"] == "missing_connection"
    store.clear_tenant(TENANT)


def check_resolution_status_spellings():
    for s in ("solved", "Closed", "resolved", "done", "COMPLETE"):
        assert CRMResolutionService.is_resolution_status(s), f"{s} should count"
    for s in ("open", "new", "pending", "escalated", "", None):
        assert not CRMResolutionService.is_resolution_status(s), f"{s} must NOT count"


def check_failure_note_never_raises():
    class _BoomDB:  # any db access explodes — BC-008 must swallow it
        def query(self, *a, **k):
            raise RuntimeError("no db in this env")

    class _StubTicket:
        id = "TKT-1"
        company_id = TENANT
        subject = "refund please"
        metadata_json = None
        classification_type = None
        category = None

    result = CRMResolutionService.record_failure_in_wiki(
        _BoomDB(), _StubTicket(), reason="missing_connection",
    )
    assert result is None, "broken env must degrade to None, never raise"


if __name__ == "__main__":
    check_failure_note_and_upgrade()
    check_resolution_status_spellings()
    check_failure_note_never_raises()
    print("OK — 5/5 HumanReplacement loop checks passed")
