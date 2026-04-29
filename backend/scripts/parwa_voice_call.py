#!/usr/bin/env python3
"""
PARWA Voice Call Service - Hindi
================================

Makes a voice call using Twilio with Hindi TTS to showcase PARWA features.
"""

import os
import sys
from datetime import datetime

# Add path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Twilio credentials from environment (SECURE - not hardcoded)
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")

# Hindi Voice Message for PARWA Demo
HINDI_VOICE_MESSAGE = """
नमस्ते! TechCorp Solutions में आपका स्वागत है।

मैं PARWA AI सपोर्ट सिस्टम से आपको कॉल कर रहा हूँ। मैं आपको PARWA की सभी विशेषताओं के बारे में बताना चाहता हूँ:

पहली बात, Mini PARWA: यह Email और Chat सपोर्ट प्रदान करता है। हर महीने 2000 टिकट तक की सीमा है। यह सिर्फ Tier 1 AI तकनीकों का उपयोग करता है।

दूसरी बात, Full PARWA: यह Email, Chat, SMS और Voice सपोर्ट प्रदान करता है। हर महीने 5000 टिकट तक की सीमा है। इसमें Tier 1 और Tier 2 दोनों AI तकनीकें शामिल हैं।

तीसरी बात, PARWA में Advanced AI तकनीकें हैं जैसे:
- Multi-turn Reasoning
- Step-back Analysis
- Tree of Thoughts
- Advanced Sentiment Analysis

आपका ऑर्डर सफलतापूर्वक रजिस्टर हो गया है।

अगर आपके कोई सवाल हो तो 24/7 हमसे संपर्क करें।

धन्यवाद! आपका दिन शुभ हो!
"""


def create_twiml_for_hindi(message: str) -> str:
    """Create TwiML for Hindi voice message"""

    # Split message into smaller chunks for better TTS
    sentences = message.replace("\n", " ").split(". ")

    # Build TwiML with Say tags
    say_tags = []
    for sentence in sentences:
        if sentence.strip():
            say_tags.append(
                f'        <Say language="hi-IN" voice="Polly.Aditi">{sentence.strip()}.</Say>'
            )

    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="1"/>
{chr(10).join(say_tags)}
    <Pause length="1"/>
</Response>"""

    return twiml


def make_voice_call_twiml(to_number: str, twiml: str) -> dict:
    """
    Make a voice call using TwiML.

    Args:
        to_number: Phone number to call (with country code)
        twiml: TwiML content for the call

    Returns:
        dict with call details
    """
    result = {
        "success": False,
        "call_sid": None,
        "to_number": to_number,
        "from_number": TWILIO_PHONE_NUMBER,
        "error": None,
    }

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        result["error"] = "Twilio credentials not set"
        result["note"] = (
            "Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables"
        )
        return result

    if not TWILIO_PHONE_NUMBER:
        result["error"] = "Twilio phone number not set"
        result["note"] = "Set TWILIO_PHONE_NUMBER environment variable"
        return result

    try:
        # Import Twilio client
        from twilio.rest import Client

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        # Make the call
        call = client.calls.create(
            to=to_number, from_=TWILIO_PHONE_NUMBER, twiml=twiml, timeout=30
        )

        result["success"] = True
        result["call_sid"] = call.sid
        result["status"] = call.status
        result["message"] = "Voice call initiated successfully"

    except ImportError:
        result["error"] = "Twilio library not installed"
        result["note"] = "Install with: pip install twilio"
    except Exception as e:
        result["error"] = str(e)

    return result


def make_voice_call_tts(to_number: str, audio_url: str) -> dict:
    """
    Make a voice call using a pre-recorded audio URL.

    Args:
        to_number: Phone number to call
        audio_url: URL to the audio file to play

    Returns:
        dict with call details
    """
    result = {
        "success": False,
        "call_sid": None,
        "to_number": to_number,
        "from_number": TWILIO_PHONE_NUMBER,
        "error": None,
    }

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        result["error"] = "Twilio credentials not set"
        return result

    try:
        from twilio.rest import Client

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        # TwiML to play audio
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
</Response>"""

        call = client.calls.create(to=to_number, from_=TWILIO_PHONE_NUMBER, twiml=twiml)

        result["success"] = True
        result["call_sid"] = call.sid
        result["status"] = call.status

    except Exception as e:
        result["error"] = str(e)

    return result


def send_sms_notification(to_number: str, message: str) -> dict:
    """Send SMS notification"""
    result = {"success": False, "message_sid": None, "error": None}

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        result["error"] = "Twilio credentials not set"
        return result

    try:
        from twilio.rest import Client

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        msg = client.messages.create(
            to=to_number, from_=TWILIO_PHONE_NUMBER, body=message
        )

        result["success"] = True
        result["message_sid"] = msg.sid
        result["status"] = msg.status

    except Exception as e:
        result["error"] = str(e)

    return result


def test_twilio_connection() -> dict:
    """Test Twilio API connection"""
    result = {
        "success": False,
        "account_sid": (
            TWILIO_ACCOUNT_SID[:10] + "..." if TWILIO_ACCOUNT_SID else "Not set"
        ),
        "phone_number": TWILIO_PHONE_NUMBER,
        "error": None,
    }

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        result["error"] = "Credentials not set"
        return result

    try:
        from twilio.rest import Client

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        # Get account info
        account = client.api.accounts(TWILIO_ACCOUNT_SID).fetch()

        result["success"] = True
        result["account_name"] = account.friendly_name
        result["account_status"] = account.status
        result["account_type"] = account.type

    except Exception as e:
        result["error"] = str(e)

    return result


def demo_parwa_voice_call(phone_number: str):
    """Demo PARWA voice call in Hindi"""

    print("\n" + "=" * 70)
    print("PARWA VOICE CALL DEMO - HINDI")
    print("=" * 70)

    print(f"\n📞 Target Phone: {phone_number}")
    print(f"📅 Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Test connection first
    print("\n--- Testing Twilio Connection ---")
    conn_test = test_twilio_connection()

    if conn_test["success"]:
        print("✅ Connected to Twilio")
        print(f"   Account: {conn_test.get('account_name', 'N/A')}")
        print(f"   Status: {conn_test.get('account_status', 'N/A')}")
        print(f"   Phone: {conn_test.get('phone_number', 'N/A')}")
    else:
        print(f"❌ Connection failed: {conn_test['error']}")
        return

    # Create TwiML for Hindi message
    print("\n--- Creating Hindi Voice Message ---")
    twiml = create_twiml_for_hindi(HINDI_VOICE_MESSAGE)
    print(f"✅ TwiML created ({len(twiml)} bytes)")

    # Make the call
    print("\n--- Initiating Voice Call ---")
    call_result = make_voice_call_twiml(phone_number, twiml)

    if call_result["success"]:
        print("✅ Voice call initiated!")
        print(f"   Call SID: {call_result['call_sid']}")
        print(f"   Status: {call_result.get('status', 'unknown')}")
        print(f"   To: {call_result['to_number']}")
        print(f"   From: {call_result['from_number']}")
    else:
        print(f"❌ Call failed: {call_result['error']}")
        if call_result.get("note"):
            print(f"   Note: {call_result['note']}")

    # Also send SMS confirmation
    print("\n--- Sending SMS Confirmation ---")
    sms_message = "PARWA Demo: आपका voice call सफलतापूर्वक पूरा हुआ। Thank you for testing PARWA AI Support System! - TechCorp Solutions"

    sms_result = send_sms_notification(phone_number, sms_message)

    if sms_result["success"]:
        print("✅ SMS sent successfully")
        print(f"   Message SID: {sms_result['message_sid']}")
    else:
        print(f"❌ SMS failed: {sms_result['error']}")

    print("\n" + "=" * 70)
    print("VOICE CALL DEMO COMPLETE")
    print("=" * 70)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="PARWA Voice Call Service - Hindi")
    parser.add_argument(
        "--phone", "-p", required=False, help="Phone number to call (with country code)"
    )
    parser.add_argument(
        "--test", "-t", action="store_true", help="Test Twilio connection only"
    )
    parser.add_argument(
        "--demo", "-d", action="store_true", help="Run demo with sample number"
    )

    args = parser.parse_args()

    if args.test:
        print("\n--- Testing Twilio Connection ---")
        result = test_twilio_connection()

        if result["success"]:
            print("✅ Connection successful")
            print(f"   Account SID: {result['account_sid']}")
            print(f"   Account Name: {result.get('account_name', 'N/A')}")
            print(f"   Phone Number: {result.get('phone_number', 'N/A')}")
        else:
            print(f"❌ Connection failed: {result['error']}")

        return

    if args.demo:
        # Demo mode - just show what would happen
        print("\n" + "=" * 70)
        print("PARWA VOICE CALL DEMO MODE")
        print("=" * 70)

        print("\nHindi Voice Message:")
        print("-" * 50)
        print(HINDI_VOICE_MESSAGE)
        print("-" * 50)

        print("\nTwiML Generated:")
        print("-" * 50)
        print(create_twiml_for_hindi(HINDI_VOICE_MESSAGE))
        print("-" * 50)

        # Test connection
        conn = test_twilio_connection()
        print(f"\nTwilio Connection: {
                '✅ OK' if conn['success'] else '❌ '
                + conn['error']}")

        return

    if args.phone:
        demo_parwa_voice_call(args.phone)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
