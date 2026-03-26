"""
Tests for Cross-Client Validation System.

CRITICAL: All tests verify privacy guarantees:
- All 5 clients validate
- Each client shows improvement
- No client regresses
- Collective intelligence helps
- Industry benchmarks met
"""

import pytest
from datetime import datetime
from typing import Dict

from validation.cross_client_validator import (
    CrossClientValidator,
    ValidationResult,
    ClientValidationResult,
    ValidationStatus,
    ClientStatus,
    validate_all_clients,
)
from validation.per_client_accuracy import (
    PerClientAccuracy,
    ClientMetrics,
    calculate_client_accuracy,
)
from validation.industry_benchmarks import (
    IndustryBenchmarks,
    IndustryBenchmarkSet,
    IndustryStandard,
    IndustryType,
    get_industry_benchmark,
)
from validation.improvement_tracker import (
    ImprovementTracker,
    ImprovementRecord,
    MilestoneStatus,
    TrendDirection,
    track_improvement,
)


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def validator() -> CrossClientValidator:
    """Create a cross-client validator"""
    return CrossClientValidator()


@pytest.fixture
def accuracy_tracker() -> PerClientAccuracy:
    """Create a per-client accuracy tracker"""
    return PerClientAccuracy()


@pytest.fixture
def improvement_tracker() -> ImprovementTracker:
    """Create an improvement tracker"""
    return ImprovementTracker()


@pytest.fixture
def industry_benchmarks() -> IndustryBenchmarks:
    """Create industry benchmarks"""
    return IndustryBenchmarks()


@pytest.fixture
def sample_client_accuracies() -> Dict[str, float]:
    """Sample accuracies for all 5 clients (all improved and meet target)"""
    return {
        "client_001": 0.78,  # E-commerce: 6% improvement
        "client_002": 0.79,  # SaaS: 7% improvement
        "client_003": 0.77,  # Healthcare: 5% improvement
        "client_004": 0.77,  # Logistics: 5% improvement
        "client_005": 0.78,  # FinTech: 6% improvement
    }


# ==============================================================================
# Cross-Client Validator Tests
# ==============================================================================

class TestCrossClientValidator:
    """Tests for CrossClientValidator"""

    def test_validator_initialization(self, validator):
        """Test validator initializes correctly"""
        assert validator.baseline_accuracy == 0.72
        assert validator.target_accuracy == 0.77
        assert validator.min_improvement == 0.05

    def test_validate_client_success(self, validator):
        """Test validating a single client"""
        result = validator.validate_client("client_001", 0.78)

        assert result.client_id == "client_001"
        assert result.industry == "ecommerce"
        assert result.current_accuracy == 0.78
        assert result.baseline_accuracy == 0.72
        assert result.status == ClientStatus.IMPROVED

    def test_validate_client_regressed(self, validator):
        """Test detecting a regressed client"""
        result = validator.validate_client("client_001", 0.68)

        assert result.current_accuracy < result.baseline_accuracy
        assert result.status == ClientStatus.REGRESSED

    def test_validate_client_unchanged(self, validator):
        """Test detecting unchanged client"""
        result = validator.validate_client("client_001", 0.72)

        assert result.status == ClientStatus.UNCHANGED

    def test_validate_all_clients_success(self, validator, sample_client_accuracies):
        """Test validating all clients successfully"""
        result = validator.validate_all_clients(sample_client_accuracies)

        assert result.total_clients == 5
        assert result.regressed_clients == 0
        assert result.improved_clients == 5
        assert result.status == ValidationStatus.PASSED
        assert result.meets_requirements is True

    def test_validate_all_clients_with_regression(self, validator):
        """Test validation fails when a client regresses"""
        accuracies = {
            "client_001": 0.78,
            "client_002": 0.79,
            "client_003": 0.68,  # Regressed!
            "client_004": 0.76,
            "client_005": 0.78,
        }

        result = validator.validate_all_clients(accuracies)

        assert result.regressed_clients == 1
        assert result.status == ValidationStatus.FAILED
        assert result.meets_requirements is False

    def test_validate_missing_client_raises_error(self, validator):
        """Test that missing clients raise error"""
        accuracies = {
            "client_001": 0.78,
            "client_002": 0.79,
            # Missing client_003, client_004, client_005
        }

        with pytest.raises(ValueError, match="Missing clients"):
            validator.validate_all_clients(accuracies)

    def test_no_client_data_in_output(self, validator, sample_client_accuracies):
        """CRITICAL: Verify no client-specific data in output"""
        result = validator.validate_all_clients(sample_client_accuracies)
        result_dict = result.to_dict()

        # Check that results don't contain sensitive data
        result_str = str(result_dict).lower()

        # No customer data patterns
        assert "email" not in result_str
        assert "phone" not in result_str
        assert "ssn" not in result_str
        assert "patient" not in result_str

    def test_check_requirements_met(self, validator, sample_client_accuracies):
        """Test requirement checking"""
        result = validator.validate_all_clients(sample_client_accuracies)
        requirements = validator.check_requirements_met(result)

        assert requirements["all_clients_improved"] is True
        assert requirements["no_client_regressed"] is True
        assert requirements["average_improvement_met"] is True
        assert requirements["all_requirements_met"] is True

    def test_validation_history(self, validator, sample_client_accuracies):
        """Test validation history is tracked"""
        validator.validate_all_clients(sample_client_accuracies)

        history = validator.get_validation_history()
        assert len(history) == 1

        latest = validator.get_latest_validation()
        assert latest is not None


class TestValidateAllClientsFunction:
    """Tests for convenience function"""

    def test_validate_all_clients_function(self, sample_client_accuracies):
        """Test the convenience validation function"""
        result = validate_all_clients(sample_client_accuracies)

        assert isinstance(result, ValidationResult)
        assert result.total_clients == 5


# ==============================================================================
# Per-Client Accuracy Tests
# ==============================================================================

class TestPerClientAccuracy:
    """Tests for PerClientAccuracy"""

    def test_tracker_initialization(self, accuracy_tracker):
        """Test tracker initializes correctly"""
        assert len(accuracy_tracker.CLIENT_CONFIGS) == 5

    def test_calculate_metrics_success(self, accuracy_tracker):
        """Test calculating client metrics"""
        metrics = accuracy_tracker.calculate_metrics(
            client_id="client_001",
            resolution_rate=0.80,
            first_contact_resolution=0.70,
            escalation_rate=0.10,
            customer_satisfaction=0.85,
            response_quality=0.82,
            faq_match_rate=0.88,
            total_tickets=1000,
            total_resolved=800,
            total_escalated=100,
            avg_response_time_ms=250.0,
        )

        assert metrics.client_id == "client_001"
        assert metrics.industry == "ecommerce"
        assert metrics.overall_accuracy > 0
        assert metrics.improvement_percentage > 0

    def test_calculate_metrics_healthcare_client(self, accuracy_tracker):
        """Test healthcare client with HIPAA compliance"""
        metrics = accuracy_tracker.calculate_metrics(
            client_id="client_003",
            resolution_rate=0.78,
            first_contact_resolution=0.68,
            escalation_rate=0.12,
            customer_satisfaction=0.82,
            response_quality=0.85,
            faq_match_rate=0.80,
            total_tickets=500,
            total_resolved=390,
            total_escalated=60,
            avg_response_time_ms=300.0,
        )

        assert metrics.industry == "healthcare"
        assert metrics.hipaa_compliant is True

    def test_calculate_metrics_fintech_client(self, accuracy_tracker):
        """Test fintech client with PCI DSS compliance"""
        metrics = accuracy_tracker.calculate_metrics(
            client_id="client_005",
            resolution_rate=0.82,
            first_contact_resolution=0.75,
            escalation_rate=0.08,
            customer_satisfaction=0.88,
            response_quality=0.86,
            faq_match_rate=0.85,
            total_tickets=800,
            total_resolved=656,
            total_escalated=64,
            avg_response_time_ms=200.0,
        )

        assert metrics.industry == "fintech"
        assert metrics.pci_dss_compliant is True

    def test_get_client_metrics(self, accuracy_tracker):
        """Test retrieving client metrics"""
        accuracy_tracker.calculate_metrics(
            client_id="client_001",
            resolution_rate=0.80,
            first_contact_resolution=0.70,
            escalation_rate=0.10,
            customer_satisfaction=0.85,
            response_quality=0.82,
            faq_match_rate=0.88,
            total_tickets=1000,
            total_resolved=800,
            total_escalated=100,
            avg_response_time_ms=250.0,
        )

        metrics = accuracy_tracker.get_client_metrics("client_001")
        assert metrics is not None
        assert metrics.client_id == "client_001"

    def test_get_all_client_metrics(self, accuracy_tracker):
        """Test retrieving all client metrics"""
        all_metrics = accuracy_tracker.get_all_client_metrics()
        assert len(all_metrics) == 5

    def test_compare_to_industry_baseline(self, accuracy_tracker):
        """Test comparing to industry baseline"""
        metrics = accuracy_tracker.calculate_metrics(
            client_id="client_001",
            resolution_rate=0.80,
            first_contact_resolution=0.70,
            escalation_rate=0.10,
            customer_satisfaction=0.85,
            response_quality=0.82,
            faq_match_rate=0.88,
            total_tickets=1000,
            total_resolved=800,
            total_escalated=100,
            avg_response_time_ms=250.0,
        )

        comparison = accuracy_tracker.compare_to_industry_baseline(metrics)

        assert "resolution_rate" in comparison
        assert "baseline" in comparison["resolution_rate"]
        assert "current" in comparison["resolution_rate"]

    def test_improvement_trend_tracking(self, accuracy_tracker):
        """Test improvement trend detection"""
        # First measurement
        accuracy_tracker.calculate_metrics(
            client_id="client_001",
            resolution_rate=0.75,
            first_contact_resolution=0.65,
            escalation_rate=0.15,
            customer_satisfaction=0.80,
            response_quality=0.78,
            faq_match_rate=0.82,
            total_tickets=500,
            total_resolved=375,
            total_escalated=75,
            avg_response_time_ms=300.0,
        )

        # Second measurement (improved)
        metrics = accuracy_tracker.calculate_metrics(
            client_id="client_001",
            resolution_rate=0.80,
            first_contact_resolution=0.70,
            escalation_rate=0.10,
            customer_satisfaction=0.85,
            response_quality=0.82,
            faq_match_rate=0.88,
            total_tickets=1000,
            total_resolved=800,
            total_escalated=100,
            avg_response_time_ms=250.0,
        )

        assert metrics.improvement_trend == "improving"

    def test_invalid_client_raises_error(self, accuracy_tracker):
        """Test that invalid client raises error"""
        with pytest.raises(ValueError, match="Unknown client"):
            accuracy_tracker.calculate_metrics(
                client_id="invalid_client",
                resolution_rate=0.80,
                first_contact_resolution=0.70,
                escalation_rate=0.10,
                customer_satisfaction=0.85,
                response_quality=0.82,
                faq_match_rate=0.88,
                total_tickets=1000,
                total_resolved=800,
                total_escalated=100,
                avg_response_time_ms=250.0,
            )


class TestCalculateClientAccuracyFunction:
    """Tests for convenience function"""

    def test_calculate_client_accuracy_function(self):
        """Test the convenience accuracy function"""
        metrics = calculate_client_accuracy(
            client_id="client_001",
            resolution_rate=0.80,
            first_contact_resolution=0.70,
            escalation_rate=0.10,
            customer_satisfaction=0.85,
            response_quality=0.82,
            faq_match_rate=0.88,
            total_tickets=1000,
            total_resolved=800,
            total_escalated=100,
            avg_response_time_ms=250.0,
        )

        assert isinstance(metrics, ClientMetrics)
        assert metrics.client_id == "client_001"


# ==============================================================================
# Industry Benchmarks Tests
# ==============================================================================

class TestIndustryBenchmarks:
    """Tests for IndustryBenchmarks"""

    def test_benchmarks_initialization(self, industry_benchmarks):
        """Test benchmarks initializes correctly"""
        assert len(industry_benchmarks._benchmarks) == 5

    def test_get_ecommerce_benchmark(self, industry_benchmarks):
        """Test getting e-commerce benchmark"""
        benchmark = industry_benchmarks.get_benchmark(IndustryType.ECOMMERCE)

        assert benchmark is not None
        assert benchmark.industry == IndustryType.ECOMMERCE
        assert "resolution_rate" in benchmark.standards

    def test_get_healthcare_benchmark(self, industry_benchmarks):
        """Test getting healthcare benchmark with HIPAA"""
        benchmark = industry_benchmarks.get_benchmark(IndustryType.HEALTHCARE)

        assert benchmark is not None
        assert "HIPAA" in benchmark.compliance_requirements

    def test_get_fintech_benchmark(self, industry_benchmarks):
        """Test getting fintech benchmark with PCI DSS"""
        benchmark = industry_benchmarks.get_benchmark(IndustryType.FINTECH)

        assert benchmark is not None
        assert "PCI_DSS" in benchmark.compliance_requirements

    def test_evaluate_against_industry(self, industry_benchmarks):
        """Test evaluating metrics against industry"""
        metrics = {
            "resolution_rate": 0.80,
            "first_contact_resolution": 0.70,
            "customer_satisfaction": 0.85,
            "response_quality": 0.82,
            "faq_match_rate": 0.88,
        }

        result = industry_benchmarks.evaluate_against_industry(
            IndustryType.ECOMMERCE,
            metrics
        )

        assert "evaluations" in result
        assert "overall_score" in result
        assert result["metrics_evaluated"] == 5

    def test_industry_standard_evaluation(self, industry_benchmarks):
        """Test individual standard evaluation"""
        benchmark = industry_benchmarks.get_benchmark(IndustryType.ECOMMERCE)
        standard = benchmark.standards["resolution_rate"]

        eval_result = standard.evaluate(0.80)

        assert eval_result["actual"] == 0.80
        assert eval_result["rating"] in ["poor", "below_average", "average", "good", "excellent"]
        assert "percentile" in eval_result

    def test_compare_industries(self, industry_benchmarks):
        """Test comparing across industries"""
        industry_metrics = {
            IndustryType.ECOMMERCE: {
                "resolution_rate": 0.80,
                "first_contact_resolution": 0.70,
                "customer_satisfaction": 0.85,
                "response_quality": 0.82,
                "faq_match_rate": 0.88,
            },
            IndustryType.SAAS: {
                "resolution_rate": 0.82,
                "first_contact_resolution": 0.72,
                "customer_satisfaction": 0.87,
                "response_quality": 0.85,
                "faq_match_rate": 0.90,
            },
        }

        result = industry_benchmarks.compare_industries(industry_metrics)

        assert "industry_comparisons" in result
        assert "cross_industry_average" in result
        assert "top_performing_industry" in result


class TestGetIndustryBenchmarkFunction:
    """Tests for convenience function"""

    def test_get_industry_benchmark_valid(self):
        """Test getting benchmark with valid industry"""
        benchmark = get_industry_benchmark("ecommerce")

        assert benchmark is not None
        assert benchmark.industry == IndustryType.ECOMMERCE

    def test_get_industry_benchmark_invalid(self):
        """Test getting benchmark with invalid industry"""
        benchmark = get_industry_benchmark("invalid_industry")

        assert benchmark is None


# ==============================================================================
# Improvement Tracker Tests
# ==============================================================================

class TestImprovementTracker:
    """Tests for ImprovementTracker"""

    def test_tracker_initialization(self, improvement_tracker):
        """Test tracker initializes correctly"""
        assert improvement_tracker.baseline_accuracy == 0.72
        assert improvement_tracker.target_accuracy == 0.77

    def test_record_improvement(self, improvement_tracker):
        """Test recording improvement"""
        record = improvement_tracker.record_improvement(
            current_accuracy=0.77,
            week=22,
            phase=6,
            clients_improved=5,
            clients_total=5,
            training_runs=1,
            collective_intelligence_active=True,
        )

        assert record.current_accuracy == 0.77
        assert record.improvement_percentage > 0
        assert record.clients_improved == 5
        assert record.trend in [TrendDirection.UP, TrendDirection.STABLE]

    def test_improvement_trend_calculation(self, improvement_tracker):
        """Test improvement trend calculation"""
        # First record
        improvement_tracker.record_improvement(
            current_accuracy=0.74,
            week=20,
            phase=6,
            clients_improved=3,
            clients_total=5,
        )

        # Second record (improved)
        record = improvement_tracker.record_improvement(
            current_accuracy=0.77,
            week=22,
            phase=6,
            clients_improved=5,
            clients_total=5,
        )

        assert record.trend == TrendDirection.UP

    def test_milestone_tracking(self, improvement_tracker):
        """Test milestone progress tracking"""
        improvement_tracker.record_improvement(
            current_accuracy=0.77,
            week=22,
            phase=6,
            clients_improved=5,
            clients_total=5,
        )

        progress = improvement_tracker.get_milestone_progress()

        assert "milestones" in progress
        assert "current_milestone" in progress
        assert "overall_progress_pct" in progress

    def test_generate_report(self, improvement_tracker):
        """Test report generation"""
        improvement_tracker.record_improvement(
            current_accuracy=0.77,
            week=22,
            phase=6,
            clients_improved=5,
            clients_total=5,
            training_runs=2,
            collective_intelligence_active=True,
        )

        report = improvement_tracker.generate_report()

        assert "summary" in report
        assert "trend_analysis" in report
        assert "client_summary" in report
        assert "milestone_progress" in report
        assert "recommendations" in report

    def test_target_achievement_detection(self, improvement_tracker):
        """Test detecting target achievement"""
        record = improvement_tracker.record_improvement(
            current_accuracy=0.77,
            week=22,
            phase=6,
            clients_improved=5,
            clients_total=5,
        )

        report = improvement_tracker.generate_report()

        assert report["summary"]["meets_target"] is True

    def test_velocity_calculation(self, improvement_tracker):
        """Test improvement velocity calculation"""
        record = improvement_tracker.record_improvement(
            current_accuracy=0.77,
            week=22,
            phase=6,
            clients_improved=5,
            clients_total=5,
        )

        # Velocity should be (0.77 - 0.72) / (22 - 19) = 0.0167 per week
        assert record.velocity > 0

    def test_recommendations_generation(self, improvement_tracker):
        """Test recommendation generation"""
        # Record below target
        improvement_tracker.record_improvement(
            current_accuracy=0.74,
            week=21,
            phase=6,
            clients_improved=3,
            clients_total=5,
            collective_intelligence_active=False,
        )

        report = improvement_tracker.generate_report()

        # Should have recommendations for improvement
        assert len(report["recommendations"]) > 0

    def test_improvement_history(self, improvement_tracker):
        """Test improvement history tracking"""
        improvement_tracker.record_improvement(
            current_accuracy=0.74,
            week=20,
            phase=6,
            clients_improved=3,
            clients_total=5,
        )

        improvement_tracker.record_improvement(
            current_accuracy=0.77,
            week=22,
            phase=6,
            clients_improved=5,
            clients_total=5,
        )

        history = improvement_tracker.get_improvement_history()

        assert len(history) == 2
        assert history[0].current_accuracy == 0.74
        assert history[1].current_accuracy == 0.77


class TestTrackImprovementFunction:
    """Tests for convenience function"""

    def test_track_improvement_function(self):
        """Test the convenience tracking function"""
        record = track_improvement(
            current_accuracy=0.77,
            week=22,
            phase=6,
            clients_improved=5,
            clients_total=5,
        )

        assert isinstance(record, ImprovementRecord)
        assert record.current_accuracy == 0.77


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestValidationIntegration:
    """Integration tests for complete validation workflow"""

    def test_full_validation_workflow(
        self,
        validator,
        accuracy_tracker,
        improvement_tracker,
        industry_benchmarks,
    ):
        """Test complete validation workflow"""
        # 1. Calculate metrics for each client
        client_accuracies = {}
        all_metrics = []

        for client_id in ["client_001", "client_002", "client_003", "client_004", "client_005"]:
            metrics = accuracy_tracker.calculate_metrics(
                client_id=client_id,
                resolution_rate=0.80,
                first_contact_resolution=0.70,
                escalation_rate=0.10,
                customer_satisfaction=0.85,
                response_quality=0.82,
                faq_match_rate=0.88,
                total_tickets=1000,
                total_resolved=800,
                total_escalated=100,
                avg_response_time_ms=250.0,
            )
            client_accuracies[client_id] = metrics.overall_accuracy
            all_metrics.append(metrics)

        # 2. Validate across all clients
        validation_result = validator.validate_all_clients(client_accuracies)

        assert validation_result.total_clients == 5
        assert validation_result.regressed_clients == 0

        # 3. Check industry benchmarks
        for metrics in all_metrics:
            benchmark_result = industry_benchmarks.evaluate_against_industry(
                IndustryType(metrics.industry),
                {
                    "resolution_rate": metrics.resolution_rate,
                    "first_contact_resolution": metrics.first_contact_resolution,
                    "customer_satisfaction": metrics.customer_satisfaction,
                    "response_quality": metrics.response_quality,
                    "faq_match_rate": metrics.faq_match_rate,
                }
            )
            assert benchmark_result["metrics_evaluated"] > 0

        # 4. Track improvement
        avg_accuracy = sum(client_accuracies.values()) / len(client_accuracies)
        improvement_record = improvement_tracker.record_improvement(
            current_accuracy=avg_accuracy,
            week=22,
            phase=6,
            clients_improved=validation_result.improved_clients,
            clients_total=validation_result.total_clients,
        )

        assert improvement_record.current_accuracy > 0

        # 5. Generate final report
        report = improvement_tracker.generate_report()
        assert "summary" in report

    def test_privacy_guarantees_across_workflow(
        self,
        validator,
        accuracy_tracker,
    ):
        """CRITICAL: Verify privacy throughout workflow"""
        # Calculate metrics
        metrics = accuracy_tracker.calculate_metrics(
            client_id="client_001",
            resolution_rate=0.80,
            first_contact_resolution=0.70,
            escalation_rate=0.10,
            customer_satisfaction=0.85,
            response_quality=0.82,
            faq_match_rate=0.88,
            total_tickets=1000,
            total_resolved=800,
            total_escalated=100,
            avg_response_time_ms=250.0,
        )

        # Validate
        result = validator.validate_all_clients({
            "client_001": 0.78,
            "client_002": 0.79,
            "client_003": 0.77,
            "client_004": 0.76,
            "client_005": 0.78,
        })

        # Check for sensitive data
        metrics_str = str(metrics.to_dict()).lower()
        validation_str = str(result.to_dict()).lower()

        # No sensitive patterns
        sensitive_patterns = [
            "email", "phone", "ssn", "credit_card",
            "password", "patient_id", "medical_record",
            "home_address", "social_security"
        ]

        for pattern in sensitive_patterns:
            assert pattern not in metrics_str, f"Found {pattern} in metrics"
            assert pattern not in validation_str, f"Found {pattern} in validation"


# ==============================================================================
# Run Tests
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
