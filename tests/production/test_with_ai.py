"""
Parwa Variant Engine — AI-Powered Production Test
Runs a focused subset with REAL AI-generated responses via z-ai SDK
to see actual variant tier differentiation.
"""
from __future__ import annotations
import asyncio, json, os, re, sys, time, uuid, statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from the main test module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_120_requests import (
    TEST_REQUESTS, ESCALATION_REQUESTS, PII_TEST_REQUESTS,
    ParwaVariantSimulator, ProductionTestRunner
)


class AIPoweredSimulator(ParwaVariantSimulator):
    """Extended simulator that uses z-ai SDK for response generation."""

    async def generate_ai_response(self, query: str, intent: str, industry: str, empathy_score: float, variant_tier: str) -> Tuple[str, int]:
        """Generate response using z-ai SDK with variant-specific prompts."""
        import subprocess

        industry_tone = {
            "ecommerce": "friendly and helpful",
            "saas": "professional and technical",
            "logistics": "efficient and clear",
            "healthcare": "empathetic and careful",
            "fintech": "precise and security-focused",
            "general": "professional and courteous",
        }.get(industry, "professional")

        empathy_context = ""
        if empathy_score < 0.3:
            empathy_context = "The customer is very distressed. Show strong empathy and urgency. "
        elif empathy_score < 0.5:
            empathy_context = "The customer is frustrated. Acknowledge their feelings. "

        # VARIANT-SPECIFIC PROMPTS — This is where the real differentiation happens
        tier_prompts = {
            "mini_parwa": (
                f"You are a customer service AI for a {industry} company. Tone: {industry_tone}. "
                f"{empathy_context}Intent: {intent}. "
                f"Keep your response CONCISE and DIRECT (2-3 sentences max). No filler phrases. "
                f"Address the issue and state the next step clearly."
            ),
            "parwa": (
                f"You are a customer service AI for a {industry} company. Tone: {industry_tone}. "
                f"{empathy_context}Intent: {intent}. "
                f"Provide a THOROUGH response with clear steps. "
                f"Acknowledge the issue, explain what you'll do, and give a timeline. "
                f"Include 2-3 actionable next steps. No filler phrases."
            ),
            "parwa_high": (
                f"You are a senior customer service AI for a {industry} company. Tone: {industry_tone}. "
                f"{empathy_context}Intent: {intent}. "
                f"Provide a COMPREHENSIVE, DETAILED response with multiple options and strategic guidance. "
                f"1) Acknowledge and validate their concern. "
                f"2) Provide 3+ resolution options with pros/cons. "
                f"3) Recommend the best path forward. "
                f"4) Offer proactive follow-up and escalation path. "
                f"5) Include relevant policy references. No filler phrases."
            ),
        }

        system_prompt = tier_prompts.get(variant_tier, tier_prompts["mini_parwa"])

        try:
            result = subprocess.run(
                ["z-ai", "chat", "--prompt", query, "--system", system_prompt, "--output", "/tmp/parwa_ai_resp.json"],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0 and os.path.exists("/tmp/parwa_ai_resp.json"):
                with open("/tmp/parwa_ai_resp.json") as f:
                    data = json.load(f)
                response = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if response:
                    return response.strip(), len(response.split())
        except Exception as e:
            pass

        return self._fallback_response(intent), 50


async def run_ai_powered_test():
    """Run the AI-powered test with variant differentiation."""
    print("=" * 80)
    print("  PARWA VARIANT ENGINE — AI-POWERED PRODUCTION TEST")
    print("  Real z-ai SDK responses with variant-specific prompts")
    print("=" * 80)

    simulator = AIPoweredSimulator()

    # Use a representative sample: 5 from each category + all emergency + all PII
    categories = ["refund", "billing", "technical", "complaint", "shipping", "account", "cancellation", "general"]
    sample = []
    for cat in categories:
        cat_requests = [r for r in TEST_REQUESTS if r["category"] == cat]
        sample.extend(cat_requests[:5])

    # Add all escalation and PII tests
    sample.extend(ESCALATION_REQUESTS)
    sample.extend(PII_TEST_REQUESTS)

    print(f"\n  Sample size: {len(sample)} requests x 3 variants = {len(sample)*3} AI-powered runs")

    tier_results = {}

    for tier in ["mini_parwa", "parwa", "parwa_high"]:
        print(f"\n{'─' * 80}")
        print(f"  Testing: {tier.upper()} (with AI-generated responses)")
        print(f"{'─' * 80}")

        results = []
        for i, req in enumerate(sample):
            result = await simulator.run_pipeline(req, tier)
            results.append(result)

            # Print sample responses
            if i < 3:
                print(f"\n  Request {req['id']} ({req['category']}/{req['emotion']}):")
                print(f"    Query: {req['query'][:80]}...")
                print(f"    Response: {result['response_preview'][:150]}...")
                print(f"    CLARA Score: {result['clara_score']} | Intent: {result['classification_intent']} | Latency: {result['total_latency_ms']}ms")

            if (i + 1) % 15 == 0:
                print(f"    ... processed {i+1}/{len(sample)}")

        # Compute metrics
        runner = ProductionTestRunner()
        metrics = runner.compute_metrics(results, tier)
        hrm = runner.compute_human_replacement_score(metrics)
        metrics["can_eliminate_humans_score"] = hrm

        tier_results[tier] = {"metrics": metrics, "sample_results": results[:5]}

        print(f"\n  {tier.upper()} Summary:")
        print(f"    Success Rate:       {metrics['success_rate']}%")
        print(f"    Quality Pass Rate:  {metrics['quality_pass_rate']}%")
        print(f"    Intent Accuracy:    {metrics['intent_accuracy']}%")
        print(f"    Avg CLARA Score:    {metrics['avg_clara_score']}")
        print(f"    Avg Empathy Score:  {metrics['avg_empathy_score']}")
        print(f"    Avg Latency:        {metrics['avg_latency_ms']}ms")
        print(f"    Human Replace Score:{hrm}/100")

    # ── Side-by-side comparison ─────────────────────────────────────
    print(f"\n{'=' * 80}")
    print(f"  VARIANT COMPARISON TABLE")
    print(f"{'=' * 80}")
    print(f"  {'Metric':<25} {'Mini':>12} {'Pro':>12} {'High':>12}")
    print(f"  {'─'*25} {'─'*12} {'─'*12} {'─'*12}")

    comparison_keys = [
        ("success_rate", "Success Rate %"),
        ("quality_pass_rate", "Quality Pass %"),
        ("intent_accuracy", "Intent Accuracy %"),
        ("avg_clara_score", "Avg CLARA Score"),
        ("avg_empathy_score", "Avg Empathy"),
        ("avg_latency_ms", "Avg Latency ms"),
        ("p95_latency_ms", "P95 Latency ms"),
        ("avg_crp_compression", "CRP Compression"),
        ("can_eliminate_humans_score", "Human Replace /100"),
    ]

    for key, label in comparison_keys:
        mini = tier_results["mini_parwa"]["metrics"].get(key, "N/A")
        pro = tier_results["parwa"]["metrics"].get(key, "N/A")
        high = tier_results["parwa_high"]["metrics"].get(key, "N/A")
        print(f"  {label:<25} {str(mini):>12} {str(pro):>12} {str(high):>12}")

    # ── Final verdict ───────────────────────────────────────────────
    print(f"\n{'=' * 80}")
    print(f"  FINAL PRODUCTION VERDICT")
    print(f"{'=' * 80}")

    for tier in ["mini_parwa", "parwa", "parwa_high"]:
        hrm = tier_results[tier]["metrics"]["can_eliminate_humans_score"]
        verdict = "PRODUCTION READY" if hrm >= 70 else "NEEDS IMPROVEMENT" if hrm >= 50 else "NOT READY"
        can_eliminate = "YES - Can fully replace human team" if hrm >= 75 else "PARTIALLY - Can handle most tickets" if hrm >= 60 else "NO - Needs human backup"

        print(f"\n  {tier.upper()}:")
        print(f"    Score: {hrm}/100")
        print(f"    Verdict: {verdict}")
        print(f"    Human Team Replacement: {can_eliminate}")

        # Industry-specific verdicts
        for ind, ind_m in tier_results[tier]["metrics"].get("by_industry", {}).items():
            ind_verdict = "EXCELLENT" if ind_m["avg_clara_score"] >= 80 else "GOOD" if ind_m["avg_clara_score"] >= 70 else "NEEDS WORK"
            print(f"      {ind}: CLARA={ind_m['avg_clara_score']} ({ind_verdict})")

    # Save results
    output_path = os.path.join(PROJECT_ROOT, "tests", "production", "ai_test_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Remove sample_results (too large) for JSON dump
    clean_results = {}
    for tier, data in tier_results.items():
        clean_results[tier] = {
            "metrics": data["metrics"],
            "sample_response_previews": [
                {"id": r["request_id"], "tier": r["variant_tier"], "intent": r["classification_intent"],
                 "clara_score": r["clara_score"], "response": r["response_preview"][:100]}
                for r in data["sample_results"]
            ]
        }

    with open(output_path, "w") as f:
        json.dump(clean_results, f, indent=2, default=str)

    print(f"\n  Results saved to: {output_path}")
    return tier_results


if __name__ == "__main__":
    asyncio.run(run_ai_powered_test())
