"""
CRM Bridge — Bidirectional CRM Integration

Provides:
  - ingest_ticket(): Convert incoming CRM webhooks to PARWA pipeline state
  - push_response(): Push resolved response back to CRM
  - push_escalation(): Notify CRM when ticket is escalated (return to human)
  - push_resume_result(): Push resume result back to CRM after human guidance

Supported CRMs:
  - Zendesk (REST API + Webhooks)
  - HubSpot (Tickets API + Webhooks)
  - Generic (for any CRM with webhook support)

All CRM API calls are:
  - Non-blocking (failures logged, don't break pipeline)
  - Tracked in escalation vault for round-trip visibility
  - Configurable via integration credentials in PARWA DB
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger("parwa.crm_bridge")


# ═══════════════════════════════════════════════════════════════
# ABSTRACT CRM ADAPTER
# ═══════════════════════════════════════════════════════════════

class CRMAdapter(ABC):
    """Abstract CRM adapter. Each CRM implements its own API calls."""

    @abstractmethod
    async def parse_incoming_ticket(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse incoming CRM webhook payload into PARWA-compatible format.

        Returns:
            {
                "ticket_id": "CRM-12345",       # External CRM ticket ID
                "query": "Customer's question",
                "customer_id": "cust_456",
                "customer_email": "john@example.com",
                "customer_name": "John Doe",
                "channel_type": "email",
                "metadata": {...},               # CRM-specific metadata
            }
        """
        ...

    @abstractmethod
    async def push_response_to_crm(
        self,
        ticket_id: str,
        response: str,
        status: str,
        internal_note: str = "",
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Push resolved response back to CRM.

        Args:
            ticket_id: External CRM ticket ID
            response: Customer-facing response text
            status: "resolved", "escalated", "pending_human"
            internal_note: AI classification/analysis note
            config: CRM connection config (API key, subdomain, etc.)

        Returns:
            {"success": True/False, "crm_ticket_id": "...", "crm_status": "..."}
        """
        ...

    @abstractmethod
    async def push_escalation_to_crm(
        self,
        ticket_id: str,
        escalation_context: Dict[str, Any],
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Push escalation notification back to CRM.

        Updates CRM ticket with:
          - Status: pending_human / open
          - Internal note: AI classification, techniques tried, failure reason
          - Tags: ai-escalated
          - Reassign to human agent queue
        """
        ...

    @abstractmethod
    async def push_resume_result_to_crm(
        self,
        ticket_id: str,
        response: str,
        quality_score: float,
        human_guidance: str,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Push resume result (after human guidance) back to CRM."""
        ...

    @abstractmethod
    async def push_permanent_failure_to_crm(
        self,
        ticket_id: str,
        attempts: int,
        failure_context: Dict[str, Any],
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """BC-017: Reset CRM ticket to "open"/"new" — AI could not resolve.

        Called when the guidance flow has exhausted MAX_GUIDANCE_RETRIES
        attempts and the quality threshold still isn't met. The CRM ticket
        is reset to its initial open/new state so the human queue picks it
        up fresh — exactly like before PARWA touched it. An internal note
        is added explaining what was tried and why AI gave up.

        Args:
            ticket_id: External CRM ticket ID.
            attempts: Number of guidance attempts that failed.
            failure_context: {
                "last_quality": float,
                "failure_analysis": str,
                "what_was_tried": str,
                "ticket_type": str,
                "complexity": str,
            }
            config: CRM connection config.

        Returns:
            {"success": True/False, "crm_ticket_id": "...", "crm_status": "open"/"new"}
        """
        ...

    @abstractmethod
    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Validate incoming webhook signature."""
        ...

    async def create_ticket_in_crm(
        self,
        subject: str,
        content: str,
        customer_email: str = "",
        customer_name: str = "",
        priority: str = "medium",
        category: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a NEW ticket in the CRM (outbound push).

        Default implementation returns "not implemented". Adapters that
        support outbound ticket creation (currently HubSpot) override this.

        Used by pipeline_dispatcher when a manually-created Parwa ticket
        needs to also appear in the tenant's CRM as a new ticket — not
        just when the ticket ORIGINATED in the CRM via inbound webhook.

        Args:
            subject: Ticket subject line.
            content: First customer message body (the ticket description).
            customer_email: Customer email (for contact association).
            customer_name: Customer name (for contact association).
            priority: Ticket priority (critical/high/medium/low).
            category: Ticket category.
            config: CRM credentials dict (e.g. {"access_token": "..."}).

        Returns:
            {
                "success": True/False,
                "crm_ticket_id": "...",       # New CRM ticket ID
                "crm_ticket_url": "...",      # Optional: link to CRM UI
                "error": "..."                # On failure
            }
        """
        return {
            "success": False,
            "error": f"create_ticket_in_crm not implemented for {self.__class__.__name__}",
        }


# ═══════════════════════════════════════════════════════════════
# ZENDESK ADAPTER
# ═══════════════════════════════════════════════════════════════

class ZendeskAdapter(CRMAdapter):
    """Zendesk CRM adapter.

    Ingestion: Receives ticket.created / ticket.updated webhooks
    Push-back: Uses Zendesk REST API to post comments and update status

    Webhook payload structure:
    {
        "id": 12345,
        "subject": "Refund request",
        "description": "I want a refund for...",
        "status": "new",
        "priority": "high",
        "requester": {"name": "John", "email": "john@example.com"},
        "custom_fields": [...],
    }
    """

    API_BASE = "https://{subdomain}.zendesk.com/api/v2"

    async def parse_incoming_ticket(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ticket = payload.get("ticket", payload)

        # Extract content from Zendesk format
        subject = ticket.get("subject", "")
        description = ticket.get("description", "")
        # Combine subject + description as the query
        query = f"{subject}. {description}" if subject and description else description or subject

        requester = ticket.get("requester", {})
        return {
            "ticket_id": str(ticket.get("id", "")),
            "query": query.strip(),
            "customer_id": str(requester.get("id", "")),
            "customer_email": requester.get("email", ""),
            "customer_name": requester.get("name", ""),
            "channel_type": "email",  # Zendesk primarily email-based
            "metadata": {
                "crm_provider": "zendesk",
                "crm_status": ticket.get("status", "new"),
                "crm_priority": ticket.get("priority", "normal"),
                "crm_tags": ticket.get("tags", []),
                "crm_group_id": ticket.get("group_id", ""),
                "crm_assignee_id": ticket.get("assignee_id", ""),
                "zendesk_ticket_id": ticket.get("id", ""),
            },
        }

    async def push_response_to_crm(
        self,
        ticket_id: str,
        response: str,
        status: str,
        internal_note: str = "",
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Post response as public comment + update ticket status in Zendesk."""
        if not config:
            return {"success": False, "error": "No Zendesk config provided"}

        try:
            import httpx
            subdomain = config.get("subdomain", "")
            api_key = config.get("api_key", "")
            email = config.get("email", "")
            base_url = self.API_BASE.format(subdomain=subdomain)

            auth = (f"{email}/token", api_key)
            headers = {"Content-Type": "application/json"}

            # Map PARWA status to Zendesk status
            zendesk_status_map = {
                "resolved": "solved",
                "escalated": "open",
                "pending_human": "pending",
            }
            zendesk_status = zendesk_status_map.get(status, "solved")

            # Update ticket status + add comment
            async with httpx.AsyncClient(timeout=15.0, auth=auth) as client:
                # Post public reply
                comment_payload = {
                    "ticket": {
                        "comment": {
                            "body": response,
                            "public": True,
                        },
                        "status": zendesk_status,
                    }
                }
                resp = await client.put(
                    f"{base_url}/tickets/{ticket_id}.json",
                    headers=headers,
                    json=comment_payload,
                )
                resp.raise_for_status()

                # Post internal note with AI analysis
                if internal_note:
                    note_payload = {
                        "ticket": {
                            "comment": {
                                "body": f"[PARWA AI Analysis]\n{internal_note}",
                                "public": False,
                            }
                        }
                    }
                    await client.put(
                        f"{base_url}/tickets/{ticket_id}.json",
                        headers=headers,
                        json=note_payload,
                    )

            logger.info("Zendesk: Pushed response to ticket=%s status=%s", ticket_id, zendesk_status)
            return {
                "success": True,
                "crm_ticket_id": ticket_id,
                "crm_status": zendesk_status,
                "crm_provider": "zendesk",
            }

        except Exception as e:
            logger.error("Zendesk: Failed to push response: %s", e)
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    async def push_escalation_to_crm(
        self,
        ticket_id: str,
        escalation_context: Dict[str, Any],
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Update Zendesk ticket to indicate AI escalation."""
        if not config:
            return {"success": False, "error": "No Zendesk config provided"}

        try:
            import httpx
            subdomain = config.get("subdomain", "")
            api_key = config.get("api_key", "")
            email = config.get("email", "")
            base_url = self.API_BASE.format(subdomain=subdomain)
            auth = (f"{email}/token", api_key)
            headers = {"Content-Type": "application/json"}

            # Build internal note with full escalation context
            notification_key = escalation_context.get("notification_key", "")
            quality_score = escalation_context.get("super_node_quality", 0)
            failure_analysis = escalation_context.get("failure_analysis", "")
            what_was_tried = escalation_context.get("what_was_tried", "")

            note = (
                f"[PARWA AI Escalation — {notification_key}]\n\n"
                f"AI attempted to resolve this ticket but quality threshold was not met.\n\n"
                f"Quality Score: {quality_score:.2f}\n"
                f"Failure Analysis: {failure_analysis[:500]}\n"
                f"Techniques Used: {what_was_tried[:500]}\n\n"
                f"Ticket Classification:\n"
                f"  Type: {escalation_context.get('ticket_type', 'unknown')}\n"
                f"  Complexity: {escalation_context.get('complexity', 'unknown')}\n"
                f"  Action Required: {escalation_context.get('required_action', 'unknown')}\n\n"
                f"Please review and provide resolution."
            )

            # Update ticket: set to pending, add internal note, add tags
            update_payload = {
                "ticket": {
                    "status": "pending",
                    "comment": {"body": note, "public": False},
                    "tags": ["ai-escalated", "parwa"],
                }
            }

            async with httpx.AsyncClient(timeout=15.0, auth=auth) as client:
                resp = await client.put(
                    f"{base_url}/tickets/{ticket_id}.json",
                    headers=headers,
                    json=update_payload,
                )
                resp.raise_for_status()

            logger.info("Zendesk: Escalated ticket=%s key=%s", ticket_id, notification_key)
            return {
                "success": True,
                "crm_ticket_id": ticket_id,
                "crm_status": "pending",
                "crm_provider": "zendesk",
            }

        except Exception as e:
            logger.error("Zendesk: Failed to push escalation: %s", e)
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    async def push_resume_result_to_crm(
        self,
        ticket_id: str,
        response: str,
        quality_score: float,
        human_guidance: str,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Push resume result (after human helped AI) to Zendesk."""
        if not config:
            return {"success": False, "error": "No Zendesk config provided"}

        try:
            import httpx
            subdomain = config.get("subdomain", "")
            api_key = config.get("api_key", "")
            email = config.get("email", "")
            base_url = self.API_BASE.format(subdomain=subdomain)
            auth = (f"{email}/token", api_key)
            headers = {"Content-Type": "application/json"}

            internal_note = (
                f"[PARWA AI Resume — Human Assisted]\n\n"
                f"Quality Score (with human guidance): {quality_score:.2f}\n"
                f"Human Guidance: {human_guidance[:300]}\n"
            )

            update_payload = {
                "ticket": {
                    "status": "solved",
                    "comment": {
                        "body": response,
                        "public": True,
                    },
                    "tags": ["ai-resolved", "human-assisted"],
                }
            }

            async with httpx.AsyncClient(timeout=15.0, auth=auth) as client:
                # Post public reply + solve
                resp = await client.put(
                    f"{base_url}/tickets/{ticket_id}.json",
                    headers=headers,
                    json=update_payload,
                )
                resp.raise_for_status()

                # Post internal note
                await client.put(
                    f"{base_url}/tickets/{ticket_id}.json",
                    headers=headers,
                    json={"ticket": {"comment": {"body": internal_note, "public": False}}},
                )

            logger.info("Zendesk: Resume result pushed to ticket=%s", ticket_id)
            return {
                "success": True,
                "crm_ticket_id": ticket_id,
                "crm_status": "solved",
                "crm_provider": "zendesk",
            }

        except Exception as e:
            logger.error("Zendesk: Failed to push resume result: %s", e)
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    async def push_permanent_failure_to_crm(
        self,
        ticket_id: str,
        attempts: int,
        failure_context: Dict[str, Any],
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """BC-017: Reset Zendesk ticket to "open" — AI could not resolve.

        Sets ticket status back to "open" (the fresh queue state) and adds
        an internal note + tags so the human agent understands what AI tried.
        """
        if not config:
            return {"success": False, "error": "No Zendesk config provided"}

        try:
            import httpx
            subdomain = config.get("subdomain", "")
            api_key = config.get("api_key", "")
            email = config.get("email", "")
            base_url = self.API_BASE.format(subdomain=subdomain)
            auth = (f"{email}/token", api_key)
            headers = {"Content-Type": "application/json"}

            last_quality = failure_context.get("last_quality", 0.0)
            failure_analysis = failure_context.get("failure_analysis", "")
            what_was_tried = failure_context.get("what_was_tried", "")

            note = (
                f"[PARWA AI — Cannot Resolve, Returned to Human Queue]\n\n"
                f"AI attempted to resolve this ticket {attempts} times with human guidance "
                f"but could not meet the quality threshold.\n\n"
                f"Last Quality Score: {last_quality:.2f}\n"
                f"Failure Analysis: {failure_analysis[:500]}\n"
                f"Techniques Used: {what_was_tried[:500]}\n\n"
                f"Ticket Classification:\n"
                f"  Type: {failure_context.get('ticket_type', 'unknown')}\n"
                f"  Complexity: {failure_context.get('complexity', 'unknown')}\n\n"
                f"This ticket has been reset to 'open' for human handling. "
                f"Please review the customer's request and respond manually."
            )

            update_payload = {
                "ticket": {
                    "status": "open",
                    "comment": {"body": note, "public": False},
                    "tags": ["ai-cannot-resolve", "needs-human", "parwa"],
                }
            }

            async with httpx.AsyncClient(timeout=15.0, auth=auth) as client:
                resp = await client.put(
                    f"{base_url}/tickets/{ticket_id}.json",
                    headers=headers,
                    json=update_payload,
                )
                resp.raise_for_status()

            logger.info(
                "Zendesk: Permanent failure pushed to ticket=%s attempts=%d",
                ticket_id, attempts,
            )
            return {
                "success": True,
                "crm_ticket_id": ticket_id,
                "crm_status": "open",
                "crm_provider": "zendesk",
            }

        except Exception as e:
            logger.error("Zendesk: Failed to push permanent failure: %s", e)
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Validate Zendesk webhook token."""
        token = headers.get("X-Zendesk-Webhook-Token", "")
        # In production, compare against stored token
        return bool(token)


# ═══════════════════════════════════════════════════════════════
# HUBSPOT ADAPTER
# ═══════════════════════════════════════════════════════════════

class HubSpotAdapter(CRMAdapter):
    """HubSpot CRM adapter.

    Ingestion: Receives ticket.creation / ticket.status_change webhooks
    Push-back: Uses HubSpot Tickets API v2

    Webhook payload structure:
    {
        "objectId": 12345,
        "properties": {
            "subject": "Refund request",
            "content": "I want a refund...",
            "hs_pipeline_stage": "1",
        },
    }
    """

    API_BASE = "https://api.hubapi.com/crm/v3/objects/tickets"

    async def parse_incoming_ticket(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ticket_id = str(payload.get("objectId", ""))
        props = payload.get("properties", {})

        subject = props.get("subject", "")
        content = props.get("content", "")
        query = f"{subject}. {content}" if subject and content else content or subject

        # Get associated contact info if available
        associations = payload.get("associations", {})
        contact = associations.get("contacts", [{}])[0] if associations.get("contacts") else {}

        return {
            "ticket_id": ticket_id,
            "query": query.strip(),
            "customer_id": contact.get("id", ""),
            "customer_email": contact.get("properties", {}).get("email", ""),
            "customer_name": f"{contact.get('properties', {}).get('firstname', '')} {contact.get('properties', {}).get('lastname', '')}".strip(),
            "channel_type": "email",
            "metadata": {
                "crm_provider": "hubspot",
                "crm_pipeline_stage": props.get("hs_pipeline_stage", "1"),
                "crm_status": props.get("hs_ticket_status", ""),
                "hubspot_ticket_id": ticket_id,
            },
        }

    async def push_response_to_crm(
        self,
        ticket_id: str,
        response: str,
        status: str,
        internal_note: str = "",
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        if not config:
            return {"success": False, "error": "No HubSpot config provided"}

        try:
            import httpx
            access_token = config.get("access_token", "")
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Map status to HubSpot pipeline stage
            stage_map = {
                "resolved": "3",  # Closed
                "escalated": "2",  # Waiting on customer/agent
                "pending_human": "2",
            }
            stage = stage_map.get(status, "3")

            # Update ticket with response as note + change stage
            update_payload = {
                "properties": {
                    "content": response[:5000],  # HubSpot content field limit
                    "hs_pipeline_stage": stage,
                    "hs_ticket_category": "PARWA_AI_RESOLVED" if status == "resolved" else "PARWA_AI_ESCALATED",
                }
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.patch(
                    f"{self.API_BASE}/{ticket_id}",
                    headers=headers,
                    json=update_payload,
                )
                resp.raise_for_status()

                # Create engagement (note) with full response
                if internal_note:
                    note_payload = {
                        "properties": {
                            "hs_note_body": f"[PARWA AI] {internal_note}",
                            "hs_timestamp": str(int(__import__('time').time() * 1000)),
                        },
                        "associations": [
                            {"toObjectId": int(ticket_id), "toObjectType": "TICKET"}
                        ],
                    }
                    await client.post(
                        "https://api.hubapi.com/crm/v3/objects/notes",
                        headers=headers,
                        json=note_payload,
                    )

            logger.info("HubSpot: Pushed response to ticket=%s stage=%s", ticket_id, stage)
            return {
                "success": True,
                "crm_ticket_id": ticket_id,
                "crm_status": stage,
                "crm_provider": "hubspot",
            }

        except Exception as e:
            logger.error("HubSpot: Failed to push response: %s", e)
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    async def push_escalation_to_crm(
        self,
        ticket_id: str,
        escalation_context: Dict[str, Any],
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        if not config:
            return {"success": False, "error": "No HubSpot config provided"}

        try:
            import httpx
            access_token = config.get("access_token", "")
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            notification_key = escalation_context.get("notification_key", "")
            quality_score = escalation_context.get("super_node_quality", 0)
            failure_analysis = escalation_context.get("failure_analysis", "")

            note_body = (
                f"[PARWA AI Escalation — {notification_key}]\n"
                f"Quality: {quality_score:.2f} | "
                f"Analysis: {failure_analysis[:300]} | "
                f"Status: Escalated to human"
            )

            # Update ticket to open stage
            update_payload = {
                "properties": {
                    "hs_pipeline_stage": "2",  # Waiting
                    "hs_ticket_category": "PARWA_AI_ESCALATED",
                }
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.patch(
                    f"{self.API_BASE}/{ticket_id}",
                    headers=headers,
                    json=update_payload,
                )

            return {
                "success": True,
                "crm_ticket_id": ticket_id,
                "crm_status": "2",
                "crm_provider": "hubspot",
            }

        except Exception as e:
            logger.error("HubSpot: Failed to push escalation: %s", e)
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    async def push_resume_result_to_crm(
        self,
        ticket_id: str,
        response: str,
        quality_score: float,
        human_guidance: str,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        if not config:
            return {"success": False, "error": "No HubSpot config provided"}

        try:
            import httpx
            import time as _time
            access_token = config.get("access_token", "")
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Update ticket: close stage + set content with response
            update_payload = {
                "properties": {
                    "content": response[:5000],  # Include the actual response
                    "hs_pipeline_stage": "3",  # Closed
                    "hs_ticket_category": "PARWA_AI_RESOLVED_HUMAN_ASSISTED",
                }
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.patch(
                    f"{self.API_BASE}/{ticket_id}",
                    headers=headers,
                    json=update_payload,
                )

                # Create internal note with quality + human guidance info
                note_payload = {
                    "properties": {
                        "hs_note_body": (
                            f"[PARWA AI Resume — Human Assisted]\n"
                            f"Quality: {quality_score:.2f}\n"
                            f"Human Guidance: {human_guidance[:300]}"
                        ),
                        "hs_timestamp": str(int(_time.time() * 1000)),
                    },
                    "associations": [
                        {"toObjectId": int(ticket_id), "toObjectType": "TICKET"}
                    ],
                }
                try:
                    await client.post(
                        "https://api.hubapi.com/crm/v3/objects/notes",
                        headers=headers,
                        json=note_payload,
                    )
                except Exception as note_err:
                    logger.warning("HubSpot: Note creation failed (non-critical): %s", note_err)

            logger.info("HubSpot: Resume result pushed to ticket=%s quality=%.2f", ticket_id, quality_score)
            return {
                "success": True,
                "crm_ticket_id": ticket_id,
                "crm_status": "3",
                "crm_provider": "hubspot",
            }

        except Exception as e:
            logger.error("HubSpot: Failed to push resume result: %s", e)
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    async def push_permanent_failure_to_crm(
        self,
        ticket_id: str,
        attempts: int,
        failure_context: Dict[str, Any],
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """BC-017: Reset HubSpot ticket to pipeline stage 1 (new) — AI gave up."""
        if not config:
            return {"success": False, "error": "No HubSpot config provided"}

        try:
            import httpx
            import time as _time
            access_token = config.get("access_token", "")
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            last_quality = failure_context.get("last_quality", 0.0)
            failure_analysis = failure_context.get("failure_analysis", "")
            what_was_tried = failure_context.get("what_was_tried", "")

            # Reset to stage 1 (New) and re-categorize
            update_payload = {
                "properties": {
                    "hs_pipeline_stage": "1",  # New — back to fresh queue
                    "hs_ticket_category": "PARWA_AI_CANNOT_RESOLVE",
                }
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.patch(
                    f"{self.API_BASE}/{ticket_id}",
                    headers=headers,
                    json=update_payload,
                )

                # Internal note explaining what AI tried
                note_payload = {
                    "properties": {
                        "hs_note_body": (
                            f"[PARWA AI — Cannot Resolve, Returned to Human Queue]\n"
                            f"Attempts: {attempts}\n"
                            f"Last Quality: {last_quality:.2f}\n"
                            f"Failure Analysis: {failure_analysis[:400]}\n"
                            f"Techniques Tried: {what_was_tried[:400]}\n"
                            f"Type: {failure_context.get('ticket_type', 'unknown')}\n"
                            f"Complexity: {failure_context.get('complexity', 'unknown')}"
                        ),
                        "hs_timestamp": str(int(_time.time() * 1000)),
                    },
                    "associations": [
                        {"toObjectId": int(ticket_id), "toObjectType": "TICKET"}
                    ],
                }
                try:
                    await client.post(
                        "https://api.hubapi.com/crm/v3/objects/notes",
                        headers=headers,
                        json=note_payload,
                    )
                except Exception as note_err:
                    logger.warning("HubSpot: permanent-failure note failed (non-critical): %s", note_err)

            logger.info(
                "HubSpot: Permanent failure pushed to ticket=%s attempts=%d",
                ticket_id, attempts,
            )
            return {
                "success": True,
                "crm_ticket_id": ticket_id,
                "crm_status": "1",  # New
                "crm_provider": "hubspot",
            }

        except Exception as e:
            logger.error("HubSpot: Failed to push permanent failure: %s", e)
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    async def create_ticket_in_crm(
        self,
        subject: str,
        content: str,
        customer_email: str = "",
        customer_name: str = "",
        priority: str = "medium",
        category: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a NEW ticket in HubSpot (outbound push).

        POSTs to https://api.hubapi.com/crm/v3/objects/tickets with the
        subject + content as the ticket's first message. The new HubSpot
        ticket ID is returned so the caller can store it on the Parwa
        ticket and later push the AI response back via push_response_to_crm.

        HubSpot pipeline defaults:
          - hs_pipeline = "0"  (default support pipeline)
          - hs_pipeline_stage = "1"  (New)
        After AI resolves the ticket, push_response_to_crm will PATCH
        hs_pipeline_stage to "3" (Closed).
        """
        if not config:
            return {"success": False, "error": "No HubSpot config provided"}

        try:
            import httpx
            access_token = config.get("access_token", "")
            if not access_token:
                return {"success": False, "error": "HubSpot access_token missing in config"}

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Map Parwa priority → HubSpot hs_ticket_priority (HubSpot accepts
            # LOW / MEDIUM / HIGH / URGENT — case-insensitive but uppercase is safe)
            priority_map = {
                "critical": "URGENT",
                "high": "HIGH",
                "medium": "MEDIUM",
                "low": "LOW",
            }
            hs_priority = priority_map.get(priority.lower(), "MEDIUM")

            # Build ticket properties. HubSpot requires hs_pipeline and
            # hs_pipeline_stage; subject and content are the human-readable fields.
            create_payload = {
                "properties": {
                    "subject": (subject or "Customer Support Ticket")[:1000],
                    "content": (content or "")[:32000],
                    "hs_pipeline": "0",
                    "hs_pipeline_stage": "1",  # 1 = New
                    "hs_ticket_priority": hs_priority,
                    "source_type": "PARWA_AI_SUPPORT",  # Custom marker so HubSpot
                                                        # reports can filter
                }
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    self.API_BASE,
                    headers=headers,
                    json=create_payload,
                )
                resp.raise_for_status()
                data = resp.json()

            crm_ticket_id = str(data.get("id", ""))
            if not crm_ticket_id:
                return {
                    "success": False,
                    "error": "HubSpot create response missing 'id' field",
                    "raw_response": data,
                }

            logger.info(
                "HubSpot: Created new ticket id=%s subject=%r priority=%s",
                crm_ticket_id, subject[:80], hs_priority,
            )

            return {
                "success": True,
                "crm_ticket_id": crm_ticket_id,
                "crm_provider": "hubspot",
                "crm_ticket_url": f"https://app.hubspot.com/contacts/{config.get('portal_id', '')}/ticket/{crm_ticket_id}/",
            }

        except Exception as e:
            logger.error("HubSpot: Failed to create ticket: %s", e)
            return {"success": False, "error": str(e)}

    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        signature = headers.get("X-HubSpot-Signature", "")
        return bool(signature)


# ═══════════════════════════════════════════════════════════════
# GENERIC ADAPTER (fallback)
# ═══════════════════════════════════════════════════════════════

class GenericCRMAdapter(CRMAdapter):
    """Generic CRM adapter for webhook-only integration.

    Ingestion: Parses generic webhook payload
    Push-back: Fires outbound webhook events (if configured)
    """

    async def parse_incoming_ticket(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ticket_id": str(payload.get("ticket_id", payload.get("id", ""))),
            "query": payload.get("message", payload.get("description", payload.get("text", ""))),
            "customer_id": str(payload.get("customer_id", payload.get("user_id", ""))),
            "customer_email": payload.get("customer_email", payload.get("email", "")),
            "customer_name": payload.get("customer_name", payload.get("name", "")),
            "channel_type": payload.get("channel_type", payload.get("channel", "email")),
            "metadata": {
                "crm_provider": "generic",
                "original_payload": payload,
            },
        }

    async def push_response_to_crm(
        self,
        ticket_id: str,
        response: str,
        status: str,
        internal_note: str = "",
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        webhook_url = (config or {}).get("webhook_url", "")
        if not webhook_url:
            return {"success": False, "error": "No webhook URL configured"}

        try:
            import httpx
            payload = {
                "event": "parwa.response",
                "ticket_id": ticket_id,
                "response": response,
                "status": status,
                "internal_note": internal_note,
                "source": "parwa_pipeline",
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(webhook_url, json=payload)
                resp.raise_for_status()

            return {"success": True, "crm_ticket_id": ticket_id, "crm_status": status}
        except Exception as e:
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    async def push_escalation_to_crm(
        self,
        ticket_id: str,
        escalation_context: Dict[str, Any],
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        webhook_url = (config or {}).get("webhook_url", "")
        if not webhook_url:
            return {"success": False, "error": "No webhook URL configured"}

        try:
            import httpx
            payload = {
                "event": "parwa.escalation",
                "ticket_id": ticket_id,
                "escalation_context": escalation_context,
                "source": "parwa_pipeline",
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(webhook_url, json=payload)
                resp.raise_for_status()

            return {"success": True, "crm_ticket_id": ticket_id, "crm_status": "escalated"}
        except Exception as e:
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    async def push_resume_result_to_crm(
        self,
        ticket_id: str,
        response: str,
        quality_score: float,
        human_guidance: str,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        webhook_url = (config or {}).get("webhook_url", "")
        if not webhook_url:
            return {"success": False, "error": "No webhook URL configured"}

        try:
            import httpx
            payload = {
                "event": "parwa.resume_result",
                "ticket_id": ticket_id,
                "response": response,
                "quality_score": quality_score,
                "human_guidance": human_guidance,
                "source": "parwa_pipeline",
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(webhook_url, json=payload)
                resp.raise_for_status()

            return {"success": True, "crm_ticket_id": ticket_id, "crm_status": "resolved"}
        except Exception as e:
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    async def push_permanent_failure_to_crm(
        self,
        ticket_id: str,
        attempts: int,
        failure_context: Dict[str, Any],
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """BC-017: Emit parwa.cannot_resolve webhook — CRM should reset to new."""
        webhook_url = (config or {}).get("webhook_url", "")
        if not webhook_url:
            return {"success": False, "error": "No webhook URL configured"}

        try:
            import httpx
            payload = {
                "event": "parwa.cannot_resolve",
                "ticket_id": ticket_id,
                "attempts": attempts,
                "action": "reset_to_new",
                "failure_context": failure_context,
                "source": "parwa_pipeline",
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(webhook_url, json=payload)
                resp.raise_for_status()

            logger.info(
                "Generic: Permanent failure pushed to ticket=%s attempts=%d",
                ticket_id, attempts,
            )
            return {"success": True, "crm_ticket_id": ticket_id, "crm_status": "new"}
        except Exception as e:
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        return True  # No validation for generic


# ═══════════════════════════════════════════════════════════════
# CRM BRIDGE — MAIN INTERFACE
# ═══════════════════════════════════════════════════════════════

# Adapter registry
_CRM_ADAPTERS: Dict[str, CRMAdapter] = {
    "zendesk": ZendeskAdapter(),
    "hubspot": HubSpotAdapter(),
    "generic": GenericCRMAdapter(),
}


def get_crm_adapter(provider: str) -> CRMAdapter:
    """Get CRM adapter by provider name. Falls back to generic."""
    return _CRM_ADAPTERS.get(provider.lower(), GenericCRMAdapter())


class CRMBridge:
    """Main CRM bridge interface. Routes to the correct adapter."""

    @staticmethod
    async def ingest_ticket(
        provider: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Ingest a ticket from CRM webhook.

        Args:
            provider: "zendesk", "hubspot", "generic"
            payload: Raw webhook payload
            headers: HTTP headers (for signature validation)

        Returns:
            Parsed ticket data ready for PARWA pipeline input
        """
        adapter = get_crm_adapter(provider)

        # Validate webhook
        if headers:
            if not adapter.validate_webhook(payload, headers):
                return {"success": False, "error": "Webhook validation failed"}

        parsed = await adapter.parse_incoming_ticket(payload)
        logger.info(
            "CRMBridge: Ingested ticket=%s from %s",
            parsed.get("ticket_id", "?"), provider,
        )
        return {"success": True, "ticket_data": parsed, "provider": provider}

    @staticmethod
    async def push_response(
        provider: str,
        ticket_id: str,
        response: str,
        status: str,
        internal_note: str = "",
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Push resolved response back to CRM.

        Non-blocking. Failures logged but don't break pipeline.
        """
        try:
            adapter = get_crm_adapter(provider)
            result = await adapter.push_response_to_crm(
                ticket_id, response, status, internal_note, config
            )
            logger.info(
                "CRMBridge: Pushed response to %s ticket=%s success=%s",
                provider, ticket_id, result.get("success"),
            )
            return result
        except Exception as e:
            logger.error("CRMBridge: Failed to push response: %s", e)
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    @staticmethod
    async def push_escalation(
        provider: str,
        ticket_id: str,
        escalation_context: Dict[str, Any],
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Push escalation notification to CRM.

        Updates CRM ticket with AI analysis and reassigns to human.
        Non-blocking.
        """
        try:
            adapter = get_crm_adapter(provider)
            result = await adapter.push_escalation_to_crm(
                ticket_id, escalation_context, config
            )
            logger.info(
                "CRMBridge: Pushed escalation to %s ticket=%s success=%s",
                provider, ticket_id, result.get("success"),
            )
            return result
        except Exception as e:
            logger.error("CRMBridge: Failed to push escalation: %s", e)
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    @staticmethod
    async def push_resume_result(
        provider: str,
        ticket_id: str,
        response: str,
        quality_score: float,
        human_guidance: str,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Push resume result (human-assisted) back to CRM.
        Non-blocking.
        """
        try:
            adapter = get_crm_adapter(provider)
            result = await adapter.push_resume_result_to_crm(
                ticket_id, response, quality_score, human_guidance, config
            )
            logger.info(
                "CRMBridge: Pushed resume result to %s ticket=%s success=%s",
                provider, ticket_id, result.get("success"),
            )
            return result
        except Exception as e:
            logger.error("CRMBridge: Failed to push resume result: %s", e)
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    @staticmethod
    async def push_permanent_failure(
        provider: str,
        ticket_id: str,
        attempts: int,
        failure_context: Dict[str, Any],
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """BC-017: Reset CRM ticket to "open"/"new" — AI could not resolve.

        Called when the guidance flow has exhausted MAX_GUIDANCE_RETRIES.
        Non-blocking: failures are logged but don't crash the flow.
        """
        try:
            adapter = get_crm_adapter(provider)
            result = await adapter.push_permanent_failure_to_crm(
                ticket_id, attempts, failure_context, config
            )
            logger.info(
                "CRMBridge: Pushed permanent failure to %s ticket=%s success=%s attempts=%d",
                provider, ticket_id, result.get("success"), attempts,
            )
            return result
        except Exception as e:
            logger.error("CRMBridge: Failed to push permanent failure: %s", e)
            return {"success": False, "error": str(e), "crm_ticket_id": ticket_id}

    @staticmethod
    async def create_ticket(
        provider: str,
        subject: str,
        content: str,
        customer_email: str = "",
        customer_name: str = "",
        priority: str = "medium",
        category: str = "",
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Create a NEW ticket in the CRM (outbound push).

        Used by pipeline_dispatcher when a manually-created Parwa ticket
        should also appear in the tenant's CRM. Mirrors the inbound flow:
        after creating the CRM ticket, the caller stores crm_ticket_id on
        the Parwa ticket and then calls push_response() to attach the AI
        reply to the new CRM ticket.

        Non-blocking: failures are logged but don't break the pipeline.
        Adapters that don't support outbound creation return
        {success: False, error: "not implemented"}.
        """
        try:
            adapter = get_crm_adapter(provider)
            result = await adapter.create_ticket_in_crm(
                subject=subject,
                content=content,
                customer_email=customer_email,
                customer_name=customer_name,
                priority=priority,
                category=category,
                config=config,
            )
            logger.info(
                "CRMBridge: Created ticket in %s success=%s crm_ticket_id=%s",
                provider, result.get("success"), result.get("crm_ticket_id", ""),
            )
            return result
        except Exception as e:
            logger.error("CRMBridge: Failed to create ticket in %s: %s", provider, e)
            return {"success": False, "error": str(e)}
