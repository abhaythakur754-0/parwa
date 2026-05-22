"""
Real Twilio Integration Tests — only runs when TWILIO_ACCOUNT_SID is set.

Tests actual SMS sending, call initiation, and status checking with Twilio.
These tests use REAL API calls and will consume Twilio credits.
"""

import os
import time
import pytest

TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE = os.environ.get("TWILIO_PHONE_NUMBER", "")
TEST_PHONE = "+919652852014"  # Verified test number

pytestmark = pytest.mark.skipif(
    not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_PHONE]),
    reason="Twilio credentials not configured — set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER"
)


@pytest.fixture
def twilio_client():
    from twilio.rest import Client
    return Client(TWILIO_SID, TWILIO_TOKEN)


class TestRealTwilioSMS:
    """Test real SMS sending via Twilio."""

    def test_send_sms_real(self, twilio_client):
        """Should send an SMS and return a valid MessageSid."""
        msg = twilio_client.messages.create(
            body="PARWA Integration Test: SMS channel verified!",
            from_=TWILIO_PHONE,
            to=TEST_PHONE,
        )
        assert msg.sid.startswith("SM")
        assert msg.status in ("queued", "sent", "delivered")
        assert msg.to == TEST_PHONE
        assert msg.from_ == TWILIO_PHONE

    def test_sms_delivery_status(self, twilio_client):
        """Should check SMS delivery status."""
        msg = twilio_client.messages.create(
            body="PARWA Test: Checking delivery status",
            from_=TWILIO_PHONE,
            to=TEST_PHONE,
        )
        time.sleep(2)
        fetched = twilio_client.messages(msg.sid).fetch()
        assert fetched.status in ("queued", "sent", "delivered", "undelivered")


class TestRealTwilioVoice:
    """Test real voice calls via Twilio."""

    def test_make_call_real(self, twilio_client):
        """Should initiate an outbound call and return a valid CallSid."""
        call = twilio_client.calls.create(
            twiml='<Response><Say voice="Polly.Aditi" language="en-IN">Hello! This is a PARWA integration test call. The voice channel is working correctly. Goodbye!</Say></Response>',
            from_=TWILIO_PHONE,
            to=TEST_PHONE,
        )
        assert call.sid.startswith("CA")
        assert call.status in ("queued", "ringing", "in-progress")

    def test_call_with_gather(self, twilio_client):
        """Should initiate a call with speech recognition (Gather)."""
        twiml = '''<Response>
            <Gather input="speech dtmf" speechTimeout="auto" language="en-IN">
                <Say voice="Polly.Aditi" language="en-IN">Hello from PARWA! This is a test of our speech recognition system. Please say something or press any key.</Say>
            </Gather>
            <Say voice="Polly.Aditi" language="en-IN">Thank you for testing. Goodbye!</Say>
        </Response>'''
        call = twilio_client.calls.create(
            twiml=twiml,
            from_=TWILIO_PHONE,
            to=TEST_PHONE,
        )
        assert call.sid.startswith("CA")

    def test_check_call_status(self, twilio_client):
        """Should fetch call status after initiation."""
        call = twilio_client.calls.create(
            twiml='<Response><Say voice="Polly.Aditi">Status check test.</Say></Response>',
            from_=TWILIO_PHONE,
            to=TEST_PHONE,
        )
        time.sleep(3)
        fetched = twilio_client.calls(call.sid).fetch()
        assert fetched.status in ("queued", "ringing", "in-progress", "completed")

    def test_list_recent_calls(self, twilio_client):
        """Should list recent calls from the account."""
        calls = twilio_client.calls.list(limit=5)
        assert isinstance(calls, list)
        if calls:
            assert calls[0].sid.startswith("CA")

    def test_account_phone_numbers(self, twilio_client):
        """Should list phone numbers on the Twilio account."""
        numbers = twilio_client.incoming_phone_numbers.list()
        assert len(numbers) >= 1
        found = any(n.phone_number == TWILIO_PHONE for n in numbers)
        assert found, f"Expected phone number {TWILIO_PHONE} not found in account"


class TestRealTwilioVerifiedNumbers:
    """Test verified (caller ID) numbers on the account."""

    def test_verified_caller_ids(self, twilio_client):
        """Should list verified caller IDs (needed for trial accounts)."""
        caller_ids = twilio_client.outgoing_caller_ids.list()
        assert len(caller_ids) >= 1
        # Our test phone should be verified
        numbers = [c.phone_number for c in caller_ids]
        assert TEST_PHONE in numbers, f"Test phone {TEST_PHONE} not in verified numbers: {numbers}"
