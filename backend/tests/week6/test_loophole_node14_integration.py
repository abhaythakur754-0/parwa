"""
Tests for Node 14 Guardrails — Loophole Detection Integration.

Validates that the guardrails_node properly integrates the loophole
detection engine as Check 3, and that loophole flags appear in the
output with the correct check identifier.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Use importlib to import the node module (can't use normal import
# because Python doesn't allow module names starting with digits)
guardrails_mod = None


def _get_guardrails_module():
    """Lazy import of the guardrails node module."""
    global guardrails_mod
    if guardrails_mod is None:
        guardrails_mod = __import__(
            "app.core.langgraph.nodes.14_guardrails",
            fromlist=["guardrails_node", "_check_loopholes"],
        )
    return guardrails_mod


# ── Integration Tests ──────────────────────────────────────────────


class TestGuardrailsLoopholeIntegration:
    """Test that the guardrails node integrates loophole detection."""

    def test_guardrails_node_runs_loophole_check(self):
        """guardrails_node should invoke the loophole check (Check 3)."""
        mod = _get_guardrails_module()

        with patch.object(mod, "_check_loopholes", return_value={
            "passed": True,
            "flags": [],
            "blocked_reason": "",
        }) as mock_loophole:
            with patch.object(mod, "_check_guardrails_engine", return_value={
                "passed": True, "flags": [], "blocked_reason": "",
            }):
                with patch.object(mod, "_check_hallucination", return_value={
                    "passed": True, "flags": [], "blocked_reason": "",
                    "hallucination_score": 0.1,
                }):
                    with patch.object(mod, "_check_prompt_injection", return_value={
                        "passed": True, "flags": [], "blocked_reason": "",
                    }):
                        with patch.object(mod, "_check_brand_voice", return_value={
                            "passed": True, "flags": [], "blocked_reason": "",
                        }):
                            result = mod.guardrails_node({
                                "selected_solution": "Safe response text.",
                                "pii_redacted_message": "Original query",
                                "tenant_id": "tenant_test",
                                "variant_tier": "mini",
                            })
                            mock_loophole.assert_called_once()

    def test_loophole_flags_have_check_field(self):
        """Loophole check flags should include check='loophole_detection'."""
        mod = _get_guardrails_module()

        loophole_flags = [{
            "rule_id": "LH-015",
            "severity": "critical",
            "message": "Prompt Injection Success detected",
        }]

        with patch.object(mod, "_check_loopholes", return_value={
            "passed": False,
            "flags": loophole_flags,
            "blocked_reason": "Loophole detected: LH-015",
        }):
            with patch.object(mod, "_check_guardrails_engine", return_value={
                "passed": True, "flags": [], "blocked_reason": "",
            }):
                with patch.object(mod, "_check_hallucination", return_value={
                    "passed": True, "flags": [], "blocked_reason": "",
                    "hallucination_score": 0.1,
                }):
                    with patch.object(mod, "_check_prompt_injection", return_value={
                        "passed": True, "flags": [], "blocked_reason": "",
                    }):
                        with patch.object(mod, "_check_brand_voice", return_value={
                            "passed": True, "flags": [], "blocked_reason": "",
                        }):
                            result = mod.guardrails_node({
                                "selected_solution": "Unsafe response.",
                                "pii_redacted_message": "Query text",
                                "tenant_id": "tenant_test",
                                "variant_tier": "mini",
                            })
                            # Find loophole detection flags in output
                            loophole_output_flags = [
                                f for f in result.get("guardrails_flags", [])
                                if f.get("check") == "loophole_detection"
                            ]
                            assert len(loophole_output_flags) > 0, (
                                "Loophole check flags should include check='loophole_detection'"
                            )

    def test_critical_loophole_causes_guardrails_fail(self):
        """When loophole detects critical match, guardrails_passed=False."""
        mod = _get_guardrails_module()

        loophole_flags = [{
            "rule_id": "LH-015",
            "severity": "critical",
            "message": "Prompt Injection Success: 'JAILBREAK' (confidence=90%)",
        }]

        with patch.object(mod, "_check_loopholes", return_value={
            "passed": False,
            "flags": loophole_flags,
            "blocked_reason": "Loophole detected: BLOCKED — [LH-015]",
        }):
            with patch.object(mod, "_check_guardrails_engine", return_value={
                "passed": True, "flags": [], "blocked_reason": "",
            }):
                with patch.object(mod, "_check_hallucination", return_value={
                    "passed": True, "flags": [], "blocked_reason": "",
                    "hallucination_score": 0.1,
                }):
                    with patch.object(mod, "_check_prompt_injection", return_value={
                        "passed": True, "flags": [], "blocked_reason": "",
                    }):
                        with patch.object(mod, "_check_brand_voice", return_value={
                            "passed": True, "flags": [], "blocked_reason": "",
                        }):
                            result = mod.guardrails_node({
                                "selected_solution": "Unsafe response.",
                                "pii_redacted_message": "Query",
                                "tenant_id": "tenant_test",
                                "variant_tier": "mini",
                            })
                            assert result["guardrails_passed"] is False

    def test_medium_loophole_does_not_block_guardrails(self):
        """Medium severity loophole should NOT cause guardrails_passed=False 
        because the loophole engine only sets requires_block=False for medium."""
        mod = _get_guardrails_module()

        # When loophole engine returns passed=True (medium = no block)
        loophole_flags = [{
            "rule_id": "LH-008",
            "severity": "medium",
            "message": "Brand Voice Violation: casual language",
        }]

        with patch.object(mod, "_check_loopholes", return_value={
            "passed": True,  # Medium severity doesn't block in engine
            "flags": loophole_flags,
            "blocked_reason": "",
        }):
            with patch.object(mod, "_check_guardrails_engine", return_value={
                "passed": True, "flags": [], "blocked_reason": "",
            }):
                with patch.object(mod, "_check_hallucination", return_value={
                    "passed": True, "flags": [], "blocked_reason": "",
                    "hallucination_score": 0.1,
                }):
                    with patch.object(mod, "_check_prompt_injection", return_value={
                        "passed": True, "flags": [], "blocked_reason": "",
                    }):
                        with patch.object(mod, "_check_brand_voice", return_value={
                            "passed": True, "flags": [], "blocked_reason": "",
                        }):
                            result = mod.guardrails_node({
                                "selected_solution": "Slightly casual response.",
                                "pii_redacted_message": "Query",
                                "tenant_id": "tenant_test",
                                "variant_tier": "mini",
                            })
                            assert result["guardrails_passed"] is True


# ── BC-008 Fallback Tests ──────────────────────────────────────────


class TestLoopholeFallback:
    """Test BC-008 fallback when loophole engine is unavailable."""

    def test_loophole_import_error_falls_back_to_warning(self):
        """When loophole engine can't be imported, guardrails pass with warning."""
        mod = _get_guardrails_module()

        with patch.object(mod, "_check_loopholes", side_effect=ImportError("No module")):
            with patch.object(mod, "_check_guardrails_engine", return_value={
                "passed": True, "flags": [], "blocked_reason": "",
            }):
                with patch.object(mod, "_check_hallucination", return_value={
                    "passed": True, "flags": [], "blocked_reason": "",
                    "hallucination_score": 0.1,
                }):
                    with patch.object(mod, "_check_prompt_injection", return_value={
                        "passed": True, "flags": [], "blocked_reason": "",
                    }):
                        with patch.object(mod, "_check_brand_voice", return_value={
                            "passed": True, "flags": [], "blocked_reason": "",
                        }):
                            result = mod.guardrails_node({
                                "selected_solution": "Some response.",
                                "pii_redacted_message": "Query",
                                "tenant_id": "tenant_test",
                                "variant_tier": "mini",
                            })
                            # BC-008: Should pass, not block
                            assert result["guardrails_passed"] is True
