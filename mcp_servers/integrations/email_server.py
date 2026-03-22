"""
PARWA Email MCP Server.

MCP server for email operations via Brevo integration.
Wraps the EmailClient and exposes it as MCP tools.
"""
from typing import Dict, Any, List
import asyncio

from mcp_servers.base_server import BaseMCPServer
from shared.integrations.email_client import EmailClient, EmailStatus, EmailPriority
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class EmailServer(BaseMCPServer):
    """
    MCP Server for email operations.

    Tools provided:
    - send_email: Send a transactional email
    - send_bulk_emails: Send emails to multiple recipients
    - get_email_status: Get delivery status of an email
    - get_templates: List available email templates

    This server wraps the EmailClient and exposes its functionality
    through the MCP protocol.
    """

    def __init__(
        self,
        config: Dict[str, Any] = None,
        email_client: EmailClient = None
    ) -> None:
        """
        Initialize Email MCP Server.

        Args:
            config: Server configuration
            email_client: Optional EmailClient instance (created if not provided)
        """
        self._email_client = email_client or EmailClient()
        super().__init__(name="email_server", config=config)

    def _register_tools(self) -> None:
        """Register all email tools."""
        # Tool: send_email
        self.register_tool(
            name="send_email",
            description=(
                "Send a transactional email to one or more recipients. "
                "Supports HTML content and optional templates."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content (HTML)",
                    },
                    "template_id": {
                        "type": "string",
                        "description": "Optional template ID to use",
                    },
                },
                "required": ["to", "subject", "body"],
            },
            handler=self._handle_send_email,
        )

        # Tool: send_bulk_emails
        self.register_tool(
            name="send_bulk_emails",
            description=(
                "Send bulk emails to multiple recipients. "
                "Maximum 10,000 recipients per batch."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "recipients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of recipient email addresses",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content (HTML)",
                    },
                },
                "required": ["recipients", "subject", "body"],
            },
            handler=self._handle_send_bulk_emails,
        )

        # Tool: get_email_status
        self.register_tool(
            name="get_email_status",
            description="Get the delivery status of a previously sent email.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "Message ID from send_email response",
                    },
                },
                "required": ["email_id"],
            },
            handler=self._handle_get_email_status,
        )

        # Tool: get_templates
        self.register_tool(
            name="get_templates",
            description="List available email templates.",
            parameters_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=self._handle_get_templates,
        )

    async def _on_start(self) -> None:
        """Connect to email service on startup."""
        if not self._email_client.is_connected:
            success = await self._email_client.connect()
            if not success:
                raise RuntimeError("Failed to connect to email service")

    async def _on_stop(self) -> None:
        """Disconnect from email service on shutdown."""
        await self._email_client.disconnect()

    async def _handle_send_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle send_email tool call.

        Args:
            params: Tool parameters with to, subject, body, template_id (optional)

        Returns:
            Email send result with message_id and status
        """
        to = params.get("to")
        subject = params.get("subject")
        body = params.get("body")
        template_id = params.get("template_id")

        try:
            if template_id:
                # Use template if provided
                result = await self._email_client.send_template_email(
                    to=to,
                    template_id=int(template_id),
                    params={"subject": subject, "body": body},
                )
            else:
                result = await self._email_client.send_email(
                    to=to,
                    subject=subject,
                    html_content=body,
                )

            return {
                "message_id": result.get("message_id"),
                "status": result.get("status"),
                "to": result.get("to"),
                "subject": result.get("subject"),
            }

        except ValueError as e:
            logger.error({
                "event": "email_send_validation_error",
                "error": str(e),
            })
            return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error({
                "event": "email_send_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to send email"}

    async def _handle_send_bulk_emails(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle send_bulk_emails tool call.

        Args:
            params: Tool parameters with recipients, subject, body

        Returns:
            Bulk send result with batch_id and recipient_count
        """
        recipients = params.get("recipients", [])
        subject = params.get("subject")
        body = params.get("body")

        try:
            # Format recipients for bulk API
            formatted_recipients = [
                {"email": email} for email in recipients
            ]

            result = await self._email_client.send_bulk_email(
                recipients=formatted_recipients,
                subject=subject,
                html_content=body,
            )

            return {
                "batch_id": result.get("batch_id"),
                "recipient_count": result.get("recipient_count"),
                "status": result.get("status"),
            }

        except ValueError as e:
            logger.error({
                "event": "bulk_email_validation_error",
                "error": str(e),
            })
            return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error({
                "event": "bulk_email_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to send bulk emails"}

    async def _handle_get_email_status(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle get_email_status tool call.

        Args:
            params: Tool parameters with email_id

        Returns:
            Email delivery status
        """
        email_id = params.get("email_id")

        try:
            result = await self._email_client.get_email_status(email_id)

            return {
                "message_id": result.get("message_id"),
                "status": result.get("status"),
                "delivered_at": result.get("delivered_at"),
                "opened": result.get("opened", False),
                "clicked": result.get("clicked", False),
            }

        except ValueError as e:
            logger.error({
                "event": "email_status_validation_error",
                "error": str(e),
            })
            return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error({
                "event": "email_status_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to get email status"}

    async def _handle_get_templates(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_templates tool call.

        Args:
            params: Empty parameters

        Returns:
            List of available templates
        """
        try:
            templates = await self._email_client.get_templates()

            return {
                "templates": templates,
                "count": len(templates),
            }

        except Exception as e:
            logger.error({
                "event": "templates_fetch_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to get templates"}
