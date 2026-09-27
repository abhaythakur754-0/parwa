"""
Week 2 Tests — FAKE Voting Sub-System
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─── Config Tests ────────────────────────────────────────────────


class TestFakeVotingConfig:
    """Tests for variant-specific FAKE Voting configuration."""

    def test_mini_parwa_config(self):
        from app.core.fake_voting import get_fake_voting_config
        cfg = get_fake_voting_config("mini_parwa")
        assert cfg.num_candidates == 3
        assert cfg.consensus_threshold == 0.50
        assert "fluency" in cfg.evaluators
        assert "relevance" in cfg.evaluators

    def test_parwa_config(self):
        from app.core.fake_voting import get_fake_voting_config
        cfg = get_fake_voting_config("parwa")
        assert cfg.num_candidates == 5
        assert cfg.consensus_threshold == 0.60

    def test_parwa_high_config(self):
        from app.core.fake_voting import get_fake_voting_config
        cfg = get_fake_voting_config("parwa_high")
        assert cfg.num_candidates == 7
        assert cfg.consensus_threshold == 0.75
        assert "empathy" in cfg.evaluators

    def test_unknown_variant_defaults_to_mini(self):
        from app.core.fake_voting import get_fake_voting_config
        cfg = get_fake_voting_config("unknown_plan")
        assert cfg.num_candidates == 3
        assert cfg.consensus_threshold == 0.50


# ─── Red Flag Engine Tests ───────────────────────────────────────


class TestRedFlagEngine:
    """Tests for red flag detection."""

    @pytest.mark.asyncio
    async def test_hallucination_detection(self):
        from app.core.fake_voting import RedFlagEngine
        engine = RedFlagEngine()
        flags = await engine.check_red_flags(
            "I think this might possibly be the case, probably around 50%",
            "What is the refund policy?", "co_1"
        )
        types = [f["type"] for f in flags]
        assert "hallucination_risk" in types

    @pytest.mark.asyncio
    async def test_pii_leakage_detection(self):
        from app.core.fake_voting import RedFlagEngine
        engine = RedFlagEngine()
        flags = await engine.check_red_flags(
            "Please send your SSN 123-45-6789 to support@example.com",
            "How do I contact support?", "co_1"
        )
        types = [f["type"] for f in flags]
        assert "pii_leakage" in types

    @pytest.mark.asyncio
    async def test_off_topic_detection(self):
        from app.core.fake_voting import RedFlagEngine
        engine = RedFlagEngine()
        flags = await engine.check_red_flags(
            "The weather today is sunny and warm with clear skies.",
            "How do I reset my password?", "co_1"
        )
        types = [f["type"] for f in flags]
        assert "off_topic" in types

    @pytest.mark.asyncio
    async def test_policy_violation_detection(self):
        from app.core.fake_voting import RedFlagEngine
        engine = RedFlagEngine()
        flags = await engine.check_red_flags(
            "We guarantee you will never have any issues with our service.",
            "Is this reliable?", "co_1"
        )
        types = [f["type"] for f in flags]
        assert "policy_violation" in types

    @pytest.mark.asyncio
    async def test_no_flags_clean_text(self):
        from app.core.fake_voting import RedFlagEngine
        engine = RedFlagEngine()
        flags = await engine.check_red_flags(
            "To reset your password, go to Settings and click Reset Password.",
            "How do I reset my password?", "co_1"
        )
        assert len(flags) == 0

    @pytest.mark.asyncio
    async def test_multiple_flags(self):
        from app.core.fake_voting import RedFlagEngine
        engine = RedFlagEngine()
        flags = await engine.check_red_flags(
            "I think this is probably correct. Call me at 555-123-4567 for help.",
            "What is the pricing?", "co_1"
        )
        types = [f["type"] for f in flags]
        assert len(types) >= 2  # hallucination + PII


# ─── FAKE Voting Engine Tests ────────────────────────────────────


class TestFakeVotingEngine:
    """Tests for the main voting engine."""

    @pytest.mark.asyncio
    async def test_vote_single_candidate_wins(self):
        from app.core.fake_voting import FakeVotingEngine, get_fake_voting_config
        engine = FakeVotingEngine(get_fake_voting_config("mini_parwa"))
        candidates = [{"solution": "Go to settings to reset password.", "confidence": 0.8}]
        result = await engine.vote(candidates, "How to reset password?", "co_1", "mini_parwa")
        assert result["winner"]["solution"] == candidates[0]["solution"]

    @pytest.mark.asyncio
    async def test_vote_returns_consensus_score(self):
        from app.core.fake_voting import FakeVotingEngine, get_fake_voting_config
        engine = FakeVotingEngine(get_fake_voting_config("mini_parwa"))
        candidates = [{"solution": "Good response about billing.", "confidence": 0.9}]
        result = await engine.vote(candidates, "Billing question", "co_1")
        assert "consensus_score" in result
        assert 0.0 <= result["consensus_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_vote_fallback_on_error(self):
        from app.core.fake_voting import FakeVotingEngine, get_fake_voting_config

        engine = FakeVotingEngine(get_fake_voting_config("mini_parwa"))
        # Force all evaluators to fail by making SmartRouter unavailable
        with patch("app.core.fake_voting.SmartRouter", side_effect=Exception("no router")):
            candidates = [
                {"solution": "First candidate", "confidence": 0.5},
                {"solution": "Second candidate", "confidence": 0.7},
            ]
            result = await engine.vote(candidates, "test query", "co_1", "mini_parwa")
        # BC-008: should still return a valid winner
        assert "winner" in result
        assert "solution" in result["winner"]

    @pytest.mark.asyncio
    async def test_vote_with_red_flags(self):
        from app.core.fake_voting import FakeVotingEngine, get_fake_voting_config
        engine = FakeVotingEngine(get_fake_voting_config("parwa_high"))
        candidates = [
            {"solution": "Call me at 555-123-4567 for your SSN 123-45-6789.", "confidence": 0.9},
            {"solution": "Go to Settings to reset your password safely.", "confidence": 0.8},
        ]
        result = await engine.vote(candidates, "reset password", "co_1", "parwa_high")
        assert "red_flags" in result
