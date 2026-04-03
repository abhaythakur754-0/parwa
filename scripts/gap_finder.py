#!/usr/bin/env python3
"""
PARWA Gap Finder - Reusable tool for finding testing gaps
Usage: python scripts/gap_finder.py "<feature description>" [--output json|text]
"""

import sys
import json
import argparse
import asyncio
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

SYSTEM_PROMPT = """You are a senior software testing engineer. Your job is to find loopholes, bugs, and missing test cases in any software project.

You think in 4 layers:
1. UNIT GAPS — individual functions with edge cases
2. INTEGRATION GAPS — two systems talking to each other, what breaks at the seams
3. FLOW GAPS — full user journeys nobody tested end to end
4. BREAK TESTS — adversarial scenarios where users do unexpected things

You know these failure patterns:
- Race conditions (two things at same time)
- Idempotency failures (same request sent twice)
- Tenant isolation leaks (one customer sees another's data)
- Webhook double-fires (payment systems sending same event twice)
- State loss (in-memory data gone on restart)
- Missing rollback (partial success leaving broken state)
- Silent failures (errors swallowed, never surfaced)
- Cascade failures (one system down takes others down)

PARWA CONTEXT:
- Multi-tenant SaaS platform for AI-powered customer support
- Three pricing tiers: Starter ($999/2K tickets), Growth ($2,499/5K tickets), High ($3,999/15K tickets)
- Payment model: Netflix-style - payment fails = STOP immediately, no refunds, no trials, no grace period
- Uses Paddle for billing, PostgreSQL for database, Redis for caching, Celery for background jobs
- Tenant isolation via company_id on all tables

IMPORTANT: You MUST respond in this EXACT format:

GAPS FOUND: [number]

GAP 1
Severity: CRITICAL
Title: [short title]
What breaks: [one sentence]
Real scenario: [concrete example with actual data]
AI agent prompt: [exact prompt to paste into coding AI to write this test]

GAP 2
Severity: HIGH
Title: [short title]
What breaks: [one sentence]
Real scenario: [concrete example]
AI agent prompt: [exact prompt]

[continue for all gaps]

Keep it tight and actionable. Every gap needs an AI agent prompt they can copy paste directly.
Find 3-7 gaps for any feature described."""


async def find_gaps(feature_description: str) -> str:
    """Use z-ai-web-dev-sdk to find gaps in the feature."""
    try:
        # Create a temporary Node.js script to call the SDK
        node_script = f'''
import ZAI from 'z-ai-web-dev-sdk';

async function main() {{
    const zai = await ZAI.create();
    
    const completion = await zai.chat.completions.create({{
        messages: [
            {{ role: 'system', content: {json.dumps(SYSTEM_PROMPT)} }},
            {{ role: 'user', content: {json.dumps(feature_description)} }}
        ],
        max_tokens: 4000
    }});
    
    console.log(completion.choices[0]?.message?.content || 'No response');
}}

main().catch(e => {{ console.error('Error:', e.message); process.exit(1); }});
'''
        
        # Write to temp file and execute
        with NamedTemporaryFile(mode='w', suffix='.mjs', delete=False, dir='/home/z/my-project/parwa') as f:
            f.write(node_script)
            temp_path = f.name
        
        result = subprocess.run(
            ['node', temp_path],
            capture_output=True,
            text=True,
            cwd='/home/z/my-project/parwa',
            timeout=120
        )
        
        # Clean up temp file
        Path(temp_path).unlink(missing_ok=True)
        
        if result.returncode != 0:
            return f"Error calling AI: {result.stderr}"
        
        return result.stdout.strip()
        
    except subprocess.TimeoutExpired:
        return "Error: AI request timed out"
    except Exception as e:
        return f"Error: {str(e)}"


def parse_gaps(text: str) -> dict:
    """Parse the AI response into structured gaps."""
    lines = text.split("\n")
    gaps = []
    current = None
    found_count = None
    
    for line in lines:
        line = line.strip()
        if line.startswith("GAPS FOUND:"):
            found_count = line.replace("GAPS FOUND:", "").strip()
            continue
        if line.startswith("GAP ") and len(line) > 4:
            # Extract number from "GAP 1" or "GAP 2" etc
            parts = line[4:].strip().split()
            if parts and parts[0].isdigit():
                if current:
                    gaps.append(current)
                current = {"severity": "MEDIUM", "title": "", "breaks": "", "scenario": "", "prompt": ""}
                continue
        if not current:
            continue
        if line.startswith("Severity:"):
            current["severity"] = line.replace("Severity:", "").strip().upper()
        elif line.startswith("Title:"):
            current["title"] = line.replace("Title:", "").strip()
        elif line.startswith("What breaks:"):
            current["breaks"] = line.replace("What breaks:", "").strip()
        elif line.startswith("Real scenario:"):
            current["scenario"] = line.replace("Real scenario:", "").strip()
        elif line.startswith("AI agent prompt:"):
            current["prompt"] = line.replace("AI agent prompt:", "").strip()
    
    if current:
        gaps.append(current)
    
    return {"found_count": found_count or len(gaps), "gaps": gaps, "raw_response": text}


def print_gaps(result: dict):
    """Pretty print the gaps to console."""
    print(f"\n{'='*60}")
    print(f"⚡ {result['found_count']} GAPS FOUND")
    print('='*60)
    
    if not result['gaps']:
        print("\nNo gaps found. Either:")
        print("  1. Your tests are comprehensive (great!)")
        print("  2. The feature description needs more detail")
        print("\nRaw AI response saved to JSON file.")
        return
    
    for i, gap in enumerate(result['gaps'], 1):
        sev_colors = {
            "CRITICAL": "\033[91m",  # Red
            "HIGH": "\033[93m",      # Yellow
            "MEDIUM": "\033[92m",    # Green
            "LOW": "\033[94m",       # Blue
        }
        color = sev_colors.get(gap['severity'], "\033[0m")
        reset = "\033[0m"
        
        print(f"\n┌─ GAP {i} ─────────────────────────────────────")
        print(f"│ {color}[{gap['severity']}]{reset} {gap['title']}")
        if gap['breaks']:
            print(f"│ Breaks: {gap['breaks']}")
        if gap['scenario']:
            print(f"│ Scenario: {gap['scenario']}")
        if gap['prompt']:
            print(f"│")
            print(f"│ AI PROMPT:")
            prompt_display = gap['prompt'][:150] + "..." if len(gap['prompt']) > 150 else gap['prompt']
            print(f"│ {prompt_display}")
        print(f"└──────────────────────────────────────────────")


# Pre-defined prompts for Week 5 Payment features
W5_PROMPTS = {
    "w5d1": """Week 5 Day 1: Paddle Client + Database Tables

I'm building the Paddle billing client and database tables for PARWA:
- PaddleClient class with methods: create_subscription, cancel_subscription, update_subscription, get_subscription
- Database tables: subscriptions, billing_events, invoices, payment_methods, overage_records
- Tenant isolation via company_id on all billing tables
- Paddle webhook signature verification using HMAC-SHA256

What testing gaps exist? Focus on: idempotency, tenant isolation, webhook security, race conditions.""",

    "w5d2": """Week 5 Day 2: Subscription Lifecycle + Webhook Handler

I'm building subscription lifecycle management and Paddle webhook handler:
- Subscription states: active, past_due, canceled, expired
- Webhook events: subscription_created, subscription_updated, subscription_canceled, payment_failed
- PaddleHandler.process_event() routing to correct handlers
- Automatic subscription state transitions on webhook events
- Tenant context propagation in webhook processing

What testing gaps exist? Focus on: state machine edge cases, webhook replay attacks, double-processing, partial failures.""",

    "w5d3": """Week 5 Day 3: Overage Detection + Auto-Charge

I'm building ticket overage detection and automatic charging:
- Daily Celery task checking ticket counts vs plan limits
- Overage rate: $0.10 per ticket over limit
- Automatic Paddle charge for overages
- Overage notification emails to customers
- Overage tracking in database

What testing gaps exist? Focus on: race conditions in counting, charge failures, partial overage handling, notification failures.""",

    "w5d4": """Week 5 Day 4: Payment Failure Handling

I'm building payment failure handling with Netflix-style immediate stop:
- Payment fails = subscription stops immediately (no grace period)
- No refunds, no trials, no second chances
- Automatic service suspension on payment failure
- Email notifications for payment failures
- Manual reactivation flow after payment update

What testing gaps exist? Focus on: timing of suspension, partial service states, reactivation edge cases, tenant data access after suspension.""",

    "w5d5": """Week 5 Day 5: Billing API Endpoints + Frontend Integration

I'm building billing API endpoints and frontend integration:
- GET /api/billing/subscription - current subscription details
- POST /api/billing/upgrade - upgrade plan
- POST /api/billing/cancel - cancel subscription
- GET /api/billing/invoices - invoice history
- Frontend components: pricing page, billing dashboard, plan comparison

What testing gaps exist? Focus on: API authorization, tenant isolation, race conditions in upgrades, frontend state sync.""",

    "w5d6": """Week 5 Day 6: Full Payment Flow E2E Testing

I'm building end-to-end tests for the complete payment flow:
- Customer signup → plan selection → Paddle checkout → subscription activation
- Monthly renewal → overage detection → auto-charge
- Payment failure → immediate suspension → payment update → reactivation
- Plan upgrade mid-cycle → prorated billing
- Subscription cancellation → service termination

What testing gaps exist? Focus on: full user journeys, timing edge cases, state consistency across services, recovery from failures.""",
}


def main():
    parser = argparse.ArgumentParser(description="PARWA Gap Finder - Find testing gaps in features")
    parser.add_argument("feature", nargs="?", help="Feature description or W5 day code (w5d1-w5d6)")
    parser.add_argument("--output", "-o", choices=["json", "text"], default="text", help="Output format")
    parser.add_argument("--list", "-l", action="store_true", help="List available W5 prompts")
    parser.add_argument("--raw", "-r", action="store_true", help="Show raw AI response")
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable Week 5 prompts:")
        for code, desc in W5_PROMPTS.items():
            print(f"  {code}: {desc.split(chr(10))[0].strip()}")
        print("\nUsage: python scripts/gap_finder.py w5d1")
        return
    
    if not args.feature:
        print("Usage: python scripts/gap_finder.py \"<feature description>\"")
        print("       python scripts/gap_finder.py w5d1  # for pre-defined Week 5 prompts")
        print("       python scripts/gap_finder.py --list  # show all W5 prompts")
        sys.exit(1)
    
    # Check if it's a W5 prompt code
    feature = W5_PROMPTS.get(args.feature.lower(), args.feature)
    
    print(f"\n🔍 Analyzing: {args.feature if args.feature in W5_PROMPTS else feature[:60]}...")
    print("⏳ Calling AI (this may take 10-30 seconds)...\n")
    
    # Run the gap finder
    result_text = asyncio.run(find_gaps(feature))
    
    if args.raw:
        print("\n" + "="*60)
        print("RAW AI RESPONSE:")
        print("="*60)
        print(result_text)
        print("="*60 + "\n")
    
    parsed = parse_gaps(result_text)
    
    if args.output == "json":
        print(json.dumps(parsed, indent=2))
    else:
        print_gaps(parsed)
    
    # Save to file
    output_file = Path("/home/z/my-project/parwa") / f"gap_analysis_{args.feature.replace(' ', '_')}.json"
    with open(output_file, "w") as f:
        json.dump(parsed, f, indent=2)
    print(f"\n📁 Full results saved to: {output_file}")


if __name__ == "__main__":
    main()
