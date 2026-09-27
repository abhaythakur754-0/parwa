#!/bin/bash
# =============================================================================
# Parwa - Push to GitHub
# =============================================================================
# Usage: ./push_to_github.sh YOUR_GITHUB_TOKEN [REPO_URL]
#
# If REPO_URL is not provided, it will create: https://github.com/YOUR_USERNAME/parwa-backend.git
# =============================================================================

TOKEN="${1:?Error: GitHub token required. Usage: $0 <token> [repo_url]}"
REPO_URL="${2:-}"

set -e  # Exit on any error

echo "🚀 Pushing Parwa Production Backend to GitHub..."
echo ""

# Get user info from token
echo "📋 Verifying token..."
USER_INFO=$(curl -s -H "Authorization: token $TOKEN" https://api.github.com/user)

if echo "$USER_INFO" | grep -q "Bad credentials"; then
    echo "❌ Error: Invalid or expired GitHub token"
    echo "   Please generate a new token at: https://github.com/settings/tokens"
    echo "   Required scopes: repo, write:public_key"
    exit 1
fi

USERNAME=$(echo "$USER_INFO" | grep -o '"login":"[^"]*"' | cut -d'"' -f4)
echo "✅ Authenticated as: $USERNAME"

# Determine repo URL
if [ -z "$REPO_URL" ]; then
    REPO_URL="https://github.com/${USERNAME}/parwa-backend.git"
    echo "📦 Target repository: $REPO_URL"
    echo ""
    
    # Check if repo exists
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: token $TOKEN" \
        "https://api.github.com/repos/${USERNAME}/parwa-backend")
    
    if [ "$HTTP_STATUS" = "404" ]; then
        echo "📁 Repository doesn't exist. Creating..."
        CREATE_RESPONSE=$(curl -s -X POST -H "Authorization: token $TOKEN" \
            -H "Content-Type: application/json" \
            -d '{
                "name": "parwa-backend",
                "description": "Parwa Production Backend - Variant limits, Trial tracking, Integration tools",
                "private": false,
                "has_issues": true,
                "has_projects": true,
                "has_wiki": true
            }' \
            https://api.github.com/user/repos)
        
        if echo "$CREATE_RESPONSE" | grep -q '"full_name"'; then
            echo "✅ Repository created successfully!"
        else
            echo "⚠️ Could not create repo. You may need to create it manually."
            echo "   Response: $CREATE_RESPONSE"
        fi
    else
        echo "✅ Repository exists"
    fi
fi

# Configure remote
echo ""
echo "🔗 Configuring remote..."
cd /home/z/my-project

# Remove existing origin if any
git remote remove origin 2>/dev/null || true

# Add new remote with token
git remote add origin "https://${TOKEN}@github.com/${USERNAME}/parwa-backend.git"

# Push to GitHub
echo ""
echo "⬆️  Pushing to GitHub..."
git push -u origin main 2>&1 || git push -u origin master 2>&1 || {
    # If neither main nor master works, try to push current branch
    CURRENT_BRANCH=$(git branch --show-current)
    git push -u origin $CURRENT_BRANCH 2>&1
}

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ SUCCESS! Code pushed to GitHub"
    echo "=========================================="
    echo "📍 Repository: https://github.com/${USERNAME}/parwa-backend"
    echo ""
    echo "📦 What was pushed:"
    echo "   • backend/main.py - Production backend v2.0.0"
    echo "   • Database integration (usage limits, trials, integrations)"
    echo "   • All cleanup scripts"
    echo ""
    echo "🎉 Ready for production deployment!"
else
    echo ""
    echo "❌ Push failed. Please check:"
    echo "   1. Token has 'repo' scope permissions"
    echo "   2. You have write access to the repository"
    echo "   3. Network connectivity"
    exit 1
fi
