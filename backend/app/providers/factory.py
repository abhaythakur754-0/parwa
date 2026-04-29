"""
PARWA Provider Factory

Factory for creating provider instances. Uses the registry to find
provider classes and instantiates them with the provided configuration.

Usage:
    from app.providers import ProviderFactory, ProviderType

    # Create an email provider
    email = ProviderFactory.create(
        provider_type=ProviderType.EMAIL,
        provider_name="brevo",
        config={"api_key": "your-api-key"}
    )

    # Send an email
    result = email.send_email(EmailMessage(...))

    # Create an SMS provider
    sms = ProviderFactory.create(
        provider_type=ProviderType.SMS,
        provider_name="twilio",
        config={
            "account_sid": "your-sid",
            "auth_token": "your-token",
            "phone_number": "+1234567890"
        }
    )

    # Send SMS
    result = sms.send_sms(SMSMessage(...))
"""

from typing import Any, Dict, List

from app.providers.base import (
    BaseProvider,
    ChatMessage,
    ChatProvider,
    EmailMessage,
    EmailProvider,
    ProviderType,
    SMSMessage,
    SMSProvider,
    VoiceCall,
    VoiceProvider,
)
from app.providers.registry import ProviderRegistry


class ProviderFactory:
    """Factory for creating provider instances.

    This is the main entry point for creating any provider.
    It looks up the provider class in the registry and instantiates
    it with the provided configuration.
    """

    @classmethod
    def create(
        cls,
        provider_type: ProviderType,
        provider_name: str,
        config: Dict[str, Any],
        validate: bool = True,
    ) -> BaseProvider:
        """Create a provider instance.

        Args:
            provider_type: Type of provider (email, sms, etc.)
            provider_name: Name of the provider (brevo, twilio, etc.)
            config: Provider-specific configuration dict.
            validate: Whether to validate the connection after creation.

        Returns:
            Provider instance.

        Raises:
            ValueError: If provider not found or config invalid.
        """
        provider_class = ProviderRegistry.get_provider_class(
            provider_type, provider_name
        )

        # Create instance
        provider = provider_class(config)

        # Validate connection if requested
        if validate:
            result = provider.test_connection()
            if not result.success:
                raise ValueError(
                    f"Provider connection test failed: {result.error_message}"
                )

        return provider

    @classmethod
    def create_from_settings(
        cls,
        provider_type: ProviderType,
        settings: Any,
    ) -> BaseProvider:
        """Create a provider from application settings.

        Looks for provider configuration in settings and creates
        the appropriate provider instance.

        Args:
            provider_type: Type of provider to create.
            settings: Application settings object.

        Returns:
            Provider instance.
        """
        # Get provider name from settings
        provider_name = cls._get_provider_name_from_settings(provider_type, settings)

        # Get config from settings
        config = cls._get_provider_config_from_settings(
            provider_type, provider_name, settings
        )

        return cls.create(provider_type, provider_name, config, validate=False)

    @classmethod
    def list_available(
        cls,
        provider_type: ProviderType = None,
    ) -> List[Dict[str, Any]]:
        """List all available providers.

        Args:
            provider_type: Optional filter by type.

        Returns:
            List of provider info dicts.
        """
        return ProviderRegistry.list_providers(provider_type)

    @classmethod
    def get_provider_info(
        cls,
        provider_type: ProviderType,
        provider_name: str,
    ) -> Dict[str, Any]:
        """Get information about a specific provider.

        Args:
            provider_type: Type of provider.
            provider_name: Name of the provider.

        Returns:
            Dict with provider information.
        """
        return ProviderRegistry.get_metadata(provider_type, provider_name)

    @classmethod
    def _get_provider_name_from_settings(
        cls,
        provider_type: ProviderType,
        settings: Any,
    ) -> str:
        """Get provider name from settings.

        Args:
            provider_type: Type of provider.
            settings: Settings object.

        Returns:
            Provider name string.
        """
        type_key = (
            provider_type.value
            if isinstance(provider_type, ProviderType)
            else provider_type
        )

        # Map provider types to settings attributes
        settings_map = {
            "email": getattr(settings, "EMAIL_PROVIDER", "brevo"),
            "sms": getattr(settings, "SMS_PROVIDER", "twilio"),
            "voice": getattr(settings, "VOICE_PROVIDER", "twilio"),
            "chat": getattr(settings, "CHAT_PROVIDER", "slack"),
        }

        return settings_map.get(type_key, "")

    @classmethod
    def _get_provider_config_from_settings(
        cls,
        provider_type: ProviderType,
        provider_name: str,
        settings: Any,
    ) -> Dict[str, Any]:
        """Get provider configuration from settings.

        Args:
            provider_type: Type of provider.
            provider_name: Name of the provider.
            settings: Settings object.

        Returns:
            Configuration dict.
        """
        type_key = (
            provider_type.value
            if isinstance(provider_type, ProviderType)
            else provider_type
        )

        # Email providers
        if type_key == "email":
            if provider_name == "brevo":
                return {
                    "api_key": getattr(settings, "BREVO_API_KEY", ""),
                    "from_email": getattr(settings, "FROM_EMAIL", "noreply@parwa.ai"),
                    "from_name": getattr(settings, "FROM_NAME", "PARWA"),
                }
            elif provider_name == "sendgrid":
                return {
                    "api_key": getattr(settings, "SENDGRID_API_KEY", ""),
                    "from_email": getattr(settings, "FROM_EMAIL", "noreply@parwa.ai"),
                }
            elif provider_name == "mailgun":
                return {
                    "api_key": getattr(settings, "MAILGUN_API_KEY", ""),
                    "domain": getattr(settings, "MAILGUN_DOMAIN", ""),
                }
            elif provider_name == "ses":
                return {
                    "access_key": getattr(settings, "AWS_ACCESS_KEY_ID", ""),
                    "secret_key": getattr(settings, "AWS_SECRET_ACCESS_KEY", ""),
                    "region": getattr(settings, "AWS_REGION", "us-east-1"),
                }

        # SMS providers
        elif type_key == "sms":
            if provider_name == "twilio":
                return {
                    "account_sid": getattr(settings, "TWILIO_ACCOUNT_SID", ""),
                    "auth_token": getattr(settings, "TWILIO_AUTH_TOKEN", ""),
                    "phone_number": getattr(settings, "TWILIO_PHONE_NUMBER", ""),
                }
            elif provider_name == "messagebird":
                return {
                    "api_key": getattr(settings, "MESSAGEBIRD_API_KEY", ""),
                    "originator": getattr(settings, "MESSAGEBIRD_ORIGINATOR", ""),
                }
            elif provider_name == "vonage":
                return {
                    "api_key": getattr(settings, "VONAGE_API_KEY", ""),
                    "api_secret": getattr(settings, "VONAGE_API_SECRET", ""),
                    "from_number": getattr(settings, "VONAGE_FROM_NUMBER", ""),
                }
            elif provider_name == "plivo":
                return {
                    "auth_id": getattr(settings, "PLIVO_AUTH_ID", ""),
                    "auth_token": getattr(settings, "PLIVO_AUTH_TOKEN", ""),
                    "from_number": getattr(settings, "PLIVO_FROM_NUMBER", ""),
                }
            elif provider_name == "sinch":
                return {
                    "service_plan_id": getattr(settings, "SINCH_SERVICE_PLAN_ID", ""),
                    "api_token": getattr(settings, "SINCH_API_TOKEN", ""),
                    "from_number": getattr(settings, "SINCH_FROM_NUMBER", ""),
                }

        # Voice providers
        elif type_key == "voice":
            if provider_name == "twilio":
                return {
                    "account_sid": getattr(settings, "TWILIO_ACCOUNT_SID", ""),
                    "auth_token": getattr(settings, "TWILIO_AUTH_TOKEN", ""),
                    "phone_number": getattr(settings, "TWILIO_PHONE_NUMBER", ""),
                }
            elif provider_name == "vonage":
                return {
                    "api_key": getattr(settings, "VONAGE_API_KEY", ""),
                    "api_secret": getattr(settings, "VONAGE_API_SECRET", ""),
                    "application_id": getattr(settings, "VONAGE_APPLICATION_ID", ""),
                }

        # Chat providers
        elif type_key == "chat":
            if provider_name == "slack":
                return {
                    "bot_token": getattr(settings, "SLACK_BOT_TOKEN", ""),
                }
            elif provider_name == "discord":
                return {
                    "bot_token": getattr(settings, "DISCORD_BOT_TOKEN", ""),
                }
            elif provider_name == "teams":
                return {
                    "webhook_url": getattr(settings, "TEAMS_WEBHOOK_URL", ""),
                    "tenant_id": getattr(settings, "TEAMS_TENANT_ID", ""),
                    "client_id": getattr(settings, "TEAMS_CLIENT_ID", ""),
                    "client_secret": getattr(settings, "TEAMS_CLIENT_SECRET", ""),
                }

        return {}


class UniversalEmailService:
    """Universal email service that works with any email provider.

    This is a high-level service that abstracts away the specific
    email provider implementation. Use this in application code.
    """

    def __init__(self, provider: EmailProvider):
        """Initialize with an email provider.

        Args:
            provider: An EmailProvider instance.
        """
        self.provider = provider

    def send(
        self,
        to: str,
        subject: str,
        html_content: str,
        text_content: str = None,
        from_email: str = None,
        from_name: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send an email.

        Args:
            to: Recipient email address.
            subject: Email subject.
            html_content: HTML body.
            text_content: Plain text body (optional).
            from_email: Sender email (optional).
            from_name: Sender name (optional).
            **kwargs: Additional options (cc, bcc, attachments, etc.)

        Returns:
            Dict with result status.
        """
        message = EmailMessage(
            to=to,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            from_email=from_email,
            from_name=from_name,
            cc=kwargs.get("cc", []),
            bcc=kwargs.get("bcc", []),
            attachments=kwargs.get("attachments", []),
            headers=kwargs.get("headers", {}),
            tags=kwargs.get("tags", []),
        )

        result = self.provider.send_email(message)
        return result.to_dict()

    def send_template(
        self,
        template_id: str,
        to: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send an email using a provider template.

        Args:
            template_id: Provider's template ID.
            to: Recipient email address.
            variables: Template variables.

        Returns:
            Dict with result status.
        """
        result = self.provider.send_template_email(template_id, to, variables)
        return result.to_dict()

    def test_connection(self) -> Dict[str, Any]:
        """Test the provider connection.

        Returns:
            Dict with test result.
        """
        result = self.provider.test_connection()
        return result.to_dict()


class UniversalSMSService:
    """Universal SMS service that works with any SMS provider.

    This is a high-level service that abstracts away the specific
    SMS provider implementation. Use this in application code.
    """

    def __init__(self, provider: SMSProvider):
        """Initialize with an SMS provider.

        Args:
            provider: An SMSProvider instance.
        """
        self.provider = provider

    def send(
        self,
        to: str,
        body: str,
        from_number: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send an SMS.

        Args:
            to: Recipient phone number (E.164 format).
            body: SMS message body.
            from_number: Sender phone number (optional).
            **kwargs: Additional options (media_urls, scheduled_at, etc.)

        Returns:
            Dict with result status.
        """
        message = SMSMessage(
            to=to,
            body=body,
            from_number=from_number,
            media_urls=kwargs.get("media_urls", []),
            scheduled_at=kwargs.get("scheduled_at"),
            status_callback=kwargs.get("status_callback"),
        )

        result = self.provider.send_sms(message)
        return result.to_dict()

    def get_status(self, message_id: str) -> Dict[str, Any]:
        """Get delivery status of a message.

        Args:
            message_id: Provider's message ID.

        Returns:
            Dict with status information.
        """
        return self.provider.get_message_status(message_id)

    def test_connection(self) -> Dict[str, Any]:
        """Test the provider connection.

        Returns:
            Dict with test result.
        """
        result = self.provider.test_connection()
        return result.to_dict()


class UniversalVoiceService:
    """Universal voice service that works with any voice provider."""

    def __init__(self, provider: VoiceProvider):
        self.provider = provider

    def make_call(
        self,
        to: str,
        from_number: str,
        url: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make an outbound call.

        Args:
            to: Destination phone number.
            from_number: Caller ID phone number.
            url: URL for call instructions (TwiML, etc.)
            **kwargs: Additional options.

        Returns:
            Dict with result status.
        """
        call = VoiceCall(
            to=to,
            from_number=from_number,
            url=url,
            status_callback=kwargs.get("status_callback"),
            timeout=kwargs.get("timeout", 30),
            record=kwargs.get("record", False),
        )

        result = self.provider.make_call(call)
        return result.to_dict()

    def get_status(self, call_id: str) -> Dict[str, Any]:
        """Get call status.

        Args:
            call_id: Provider's call ID.

        Returns:
            Dict with call status.
        """
        return self.provider.get_call_status(call_id)

    def hangup(self, call_id: str) -> Dict[str, Any]:
        """Hang up a call.

        Args:
            call_id: Provider's call ID.

        Returns:
            Dict with result status.
        """
        result = self.provider.hangup_call(call_id)
        return result.to_dict()


class UniversalChatService:
    """Universal chat service that works with any chat provider."""

    def __init__(self, provider: ChatProvider):
        self.provider = provider

    def send_message(
        self,
        channel_id: str,
        text: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a chat message.

        Args:
            channel_id: Channel/room ID.
            text: Message text.
            **kwargs: Additional options (blocks, attachments, etc.)

        Returns:
            Dict with result status.
        """
        message = ChatMessage(
            channel=self.provider.provider_name,
            channel_id=channel_id,
            text=text,
            blocks=kwargs.get("blocks"),
            attachments=kwargs.get("attachments"),
            thread_ts=kwargs.get("thread_ts"),
        )

        result = self.provider.send_message(message)
        return result.to_dict()

    def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get channel information.

        Args:
            channel_id: Channel ID.

        Returns:
            Dict with channel info.
        """
        return self.provider.get_channel_info(channel_id)
