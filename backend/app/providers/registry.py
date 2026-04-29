"""
PARWA Provider Registry

Registry of all available providers. Each provider registers itself here.
The factory uses this registry to instantiate providers by name.

To add a new provider:
1. Create a provider class extending the appropriate base class
2. Add the provider to the registry below
3. The factory will automatically make it available
"""

from typing import Any, Dict, List, Type

from app.providers.base import (
    BaseProvider,
    ProviderType,
)
from app.providers.chat.discord import DiscordChatProvider
from app.providers.chat.slack import SlackChatProvider
from app.providers.chat.teams import TeamsChatProvider
from app.providers.email.brevo import BrevoEmailProvider
from app.providers.email.mailgun import MailgunEmailProvider
from app.providers.email.postmark import PostmarkEmailProvider
from app.providers.email.sendgrid import SendGridEmailProvider
from app.providers.email.ses import SESEmailProvider
from app.providers.email.smtp import SMTPEmailProvider
from app.providers.sms.messagebird import MessageBirdSMSProvider
from app.providers.sms.plivo import PlivoSMSProvider
from app.providers.sms.sinch import SinchSMSProvider
from app.providers.sms.twilio import TwilioSMSProvider
from app.providers.sms.vonage import VonageSMSProvider
from app.providers.voice.twilio_voice import TwilioVoiceProvider
from app.providers.voice.vonage_voice import VonageVoiceProvider


class ProviderRegistry:
    """Registry of all available providers.

    This is a centralized registry that maps provider names to their
    implementation classes. New providers are added here.
    """

    # Provider class registry: {provider_type: {provider_name: provider_class}}
    _providers: Dict[str, Dict[str, Type[BaseProvider]]] = {
        ProviderType.EMAIL.value: {},
        ProviderType.SMS.value: {},
        ProviderType.VOICE.value: {},
        ProviderType.CHAT.value: {},
        ProviderType.HELPDESK.value: {},
        ProviderType.CRM.value: {},
        ProviderType.ECOMMERCE.value: {},
        ProviderType.PAYMENT.value: {},
        ProviderType.STORAGE.value: {},
        ProviderType.AI.value: {},
    }

    # Provider metadata: {provider_type: {provider_name: metadata}}
    _metadata: Dict[str, Dict[str, Dict[str, Any]]] = {
        ProviderType.EMAIL.value: {},
        ProviderType.SMS.value: {},
        ProviderType.VOICE.value: {},
        ProviderType.CHAT.value: {},
        ProviderType.HELPDESK.value: {},
        ProviderType.CRM.value: {},
        ProviderType.ECOMMERCE.value: {},
        ProviderType.PAYMENT.value: {},
        ProviderType.STORAGE.value: {},
        ProviderType.AI.value: {},
    }

    @classmethod
    def register(
        cls,
        provider_type: ProviderType,
        provider_name: str,
        provider_class: Type[BaseProvider],
        metadata: Dict[str, Any] = None,
    ) -> None:
        """Register a provider class.

        Args:
            provider_type: Type of provider (email, sms, etc.)
            provider_name: Unique name for the provider (e.g., "brevo")
            provider_class: The provider implementation class
            metadata: Optional metadata (display_name, description, etc.)
        """
        type_key = (
            provider_type.value
            if isinstance(provider_type, ProviderType)
            else provider_type
        )

        if type_key not in cls._providers:
            cls._providers[type_key] = {}
            cls._metadata[type_key] = {}

        cls._providers[type_key][provider_name.lower()] = provider_class

        # Default metadata from class attributes
        default_meta = {
            "display_name": getattr(provider_class, "display_name", provider_name),
            "description": getattr(provider_class, "description", ""),
            "website": getattr(provider_class, "website", ""),
            "capabilities": [
                c.value for c in getattr(provider_class, "capabilities", [])
            ],
            "required_config_fields": getattr(
                provider_class, "required_config_fields", []
            ),
        }

        # Override with provided metadata
        if metadata:
            default_meta.update(metadata)

        cls._metadata[type_key][provider_name.lower()] = default_meta

    @classmethod
    def get_provider_class(
        cls,
        provider_type: ProviderType,
        provider_name: str,
    ) -> Type[BaseProvider]:
        """Get a provider class by type and name.

        Args:
            provider_type: Type of provider.
            provider_name: Name of the provider.

        Returns:
            The provider class.

        Raises:
            ValueError: If provider not found.
        """
        type_key = (
            provider_type.value
            if isinstance(provider_type, ProviderType)
            else provider_type
        )

        if type_key not in cls._providers:
            raise ValueError(f"Unknown provider type: {provider_type}")

        name_lower = provider_name.lower()
        if name_lower not in cls._providers[type_key]:
            available = list(cls._providers[type_key].keys())
            raise ValueError(
                f"Unknown provider '{provider_name}' for type '{provider_type}'. "
                f"Available: {', '.join(available)}"
            )

        return cls._providers[type_key][name_lower]

    @classmethod
    def get_metadata(
        cls,
        provider_type: ProviderType,
        provider_name: str,
    ) -> Dict[str, Any]:
        """Get metadata for a provider.

        Args:
            provider_type: Type of provider.
            provider_name: Name of the provider.

        Returns:
            Dict with provider metadata.
        """
        type_key = (
            provider_type.value
            if isinstance(provider_type, ProviderType)
            else provider_type
        )
        name_lower = provider_name.lower()

        return cls._metadata.get(type_key, {}).get(name_lower, {})

    @classmethod
    def list_providers(
        cls,
        provider_type: ProviderType = None,
    ) -> List[Dict[str, Any]]:
        """List all registered providers.

        Args:
            provider_type: Optional filter by type.

        Returns:
            List of provider info dicts.
        """
        result = []

        if provider_type:
            type_key = (
                provider_type.value
                if isinstance(provider_type, ProviderType)
                else provider_type
            )
            types_to_check = [type_key]
        else:
            types_to_check = list(cls._providers.keys())

        for type_key in types_to_check:
            for name, meta in cls._metadata.get(type_key, {}).items():
                result.append(
                    {
                        "type": type_key,
                        "name": name,
                        **meta,
                    }
                )

        return result

    @classmethod
    def list_providers_by_type(
        cls,
        provider_type: ProviderType,
    ) -> List[Dict[str, Any]]:
        """List providers of a specific type.

        Args:
            provider_type: Type of provider to list.

        Returns:
            List of provider info dicts.
        """
        return cls.list_providers(provider_type)


# ============================================================
# EMAIL PROVIDERS REGISTRATION
# ============================================================

# Import email providers

# Register email providers
ProviderRegistry.register(
    ProviderType.EMAIL,
    "brevo",
    BrevoEmailProvider,
    metadata={
        "display_name": "Brevo (Sendinblue)",
        "description": "Transactional and marketing email service",
        "website": "https://www.brevo.com",
    },
)

ProviderRegistry.register(
    ProviderType.EMAIL,
    "sendgrid",
    SendGridEmailProvider,
    metadata={
        "display_name": "SendGrid",
        "description": "Email delivery and marketing platform",
        "website": "https://sendgrid.com",
    },
)

ProviderRegistry.register(
    ProviderType.EMAIL,
    "mailgun",
    MailgunEmailProvider,
    metadata={
        "display_name": "Mailgun",
        "description": "Email API service for developers",
        "website": "https://www.mailgun.com",
    },
)

ProviderRegistry.register(
    ProviderType.EMAIL,
    "ses",
    SESEmailProvider,
    metadata={
        "display_name": "AWS SES",
        "description": "Amazon Simple Email Service",
        "website": "https://aws.amazon.com/ses/",
    },
)

ProviderRegistry.register(
    ProviderType.EMAIL,
    "postmark",
    PostmarkEmailProvider,
    metadata={
        "display_name": "Postmark",
        "description": "Fast and reliable email delivery",
        "website": "https://postmarkapp.com",
    },
)

ProviderRegistry.register(
    ProviderType.EMAIL,
    "smtp",
    SMTPEmailProvider,
    metadata={
        "display_name": "Custom SMTP",
        "description": "Any SMTP server",
        "website": "",
    },
)


# ============================================================
# SMS PROVIDERS REGISTRATION
# ============================================================

# Import SMS providers

# Register SMS providers
ProviderRegistry.register(
    ProviderType.SMS,
    "twilio",
    TwilioSMSProvider,
    metadata={
        "display_name": "Twilio",
        "description": "Cloud communications platform for SMS and Voice",
        "website": "https://www.twilio.com",
    },
)

ProviderRegistry.register(
    ProviderType.SMS,
    "messagebird",
    MessageBirdSMSProvider,
    metadata={
        "display_name": "MessageBird",
        "description": "Cloud communications API platform",
        "website": "https://messagebird.com",
    },
)

ProviderRegistry.register(
    ProviderType.SMS,
    "vonage",
    VonageSMSProvider,
    metadata={
        "display_name": "Vonage (Nexmo)",
        "description": "Cloud communications and messaging API",
        "website": "https://www.vonage.com",
    },
)

ProviderRegistry.register(
    ProviderType.SMS,
    "plivo",
    PlivoSMSProvider,
    metadata={
        "display_name": "Plivo",
        "description": "Cloud communication platform",
        "website": "https://www.plivo.com",
    },
)

ProviderRegistry.register(
    ProviderType.SMS,
    "sinch",
    SinchSMSProvider,
    metadata={
        "display_name": "Sinch",
        "description": "Cloud communications for messaging and voice",
        "website": "https://www.sinch.com",
    },
)


# ============================================================
# VOICE PROVIDERS REGISTRATION
# ============================================================


ProviderRegistry.register(
    ProviderType.VOICE,
    "twilio",
    TwilioVoiceProvider,
    metadata={
        "display_name": "Twilio Voice",
        "description": "Programmable voice API",
        "website": "https://www.twilio.com/voice",
    },
)

ProviderRegistry.register(
    ProviderType.VOICE,
    "vonage",
    VonageVoiceProvider,
    metadata={
        "display_name": "Vonage Voice",
        "description": "Voice API for calls and more",
        "website": "https://www.vonage.com/voice/",
    },
)


# ============================================================
# CHAT PROVIDERS REGISTRATION
# ============================================================


ProviderRegistry.register(
    ProviderType.CHAT,
    "slack",
    SlackChatProvider,
    metadata={
        "display_name": "Slack",
        "description": "Business communication platform",
        "website": "https://slack.com",
    },
)

ProviderRegistry.register(
    ProviderType.CHAT,
    "discord",
    DiscordChatProvider,
    metadata={
        "display_name": "Discord",
        "description": "Chat and community platform",
        "website": "https://discord.com",
    },
)

ProviderRegistry.register(
    ProviderType.CHAT,
    "teams",
    TeamsChatProvider,
    metadata={
        "display_name": "Microsoft Teams",
        "description": "Microsoft collaboration platform",
        "website": "https://teams.microsoft.com",
    },
)
