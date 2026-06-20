#!/bin/bash
# Run all 4 tickets sequentially, saving results to files.
# Each ticket takes ~3-4 min with 6s LLM throttle.
# Total: ~15-20 min for all 4 tickets.
cd /home/z/my-project/parwa/backend

RESULTS_DIR="tests/results"
mkdir -p "$RESULTS_DIR"

LOG="$RESULTS_DIR/run.log"
echo "=== PHASE 1 LIVE TEST STARTED: $(date -u) ===" > "$LOG"

for i in 1 2 3 4; do
    echo "" >> "$LOG"
    echo "=== TICKET $i STARTED: $(date -u) ===" >> "$LOG"
    
    # Kill any stale proxy
    pkill -f "llm_proxy.js" 2>/dev/null
    sleep 2
    
    # Run ticket (no timeout needed, the proxy handles rate limiting)
    python tests/test_single_ticket.py $i >> "$LOG" 2>&1
    
    echo "=== TICKET $i FINISHED: $(date -u) ===" >> "$LOG"
    
    # Wait 30s between tickets for rate limit reset
    if [ $i -lt 4 ]; then
        echo "Waiting 30s between tickets..." >> "$LOG"
        sleep 30
    fi
done

echo "" >> "$LOG"
echo "=== ALL TICKETS COMPLETED: $(date -u) ===" >> "$LOG"
echo "DONE"