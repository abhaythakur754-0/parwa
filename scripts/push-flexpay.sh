#!/bin/bash
set -e

echo "=== Pushing FlexPay UI Changes ==="
cd /home/z/my-project/parwa-src

echo "Current directory: $(pwd)"
echo "Git status:"
git status --short

echo ""
echo "Staging changes..."
git add src/app/dashboard/billing/page.tsx src/lib/flexpay/razorpay-integration.ts

echo ""
echo "Committing..."
git commit -m "feat: Add FlexPay info banner with USD pricing and feature timeline

- Add FlexPay explanation banner with \$100/day bank limit info
- Show feature availability timeline (Day 1 vs Day 11)
- Display immediate features: Ticket Management, Team Collaboration, Analytics, Workflows
- Display Day 11 features: SMS Notifications, Calling Features
- Add reassurance about instant access for Month 2+ renewals
- Update all pricing text to use USD (\$)"

echo ""
echo "Pushing to origin/main..."
git push origin main

echo ""
echo "✅ Done! Now updating parent repo..."
cd /home/z/my-project
git add parwa-src
git commit -m "chore: update parwa-src submodule with FlexPay UI changes"
git push origin main

echo ""
echo "✅✅✅ ALL DONE! Changes pushed successfully."
