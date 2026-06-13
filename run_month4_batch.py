#!/usr/bin/env python3
"""Month 4 Batch Runner - runs all 15 tickets x 3 variants with NVIDIA+ZAI"""
import asyncio, json, time, sys, os
os.environ['NVIDIA_API_KEY'] = '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'
os.environ['PARWA_MOCK_MODE'] = 'false'
sys.stdout.reconfigure(line_buffering=True)

async def run():
    from parwa.eval.month4_tickets import MONTH4_TICKETS
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm
    
    variants = ['mini', 'parwa', 'high']
    all_results = {v: [] for v in variants}
    
    for variant in variants:
        print(f'\n=== {variant.upper()} ===', flush=True)
        for i, ticket in enumerate(MONTH4_TICKETS):
            reset_parwa_graph(); reset_crm()
            tid = ticket['id']
            print(f'[{variant.upper()}] [{i+1}/15] {tid}...', end=' ', flush=True)
            start = time.time()
            try:
                result = await aprocess_ticket(raw_message=ticket['message'], customer_id=ticket['customer_id'], channel='email', variant=variant)
                elapsed = time.time() - start
                intent = str(result.get('intent', '?')).lower().replace('sentimenttype.', '')
                sentiment = str(result.get('sentiment', 'neutral')).lower().replace('sentimenttype.', '')
                escalate = result.get('should_escalate', False)
                confidence = result.get('intent_confidence', 0)
                esc_trigger = result.get('escalation_trigger_reason', '')
                clarifying = result.get('clarifying_question', '')
                low_conf = result.get('low_confidence_flag', False)
                intent_ok = intent == ticket['expected_intent'].lower()
                sent_ok = sentiment == ticket['expected_sentiment'].lower()
                esc_ok = bool(escalate) == ticket['expected_escalation']
                print(f'{elapsed:.0f}s I:{"V" if intent_ok else "X"} S:{"V" if sent_ok else "X"} E:{"V" if esc_ok else "X"}', flush=True)
                all_results[variant].append({'ticket_id': tid, 'category': ticket['category'], 'difficulty': ticket['difficulty'],
                    'predicted_intent': intent, 'expected_intent': ticket['expected_intent'],
                    'predicted_sentiment': sentiment, 'expected_sentiment': ticket['expected_sentiment'],
                    'predicted_escalate': bool(escalate), 'expected_escalate': ticket['expected_escalation'],
                    'intent_correct': intent_ok, 'sentiment_correct': sent_ok, 'escalation_correct': esc_ok,
                    'confidence': confidence, 'time_s': round(elapsed, 1),
                    'clarifying_question': clarifying, 'low_confidence_flag': low_conf, 'escalation_trigger_reason': esc_trigger,
                    'response_preview': result.get('final_response', '')[:200]})
            except Exception as e:
                elapsed = time.time() - start
                print(f'FAIL {elapsed:.0f}s: {e}', flush=True)
                all_results[variant].append({'ticket_id': tid, 'error': str(e), 'intent_correct': False, 'sentiment_correct': False, 'escalation_correct': False,
                    'predicted_intent': 'error', 'expected_intent': ticket['expected_intent'],
                    'predicted_sentiment': 'error', 'expected_sentiment': ticket['expected_sentiment'],
                    'predicted_escalate': False, 'expected_escalate': ticket['expected_escalation']})
    
    with open('/home/z/my-project/download/month4_variant_comparison.json', 'w') as f:
        json.dump({'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'), 'llm': 'nvidia_primary_zai_fallback', 'results': all_results}, f, indent=2, default=str)
    
    print(f'\n{"="*60}', flush=True)
    print('MONTH 4 COMPARISON', flush=True)
    print(f'{"="*60}', flush=True)
    print(f'{"Metric":<25s} {"Mini":>8s} {"PARWA":>8s} {"High":>8s}', flush=True)
    for metric, label in [('intent_correct', 'Intent'), ('sentiment_correct', 'Sentiment'), ('escalation_correct', 'Escalation')]:
        vals = []
        for v in variants:
            r = all_results[v]
            pct = sum(1 for x in r if x.get(metric)) / max(len(r), 1) * 100
            vals.append(f'{pct:.0f}%')
        print(f'{label:<25s} {vals[0]:>8s} {vals[1]:>8s} {vals[2]:>8s}', flush=True)
    
    for v in variants:
        r = all_results[v]
        right = [x['ticket_id'] for x in r if x.get('intent_correct') and x.get('sentiment_correct')]
        wrong = [x['ticket_id'] for x in r if not x.get('intent_correct') or not x.get('sentiment_correct')]
        ignored = [x['ticket_id'] for x in r if x.get('predicted_escalate') and not x.get('expected_escalate')]
        print(f'\n{v.upper()}: RIGHT={right} WRONG={wrong} IGNORED={ignored}', flush=True)
        for x in r:
            if not x.get('intent_correct') or not x.get('sentiment_correct'):
                print(f'  {x["ticket_id"]}: i={x.get("predicted_intent","?")}(exp:{x.get("expected_intent","?")}), s={x.get("predicted_sentiment","?")}(exp:{x.get("expected_sentiment","?")})', flush=True)
    print(f'\nDone! Saved to /home/z/my-project/download/month4_variant_comparison.json', flush=True)

asyncio.run(run())
