"""
Unit tests for Superglue Actions API + service layer + schemas + DB model.

Run: pytest tests/unit/test_superglue_actions_api.py -v
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from app.core.action_safety import ActionSafetyLevel
from app.schemas.superglue_actions import (
    ActionSafetyResponse,
    ClassifyActionRequest,
    ClassifyActionResponse,
    OverrideRequest,
    PersistClassificationRequest,
)


# ═══════════════════════════════════════════════════════════════════
# Pydantic Schemas Validation
# ═══════════════════════════════════════════════════════════════════

class TestSchemas:
    """Validate Pydantic schemas."""

    def test_classify_action_request_min_length(self):
        with pytest.raises(Exception):
            ClassifyActionRequest(tool_name="")

    def test_classify_action_request_ok(self):
        req = ClassifyActionRequest(tool_name="refund_tool", tool_description="Process refund")
        assert req.tool_name == "refund_tool"

    def test_classify_action_request_optional_desc(self):
        req = ClassifyActionRequest(tool_name="tool")
        assert req.tool_description is None

    def test_override_request(self):
        req = OverrideRequest(approval_required_override=True)
        assert req.approval_required_override is True

    def test_persist_request(self):
        req = PersistClassificationRequest(
            tool_id="t1", tool_name="Refund Tool",
            tool_description="Refund processing",
            output_schema={"type": "object"},
        )
        assert req.tool_id == "t1"
        assert req.output_schema == {"type": "object"}

    def test_persist_request_min_length(self):
        with pytest.raises(Exception):
            PersistClassificationRequest(tool_id="", tool_name="Tool")

    def test_action_safety_response(self):
        resp = ActionSafetyResponse(
            id="uuid-1", tool_id="t1", tool_name="Tool",
            safety_level="financial", needs_approval=True,
            regulatory_frameworks=["PCI-DSS"], is_active=True,
        )
        assert resp.safety_level == "financial"
        assert resp.needs_approval is True

    def test_classify_action_response(self):
        resp = ClassifyActionResponse(
            safety_level="read", needs_approval=False,
            matched_keyword="get", reasoning="test", confidence=0.9,
            regulatory_frameworks=[],
        )
        assert resp.confidence == 0.9


# ═══════════════════════════════════════════════════════════════════
# Service Layer (superglue_action_service.py)
# ═══════════════════════════════════════════════════════════════════

class TestSuperglueActionService:
    """Test the service layer without DB."""

    def test_classify_and_persist_no_db(self):
        """Without DB session, returns dict (no persist)."""
        from app.services.superglue_action_service import classify_and_persist
        result = classify_and_persist(
            company_id="company-1",
            tool_id="refund-by-email",
            tool_name="Refund by Email",
            tool_description="Process customer refund",
        )
        assert result["tool_id"] == "refund-by-email"
        assert result["safety_level"] == "financial"
        assert result["needs_approval"] is True
        assert "PCI-DSS" in result["regulatory_frameworks"]
        assert result["is_active"] is True

    def test_classify_and_persist_read_tool(self):
        """READ-level tool does not need approval."""
        from app.services.superglue_action_service import classify_and_persist
        result = classify_and_persist(
            company_id="company-1",
            tool_id="get-order-status",
            tool_name="Get Order Status",
        )
        assert result["safety_level"] == "read"
        assert result["needs_approval"] is False
        assert result["regulatory_frameworks"] == []

    def test_get_classification_no_db(self):
        """Without DB, returns None."""
        from app.services.superglue_action_service import get_classification
        result = get_classification("company-1", "tool-1")
        assert result is None

    def test_list_classifications_no_db(self):
        """Without DB, returns empty list."""
        from app.services.superglue_action_service import list_classifications
        result = list_classifications("company-1")
        assert result == []

    def test_toggle_override_no_db(self):
        """Without DB, returns None."""
        from app.services.superglue_action_service import toggle_override
        result = toggle_override("company-1", "tool-1", True)
        assert result is None


class TestServiceBC008:
    """BC-008: service never crashes."""

    def test_classify_persist_invalid_input(self):
        from app.services.superglue_action_service import classify_and_persist
        result = classify_and_persist("", "", "")
        assert isinstance(result, dict)
        assert "safety_level" in result


class TestDBModel:
    """Verify SuperglueActionSafety model file structure (no SQLAlchemy import)."""

    def test_model_file_exists(self):
        model_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend",
                                    "database", "models", "superglue_action_safety.py")
        assert os.path.exists(model_path)

    def test_model_has_tablename(self):
        model_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend",
                                    "database", "models", "superglue_action_safety.py")
        with open(model_path) as f:
            content = f.read()
        assert '__tablename__ = "superglue_action_safety"' in content

    def test_model_has_company_id_fk(self):
        model_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend",
                                    "database", "models", "superglue_action_safety.py")
        with open(model_path) as f:
            content = f.read()
        assert 'company_id' in content
        assert 'ForeignKey("companies.id"' in content

    def test_model_has_approval_override(self):
        model_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend",
                                    "database", "models", "superglue_action_safety.py")
        with open(model_path) as f:
            content = f.read()
        assert 'approval_required_override' in content

    def test_model_imported_in_init(self):
        init_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend",
                                 "database", "models", "__init__.py")
        with open(init_path) as f:
            content = f.read()
        assert 'SuperglueActionSafety' in content
