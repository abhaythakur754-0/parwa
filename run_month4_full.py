#!/usr/bin/env python3
"""Month 4 Full Batch Runner — all 15 tickets x 3 variants."""
import asyncio
import json
import os
import sys
import time
import traceback

os.environ["PARWA_MOCK_MODE"] = "false"

LOG_FILE = "/home/z/my-project/download/month4_progress.txt"
OUT_FILE = "/home/z/my-project/download/month4_variant_comparison.json"


def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


async def run_one(ticket, variant, delay=3.0):
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm

    reset_crm()
    reset_parwa_graph()

    if delay > 0:
        await asyncio.sleep(delay)

    tid = ticket["id"]
    start = time.time()
    try:
        result = await aprocess_ticket(
            raw_message=ticket["message"],
            customer_id=ticket["customer_id"],
            channel="email",
            variant=variant,
        )
        elapsed = (time.time() - start) * 1000

        # Evaluate
        pred_intent = str(result.get("intent", "")).lower().replace("sentimenttype.", "")
        pred_sent = str(result.get("sentiment", "")).lower().replace("sentimenttype.", "")
        pred_esc = result.get("should_escalate", False)
        if isinstance(pred_esc, str):
            pred_esc = pred_esc.lower() in ("true", "yes")

        exp_intent = ticket["expected_intent"].lower()
        exp_sent = ticket["expected_sentiment"].lower()
        exp_esc = ticket["expected_escalation"]

        intent_ok = pred_intent == exp_intent
        sent_ok = pred_sent == exp_sent
        esc_ok = pred_esc == exp_esc

        icon_i = "Y" if intent_ok else "N"
        icon_s = "Y" if sent_ok else "N"
        icon_e = "Y" if esc_ok else "N"

        log(f"{tid}/{variant}: I:{icon_i} S:{icon_s} E:{icon_e} conf={result.get('intent_confidence',0):.2f} {elapsed:.0f}ms pred_i={pred_intent} exp_i={exp_intent}")

        return {
            "ticket_id": tid,
            "variant": variant,
            "intent_correct": intent_ok,
            "sentiment_correct": sent_ok,
            "escalation_correct": esc_ok,
            "predicted_intent": pred_intent,
            "expected_intent": exp_intent,
            "predicted_sentiment": pred_sent,
            "expected_sentiment": exp_sent,
            "predicted_escalate": pred_esc,
            "expected_escalate": exp_esc,
            "intent_confidence": result.get("intent_confidence", 0),
            "quality_score": result.get("quality_score", 0),
            "clarifying_question": result.get("clarifying_question", ""),
            "multi_intent_detected": result.get("multi_intent_detected", False),
            "low_confidence_flag": result.get("low_confidence_flag", False),
            "escalation_trigger_reason": result.get("escalation_trigger_reason", ""),
            "time_ms": round(elapsed),
            "category": ticket["category"],
            "difficulty": ticket["difficulty"],
            "response_preview": result.get("final_response", "")[:200],
        }
    except Exception as e:
        log(f"{tid}/{variant}: ERROR - {e}")
        traceback.print_exc()
        return {
            "ticket_id": tid, "variant": variant, "error": str(e),
            "intent_correct": False, "sentiment_correct": False,
            "escalation_correct": False, "category": ticket["category"],
            "difficulty": ticket["difficulty"],
            "predicted_intent": "error", "expected_intent": ticket["expected_intent"],
            "predicted_sentiment": "error", "expected_sentiment": ticket["expected_sentiment"],
            "predicted_escalate": False, "expected_escalate": ticket["expected_escalation"],
            "intent_confidence": 0, "quality_score": 0, "time_ms": 0,
        }


async def main():
    from parwa.eval.month4_tickets import MONTH4_TICKETS

    # Clear log
    with open(LOG_FILE, "w") as f:
        f.write(f"Month 4 Batch Runner started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    results = {"mini": [], "parwa": [], "high": []}

    for variant in ["mini", "parwa", "high"]:
        log(f"\n===== Running variant: {variant.upper()} =====")
        for i, ticket in enumerate(MONTH4_TICKETS):
            try:
                # Add extra delay between tickets for rate limit management
                # ZAI SDK has ~30 RPM, each ticket uses ~15-20 LLM calls
                # So we need ~45-60s between tickets minimum
                extra_delay = 5.0 if i > 0 else 0.0
                r = await run_one(ticket, variant, delay=3.0 + extra_delay)
                results[variant].append(r)
            except Exception as e:
                log(f"FATAL on {ticket['id']}/{variant}: {e}")
                traceback.print_exc()
                results[variant].append({
                    "ticket_id": ticket["id"], "variant": variant, "error": str(e),
                    "intent_correct": False, "sentiment_correct": False,
                    "escalation_correct": False, "category": ticket["category"],
                    "difficulty": ticket["difficulty"],
                    "predicted_intent": "fatal_error", "expected_intent": ticket["expected_intent"],
                    "predicted_sentiment": "fatal_error", "expected_sentiment": ticket["expected_sentiment"],
                    "predicted_escalate": False, "expected_escalate": ticket["expected_escalation"],
                    "intent_confidence": 0, "quality_score": 0, "time_ms": 0,
                })
            # Save intermediate results after each ticket
            try:
                with open(OUT_FILE, "w") as f:
                    json.dump({
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "in_progress": True,
                        "current_variant": variant,
                        "per_variant_results": results,
                    }, f, indent=2, default=str)
            except Exception:
                pass

    # Compute summaries
    summary = {}
    for variant in ["mini", "parwa", "high"]:
        rs = results[variant]
        total = len(rs)
        if total == 0:
            continue

        intent_acc = sum(1 for r in rs if r.get("intent_correct")) / total * 100
        sent_acc = sum(1 for r in rs if r.get("sentiment_correct")) / total * 100
        esc_acc = sum(1 for r in rs if r.get("escalation_correct")) / total * 100

        # Autonomous resolution: correctly NOT escalating when not needed
        auto_count = sum(
            1 for r in rs
            if not r.get("predicted_escalate", True) and not r.get("expected_escalate", True)
        )
        auto_res = auto_count / total * 100

        summary[variant] = {
            "intent_accuracy": round(intent_acc, 1),
            "sentiment_accuracy": round(sent_acc, 1),
            "escalation_accuracy": round(esc_acc, 1),
            "autonomous_resolution": round(auto_res, 1),
        }
        log(f"{variant.upper()}: Intent={intent_acc:.1f}% Sent={sent_acc:.1f}% Esc={esc_acc:.1f}% AutoRes={auto_res:.1f}%")

    # Save results
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "variant_summaries": summary,
        "per_variant_results": results,
    }
    with open(OUT_FILE, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Final comparison
    log("\n===== FINAL COMPARISON =====")
    log(f"{'Variant':<10} {'Intent':>8} {'Sentiment':>10} {'Escalation':>10} {'AutoRes':>8}")
    log("-" * 50)
    for v in ["mini", "parwa", "high"]:
        s = summary.get(v, {})
        log(f"{v:<10} {s.get('intent_accuracy',0):>7.1f}% {s.get('sentiment_accuracy',0):>9.1f}% {s.get('escalation_accuracy',0):>9.1f}% {s.get('autonomous_resolution',0):>7.1f}%")

    # What each variant GOT RIGHT vs WRONG vs IGNORED
    for variant in ["mini", "parwa", "high"]:
        rs = results[variant]
        got_right = [r["ticket_id"] for r in rs if r.get("intent_correct") and r.get("sentiment_correct")]
        got_wrong = [r["ticket_id"] for r in rs if not r.get("intent_correct") or not r.get("sentiment_correct")]
        ignored = [r["ticket_id"] for r in rs if r.get("predicted_escalate") and not r.get("expected_escalate")]

        log(f"\n{variant.upper()}:")
        log(f"  GOT RIGHT ({len(got_right)}): {got_right}")
        log(f"  GOT WRONG ({len(got_wrong)}): {got_wrong}")
        log(f"  IGNORED/ESCALATED ({len(ignored)}): {ignored}")

        for r in rs:
            if not r.get("intent_correct") or not r.get("sentiment_correct"):
                log(f"  WRONG {r['ticket_id']}: pred_i={r.get('predicted_intent','?')} exp_i={r.get('expected_intent','?')} | pred_s={r.get('predicted_sentiment','?')} exp_s={r.get('expected_sentiment','?')}")

    log(f"\nCompleted at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Results saved to {OUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
