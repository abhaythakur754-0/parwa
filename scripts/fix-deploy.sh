#!/bin/bash
set -e

echo "=== Fixing FlexPay Deployment ==="

# Go to parwa-src directory
cd /home/z/my-project/parwa-src
echo "Working in: $(pwd)"

# Check status
echo ""
echo "Git status:"
git status --short src/app/dashboard/billing/page.tsx src/lib/flexpay/razorpay-integration.ts

# Stage changes
echo ""
echo "Staging files..."
git add src/app/dashboard/billing/page.tsx src/lib/flexpay/razorpay-integration.ts

# Verify staged
echo ""
echo "Staged changes:"
git diff --cached --stat

# Commit
echo ""
echo "Committing..."
git commit -m "feat: Add FlexPay info banner with USD pricing and feature timeline

- Add explanation banner about \$100/day bank transaction limit
- Show Day 1 features: Ticket Management, Team Collaboration, Analytics, Workflows  
- Show Day 11 features: SMS Notifications, Calling Features
- Add Month 2+ instant access reassurance note
- Update all pricing text to use USD (\$)"

# Push to remote
echo ""
echo "Pushing to origin/main..."
git push origin main

# Now update parent repo
echo ""
echo "Updating parent repo..."
cd /home/z/my-project
git add parwa-src
git commit -m "chore: update parwa-src submodule with FlexPay UI"
git push origin main

echo ""
echo "✅✅✅ SUCCESS! Changes deployed."
echo "Wait 2-3 minutes for Vercel deployment."
