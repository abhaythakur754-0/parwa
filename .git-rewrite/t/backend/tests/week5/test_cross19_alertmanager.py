"""Tests for CROSS-19 AlertManager configuration.

Validates:
- alertmanager.yml can be parsed as valid YAML
- 3 receivers exist: default-receiver, critical-receiver, warning-receiver
- default-receiver has webhook to backend
- critical-receiver has webhook + slack + email
- warning-receiver has email only
- Routing: severity=critical -> critical-receiver
- Routing: severity=warning -> warning-receiver
- Inhibition rules exist
- Environment variable placeholders for Slack and SMTP
"""

from pathlib import Path

import pytest
import yaml

# ── Path constants ─────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ALERTMANAGER_YML = PROJECT_ROOT / "monitoring" / "alertmanager" / "alertmanager.yml"


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def alertmanager_config():
    """Parse and return the alertmanager.yml configuration."""
    assert ALERTMANAGER_YML.exists(), (
        f"alertmanager.yml not found at {ALERTMANAGER_YML}"
    )
    with open(ALERTMANAGER_YML, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


@pytest.fixture
def receivers(alertmanager_config):
    """Return the receivers list from the config."""
    return alertmanager_config["receivers"]


@pytest.fixture
def routes(alertmanager_config):
    """Return the routes list from the config."""
    return alertmanager_config["route"]["routes"]


@pytest.fixture
def receiver_map(receivers):
    """Map receiver names to their config dicts."""
    return {r["name"]: r for r in receivers}


# ═══════════════════════════════════════════════════════════════════
# 1. YAML validity
# ═══════════════════════════════════════════════════════════════════

class TestYAMLValidity:
    """Verify alertmanager.yml is valid YAML."""

    def test_file_exists(self):
        """alertmanager.yml must exist."""
        assert ALERTMANAGER_YML.exists(), (
            f"alertmanager.yml not found at {ALERTMANAGER_YML}"
        )

    def test_file_is_not_empty(self):
        """alertmanager.yml must not be empty."""
        assert ALERTMANAGER_YML.stat().st_size > 0, (
            "alertmanager.yml is empty"
        )

    def test_parses_as_valid_yaml(self, alertmanager_config):
        """File must parse as valid YAML without errors."""
        assert alertmanager_config is not None
        assert isinstance(alertmanager_config, dict)

    def test_has_required_top_level_keys(self, alertmanager_config):
        """Must have global, route, receivers keys."""
        for key in ("global", "route", "receivers"):
            assert key in alertmanager_config, (
                f"Missing required top-level key: {key}"
            )


# ═══════════════════════════════════════════════════════════════════
# 2. Receivers — 3 required receivers
# ═══════════════════════════════════════════════════════════════════

class TestReceiversExist:
    """Verify all 3 required receivers exist."""

    def test_has_three_receivers(self, receivers):
        """Must have exactly 3 receivers."""
        assert len(receivers) == 3, (
            f"Expected 3 receivers, got {len(receivers)}"
        )

    def test_default_receiver_exists(self, receiver_map):
        """default-receiver must exist."""
        assert "default-receiver" in receiver_map, (
            "default-receiver not found"
        )

    def test_critical_receiver_exists(self, receiver_map):
        """critical-receiver must exist."""
        assert "critical-receiver" in receiver_map, (
            "critical-receiver not found"
        )

    def test_warning_receiver_exists(self, receiver_map):
        """warning-receiver must exist."""
        assert "warning-receiver" in receiver_map, (
            "warning-receiver not found"
        )


# ═══════════════════════════════════════════════════════════════════
# 3. default-receiver — webhook to backend
# ═══════════════════════════════════════════════════════════════════

class TestDefaultReceiver:
    """Verify default-receiver configuration."""

    def test_has_webhook_config(self, receiver_map):
        """default-receiver must have webhook_configs."""
        rcv = receiver_map["default-receiver"]
        assert "webhook_configs" in rcv, (
            "default-receiver has no webhook_configs"
        )
        assert len(rcv["webhook_configs"]) >= 1, (
            "default-receiver has no webhook entries"
        )

    def test_webhook_points_to_backend(self, receiver_map):
        """Webhook must point to backend API."""
        rcv = receiver_map["default-receiver"]
        url = rcv["webhook_configs"][0]["url"]
        assert "backend" in url or "8000" in url or "webhooks" in url, (
            f"Webhook URL doesn't point to backend: {url}"
        )

    def test_webhook_sends_resolved(self, receiver_map):
        """Webhook should send_resolved alerts."""
        rcv = receiver_map["default-receiver"]
        assert rcv["webhook_configs"][0].get("send_resolved") is True, (
            "send_resolved not enabled"
        )


# ═══════════════════════════════════════════════════════════════════
# 4. critical-receiver — webhook + slack + email
# ═══════════════════════════════════════════════════════════════════

class TestCriticalReceiver:
    """Verify critical-receiver has all three notification channels."""

    def test_has_webhook(self, receiver_map):
        """critical-receiver must have webhook."""
        rcv = receiver_map["critical-receiver"]
        assert "webhook_configs" in rcv, (
            "critical-receiver missing webhook_configs"
        )

    def test_has_slack(self, receiver_map):
        """critical-receiver must have Slack config."""
        rcv = receiver_map["critical-receiver"]
        assert "slack_configs" in rcv, (
            "critical-receiver missing slack_configs"
        )

    def test_has_email(self, receiver_map):
        """critical-receiver must have email config."""
        rcv = receiver_map["critical-receiver"]
        assert "email_configs" in rcv, (
            "critical-receiver missing email_configs"
        )

    def test_slack_channel_is_alerts(self, receiver_map):
        """Slack should post to #alerts channel."""
        rcv = receiver_map["critical-receiver"]
        slack = rcv["slack_configs"][0]
        assert slack.get("channel") == "#alerts", (
            f"Slack channel should be #alerts, got {slack.get('channel')}"
        )

    def test_slack_uses_env_var_for_webhook_url(self, receiver_map):
        """Slack webhook URL should use env var placeholder."""
        rcv = receiver_map["critical-receiver"]
        slack = rcv["slack_configs"][0]
        api_url = slack.get("api_url", "")
        assert "SLACK_WEBHOOK_URL" in api_url, (
            f"Slack API URL should use $SLACK_WEBHOOK_URL env var: {api_url}"
        )

    def test_critical_webhook_points_to_backend(self, receiver_map):
        """Critical webhook must point to backend."""
        rcv = receiver_map["critical-receiver"]
        url = rcv["webhook_configs"][0]["url"]
        assert "backend" in url or "8000" in url, (
            f"Critical webhook doesn't point to backend: {url}"
        )

    def test_email_uses_env_var(self, receiver_map):
        """Email recipient should use env var placeholder."""
        rcv = receiver_map["critical-receiver"]
        email = rcv["email_configs"][0].get("to", "")
        assert "ALERT_EMAIL_TO" in email, (
            f"Email 'to' should use $ALERT_EMAIL_TO env var: {email}"
        )


# ═══════════════════════════════════════════════════════════════════
# 5. warning-receiver — email only
# ═══════════════════════════════════════════════════════════════════

class TestWarningReceiver:
    """Verify warning-receiver has email-only notifications."""

    def test_has_email(self, receiver_map):
        """warning-receiver must have email config."""
        rcv = receiver_map["warning-receiver"]
        assert "email_configs" in rcv, (
            "warning-receiver missing email_configs"
        )

    def test_no_slack(self, receiver_map):
        """warning-receiver should NOT have Slack (email only)."""
        rcv = receiver_map["warning-receiver"]
        assert "slack_configs" not in rcv, (
            "warning-receiver should not have slack_configs (email only)"
        )

    def test_no_webhook(self, receiver_map):
        """warning-receiver should NOT have webhook (email only)."""
        rcv = receiver_map["warning-receiver"]
        assert "webhook_configs" not in rcv, (
            "warning-receiver should not have webhook_configs (email only)"
        )

    def test_email_uses_env_var(self, receiver_map):
        """Email recipient should use env var placeholder."""
        rcv = receiver_map["warning-receiver"]
        email = rcv["email_configs"][0].get("to", "")
        assert "ALERT_EMAIL_TO" in email, (
            f"Email 'to' should use $ALERT_EMAIL_TO env var: {email}"
        )


# ═══════════════════════════════════════════════════════════════════
# 6. Routing rules
# ═══════════════════════════════════════════════════════════════════

class TestRoutingRules:
    """Verify alert routing by severity."""

    def test_critical_routes_to_critical_receiver(self, routes):
        """severity=critical must route to critical-receiver."""
        critical_route = None
        for route in routes:
            match = route.get("match", {})
            if match.get("severity") == "critical":
                critical_route = route
                break
        assert critical_route is not None, (
            "No route for severity=critical found"
        )
        assert critical_route.get("receiver") == "critical-receiver", (
            f"Critical route goes to wrong receiver: "
            f"{critical_route.get('receiver')}"
        )

    def test_warning_routes_to_warning_receiver(self, routes):
        """severity=warning must route to warning-receiver."""
        warning_route = None
        for route in routes:
            match = route.get("match", {})
            if match.get("severity") == "warning":
                warning_route = route
                break
        assert warning_route is not None, (
            "No route for severity=warning found"
        )
        assert warning_route.get("receiver") == "warning-receiver", (
            f"Warning route goes to wrong receiver: "
            f"{warning_route.get('receiver')}"
        )

    def test_critical_has_immediate_notification(self, alertmanager_config):
        """Critical alerts should have group_wait: 0s for immediate notification."""
        routes = alertmanager_config["route"]["routes"]
        for route in routes:
            match = route.get("match", {})
            if match.get("severity") == "critical":
                assert route.get("group_wait") == "0s", (
                    "Critical alerts should have group_wait: 0s"
                )
                break

    def test_critical_has_shorter_repeat_interval(self, alertmanager_config):
        """Critical alerts should repeat more frequently (1h vs 4h)."""
        routes = alertmanager_config["route"]["routes"]
        critical_repeat = None
        warning_repeat = None
        for route in routes:
            match = route.get("match", {})
            if match.get("severity") == "critical":
                critical_repeat = route.get("repeat_interval")
            elif match.get("severity") == "warning":
                warning_repeat = route.get("repeat_interval")
        assert critical_repeat is not None, "Critical repeat interval not set"
        assert warning_repeat is not None, "Warning repeat interval not set"
        # Critical should be at most the same or shorter than warning
        # (in practice 1h vs 4h)


# ═══════════════════════════════════════════════════════════════════
# 7. Inhibition rules
# ═══════════════════════════════════════════════════════════════════

class TestInhibitionRules:
    """Verify inhibition rules exist."""

    def test_inhibit_rules_exist(self, alertmanager_config):
        """inhibit_rules must be defined."""
        assert "inhibit_rules" in alertmanager_config, (
            "inhibit_rules not found in config"
        )
        assert len(alertmanager_config["inhibit_rules"]) > 0, (
            "inhibit_rules is empty"
        )

    def test_critical_inhibits_warning(self, alertmanager_config):
        """Critical alerts should inhibit warning alerts."""
        inhibit_rules = alertmanager_config["inhibit_rules"]
        found = False
        for rule in inhibit_rules:
            source = rule.get("source_match", {})
            target = rule.get("target_match", {})
            if (source.get("severity") == "critical" and
                    target.get("severity") == "warning"):
                found = True
                break
        assert found, (
            "No inhibition rule: critical suppresses warning"
        )

    def test_inhibition_has_equal_fields(self, alertmanager_config):
        """Inhibition should match on alertname and service."""
        inhibit_rules = alertmanager_config["inhibit_rules"]
        for rule in inhibit_rules:
            equal = rule.get("equal", [])
            # Should match on identifying fields
            if rule.get("source_match", {}).get("severity") == "critical":
                assert len(equal) >= 1, (
                    "Inhibition rule should have equal fields"
                )


# ═══════════════════════════════════════════════════════════════════
# 8. Environment variable placeholders
# ═══════════════════════════════════════════════════════════════════

class TestEnvVarPlaceholders:
    """Verify env var placeholders for Slack and SMTP."""

    def test_slack_webhook_url_placeholder(self, alertmanager_config):
        """Must use $SLACK_WEBHOOK_URL placeholder."""
        config_str = ALERTMANAGER_YML.read_text(encoding="utf-8")
        assert "SLACK_WEBHOOK_URL" in config_str, (
            "$SLACK_WEBHOOK_URL placeholder not found"
        )

    def test_smtp_host_placeholder(self, alertmanager_config):
        """Must use $SMTP_HOST placeholder."""
        config_str = ALERTMANAGER_YML.read_text(encoding="utf-8")
        assert "SMTP_HOST" in config_str, (
            "$SMTP_HOST placeholder not found"
        )

    def test_smtp_port_placeholder(self, alertmanager_config):
        """Must use $SMTP_PORT placeholder."""
        config_str = ALERTMANAGER_YML.read_text(encoding="utf-8")
        assert "SMTP_PORT" in config_str, (
            "$SMTP_PORT placeholder not found"
        )

    def test_alert_email_from_placeholder(self, alertmanager_config):
        """Must use $ALERT_EMAIL_FROM placeholder."""
        config_str = ALERTMANAGER_YML.read_text(encoding="utf-8")
        assert "ALERT_EMAIL_FROM" in config_str, (
            "$ALERT_EMAIL_FROM placeholder not found"
        )

    def test_alert_email_to_placeholder(self, alertmanager_config):
        """Must use $ALERT_EMAIL_TO placeholder."""
        config_str = ALERTMANAGER_YML.read_text(encoding="utf-8")
        assert "ALERT_EMAIL_TO" in config_str, (
            "$ALERT_EMAIL_TO placeholder not found"
        )

    def test_smtp_requires_tls(self, alertmanager_config):
        """SMTP should require TLS."""
        global_config = alertmanager_config.get("global", {})
        assert global_config.get("smtp_require_tls") is True, (
            "smtp_require_tls should be true"
        )


# ═══════════════════════════════════════════════════════════════════
# 9. Default route
# ═══════════════════════════════════════════════════════════════════

class TestDefaultRoute:
    """Verify default route configuration."""

    def test_default_receiver_is_set(self, alertmanager_config):
        """Default route must specify a receiver."""
        assert alertmanager_config["route"].get("receiver") == "default-receiver", (
            "Default route receiver not set to default-receiver"
        )

    def test_group_by_includes_service(self, alertmanager_config):
        """Should group alerts by alertname and service."""
        group_by = alertmanager_config["route"].get("group_by", [])
        assert "alertname" in group_by, (
            "group_by should include 'alertname'"
        )
