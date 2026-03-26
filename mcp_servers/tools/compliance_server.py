"""
PARWA MCP Compliance Server.

Provides compliance operations via MCP including:
- GDPR compliance checks and data operations
- Jurisdiction-specific rule lookups
- Compliance action validation

All operations are tool-based and inherit from BaseMCPServer.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio

from mcp_servers.base_server import BaseMCPServer
from shared.core_functions.logger import get_logger
from shared.compliance.gdpr_engine import GDPREngine, GDPRRequestType
from shared.compliance.jurisdiction import JurisdictionManager

logger = get_logger(__name__)


class ComplianceServer(BaseMCPServer):
    """
    MCP Server for compliance operations.

    Provides tools for GDPR compliance, jurisdiction rules,
    and compliance action validation.

    Tools:
        - check_compliance: Check if an action is compliant
        - get_jurisdiction_rules: Get rules for a jurisdiction
        - gdpr_export: Export user data (GDPR Article 20)
        - gdpr_delete: Delete user data (GDPR Article 17)
    """

    # Actions that require compliance checks
    COMPLIANCE_ACTIONS = {
        "data_export": {"requires_consent": False, "audit_required": True},
        "data_deletion": {"requires_consent": False, "audit_required": True},
        "data_sharing": {"requires_consent": True, "audit_required": True},
        "marketing_email": {"requires_consent": True, "audit_required": False},
        "third_party_access": {"requires_consent": True, "audit_required": True},
        "cross_border_transfer": {"requires_consent": True, "audit_required": True},
        "profiling": {"requires_consent": True, "audit_required": True},
        "automated_decision": {"requires_consent": True, "audit_required": True},
    }

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        gdpr_engine: Optional[GDPREngine] = None
    ) -> None:
        """
        Initialize Compliance Server.

        Args:
            config: Optional server configuration
            gdpr_engine: Optional GDPR engine instance
        """
        super().__init__(name="compliance_server", config=config)
        self._gdpr_engine = gdpr_engine or GDPREngine()
        self._jurisdiction_manager = JurisdictionManager()
        self._audit_log: List[Dict[str, Any]] = []

    def _register_tools(self) -> None:
        """Register all compliance tools."""
        self.register_tool(
            name="check_compliance",
            description="Check if an action is compliant with regulations",
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action to check",
                        "enum": list(self.COMPLIANCE_ACTIONS.keys())
                    },
                    "context": {
                        "type": "object",
                        "description": "Context for the action"
                    },
                    "jurisdiction": {
                        "type": "string",
                        "description": "Jurisdiction code (e.g., 'EU', 'US', 'CA')"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID for consent check"
                    }
                },
                "required": ["action", "context"]
            },
            handler=self._handle_check_compliance
        )

        self.register_tool(
            name="get_jurisdiction_rules",
            description="Get compliance rules for a specific jurisdiction",
            parameters_schema={
                "type": "object",
                "properties": {
                    "jurisdiction": {
                        "type": "string",
                        "description": "Jurisdiction code (e.g., 'EU', 'US', 'CA')"
                    }
                },
                "required": ["jurisdiction"]
            },
            handler=self._handle_get_jurisdiction_rules
        )

        self.register_tool(
            name="gdpr_export",
            description="Export user data for GDPR portability (Article 20)",
            parameters_schema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID to export data for"
                    },
                    "include_pii": {
                        "type": "boolean",
                        "description": "Include PII in export",
                        "default": False
                    }
                },
                "required": ["user_id"]
            },
            handler=self._handle_gdpr_export
        )

        self.register_tool(
            name="gdpr_delete",
            description="Delete user data for GDPR erasure (Article 17)",
            parameters_schema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID to delete data for"
                    },
                    "retention_exceptions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Legal reasons to retain some data"
                    }
                },
                "required": ["user_id"]
            },
            handler=self._handle_gdpr_delete
        )

    async def _on_start(self) -> None:
        """Initialize compliance server resources."""
        logger.info({
            "event": "compliance_server_starting",
            "server": self._name,
        })
        await asyncio.sleep(0.01)

    async def _handle_check_compliance(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle check_compliance tool call.

        Args:
            params: Tool parameters

        Returns:
            Dict with compliance status
        """
        action = params["action"]
        context = params.get("context", {})
        jurisdiction = params.get("jurisdiction", "EU")
        user_id = params.get("user_id")

        # Get action requirements
        action_config = self.COMPLIANCE_ACTIONS.get(action, {})
        requires_consent = action_config.get("requires_consent", False)
        audit_required = action_config.get("audit_required", False)

        # Check jurisdiction rules
        jurisdiction_result = self._check_jurisdiction_compliance(
            action, jurisdiction, context
        )

        # Check consent if required
        consent_status = None
        if requires_consent and user_id:
            consent_status = self._check_user_consent(user_id, action)

        # Determine overall compliance
        is_compliant = True
        issues = []

        if not jurisdiction_result.get("compliant", True):
            is_compliant = False
            issues.extend(jurisdiction_result.get("issues", []))

        if consent_status is not None and not consent_status.get("has_consent", True):
            is_compliant = False
            issues.append(f"Missing consent for action: {action}")

        # Create audit record if required
        if audit_required:
            audit_record = {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "user_id": user_id,
                "jurisdiction": jurisdiction,
                "compliant": is_compliant,
                "context": context
            }
            self._audit_log.append(audit_record)

        result = {
            "status": "success",
            "compliant": is_compliant,
            "action": action,
            "jurisdiction": jurisdiction,
            "requires_consent": requires_consent,
            "consent_status": consent_status,
            "issues": issues if issues else None
        }

        logger.info({
            "event": "compliance_check",
            "action": action,
            "jurisdiction": jurisdiction,
            "compliant": is_compliant
        })

        return result

    async def _handle_get_jurisdiction_rules(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle get_jurisdiction_rules tool call.

        Args:
            params: Tool parameters

        Returns:
            Dict with jurisdiction rules
        """
        jurisdiction = params["jurisdiction"]

        try:
            rules = self._jurisdiction_manager.get_rules(jurisdiction)

            return {
                "status": "success",
                "jurisdiction": jurisdiction,
                "rules": rules
            }

        except Exception as e:
            logger.error({
                "event": "jurisdiction_rules_error",
                "jurisdiction": jurisdiction,
                "error": str(e)
            })

            return {
                "status": "error",
                "message": f"Jurisdiction '{jurisdiction}' not found",
                "available_jurisdictions": self._jurisdiction_manager.list_jurisdictions()
            }

    async def _handle_gdpr_export(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle gdpr_export tool call.

        Args:
            params: Tool parameters

        Returns:
            Dict with export data or reference
        """
        user_id = params["user_id"]
        include_pii = params.get("include_pii", False)

        try:
            # Create request
            request = self._gdpr_engine.create_access_request(
                user_id=user_id,
                request_type=GDPRRequestType.PORTABILITY
            )

            # Export data
            export = self._gdpr_engine.export_user_data(
                user_id=user_id,
                request=request,
                include_pii=include_pii
            )

            logger.info({
                "event": "gdpr_export",
                "user_id": user_id,
                "request_id": request.request_id,
                "records": export.total_records
            })

            return {
                "status": "success",
                "request_id": request.request_id,
                "export_reference": export.request_id,
                "user_id": user_id,
                "total_records": export.total_records,
                "data_categories": list(export.data_categories.keys()),
                "expires_at": export.expires_at.isoformat() if export.expires_at else None,
                "processing_time_ms": export.processing_time_ms
            }

        except Exception as e:
            logger.error({
                "event": "gdpr_export_error",
                "user_id": user_id,
                "error": str(e)
            })

            return {
                "status": "error",
                "message": f"GDPR export failed: {str(e)}"
            }

    async def _handle_gdpr_delete(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle gdpr_delete tool call.

        Args:
            params: Tool parameters

        Returns:
            Dict with deletion status
        """
        user_id = params["user_id"]
        retention_exceptions = params.get("retention_exceptions", [])

        try:
            # Create request
            request = self._gdpr_engine.create_access_request(
                user_id=user_id,
                request_type=GDPRRequestType.ERASURE
            )

            # Process erasure
            result = self._gdpr_engine.process_erasure_request(
                user_id=user_id,
                request=request,
                retention_exceptions=retention_exceptions
            )

            logger.info({
                "event": "gdpr_delete",
                "user_id": user_id,
                "request_id": request.request_id,
                "success": result.success,
                "records_erased": result.records_erased
            })

            return {
                "status": "success" if result.success else "partial",
                "request_id": request.request_id,
                "user_id": user_id,
                "records_processed": result.records_processed,
                "records_erased": result.records_erased,
                "records_retained": result.records_retained,
                "retention_reasons": result.retention_reasons,
                "anonymized_fields": result.anonymized_fields,
                "processing_time_ms": result.processing_time_ms
            }

        except Exception as e:
            logger.error({
                "event": "gdpr_delete_error",
                "user_id": user_id,
                "error": str(e)
            })

            return {
                "status": "error",
                "message": f"GDPR deletion failed: {str(e)}"
            }

    def _check_jurisdiction_compliance(
        self, action: str, jurisdiction: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check action compliance with jurisdiction rules."""
        try:
            rules = self._jurisdiction_manager.get_rules(jurisdiction)

            issues = []
            action_rules = rules.get("actions", {}).get(action, {})

            # Check if action is allowed
            if action_rules.get("restricted", False):
                if not context.get("legal_basis"):
                    issues.append(f"Action '{action}' requires legal basis in {jurisdiction}")

            # Check data type restrictions
            data_types = context.get("data_types", [])
            restricted_types = rules.get("restricted_data_types", [])
            for dt in data_types:
                if dt in restricted_types:
                    issues.append(f"Data type '{dt}' is restricted in {jurisdiction}")

            return {
                "compliant": len(issues) == 0,
                "issues": issues if issues else None
            }

        except Exception:
            # Default to compliant if jurisdiction not found
            return {"compliant": True, "issues": None}

    def _check_user_consent(
        self, user_id: str, action: str
    ) -> Dict[str, Any]:
        """Check if user has consented to action."""
        # Mock consent check - in production, check actual consent records
        return {
            "has_consent": True,
            "consent_date": datetime.now().isoformat(),
            "consent_type": "explicit"
        }


def get_compliance_server() -> ComplianceServer:
    """
    Get a ComplianceServer instance.

    Returns:
        ComplianceServer instance
    """
    return ComplianceServer()
