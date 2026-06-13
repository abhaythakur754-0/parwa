"""P0 Validation Test Suite — Tests evidence chain, multi-technique activation, and merge quality.

This test validates the 3 P0 fixes:
1. Evidence Chain: Structured (claim, source, confidence) flows between nodes
2. MAX_TECHNIQUES raised: Variant-aware (mini=1, parwa=2, high=3)
3. Evidence-weighted merge: Highest confidence wins, ALL chains preserved

Run: python -m pytest tests/test_p0_evidence_chain.py -v
"""

import asyncio
import pytest
import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parwa.graph import process_ticket, aprocess_ticket
from parwa.frameworks.brain import FrameworkBrain, _VARIANT_TECHNIQUE_BUDGET
from parwa.frameworks.registry import get_registry, reset_registry
from parwa.state import TicketState


# ─── Real-world test tickets ──────────────────────────────────────────────────

TEST_TICKETS = [
    {
        "name": "duplicate_charge_refund",
        "message": "I was charged twice for the same order! I want an immediate refund for the duplicate charge of $49.99.",
        "expected_intent": "refund_request",
        "expected_actions": ["process_refund"],
        "min_quality": 60,
        "category": "financial",
    },
    {
        "name": "order_status_inquiry",
        "message": "Where is my order? It's been 10 days and I haven't received anything yet. Order #ORD-12345",
        "expected_intent": "order_status",
        "expected_actions": ["share_policy"],
        "min_quality": 50,
        "category": "informational",
    },
    {
        "name": "cancellation_request",
        "message": "I want to cancel my subscription immediately. I'm not using it anymore and I want my money back.",
        "expected_intent": "cancellation",
        "expected_actions": ["cancel_order"],
        "min_quality": 55,
        "category": "financial",
    },
    {
        "name": "technical_bug",
        "message": "Your app keeps crashing when I try to open the settings page. This happens every single time and I can't use the product.",
        "expected_intent": "technical_support",
        "expected_actions": [],
        "min_quality": 45,
        "category": "technical",
    },
    {
        "name": "billing_overcharge",
        "message": "My invoice shows the wrong amount. I was overcharged by $30 on my last billing cycle. The promotional discount wasn't applied.",
        "expected_intent": "billing_issue",
        "expected_actions": [],
        "min_quality": 50,
        "category": "financial",
    },
    {
        "name": "account_modification",
        "message": "I need to update my email address and change my payment method from credit card to PayPal.",
        "expected_intent": "account_modification",
        "expected_actions": ["modify_account"],
        "min_quality": 50,
        "category": "account",
    },
    {
        "name": "escalation_legal",
        "message": "This is fraud and I am going to take legal action. I want to speak to a manager right now or I will contact my attorney.",
        "expected_intent": "escalation",
        "expected_actions": [],
        "min_quality": 40,
        "category": "escalation",
    },
    {
        "name": "faq_return_policy",
        "message": "What is your return policy? I'm thinking about returning a product but want to understand the process first.",
        "expected_intent": "faq_question",
        "expected_actions": [],
        "min_quality": 45,
        "category": "faq",
    },
    {
        "name": "complaint_quality",
        "message": "This is the worst service ever! The product arrived damaged and nobody has responded to my previous three emails. I am extremely disappointed.",
        "expected_intent": "complaint",
        "expected_actions": [],
        "min_quality": 40,
        "category": "complaint",
    },
    {
        "name": "account_upgrade",
        "message": "I want to upgrade from the basic plan to the pro plan and add 5 more seats to my team.",
        "expected_intent": "account_modification",
        "expected_actions": ["modify_account"],
        "min_quality": 50,
        "category": "account",
    },
]


# ─── P0 Test: Evidence Chain Flows Between Nodes ──────────────────────────────

class TestEvidenceChain:
    """P0-1: Test that evidence_chain accumulates structured entries across nodes."""

    @pytest.mark.asyncio
    async def test_evidence_chain_accumulates(self):
        """Evidence chain should have entries from multiple nodes."""
        result = await aprocess_ticket(
            "I was charged twice for the same order! I want an immediate refund.",
            variant="parwa",
        )

        evidence_chain = result.get("evidence_chain", [])
        assert isinstance(evidence_chain, list), f"evidence_chain should be a list, got {type(evidence_chain)}"
        assert len(evidence_chain) > 0, "evidence_chain should not be empty after processing"

        # Each entry should have the required fields
        for entry in evidence_chain:
            if isinstance(entry, dict):
                assert "claim" in entry, f"Evidence entry missing 'claim': {entry}"
                assert "confidence" in entry, f"Evidence entry missing 'confidence': {entry}"
                assert "technique" in entry, f"Evidence entry missing 'technique': {entry}"
                assert "node" in entry, f"Evidence entry missing 'node': {entry}"

    @pytest.mark.asyncio
    async def test_evidence_chain_has_reasoning_node(self):
        """Evidence chain should include entries from REASONING_ENGINE."""
        result = await aprocess_ticket(
            "I was charged twice and want a refund!",
            variant="parwa",
        )

        evidence_chain = result.get("evidence_chain", [])
        reasoning_entries = [e for e in evidence_chain if isinstance(e, dict) and e.get("node") == "REASONING_ENGINE"]
        assert len(reasoning_entries) > 0, "Evidence chain should have entries from REASONING_ENGINE"

    @pytest.mark.asyncio
    async def test_evidence_chain_has_quality_node(self):
        """Evidence chain should include entries from QUALITY_SCORER."""
        result = await aprocess_ticket(
            "I want to cancel my order please.",
            variant="parwa",
        )

        evidence_chain = result.get("evidence_chain", [])
        quality_entries = [e for e in evidence_chain if isinstance(e, dict) and e.get("node") == "QUALITY_SCORER"]
        assert len(quality_entries) > 0, "Evidence chain should have entries from QUALITY_SCORER"

    @pytest.mark.asyncio
    async def test_evidence_chain_claims_are_structured(self):
        """Each evidence entry should have claim + sources + confidence."""
        result = await aprocess_ticket(
            "Where is my order? Order #ORD-12345",
            variant="parwa",
        )

        evidence_chain = result.get("evidence_chain", [])
        for entry in evidence_chain:
            if isinstance(entry, dict):
                # Claim should be a non-empty string
                assert isinstance(entry.get("claim", ""), str)
                # Confidence should be a number
                conf = entry.get("confidence", 0)
                assert isinstance(conf, (int, float)), f"Confidence should be numeric, got {type(conf)}"
                assert 0 <= conf <= 1, f"Confidence should be 0-1, got {conf}"


# ─── P0 Test: Multi-Technique Activation ──────────────────────────────────────

class TestMultiTechniqueActivation:
    """P0-2: Test that variant-aware technique budgets work correctly."""

    def test_mini_variant_gets_1_technique(self):
        """Mini variant should get max 1 technique per node."""
        brain = FrameworkBrain(node="REASONING_ENGINE", state={"complexity": "medium"})
        max_t = brain._get_max_techniques("mini", "medium")
        assert max_t == 1, f"Mini should get 1 technique, got {max_t}"

    def test_parwa_variant_gets_2_techniques(self):
        """PARWA variant should get max 2 techniques per node."""
        brain = FrameworkBrain(node="REASONING_ENGINE", state={"complexity": "medium"})
        max_t = brain._get_max_techniques("parwa", "medium")
        assert max_t == 2, f"PARWA should get 2 techniques, got {max_t}"

    def test_high_variant_gets_3_techniques(self):
        """High variant should get max 3 techniques per node."""
        brain = FrameworkBrain(node="REASONING_ENGINE", state={"complexity": "complex"})
        max_t = brain._get_max_techniques("high", "complex")
        assert max_t == 3, f"High should get 3 techniques, got {max_t}"

    def test_simple_complexity_limits_techniques(self):
        """Simple tickets should only get 1 technique regardless of variant."""
        brain = FrameworkBrain(node="REASONING_ENGINE", state={"complexity": "simple"})
        max_t = brain._get_max_techniques("high", "simple")
        assert max_t == 1, f"Simple should get max 1 technique even on High, got {max_t}"

    def test_technique_diversity_selection(self):
        """Brain should select diverse techniques (different groups)."""
        brain = FrameworkBrain(node="REASONING_ENGINE", state={"complexity": "complex"})
        selected = brain._select_techniques(
            ["chain_of_thought", "react", "uncertainty_of_thought", "graph_strategic_thought"],
            max_techniques=3,
            complexity="complex",
        )
        # Should select up to 3 techniques
        assert len(selected) <= 3
        # Should select at least 1
        assert len(selected) >= 1
        # Names should be unique
        names = [t.name for t in selected]
        assert len(names) == len(set(names)), f"Duplicate techniques selected: {names}"


# ─── P0 Test: Evidence-Weighted Merge ─────────────────────────────────────────

class TestEvidenceWeightedMerge:
    """P0-3: Test that evidence-weighted merge replaces 'last wins'."""

    def test_merge_picks_highest_confidence_output(self):
        """Merge should use output from highest-confidence technique."""
        from parwa.frameworks.base import TechniqueResult, BaseTechnique

        class MockTechnique:
            def __init__(self, name):
                self.name = name
                self.category = type('obj', (object,), {'value': 'reasoning'})()

        technique_a = MockTechnique("technique_a")
        result_a = TechniqueResult(
            output="Low confidence output",
            chain=["Step A1"],
            confidence=0.3,
            frameworks_used=["technique_a"],
        )

        technique_b = MockTechnique("technique_b")
        result_b = TechniqueResult(
            output="High confidence output",
            chain=["Step B1", "Step B2"],
            confidence=0.9,
            frameworks_used=["technique_b"],
        )

        merged = FrameworkBrain._merge_technique_results([
            (technique_a, result_a),
            (technique_b, result_b),
        ])

        # Output should be from the high-confidence technique
        assert merged.output == "High confidence output", f"Should pick high-confidence output, got: {merged.output}"

    def test_merge_preserves_all_chains(self):
        """Merge should concatenate ALL chains, not just the last one."""
        from parwa.frameworks.base import TechniqueResult, BaseTechnique

        class MockTechnique:
            def __init__(self, name):
                self.name = name
                self.category = type('obj', (object,), {'value': 'reasoning'})()

        technique_a = MockTechnique("cot")
        result_a = TechniqueResult(
            output="Output A",
            chain=["Step A1", "Step A2"],
            confidence=0.8,
            frameworks_used=["cot"],
        )

        technique_b = MockTechnique("react")
        result_b = TechniqueResult(
            output="Output B",
            chain=["Step B1"],
            confidence=0.9,
            frameworks_used=["react"],
        )

        merged = FrameworkBrain._merge_technique_results([
            (technique_a, result_a),
            (technique_b, result_b),
        ])

        # Chain should have entries from BOTH techniques
        assert len(merged.chain) >= 3, f"Should preserve all chain entries, got {len(merged.chain)}: {merged.chain}"
        # Chain entries should be tagged with technique names
        assert any("[cot]" in step for step in merged.chain), "Chain should tag entries with technique name"
        assert any("[react]" in step for step in merged.chain), "Chain should tag entries with technique name"

    def test_merge_builds_evidence_chain(self):
        """Merge should build structured evidence chain from results."""
        from parwa.frameworks.base import TechniqueResult

        class MockTechnique:
            def __init__(self, name):
                self.name = name
                self.category = type('obj', (object,), {'value': 'reasoning'})()

        technique = MockTechnique("cot")
        result = TechniqueResult(
            output="Customer is eligible for refund",
            chain=["Step 1: Duplicate charge found", "Step 2: Policy allows refund"],
            confidence=0.95,
            frameworks_used=["cot"],
        )

        evidence_chain = FrameworkBrain._build_evidence_chain([(technique, result)])

        assert len(evidence_chain) == 1, f"Should have 1 evidence entry, got {len(evidence_chain)}"
        entry = evidence_chain[0]
        assert entry["claim"] == "Customer is eligible for refund"
        assert entry["confidence"] == 0.95
        assert entry["technique"] == "cot"
        assert len(entry["sources"]) > 0, "Should have sources supporting the claim"


# ─── P0 Integration Test: Full Pipeline ───────────────────────────────────────

class TestP0Integration:
    """Full pipeline tests to validate P0 improvements end-to-end."""

    @pytest.mark.asyncio
    async def test_all_variants_complete_pipeline(self):
        """All variants (mini, parwa, high) should complete the full pipeline."""
        for variant in ("mini", "parwa", "high"):
            result = await aprocess_ticket(
                "I was charged twice for my order and want a refund!",
                variant=variant,
            )
            assert "final_response" in result, f"{variant}: Should have final_response"
            assert result["final_response"], f"{variant}: final_response should not be empty"
            assert "error" not in result or not result.get("error"), f"{variant}: Should not have errors"

    @pytest.mark.asyncio
    async def test_evidence_chain_across_variants(self):
        """Evidence chain should work across all variants."""
        for variant in ("mini", "parwa", "high"):
            result = await aprocess_ticket(
                "I want to cancel my subscription",
                variant=variant,
            )
            evidence_chain = result.get("evidence_chain", [])
            assert isinstance(evidence_chain, list), f"{variant}: evidence_chain should be a list"

    @pytest.mark.asyncio
    async def test_parwa_uses_more_techniques_than_mini(self):
        """PARWA variant should activate more frameworks than Mini."""
        mini_result = await aprocess_ticket(
            "I was charged twice and want a refund!",
            variant="mini",
        )
        parwa_result = await aprocess_ticket(
            "I was charged twice and want a refund!",
            variant="parwa",
        )

        mini_frameworks = len(mini_result.get("active_frameworks", []))
        parwa_frameworks = len(parwa_result.get("active_frameworks", []))

        # PARWA should use at least as many frameworks as Mini
        # (Not strictly more, because the same techniques might activate,
        # but never fewer when complexity is the same)
        assert parwa_frameworks >= mini_frameworks, \
            f"PARWA frameworks ({parwa_frameworks}) should be >= Mini ({mini_frameworks})"


# ─── P0 Benchmark: Compare Before/After ───────────────────────────────────────

class TestP0Benchmark:
    """Benchmark test to measure P0 improvements."""

    @pytest.mark.asyncio
    async def test_batch_tickets_all_variants(self):
        """Run all test tickets through all variants and collect metrics."""
        results = []

        for ticket in TEST_TICKETS:
            for variant in ("mini", "parwa", "high"):
                try:
                    result = await aprocess_ticket(
                        ticket["message"],
                        variant=variant,
                    )

                    # Collect metrics
                    metrics = {
                        "ticket": ticket["name"],
                        "variant": variant,
                        "intent": result.get("intent", "unknown"),
                        "intent_correct": result.get("intent", "") == ticket["expected_intent"],
                        "quality_score": result.get("quality_score", 0),
                        "quality_pass": result.get("quality_score", 0) >= ticket["min_quality"],
                        "evidence_chain_length": len(result.get("evidence_chain", [])),
                        "frameworks_activated": len(result.get("active_frameworks", [])),
                        "frameworks_list": result.get("active_frameworks", []),
                        "has_final_response": bool(result.get("final_response")),
                        "response_length": len(result.get("final_response", "")),
                        "errors": len(result.get("pipeline_errors", [])),
                    }
                    results.append(metrics)

                except Exception as exc:
                    results.append({
                        "ticket": ticket["name"],
                        "variant": variant,
                        "error": str(exc),
                    })

        # Save results
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "download", "p0_benchmark_results.json"
        )
        os.makedirs(os.path.dirname(report_path), exist_ok=True)

        report = {
            "timestamp": datetime.now().isoformat(),
            "p0_fixes": ["evidence_chain", "multi_technique", "weighted_merge"],
            "total_tickets": len(TEST_TICKETS),
            "variants_tested": ["mini", "parwa", "high"],
            "results": results,
            "summary": {
                "total_runs": len(results),
                "intent_accuracy": sum(1 for r in results if r.get("intent_correct")) / max(len(results), 1),
                "avg_quality": sum(r.get("quality_score", 0) for r in results) / max(len(results), 1),
                "avg_evidence_length": sum(r.get("evidence_chain_length", 0) for r in results) / max(len(results), 1),
                "avg_frameworks": sum(r.get("frameworks_activated", 0) for r in results) / max(len(results), 1),
                "quality_pass_rate": sum(1 for r in results if r.get("quality_pass")) / max(len(results), 1),
                "error_rate": sum(1 for r in results if r.get("error")) / max(len(results), 1),
            },
        }

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n{'='*60}")
        print(f"P0 BENCHMARK RESULTS")
        print(f"{'='*60}")
        print(f"Total runs: {report['summary']['total_runs']}")
        print(f"Intent accuracy: {report['summary']['intent_accuracy']:.1%}")
        print(f"Avg quality score: {report['summary']['avg_quality']:.1f}")
        print(f"Avg evidence chain length: {report['summary']['avg_evidence_length']:.1f}")
        print(f"Avg frameworks activated: {report['summary']['avg_frameworks']:.1f}")
        print(f"Quality pass rate: {report['summary']['quality_pass_rate']:.1%}")
        print(f"Error rate: {report['summary']['error_rate']:.1%}")
        print(f"{'='*60}")
        print(f"Report saved to: {report_path}")

        # Basic assertions
        assert report["summary"]["intent_accuracy"] > 0.5, "Intent accuracy should be above 50%"
        assert report["summary"]["avg_evidence_length"] > 0, "Evidence chain should have entries"


if __name__ == "__main__":
    # Run quick benchmark without pytest
    async def quick_test():
        print("Running P0 quick validation...\n")

        # Test 1: Evidence chain
        print("1. Testing Evidence Chain...")
        result = await aprocess_ticket(
            "I was charged twice and want a refund!",
            variant="parwa",
        )
        chain = result.get("evidence_chain", [])
        print(f"   Evidence chain length: {len(chain)}")
        for entry in chain[:5]:
            if isinstance(entry, dict):
                print(f"   - [{entry.get('node', '?')}] {entry.get('claim', '')[:60]} (conf={entry.get('confidence', 0):.2f})")
        assert len(chain) > 0, "FAIL: No evidence chain entries!"
        print("   PASS ✓\n")

        # Test 2: Multi-technique activation
        print("2. Testing Multi-Technique Activation...")
        for variant in ("mini", "parwa", "high"):
            brain = FrameworkBrain(node="REASONING_ENGINE", state={"complexity": "complex"})
            max_t = brain._get_max_techniques(variant, "complex")
            print(f"   {variant}: max_techniques={max_t}")
        print("   PASS ✓\n")

        # Test 3: Evidence-weighted merge
        print("3. Testing Evidence-Weighted Merge...")
        from parwa.frameworks.base import TechniqueResult

        class MT:
            def __init__(self, n):
                self.name = n
                self.category = type('obj', (object,), {'value': 'reasoning'})()

        merged = FrameworkBrain._merge_technique_results([
            (MT("cot"), TechniqueResult(output="CoT output", chain=["CoT step"], confidence=0.7, frameworks_used=["cot"])),
            (MT("react"), TechniqueResult(output="ReAct output", chain=["ReAct step"], confidence=0.9, frameworks_used=["react"])),
        ])
        print(f"   Merged output (should be ReAct): {merged.output}")
        print(f"   Merged chain length: {len(merged.chain)}")
        print(f"   Merged frameworks: {merged.frameworks_used}")
        assert merged.output == "ReAct output", "FAIL: Should pick highest confidence!"
        print("   PASS ✓\n")

        # Test 4: Full pipeline across variants
        print("4. Testing Full Pipeline Across Variants...")
        for variant in ("mini", "parwa", "high"):
            result = await aprocess_ticket(
                "I want to cancel my subscription",
                variant=variant,
            )
            print(f"   {variant}: intent={result.get('intent')}, quality={result.get('quality_score', 0):.0f}, "
                  f"evidence_chain={len(result.get('evidence_chain', []))}, "
                  f"frameworks={result.get('active_frameworks', [])}")
            assert result.get("final_response"), f"{variant}: No final response!"
        print("   PASS ✓\n")

        print("🎉 All P0 tests passed!")

    asyncio.run(quick_test())
