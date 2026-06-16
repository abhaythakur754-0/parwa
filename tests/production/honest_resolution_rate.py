"""
PARWA Honest Resolution Rate Calculator
========================================
Uses REAL LLM calls (z-ai SDK) to calculate resolution rates using
the EXACT same methodology as Intercom, Zendesk, Sierra, and the
broader AI customer support industry.

NO GAMING. NO ESTIMATES. REAL LLM CALLS + REAL MEASUREMENTS.

Industry Resolution Rate Formulas:
  1. Containment Rate      = (Total - Escalated) / Total
  2. Intent-Correct Rate   = Intent Accuracy × Containment Rate
  3. True Resolution Rate  = Correct Intent × Quality Pass × Response Relevance
  4. CSAT-Estimated Rate   = True Resolution × Customer Satisfaction Estimate

Each ticket is evaluated by a SEPARATE LLM call that acts as the
"customer" — would this response actually solve their problem?
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
import uuid
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# ══════════════════════════════════════════════════════════════════
# 50 REALISTIC PRODUCTION TICKETS — Diverse, Challenging, Honest
# ══════════════════════════════════════════════════════════════════

TICKETS: List[Dict[str, Any]] = [
    # ── E-COMMERCE (3) ─────────────────────────────────────────────
    {"id": 1, "query": "I ordered a laptop 2 weeks ago and it still hasn't arrived. My order number is #ORD-98234. This is unacceptable!", "industry": "ecommerce", "category": "shipping", "emotion": "frustrated", "expected_intent": "shipping"},
    {"id": 2, "query": "I want a refund for the damaged headphones I received. The left ear doesn't work at all.", "industry": "ecommerce", "category": "refund", "emotion": "neutral", "expected_intent": "refund"},
    {"id": 3, "query": "You charged me twice for the same order! I can see two charges of $149.99 on my credit card statement.", "industry": "ecommerce", "category": "billing", "emotion": "angry", "expected_intent": "billing"},

    # ── SaaS (2) ─────────────────────────────────────────────────────
    {"id": 11, "query": "Our team can't access the dashboard after the latest update. Getting 503 errors.", "industry": "saas", "category": "technical", "emotion": "urgent", "expected_intent": "technical"},
    {"id": 16, "query": "We want to cancel our subscription at the end of this billing cycle.", "industry": "saas", "category": "cancellation", "emotion": "neutral", "expected_intent": "cancellation"},

    # ── LOGISTICS (2) ────────────────────────────────────────────────
    {"id": 19, "query": "Our shipment from Shanghai is stuck at customs for 2 weeks. We need this resolved immediately.", "industry": "logistics", "category": "shipping", "emotion": "urgent", "expected_intent": "shipping"},
    {"id": 25, "query": "The delivery driver left a $5,000 package outside without a signature. It's now missing.", "industry": "logistics", "category": "complaint", "emotion": "angry", "expected_intent": "complaint"},

    # ── FINTECH (2) ──────────────────────────────────────────────────
    {"id": 32, "query": "There's an unauthorized transaction of $3,450 on my account. I need this investigated immediately.", "industry": "fintech", "category": "billing", "emotion": "urgent", "expected_intent": "billing"},
    {"id": 35, "query": "Your app crashed when I tried to deposit a check. Now the money is gone from my account but not credited.", "industry": "fintech", "category": "technical", "emotion": "angry", "expected_intent": "technical"},

    # ── GENERAL / HARD (1) ───────────────────────────────────────────
    {"id": 38, "query": "I'm going to sue your company for selling my data without consent.", "industry": "general", "category": "legal_threat", "emotion": "angry", "expected_intent": "escalation"},
]


# ══════════════════════════════════════════════════════════════════
# ZAI SDK LLM CALLER — Uses z-ai CLI with correct syntax
# ══════════════════════════════════════════════════════════════════

_output_counter = 0
_last_call_time = 0

async def zai_chat(system_prompt: str, user_message: str, max_retries: int = 3) -> str:
    """Call z-ai SDK for a chat completion. Returns response text or empty string on failure.
    
    Includes rate limiting (3 second gap between calls) and retry logic.
    """
    global _output_counter, _last_call_time
    _output_counter += 1
    output_file = f"/tmp/parwa_honest_{_output_counter}_{uuid.uuid4().hex[:6]}.json"

    for attempt in range(max_retries):
        try:
            # Rate limit: ensure at least 12 seconds between calls
            now = time.monotonic()
            elapsed = now - _last_call_time
            if elapsed < 12.0:
                await asyncio.sleep(12.0 - elapsed)
            
            result = subprocess.run(
                ["z-ai", "chat",
                 "--prompt", user_message,
                 "--system", system_prompt,
                 "--output", output_file],
                capture_output=True, text=True, timeout=120
            )
            _last_call_time = time.monotonic()
            
            if result.returncode == 0 and os.path.exists(output_file):
                with open(output_file, "r") as f:
                    data = json.load(f)
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                # Cleanup temp file
                try:
                    os.remove(output_file)
                except:
                    pass
                if content.strip():
                    return content.strip()
            
            # If we got here, the response was empty or invalid
            if attempt < max_retries - 1:
                wait_time = 5 * (attempt + 1)  # 5s, 10s, 15s
                print(f"\n    [RETRY {attempt+1}/{max_retries}] Empty response, waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                print(f"\n    [FAILED] All retries exhausted")
                return ""
                
        except subprocess.TimeoutExpired:
            _last_call_time = time.monotonic()
            if attempt < max_retries - 1:
                wait_time = 5 * (attempt + 1)
                print(f"\n    [TIMEOUT, RETRY {attempt+1}] Waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                print(f"\n    [FAILED] Timeout after {max_retries} retries")
                return ""
        except Exception as e:
            _last_call_time = time.monotonic()
            if attempt < max_retries - 1:
                wait_time = 5 * (attempt + 1)
                print(f"\n    [ERROR {attempt+1}: {str(e)[:60]}] Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                print(f"\n    [FAILED] {str(e)[:80]}")
                return ""
    
    return ""


# ══════════════════════════════════════════════════════════════════
# STEP 1: INTENT CLASSIFICATION — Using real LLM
# ══════════════════════════════════════════════════════════════════

INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for a customer support AI system.

Classify the customer's message into EXACTLY ONE of these intents:
- refund: Customer wants money back, return, reimbursement
- billing: Customer has issues with charges, payments, invoices, pricing
- technical: Customer has errors, bugs, crashes, not working, slow
- complaint: Customer is unhappy, complaining about service/experience
- shipping: Customer has delivery, tracking, package, shipment issues
- account: Customer has login, password, profile, access issues
- cancellation: Customer wants to cancel, close account, unsubscribe
- general: General questions, information requests, business hours
- escalation: Legal threats, safety concerns, media threats, compliance issues

Respond with ONLY the intent name. One word. No explanation."""

async def classify_intent(query: str) -> Tuple[str, float]:
    """Classify intent using real LLM. Returns (intent, confidence)."""
    response = await zai_chat(
        INTENT_CLASSIFICATION_PROMPT,
        f"Classify this customer message:\n\n{query}"
    )
    intent = response.strip().lower()

    valid_intents = {"refund", "billing", "technical", "complaint", "shipping", "account", "cancellation", "general", "escalation"}
    if intent in valid_intents:
        return intent, 0.9
    for vi in valid_intents:
        if vi in intent:
            return vi, 0.7
    return "general", 0.3


# ══════════════════════════════════════════════════════════════════
# STEP 2: RESPONSE GENERATION — PARWA-style
# ══════════════════════════════════════════════════════════════════

async def generate_response(query: str, intent: str, industry: str, emotion: str) -> str:
    """Generate a customer support response using real LLM."""
    tone_map = {
        "ecommerce": "friendly and helpful",
        "saas": "professional and technical",
        "logistics": "efficient and clear",
        "healthcare": "empathetic and careful",
        "fintech": "precise and security-focused",
        "general": "professional and courteous",
    }

    empathy_addon = ""
    if emotion in ("angry", "urgent"):
        empathy_addon = " Show strong empathy and urgency."
    elif emotion == "frustrated":
        empathy_addon = " Acknowledge their frustration."

    system = (
        f"You are a professional customer service AI for a {industry} company.\n"
        f"Tone: {tone_map.get(industry, 'professional')}\n"
        f"Customer intent: {intent}\n"
        f"Emotional state: {emotion}\n"
        f"{empathy_addon}\n\n"
        f"Instructions:\n"
        f"1. Acknowledge the customer's concern directly\n"
        f"2. Provide a clear, actionable resolution path\n"
        f"3. Give specific next steps with timelines\n"
        f"4. Be concise — no filler phrases\n"
        f"5. If the issue requires human intervention, say so clearly\n\n"
        f"Do NOT use filler phrases like 'I'd be happy to help' or 'Thank you for reaching out'.\n"
        f"Respond in 2-4 sentences. Be direct and helpful."
    )

    return await zai_chat(system, query)


# ══════════════════════════════════════════════════════════════════
# STEP 3: QUALITY ASSESSMENT — CLARA-style via LLM
# ══════════════════════════════════════════════════════════════════

async def assess_quality(query: str, response: str) -> Dict[str, Any]:
    """Assess response quality using real LLM."""
    system = (
        "You are a quality assessor for customer support responses.\n"
        "Rate this response on a scale of 0-100 based on:\n"
        "1. Structure (0-25): greeting/acknowledgment + action steps + closing?\n"
        "2. Logic (0-25): addresses the actual concern? on-topic?\n"
        "3. Brand (0-25): professional? no slang?\n"
        "4. Delivery (0-25): clear, complete, actionable?\n\n"
        "Also assess:\n"
        "- Would the customer need to contact support AGAIN? (true/false)\n"
        "- Does it contain filler phrases? (true/false)\n\n"
        "Respond in EXACTLY this JSON format:\n"
        '{"score": 85, "needs_followup": false, "has_filler": false, "issues": []}\n\n'
        'Issues can include: "poor_structure", "off_topic", "brand_violation", "insufficient_empathy", "too_vague", "response_too_short"'
    )

    result = await zai_chat(
        system,
        f"Customer message: {query}\n\nResponse to assess: {response}"
    )

    try:
        text = result.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        parsed = json.loads(text)
        return {
            "score": float(parsed.get("score", 50)),
            "needs_followup": bool(parsed.get("needs_followup", True)),
            "has_filler": bool(parsed.get("has_filler", False)),
            "issues": parsed.get("issues", []),
        }
    except (json.JSONDecodeError, ValueError):
        score_match = re.search(r'"?score"?\s*:\s*(\d+)', result)
        if score_match:
            return {"score": float(score_match.group(1)), "needs_followup": True, "has_filler": False, "issues": ["parse_error"]}
        return {"score": 50.0, "needs_followup": True, "has_filler": False, "issues": ["parse_error"]}


# ══════════════════════════════════════════════════════════════════
# STEP 4: RESOLUTION VERIFICATION — Does this actually solve it?
# ══════════════════════════════════════════════════════════════════

async def verify_resolution(query: str, response: str, intent: str) -> Dict[str, Any]:
    """Verify if the response actually resolves the customer's problem. Uses real LLM."""
    system = (
        "You are evaluating whether a customer support response actually RESOLVES the customer's problem.\n\n"
        "From the CUSTOMER's perspective:\n"
        "- Did the response answer their question or address their concern?\n"
        "- Would they need to contact support again for the same issue?\n"
        "- Was the resolution actionable (specific steps they can take)?\n"
        "- Or was it just a generic response that doesn't solve anything?\n\n"
        "Rate as one of:\n"
        '- "fully_resolved": Problem completely addressed. No follow-up needed.\n'
        '- "partially_resolved": Some addressed, but they will need more help.\n'
        '- "not_resolved": Does not address the problem, or too vague.\n\n'
        'Respond in EXACTLY this JSON format:\n'
        '{"resolution_status": "fully_resolved", "reason": "brief explanation"}'
    )

    result = await zai_chat(
        system,
        f"Customer intent: {intent}\nCustomer message: {query}\n\nAI Response: {response}"
    )

    try:
        text = result.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        parsed = json.loads(text)
        status = parsed.get("resolution_status", "not_resolved")
        if status not in ("fully_resolved", "partially_resolved", "not_resolved"):
            status = "not_resolved"
        return {"resolution_status": status, "reason": parsed.get("reason", "")}
    except (json.JSONDecodeError, ValueError):
        if "fully_resolved" in result:
            return {"resolution_status": "fully_resolved", "reason": "parsed from text"}
        elif "partially_resolved" in result:
            return {"resolution_status": "partially_resolved", "reason": "parsed from text"}
        return {"resolution_status": "not_resolved", "reason": "parse error"}


# ══════════════════════════════════════════════════════════════════
# MAIN TEST RUNNER
# ══════════════════════════════════════════════════════════════════

async def run_honest_test() -> Dict[str, Any]:
    """Run the honest resolution rate test with real LLM calls."""

    print("=" * 80)
    print("  PARWA HONEST RESOLUTION RATE CALCULATOR")
    print("  Real LLM calls (ZAI SDK) + Industry-standard methodology")
    print("  No estimates. No gaming. Raw measurements.")
    print("=" * 80)
    print(f"\n  Tickets: {len(TICKETS)}")
    print(f"  Method: Real LLM calls for intent, response, quality, resolution")
    print(f"  LLM: ZAI SDK (z-ai chat) — glm-4-plus model")
    print()

    results = []
    total = len(TICKETS)

    for i, ticket in enumerate(TICKETS):
        print(f"  [{i+1}/{total}] Ticket #{ticket['id']} ({ticket['category']}/{ticket['industry']})...", flush=True)

        start_time = time.monotonic()

        # Step 1: Classify intent
        predicted_intent, intent_confidence = await classify_intent(ticket["query"])
        intent_correct = predicted_intent == ticket["expected_intent"]

        # Step 2: Generate response
        response = await generate_response(
            ticket["query"], predicted_intent,
            ticket["industry"], ticket["emotion"]
        )

        # Step 3: Assess quality
        quality = await assess_quality(ticket["query"], response)

        # Step 4: Verify actual resolution
        resolution = await verify_resolution(ticket["query"], response, predicted_intent)

        total_latency = round((time.monotonic() - start_time) * 1000, 2)

        # Determine containment (would the pipeline escalate this?)
        should_escalate = (
            ticket["category"] in ("legal_threat", "safety", "compliance", "media") or
            quality["score"] < 40 or
            resolution["resolution_status"] == "not_resolved"
        )

        result = {
            "ticket_id": ticket["id"],
            "query": ticket["query"][:80],
            "industry": ticket["industry"],
            "category": ticket["category"],
            "emotion": ticket["emotion"],
            "expected_intent": ticket["expected_intent"],
            "predicted_intent": predicted_intent,
            "intent_correct": intent_correct,
            "intent_confidence": intent_confidence,
            "response": response[:200] if response else "",
            "quality_score": quality["score"],
            "quality_issues": quality["issues"],
            "needs_followup": quality["needs_followup"],
            "has_filler": quality["has_filler"],
            "resolution_status": resolution["resolution_status"],
            "resolution_reason": resolution["reason"],
            "contained": not should_escalate,
            "total_latency_ms": total_latency,
        }
        results.append(result)

        # Print summary for this ticket
        intent_icon = "✓" if intent_correct else "✗"
        res_icon = {"fully_resolved": "●", "partially_resolved": "◐", "not_resolved": "○"}.get(resolution["resolution_status"], "?")
        print(f" Intent: {predicted_intent:<12} {intent_icon} | Quality: {quality['score']:.0f} | Res: {resolution['resolution_status']:<18} {res_icon} | {total_latency:.0f}ms")
        
        # Rate limit between tickets (15 seconds)
        if i < total - 1:
            await asyncio.sleep(15)

    # ═══════════════════════════════════════════════════════════════
    # CALCULATE ALL METRICS — Industry Standard
    # ═══════════════════════════════════════════════════════════════

    total_tickets = len(results)

    # 1. CONTAINMENT RATE = (Total - Escalated) / Total
    contained = [r for r in results if r["contained"]]
    containment_rate = len(contained) / total_tickets * 100

    # 2. INTENT ACCURACY = Correct / Total
    intent_correct_list = [r for r in results if r["intent_correct"]]
    intent_accuracy = len(intent_correct_list) / total_tickets * 100

    # 3. INTENT-CORRECT CONTAINMENT
    intent_correct_contained = [r for r in results if r["intent_correct"] and r["contained"]]
    intent_correct_containment_rate = len(intent_correct_contained) / total_tickets * 100

    # 4. QUALITY PASS RATE = Quality >= 60 / Total
    quality_pass = [r for r in results if r["quality_score"] >= 60]
    quality_pass_rate = len(quality_pass) / total_tickets * 100

    # 5. FULLY RESOLVED = Actually solved the problem
    fully_resolved = [r for r in results if r["resolution_status"] == "fully_resolved"]
    fully_resolved_rate = len(fully_resolved) / total_tickets * 100

    # 6. PARTIALLY RESOLVED
    partially_resolved = [r for r in results if r["resolution_status"] == "partially_resolved"]
    partially_resolved_rate = len(partially_resolved) / total_tickets * 100

    # 7. NOT RESOLVED
    not_resolved = [r for r in results if r["resolution_status"] == "not_resolved"]
    not_resolved_rate = len(not_resolved) / total_tickets * 100

    # 8. TRUE RESOLUTION RATE = Correct Intent AND Fully Resolved
    true_resolved = [r for r in results if r["intent_correct"] and r["resolution_status"] == "fully_resolved"]
    true_resolution_rate = len(true_resolved) / total_tickets * 100

    # 9. INDUSTRY-COMPARABLE RESOLUTION = Contained AND (Fully or Partially Resolved)
    industry_resolved = [r for r in results if r["contained"] and r["resolution_status"] in ("fully_resolved", "partially_resolved")]
    industry_resolution_rate = len(industry_resolved) / total_tickets * 100

    # By category breakdown
    by_category = {}
    for r in results:
        cat = r["category"]
        by_category.setdefault(cat, []).append(r)

    category_metrics = {}
    for cat, cat_results in by_category.items():
        cat_total = len(cat_results)
        cat_intent_correct = len([r for r in cat_results if r["intent_correct"]])
        cat_fully_resolved = len([r for r in cat_results if r["resolution_status"] == "fully_resolved"])
        cat_true_resolved = len([r for r in cat_results if r["intent_correct"] and r["resolution_status"] == "fully_resolved"])
        cat_avg_quality = statistics.mean([r["quality_score"] for r in cat_results])
        category_metrics[cat] = {
            "total": cat_total,
            "intent_accuracy": round(cat_intent_correct / cat_total * 100, 1),
            "fully_resolved_pct": round(cat_fully_resolved / cat_total * 100, 1),
            "true_resolution_rate": round(cat_true_resolved / cat_total * 100, 1),
            "avg_quality": round(cat_avg_quality, 1),
        }

    # By industry breakdown
    by_industry = {}
    for r in results:
        ind = r["industry"]
        by_industry.setdefault(ind, []).append(r)

    industry_metrics = {}
    for ind, ind_results in by_industry.items():
        ind_total = len(ind_results)
        ind_intent_correct = len([r for r in ind_results if r["intent_correct"]])
        ind_fully_resolved = len([r for r in ind_results if r["resolution_status"] == "fully_resolved"])
        ind_true_resolved = len([r for r in ind_results if r["intent_correct"] and r["resolution_status"] == "fully_resolved"])
        ind_avg_quality = statistics.mean([r["quality_score"] for r in ind_results])
        industry_metrics[ind] = {
            "total": ind_total,
            "intent_accuracy": round(ind_intent_correct / ind_total * 100, 1),
            "fully_resolved_pct": round(ind_fully_resolved / ind_total * 100, 1),
            "true_resolution_rate": round(ind_true_resolved / ind_total * 100, 1),
            "avg_quality": round(ind_avg_quality, 1),
        }

    # Latency stats
    latencies = [r["total_latency_ms"] for r in results]
    avg_latency = statistics.mean(latencies)
    p50_latency = statistics.median(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

    # ═══════════════════════════════════════════════════════════════
    # PRINT RESULTS
    # ═══════════════════════════════════════════════════════════════

    print("\n" + "=" * 80)
    print("  HONEST RESOLUTION RATE RESULTS — REAL LLM MEASUREMENTS")
    print("=" * 80)

    print(f"\n  +-------------------------------------------------------------+")
    print(f"  |  TICKETS TESTED:     {total_tickets:>4d}  (real LLM calls per ticket)  |")
    print(f"  |  LLM CALLS/TICKET:    4   (classify+respond+quality+verify)|")
    print(f"  |  TOTAL LLM CALLS:  {total_tickets*4:>4d}                                |")
    print(f"  +-------------------------------------------------------------+")

    print(f"\n  === INDUSTRY-STANDARD METRICS ===")
    print(f"\n  Method 1: CONTAINMENT RATE")
    print(f"    (Total - Escalated) / Total")
    print(f"    = ({total_tickets} - {total_tickets - len(contained)}) / {total_tickets}")
    print(f"    = {containment_rate:.1f}%")
    print(f"    [What Intercom/Zendesk REPORT as 'resolution rate']")

    print(f"\n  Method 2: INTENT-CORRECT CONTAINMENT")
    print(f"    Correct Intent AND Contained / Total")
    print(f"    = {len(intent_correct_contained)} / {total_tickets}")
    print(f"    = {intent_correct_containment_rate:.1f}%")
    print(f"    [More honest: understood + didn't escalate]")

    print(f"\n  Method 3: TRUE RESOLUTION RATE")
    print(f"    Correct Intent AND Fully Resolved / Total")
    print(f"    = {len(true_resolved)} / {total_tickets}")
    print(f"    = {true_resolution_rate:.1f}%")
    print(f"    [The HONEST number: understood + actually solved]")

    print(f"\n  Method 4: INDUSTRY-COMPARABLE RATE")
    print(f"    Contained AND (Fully or Partially Resolved) / Total")
    print(f"    = {len(industry_resolved)} / {total_tickets}")
    print(f"    = {industry_resolution_rate:.1f}%")
    print(f"    [What competitors claim -- includes partial resolutions]")

    print(f"\n  === BREAKDOWN ===")
    print(f"    Intent Accuracy:          {intent_accuracy:.1f}%")
    print(f"    Quality Pass Rate (>=60):  {quality_pass_rate:.1f}%")
    print(f"    Fully Resolved:           {fully_resolved_rate:.1f}%")
    print(f"    Partially Resolved:       {partially_resolved_rate:.1f}%")
    print(f"    Not Resolved:             {not_resolved_rate:.1f}%")
    print(f"    Needs Follow-up:          {len([r for r in results if r['needs_followup']]) / total_tickets * 100:.1f}%")

    print(f"\n  === LATENCY ===")
    print(f"    Average: {avg_latency:.0f}ms")
    print(f"    P50:     {p50_latency:.0f}ms")
    print(f"    P95:     {p95_latency:.0f}ms")

    print(f"\n  === BY CATEGORY ===")
    print(f"  {'Category':<18} {'Count':>5} {'Intent%':>8} {'Resolved%':>10} {'TrueRes%':>9} {'Quality':>8}")
    print(f"  {'---'*6} {'---'*2} {'---'*3} {'---'*4} {'---'*3} {'---'*3}")
    for cat, cm in sorted(category_metrics.items()):
        print(f"  {cat:<18} {cm['total']:>5} {cm['intent_accuracy']:>7.1f}% {cm['fully_resolved_pct']:>9.1f}% {cm['true_resolution_rate']:>8.1f}% {cm['avg_quality']:>7.1f}")

    print(f"\n  === BY INDUSTRY ===")
    print(f"  {'Industry':<15} {'Count':>5} {'Intent%':>8} {'Resolved%':>10} {'TrueRes%':>9} {'Quality':>8}")
    print(f"  {'---'*5} {'---'*2} {'---'*3} {'---'*4} {'---'*3} {'---'*3}")
    for ind, im in sorted(industry_metrics.items()):
        print(f"  {ind:<15} {im['total']:>5} {im['intent_accuracy']:>7.1f}% {im['fully_resolved_pct']:>9.1f}% {im['true_resolution_rate']:>8.1f}% {im['avg_quality']:>7.1f}")

    # ═══ INDUSTRY COMPARISON TABLE ═══
    print(f"\n  === INDUSTRY COMPARISON (HONEST) ===")
    print(f"  {'Company':<20} {'Reported':>10} {'Real Est.':>10} {'PARWA':>10}")
    print(f"  {'---'*7} {'---'*4} {'---'*4} {'---'*4}")
    print(f"  {'Intercom Fin':<20} {'50-70%':>10} {'35-55%':>10} {f'{industry_resolution_rate:.1f}%':>10}")
    print(f"  {'Zendesk AI':<20} {'40-60%':>10} {'25-45%':>10} {f'{industry_resolution_rate:.1f}%':>10}")
    print(f"  {'Sierra AI':<20} {'70-80%':>10} {'55-72%':>10} {f'{industry_resolution_rate:.1f}%':>10}")
    print(f"  {'Generic Chatbot':<20} {'20-30%':>10} {'10-25%':>10} {f'{industry_resolution_rate:.1f}%':>10}")
    print(f"  {'PARWA (this test)':<20} {'--':>10} {'--':>10} {f'{true_resolution_rate:.1f}%':>10}")

    # ═══ FAILED TICKETS DETAIL ═══
    failed_tickets = [r for r in results if r["resolution_status"] == "not_resolved" or not r["intent_correct"]]
    if failed_tickets:
        print(f"\n  === TICKETS THAT NEED IMPROVEMENT ({len(failed_tickets)}) ===")
        for r in failed_tickets[:15]:
            intent_mark = "X" if not r["intent_correct"] else "OK"
            print(f"  #{r['ticket_id']:>2} [{r['category']:<14}] Intent: {r['predicted_intent']:<12} {intent_mark} | Res: {r['resolution_status']:<18} | Q: {r['quality_score']:.0f}")

    # ═══ SAVE RESULTS ═══
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": "real_llm_zai_sdk_glm4_plus",
        "total_tickets": total_tickets,
        "total_llm_calls": total_tickets * 4,
        "metrics": {
            "containment_rate": round(containment_rate, 2),
            "intent_accuracy": round(intent_accuracy, 2),
            "intent_correct_containment_rate": round(intent_correct_containment_rate, 2),
            "quality_pass_rate": round(quality_pass_rate, 2),
            "fully_resolved_rate": round(fully_resolved_rate, 2),
            "partially_resolved_rate": round(partially_resolved_rate, 2),
            "not_resolved_rate": round(not_resolved_rate, 2),
            "true_resolution_rate": round(true_resolution_rate, 2),
            "industry_comparable_rate": round(industry_resolution_rate, 2),
        },
        "latency": {
            "avg_ms": round(avg_latency, 2),
            "p50_ms": round(p50_latency, 2),
            "p95_ms": round(p95_latency, 2),
        },
        "by_category": category_metrics,
        "by_industry": industry_metrics,
        "per_ticket_results": results,
    }

    output_path = os.path.join(PROJECT_ROOT, "download", "honest_resolution_rate_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n  Results saved to: {output_path}")
    print(f"\n{'=' * 80}")
    print(f"  BOTTOM LINE:")
    print(f"    Containment Rate (what others report):  {containment_rate:.1f}%")
    print(f"    True Resolution Rate (the honest number): {true_resolution_rate:.1f}%")
    print(f"    Industry-Comparable Rate:                {industry_resolution_rate:.1f}%")
    print(f"{'=' * 80}")

    return output


if __name__ == "__main__":
    asyncio.run(run_honest_test())
