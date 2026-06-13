"""Month 2 Evaluation Dataset — 200+ messages with ground truth labels.

Split into:
- 100 intent classification messages (10 per intent category)
- 50 sentiment analysis messages (balanced across angry/frustrated/happy/neutral)
- 50 escalation decision messages (25 should-escalate, 25 should-not-escalate)
- 20 edge case messages (multi-intent, ambiguous, adversarial)

Each message includes:
- message: The customer's raw text
- expected_intent: One of 10 IntentType values
- expected_sentiment: One of 4 SentimentType values
- expected_escalation: bool
- complexity: simple/medium/complex/critical
- customer_context: Optional dict with order/CRM context for context-aware testing
- tags: List of tags for categorization (e.g., "edge_case", "multi_issue")
"""

from __future__ import annotations


# ════════════════════════════════════════════════════════════════════════════════
# INTENT CLASSIFICATION DATASET (100 messages — 10 per intent)
# ════════════════════════════════════════════════════════════════════════════════

INTENT_DATASET = [
    # ─── refund_request (10 messages) ────────────────────────────────────────
    {"message": "I was charged twice for the same order on January 5th, please refund the duplicate $49.99 charge", "expected_intent": "refund_request", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {"order_id": "ORD-7821", "amount": "$49.99"}, "tags": ["duplicate_charge"]},
    {"message": "Can I get my money back? The product I received is completely different from what was advertised.", "expected_intent": "refund_request", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["product_mismatch"]},
    {"message": "You charged me $189.99 twice! I want a refund immediately.", "expected_intent": "refund_request", "expected_sentiment": "angry", "expected_escalation": False, "complexity": "simple", "customer_context": {"amount": "$189.99"}, "tags": ["duplicate_charge", "angry"]},
    {"message": "I need a refund for my order. The item arrived damaged with a cracked screen.", "expected_intent": "refund_request", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["damaged_product"]},
    {"message": "Please process a refund for order #ORD-4521. The subscription was cancelled but I was still billed.", "expected_intent": "refund_request", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {"order_id": "ORD-4521"}, "tags": ["billing_error"]},
    {"message": "I returned my item two weeks ago and still haven't received my refund. What's the status?", "expected_intent": "refund_request", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["delayed_refund"]},
    {"message": "The automatic renewal charged my card but I never signed up for it. I want my money back.", "expected_intent": "refund_request", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["unauthorized_charge"]},
    {"message": "Reimburse me for the defective headphones. I sent them back 3 weeks ago.", "expected_intent": "refund_request", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["delayed_refund"]},
    {"message": "I want a refund. Your product is garbage and nothing like the description.", "expected_intent": "refund_request", "expected_sentiment": "angry", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["angry", "product_dissatisfaction"]},
    {"message": "Double charge on my credit card statement for order #ORD-9923, please process refund", "expected_intent": "refund_request", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {"order_id": "ORD-9923"}, "tags": ["duplicate_charge"]},

    # ─── order_status (10 messages) ──────────────────────────────────────────
    {"message": "Where is my order? It's been 10 days and I haven't received anything.", "expected_intent": "order_status", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["delayed_delivery"]},
    {"message": "Can you tell me the delivery status of my order #ORD-12345?", "expected_intent": "order_status", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {"order_id": "ORD-12345"}, "tags": []},
    {"message": "Has my package shipped yet? I need it by Friday for a gift.", "expected_intent": "order_status", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["time_sensitive"]},
    {"message": "My tracking number shows no updates for a week. Where is my order?", "expected_intent": "order_status", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["tracking_issue"]},
    {"message": "I ordered 5 days ago and still no shipping confirmation email.", "expected_intent": "order_status", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["no_confirmation"]},
    {"message": "Check the status of my recent purchase. Order should have arrived by now.", "expected_intent": "order_status", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "When will my delivery arrive? The tracking link doesn't work.", "expected_intent": "order_status", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["tracking_issue"]},
    {"message": "I need tracking info for order #ORD-5678, placed on December 15th.", "expected_intent": "order_status", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {"order_id": "ORD-5678"}, "tags": []},
    {"message": "My order status page shows 'processing' for 2 weeks. Is something wrong?", "expected_intent": "order_status", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["stuck_processing"]},
    {"message": "Just wondering when my order will be delivered, no rush.", "expected_intent": "order_status", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["casual"]},

    # ─── cancellation (10 messages) ──────────────────────────────────────────
    {"message": "I want to cancel my subscription effective immediately.", "expected_intent": "cancellation", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["subscription"]},
    {"message": "Please cancel order #ORD-67890, I no longer need the items.", "expected_intent": "cancellation", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {"order_id": "ORD-67890"}, "tags": ["order_cancellation"]},
    {"message": "Cancel my account right now. I'm done with this terrible service.", "expected_intent": "cancellation", "expected_sentiment": "angry", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["angry", "account_cancellation"]},
    {"message": "I need to stop my recurring payments. The service was supposed to end last month.", "expected_intent": "cancellation", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["recurring_billing"]},
    {"message": "How do I cancel my plan? I want to switch to a different provider.", "expected_intent": "cancellation", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "Please cancel my monthly subscription before the next billing cycle on the 1st.", "expected_intent": "cancellation", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["time_sensitive"]},
    {"message": "I want to cancel the Pro plan and downgrade to the free tier.", "expected_intent": "cancellation", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["downgrade"]},
    {"message": "Cancel my order before it ships. I found a better deal elsewhere.", "expected_intent": "cancellation", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["order_cancellation"]},
    {"message": "I need to terminate my contract immediately. The service doesn't meet our needs.", "expected_intent": "cancellation", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["contract_termination"]},
    {"message": "Stop order #ORD-11111 and refund the payment please.", "expected_intent": "cancellation", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "medium", "customer_context": {"order_id": "ORD-11111"}, "tags": ["multi_issue", "cancel_and_refund"]},

    # ─── technical_support (10 messages) ─────────────────────────────────────
    {"message": "Your app keeps crashing when I try to open settings on my iPhone.", "expected_intent": "technical_support", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["mobile"]},
    {"message": "The integration with Slack is broken and not syncing messages properly.", "expected_intent": "technical_support", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["integration"]},
    {"message": "I cannot log in to my account, it shows a 500 error every time.", "expected_intent": "technical_support", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["login_issue"]},
    {"message": "The API is returning unexpected results. It worked fine yesterday.", "expected_intent": "technical_support", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["api"]},
    {"message": "My dashboard shows a blank screen after the latest update.", "expected_intent": "technical_support", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["ui_bug"]},
    {"message": "How do I fix the connection error between my CRM and your platform?", "expected_intent": "technical_support", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "complex", "customer_context": {}, "tags": ["integration"]},
    {"message": "The export function is not working — it downloads a corrupted CSV file.", "expected_intent": "technical_support", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["export_bug"]},
    {"message": "Dead pixels appeared on my monitor after the firmware update. Can you help?", "expected_intent": "technical_support", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["hardware"]},
    {"message": "Webhook notifications stopped working 3 days ago. No errors in the logs.", "expected_intent": "technical_support", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "complex", "customer_context": {}, "tags": ["webhook", "debugging"]},
    {"message": "The plugin pack causes my browser to freeze. I'm using Chrome 120.", "expected_intent": "technical_support", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["plugin", "browser"]},

    # ─── billing_issue (10 messages) ─────────────────────────────────────────
    {"message": "My invoice shows the wrong amount. I was charged $200 instead of $150.", "expected_intent": "billing_issue", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {"amount": "$200 vs $150"}, "tags": ["wrong_amount"]},
    {"message": "I was overcharged on my last bill. Can you explain these extra charges?", "expected_intent": "billing_issue", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["overcharged"]},
    {"message": "Why is there a $29.99 charge on my statement I didn't authorize?", "expected_intent": "billing_issue", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {"amount": "$29.99"}, "tags": ["unauthorized"]},
    {"message": "My payment method was charged but I never received a receipt or confirmation.", "expected_intent": "billing_issue", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["missing_receipt"]},
    {"message": "The billing cycle changed without notice. My invoice is completely different.", "expected_intent": "billing_issue", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["cycle_change"]},
    {"message": "My card was declined and now my account is suspended. Please fix this!", "expected_intent": "billing_issue", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["payment_declined"]},
    {"message": "I see a charge for a subscription I don't have. What is this about?", "expected_intent": "billing_issue", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["mystery_charge"]},
    {"message": "Can you explain the tax calculation on my latest invoice? It seems incorrect.", "expected_intent": "billing_issue", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["tax_issue"]},
    {"message": "I was charged for a subscription I cancelled last month. This is the second time!", "expected_intent": "billing_issue", "expected_sentiment": "angry", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["recurring_issue", "angry"]},
    {"message": "The promotional discount wasn't applied to my bill. I signed up with code SAVE20.", "expected_intent": "billing_issue", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["discount"]},

    # ─── account_modification (10 messages) ──────────────────────────────────
    {"message": "Can you update my email address from old@example.com to new@example.com?", "expected_intent": "account_modification", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["email_change"]},
    {"message": "I need to change the phone number on my account to +1-555-0199.", "expected_intent": "account_modification", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["phone_change"]},
    {"message": "Update my billing address to 123 New Street, New York, NY 10001.", "expected_intent": "account_modification", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["address_change"]},
    {"message": "Please add 5 more seats to my team plan. We're growing.", "expected_intent": "account_modification", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["seat_addition"]},
    {"message": "I want to upgrade from the basic plan to the professional plan.", "expected_intent": "account_modification", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["plan_upgrade"]},
    {"message": "Can you reactivate my account? It was suspended by mistake.", "expected_intent": "account_modification", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["reactivation"]},
    {"message": "I need to change my company name from 'Old Corp' to 'New Corp Inc.' on the account.", "expected_intent": "account_modification", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["company_name"]},
    {"message": "Please switch my payment method from credit card to bank transfer.", "expected_intent": "account_modification", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["payment_method"]},
    {"message": "I need to add admin privileges for user john@company.com on our account.", "expected_intent": "account_modification", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["permissions"]},
    {"message": "Transfer my account to a different region/data center. We moved to Europe.", "expected_intent": "account_modification", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "complex", "customer_context": {}, "tags": ["region_transfer"]},

    # ─── faq_question (10 messages) ──────────────────────────────────────────
    {"message": "What is your return policy?", "expected_intent": "faq_question", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "Do you offer refunds for digital products?", "expected_intent": "faq_question", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "What are your business hours for phone support?", "expected_intent": "faq_question", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "How do I reset my password?", "expected_intent": "faq_question", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "What shipping options do you have available?", "expected_intent": "faq_question", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "Can you tell me about your pricing plans and what's included?", "expected_intent": "faq_question", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "What payment methods do you accept?", "expected_intent": "faq_question", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "Do you offer enterprise or volume discounts?", "expected_intent": "faq_question", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "What warranty coverage do you provide for hardware products?", "expected_intent": "faq_question", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "How long does the free trial last and what features are included?", "expected_intent": "faq_question", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},

    # ─── complaint (10 messages) ─────────────────────────────────────────────
    {"message": "This is the worst service I have ever experienced. Absolutely terrible.", "expected_intent": "complaint", "expected_sentiment": "angry", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["angry"]},
    {"message": "I am extremely disappointed with the quality of your product. Not worth the price.", "expected_intent": "complaint", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "Your customer service is unacceptable. I have been waiting for hours on hold.", "expected_intent": "complaint", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["wait_time"]},
    {"message": "I have never dealt with such an unprofessional company. This is ridiculous.", "expected_intent": "complaint", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "Your shipping is incredibly slow. Two weeks and no update. Worst experience ever.", "expected_intent": "complaint", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["shipping"]},
    {"message": "The product quality has severely declined. This used to be a good brand.", "expected_intent": "complaint", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["quality_decline"]},
    {"message": "Your website is misleading. The product doesn't match the description at all.", "expected_intent": "complaint", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["misleading"]},
    {"message": "I've had nothing but problems since I signed up. Very disappointed.", "expected_intent": "complaint", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "Your team promised a callback but nobody ever called. This is the third time.", "expected_intent": "complaint", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["broken_promise"]},
    {"message": "The onboarding process was a nightmare. Your documentation is outdated and confusing.", "expected_intent": "complaint", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "customer_context": {}, "tags": ["onboarding"]},

    # ─── escalation (10 messages) ────────────────────────────────────────────
    {"message": "I need to speak to a manager right now about this ongoing issue.", "expected_intent": "escalation", "expected_sentiment": "angry", "expected_escalation": True, "complexity": "simple", "customer_context": {}, "tags": ["manager_request"]},
    {"message": "Connect me with a supervisor immediately. Your agents can't help me.", "expected_intent": "escalation", "expected_sentiment": "frustrated", "expected_escalation": True, "complexity": "simple", "customer_context": {}, "tags": ["supervisor_request"]},
    {"message": "I want to talk to someone who can actually resolve this problem.", "expected_intent": "escalation", "expected_sentiment": "frustrated", "expected_escalation": True, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "Transfer me to a human agent. This chatbot is not helping at all.", "expected_intent": "escalation", "expected_sentiment": "frustrated", "expected_escalation": True, "complexity": "simple", "customer_context": {}, "tags": ["human_request"]},
    {"message": "Let me speak to your manager. I've been dealing with this for weeks.", "expected_intent": "escalation", "expected_sentiment": "angry", "expected_escalation": True, "complexity": "simple", "customer_context": {}, "tags": ["manager_request"]},
    {"message": "I will contact my attorney about this fraud on my account.", "expected_intent": "escalation", "expected_sentiment": "angry", "expected_escalation": True, "complexity": "critical", "customer_context": {}, "tags": ["legal_threat"]},
    {"message": "This is illegal and I am going to take legal action against your company.", "expected_intent": "escalation", "expected_sentiment": "angry", "expected_escalation": True, "complexity": "critical", "customer_context": {}, "tags": ["legal_threat"]},
    {"message": "I will sue your company for breach of contract if this isn't resolved today.", "expected_intent": "escalation", "expected_sentiment": "angry", "expected_escalation": True, "complexity": "critical", "customer_context": {}, "tags": ["legal_threat"]},
    {"message": "My attorney will be in touch regarding this matter. Expect formal correspondence.", "expected_intent": "escalation", "expected_sentiment": "angry", "expected_escalation": True, "complexity": "critical", "customer_context": {}, "tags": ["legal_threat"]},
    {"message": "This is fraud and I am reporting you to the authorities and the BBB.", "expected_intent": "escalation", "expected_sentiment": "angry", "expected_escalation": True, "complexity": "critical", "customer_context": {}, "tags": ["legal_threat", "regulatory"]},

    # ─── general_inquiry (10 messages) ────────────────────────────────────────
    {"message": "Hello, I was wondering what enterprise support options are available for our company?", "expected_intent": "general_inquiry", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "Thanks for your help, everything is great. Just wanted to say hi!", "expected_intent": "general_inquiry", "expected_sentiment": "happy", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["positive"]},
    {"message": "I just wanted to say great job on the new features!", "expected_intent": "general_inquiry", "expected_sentiment": "happy", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["praise"]},
    {"message": "I have a question about my account but I'm not sure what category it falls under.", "expected_intent": "general_inquiry", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["ambiguous"]},
    {"message": "Can someone help me figure out which plan is right for my team?", "expected_intent": "general_inquiry", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "Hello, how are you today? I'm just checking in.", "expected_intent": "general_inquiry", "expected_sentiment": "happy", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "I'm interested in learning more about your company and services.", "expected_intent": "general_inquiry", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "Do you have a partner or reseller program?", "expected_intent": "general_inquiry", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "I'd like to schedule a demo of your platform for our executive team.", "expected_intent": "general_inquiry", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": []},
    {"message": "Great experience so far! Looking forward to exploring more features.", "expected_intent": "general_inquiry", "expected_sentiment": "happy", "expected_escalation": False, "complexity": "simple", "customer_context": {}, "tags": ["positive"]},
]


# ════════════════════════════════════════════════════════════════════════════════
# SENTIMENT ANALYSIS DATASET (50 messages — balanced across 4 sentiments)
# ════════════════════════════════════════════════════════════════════════════════

SENTIMENT_DATASET = [
    # ─── ANGRY (15 messages) ─────────────────────────────────────────────────
    {"message": "I am absolutely furious! I will contact my attorney about this fraud!", "expected_sentiment": "angry", "expected_urgency": 0.9, "tags": ["legal_threat"]},
    {"message": "This is outrageous! I demand to speak to a manager right now!", "expected_sentiment": "angry", "expected_urgency": 0.95, "tags": ["manager_demand"]},
    {"message": "I've had it with this company! Four attempts and nobody has responded!", "expected_sentiment": "angry", "expected_urgency": 0.9, "tags": ["repeated_contact"]},
    {"message": "Your service is a complete scam! I want all my money back immediately!", "expected_sentiment": "angry", "expected_urgency": 0.85, "tags": ["scam_accusation"]},
    {"message": "I'm going to report this to the authorities! This is illegal!", "expected_sentiment": "angry", "expected_urgency": 0.95, "tags": ["regulatory"]},
    {"message": "This is the third time I'm writing and I'm beyond angry. Fix this NOW.", "expected_sentiment": "angry", "expected_urgency": 0.9, "tags": ["repeated_contact"]},
    {"message": "How dare you charge my card without authorization! I'm disgusted!", "expected_sentiment": "angry", "expected_urgency": 0.9, "tags": ["unauthorized_charge"]},
    {"message": "I will sue your company for this breach of contract!", "expected_sentiment": "angry", "expected_urgency": 0.95, "tags": ["legal_threat"]},
    {"message": "Nobody has helped me after 5 emails! This is the worst company ever!", "expected_sentiment": "angry", "expected_urgency": 0.85, "tags": ["no_response"]},
    {"message": "I demand immediate action! This is completely unacceptable and I won't stand for it!", "expected_sentiment": "angry", "expected_urgency": 0.9, "tags": ["demand"]},
    {"message": "Your fraud department needs to explain these charges or my lawyer gets involved!", "expected_sentiment": "angry", "expected_urgency": 0.95, "tags": ["legal_threat"]},
    {"message": "This is the worst experience of my life. I am OUTRAGED by this treatment!", "expected_sentiment": "angry", "expected_urgency": 0.85, "tags": ["outrage"]},
    {"message": "Unbelievable! You people are thieves! I demand a resolution right this second!", "expected_sentiment": "angry", "expected_urgency": 0.9, "tags": ["accusation"]},
    {"message": "My attorney will hear about this. I'm not letting this go.", "expected_sentiment": "angry", "expected_urgency": 0.9, "tags": ["legal_threat"]},
    {"message": "I'm going to sue. This is fraud and I have proof of your illegal activities.", "expected_sentiment": "angry", "expected_urgency": 0.95, "tags": ["legal_threat"]},

    # ─── FRUSTRATED (15 messages) ────────────────────────────────────────────
    {"message": "I've been waiting for two weeks and my order still hasn't arrived.", "expected_sentiment": "frustrated", "expected_urgency": 0.6, "tags": ["delayed"]},
    {"message": "This is really frustrating. I've tried everything and nothing works.", "expected_sentiment": "frustrated", "expected_urgency": 0.55, "tags": []},
    {"message": "I'm very disappointed with the quality. Not what I expected at all.", "expected_sentiment": "frustrated", "expected_urgency": 0.5, "tags": ["quality"]},
    {"message": "Why is this so complicated? I just want to update my account settings.", "expected_sentiment": "frustrated", "expected_urgency": 0.45, "tags": ["complexity"]},
    {"message": "I was charged twice for the same order. This shouldn't be so hard to fix.", "expected_sentiment": "frustrated", "expected_urgency": 0.65, "tags": ["duplicate_charge"]},
    {"message": "The app keeps crashing and I've lost all my work twice today.", "expected_sentiment": "frustrated", "expected_urgency": 0.7, "tags": ["data_loss"]},
    {"message": "Your website said 2-day shipping but it's been 8 days. Not happy.", "expected_sentiment": "frustrated", "expected_urgency": 0.6, "tags": ["shipping_delay"]},
    {"message": "I can't believe the billing is wrong again. This is the second month.", "expected_sentiment": "frustrated", "expected_urgency": 0.7, "tags": ["recurring_billing"]},
    {"message": "This process is unnecessarily complicated. Can someone just help me?", "expected_sentiment": "frustrated", "expected_urgency": 0.55, "tags": []},
    {"message": "The product doesn't match what was shown on the website. Very misleading.", "expected_sentiment": "frustrated", "expected_urgency": 0.5, "tags": ["misleading"]},
    {"message": "I've been on hold for 30 minutes. This is really inconvenient.", "expected_sentiment": "frustrated", "expected_urgency": 0.55, "tags": ["wait_time"]},
    {"message": "Still waiting for my refund from 3 weeks ago. Unacceptable delay.", "expected_sentiment": "frustrated", "expected_urgency": 0.65, "tags": ["refund_delay"]},
    {"message": "The integration broke after your last update and no one told us.", "expected_sentiment": "frustrated", "expected_urgency": 0.6, "tags": ["integration"]},
    {"message": "I'm disappointed that the feature I paid for doesn't work as advertised.", "expected_sentiment": "frustrated", "expected_urgency": 0.55, "tags": ["feature_broken"]},
    {"message": "This is the second time my account was suspended by mistake. Please fix it.", "expected_sentiment": "frustrated", "expected_urgency": 0.7, "tags": ["recurring_issue"]},

    # ─── HAPPY (10 messages) ─────────────────────────────────────────────────
    {"message": "Thank you so much! Your team resolved my issue perfectly.", "expected_sentiment": "happy", "expected_urgency": 0.1, "tags": []},
    {"message": "Great service! I'm really impressed with how fast this was handled.", "expected_sentiment": "happy", "expected_urgency": 0.1, "tags": []},
    {"message": "This is exactly what I needed. Thanks for the quick response!", "expected_sentiment": "happy", "expected_urgency": 0.1, "tags": []},
    {"message": "Love the new update! The dashboard is much better now.", "expected_sentiment": "happy", "expected_urgency": 0.05, "tags": ["praise"]},
    {"message": "Perfect, that answers my question. You guys are awesome!", "expected_sentiment": "happy", "expected_urgency": 0.05, "tags": []},
    {"message": "Excellent customer service. I'll definitely recommend you to colleagues.", "expected_sentiment": "happy", "expected_urgency": 0.05, "tags": ["recommendation"]},
    {"message": "Wow, that was fast! Problem solved. Thank you!", "expected_sentiment": "happy", "expected_urgency": 0.05, "tags": []},
    {"message": "I really appreciate your help today. Everything is working great now.", "expected_sentiment": "happy", "expected_urgency": 0.05, "tags": []},
    {"message": "Just wanted to say great job on the new features. They're very useful!", "expected_sentiment": "happy", "expected_urgency": 0.05, "tags": ["praise"]},
    {"message": "The refund was processed quickly. Thanks for making this easy!", "expected_sentiment": "happy", "expected_urgency": 0.1, "tags": []},

    # ─── NEUTRAL (10 messages) ───────────────────────────────────────────────
    {"message": "What are your business hours?", "expected_sentiment": "neutral", "expected_urgency": 0.2, "tags": []},
    {"message": "Can you tell me the status of order #ORD-4521?", "expected_sentiment": "neutral", "expected_urgency": 0.3, "tags": []},
    {"message": "I need to update my email address on my account.", "expected_sentiment": "neutral", "expected_urgency": 0.2, "tags": []},
    {"message": "How do I reset my password?", "expected_sentiment": "neutral", "expected_urgency": 0.2, "tags": []},
    {"message": "What payment methods do you accept?", "expected_sentiment": "neutral", "expected_urgency": 0.15, "tags": []},
    {"message": "I'd like to know about your enterprise pricing.", "expected_sentiment": "neutral", "expected_urgency": 0.2, "tags": []},
    {"message": "Can you check if my subscription includes API access?", "expected_sentiment": "neutral", "expected_urgency": 0.2, "tags": []},
    {"message": "Please add 3 more seats to my team plan.", "expected_sentiment": "neutral", "expected_urgency": 0.2, "tags": []},
    {"message": "I want to upgrade from basic to professional plan.", "expected_sentiment": "neutral", "expected_urgency": 0.2, "tags": []},
    {"message": "What is the warranty period for hardware products?", "expected_sentiment": "neutral", "expected_urgency": 0.15, "tags": []},
]


# ════════════════════════════════════════════════════════════════════════════════
# ESCALATION DECISION DATASET (50 messages — 25 should-escalate, 25 should-not)
# ════════════════════════════════════════════════════════════════════════════════

ESCALATION_DATASET = [
    # ─── SHOULD ESCALATE (25 messages) ───────────────────────────────────────
    {"message": "I will contact my attorney about this fraud on my account.", "expected_escalation": True, "escalation_reason": "legal_threat", "intent": "escalation", "sentiment": "angry", "urgency": 0.95, "tags": ["legal"]},
    {"message": "This is illegal and I am going to take legal action.", "expected_escalation": True, "escalation_reason": "legal_threat", "intent": "escalation", "sentiment": "angry", "urgency": 0.95, "tags": ["legal"]},
    {"message": "I will sue your company for breach of contract.", "expected_escalation": True, "escalation_reason": "legal_threat", "intent": "escalation", "sentiment": "angry", "urgency": 0.9, "tags": ["legal"]},
    {"message": "My lawyer will be in touch regarding this matter.", "expected_escalation": True, "escalation_reason": "legal_threat", "intent": "escalation", "sentiment": "angry", "urgency": 0.9, "tags": ["legal"]},
    {"message": "This is fraud and I am reporting you to the authorities.", "expected_escalation": True, "escalation_reason": "legal_threat", "intent": "escalation", "sentiment": "angry", "urgency": 0.95, "tags": ["legal"]},
    {"message": "I need to speak to a manager right now!", "expected_escalation": True, "escalation_reason": "manager_request", "intent": "escalation", "sentiment": "angry", "urgency": 0.85, "tags": ["manager"]},
    {"message": "Connect me with a supervisor immediately.", "expected_escalation": True, "escalation_reason": "manager_request", "intent": "escalation", "sentiment": "frustrated", "urgency": 0.8, "tags": ["manager"]},
    {"message": "Let me speak to your manager. I've been dealing with this for weeks.", "expected_escalation": True, "escalation_reason": "manager_request", "intent": "escalation", "sentiment": "angry", "urgency": 0.85, "tags": ["manager"]},
    {"message": "I demand to speak to a manager about this unacceptable situation!", "expected_escalation": True, "escalation_reason": "manager_request", "intent": "escalation", "sentiment": "angry", "urgency": 0.9, "tags": ["manager"]},
    {"message": "Transfer me to a human agent, this chatbot is useless.", "expected_escalation": True, "escalation_reason": "human_request", "intent": "escalation", "sentiment": "frustrated", "urgency": 0.8, "tags": ["human_request"]},
    {"message": "I've emailed three times and nobody has responded. This is my fourth attempt.", "expected_escalation": True, "escalation_reason": "repeated_contact", "intent": "complaint", "sentiment": "angry", "urgency": 0.85, "tags": ["repeated"]},
    {"message": "Nobody has responded to my previous tickets. This is completely unacceptable!", "expected_escalation": True, "escalation_reason": "repeated_contact", "intent": "complaint", "sentiment": "angry", "urgency": 0.85, "tags": ["repeated"]},
    {"message": "This is my third email about the same issue. I need someone to actually help me!", "expected_escalation": True, "escalation_reason": "repeated_contact", "intent": "complaint", "sentiment": "frustrated", "urgency": 0.8, "tags": ["repeated"]},
    {"message": "I'm going to report this to the BBB and consumer protection.", "expected_escalation": True, "escalation_reason": "regulatory_threat", "intent": "complaint", "sentiment": "angry", "urgency": 0.9, "tags": ["regulatory"]},
    {"message": "If this isn't resolved today, I'm contacting the attorney general.", "expected_escalation": True, "escalation_reason": "regulatory_threat", "intent": "complaint", "sentiment": "angry", "urgency": 0.9, "tags": ["regulatory"]},
    {"message": "I want to file a formal complaint with your compliance department.", "expected_escalation": True, "escalation_reason": "compliance", "intent": "escalation", "sentiment": "frustrated", "urgency": 0.7, "tags": ["compliance"]},
    {"message": "My data was breached and I need to speak with someone about this immediately!", "expected_escalation": True, "escalation_reason": "data_breach", "intent": "escalation", "sentiment": "angry", "urgency": 0.95, "tags": ["data_breach"]},
    {"message": "I found a security vulnerability in your system. This needs immediate attention.", "expected_escalation": True, "escalation_reason": "security", "intent": "escalation", "sentiment": "neutral", "urgency": 0.9, "tags": ["security"]},
    {"message": "This is a safety hazard! Someone could get hurt. I need to speak to someone now!", "expected_escalation": True, "escalation_reason": "safety", "intent": "escalation", "sentiment": "angry", "urgency": 0.95, "tags": ["safety"]},
    {"message": "I'm a journalist investigating your company's practices. I need a statement.", "expected_escalation": True, "escalation_reason": "media", "intent": "escalation", "sentiment": "neutral", "urgency": 0.8, "tags": ["media"]},
    {"message": "My account was hacked and unauthorized purchases were made. This is serious!", "expected_escalation": True, "escalation_reason": "security", "intent": "escalation", "sentiment": "angry", "urgency": 0.9, "tags": ["security"]},
    {"message": "I'm contacting you on behalf of my law firm regarding a client dispute.", "expected_escalation": True, "escalation_reason": "legal_threat", "intent": "escalation", "sentiment": "neutral", "urgency": 0.85, "tags": ["legal"]},
    {"message": "Your product caused property damage. I need to discuss compensation with management.", "expected_escalation": True, "escalation_reason": "liability", "intent": "complaint", "sentiment": "angry", "urgency": 0.85, "tags": ["liability"]},
    {"message": "I've been overcharged for 6 months straight. This is systemic fraud. I need executive escalation.", "expected_escalation": True, "escalation_reason": "systemic_fraud", "intent": "complaint", "sentiment": "angry", "urgency": 0.9, "tags": ["fraud"]},
    {"message": "I want to exercise my GDPR right to erasure. This needs your data protection officer.", "expected_escalation": True, "escalation_reason": "compliance", "intent": "escalation", "sentiment": "neutral", "urgency": 0.7, "tags": ["compliance"]},

    # ─── SHOULD NOT ESCALATE (25 messages) ───────────────────────────────────
    {"message": "Where is my order? It's been a few days.", "expected_escalation": False, "escalation_reason": None, "intent": "order_status", "sentiment": "neutral", "urgency": 0.3, "tags": []},
    {"message": "Can I get a refund for my purchase?", "expected_escalation": False, "escalation_reason": None, "intent": "refund_request", "sentiment": "neutral", "urgency": 0.3, "tags": []},
    {"message": "What is your return policy?", "expected_escalation": False, "escalation_reason": None, "intent": "faq_question", "sentiment": "neutral", "urgency": 0.2, "tags": []},
    {"message": "I was charged twice for the same order. Please fix it.", "expected_escalation": False, "escalation_reason": None, "intent": "refund_request", "sentiment": "frustrated", "urgency": 0.5, "tags": []},
    {"message": "How do I update my email address?", "expected_escalation": False, "escalation_reason": None, "intent": "account_modification", "sentiment": "neutral", "urgency": 0.2, "tags": []},
    {"message": "The app keeps crashing when I open settings.", "expected_escalation": False, "escalation_reason": None, "intent": "technical_support", "sentiment": "frustrated", "urgency": 0.5, "tags": []},
    {"message": "I want to cancel my subscription.", "expected_escalation": False, "escalation_reason": None, "intent": "cancellation", "sentiment": "neutral", "urgency": 0.3, "tags": []},
    {"message": "My invoice shows the wrong amount. Can you correct it?", "expected_escalation": False, "escalation_reason": None, "intent": "billing_issue", "sentiment": "neutral", "urgency": 0.3, "tags": []},
    {"message": "I'm disappointed with the product quality. Not what I expected.", "expected_escalation": False, "escalation_reason": None, "intent": "complaint", "sentiment": "frustrated", "urgency": 0.4, "tags": []},
    {"message": "Can you check the delivery status for my order?", "expected_escalation": False, "escalation_reason": None, "intent": "order_status", "sentiment": "neutral", "urgency": 0.2, "tags": []},
    {"message": "I need to add more seats to my team plan.", "expected_escalation": False, "escalation_reason": None, "intent": "account_modification", "sentiment": "neutral", "urgency": 0.2, "tags": []},
    {"message": "Do you offer enterprise discounts?", "expected_escalation": False, "escalation_reason": None, "intent": "faq_question", "sentiment": "neutral", "urgency": 0.15, "tags": []},
    {"message": "The integration isn't working properly after the update.", "expected_escalation": False, "escalation_reason": None, "intent": "technical_support", "sentiment": "neutral", "urgency": 0.4, "tags": []},
    {"message": "I want to upgrade my plan to professional.", "expected_escalation": False, "escalation_reason": None, "intent": "account_modification", "sentiment": "neutral", "urgency": 0.2, "tags": []},
    {"message": "My payment was declined. Can you try again?", "expected_escalation": False, "escalation_reason": None, "intent": "billing_issue", "sentiment": "neutral", "urgency": 0.3, "tags": []},
    {"message": "I'm frustrated with the shipping delay but I understand things happen.", "expected_escalation": False, "escalation_reason": None, "intent": "complaint", "sentiment": "frustrated", "urgency": 0.4, "tags": ["understanding"]},
    {"message": "Your website is a bit slow today. Just wanted to let you know.", "expected_escalation": False, "escalation_reason": None, "intent": "technical_support", "sentiment": "neutral", "urgency": 0.2, "tags": ["minor"]},
    {"message": "I need a refund for the defective product. Can you help?", "expected_escalation": False, "escalation_reason": None, "intent": "refund_request", "sentiment": "frustrated", "urgency": 0.5, "tags": []},
    {"message": "What are your shipping options for international orders?", "expected_escalation": False, "escalation_reason": None, "intent": "faq_question", "sentiment": "neutral", "urgency": 0.15, "tags": []},
    {"message": "The dashboard is a bit confusing. How do I find my usage stats?", "expected_escalation": False, "escalation_reason": None, "intent": "technical_support", "sentiment": "neutral", "urgency": 0.25, "tags": []},
    {"message": "I'd like to change my billing cycle from monthly to annual.", "expected_escalation": False, "escalation_reason": None, "intent": "account_modification", "sentiment": "neutral", "urgency": 0.2, "tags": []},
    {"message": "Can you reset my password? I can't access my account.", "expected_escalation": False, "escalation_reason": None, "intent": "faq_question", "sentiment": "neutral", "urgency": 0.3, "tags": []},
    {"message": "The product arrived a day late. Not ideal but not a big deal.", "expected_escalation": False, "escalation_reason": None, "intent": "complaint", "sentiment": "neutral", "urgency": 0.2, "tags": ["minor"]},
    {"message": "I was overcharged by $5 on my last bill. Small amount but wanted to flag it.", "expected_escalation": False, "escalation_reason": None, "intent": "billing_issue", "sentiment": "neutral", "urgency": 0.25, "tags": ["minor"]},
    {"message": "Thank you for the help! Everything is working great now.", "expected_escalation": False, "escalation_reason": None, "intent": "general_inquiry", "sentiment": "happy", "urgency": 0.05, "tags": ["positive"]},
]


# ════════════════════════════════════════════════════════════════════════════════
# EDGE CASE DATASET (20 messages — multi-intent, ambiguous, adversarial)
# ════════════════════════════════════════════════════════════════════════════════

EDGE_CASE_DATASET = [
    # ─── Multi-intent messages ───────────────────────────────────────────────
    {"message": "Cancel my order AND refund the payment. The product was damaged on arrival.", "expected_intent": "cancellation", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "complex", "tags": ["multi_intent"]},
    {"message": "I want a refund for the overcharge and I need my account reactivated.", "expected_intent": "refund_request", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "complex", "tags": ["multi_intent"]},
    {"message": "Fix the bug in your app and also update my billing address while you're at it.", "expected_intent": "technical_support", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "complex", "tags": ["multi_intent"]},
    {"message": "The product is defective, I want a refund, and I need to speak to someone about this!", "expected_intent": "refund_request", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "complex", "tags": ["multi_intent"]},

    # ─── Ambiguous messages ──────────────────────────────────────────────────
    {"message": "I have a question about my account", "expected_intent": "general_inquiry", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "tags": ["ambiguous"]},
    {"message": "Something went wrong with my order", "expected_intent": "order_status", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "medium", "tags": ["ambiguous"]},
    {"message": "I'm not happy", "expected_intent": "complaint", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "simple", "tags": ["ambiguous"]},
    {"message": "Help", "expected_intent": "general_inquiry", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "tags": ["ambiguous", "very_short"]},

    # ─── Very short messages ─────────────────────────────────────────────────
    {"message": "Refund please", "expected_intent": "refund_request", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "tags": ["very_short"]},
    {"message": "Where's my order?", "expected_intent": "order_status", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "tags": ["very_short"]},
    {"message": "Cancel it", "expected_intent": "cancellation", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "tags": ["very_short"]},
    {"message": "Broken app", "expected_intent": "technical_support", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "simple", "tags": ["very_short"]},

    # ─── Sarcastic/indirect messages ─────────────────────────────────────────
    {"message": "Oh great, another billing error. Just what I needed today.", "expected_intent": "billing_issue", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "tags": ["sarcastic"]},
    {"message": "Wow, 3 weeks for shipping. That's some kind of record, isn't it?", "expected_intent": "complaint", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "tags": ["sarcastic"]},

    # ─── With PII (should be handled by PII guard) ───────────────────────────
    {"message": "My SSN is 123-45-6789 and I need to update my account. Someone used my identity.", "expected_intent": "account_modification", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "complex", "tags": ["pii", "identity_theft"]},
    {"message": "My credit card 4111-1111-1111-1111 was charged without authorization. My email is john@gmail.com.", "expected_intent": "billing_issue", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "medium", "tags": ["pii"]},

    # ─── Non-English / mixed language ────────────────────────────────────────
    {"message": "I need ayuda with my order por favor. It hasn't arrived yet.", "expected_intent": "order_status", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "medium", "tags": ["mixed_language"]},
    {"message": "Mon compte est suspendu, please help reactivate my account.", "expected_intent": "account_modification", "expected_sentiment": "neutral", "expected_escalation": False, "complexity": "medium", "tags": ["mixed_language"]},

    # ─── Very long / detailed messages ───────────────────────────────────────
    {"message": "I purchased your premium wireless headphones (model WH-1000XM5, serial number SN78291, order #ORD-44221) on December 15th, 2025, from your online store. Upon receiving the product on December 22nd, I discovered that the left ear cup produces a persistent crackling noise at volumes above 60%. I have tried the following troubleshooting steps: 1) Reset the headphones, 2) Updated firmware to v3.1, 3) Tested with multiple devices (iPhone 15, MacBook Pro, Sony TV), 4) Replaced the ear cushions. The issue persists across all devices and volume levels. I would like a full refund of $349.99 or a replacement unit shipped immediately.", "expected_intent": "refund_request", "expected_sentiment": "frustrated", "expected_escalation": False, "complexity": "complex", "tags": ["detailed", "long"]},
]


def get_full_dataset() -> list[dict]:
    """Combine all datasets into one comprehensive evaluation set."""
    full = []
    for item in INTENT_DATASET:
        full.append({**item, "source": "intent"})
    for item in SENTIMENT_DATASET:
        full.append({
            "message": item["message"],
            "expected_sentiment": item["expected_sentiment"],
            "expected_urgency": item["expected_urgency"],
            "tags": item.get("tags", []),
            "source": "sentiment",
        })
    for item in ESCALATION_DATASET:
        full.append({
            "message": item["message"],
            "expected_escalation": item["expected_escalation"],
            "escalation_reason": item.get("escalation_reason"),
            "intent": item.get("intent"),
            "sentiment": item.get("sentiment"),
            "urgency": item.get("urgency"),
            "tags": item.get("tags", []),
            "source": "escalation",
        })
    for item in EDGE_CASE_DATASET:
        full.append({**item, "source": "edge_case"})
    return full


def get_dataset_stats() -> dict:
    """Get statistics about the evaluation dataset."""
    intent_counts = {}
    for item in INTENT_DATASET:
        intent = item["expected_intent"]
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

    sentiment_counts = {}
    for item in SENTIMENT_DATASET:
        sent = item["expected_sentiment"]
        sentiment_counts[sent] = sentiment_counts.get(sent, 0) + 1

    esc_should = sum(1 for item in ESCALATION_DATASET if item["expected_escalation"])
    esc_should_not = sum(1 for item in ESCALATION_DATASET if not item["expected_escalation"])

    return {
        "total_messages": len(INTENT_DATASET) + len(SENTIMENT_DATASET) + len(ESCALATION_DATASET) + len(EDGE_CASE_DATASET),
        "intent_dataset": len(INTENT_DATASET),
        "sentiment_dataset": len(SENTIMENT_DATASET),
        "escalation_dataset": len(ESCALATION_DATASET),
        "edge_case_dataset": len(EDGE_CASE_DATASET),
        "intent_distribution": intent_counts,
        "sentiment_distribution": sentiment_counts,
        "escalation_should_escalate": esc_should,
        "escalation_should_not_escalate": esc_should_not,
    }
