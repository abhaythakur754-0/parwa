"""
Tests for F-143: GST (Guided Sequential Thinking) — Tier 3 Premium AI Reasoning.

Covers configuration, dataclasses, enums, should_activate logic, each
checkpoint individually, option generation per decision scope, impact
analysis scoring, risk assessment, recommendation selection, full
pipeline, company isolation (BC-001), and error fallback (BC-008).

Target: 80+ tests.
"""

import pytest
from unittest.mock import patch

from app.core.technique_router import TechniqueID, QuerySignals
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
)
from app.core.techniques.gst import (
    GSTConfig,
    GSTNode,
    GSTProcessor,
    GSTCheckpoint,
    GSTOption,
    GSTResult,
    DecisionScope,
    RiskCategory,
    RiskSeverity,
    _SCOPE_OPTIONS,
    _SCOPE_STAKEHOLDERS,
    _SCOPE_CONSTRAINTS,
    _DEFAULT_WEIGHTS,
)

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def processor() -> GSTProcessor:
    return GSTProcessor()


@pytest.fixture
def company_processor() -> GSTProcessor:
    config = GSTConfig(
        company_id="comp_456",
        max_options=2,
        risk_threshold=0.5,
    )
    return GSTProcessor(config=config)


@pytest.fixture
def node() -> GSTNode:
    return GSTNode()


@pytest.fixture
def strategic_state() -> ConversationState:
    return ConversationState(
        query="We need to modify our contract terms for the upcoming renewal",
        signals=QuerySignals(is_strategic_decision=True),
    )


@pytest.fixture
def non_strategic_state() -> ConversationState:
    return ConversationState(
        query="How do I reset my password?",
        signals=QuerySignals(is_strategic_decision=False),
    )


@pytest.fixture
def empty_state() -> ConversationState:
    return ConversationState(
        query="",
        signals=QuerySignals(is_strategic_decision=True),
    )


# ── Config Tests ─────────────────────────────────────────────────────


class TestGSTConfig:
    """Tests for GSTConfig frozen dataclass."""

    def test_default_config(self):
        config = GSTConfig()
        assert config.company_id == ""
        assert config.max_options == 5
        assert config.risk_threshold == 0.7

    def test_frozen_immutability(self):
        config = GSTConfig(company_id="comp_1")
        with pytest.raises(AttributeError):
            config.company_id = "new"  # type: ignore

    def test_custom_config(self):
        config = GSTConfig(
            company_id="comp_2",
            max_options=3,
            risk_threshold=0.5,
        )
        assert config.company_id == "comp_2"
        assert config.max_options == 3
        assert config.risk_threshold == 0.5

    def test_max_options_zero(self):
        config = GSTConfig(max_options=0)
        assert config.max_options == 0

    def test_max_options_large(self):
        config = GSTConfig(max_options=100)
        assert config.max_options == 100

    def test_company_id_default_empty(self):
        config = GSTConfig()
        assert config.company_id == ""

    def test_risk_threshold_zero(self):
        config = GSTConfig(risk_threshold=0.0)
        assert config.risk_threshold == 0.0

    def test_risk_threshold_one(self):
        config = GSTConfig(risk_threshold=1.0)
        assert config.risk_threshold == 1.0


# ── Enum Tests ───────────────────────────────────────────────────────


class TestDecisionScope:
    """Tests for DecisionScope enum."""

    def test_all_scopes(self):
        expected = {
            "contract_modification",
            "feature_request",
            "policy_change",
            "escalation",
            "pricing",
            "general",
        }
        actual = {s.value for s in DecisionScope}
        assert actual == expected

    def test_contract_modification(self):
        assert DecisionScope.CONTRACT_MODIFICATION.value == "contract_modification"

    def test_feature_request(self):
        assert DecisionScope.FEATURE_REQUEST.value == "feature_request"

    def test_policy_change(self):
        assert DecisionScope.POLICY_CHANGE.value == "policy_change"

    def test_escalation(self):
        assert DecisionScope.ESCALATION.value == "escalation"

    def test_pricing(self):
        assert DecisionScope.PRICING.value == "pricing"

    def test_general(self):
        assert DecisionScope.GENERAL.value == "general"

    def test_string_comparison(self):
        assert DecisionScope.CONTRACT_MODIFICATION == "contract_modification"


class TestRiskCategory:
    """Tests for RiskCategory enum."""

    def test_all_categories(self):
        expected = {"compliance", "customer_churn", "financial", "operational"}
        actual = {c.value for c in RiskCategory}
        assert actual == expected

    def test_compliance(self):
        assert RiskCategory.COMPLIANCE.value == "compliance"

    def test_customer_churn(self):
        assert RiskCategory.CUSTOMER_CHURN.value == "customer_churn"

    def test_financial(self):
        assert RiskCategory.FINANCIAL.value == "financial"

    def test_operational(self):
        assert RiskCategory.OPERATIONAL.value == "operational"


class TestRiskSeverity:
    """Tests for RiskSeverity enum."""

    def test_all_severities(self):
        expected = {"low", "medium", "high", "critical"}
        actual = {s.value for s in RiskSeverity}
        assert actual == expected

    def test_ordering(self):
        assert RiskSeverity.LOW.value == "low"
        assert RiskSeverity.MEDIUM.value == "medium"
        assert RiskSeverity.HIGH.value == "high"
        assert RiskSeverity.CRITICAL.value == "critical"


# ── Dataclass Tests ──────────────────────────────────────────────────


class TestGSTCheckpoint:
    """Tests for GSTCheckpoint dataclass."""

    def test_default_values(self):
        cp = GSTCheckpoint()
        assert cp.checkpoint_number == 0
        assert cp.name == ""
        assert cp.result == {}

    def test_full_creation(self):
        cp = GSTCheckpoint(
            checkpoint_number=1,
            name="problem_definition",
            result={"scope": "contract_modification"},
        )
        assert cp.checkpoint_number == 1
        assert cp.name == "problem_definition"
        assert cp.result["scope"] == "contract_modification"

    def test_mutable(self):
        cp = GSTCheckpoint()
        cp.name = "updated"
        assert cp.name == "updated"

    def test_to_dict_keys(self):
        cp = GSTCheckpoint(checkpoint_number=3, name="test", result={"a": 1})
        d = cp.to_dict()
        assert set(d.keys()) == {"checkpoint_number", "name", "result"}
        assert d["checkpoint_number"] == 3
        assert d["name"] == "test"
        assert d["result"] == {"a": 1}


class TestGSTOption:
    """Tests for GSTOption dataclass."""

    def test_default_values(self):
        opt = GSTOption()
        assert opt.option_id == ""
        assert opt.description == ""
        assert opt.impact_scores == {}
        assert opt.risks == []
        assert opt.total_score == 0.0

    def test_full_creation(self):
        opt = GSTOption(
            option_id="contract_modification_opt_1",
            description="Approve the modification",
            impact_scores={"customer_satisfaction": 0.9, "cost_impact": 0.3},
            risks=[{"category": "financial", "severity": "medium"}],
            total_score=0.65,
        )
        assert opt.option_id == "contract_modification_opt_1"
        assert opt.total_score == 0.65
        assert len(opt.risks) == 1

    def test_to_dict_keys(self):
        opt = GSTOption(
            option_id="opt_1",
            description="test",
            impact_scores={"a": 0.5},
            risks=[{"r": "low"}],
            total_score=0.5,
        )
        d = opt.to_dict()
        expected_keys = {
            "option_id",
            "description",
            "impact_scores",
            "risks",
            "total_score",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_total_score_rounded(self):
        opt = GSTOption(total_score=0.654321)
        d = opt.to_dict()
        assert d["total_score"] == 0.6543


class TestGSTResult:
    """Tests for GSTResult dataclass."""

    def test_default_values(self):
        result = GSTResult()
        assert result.problem_definition == {}
        assert result.options == []
        assert result.recommendation == {}
        assert result.checkpoints == []
        assert result.steps_applied == []
        assert result.risk_summary == {}

    def test_full_creation(self):
        options = [GSTOption(option_id="opt_1")]
        checkpoints = [GSTCheckpoint(checkpoint_number=1, name="test")]
        result = GSTResult(
            problem_definition={"scope": "contract_modification"},
            options=options,
            recommendation={"selected_option": {"option_id": "opt_1"}},
            checkpoints=checkpoints,
            steps_applied=["problem_definition", "option_generation"],
            risk_summary={"overall_max_severity": "medium"},
        )
        assert len(result.options) == 1
        assert len(result.checkpoints) == 1
        assert result.steps_applied == ["problem_definition", "option_generation"]

    def test_to_dict_keys(self):
        result = GSTResult()
        d = result.to_dict()
        expected_keys = {
            "problem_definition",
            "options",
            "recommendation",
            "checkpoints",
            "steps_applied",
            "risk_summary",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_options_serialized(self):
        opt = GSTOption(option_id="opt_1", description="desc")
        result = GSTResult(options=[opt])
        d = result.to_dict()
        assert len(d["options"]) == 1
        assert d["options"][0]["option_id"] == "opt_1"

    def test_to_dict_checkpoints_serialized(self):
        cp = GSTCheckpoint(checkpoint_number=2, name="impact_analysis")
        result = GSTResult(checkpoints=[cp])
        d = result.to_dict()
        assert len(d["checkpoints"]) == 1
        assert d["checkpoints"][0]["name"] == "impact_analysis"


# ── Node Basic Tests ────────────────────────────────────────────────


class TestGSTNode:
    """Tests for the GSTNode class."""

    def test_is_base_technique_node(self, node):
        assert isinstance(node, BaseTechniqueNode)

    def test_technique_id(self, node):
        assert node.technique_id == TechniqueID.GST

    def test_technique_id_is_string(self, node):
        assert isinstance(node.technique_id.value, str)

    def test_technique_info_populated(self, node):
        assert node.technique_info is not None
        assert node.technique_info.id == TechniqueID.GST

    def test_tier_3(self, node):
        from app.core.technique_router import TechniqueTier

        assert node.technique_info.tier == TechniqueTier.TIER_3

    def test_node_with_custom_config(self):
        config = GSTConfig(
            company_id="custom",
            max_options=2,
        )
        node = GSTNode(config=config)
        assert node.technique_id == TechniqueID.GST


# ── should_activate Tests ────────────────────────────────────────────


class TestShouldActivate:
    """Tests for GSTNode.should_activate()."""

    @pytest.mark.asyncio
    async def test_strategic_decision_activates(self, node, strategic_state):
        assert await node.should_activate(strategic_state) is True

    @pytest.mark.asyncio
    async def test_non_strategic_does_not_activate(self, node, non_strategic_state):
        assert await node.should_activate(non_strategic_state) is False

    @pytest.mark.asyncio
    async def test_default_signals_false(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(),
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_explicit_false(self, node):
        state = ConversationState(
            query="test",
            signals=QuerySignals(is_strategic_decision=False),
        )
        assert await node.should_activate(state) is False

    @pytest.mark.asyncio
    async def test_other_signals_irrelevant_when_strategic(self, node):
        """Even with low confidence, strategic decision should activate."""
        state = ConversationState(
            query="test",
            signals=QuerySignals(
                is_strategic_decision=True,
                confidence_score=0.1,
                sentiment_score=0.0,
            ),
        )
        assert await node.should_activate(state) is True


# ── Step 1: Problem Definition Tests ────────────────────────────────


class TestDefineProblem:
    """Tests for Step 1 — define_problem()."""

    @pytest.mark.asyncio
    async def test_contract_modification(self, processor):
        result = await processor.define_problem(
            "We need to modify our contract terms",
        )
        assert result["scope"] == "contract_modification"
        assert "customer" in result["stakeholders"]
        assert "company" in result["stakeholders"]
        assert len(result["constraints"]) > 0

    @pytest.mark.asyncio
    async def test_feature_request(self, processor):
        result = await processor.define_problem(
            "We would like to request a new feature for our dashboard",
        )
        assert result["scope"] == "feature_request"

    @pytest.mark.asyncio
    async def test_policy_change(self, processor):
        result = await processor.define_problem(
            "Our compliance team wants to change the refund policy",
        )
        assert result["scope"] == "policy_change"

    @pytest.mark.asyncio
    async def test_escalation(self, processor):
        result = await processor.define_problem(
            "This needs immediate escalation to management",
        )
        assert result["scope"] == "escalation"

    @pytest.mark.asyncio
    async def test_pricing(self, processor):
        result = await processor.define_problem(
            "We want to discuss pricing changes for our plan",
        )
        assert result["scope"] == "pricing"

    @pytest.mark.asyncio
    async def test_general(self, processor):
        result = await processor.define_problem(
            "How should we handle this situation?",
        )
        assert result["scope"] == "general"

    @pytest.mark.asyncio
    async def test_empty_query(self, processor):
        result = await processor.define_problem("")
        assert result == {}

    @pytest.mark.asyncio
    async def test_whitespace_query(self, processor):
        result = await processor.define_problem("   ")
        assert result == {}

    @pytest.mark.asyncio
    async def test_has_description(self, processor):
        result = await processor.define_problem(
            "Modify the contract renewal terms",
        )
        assert "description" in result
        assert "contract" in result["description"].lower()

    @pytest.mark.asyncio
    async def test_stakeholders_present(self, processor):
        result = await processor.define_problem(
            "We want a feature added to the product",
        )
        assert "stakeholders" in result
        assert isinstance(result["stakeholders"], list)
        assert len(result["stakeholders"]) > 0

    @pytest.mark.asyncio
    async def test_constraints_present(self, processor):
        result = await processor.define_problem(
            "Modify our contract",
        )
        assert "constraints" in result
        assert isinstance(result["constraints"], list)


# ── Step 2: Option Generation Tests ──────────────────────────────────


class TestGenerateOptions:
    """Tests for Step 2 — generate_options()."""

    @pytest.mark.asyncio
    async def test_contract_options(self, processor):
        options = await processor.generate_options(
            DecisionScope.CONTRACT_MODIFICATION,
        )
        assert len(options) >= 2
        assert all(isinstance(o, GSTOption) for o in options)
        assert all(
            o.option_id.startswith("contract_modification_opt_") for o in options
        )

    @pytest.mark.asyncio
    async def test_feature_options(self, processor):
        options = await processor.generate_options(
            DecisionScope.FEATURE_REQUEST,
        )
        assert len(options) >= 2

    @pytest.mark.asyncio
    async def test_policy_options(self, processor):
        options = await processor.generate_options(
            DecisionScope.POLICY_CHANGE,
        )
        assert len(options) >= 2

    @pytest.mark.asyncio
    async def test_escalation_options(self, processor):
        options = await processor.generate_options(
            DecisionScope.ESCALATION,
        )
        assert len(options) >= 2

    @pytest.mark.asyncio
    async def test_pricing_options(self, processor):
        options = await processor.generate_options(
            DecisionScope.PRICING,
        )
        assert len(options) >= 2

    @pytest.mark.asyncio
    async def test_general_options(self, processor):
        options = await processor.generate_options(
            DecisionScope.GENERAL,
        )
        assert len(options) >= 2

    @pytest.mark.asyncio
    async def test_max_options_respected(self, company_processor):
        options = await company_processor.generate_options(
            DecisionScope.CONTRACT_MODIFICATION,
        )
        assert len(options) <= 2  # company_processor has max_options=2

    @pytest.mark.asyncio
    async def test_default_max_options(self, processor):
        options = await processor.generate_options(
            DecisionScope.GENERAL,
        )
        assert len(options) <= 5

    @pytest.mark.asyncio
    async def test_options_have_base_scores(self, processor):
        options = await processor.generate_options(
            DecisionScope.CONTRACT_MODIFICATION,
        )
        for opt in options:
            assert "customer_satisfaction" in opt.impact_scores
            assert "cost_impact" in opt.impact_scores
            assert "policy_compliance" in opt.impact_scores
            assert "implementation_feasibility" in opt.impact_scores

    @pytest.mark.asyncio
    async def test_options_have_risks(self, processor):
        options = await processor.generate_options(
            DecisionScope.CONTRACT_MODIFICATION,
        )
        for opt in options:
            assert isinstance(opt.risks, list)

    @pytest.mark.asyncio
    async def test_option_descriptions_nonempty(self, processor):
        options = await processor.generate_options(
            DecisionScope.PRICING,
        )
        for opt in options:
            assert opt.description != ""

    @pytest.mark.asyncio
    async def test_max_options_zero(self):
        config = GSTConfig(max_options=0)
        proc = GSTProcessor(config=config)
        options = await proc.generate_options(DecisionScope.GENERAL)
        assert len(options) == 0


# ── Step 3: Impact Analysis Tests ────────────────────────────────────


class TestAnalyzeImpact:
    """Tests for Step 3 — analyze_impact()."""

    @pytest.mark.asyncio
    async def test_calculates_total_score(self, processor):
        options = [
            GSTOption(
                option_id="opt_1",
                impact_scores={
                    "customer_satisfaction": 0.8,
                    "cost_impact": 0.6,
                    "policy_compliance": 0.9,
                    "implementation_feasibility": 0.7,
                },
            ),
        ]
        result = await processor.analyze_impact(options)
        assert result[0].total_score > 0.0

    @pytest.mark.asyncio
    async def test_uses_default_weights(self, processor):
        options = [
            GSTOption(
                option_id="opt_1",
                impact_scores={
                    "customer_satisfaction": 1.0,
                    "cost_impact": 1.0,
                    "policy_compliance": 1.0,
                    "implementation_feasibility": 1.0,
                },
            ),
        ]
        result = await processor.analyze_impact(options)
        assert result[0].total_score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_zero_scores(self, processor):
        options = [
            GSTOption(
                option_id="opt_1",
                impact_scores={
                    "customer_satisfaction": 0.0,
                    "cost_impact": 0.0,
                    "policy_compliance": 0.0,
                    "implementation_feasibility": 0.0,
                },
            ),
        ]
        result = await processor.analyze_impact(options)
        assert result[0].total_score == 0.0

    @pytest.mark.asyncio
    async def test_custom_weights(self, processor):
        options = [
            GSTOption(
                option_id="opt_1",
                impact_scores={
                    "customer_satisfaction": 1.0,
                    "cost_impact": 0.0,
                    "policy_compliance": 0.0,
                    "implementation_feasibility": 0.0,
                },
            ),
        ]
        custom_weights = {
            "customer_satisfaction": 1.0,
            "cost_impact": 0.0,
            "policy_compliance": 0.0,
            "implementation_feasibility": 0.0,
        }
        result = await processor.analyze_impact(options, weights=custom_weights)
        assert result[0].total_score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_multiple_options_ranked(self, processor):
        options = [
            GSTOption(
                option_id="opt_low",
                impact_scores={
                    "customer_satisfaction": 0.3,
                    "cost_impact": 0.3,
                    "policy_compliance": 0.3,
                    "implementation_feasibility": 0.3,
                },
            ),
            GSTOption(
                option_id="opt_high",
                impact_scores={
                    "customer_satisfaction": 0.9,
                    "cost_impact": 0.9,
                    "policy_compliance": 0.9,
                    "implementation_feasibility": 0.9,
                },
            ),
        ]
        result = await processor.analyze_impact(options)
        assert result[0].total_score < result[1].total_score

    @pytest.mark.asyncio
    async def test_missing_dimension_defaults_zero(self, processor):
        options = [
            GSTOption(
                option_id="opt_1",
                impact_scores={"customer_satisfaction": 0.5},
            ),
        ]
        result = await processor.analyze_impact(options)
        assert result[0].total_score > 0.0
        # Only customer_satisfaction contributes
        assert result[0].total_score == pytest.approx(
            0.5 * _DEFAULT_WEIGHTS["customer_satisfaction"]
        )

    @pytest.mark.asyncio
    async def test_empty_options(self, processor):
        result = await processor.analyze_impact([])
        assert result == []

    @pytest.mark.asyncio
    async def test_scores_are_float(self, processor):
        options = [
            GSTOption(
                option_id="opt_1",
                impact_scores={
                    "customer_satisfaction": 0.8,
                    "cost_impact": 0.6,
                    "policy_compliance": 0.9,
                    "implementation_feasibility": 0.7,
                },
            ),
        ]
        result = await processor.analyze_impact(options)
        assert isinstance(result[0].total_score, float)


# ── Step 4: Risk Assessment Tests ────────────────────────────────────


class TestAssessRisks:
    """Tests for Step 4 — assess_risks()."""

    @pytest.mark.asyncio
    async def test_basic_structure(self, processor):
        options = [
            GSTOption(
                option_id="opt_1",
                risks=[
                    {
                        "category": RiskCategory.FINANCIAL,
                        "severity": RiskSeverity.MEDIUM,
                    }
                ],
            ),
        ]
        result = await processor.assess_risks(options)
        assert "per_option" in result
        assert "overall_max_severity" in result
        assert "risk_categories" in result
        assert "overall_risk_score" in result

    @pytest.mark.asyncio
    async def test_per_option_risk_count(self, processor):
        options = [
            GSTOption(
                option_id="opt_1",
                risks=[
                    {"category": "financial", "severity": "medium"},
                    {"category": "operational", "severity": "low"},
                ],
            ),
        ]
        result = await processor.assess_risks(options)
        assert result["per_option"][0]["risk_count"] == 2

    @pytest.mark.asyncio
    async def test_max_severity_correct(self, processor):
        options = [
            GSTOption(
                option_id="opt_1",
                risks=[
                    {"category": "financial", "severity": "critical"},
                    {"category": "operational", "severity": "low"},
                ],
            ),
        ]
        result = await processor.assess_risks(options)
        assert result["per_option"][0]["max_severity"] == "critical"
        assert result["overall_max_severity"] == "critical"

    @pytest.mark.asyncio
    async def test_no_risks(self, processor):
        options = [GSTOption(option_id="opt_1", risks=[])]
        result = await processor.assess_risks(options)
        assert result["per_option"][0]["risk_count"] == 0
        assert result["per_option"][0]["max_severity"] == "none"
        assert result["per_option"][0]["risk_score"] == 0.0

    @pytest.mark.asyncio
    async def test_empty_options(self, processor):
        result = await processor.assess_risks([])
        assert result["overall_max_severity"] == "low"
        assert result["overall_risk_score"] == 0.0

    @pytest.mark.asyncio
    async def test_risk_categories_collected(self, processor):
        options = [
            GSTOption(
                option_id="opt_1",
                risks=[
                    {"category": "financial", "severity": "medium"},
                    {"category": "compliance", "severity": "low"},
                ],
            ),
        ]
        result = await processor.assess_risks(options)
        assert "financial" in result["risk_categories"]
        assert "compliance" in result["risk_categories"]

    @pytest.mark.asyncio
    async def test_risk_score_range(self, processor):
        options = [
            GSTOption(
                option_id="opt_1",
                risks=[{"category": "financial", "severity": "critical"}],
            ),
        ]
        result = await processor.assess_risks(options)
        assert 0.0 <= result["per_option"][0]["risk_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_multiple_options_max_severity(self, processor):
        options = [
            GSTOption(
                option_id="opt_low",
                risks=[{"category": "operational", "severity": "low"}],
            ),
            GSTOption(
                option_id="opt_high",
                risks=[{"category": "financial", "severity": "critical"}],
            ),
        ]
        result = await processor.assess_risks(options)
        assert result["overall_max_severity"] == "critical"

    @pytest.mark.asyncio
    async def test_string_severity_values(self, processor):
        """Test that string-based severity values work."""
        options = [
            GSTOption(
                option_id="opt_1",
                risks=[{"category": "financial", "severity": "high"}],
            ),
        ]
        result = await processor.assess_risks(options)
        assert result["per_option"][0]["max_severity"] == "high"


# ── Step 5: Recommendation Tests ─────────────────────────────────────


class TestRecommend:
    """Tests for Step 5 — recommend()."""

    @pytest.mark.asyncio
    async def test_selects_best_option(self, processor):
        options = [
            GSTOption(option_id="low", total_score=0.3),
            GSTOption(option_id="high", total_score=0.8),
        ]
        risk_summary = {
            "per_option": [
                {"option_id": "low", "risk_score": 0.0},
                {"option_id": "high", "risk_score": 0.0},
            ],
        }
        result = await processor.recommend(options, risk_summary)
        assert result["selected_option"]["option_id"] == "high"

    @pytest.mark.asyncio
    async def test_has_rationale(self, processor):
        options = [
            GSTOption(
                option_id="opt_1",
                total_score=0.7,
                impact_scores={"customer_satisfaction": 0.8, "cost_impact": 0.6},
            ),
        ]
        risk_summary = {
            "per_option": [{"option_id": "opt_1", "risk_score": 0.0}],
        }
        result = await processor.recommend(options, risk_summary)
        assert "rationale" in result
        assert len(result["rationale"]) > 0

    @pytest.mark.asyncio
    async def test_empty_options(self, processor):
        result = await processor.recommend([], {"per_option": []})
        assert result["selected_option"] is None
        assert "No options" in result["rationale"]

    @pytest.mark.asyncio
    async def test_risk_threshold_filters(self):
        """Options with high risk should be filtered when risk_threshold is high."""
        config = GSTConfig(risk_threshold=0.8)
        proc = GSTProcessor(config=config)
        options = [
            GSTOption(option_id="risky", total_score=0.9),
            GSTOption(option_id="safe", total_score=0.7),
        ]
        risk_summary = {
            "per_option": [
                {"option_id": "risky", "risk_score": 0.5},
                {"option_id": "safe", "risk_score": 0.0},
            ],
        }
        # risky: 1 - 0.5 = 0.5 < 0.8 threshold → filtered out
        result = await proc.recommend(options, risk_summary)
        assert result["selected_option"]["option_id"] == "safe"

    @pytest.mark.asyncio
    async def test_fallback_when_all_risky(self):
        """When no option passes risk threshold, fallback to highest scored."""
        config = GSTConfig(risk_threshold=0.9)
        proc = GSTProcessor(config=config)
        options = [
            GSTOption(option_id="med", total_score=0.5),
            GSTOption(option_id="high", total_score=0.8),
        ]
        risk_summary = {
            "per_option": [
                {"option_id": "med", "risk_score": 0.5},
                {"option_id": "high", "risk_score": 0.3},
            ],
        }
        # Both fail: 1-0.5=0.5 < 0.9, 1-0.3=0.7 < 0.9
        result = await proc.recommend(options, risk_summary)
        assert result["selected_option"]["option_id"] == "high"
        assert "No option met the risk threshold" in result["rationale"]

    @pytest.mark.asyncio
    async def test_all_options_safe(self):
        config = GSTConfig(risk_threshold=0.0)
        proc = GSTProcessor(config=config)
        options = [
            GSTOption(option_id="opt_1", total_score=0.9),
            GSTOption(option_id="opt_2", total_score=0.7),
        ]
        risk_summary = {
            "per_option": [
                {"option_id": "opt_1", "risk_score": 0.5},
                {"option_id": "opt_2", "risk_score": 0.3},
            ],
        }
        result = await proc.recommend(options, risk_summary)
        assert result["selected_option"]["option_id"] == "opt_1"
        assert "No option met" not in result["rationale"]

    @pytest.mark.asyncio
    async def test_rationale_includes_score(self, processor):
        options = [
            GSTOption(
                option_id="opt_1",
                total_score=0.75,
                impact_scores={"customer_satisfaction": 0.9},
            ),
        ]
        risk_summary = {
            "per_option": [{"option_id": "opt_1", "risk_score": 0.1}],
        }
        result = await processor.recommend(options, risk_summary)
        assert "0.75" in result["rationale"]


# ── Full Pipeline Tests ──────────────────────────────────────────────


class TestFullPipeline:
    """Tests for the full 5-checkpoint process() method."""

    @pytest.mark.asyncio
    async def test_contract_query_pipeline(self, processor):
        result = await processor.process(
            "We need to modify our contract terms for renewal",
        )
        assert result.problem_definition != {}
        assert len(result.options) >= 2
        assert result.recommendation != {}
        assert len(result.checkpoints) == 5
        assert len(result.steps_applied) >= 4
        assert "problem_definition" in result.steps_applied

    @pytest.mark.asyncio
    async def test_feature_request_pipeline(self, processor):
        result = await processor.process(
            "Can we request a new feature for our account dashboard?",
        )
        assert result.problem_definition["scope"] == "feature_request"
        assert len(result.options) > 0

    @pytest.mark.asyncio
    async def test_policy_change_pipeline(self, processor):
        result = await processor.process(
            "We need to change our refund policy",
        )
        assert result.problem_definition["scope"] == "policy_change"
        assert result.risk_summary != {}

    @pytest.mark.asyncio
    async def test_escalation_pipeline(self, processor):
        result = await processor.process(
            "This issue needs escalation to senior management",
        )
        assert result.problem_definition["scope"] == "escalation"

    @pytest.mark.asyncio
    async def test_pricing_pipeline(self, processor):
        result = await processor.process(
            "We want to discuss pricing changes for our plan",
        )
        assert result.problem_definition["scope"] == "pricing"

    @pytest.mark.asyncio
    async def test_general_pipeline(self, processor):
        result = await processor.process(
            "How should we handle this complex situation?",
        )
        assert result.problem_definition["scope"] == "general"

    @pytest.mark.asyncio
    async def test_empty_query_pipeline(self, processor):
        result = await processor.process("")
        assert result.steps_applied == ["empty_input"]

    @pytest.mark.asyncio
    async def test_whitespace_query_pipeline(self, processor):
        result = await processor.process("   ")
        assert result.steps_applied == ["empty_input"]

    @pytest.mark.asyncio
    async def test_all_checkpoints_present(self, processor):
        result = await processor.process("Modify the contract terms")
        checkpoint_names = [cp.name for cp in result.checkpoints]
        expected = [
            "problem_definition",
            "option_generation",
            "impact_analysis",
            "risk_assessment",
            "recommendation",
        ]
        for name in expected:
            assert name in checkpoint_names

    @pytest.mark.asyncio
    async def test_checkpoint_numbers_sequential(self, processor):
        result = await processor.process("Modify the contract terms")
        numbers = [cp.checkpoint_number for cp in result.checkpoints]
        assert numbers == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_all_steps_applied(self, processor):
        result = await processor.process("Modify our contract renewal")
        expected_steps = [
            "problem_definition",
            "option_generation",
            "impact_analysis",
            "risk_assessment",
            "recommendation",
        ]
        for step in expected_steps:
            assert step in result.steps_applied

    @pytest.mark.asyncio
    async def test_to_dict_returns_dict(self, processor):
        result = await processor.process("contract modification request")
        d = result.to_dict()
        assert isinstance(d, dict)

    @pytest.mark.asyncio
    async def test_recommendation_has_selected_option(self, processor):
        result = await processor.process("We need to change the pricing")
        assert result.recommendation.get("selected_option") is not None
        assert result.recommendation["selected_option"].get("option_id") is not None

    @pytest.mark.asyncio
    async def test_risk_summary_has_structure(self, processor):
        result = await processor.process("Modify contract terms")
        assert "per_option" in result.risk_summary
        assert "overall_max_severity" in result.risk_summary
        assert "risk_categories" in result.risk_summary

    @pytest.mark.asyncio
    async def test_options_have_total_scores(self, processor):
        result = await processor.process("Feature request for dashboard")
        for opt in result.options:
            assert opt.total_score > 0.0


# ── Scope Classification Tests ───────────────────────────────────────


class TestClassifyScope:
    """Tests for the _classify_scope() utility method."""

    def test_contract_scope(self):
        assert (
            GSTProcessor._classify_scope("modify the contract terms")
            == DecisionScope.CONTRACT_MODIFICATION
        )

    def test_feature_scope(self):
        assert (
            GSTProcessor._classify_scope("request a new feature for the dashboard")
            == DecisionScope.FEATURE_REQUEST
        )

    def test_policy_scope(self):
        assert (
            GSTProcessor._classify_scope("change the refund policy")
            == DecisionScope.POLICY_CHANGE
        )

    def test_escalation_scope(self):
        assert (
            GSTProcessor._classify_scope("escalate this to management immediately")
            == DecisionScope.ESCALATION
        )

    def test_pricing_scope(self):
        assert (
            GSTProcessor._classify_scope("adjust the pricing for our plan")
            == DecisionScope.PRICING
        )

    def test_general_scope(self):
        assert (
            GSTProcessor._classify_scope("how should we handle this")
            == DecisionScope.GENERAL
        )

    def test_case_insensitive(self):
        assert (
            GSTProcessor._classify_scope("MODIFY THE CONTRACT")
            == DecisionScope.CONTRACT_MODIFICATION
        )

    def test_empty_query(self):
        assert GSTProcessor._classify_scope("") == DecisionScope.GENERAL

    def test_amendment_triggers_contract(self):
        assert (
            GSTProcessor._classify_scope("contract amendment needed")
            == DecisionScope.CONTRACT_MODIFICATION
        )

    def test_enhancement_triggers_feature(self):
        assert (
            GSTProcessor._classify_scope("enhancement request for reporting")
            == DecisionScope.FEATURE_REQUEST
        )

    def test_regulation_triggers_policy(self):
        assert (
            GSTProcessor._classify_scope("regulation requires policy update")
            == DecisionScope.POLICY_CHANGE
        )

    def test_urgent_triggers_escalation(self):
        assert (
            GSTProcessor._classify_scope("urgent priority issue")
            == DecisionScope.ESCALATION
        )

    def test_discount_triggers_pricing(self):
        assert (
            GSTProcessor._classify_scope("apply a discount to the account")
            == DecisionScope.PRICING
        )


# ── Node execute() Tests ─────────────────────────────────────────────


class TestNodeExecute:
    """Tests for GSTNode.execute()."""

    @pytest.mark.asyncio
    async def test_execute_updates_state(self, node, strategic_state):
        result = await node.execute(strategic_state)
        assert result is strategic_state
        assert TechniqueID.GST.value in result.technique_results

    @pytest.mark.asyncio
    async def test_execute_records_result(self, node, strategic_state):
        result = await node.execute(strategic_state)
        record = result.technique_results[TechniqueID.GST.value]
        assert record["status"] == "success"
        assert "result" in record

    @pytest.mark.asyncio
    async def test_execute_with_empty_query(self, node, empty_state):
        result = await node.execute(empty_state)
        assert result is empty_state

    @pytest.mark.asyncio
    async def test_execute_result_has_dict(self, node, strategic_state):
        result = await node.execute(strategic_state)
        record = result.technique_results[TechniqueID.GST.value]
        assert isinstance(record["result"], dict)

    @pytest.mark.asyncio
    async def test_execute_appends_response(self, node, strategic_state):
        result = await node.execute(strategic_state)
        assert len(result.response_parts) > 0


# ── Company Isolation Tests (BC-001) ─────────────────────────────────


class TestCompanyIsolation:
    """BC-001: Company data must be isolated."""

    def test_company_processor_has_company_id(self, company_processor):
        assert company_processor.config.company_id == "comp_456"

    def test_default_processor_no_company_id(self, processor):
        assert processor.config.company_id == ""

    def test_two_companies_independent(self):
        config1 = GSTConfig(company_id="A", max_options=1)
        config2 = GSTConfig(company_id="B", max_options=5)
        p1 = GSTProcessor(config=config1)
        p2 = GSTProcessor(config=config2)
        assert p1.config.max_options == 1
        assert p2.config.max_options == 5

    def test_node_company_config(self):
        config = GSTConfig(company_id="tenant_X")
        node = GSTNode(config=config)
        assert node._config.company_id == "tenant_X"

    def test_configs_not_shared(self):
        c1 = GSTConfig(company_id="A")
        c2 = GSTConfig(company_id="B")
        assert c1.company_id != c2.company_id

    def test_different_risk_thresholds(self):
        config1 = GSTConfig(company_id="A", risk_threshold=0.3)
        config2 = GSTConfig(company_id="B", risk_threshold=0.9)
        assert config1.risk_threshold != config2.risk_threshold


# ── Error Fallback Tests (BC-008) ─────────────────────────────────────


class TestErrorFallback:
    """BC-008: Never crash — return original state on error."""

    @pytest.mark.asyncio
    async def test_execute_returns_original_on_exception(self, node, strategic_state):
        """Force an exception inside execute() and verify original state returned."""
        with patch.object(
            node._processor,
            "process",
            side_effect=RuntimeError("boom"),
        ):
            result = await node.execute(strategic_state)
            assert result is strategic_state

    @pytest.mark.asyncio
    async def test_process_returns_fallback_on_internal_error(self, processor):
        """Force an exception inside process() pipeline."""
        with patch.object(
            processor,
            "define_problem",
            side_effect=RuntimeError("pipeline error"),
        ):
            result = await processor.process("strategic query")
            assert "error_fallback" in result.steps_applied

    @pytest.mark.asyncio
    async def test_processor_error_logs_warning(self, processor):
        """Error should be logged as warning, not crash."""
        with patch.object(
            processor,
            "define_problem",
            side_effect=ValueError("error"),
        ):
            result = await processor.process("test query")
            assert isinstance(result, GSTResult)

    @pytest.mark.asyncio
    async def test_error_in_option_generation(self, processor):
        with patch.object(
            processor,
            "generate_options",
            side_effect=Exception("option gen fail"),
        ):
            result = await processor.process("strategic decision")
            assert isinstance(result, GSTResult)
            assert "error_fallback" in result.steps_applied

    @pytest.mark.asyncio
    async def test_error_in_impact_analysis(self, processor):
        with patch.object(
            processor,
            "analyze_impact",
            side_effect=Exception("impact fail"),
        ):
            result = await processor.process("modify contract")
            assert isinstance(result, GSTResult)

    @pytest.mark.asyncio
    async def test_error_in_risk_assessment(self, processor):
        with patch.object(
            processor,
            "assess_risks",
            side_effect=Exception("risk fail"),
        ):
            result = await processor.process("modify contract")
            assert isinstance(result, GSTResult)


# ── Edge Cases ───────────────────────────────────────────────────────


class TestEdgeCases:
    """Additional edge cases for robustness."""

    @pytest.mark.asyncio
    async def test_very_long_query(self, processor):
        """Very long query should be processed without crash."""
        query = "contract modification " * 500
        result = await processor.process(query)
        assert isinstance(result, GSTResult)

    @pytest.mark.asyncio
    async def test_special_characters(self, processor):
        """Special characters should not crash the processor."""
        query = "Modify contract #INV-2024-001! Price change? <test>"
        result = await processor.process(query)
        assert result.problem_definition != {}

    @pytest.mark.asyncio
    async def test_unicode_characters(self, processor):
        """Unicode characters should not crash."""
        query = "Contrat modification request — über pricing émoji"
        result = await processor.process(query)
        assert isinstance(result, GSTResult)

    @pytest.mark.asyncio
    async def test_single_word_query(self, processor):
        result = await processor.process("contract")
        assert isinstance(result, GSTResult)
        assert result.problem_definition["scope"] == "contract_modification"

    @pytest.mark.asyncio
    async def test_numeric_query(self, processor):
        result = await processor.process("12345")
        assert isinstance(result, GSTResult)

    @pytest.mark.asyncio
    async def test_none_like_empty(self, processor):
        """Empty/whitespace should produce empty_input."""
        result = await processor.process("\t\n")
        assert result.steps_applied == ["empty_input"]

    @pytest.mark.asyncio
    async def test_concurrent_processing(self, processor):
        """Two concurrent process calls should not interfere."""
        import asyncio

        r1, r2 = await asyncio.gather(
            processor.process("modify contract"),
            processor.process("change pricing"),
        )
        assert isinstance(r1, GSTResult)
        assert isinstance(r2, GSTResult)
        assert r1.problem_definition["scope"] == "contract_modification"
        assert r2.problem_definition["scope"] == "pricing"


# ── Scope Templates Data Integrity Tests ──────────────────────────────


class TestScopeTemplateIntegrity:
    """Verify that all scope templates have required structure."""

    def test_all_scopes_have_options(self):
        for scope in DecisionScope:
            assert scope in _SCOPE_OPTIONS, f"Missing options for {scope}"

    def test_all_scopes_have_stakeholders(self):
        for scope in DecisionScope:
            assert scope in _SCOPE_STAKEHOLDERS, f"Missing stakeholders for {scope}"
            assert len(_SCOPE_STAKEHOLDERS[scope]) > 0

    def test_all_scopes_have_constraints(self):
        for scope in DecisionScope:
            assert scope in _SCOPE_CONSTRAINTS, f"Missing constraints for {scope}"
            assert len(_SCOPE_CONSTRAINTS[scope]) > 0

    def test_options_have_required_fields(self):
        for scope, templates in _SCOPE_OPTIONS.items():
            for tmpl in templates:
                assert "description" in tmpl
                assert "base_scores" in tmpl
                assert "risks" in tmpl
                for dim in (
                    "customer_satisfaction",
                    "cost_impact",
                    "policy_compliance",
                    "implementation_feasibility",
                ):
                    assert dim in tmpl["base_scores"], f"Missing {dim} for {scope}"

    def test_option_scores_in_range(self):
        for scope, templates in _SCOPE_OPTIONS.items():
            for tmpl in templates:
                for dim, score in tmpl["base_scores"].items():
                    assert (
                        0.0 <= score <= 1.0
                    ), f"{scope}: {dim} score {score} out of range"

    def test_risks_have_required_fields(self):
        for scope, templates in _SCOPE_OPTIONS.items():
            for tmpl in templates:
                for risk in tmpl["risks"]:
                    assert "category" in risk
                    assert "severity" in risk

    def test_minimum_options_per_scope(self):
        for scope, templates in _SCOPE_OPTIONS.items():
            assert (
                len(templates) >= 2
            ), f"Scope {scope} has only {len(templates)} options (need >= 2)"

    def test_default_weights_sum(self):
        total = sum(_DEFAULT_WEIGHTS.values())
        assert total == pytest.approx(1.0)
