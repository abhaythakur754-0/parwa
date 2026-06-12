#!/bin/bash
set -e

# Start Next.js in background
cd /home/z/my-project/parwa
npx next dev -p 3000 -H 0.0.0.0 > /tmp/next-test.log 2>&1 &
NEXT_PID=$!
echo "Started Next.js with PID $NEXT_PID"

# Wait for it to be ready
for i in $(seq 1 30); do
  if curl -s -o /dev/null http://localhost:3000 2>/dev/null; then
    echo "Frontend ready after ${i}s"
    break
  fi
  sleep 1
done

# Verify both servers
echo "Frontend: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000)"
echo "Backend: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/docs)"

# Run the test
cd /home/z/my-project/download
node onboarding-test.mjs

# Cleanup
kill $NEXT_PID 2>/dev/null || true
