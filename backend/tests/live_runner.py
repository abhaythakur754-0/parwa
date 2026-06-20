"""Phase 1 - 4 Ticket Live Runner (NVIDIA Llama 3.1 8B)"""
import asyncio, json, os, sys, time, traceback
from datetime import datetime, timezone

sys.path.insert(0, "/home/z/my-project/parwa/backend")
os.makedirs("/home/z/my-project/parwa/backend/tests/results", exist_ok=True)

PROGRESS = "/home/z/my-project/parwa/backend/tests/results/progress.json"

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats

TICKETS = [
    {"ticket_id":"tkt_001","tenant_id":"tenant_a","query":"I have been a Pro plan customer for 8 months and I need to cancel my annual subscription and get a refund. I was charged $1,200 for the annual plan but I also have an outstanding credit of $75 from a previous billing error that was never applied. I want the full refund processed to my original payment method, and I want to know what happens to my stored data.","channel_type":"email","variant_tier":"high","quota":2000,"customer_context":{"account_tier":"pro","customer_tenure_days":240,"recent_ticket_count":3,"lifetime_value":2400},"sender":"sarah@test.com","description":"Refund+credit+data retention"},
    {"ticket_id":"tkt_002","tenant_id":"tenant_a","query":"I was charged $149 twice this month, once on the 1st and again on the 15th. Looking at my invoices, the first charge shows the correct Pro plan rate but the second one shows the High plan rate of $499. I never upgraded to High plan. Additionally, my team member who uses the same account key is seeing a different pricing page than me, she sees $99/mo instead of $149. I want both the duplicate charge fixed and an explanation for the pricing discrepancy.","channel_type":"chat","variant_tier":"high","quota":1999,"customer_context":{"account_tier":"pro","customer_tenure_days":180,"recent_ticket_count":1,"lifetime_value":1500},"sender":"mike@test.io","description":"Duplicate charge+pricing discrepancy"},
    {"ticket_id":"tkt_003","tenant_id":"tenant_a","query":"We need to change our subscription from High plan to Pro plan effective next month. But here is the complication: we have 15 team members on the High plan right now, and only 10 of them need Pro access. The other 5 should be moved to Mini. Also, we prepaid for the annual High plan 3 months ago ($4,999), so we need to know the prorated credit we will get, and whether that credit can be split across the two new plans. Finally, one of our team members is in the middle of a billing cycle dispute - how does the plan change affect their open ticket?","channel_type":"email","variant_tier":"high","quota":1998,"customer_context":{"account_tier":"high","customer_tenure_days":365,"recent_ticket_count":7,"lifetime_value":12000,"team_size":15},"sender":"cto@test.com","description":"Plan downgrade+team split+proration"},
    {"ticket_id":"tkt_004","tenant_id":"tenant_a","query":"I suspect someone has accessed my account without authorization. Three things happened: 1) My password was changed 2 days ago but I did not request this. 2) A new team member john_devops was added to my workspace yesterday. 3) Our SSO integration with Okta is showing last synced 5 days ago even though it should sync every hour. I need you to: remove the unauthorized user, reset my password, investigate the SSO sync failure, and tell me if any data was exported or modified. This is urgent - we handle sensitive financial data.","channel_type":"chat","variant_tier":"high","quota":1997,"customer_context":{"account_tier":"high","customer_tenure_days":400,"recent_ticket_count":12,"lifetime_value":18000,"team_size":25,"has_sso":True},"sender":"security@test.com","description":"Security breach+SSO failure"},
]
RDIR = "/home/z/my-project/parwa/backend/tests/results"

def wp(data):
    with open(PROGRESS+".tmp","w") as f: json.dump(data,f,default=str)
    os.replace(PROGRESS+".tmp", PROGRESS)

async def run_ticket(num, ticket):
    reset_stats()
    set_test_variant(ticket["tenant_id"], ticket["variant_tier"], ticket["quota"])
    state = {
        "ticket_id": ticket["ticket_id"], "tenant_id": ticket["tenant_id"],
        "query": ticket["query"], "channel_type": ticket.get("channel_type","email"),
        "customer_context": ticket.get("customer_context",{}),
        "metadata": {"sender": ticket.get("sender",""), "timestamp": datetime.now(timezone.utc).isoformat()},
        "loop_count": 0, "total_token_usage": 0, "technique_log": [], "errors": [],
    }
    t0 = time.time()
    try:
        graph = build_parwa_pipeline()
        compiled = graph.compile()
        result = await compiled.ainvoke(state)
        elapsed = time.time() - t0
        stats = get_stats()

        node_stats = {}
        for log in result.get("technique_log",[]):
            n = log.get("node","?")
            if n not in node_stats: node_stats[n] = {"count":0,"ms":0,"techs":[]}
            node_stats[n]["count"] += 1
            node_stats[n]["ms"] += log.get("duration_ms",0)
            node_stats[n]["techs"].append(log.get("technique","?"))

        resp = result.get("final_response","") or result.get("formatted_response","") or result.get("super_node_answer","")
        out = {
            "ticket_id": ticket["ticket_id"], "description": ticket["description"],
            "status": result.get("status"), "ticket_type": result.get("ticket_type"),
            "complexity": result.get("complexity"),
            "route": result.get("route_decision", result.get("current_path")),
            "llm_calls": result.get("total_token_usage",0),
            "tokens": stats["total_tokens"], "llm_errors": stats["total_errors"],
            "quality_score": result.get("quality_score"),
            "super_node_quality": result.get("super_node_quality"),
            "loops": result.get("loop_count",0),
            "escalated": bool(result.get("escalation_context")),
            "time_s": round(elapsed,1),
            "time_per_call_s": round(elapsed/max(result.get("total_token_usage",1),1),2),
            "node_breakdown": {f"node_{k}":v for k,v in sorted(node_stats.items())},
            "techniques": [f"N{l.get('node')}: {l.get('technique')} -> {l.get('result_summary')}" for l in result.get("technique_log",[])],
            "response_preview": resp[:800],
            "errors": [e.get("error",str(e)) for e in result.get("errors",[])],
        }
    except Exception as e:
        elapsed = time.time() - t0
        out = {"ticket_id": ticket["ticket_id"], "description": ticket["description"],
               "status": "ERROR", "error": str(e), "traceback": traceback.format_exc(),
               "time_s": round(elapsed,1)}

    with open(os.path.join(RDIR, f"ticket_{num}.json"),"w") as f:
        json.dump(out, f, indent=2, default=str)
    return out

async def main(start_from=1):
    wp({"status":"started","time":datetime.now(timezone.utc).isoformat(),"model":"NVIDIA Llama 3.1 8B","from_ticket":start_from})
    all_r = []
    t_all = time.time()
    for idx in range(start_from-1, len(TICKETS)):
        i = idx + 1
        t = TICKETS[idx]
        wp({"status":f"ticket_{i}_running","started":datetime.now(timezone.utc).isoformat(),"done":[r.get("ticket_id") for r in all_r]})
        r = await run_ticket(i, t)
        all_r.append(r)
        wp({"status":f"ticket_{i}_done","result":{"id":r["ticket_id"],"status":r["status"],"calls":r.get("llm_calls","?"),"time":r.get("time_s","?")}})
        if idx < len(TICKETS)-1:
            wp({"status":"waiting_60s","next_ticket":i+2})
            await asyncio.sleep(60)

    total = time.time() - t_all
    combined = {
        "run_time": datetime.now(timezone.utc).isoformat(),
        "model": "NVIDIA meta/llama-3.1-8b-instruct (40 RPM)",
        "total_time_s": round(total,1), "total_time_min": round(total/60,1),
        "total_calls": sum(r.get("llm_calls",0) for r in all_r if isinstance(r.get("llm_calls"),int)),
        "total_tokens": sum(r.get("tokens",0) for r in all_r if isinstance(r.get("tokens"),int)),
        "escalated_count": sum(1 for r in all_r if r.get("escalated")),
        "tickets": all_r,
    }
    with open(os.path.join(RDIR,"all_tickets_combined.json"),"w") as f:
        json.dump(combined, f, indent=2, default=str)
    wp({"status":"ALL_COMPLETE","total_calls":combined["total_calls"],"total_tokens":combined["total_tokens"],"total_time_min":combined["total_time_min"]})

if __name__ == "__main__":
    start_from = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(main(start_from))