"""Tests for Day 22 AI tasks."""

from tests.unit.test_day22_setup import setup_day22_tests  # noqa: E402
setup_day22_tests()
from backend.app.tasks.ai_tasks import (  # noqa: E402
    classify_ticket,
    generate_response,
    score_confidence,
)


class TestClassifyTicket:
    def test_returns_dict_on_success(self):
        result = classify_ticket("company-123", "ticket-1", "I have a problem")
        assert isinstance(result, dict)

    def test_return_has_status_classified(self):
        result = classify_ticket("company-123", "ticket-1", "Issue text")
        assert result["status"] == "classified"

    def test_return_has_ticket_id(self):
        result = classify_ticket("company-123", "ticket-1", "Issue")
        assert result["ticket_id"] == "ticket-1"

    def test_return_has_priority(self):
        result = classify_ticket("company-123", "ticket-1", "Issue")
        assert "priority" in result

    def test_return_has_category(self):
        result = classify_ticket("company-123", "ticket-1", "Issue")
        assert "category" in result

    def test_return_has_sentiment(self):
        result = classify_ticket("company-123", "ticket-1", "Issue")
        assert "sentiment" in result

    def test_return_has_confidence(self):
        result = classify_ticket("company-123", "ticket-1", "Issue")
        assert "confidence" in result

    def test_confidence_in_valid_range(self):
        result = classify_ticket("company-123", "ticket-1", "Issue")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_queue_is_ai_light(self):
        assert classify_ticket.queue == "ai_light"

    def test_max_retries_is_3(self):
        assert classify_ticket.max_retries == 3

    def test_soft_time_limit(self):
        assert classify_ticket.soft_time_limit == 30

    def test_time_limit(self):
        assert classify_ticket.time_limit == 60

    def test_task_name_registered(self):
        assert "ai.classify_ticket" in classify_ticket.name

    def test_empty_text_still_works(self):
        result = classify_ticket("c1", "t1", text="")
        assert result["status"] == "classified"


class TestGenerateResponse:
    def test_returns_dict_on_success(self):
        result = generate_response("company-123", "ticket-1")
        assert isinstance(result, dict)

    def test_return_has_status_generated(self):
        result = generate_response("company-123", "ticket-1")
        assert result["status"] == "generated"

    def test_return_has_ticket_id(self):
        result = generate_response("company-123", "ticket-1")
        assert result["ticket_id"] == "ticket-1"

    def test_return_has_response_text(self):
        result = generate_response("company-123", "ticket-1")
        assert "response_text" in result

    def test_return_has_confidence(self):
        result = generate_response("company-123", "ticket-1")
        assert "confidence" in result

    def test_confidence_in_valid_range(self):
        result = generate_response("company-123", "ticket-1")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_queue_is_ai_heavy(self):
        assert generate_response.queue == "ai_heavy"

    def test_max_retries_is_3(self):
        assert generate_response.max_retries == 3

    def test_soft_time_limit(self):
        assert generate_response.soft_time_limit == 120

    def test_time_limit(self):
        assert generate_response.time_limit == 300

    def test_task_name_registered(self):
        assert "ai.generate_response" in generate_response.name

    def test_with_conversation_history(self):
        history = [{"role": "user", "content": "hello"}]
        result = generate_response("c1", "t1", conversation_history=history, context="support")
        assert result["status"] == "generated"


class TestScoreConfidence:
    def test_returns_dict_on_success(self):
        result = score_confidence("company-123", "ticket-1", "Some response text")
        assert isinstance(result, dict)

    def test_return_has_status_scored(self):
        result = score_confidence("company-123", "ticket-1", "Response text")
        assert result["status"] == "scored"

    def test_return_has_ticket_id(self):
        result = score_confidence("company-123", "ticket-1", "Response")
        assert result["ticket_id"] == "ticket-1"

    def test_return_has_confidence(self):
        result = score_confidence("company-123", "ticket-1", "Response")
        assert "confidence" in result

    def test_return_has_should_escalate(self):
        result = score_confidence("company-123", "ticket-1", "Response")
        assert "should_escalate" in result

    def test_should_escalate_is_bool(self):
        result = score_confidence("company-123", "ticket-1", "Response")
        assert isinstance(result["should_escalate"], bool)

    def test_confidence_in_valid_range(self):
        result = score_confidence("company-123", "ticket-1", "Response")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_queue_is_ai_light(self):
        assert score_confidence.queue == "ai_light"

    def test_max_retries_is_2(self):
        assert score_confidence.max_retries == 2

    def test_soft_time_limit(self):
        assert score_confidence.soft_time_limit == 15

    def test_time_limit(self):
        assert score_confidence.time_limit == 30

    def test_task_name_registered(self):
        assert "ai.score_confidence" in score_confidence.name

    def test_empty_response_text(self):
        result = score_confidence("c1", "t1")
        assert result["status"] == "scored"
