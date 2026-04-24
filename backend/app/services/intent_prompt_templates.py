"""
Per-Intent Prompt Templates (SG-25)

48 specialized prompt templates organized by:
- 12 intent types (6 core + 6 extended)
- 4 response types: empathetic, informational, resolution, follow_up

Each template has: system_prompt, few_shot_examples, output_schema,
tone_instructions, and variant_access.

Parent: Week 9 Day 6 (Monday)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Data Classes ──────────────────────────────────────────────────────


@dataclass
class PromptTemplate:
    """Single prompt template for an intent × response_type combination."""

    template_id: str
    intent: str
    response_type: str  # empathetic/informational/resolution/follow_up
    system_prompt: str
    few_shot_examples: List[Dict[str, str]]
    output_schema: Dict[str, Any]
    tone_instructions: str
    variant_access: List[str]  # which variants can use this


# ── Template Registry ────────────────────────────────────────────────


class PromptTemplateRegistry:
    """Registry of 48+ specialized prompt templates (SG-25).

    Templates are organized by intent × response_type.
    Variant access controls which PARWA variant can use each template.
    """

    def __init__(self):
        self._templates: Dict[str, PromptTemplate] = {}
        self._load_all_templates()

    def _load_all_templates(self) -> None:
        """Load all templates into the registry."""
        intents = [
            "refund", "technical", "billing", "complaint", "feature_request",
            "general", "cancellation", "shipping", "inquiry", "escalation",
            "account", "feedback",
        ]
        response_types = ["empathetic", "informational", "resolution", "follow_up"]

        for intent in intents:
            for resp_type in response_types:
                template = self._build_template(intent, resp_type)
                self._templates[template.template_id] = template

    def _build_template(self, intent: str, response_type: str) -> PromptTemplate:
        """Build a single template for intent × response_type."""
        tid = f"{intent}_{response_type}"

        system_prompt = self._get_system_prompt(intent, response_type)
        few_shot = self._get_few_shot_examples(intent, response_type)
        schema = self._get_output_schema(intent, response_type)
        tone = self._get_tone_instructions(intent, response_type)
        variants = self._get_variant_access(intent, response_type)

        return PromptTemplate(
            template_id=tid,
            intent=intent,
            response_type=response_type,
            system_prompt=system_prompt,
            few_shot_examples=few_shot,
            output_schema=schema,
            tone_instructions=tone,
            variant_access=variants,
        )

    def _get_system_prompt(self, intent: str, response_type: str) -> str:
        """Generate system prompt based on intent and response type."""
        prompts = {
            ("refund", "empathetic"): (
                "You are handling a customer refund request. Acknowledge the customer's "
                "frustration empathetically. Explain the refund process clearly. If the "
                "refund is approved, provide the expected timeline. If not, explain the "
                "reason with patience and offer alternatives. Always maintain a supportive "
                "and understanding tone throughout the interaction."
            ),
            ("refund", "informational"): (
                "You are providing information about refund policies and procedures. "
                "Clearly explain refund eligibility criteria, processing timeframes, "
                "and any applicable conditions. Reference the specific policy terms. "
                "Be precise about amounts, timelines, and any deductions that may apply."
            ),
            ("refund", "resolution"): (
                "You are processing a customer refund. Confirm the refund details including "
                "amount, method, and expected processing time. Provide a reference number "
                "if applicable. Explain next steps clearly and set expectations for when "
                "the customer will see the refund reflected."
            ),
            ("refund", "follow_up"): (
                "You are following up on a previously initiated refund. Check the current "
                "status of the refund processing. Provide an update on the timeline. "
                "If there are delays, explain the reason and provide a revised estimate. "
                "Ask if there's anything else the customer needs assistance with."
            ),
            ("technical", "empathetic"): (
                "You are helping a customer with a technical issue. Acknowledge the "
                "inconvenience caused by the problem. Show understanding of how this "
                "affects their workflow. Express genuine commitment to resolving the issue "
                "quickly. Avoid technical jargon while still being helpful."
            ),
            ("technical", "informational"): (
                "You are providing technical information to a customer. Explain concepts "
                "clearly using simple language. Include step-by-step instructions where "
                "applicable. Use numbered lists for procedures. Mention any prerequisites "
                "or system requirements. Provide links to documentation when relevant."
            ),
            ("technical", "resolution"): (
                "You are resolving a customer's technical issue. Provide clear step-by-step "
                "instructions to fix the problem. Include troubleshooting steps if the "
                "initial fix doesn't work. Specify expected outcomes at each step. "
                "Offer to stay with the customer until the issue is fully resolved."
            ),
            ("technical", "follow_up"): (
                "You are following up on a technical support case. Verify that the "
                "previously suggested solution worked. If the issue persists, gather "
                "additional diagnostic information. Escalate if needed. Document any "
                "new findings for the support record."
            ),
            ("billing", "empathetic"): (
                "You are addressing a customer's billing concern. Acknowledge any "
                "frustration about unexpected charges or billing errors. Assure the "
                "customer that you will investigate thoroughly. Be transparent about "
                "the billing process and any corrections being made."
            ),
            ("billing", "informational"): (
                "You are providing billing information. Clearly explain charges, "
                "payment schedules, and invoice details. Break down costs item by "
                "item when applicable. Explain any taxes, fees, or discounts. "
                "Provide clear information about payment methods and due dates."
            ),
            ("billing", "resolution"): (
                "You are resolving a billing issue. Confirm the specific correction "
                "being made (credit, adjustment, refund). Provide the exact amounts "
                "and when they will take effect. Update the customer on their new "
                "balance or next billing cycle."
            ),
            ("billing", "follow_up"): (
                "You are following up on a billing resolution. Confirm the correction "
                "has been applied successfully. Verify the customer sees the updated "
                "amounts. Address any remaining concerns about future billing."
            ),
            ("complaint", "empathetic"): (
                "You are responding to a customer complaint. Start by sincerely "
                "acknowledging their frustration and apologizing for the negative "
                "experience. Show that you take their feedback seriously. Explain "
                "what you're doing to address their concern. Never be defensive or "
                "dismissive. Demonstrate genuine empathy throughout."
            ),
            ("complaint", "informational"): (
                "You are providing information related to a complaint. Explain the "
                "situation factually without being defensive. Acknowledge what happened "
                "and why. Outline the steps being taken to prevent recurrence. Be "
                "transparent about timelines and next steps."
            ),
            ("complaint", "resolution"): (
                "You are resolving a customer complaint. Clearly state the resolution "
                "being offered. Explain what corrective actions have been or will be "
                "taken. Provide a timeline for any pending actions. Express appreciation "
                "for the customer bringing this to your attention."
            ),
            ("complaint", "follow_up"): (
                "You are following up on a resolved complaint. Confirm the resolution "
                "was satisfactory. Ask if there are any remaining concerns. Express "
                "commitment to preventing similar issues. Thank the customer for their "
                "patience throughout the process."
            ),
            ("feature_request", "empathetic"): (
                "You are responding to a customer feature suggestion. Acknowledge their "
                "idea positively. Show appreciation for their input. Explain how feature "
                "requests are evaluated. Set realistic expectations about timelines."
            ),
            ("feature_request", "informational"): (
                "You are providing information about features and capabilities. "
                "Explain what is currently available. If the requested feature doesn't "
                "exist, explain why it may not be available yet. Suggest alternatives "
                "or workarounds if applicable."
            ),
            ("feature_request", "resolution"): (
                "You are responding to a feature request with a solution. If the feature "
                "exists, explain how to use it. If not, provide the best available "
                "alternative. If the feature is planned, share any available timeline. "
                "Offer to add the customer to the notification list."
            ),
            ("feature_request", "follow_up"): (
                "You are following up on a feature request. Provide any updates on "
                "the feature status. If no updates, explain the prioritization process. "
                "Thank the customer for their continued interest and feedback."
            ),
            ("general", "empathetic"): (
                "You are responding to a general customer inquiry with warmth and "
                "understanding. Be approachable and helpful. Show genuine interest in "
                "assisting the customer. Use a conversational but professional tone."
            ),
            ("general", "informational"): (
                "You are providing general information to a customer. Be clear and "
                "concise. Organize information logically. Use simple language. Provide "
                "relevant details without overwhelming the customer."
            ),
            ("general", "resolution"): (
                "You are resolving a general customer inquiry. Provide a clear and "
                "direct answer to their question. Include any relevant details or "
                "next steps. Confirm the resolution satisfies their need."
            ),
            ("general", "follow_up"): (
                "You are following up on a general inquiry. Verify the customer's "
                "question was fully answered. Ask if they need any additional "
                "information or assistance. Thank them for reaching out."
            ),
            ("cancellation", "empathetic"): (
                "You are handling a cancellation request. Express understanding of "
                "the customer's decision. Avoid being pushy about retention. "
                "Acknowledge any frustration that led to this decision. Process "
                "the cancellation professionally."
            ),
            ("cancellation", "informational"): (
                "You are providing cancellation information. Explain the cancellation "
                "process clearly. Detail what happens to data, subscriptions, and "
                "remaining billing. Explain any applicable refund policies or "
                "proration. Be transparent about timelines."
            ),
            ("cancellation", "resolution"): (
                "You are processing a cancellation. Confirm what was cancelled. "
                "Explain any remaining obligations or pending items. Provide "
                "confirmation of the cancellation and effective date. Offer "
                "information about reactivation if they change their mind."
            ),
            ("cancellation", "follow_up"): (
                "You are following up on a cancellation. Confirm the cancellation "
                "was processed. Ask about the reason for leaving if not already "
                "known. Offer any final assistance. Leave the door open for return."
            ),
            ("shipping", "empathetic"): (
                "You are addressing a shipping concern. Acknowledge the anxiety "
                "customers feel about delayed or lost packages. Show understanding "
                "of how important timely delivery is. Commit to finding a resolution."
            ),
            ("shipping", "informational"): (
                "You are providing shipping information. Share tracking details, "
                "estimated delivery dates, and shipping method. Explain any delays "
                "and their causes. Provide clear information about what the customer "
                "can expect next."
            ),
            ("shipping", "resolution"): (
                "You are resolving a shipping issue. Provide updated tracking "
                "information. If a package is lost, explain the replacement or "
                "refund process. Set clear expectations for resolution timeline."
            ),
            ("shipping", "follow_up"): (
                "You are following up on a shipping issue. Verify the package "
                "was delivered successfully. If there are still issues, escalate "
                "with the carrier. Confirm customer satisfaction with the resolution."
            ),
            ("inquiry", "empathetic"): (
                "You are answering a customer inquiry warmly. Welcome their question "
                "and show enthusiasm for helping. Make them feel valued as a customer. "
                "Be personable while maintaining professionalism."
            ),
            ("inquiry", "informational"): (
                "You are providing detailed information in response to an inquiry. "
                "Be thorough but organized. Use structured formatting for complex "
                "information. Anticipate follow-up questions and address them proactively."
            ),
            ("inquiry", "resolution"): (
                "You are providing a complete answer to a customer inquiry. Ensure "
                "all aspects of their question are addressed. Provide actionable "
                "next steps if applicable. Confirm they have everything they need."
            ),
            ("inquiry", "follow_up"): (
                "You are following up on an inquiry response. Check if the "
                "provided information was helpful. Address any additional questions. "
                "Offer further assistance if needed."
            ),
            ("escalation", "empathetic"): (
                "You are handling an escalation with utmost care and empathy. "
                "Acknowledge the customer's frustration and the time they've spent. "
                "Take personal ownership of resolving the issue. Assure them they "
                "are being connected to someone who can help."
            ),
            ("escalation", "informational"): (
                "You are providing context for an escalation. Explain the escalation "
                "process clearly. Set expectations about response times. Provide "
                "any reference numbers or tracking information for the escalation."
            ),
            ("escalation", "resolution"): (
                "You are resolving an escalated case. Provide a definitive resolution. "
                "Explain what actions were taken and why. Compensate for the poor "
                "experience if appropriate. Ensure the customer feels heard and valued."
            ),
            ("escalation", "follow_up"): (
                "You are following up on an escalation. Verify the resolution was "
                "satisfactory. Check for any lingering concerns. Document the outcome "
                "for quality improvement. Thank the customer for their patience."
            ),
            ("account", "empathetic"): (
                "You are helping with an account issue. Understand that account "
                "problems can cause significant anxiety. Be patient and reassuring. "
                "Guide the customer through the process step by step."
            ),
            ("account", "informational"): (
                "You are providing account-related information. Explain account "
                "settings, options, and procedures clearly. Use precise language "
                "for technical account details. Highlight any security considerations."
            ),
            ("account", "resolution"): (
                "You are resolving an account issue. Confirm what was changed or "
                "fixed. Provide updated account details if applicable. Explain any "
                "security measures taken. Verify the customer can now access their "
                "account successfully."
            ),
            ("account", "follow_up"): (
                "You are following up on an account issue. Verify the resolution "
                "is holding. Check for any related issues. Ensure the customer's "
                "account is fully functional."
            ),
            ("feedback", "empathetic"): (
                "You are receiving customer feedback with genuine appreciation. "
                "Thank them sincerely for taking the time to share their thoughts. "
                "Show that their feedback matters and will be acted upon. Be warm "
                "and receptive."
            ),
            ("feedback", "informational"): (
                "You are acknowledging feedback and explaining how it will be used. "
                "Describe the feedback process. Explain how feedback influences "
                "product decisions. Provide transparency about what happens next."
            ),
            ("feedback", "resolution"): (
                "You are responding to feedback with action. Outline specific "
                "steps being taken based on their feedback. Provide timelines if "
                "applicable. Thank the customer for helping improve the product."
            ),
            ("feedback", "follow_up"): (
                "You are following up on customer feedback. Share any changes made "
                "as a result of their feedback. Ask if they have additional "
                "suggestions. Reinforce that their input is valued."
            ),
        }
        return prompts.get(
            (intent, response_type),
            f"You are a helpful customer support assistant handling a {intent} "
            f"request with a {response_type} approach. Provide clear, professional, "
            f"and helpful responses.",
        )

    def _get_few_shot_examples(self, intent: str, response_type: str) -> List[Dict[str, str]]:
        """Get few-shot examples for the template."""
        examples: List[Dict[str, str]] = []
        intent_examples = {
            "refund": {
                "query": "I want a refund for my order #12345",
                "response": "I completely understand your frustration, and I'm sorry to hear you'd like a refund for order #12345. Let me look into this right away and process your refund as quickly as possible.",
            },
            "technical": {
                "query": "The app keeps crashing when I try to upload files",
                "response": "I'm sorry to hear you're experiencing crashes during file uploads. This must be frustrating. Let me help you troubleshoot this step by step.",
            },
            "billing": {
                "query": "I was charged twice for the same subscription",
                "response": "I understand how concerning it is to see a duplicate charge on your statement. Let me investigate this billing issue right away.",
            },
            "complaint": {
                "query": "This is the third time my issue hasn't been resolved",
                "response": "I sincerely apologize that your issue remains unresolved after multiple attempts. This is not the experience we want you to have, and I take full responsibility for making this right.",
            },
            "feature_request": {
                "query": "It would be great to have dark mode",
                "response": "Thank you for the suggestion! Dark mode is a popular request, and I appreciate you sharing your preference with us.",
            },
            "general": {
                "query": "How do I update my profile settings?",
                "response": "I'd be happy to help you update your profile settings. Let me walk you through the process.",
            },
            "cancellation": {
                "query": "I want to cancel my subscription",
                "response": "I understand you'd like to cancel your subscription. I'm sorry to see you go, and I want to make this process as smooth as possible.",
            },
            "shipping": {
                "query": "My package has been in transit for 2 weeks",
                "response": "I understand how worrying it is when a package takes longer than expected. Let me check on the status of your shipment right away.",
            },
            "inquiry": {
                "query": "What payment methods do you accept?",
                "response": "Great question! I'd be happy to tell you about our accepted payment methods.",
            },
            "escalation": {
                "query": "I need to speak to a manager immediately",
                "response": "I understand your urgency, and I want to make sure you get the attention this issue deserves. Let me connect you with a senior team member right away.",
            },
            "account": {
                "query": "I can't log into my account",
                "response": "I understand how frustrating it is to be locked out of your account. Let me help you regain access as quickly as possible.",
            },
            "feedback": {
                "query": "Your service has been excellent this year",
                "response": "Thank you so much for your kind words! Hearing that our service has met your expectations means a great deal to us.",
            },
        }

        base = intent_examples.get(intent, intent_examples["general"])
        examples.append(base)
        return examples

    def _get_output_schema(self, intent: str, response_type: str) -> Dict[str, Any]:
        """Get output schema for the template."""
        return {
            "type": "object",
            "properties": {
                "response": {
                    "type": "string",
                    "description": "The customer support response",
                },
                "intent_detected": {
                    "type": "string",
                    "enum": [
                        "refund", "technical", "billing", "complaint",
                        "feature_request", "general", "cancellation",
                        "shipping", "inquiry", "escalation", "account",
                        "feedback",
                    ],
                },
                "response_type": {
                    "type": "string",
                    "enum": ["empathetic", "informational", "resolution", "follow_up"],
                },
                "sentiment_match": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "How well the response matches customer sentiment",
                },
                "requires_escalation": {
                    "type": "boolean",
                    "description": "Whether this should be escalated to a human agent",
                },
            },
            "required": ["response", "intent_detected", "response_type"],
        }

    def _get_tone_instructions(self, intent: str, response_type: str) -> str:
        """Get tone instructions based on intent and response type."""
        tone_map = {
            "empathetic": (
                "Use warm, understanding language. Acknowledge the customer's feelings. "
                "Avoid robotic or overly formal language. Show genuine care and empathy. "
                "Use phrases like 'I understand', 'I'm sorry', 'I appreciate your patience'."
            ),
            "informational": (
                "Use clear, factual language. Be precise and organized. Avoid unnecessary "
                "filler words. Use structured formatting (lists, headers) for complex info. "
                "Maintain a helpful and knowledgeable tone."
            ),
            "resolution": (
                "Use confident, action-oriented language. Be direct about what's being "
                "done. Include specific details (amounts, dates, reference numbers). "
                "Show commitment to follow-through. Use phrases like 'I've processed', "
                "'Here's what happens next', 'You can expect'."
            ),
            "follow_up": (
                "Use warm, attentive language. Show the customer they're not forgotten. "
                "Reference previous interactions. Be proactive about next steps. "
                "Use phrases like 'I wanted to check in', 'How is everything going', "
                "'Is there anything else'."
            ),
        }
        return tone_map.get(response_type, tone_map["informational"])

    def _get_variant_access(self, intent: str, response_type: str) -> List[str]:
        """Determine which variants can use this template."""
        # All variants can use empathetic and follow_up
        if response_type in ("empathetic", "follow_up"):
            return ["mini_parwa", "parwa", "high_parwa"]

        # Resolution requires parwa or higher
        if response_type == "resolution":
            return ["parwa", "high_parwa"]

        # Informational: all variants
        return ["mini_parwa", "parwa", "high_parwa"]

    # ── Public API ────────────────────────────────────────────────────

    def get_template(
        self,
        intent: str,
        response_type: str,
        variant_type: str = "parwa",
    ) -> Optional[PromptTemplate]:
        """Get template for intent + response type, variant-filtered."""
        tid = f"{intent}_{response_type}"
        template = self._templates.get(tid)
        if template and variant_type in template.variant_access:
            return template
        return None

    def get_templates_for_intent(self, intent: str) -> List[PromptTemplate]:
        """Get all templates for an intent (all response types)."""
        return [
            t for t in self._templates.values()
            if t.intent == intent
        ]

    def list_all_templates(self) -> List[Dict[str, str]]:
        """List all templates with metadata."""
        return [
            {
                "template_id": t.template_id,
                "intent": t.intent,
                "response_type": t.response_type,
                "variant_access": t.variant_access,
            }
            for t in self._templates.values()
        ]

    def count_templates(self) -> int:
        """Total number of templates."""
        return len(self._templates)
