#!/bin/bash
# Run all 4 tickets with NVIDIA Llama 3.1 8B
# 40 RPM limit — rate limiter in llm_client.py handles spacing

cd /home/z/my-project/parwa/backend
LOGFILE="tests/results/run.log"
mkdir -p tests/results

echo "========================================" | tee -a "$LOGFILE"
echo "4-TICKET LIVE TEST - $(date -u '+%Y-%m-%d %H:%M:%S UTC')" | tee -a "$LOGFILE"
echo "Model: NVIDIA meta/llama-3.1-8b-instruct (40 RPM)" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"

TOTAL_START=$(date +%s)

for i in 1 2 3 4; do
  echo "" | tee -a "$LOGFILE"
  echo ">>> Starting Ticket $i at $(date -u '+%H:%M:%S UTC')" | tee -a "$LOGFILE"
  TICKET_START=$(date +%s)
  
  python tests/test_single_ticket.py $i 2>&1 | tee -a "$LOGFILE"
  
  TICKET_END=$(date +%s)
  TICKET_ELAPSED=$((TICKET_END - TICKET_START))
  echo ">>> Ticket $i completed in ${TICKET_ELAPSED}s" | tee -a "$LOGFILE"
  
  # Wait 65s between tickets to replenish 40 RPM quota
  if [ $i -lt 4 ]; then
    echo ">>> Waiting 65s for rate limit replenishment..." | tee -a "$LOGFILE"
    sleep 65
  fi
done

TOTAL_END=$(date +%s)
TOTAL_ELAPSED=$((TOTAL_END - TOTAL_START))
echo "" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"
echo "ALL 4 TICKETS COMPLETE - Total: ${TOTAL_ELAPSED}s ($(($TOTAL_ELAPSED / 60))m $(($TOTAL_ELAPSED % 60))s)" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"

# Print summary from all JSON files
echo "" | tee -a "$LOGFILE"
echo "=== SUMMARY ===" | tee -a "$LOGFILE"
python3 -c "
import json, os
results_dir = 'tests/results'
grand_calls = 0
grand_tokens = 0
grand_time = 0
for i in range(1, 5):
    f = os.path.join(results_dir, f'ticket_{i}.json')
    if os.path.exists(f):
        with open(f) as fh:
            d = json.load(fh)
        calls = d.get('total_llm_calls', 'N/A')
        tokens = d.get('tokens_from_client', 'N/A')
        elapsed = d.get('elapsed_seconds', 'N/A')
        status = d.get('status', 'N/A')
        quality = d.get('quality_score', 'N/A')
        route = d.get('route', 'N/A')
        loops = d.get('loop_count', 0)
        escalated = d.get('escalated', False)
        print(f'Ticket {i}: status={status} route={route} calls={calls} tokens={tokens} quality={quality} loops={loops} escalated={escalated} time={elapsed}s')
        if isinstance(calls, int): grand_calls += calls
        if isinstance(tokens, int): grand_tokens += tokens
        if isinstance(elapsed, (int, float)): grand_time += elapsed
print(f'')
print(f'TOTAL: {grand_calls} LLM calls, {grand_tokens} tokens, {grand_time:.1f}s ({grand_time/60:.1f}min)')
" 2>&1 | tee -a "$LOGFILE"