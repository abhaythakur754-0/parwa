"""Phase 4 single ticket test — ticket 1 only, file-based result"""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase4', exist_ok=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase4'

async def main():
    reset_stats()
    ticket = {'ticket_id':'tkt_p4_001','tenant_id':'tenant_a','query':'I have been a Pro plan customer for 8 months and I need to cancel my annual subscription and get a refund. I was charged $1,200 for the annual plan but I also have an outstanding credit of $75 from a previous billing error that was never applied. I want the full refund processed to my original payment method, and I want to know what happens to my stored data.','channel_type':'email','variant_tier':'high','quota':2000,'customer_context':{'account_tier':'pro','customer_tenure_days':240,'recent_ticket_count':3,'lifetime_value':2400},'sender':'sarah@test.com','description':'Refund+credit+data retention'}
    set_test_variant(ticket['tenant_id'], ticket['variant_tier'], ticket['quota'])
    state = {'ticket_id':ticket['ticket_id'],'tenant_id':ticket['tenant_id'],'query':ticket['query'],'channel_type':ticket['channel_type'],'customer_context':ticket['customer_context'],'metadata':{'sender':ticket['sender'],'timestamp':'2026-06-18T00:00:00Z'},'loop_count':0,'total_token_usage':0,'technique_log':[],'errors':[]}
    t0 = time.time()
    try:
        graph = build_parwa_pipeline(); compiled = graph.compile()
        result = await compiled.ainvoke(state)
        elapsed = time.time() - t0; stats = get_stats()
        ns = {}
        for log in result.get('technique_log',[]):
            n = f"node_{log.get('node','?')}"
            ns[n] = ns.get(n, 0) + 1
        resp = result.get('final_response','') or result.get('formatted_response','') or result.get('super_node_answer','')
        qd = result.get('quality_details',{})
        out = {'ticket_id':ticket['ticket_id'],'description':ticket['description'],'status':result.get('status'),'ticket_type':result.get('ticket_type'),'complexity':result.get('complexity'),'route':result.get('route_decision',result.get('current_path')),'llm_calls':stats['total_calls'],'tokens':stats['total_tokens'],'llm_errors':stats['total_errors'],'quality_score':result.get('quality_score'),'quality_details':qd,'super_node_quality':result.get('super_node_quality'),'loops':result.get('loop_count',0),'escalated':bool(result.get('escalation_context')),'time_s':round(elapsed,1),'time_per_call_s':round(elapsed/max(stats['total_calls'],1),2),'node_breakdown':ns,'response_preview':resp[:800],'errors':[]}
    except Exception as e:
        elapsed = time.time() - t0
        out = {'ticket_id':ticket['ticket_id'],'description':ticket['description'],'status':'ERROR','error':str(e),'traceback':traceback.format_exc(),'time_s':round(elapsed,1)}
    with open(os.path.join(RDIR,'ticket_1.json'),'w') as f:
        json.dump(out, f, indent=2, default=str)
    # Status file for easy polling
    with open(os.path.join(RDIR,'t1_status.txt'),'w') as f:
        f.write(f"DONE status={out.get('status')} quality={out.get('quality_score')} calls={out.get('llm_calls')} tokens={out.get('tokens')} time={out.get('time_s')}s escalated={out.get('escalated')}\n")
        if out.get('quality_details'):
            f.write(f"DETAILS: {json.dumps(out['quality_details'])}\n")

asyncio.run(main())