"""
PARWA Mini Tasks Package.

This package contains task modules for Mini PARWA variant.
Each task wraps a Mini agent to perform specific actions.

Available Tasks:
- answer_faq: Answer FAQ queries using Mini FAQ agent
- process_email: Process incoming emails using Mini Email agent
- handle_chat: Handle chat messages using Mini Chat agent
- make_call: Make voice calls using Mini Voice agent
- create_ticket: Create support tickets using Mini Ticket agent
- escalate: Trigger human escalation using Mini Escalation agent
- verify_refund: Verify refund requests using Mini Refund agent

All Mini tasks:
- Route to 'light' tier for processing
- Enforce Mini limits (2 concurrent calls, $50 refund max)
- Escalate when confidence < 70%
- NEVER call Paddle without pending_approval
"""
from variants.mini.tasks.answer_faq import AnswerFAQTask
from variants.mini.tasks.process_email import ProcessEmailTask
from variants.mini.tasks.handle_chat import HandleChatTask
from variants.mini.tasks.make_call import MakeCallTask
from variants.mini.tasks.create_ticket import CreateTicketTask
from variants.mini.tasks.escalate import EscalateTask
from variants.mini.tasks.verify_refund import VerifyRefundTask

__all__ = [
    "AnswerFAQTask",
    "ProcessEmailTask",
    "HandleChatTask",
    "MakeCallTask",
    "CreateTicketTask",
    "EscalateTask",
    "VerifyRefundTask",
]
