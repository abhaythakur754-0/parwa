#!/usr/bin/env python3
"""Month 4 Background Batch Runner — runs all tickets and saves results.

Run this as a background process. Results saved to:
/home/z/my-project/download/month4_variant_comparison.json
"""
import asyncio
import os
import sys

# Ensure no mock mode
os.environ["PARWA_MOCK_MODE"] = "false"

sys.path.insert(0, os.path.dirname(__file__))

from parwa.eval.month4_batch_runner import run_batch

async def main():
    # Run all 15 tickets x 3 variants with 3s delay for rate limit management
    report = await run_batch(
        variant_filter=None,  # All variants
        delay=3.0,            # 3s between tickets
        quick=False,          # Full 15 tickets
    )

    # Print final summary
    print("\n\nFINAL RESULTS SAVED TO /home/z/my-project/download/month4_variant_comparison.json")

    for variant in ["mini", "parwa", "high"]:
        analysis = report.get("variant_analyses", {}).get(variant, {})
        if analysis and analysis.get("total", 0) > 0:
            print(f"\n{variant.upper()}: Intent={analysis['intent_accuracy']}% "
                  f"Sentiment={analysis['sentiment_accuracy']}% "
                  f"Escalation={analysis['escalation_accuracy']}% "
                  f"Autonomous={analysis['autonomous_resolution_rate']}%")

if __name__ == "__main__":
    asyncio.run(main())
