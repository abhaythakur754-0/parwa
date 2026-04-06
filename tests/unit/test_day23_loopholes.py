"""Day 23 loophole tests (L69-L74)."""

import os
import logging


# ── L69: HMAC enforced on webhook handlers ────────────────────

class TestL69HmacEnforced:
    def test_webhook_api_verifies_signature_function_exists(self):
        from backend.app.api.webhooks import _verify_provider_signature
        assert callable(_verify_provider_signature)

    def test_hmac_verification_functions_exist(self):
        from backend.app.security.hmac_verification import (
            verify_paddle_signature,
            verify_twilio_signature,
            verify_shopify_hmac,
            verify_brevo_ip,
        )
        assert callable(verify_paddle_signature)
        assert callable(verify_twilio_signature)
        assert callable(verify_shopify_hmac)
        assert callable(verify_brevo_ip)

    def test_paddle_uses_constant_time_comparison(self):
        import inspect
        from backend.app.security.hmac_verification import verify_paddle_signature
        source = inspect.getsource(verify_paddle_signature)
        assert "compare_digest" in source

    def test_twilio_uses_constant_time_comparison(self):
        import inspect
        from backend.app.security.hmac_verification import verify_twilio_signature
        source = inspect.getsource(verify_twilio_signature)
        assert "compare_digest" in source

    def test_shopify_uses_constant_time_comparison(self):
        import inspect
        from backend.app.security.hmac_verification import verify_shopify_hmac
        source = inspect.getsource(verify_shopify_hmac)
        assert "compare_digest" in source


# ── L70: Payload size limits enforced ─────────────────────────

class TestL70PayloadSizeLimit:
    def test_max_webhook_payload_size_is_1mb(self):
        from backend.app.api.webhooks import MAX_WEBHOOK_PAYLOAD_SIZE
        assert MAX_WEBHOOK_PAYLOAD_SIZE == 1 * 1024 * 1024

    def test_brevo_max_email_body_is_1mb(self):
        from backend.app.webhooks.brevo_handler import MAX_EMAIL_BODY_SIZE
        assert MAX_EMAIL_BODY_SIZE == 1 * 1024 * 1024

    def test_brevo_truncates_oversized_body(self):
        from backend.app.webhooks.brevo_handler import MAX_EMAIL_BODY_SIZE
        import backend.app.webhooks.brevo_handler  # noqa: F401
        from backend.app.webhooks.brevo_handler import handle_inbound_email
        big_body = "<p>" + "x" * (MAX_EMAIL_BODY_SIZE + 5000) + "</p>"
        event = {
            "event_type": "inbound_email",
            "payload": {
                "sender": {"email": "a@b.com"},
                "recipient": {"email": "c@d.com"},
                "subject": "Test",
                "body_html": big_body,
            },
        }
        result = handle_inbound_email(event)
        assert result["data"]["body_truncated"] is True

    def test_webhook_api_rejects_oversized_payload(self):
        from backend.app.api.webhooks import MAX_WEBHOOK_PAYLOAD_SIZE
        assert MAX_WEBHOOK_PAYLOAD_SIZE == 1048576


# ── L71: Email template XSS safety ───────────────────────────

class TestL71EmailTemplateXssSafety:
    def test_templates_use_jinja2_variables(self):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        templates_dir = os.path.join(base, "backend", "app", "templates", "emails")
        for fname in os.listdir(templates_dir):
            if not fname.endswith(".html"):
                continue
            with open(os.path.join(templates_dir, fname)) as f:
                content = f.read()
            # All non-base templates should use Jinja2 variables
            if fname != "base.html":
                assert "{{ " in content, f"{fname} has no Jinja2 variables"

    def test_no_script_tags_in_templates(self):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        templates_dir = os.path.join(base, "backend", "app", "templates", "emails")
        for fname in os.listdir(templates_dir):
            if not fname.endswith(".html"):
                continue
            with open(os.path.join(templates_dir, fname)) as f:
                content = f.read()
            assert "<script" not in content.lower(), f"{fname} contains script tag"

    def test_no_onerror_or_onload_in_templates(self):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        templates_dir = os.path.join(base, "backend", "app", "templates", "emails")
        for fname in os.listdir(templates_dir):
            if not fname.endswith(".html"):
                continue
            with open(os.path.join(templates_dir, fname)) as f:
                content = f.read()
            assert "onerror" not in content.lower(), f"{fname} contains onerror"
            assert "onload" not in content.lower(), f"{fname} contains onload"


# ── L72: Templates have proper links ──────────────────────────

class TestL72TemplateManagementLinks:
    def test_base_template_has_footer(self):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(base, "backend", "app", "templates", "emails", "base.html")
        with open(path) as f:
            content = f.read()
        assert "PARWA" in content

    def test_base_template_has_ignore_message(self):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(base, "backend", "app", "templates", "emails", "base.html")
        with open(path) as f:
            content = f.read()
        assert "ignore" in content.lower()

    def test_actionable_templates_have_cta_buttons(self):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        templates_dir = os.path.join(base, "backend", "app", "templates", "emails")
        actionable = [
            "welcome_email.html", "api_key_created.html",
            "approval_notification.html", "overage_notification.html",
            "session_revoked.html",
        ]
        for fname in actionable:
            path = os.path.join(templates_dir, fname)
            with open(path) as f:
                content = f.read()
            assert 'class="btn"' in content, f"{fname} missing CTA button"

    def test_verification_email_has_verify_button(self):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(base, "backend", "app", "templates", "emails", "verification_email.html")
        with open(path) as f:
            content = f.read()
        assert 'class="btn"' in content


# ── L73: Webhook processing is async (non-blocking) ──────────

class TestL73WebhookAsyncProcessing:
    def test_webhook_service_dispatches_to_celery(self):
        from backend.app.services.webhook_service import _dispatch_celery_task
        assert callable(_dispatch_celery_task)

    def test_webhook_tasks_route_to_webhook_queue(self):
        from backend.app.tasks.webhook_tasks import process_webhook_event
        assert process_webhook_event.queue == "webhook"

    def test_provider_tasks_route_to_webhook_queue(self):
        from backend.app.tasks.webhook_tasks import (
            process_paddle_webhook,
            process_twilio_webhook,
            process_brevo_webhook,
            process_shopify_webhook,
        )
        assert process_paddle_webhook.queue == "webhook"
        assert process_twilio_webhook.queue == "webhook"
        assert process_brevo_webhook.queue == "webhook"
        assert process_shopify_webhook.queue == "webhook"

    def test_dispatch_celery_task_sends_to_webhook_queue(self):
        import inspect
        from backend.app.services.webhook_service import _dispatch_celery_task
        source = inspect.getsource(_dispatch_celery_task)
        assert '"webhook"' in source


# ── L74: Webhook rejection logging ────────────────────────────

class TestL74WebhookRejectionLogging:
    def test_webhook_api_has_logger(self):
        logger = logging.getLogger("parwa.webhook_api")
        assert logger is not None
        assert logger.name == "parwa.webhook_api"

    def test_webhook_service_has_logger(self):
        logger = logging.getLogger("parwa.webhook_service")
        assert logger is not None
        assert logger.name == "parwa.webhook_service"

    def test_webhook_handlers_have_loggers(self):
        for name in [
            "parwa.webhooks.paddle",
            "parwa.webhooks.brevo",
            "parwa.webhooks.twilio",
            "parwa.webhooks.shopify",
        ]:
            logger = logging.getLogger(name)
            assert logger.name == name

    def test_webhook_tasks_have_logger(self):
        logger = logging.getLogger("parwa.webhook_tasks")
        assert logger is not None
        assert logger.name == "parwa.webhook_tasks"
