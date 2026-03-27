"""
Tests for Feature Request & Feedback Intelligence (Week 32, Builder 4).

Tests cover:
- FeatureRequestHandler: submission, categorization, duplicates
- FeedbackAnalyzer: sentiment, themes, insights
- NPSTracker: scores, trends, segments
- RoadmapIntelligence: ranking, ROI, recommendations
- VotingSystem: weighted voting, limits, leaderboard
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from variants.saas.advanced.feature_request import (
    FeatureRequestHandler,
    FeatureRequest,
    RequestStatus,
    RequestPriority,
    RequestCategory,
)
from variants.saas.advanced.feedback_analyzer import (
    FeedbackAnalyzer,
    FeedbackItem,
    FeedbackInsight,
    SentimentType,
    UrgencyLevel,
    FeedbackSource,
)
from variants.saas.advanced.nps_tracker import (
    NPSTracker,
    NPSSurvey,
    NPSResponse,
    NPSMetrics,
    NPSCategory,
)
from variants.saas.advanced.roadmap_intelligence import (
    RoadmapIntelligence,
    RoadmapFeature,
    RoadmapRecommendation,
    FeatureStatus,
    ImpactLevel,
    EffortLevel,
)
from variants.saas.advanced.voting_system import (
    VotingSystem,
    Vote,
    VoteWeight,
    VoteStatus,
)


# =============================================================================
# FeatureRequestHandler Tests
# =============================================================================

class TestFeatureRequestHandler:
    """Tests for FeatureRequestHandler class."""

    @pytest.fixture
    def handler(self):
        """Create a feature request handler instance."""
        return FeatureRequestHandler(
            client_id="test_client_001",
            client_tier="parwa",
            is_enterprise=False
        )

    @pytest.mark.asyncio
    async def test_handler_initializes(self, handler):
        """Test that handler initializes correctly."""
        assert handler.client_id == "test_client_001"
        assert handler.client_tier == "parwa"

    @pytest.mark.asyncio
    async def test_submit_request(self, handler):
        """Test submitting a feature request."""
        request = await handler.submit_request(
            title="Add dark mode support",
            description="Please add dark mode for better visibility",
            category=RequestCategory.UX_UI,
            submitted_by="user_001",
            tags=["ui", "accessibility"]
        )

        assert request is not None
        assert request.title == "Add dark mode support"
        assert request.status == RequestStatus.SUBMITTED

    @pytest.mark.asyncio
    async def test_categorize_request(self, handler):
        """Test categorizing a request."""
        request = await handler.submit_request(
            title="New API endpoint",
            description="Need API for data export",
        )

        updated = await handler.categorize_request(request.id, RequestCategory.API)

        assert updated.category == RequestCategory.API

    @pytest.mark.asyncio
    async def test_detect_duplicate(self, handler):
        """Test duplicate detection."""
        # Submit original
        original = await handler.submit_request(
            title="Add dashboard export feature",
            description="Export dashboard data to CSV",
        )

        # Submit similar request
        duplicate = await handler.submit_request(
            title="Add dashboard export feature",
            description="Export dashboard data to CSV",
        )

        assert duplicate.status == RequestStatus.DUPLICATE
        assert duplicate.duplicate_of == original.id

    @pytest.mark.asyncio
    async def test_score_priority(self, handler):
        """Test priority scoring."""
        handler.is_enterprise = True  # Enterprise client

        request = await handler.submit_request(
            title="Critical security fix needed",
            description="Urgent security vulnerability",
            category=RequestCategory.SECURITY,
        )

        # Add votes
        await handler.add_vote(request.id, "voter_1")
        await handler.add_vote(request.id, "voter_2")

        result = await handler.score_priority(request.id)

        assert "score" in result
        assert "priority" in result

    @pytest.mark.asyncio
    async def test_update_status(self, handler):
        """Test updating request status."""
        request = await handler.submit_request(
            title="Test feature",
            description="Test description",
        )

        updated = await handler.update_status(
            request.id,
            RequestStatus.PLANNED,
            note="Added to Q2 roadmap"
        )

        assert updated.status == RequestStatus.PLANNED
        assert len(updated.notes) == 1

    @pytest.mark.asyncio
    async def test_add_vote(self, handler):
        """Test adding vote to request."""
        request = await handler.submit_request(
            title="Popular feature",
            description="Everyone wants this",
        )

        result = await handler.add_vote(request.id, "voter_001")

        assert result["voted"] is True
        assert result["votes"] == 1

    @pytest.mark.asyncio
    async def test_double_vote_prevention(self, handler):
        """Test preventing double voting."""
        request = await handler.submit_request(
            title="Feature",
            description="Description",
        )

        await handler.add_vote(request.id, "voter_001")
        result = await handler.add_vote(request.id, "voter_001")

        assert result["voted"] is False
        assert result["reason"] == "already_voted"

    @pytest.mark.asyncio
    async def test_link_github_issue(self, handler):
        """Test linking GitHub issue."""
        request = await handler.submit_request(
            title="Feature for GitHub",
            description="Description",
        )

        updated = await handler.link_github_issue(
            request.id,
            issue_id="123",
            issue_url="https://github.com/org/repo/issues/123"
        )

        assert updated.github_issue_id == "123"
        assert updated.status == RequestStatus.PLANNED

    @pytest.mark.asyncio
    async def test_get_top_requests(self, handler):
        """Test getting top requests."""
        # Create multiple requests
        for i in range(5):
            request = await handler.submit_request(
                title=f"Feature {i}",
                description=f"Description {i}",
            )
            # Add varying votes
            for j in range(i):
                await handler.add_vote(request.id, f"voter_{i}_{j}")

        top = await handler.get_top_requests(limit=3)

        assert len(top) == 3
        # Should be sorted by votes
        assert top[0].votes >= top[1].votes


# =============================================================================
# FeedbackAnalyzer Tests
# =============================================================================

class TestFeedbackAnalyzer:
    """Tests for FeedbackAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create a feedback analyzer instance."""
        return FeedbackAnalyzer(client_id="test_client_001")

    @pytest.mark.asyncio
    async def test_analyzer_initializes(self, analyzer):
        """Test that analyzer initializes correctly."""
        assert analyzer.client_id == "test_client_001"

    @pytest.mark.asyncio
    async def test_analyze_sentiment_positive(self, analyzer):
        """Test positive sentiment analysis."""
        result = await analyzer.analyze_sentiment(
            "I love this product! It's amazing and very helpful."
        )

        assert result["sentiment"] == "positive"
        assert result["score"] > 0.5

    @pytest.mark.asyncio
    async def test_analyze_sentiment_negative(self, analyzer):
        """Test negative sentiment analysis."""
        result = await analyzer.analyze_sentiment(
            "This is terrible. Very disappointing and frustrating experience."
        )

        assert result["sentiment"] == "negative"
        assert result["score"] < 0.5

    @pytest.mark.asyncio
    async def test_extract_themes(self, analyzer):
        """Test theme extraction."""
        result = await analyzer.extract_themes(
            "The application is very slow and the UI is confusing. Need better performance."
        )

        assert "performance" in result["themes"]
        assert "usability" in result["themes"]

    @pytest.mark.asyncio
    async def test_classify_urgency(self, analyzer):
        """Test urgency classification."""
        result = await analyzer.classify_urgency(
            "This is critical and blocking our production system!",
            FeedbackSource.TICKET
        )

        assert result["urgency"] in ["high", "critical"]

    @pytest.mark.asyncio
    async def test_process_feedback(self, analyzer):
        """Test processing feedback."""
        item = await analyzer.process_feedback(
            content="The new feature is great but performance is slow.",
            source=FeedbackSource.CHAT,
            customer_segment="enterprise"
        )

        assert item is not None
        assert item.processed_at is not None

    @pytest.mark.asyncio
    async def test_detect_trends(self, analyzer):
        """Test trend detection."""
        # Add multiple feedback items
        for i in range(10):
            await analyzer.process_feedback(
                content=f"Feedback item {i}",
                source=FeedbackSource.SURVEY,
            )

        trends = await analyzer.detect_trends(days=30)

        assert trends["detected"] is True
        assert trends["feedback_count"] >= 5

    @pytest.mark.asyncio
    async def test_aggregate_feedback(self, analyzer):
        """Test feedback aggregation."""
        await analyzer.process_feedback("Great product", FeedbackSource.SURVEY)
        await analyzer.process_feedback("Slow performance", FeedbackSource.TICKET)

        result = await analyzer.aggregate_feedback(group_by="source")

        assert "survey" in result["groups"]
        assert "ticket" in result["groups"]

    @pytest.mark.asyncio
    async def test_generate_insights(self, analyzer):
        """Test insight generation."""
        # Add negative feedback
        for i in range(10):
            await analyzer.process_feedback(
                content=f"The performance is terrible and slow {i}",
                source=FeedbackSource.TICKET,
            )

        insights = await analyzer.generate_insights(min_feedback=5)

        assert len(insights) >= 1


# =============================================================================
# NPSTracker Tests
# =============================================================================

class TestNPSTracker:
    """Tests for NPSTracker class."""

    @pytest.fixture
    def tracker(self):
        """Create an NPS tracker instance."""
        return NPSTracker(client_id="test_client_001", industry="saas")

    @pytest.mark.asyncio
    async def test_tracker_initializes(self, tracker):
        """Test that tracker initializes correctly."""
        assert tracker.client_id == "test_client_001"
        assert tracker.industry == "saas"

    @pytest.mark.asyncio
    async def test_create_survey(self, tracker):
        """Test creating a survey."""
        survey = await tracker.create_survey(
            name="Q1 NPS Survey",
            question="How likely are you to recommend us?"
        )

        assert survey is not None
        assert survey.name == "Q1 NPS Survey"

    @pytest.mark.asyncio
    async def test_distribute_survey(self, tracker):
        """Test distributing survey."""
        survey = await tracker.create_survey()
        result = await tracker.distribute_survey(survey.id, recipient_count=100)

        assert result["distributed"] is True

    @pytest.mark.asyncio
    async def test_record_promoter_response(self, tracker):
        """Test recording promoter response."""
        survey = await tracker.create_survey()

        response = await tracker.record_response(
            survey_id=survey.id,
            score=9,
            comment="Excellent product!",
            customer_segment="enterprise"
        )

        assert response.category == NPSCategory.PROMOTER
        assert response.score == 9

    @pytest.mark.asyncio
    async def test_record_detractor_response(self, tracker):
        """Test recording detractor response."""
        survey = await tracker.create_survey()

        response = await tracker.record_response(
            survey_id=survey.id,
            score=3,
            comment="Very disappointed"
        )

        assert response.category == NPSCategory.DETRACTOR

    @pytest.mark.asyncio
    async def test_calculate_nps_score(self, tracker):
        """Test NPS score calculation."""
        survey = await tracker.create_survey()

        # Add responses
        await tracker.record_response(survey.id, 10)  # Promoter
        await tracker.record_response(survey.id, 9)   # Promoter
        await tracker.record_response(survey.id, 8)   # Passive
        await tracker.record_response(survey.id, 5)   # Detractor

        metrics = await tracker.calculate_score(survey_id=survey.id)

        assert metrics.total_responses == 4
        assert metrics.promoters == 2
        assert metrics.detractors == 1
        # NPS = (2-1)/4 * 100 = 25
        assert metrics.nps_score == 25.0

    @pytest.mark.asyncio
    async def test_track_trends(self, tracker):
        """Test tracking trends."""
        survey = await tracker.create_survey()

        # Record multiple responses and calculate scores multiple times to build history
        for score in [9, 8, 7, 6, 10, 9]:
            await tracker.record_response(survey.id, score)

        await tracker.calculate_score()

        # Record more responses and calculate again to have 2+ periods in history
        survey2 = await tracker.create_survey()
        for score in [8, 9, 10, 8, 9]:
            await tracker.record_response(survey2.id, score)

        await tracker.calculate_score()

        trends = await tracker.track_trends()

        assert "trend" in trends
        assert "current_nps" in trends

    @pytest.mark.asyncio
    async def test_segment_analysis(self, tracker):
        """Test segment analysis."""
        survey = await tracker.create_survey()

        await tracker.record_response(survey.id, 9, customer_segment="enterprise")
        await tracker.record_response(survey.id, 7, customer_segment="smb")
        await tracker.record_response(survey.id, 5, customer_segment="smb")

        result = await tracker.segment_analysis()

        assert "enterprise" in result["segments"]
        assert "smb" in result["segments"]

    @pytest.mark.asyncio
    async def test_detractor_followup(self, tracker):
        """Test detractor follow-up."""
        survey = await tracker.create_survey()
        response = await tracker.record_response(survey.id, 4, "Not happy")

        result = await tracker.trigger_detractor_followup(response.id)

        assert result["triggered"] is True


# =============================================================================
# RoadmapIntelligence Tests
# =============================================================================

class TestRoadmapIntelligence:
    """Tests for RoadmapIntelligence class."""

    @pytest.fixture
    def roadmap(self):
        """Create a roadmap intelligence instance."""
        return RoadmapIntelligence(client_id="test_client_001")

    @pytest.mark.asyncio
    async def test_roadmap_initializes(self, roadmap):
        """Test that roadmap initializes correctly."""
        assert roadmap.client_id == "test_client_001"

    @pytest.mark.asyncio
    async def test_add_feature(self, roadmap):
        """Test adding a feature."""
        feature = await roadmap.add_feature(
            name="AI Assistant",
            description="Add AI-powered assistant",
            category="core",
            impact=ImpactLevel.HIGH,
            effort=EffortLevel.LARGE,
            segments=["enterprise", "pro"]
        )

        assert feature is not None
        assert feature.name == "AI Assistant"
        assert feature.status == FeatureStatus.BACKLOG

    @pytest.mark.asyncio
    async def test_rank_by_popularity(self, roadmap):
        """Test popularity ranking."""
        # Add features with different popularity
        f1 = await roadmap.add_feature("Popular Feature", "Desc", votes=100, requests=50)
        f2 = await roadmap.add_feature("Less Popular", "Desc", votes=10, requests=5)

        ranked = await roadmap.rank_by_popularity()

        assert len(ranked) == 2
        assert ranked[0]["feature"]["id"] == str(f1.id)

    @pytest.mark.asyncio
    async def test_estimate_impact(self, roadmap):
        """Test impact estimation."""
        feature = await roadmap.add_feature(
            "High Impact",
            "Desc",
            impact=ImpactLevel.CRITICAL,
            segments=["enterprise", "smb", "startup"]
        )

        result = await roadmap.estimate_impact(feature.id)

        assert result["impact_level"] == "critical"
        assert result["segment_reach"] == 3

    @pytest.mark.asyncio
    async def test_estimate_effort(self, roadmap):
        """Test effort estimation."""
        feature = await roadmap.add_feature(
            "Complex Feature",
            "Desc",
            effort=EffortLevel.HUGE
        )

        result = await roadmap.estimate_effort(feature.id)

        assert result["effort_level"] == "huge"
        assert result["estimated_weeks"] >= 10

    @pytest.mark.asyncio
    async def test_calculate_roi(self, roadmap):
        """Test ROI calculation."""
        feature = await roadmap.add_feature(
            "High ROI Feature",
            "Desc",
            impact=ImpactLevel.HIGH,
            effort=EffortLevel.SMALL,
            votes=100,
            revenue_impact=50000,
            strategic_value=0.8
        )

        result = await roadmap.calculate_roi(feature.id)

        assert result["roi_score"] > 2
        assert result["roi_level"] in ["excellent", "high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_generate_recommendations(self, roadmap):
        """Test generating recommendations."""
        # Add features
        await roadmap.add_feature("Feature A", "Desc", impact=ImpactLevel.HIGH, effort=EffortLevel.SMALL, votes=50)
        await roadmap.add_feature("Feature B", "Desc", impact=ImpactLevel.LOW, effort=EffortLevel.HUGE, votes=5)

        recommendations = await roadmap.generate_recommendations(count=5)

        assert len(recommendations) == 2
        # First should be higher priority
        assert recommendations[0].priority_score >= recommendations[1].priority_score


# =============================================================================
# VotingSystem Tests
# =============================================================================

class TestVotingSystem:
    """Tests for VotingSystem class."""

    @pytest.fixture
    def voting(self):
        """Create a voting system instance."""
        return VotingSystem(client_id="test_client_001", tier="parwa")

    @pytest.mark.asyncio
    async def test_voting_initializes(self, voting):
        """Test that voting initializes correctly."""
        assert voting.client_id == "test_client_001"
        assert voting.tier == "parwa"

    @pytest.mark.asyncio
    async def test_cast_vote(self, voting):
        """Test casting a vote."""
        feature_id = uuid4()

        result = await voting.cast_vote(feature_id, "user_001")

        assert result["cast"] is True
        assert result["weight"] == VoteWeight.PARWA.value  # 2 for parwa tier

    @pytest.mark.asyncio
    async def test_vote_limit(self, voting):
        """Test vote limit enforcement."""
        # Parwa tier has 15 vote limit
        for i in range(15):
            result = await voting.cast_vote(uuid4(), "user_001")
            assert result["cast"] is True

        # 16th vote should fail
        result = await voting.cast_vote(uuid4(), "user_001")
        assert result["cast"] is False
        assert result["reason"] == "vote_limit_reached"

    @pytest.mark.asyncio
    async def test_withdraw_vote(self, voting):
        """Test withdrawing a vote."""
        feature_id = uuid4()
        result = await voting.cast_vote(feature_id, "user_001")

        withdraw_result = await voting.withdraw_vote(UUID(result["vote_id"]))

        assert withdraw_result["withdrawn"] is True

    @pytest.mark.asyncio
    async def test_transfer_vote(self, voting):
        """Test transferring a vote."""
        from_feature = uuid4()
        to_feature = uuid4()

        await voting.cast_vote(from_feature, "user_001")
        result = await voting.transfer_vote(from_feature, to_feature, "user_001")

        assert result["transferred"] is True
        assert result["weight"] == VoteWeight.PARWA.value

    @pytest.mark.asyncio
    async def test_get_leaderboard(self, voting):
        """Test getting leaderboard."""
        # Cast votes for different features
        popular = uuid4()
        less_popular = uuid4()

        for i in range(5):
            await voting.cast_vote(popular, f"voter_{i}")
        await voting.cast_vote(less_popular, "voter_6")

        leaderboard = await voting.get_leaderboard()

        assert len(leaderboard.entries) == 2
        assert leaderboard.entries[0]["feature_id"] == str(popular)

    @pytest.mark.asyncio
    async def test_enterprise_weight(self):
        """Test enterprise tier has higher weight."""
        enterprise_voting = VotingSystem(client_id="test", tier="enterprise")
        feature_id = uuid4()

        result = await enterprise_voting.cast_vote(feature_id, "user_001")

        assert result["weight"] == VoteWeight.ENTERPRISE.value  # 5

    @pytest.mark.asyncio
    async def test_prevent_duplicate_vote(self, voting):
        """Test preventing duplicate votes."""
        feature_id = uuid4()

        await voting.cast_vote(feature_id, "user_001")
        result = await voting.cast_vote(feature_id, "user_001")

        assert result["cast"] is False
        assert result["reason"] == "already_voted"


# =============================================================================
# Integration Tests
# =============================================================================

class TestFeatureFeedbackIntegration:
    """Integration tests for feature request and feedback."""

    @pytest.mark.asyncio
    async def test_feedback_to_feature_workflow(self):
        """Test feedback driving feature request."""
        client_id = "test_integration_001"

        # Analyze feedback
        analyzer = FeedbackAnalyzer(client_id=client_id)
        feedback = await analyzer.process_feedback(
            content="We really need dark mode. The interface is hard to use at night.",
            source=FeedbackSource.SURVEY,
            customer_segment="premium"
        )

        # Create feature request based on feedback
        handler = FeatureRequestHandler(
            client_id=client_id,
            client_tier="parwa_high",
        )

        # Extract feature from themes
        if "ux" in feedback.themes:
            request = await handler.submit_request(
                title="Add Dark Mode Support",
                description="Based on customer feedback requesting dark mode",
                category=RequestCategory.UX_UI,
            )

            assert request is not None
            assert request.category == RequestCategory.UX_UI

    @pytest.mark.asyncio
    async def test_nps_to_retention_workflow(self):
        """Test NPS detractor triggering retention."""
        tracker = NPSTracker(client_id="test_nps_001")
        survey = await tracker.create_survey()

        # Record detractor response
        response = await tracker.record_response(
            survey_id=survey.id,
            score=4,
            comment="Service has been declining. Considering switching."
        )

        assert response.category == NPSCategory.DETRACTOR

        # Trigger follow-up
        followup = await tracker.trigger_detractor_followup(response.id)
        assert followup["triggered"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
