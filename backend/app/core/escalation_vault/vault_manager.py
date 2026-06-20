"""
Escalation Vault Manager — High-Level Operations

The single entry point for all vault operations.
Called by:
  - Node 8 (save escalation when stuck)
  - JARVIS notify (write human guidance)
  - Resume pipeline (load state + save result)
  - CRM bridge (update CRM push-back status)
  - API endpoints (read/list escalations)

All methods are async. All failures are logged but non-fatal.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.core.escalation_vault.vault_db import (
    CRM_FAILED, CRM_PENDING, CRM_UPDATED,
    HUMAN_GUIDANCE_PROVIDED, HUMAN_PENDING,
    REPROCESS_DONE, REPROCESS_FAILED, REPROCESS_PENDING,
    SOURCE_NODE_8, get_vault_db,
)
from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.vault_manager")


class VaultManager:
    """High-level escalation vault operations."""

    # ── Save Escalation (called by Node 8) ───────────────────

    @staticmethod
    async def save_escalation_from_pipeline(
        state: PipelineV2State,
        escalation_context: Optional[Dict[str, Any]] = None,
        escalation_source: str = SOURCE_NODE_8,
        crm_ticket_id: str = "",
        crm_provider: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Save full pipeline state to vault when ticket is escalated.

        Extracts all relevant fields from pipeline state and saves them
        so the ticket can be resumed later with human guidance.
        """
        try:
            vault_db = get_vault_db()
            data = {
                "tenant_id": state.get("tenant_id", ""),
                "original_ticket_id": state.get("ticket_id", ""),
                "notification_key": escalation_context.get("notification_key", "") if escalation_context else "",
                "escalation_source": escalation_source,

                # ── Pipeline State ──
                "original_query": state.get("query", ""),
                "ticket_type": state.get("ticket_type", ""),
                "complexity": state.get("complexity", ""),
                "required_action": state.get("required_action", ""),
                "action_details": state.get("action_details", {}),
                "knowledge_context": state.get("knowledge_context", []),
                "crm_data": state.get("crm_data", {}),
                "customer_context": state.get("customer_context", {}),
                "previous_attempts": escalation_context.get("previous_attempts", []) if escalation_context else [],
                "failure_analysis": escalation_context.get("failure_analysis", "") if escalation_context else "",
                "quality_score": escalation_context.get("super_node_quality", state.get("quality_score", 0.0)) if escalation_context else state.get("quality_score", 0.0),
                "technique_log": state.get("technique_log", []),
                "variant_tier": state.get("variant_tier", "parwa"),
                "wiki_section_c": state.get("wiki_section_c", []),
                "wiki_patterns": state.get("wiki_patterns", []),
                "escalation_context": escalation_context or {},
                "combined_answer": state.get("combined_answer", ""),
                "formatted_response": state.get("formatted_response", ""),

                # ── CRM ──
                "crm_ticket_id": crm_ticket_id,
                "crm_provider": crm_provider,
            }
            record = await vault_db.save_escalation(data)
            logger.info(
                "VaultManager: Saved escalation=%s ticket=%s key=%s",
                record["escalation_id"][:8], record["original_ticket_id"],
                record["notification_key"],
            )
            return record
        except Exception as e:
            logger.error("VaultManager: Failed to save escalation: %s", e, exc_info=True)
            return None

    # ── Human Guidance (called by JARVIS notify/API) ──────────

    @staticmethod
    async def provide_human_guidance(
        escalation_id: str,
        guidance: str,
        source: str = "jarvis_chat",
    ) -> Optional[Dict[str, Any]]:
        """Write human guidance to vault. Triggers reprocess eligibility."""
        try:
            vault_db = get_vault_db()
            record = await vault_db.update_human_guidance(escalation_id, guidance, source)
            if record:
                logger.info(
                    "VaultManager: Guidance received for escalation=%s source=%s",
                    escalation_id[:8], source,
                )
            return record
        except Exception as e:
            logger.error("VaultManager: Failed to save guidance: %s", e)
            return None

    # ── Provide Guidance by Notification Key ──────────────────

    @staticmethod
    async def provide_guidance_by_notification(
        notification_key: str,
        guidance: str,
        source: str = "jarvis_chat",
    ) -> Optional[Dict[str, Any]]:
        """Find escalation by PARWA-NFY key and add guidance."""
        try:
            vault_db = get_vault_db()
            record = await vault_db.get_escalation_by_notification(notification_key)
            if not record:
                logger.warning("VaultManager: No escalation found for key=%s", notification_key)
                return None
            return await VaultManager.provide_human_guidance(
                record["escalation_id"], guidance, source
            )
        except Exception as e:
            logger.error("VaultManager: Failed to save guidance by notification: %s", e)
            return None

    # ── Load for Resume (called by resume pipeline) ───────────

    @staticmethod
    async def load_for_resume(escalation_id: str) -> Optional[Dict[str, Any]]:
        """Load full escalation data for resume processing.
        
        Returns the vault record with all saved pipeline state + human guidance.
        Returns None if not found or not eligible for resume.
        """
        try:
            vault_db = get_vault_db()
            record = await vault_db.get_escalation(escalation_id)
            if not record:
                logger.warning("VaultManager: Escalation not found: %s", escalation_id)
                return None
            if record.get("human_status") != HUMAN_GUIDANCE_PROVIDED:
                logger.warning(
                    "VaultManager: Escalation %s not ready for resume (status=%s)",
                    escalation_id[:8], record.get("human_status"),
                )
                return None
            if record.get("reprocess_status") != REPROCESS_PENDING:
                logger.warning(
                    "VaultManager: Escalation %s already reprocessed (status=%s)",
                    escalation_id[:8], record.get("reprocess_status"),
                )
                return None
            return record
        except Exception as e:
            logger.error("VaultManager: Failed to load for resume: %s", e)
            return None

    # ── Save Resume Result ───────────────────────────────────

    @staticmethod
    async def save_resume_result(
        escalation_id: str,
        result: str,
        quality_score: float,
        technique_log: Optional[List[Dict]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Save the result of resume pipeline processing."""
        try:
            vault_db = get_vault_db()
            record = await vault_db.update_reprocess_result(
                escalation_id, result, quality_score, technique_log
            )
            if record:
                logger.info(
                    "VaultManager: Resume result saved for escalation=%s quality=%.4f",
                    escalation_id[:8], quality_score,
                )
            return record
        except Exception as e:
            logger.error("VaultManager: Failed to save resume result: %s", e)
            return None

    # ── CRM Push-Back Status ──────────────────────────────────

    @staticmethod
    async def update_crm_push_back(
        escalation_id: str,
        status: str,
        crm_ticket_id: str = "",
        crm_response: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update CRM push-back status after sending response to CRM."""
        try:
            vault_db = get_vault_db()
            record = await vault_db.update_crm_status(
                escalation_id, status, crm_ticket_id, crm_response
            )
            return record
        except Exception as e:
            logger.error("VaultManager: Failed to update CRM status: %s", e)
            return None

    # ── Queries ───────────────────────────────────────────────

    @staticmethod
    async def get_escalation(escalation_id: str) -> Optional[Dict[str, Any]]:
        """Get a single escalation by ID."""
        try:
            vault_db = get_vault_db()
            return await vault_db.get_escalation(escalation_id)
        except Exception as e:
            logger.error("VaultManager: Failed to get escalation: %s", e)
            return None

    @staticmethod
    async def get_escalation_by_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get escalation by original PARWA ticket ID."""
        try:
            vault_db = get_vault_db()
            return await vault_db.get_escalation_by_ticket(ticket_id)
        except Exception as e:
            logger.error("VaultManager: Failed to get escalation by ticket: %s", e)
            return None

    @staticmethod
    async def get_escalation_by_notification(notification_key: str) -> Optional[Dict[str, Any]]:
        """Get escalation by PARWA-NFY notification key."""
        try:
            vault_db = get_vault_db()
            return await vault_db.get_escalation_by_notification(notification_key)
        except Exception as e:
            logger.error("VaultManager: Failed to get escalation by notification: %s", e)
            return None

    @staticmethod
    async def get_pending_resumes(tenant_id: str) -> List[Dict[str, Any]]:
        """Get escalations awaiting reprocess (have guidance, not yet reprocessed)."""
        try:
            vault_db = get_vault_db()
            return await vault_db.get_pending_resumes(tenant_id)
        except Exception as e:
            logger.error("VaultManager: Failed to get pending resumes: %s", e)
            return []

    @staticmethod
    async def list_escalations(
        tenant_id: str,
        human_status: Optional[str] = None,
        reprocess_status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List escalations with optional filters."""
        try:
            vault_db = get_vault_db()
            return await vault_db.list_escalations(tenant_id, human_status, reprocess_status, limit)
        except Exception as e:
            logger.error("VaultManager: Failed to list escalations: %s", e)
            return []

    @staticmethod
    async def get_vault_stats(tenant_id: str) -> Dict[str, Any]:
        """Get vault statistics for a tenant."""
        try:
            vault_db = get_vault_db()
            return await vault_db.get_vault_stats(tenant_id)
        except Exception as e:
            logger.error("VaultManager: Failed to get vault stats: %s", e)
            return {"tenant_id": tenant_id, "error": str(e)}
