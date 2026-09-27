"""Voice provider adapter layer — bring-your-own calling platform.

Parwa NEVER provisions phone numbers and NEVER pays for telecom.
Every tenant connects their OWN calling platform account (pays that
platform directly) and Parwa talks to it through one of these adapters.

Adding a new provider (e.g. Exotel, Vonage):
  1. Create ``exotel_voice_provider.py`` implementing VoiceProviderBase
  2. Register it in ``get_voice_provider`` (base_voice_provider.py)
  3. Add the name to ``_VOICE_PROVIDERS`` in database/models/voice_channel.py

Each adapter is responsible for:
  - parsing the provider's webhook payload into a VoiceWebhookEvent
  - verifying the provider's request signature (HMAC etc.)
  - building the provider's call-script format (TwiML for Twilio)
  - placing outbound calls with the TENANT's credentials
"""
