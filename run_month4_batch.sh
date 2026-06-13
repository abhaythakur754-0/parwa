#!/bin/bash
# Month 4 Batch Runner — runs in background, saves progress incrementally
cd /home/z/my-project/parwa
export PARWA_MOCK_MODE=false

echo "Starting Month 4 batch runner at $(date)" > /home/z/my-project/download/month4_progress.txt

python3 -u -c "
import asyncio, os, sys, json, time
os.environ['PARWA_MOCK_MODE'] = 'false'
sys.path.insert(0, '.')

from parwa.eval.month4_tickets import MONTH4_TICKETS

LOG = '/home/z/my-project/download/month4_progress.txt'
OUT = '/home/z/my-project/download/month4_variant_comparison.json'

def log(msg):
    with open(LOG, 'a') as f:
        f.write(msg + '\n')
    print(msg, flush=True)

async def run_one(ticket, variant, delay=3.0):
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm
    
    reset_crm()
    reset_parwa_graph()
    
    if delay > 0:
        await asyncio.sleep(delay)
    
    tid = ticket['id']
    start = time.time()
    try:
        result = await aprocess_ticket(
            raw_message=ticket['message'],
            customer_id=ticket['customer_id'],
            channel='email',
            variant=variant,
        )
        elapsed = (time.time() - start) * 1000
        
        # Evaluate
        intent_ok = result.get('intent', '').lower() == ticket['expected_intent'].lower()
        sent_ok = result.get('sentiment', '').lower() == ticket['expected_sentiment'].lower()
        esc_ok = result.get('should_escalate', False) == ticket['expected_escalation']
        
        icon_i = 'Y' if intent_ok else 'N'
        icon_s = 'Y' if sent_ok else 'N'
        icon_e = 'Y' if esc_ok else 'N'
        
        log(f'{tid}/{variant}: I:{icon_i} S:{icon_s} E:{icon_e} conf={result.get(\"intent_confidence\",0):.2f} time={elapsed:.0f}ms intent={result.get(\"intent\",\"?\")} expected={ticket[\"expected_intent\"]}')
        
        return {
            'ticket_id': tid,
            'variant': variant,
            'intent_correct': intent_ok,
            'sentiment_correct': sent_ok,
            'escalation_correct': esc_ok,
            'predicted_intent': result.get('intent', ''),
            'expected_intent': ticket['expected_intent'],
            'predicted_sentiment': result.get('sentiment', ''),
            'expected_sentiment': ticket['expected_sentiment'],
            'predicted_escalate': result.get('should_escalate', False),
            'expected_escalate': ticket['expected_escalation'],
            'intent_confidence': result.get('intent_confidence', 0),
            'quality_score': result.get('quality_score', 0),
            'clarifying_question': result.get('clarifying_question', ''),
            'multi_intent_detected': result.get('multi_intent_detected', False),
            'low_confidence_flag': result.get('low_confidence_flag', False),
            'escalation_trigger_reason': result.get('escalation_trigger_reason', ''),
            'time_ms': round(elapsed),
            'response_preview': result.get('final_response', '')[:200],
        }
    except Exception as e:
        log(f'{tid}/{variant}: ERROR - {e}')
        return {'ticket_id': tid, 'variant': variant, 'error': str(e),
                'intent_correct': False, 'sentiment_correct': False, 'escalation_correct': False}

async def main():
    results = {'mini': [], 'parwa': [], 'high': []}
    
    for variant in ['mini', 'parwa', 'high']:
        log(f'\\n===== Running variant: {variant.upper()} =====')
        for ticket in MONTH4_TICKETS:
            r = await run_one(ticket, variant, delay=3.0)
            results[variant].append(r)
    
    # Compute summaries
    summary = {}
    for variant in ['mini', 'parwa', 'high']:
        rs = results[variant]
        total = len(rs)
        if total == 0:
            continue
        intent_acc = sum(1 for r in rs if r.get('intent_correct')) / total * 100
        sent_acc = sum(1 for r in rs if r.get('sentiment_correct')) / total * 100
        esc_acc = sum(1 for r in rs if r.get('escalation_correct')) / total * 100
        auto_res = sum(1 for r in rs if not r.get('predicted_escalate', False) and not r.get('expected_escalate', True)) / total * 100
        summary[variant] = {
            'intent_accuracy': round(intent_acc, 1),
            'sentiment_accuracy': round(sent_acc, 1),
            'escalation_accuracy': round(esc_acc, 1),
            'autonomous_resolution': round(auto_res, 1),
        }
        log(f'{variant.upper()}: Intent={intent_acc:.1f}% Sent={sent_acc:.1f}% Esc={esc_acc:.1f}% AutoRes={auto_res:.1f}%')
    
    # Save full results
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'variant_summaries': summary,
        'per_variant_results': results,
    }
    with open(OUT, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    log(f'\\nResults saved to {OUT}')
    log('\\n===== FINAL COMPARISON =====')
    log(f'{\"Variant\":<10} {\"Intent\":>8} {\"Sentiment\":>10} {\"Escalation\":>10} {\"AutoRes\":>8}')
    log('-' * 50)
    for v in ['mini', 'parwa', 'high']:
        s = summary.get(v, {})
        log(f'{v:<10} {s.get(\"intent_accuracy\",0):>7.1f}% {s.get(\"sentiment_accuracy\",0):>9.1f}% {s.get(\"escalation_accuracy\",0):>9.1f}% {s.get(\"autonomous_resolution\",0):>7.1f}%')
    
    # What each variant GOT RIGHT vs WRONG vs IGNORED
    for variant in ['mini', 'parwa', 'high']:
        rs = results[variant]
        got_right = [r['ticket_id'] for r in rs if r.get('intent_correct') and r.get('sentiment_correct')]
        got_wrong = [r['ticket_id'] for r in rs if not r.get('intent_correct') or not r.get('sentiment_correct')]
        ignored = [r['ticket_id'] for r in rs if r.get('predicted_escalate') and not r.get('expected_escalate')]
        
        log(f'\\n{variant.upper()}:')
        log(f'  GOT RIGHT ({len(got_right)}): {got_right}')
        log(f'  GOT WRONG ({len(got_wrong)}): {got_wrong}')
        log(f'  IGNORED/ESCALATED ({len(ignored)}): {ignored}')
        
        # Wrong details
        for r in rs:
            if not r.get('intent_correct') or not r.get('sentiment_correct'):
                log(f'  WRONG {r[\"ticket_id\"]}: predicted intent={r.get(\"predicted_intent\",\"?\")} expected={r.get(\"expected_intent\",\"?\")} | predicted sent={r.get(\"predicted_sentiment\",\"?\")} expected={r.get(\"expected_sentiment\",\"?\")}')

asyncio.run(main())
" >> /home/z/my-project/download/month4_progress.txt 2>&1

echo "Completed at $(date)" >> /home/z/my-project/download/month4_progress.txt
