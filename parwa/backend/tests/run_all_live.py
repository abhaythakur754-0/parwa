"""
Self-contained 4-ticket runner.
Writes progress and results to JSON files — no stdout dependency.
"""
import asyncio
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone

sys.path.insert(0, "/home/z/my-project/parwa/backend")

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import get_stats, reset_stats

RESULTS_DIR = "/home/z/my-project/parwa/backend/tests/results"
PROGRESS_FILE = os.path.join(RESULTS_DIR, "progress.json")

TICKETS = [
    {
        "ticket_id": "tkt_phase1_001",
        "tenant_id": "tenant_test_a",
        "query": (
            "I have been a Pro plan customer for 8 months and I need to cancel my annual subscription "
            "and get a refund. I was charged $1,200 for the annual plan but I also have an outstanding "
            "credit of $75 from a previous billing error that was never applied. I want the full refund "
            "processed to my original payment method, and I want to know what happens to my stored data."
        ),
        "channel_type": "email",
        "variant_tier": "high",
        "quota": 2000,
        "customer_context": {"account_tier": "pro", "customer_tenure_days": 240, "recent_ticket_count": 3, "lifetime_value": 2400},
        "sender": "sarah.chen@company.com",
        "description": "Complex refund + credit + data retention",
    },
    {
        "ticket_id": "tkt_phase1_002",
        "tenant_id": "tenant_test_a",
        "query": (
            "I was charged $149 twice this month, once on the 1st and again on the 15th. "
            "Looking at my invoices, the first charge shows the correct Pro plan rate but "
            "the second one shows the High plan rate of $499. I never upgraded to High plan. "
            "Additionally, my team member who uses the same account key is seeing a different "
            "pricing page than me, she sees $99/mo instead of $149. I want both the duplicate "
            "charge fixed and an explanation for the pricing discrepancy."
        ),
        "channel_type": "chat",
        "variant_tier": "high",
        "quota": 1999,
        "customer_context": {"account_tier": "pro", "customer_tenure_days": 180, "recent_ticket_count": 1, "lifetime_value": 1500},
        "sender": "mike.r@startup.io",
        "description": "Duplicate charge + pricing discrepancy",
    },
    {
        "ticket_id": "tkt_phase1_003",
        "tenant_id": "tenant_test_a",
        "query": (
            "We need to change our subscription from High plan to Pro plan effective next month. "
            "But here is the complication: we have 15 team members on the High plan right now, "
            "and only 10 of them need Pro access. The other 5 should be moved to Mini. "
            "Also, we prepaid for the annual High plan 3 months ago ($4,999), so we need to know "
            "the prorated credit we will get, and whether that credit can be split across the "
            "two new plans. Finally, one of our team members is in the middle of a billing cycle "
            "dispute — how does the plan change affect their open ticket?"
        ),
        "channel_type": "email",
        "variant_tier": "high",
        "quota": 1998,
        "customer_context": {"account_tier": "high", "customer_tenure_days": 365, "recent_ticket_count": 7, "lifetime_value": 12000, "team_size": 15},
        "sender": "cto@bigcorp.com",
        "description": "Plan downgrade + team split + proration",
    },
    {
        "ticket_id": "tkt_phase1_004",
        "tenant_id": "tenant_test_a",
        "query": (
            "I suspect someone has accessed my account without authorization. Three things happened: "
            "1) My password was changed 2 days ago but I did not request this. "
            "2) A new team member 'john_devops' was added to my workspace yesterday — I don't know "
            "who this is. "
            "3) Our SSO integration with Okta is showing 'last synced 5 days ago' even though it "
            "should sync every hour. I need you to: remove the unauthorized user, reset my password, "
            "investigate the SSO sync failure, and tell me if any data was exported or modified "
            "during this period. This is urgent — we handle sensitive financial data."
        ),
        "channel_type": "chat",
        "variant_tier": "high",
        "quota": 1997,
        "customer_context": {"account_tier": "high", "customer_tenure_days": 400, "recent_ticket_count": 12, "lifetime_value": 18000, "team_size": 25, "has_sso": True},
        "sender": "security@fincomp.com",
        "description": "Account security breach + SSO failure",
    },
]


def write_progress(data):
    """Write progress to JSON file (atomic)."""
    tmp = PROGRESS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, PROGRESS_FILE)


async def run_ticket(ticket_num):
    ticket = TICKETS[ticket_num - 1]
    ticket_id = ticket["ticket_id"]

    write_progress({
        "status": "running",
        "current_ticket": ticket_num,
        "started": datetime.now(timezone.utc).isoformat(),
        "tickets_completed": [],
    })

    start = time.time()
    set_test_variant(ticket["tenant_id"], ticket["variant_tier"], ticket["quota"])
    reset_stats()

    initial_state = {
        "ticket_id": ticket_id,
        "tenant_id": ticket["tenant_id"],
        "query": ticket["query"],
        "channel_type": ticket.get("channel_type", "email"),
        "customer_context": ticket.get("customer_context", {}),
        "metadata": {
            "sender": ticket.get("sender", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "loop_count": 0,
        "total_token_usage": 0,
        "technique_log": [],
        "errors": [],
    }

    try:
        graph = build_parwa_pipeline()
        compiled = graph.compile()
        result = await compiled.ainvoke(initial_state)
        elapsed = time.time() - start

        # Build per-node stats
        node_stats = {}
        for log in result.get("technique_log", []):
            node = log.get("node", "?")
            tech = log.get("technique", "?")
            dur = log.get("duration_ms", 0)
            if node not in node_stats:
                node_stats[node] = {"techniques": [], "total_ms": 0, "count": 0}
            node_stats[node]["techniques"].append(tech)
            node_stats[node]["total_ms"] += dur
            node_stats[node]["count"] += 1

        response = (
            result.get("final_response", "")
            or result.get("formatted_response", "")
            or result.get("simple_answer", "")
            or result.get("super_node_answer", "")
        )

        client_stats = get_stats()
        summary = {
            "ticket_id": ticket_id,
            "description": ticket["description"],
            "status": result.get("status", "unknown"),
            "ticket_type": result.get("ticket_type", "N/A"),
            "complexity": result.get("complexity", "N/A"),
            "variant_tier": result.get("variant_tier", "N/A"),
            "route": result.get("route_decision", result.get("current_path", "N/A")),
            "total_llm_calls": result.get("total_token_usage", 0),
            "total_tokens": client_stats["total_tokens"],
            "total_errors": client_stats["total_errors"],
            "quality_score": result.get("quality_score", "N/A"),
            "super_node_quality": result.get("super_node_quality"),
            "loop_count": result.get("loop_count", 0),
            "escalated": bool(result.get("escalation_context")),
            "escalation_key": result.get("escalation_context", {}).get("notification_key") if result.get("escalation_context") else None,
            "elapsed_seconds": round(elapsed, 2),
            "avg_time_per_llm_call": round(elapsed / max(result.get("total_token_usage", 1), 1), 2),
            "node_breakdown": {},
            "all_techniques": [f"Node {l.get('node')}: {l.get('technique')} -> {l.get('result_summary')}" for l in result.get("technique_log", [])],
            "final_response": response[:3000],
            "errors": [e.get("error", str(e)) for e in result.get("errors", [])],
        }

        for node, stats in sorted(node_stats.items()):
            summary["node_breakdown"][f"node_{node}"] = {
                "technique_count": stats["count"],
                "total_ms": stats["total_ms"],
                "techniques": stats["techniques"],
            }

        # Save individual ticket result
        result_file = os.path.join(RESULTS_DIR, f"ticket_{ticket_num}.json")
        with open(result_file, "w") as f:
            json.dump(summary, f, indent=2, default=str)

        return summary

    except Exception as e:
        elapsed = time.time() - start
        summary = {
            "ticket_id": ticket_id,
            "status": "ERROR",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "elapsed_seconds": round(elapsed, 2),
        }
        result_file = os.path.join(RESULTS_DIR, f"ticket_{ticket_num}.json")
        with open(result_file, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        return summary


async def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    all_results = []
    overall_start = time.time()

    write_progress({
        "status": "started",
        "started": datetime.now(timezone.utc).isoformat(),
        "model": "NVIDIA meta/llama-3.1-8b-instruct",
        "rpm_limit": 40,
    })

    for i in range(1, 5):
        ticket_start = time.time()
        summary = await run_ticket(i)
        ticket_elapsed = time.time() - ticket_start
        summary["wall_time_seconds"] = round(ticket_elapsed, 2)
        all_results.append(summary)

        write_progress({
            "status": f"ticket_{i}_done",
            "current_ticket": i,
            "tickets_completed": [
                {"num": r["ticket_id"], "status": r["status"],
                 "calls": r.get("total_llm_calls", "N/A"),
                 "time": r.get("elapsed_seconds", "N/A")}
                for r in all_results
            ],
            "elapsed_so_far": round(time.time() - overall_start, 1),
        })

        # Wait 65s between tickets to replenish 40 RPM quota
        if i < 4:
            write_progress({
                "status": f"waiting_between_tickets",
                "just_finished": i,
                "waiting_for": i + 1,
                "wait_seconds": 65,
            })
            await asyncio.sleep(65)

    total_elapsed = time.time() - overall_start

    # Save combined results
    combined = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "model": "NVIDIA meta/llama-3.1-8b-instruct (40 RPM)",
        "total_wall_time_seconds": round(total_elapsed, 1),
        "total_wall_time_minutes": round(total_elapsed / 60, 1),
        "tickets": all_results,
        "aggregate": {
            "total_llm_calls": sum(r.get("total_llm_calls", 0) for r in all_results if isinstance(r.get("total_llm_calls"), int)),
            "total_tokens": sum(r.get("total_tokens", 0) for r in all_results if isinstance(r.get("total_tokens"), int)),
            "total_errors": sum(r.get("total_errors", 0) for r in all_results if isinstance(r.get("total_errors"), int)),
            "avg_quality": "N/A",
            "escalated_count": sum(1 for r in all_results if r.get("escalated")),
        },
    }

    # Calculate avg quality
    qualities = [r["quality_score"] for r in all_results if isinstance(r.get("quality_score"), (int, float))]
    if qualities:
        combined["aggregate"]["avg_quality"] = round(sum(qualities) / len(qualities), 3)

    combined_file = os.path.join(RESULTS_DIR, "all_tickets_combined.json")
    with open(combined_file, "w") as f:
        json.dump(combined, f, indent=2, default=str)

    write_progress({
        "status": "complete",
        "total_wall_time_seconds": round(total_elapsed, 1),
        "total_llm_calls": combined["aggregate"]["total_llm_calls"],
        "total_tokens": combined["aggregate"]["total_tokens"],
        "result_file": combined_file,
    })


if __name__ == "__main__":
    asyncio.run(main())