"""
Industry Benchmarks - Industry-specific accuracy benchmarks.

CRITICAL: Provides industry-specific benchmarks for accuracy comparison.
Benchmarks are based on industry standards and best practices.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IndustryType(Enum):
    """Supported industries"""
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    HEALTHCARE = "healthcare"
    LOGISTICS = "logistics"
    FINTECH = "fintech"


@dataclass
class IndustryStandard:
    """
    Industry standard benchmark for a metric.
    
    Contains target, minimum, and excellent levels for comparison.
    """
    metric_name: str
    industry: IndustryType
    minimum_acceptable: float  # Minimum acceptable level
    industry_average: float    # Industry average
    best_in_class: float       # Best in class performance
    target: float              # PARWA target
    weight: float              # Weight in overall score
    
    def evaluate(self, actual: float) -> Dict[str, Any]:
        """
        Evaluate actual performance against benchmark.

        Args:
            actual: Actual metric value

        Returns:
            Evaluation result
        """
        if actual >= self.best_in_class:
            rating = "excellent"
            percentile = 95
        elif actual >= self.target:
            rating = "good"
            percentile = 85
        elif actual >= self.industry_average:
            rating = "average"
            percentile = 50
        elif actual >= self.minimum_acceptable:
            rating = "below_average"
            percentile = 25
        else:
            rating = "poor"
            percentile = 10

        return {
            "metric_name": self.metric_name,
            "actual": actual,
            "minimum_acceptable": self.minimum_acceptable,
            "industry_average": self.industry_average,
            "best_in_class": self.best_in_class,
            "target": self.target,
            "rating": rating,
            "percentile": percentile,
            "meets_minimum": actual >= self.minimum_acceptable,
            "meets_target": actual >= self.target,
        }


@dataclass
class IndustryBenchmarkSet:
    """
    Complete benchmark set for an industry.
    """
    industry: IndustryType
    standards: Dict[str, IndustryStandard]
    description: str
    compliance_requirements: List[str] = field(default_factory=list)

    def evaluate_all(
        self,
        metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Evaluate all metrics against benchmarks.

        Args:
            metrics: Dict of metric_name -> actual value

        Returns:
            Complete evaluation results
        """
        evaluations = {}
        weighted_score = 0.0
        total_weight = 0.0

        for metric_name, actual in metrics.items():
            if metric_name in self.standards:
                standard = self.standards[metric_name]
                eval_result = standard.evaluate(actual)
                evaluations[metric_name] = eval_result

                # Calculate weighted score
                weighted_score += actual * standard.weight
                total_weight += standard.weight

        # Calculate overall industry percentile
        if total_weight > 0:
            overall = weighted_score / total_weight
        else:
            overall = 0.0

        return {
            "industry": self.industry.value,
            "description": self.description,
            "compliance_requirements": self.compliance_requirements,
            "evaluations": evaluations,
            "overall_score": overall,
            "metrics_evaluated": len(evaluations),
            "metrics_passed_minimum": sum(
                1 for e in evaluations.values() if e["meets_minimum"]
            ),
            "metrics_met_target": sum(
                1 for e in evaluations.values() if e["meets_target"]
            ),
        }


class IndustryBenchmarks:
    """
    Industry-specific benchmarks for accuracy comparison.

    Provides benchmarks for all 5 supported industries:
    - E-commerce
    - SaaS
    - Healthcare (with HIPAA requirements)
    - Logistics
    - FinTech (with PCI DSS requirements)
    """

    def __init__(self):
        """Initialize industry benchmarks"""
        self._benchmarks = self._load_benchmarks()

    def get_benchmark(
        self,
        industry: IndustryType
    ) -> IndustryBenchmarkSet:
        """
        Get benchmark set for an industry.

        Args:
            industry: Industry type

        Returns:
            IndustryBenchmarkSet for the industry
        """
        return self._benchmarks.get(industry)

    def evaluate_against_industry(
        self,
        industry: IndustryType,
        metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Evaluate metrics against industry benchmarks.

        Args:
            industry: Industry type
            metrics: Dict of metric_name -> actual value

        Returns:
            Complete evaluation results
        """
        benchmark = self.get_benchmark(industry)
        if not benchmark:
            raise ValueError(f"No benchmarks for industry: {industry}")

        return benchmark.evaluate_all(metrics)

    def compare_industries(
        self,
        industry_metrics: Dict[IndustryType, Dict[str, float]]
    ) -> Dict[str, Any]:
        """
        Compare performance across industries.

        CRITICAL: Only compares aggregated metrics, no client data.

        Args:
            industry_metrics: Dict of industry -> metrics

        Returns:
            Cross-industry comparison
        """
        comparisons = {}

        for industry, metrics in industry_metrics.items():
            comparison = self.evaluate_against_industry(industry, metrics)
            comparisons[industry.value] = comparison

        # Calculate cross-industry averages
        avg_scores = []
        for comp in comparisons.values():
            avg_scores.append(comp["overall_score"])

        return {
            "industry_comparisons": comparisons,
            "cross_industry_average": sum(avg_scores) / len(avg_scores) if avg_scores else 0,
            "top_performing_industry": max(
                comparisons.keys(),
                key=lambda k: comparisons[k]["overall_score"]
            ) if comparisons else None,
        }

    def _load_benchmarks(self) -> Dict[IndustryType, IndustryBenchmarkSet]:
        """Load all industry benchmarks"""
        return {
            IndustryType.ECOMMERCE: self._create_ecommerce_benchmark(),
            IndustryType.SAAS: self._create_saas_benchmark(),
            IndustryType.HEALTHCARE: self._create_healthcare_benchmark(),
            IndustryType.LOGISTICS: self._create_logistics_benchmark(),
            IndustryType.FINTECH: self._create_fintech_benchmark(),
        }

    def _create_ecommerce_benchmark(self) -> IndustryBenchmarkSet:
        """Create e-commerce industry benchmarks"""
        return IndustryBenchmarkSet(
            industry=IndustryType.ECOMMERCE,
            description="E-commerce customer support benchmarks",
            compliance_requirements=["GDPR", "CCPA"],
            standards={
                "resolution_rate": IndustryStandard(
                    metric_name="resolution_rate",
                    industry=IndustryType.ECOMMERCE,
                    minimum_acceptable=0.60,
                    industry_average=0.72,
                    best_in_class=0.88,
                    target=0.80,
                    weight=0.30,
                ),
                "first_contact_resolution": IndustryStandard(
                    metric_name="first_contact_resolution",
                    industry=IndustryType.ECOMMERCE,
                    minimum_acceptable=0.50,
                    industry_average=0.65,
                    best_in_class=0.82,
                    target=0.75,
                    weight=0.20,
                ),
                "customer_satisfaction": IndustryStandard(
                    metric_name="customer_satisfaction",
                    industry=IndustryType.ECOMMERCE,
                    minimum_acceptable=0.70,
                    industry_average=0.78,
                    best_in_class=0.92,
                    target=0.85,
                    weight=0.25,
                ),
                "response_quality": IndustryStandard(
                    metric_name="response_quality",
                    industry=IndustryType.ECOMMERCE,
                    minimum_acceptable=0.65,
                    industry_average=0.75,
                    best_in_class=0.90,
                    target=0.82,
                    weight=0.15,
                ),
                "faq_match_rate": IndustryStandard(
                    metric_name="faq_match_rate",
                    industry=IndustryType.ECOMMERCE,
                    minimum_acceptable=0.70,
                    industry_average=0.80,
                    best_in_class=0.95,
                    target=0.88,
                    weight=0.10,
                ),
            },
        )

    def _create_saas_benchmark(self) -> IndustryBenchmarkSet:
        """Create SaaS industry benchmarks"""
        return IndustryBenchmarkSet(
            industry=IndustryType.SAAS,
            description="SaaS customer support benchmarks",
            compliance_requirements=["SOC2", "GDPR"],
            standards={
                "resolution_rate": IndustryStandard(
                    metric_name="resolution_rate",
                    industry=IndustryType.SAAS,
                    minimum_acceptable=0.65,
                    industry_average=0.75,
                    best_in_class=0.90,
                    target=0.82,
                    weight=0.25,
                ),
                "first_contact_resolution": IndustryStandard(
                    metric_name="first_contact_resolution",
                    industry=IndustryType.SAAS,
                    minimum_acceptable=0.55,
                    industry_average=0.68,
                    best_in_class=0.85,
                    target=0.78,
                    weight=0.20,
                ),
                "customer_satisfaction": IndustryStandard(
                    metric_name="customer_satisfaction",
                    industry=IndustryType.SAAS,
                    minimum_acceptable=0.72,
                    industry_average=0.80,
                    best_in_class=0.94,
                    target=0.87,
                    weight=0.20,
                ),
                "response_quality": IndustryStandard(
                    metric_name="response_quality",
                    industry=IndustryType.SAAS,
                    minimum_acceptable=0.68,
                    industry_average=0.78,
                    best_in_class=0.92,
                    target=0.85,
                    weight=0.20,
                ),
                "faq_match_rate": IndustryStandard(
                    metric_name="faq_match_rate",
                    industry=IndustryType.SAAS,
                    minimum_acceptable=0.72,
                    industry_average=0.82,
                    best_in_class=0.96,
                    target=0.88,
                    weight=0.15,
                ),
            },
        )

    def _create_healthcare_benchmark(self) -> IndustryBenchmarkSet:
        """Create healthcare industry benchmarks with HIPAA"""
        return IndustryBenchmarkSet(
            industry=IndustryType.HEALTHCARE,
            description="Healthcare customer support benchmarks (HIPAA compliant)",
            compliance_requirements=["HIPAA", "HITRUST", "GDPR"],
            standards={
                "resolution_rate": IndustryStandard(
                    metric_name="resolution_rate",
                    industry=IndustryType.HEALTHCARE,
                    minimum_acceptable=0.55,
                    industry_average=0.68,
                    best_in_class=0.85,
                    target=0.78,
                    weight=0.35,
                ),
                "first_contact_resolution": IndustryStandard(
                    metric_name="first_contact_resolution",
                    industry=IndustryType.HEALTHCARE,
                    minimum_acceptable=0.45,
                    industry_average=0.60,
                    best_in_class=0.80,
                    target=0.72,
                    weight=0.15,
                ),
                "customer_satisfaction": IndustryStandard(
                    metric_name="customer_satisfaction",
                    industry=IndustryType.HEALTHCARE,
                    minimum_acceptable=0.68,
                    industry_average=0.76,
                    best_in_class=0.90,
                    target=0.83,
                    weight=0.20,
                ),
                "response_quality": IndustryStandard(
                    metric_name="response_quality",
                    industry=IndustryType.HEALTHCARE,
                    minimum_acceptable=0.70,
                    industry_average=0.80,
                    best_in_class=0.93,
                    target=0.87,
                    weight=0.20,
                ),
                "faq_match_rate": IndustryStandard(
                    metric_name="faq_match_rate",
                    industry=IndustryType.HEALTHCARE,
                    minimum_acceptable=0.65,
                    industry_average=0.75,
                    best_in_class=0.90,
                    target=0.82,
                    weight=0.10,
                ),
            },
        )

    def _create_logistics_benchmark(self) -> IndustryBenchmarkSet:
        """Create logistics industry benchmarks"""
        return IndustryBenchmarkSet(
            industry=IndustryType.LOGISTICS,
            description="Logistics customer support benchmarks",
            compliance_requirements=["GDPR"],
            standards={
                "resolution_rate": IndustryStandard(
                    metric_name="resolution_rate",
                    industry=IndustryType.LOGISTICS,
                    minimum_acceptable=0.58,
                    industry_average=0.70,
                    best_in_class=0.86,
                    target=0.78,
                    weight=0.30,
                ),
                "first_contact_resolution": IndustryStandard(
                    metric_name="first_contact_resolution",
                    industry=IndustryType.LOGISTICS,
                    minimum_acceptable=0.48,
                    industry_average=0.62,
                    best_in_class=0.80,
                    target=0.73,
                    weight=0.20,
                ),
                "customer_satisfaction": IndustryStandard(
                    metric_name="customer_satisfaction",
                    industry=IndustryType.LOGISTICS,
                    minimum_acceptable=0.68,
                    industry_average=0.76,
                    best_in_class=0.90,
                    target=0.82,
                    weight=0.20,
                ),
                "response_quality": IndustryStandard(
                    metric_name="response_quality",
                    industry=IndustryType.LOGISTICS,
                    minimum_acceptable=0.62,
                    industry_average=0.72,
                    best_in_class=0.88,
                    target=0.80,
                    weight=0.15,
                ),
                "faq_match_rate": IndustryStandard(
                    metric_name="faq_match_rate",
                    industry=IndustryType.LOGISTICS,
                    minimum_acceptable=0.68,
                    industry_average=0.78,
                    best_in_class=0.92,
                    target=0.85,
                    weight=0.15,
                ),
            },
        )

    def _create_fintech_benchmark(self) -> IndustryBenchmarkSet:
        """Create fintech industry benchmarks with PCI DSS"""
        return IndustryBenchmarkSet(
            industry=IndustryType.FINTECH,
            description="FinTech customer support benchmarks (PCI DSS compliant)",
            compliance_requirements=["PCI_DSS", "SOC2", "GDPR"],
            standards={
                "resolution_rate": IndustryStandard(
                    metric_name="resolution_rate",
                    industry=IndustryType.FINTECH,
                    minimum_acceptable=0.62,
                    industry_average=0.74,
                    best_in_class=0.89,
                    target=0.80,
                    weight=0.25,
                ),
                "first_contact_resolution": IndustryStandard(
                    metric_name="first_contact_resolution",
                    industry=IndustryType.FINTECH,
                    minimum_acceptable=0.52,
                    industry_average=0.66,
                    best_in_class=0.84,
                    target=0.76,
                    weight=0.20,
                ),
                "customer_satisfaction": IndustryStandard(
                    metric_name="customer_satisfaction",
                    industry=IndustryType.FINTECH,
                    minimum_acceptable=0.70,
                    industry_average=0.79,
                    best_in_class=0.93,
                    target=0.85,
                    weight=0.25,
                ),
                "response_quality": IndustryStandard(
                    metric_name="response_quality",
                    industry=IndustryType.FINTECH,
                    minimum_acceptable=0.68,
                    industry_average=0.78,
                    best_in_class=0.92,
                    target=0.85,
                    weight=0.20,
                ),
                "faq_match_rate": IndustryStandard(
                    metric_name="faq_match_rate",
                    industry=IndustryType.FINTECH,
                    minimum_acceptable=0.70,
                    industry_average=0.80,
                    best_in_class=0.94,
                    target=0.86,
                    weight=0.10,
                ),
            },
        )


def get_industry_benchmark(
    industry: str
) -> Optional[IndustryBenchmarkSet]:
    """
    Convenience function to get industry benchmark.

    Args:
        industry: Industry name string

    Returns:
        IndustryBenchmarkSet or None
    """
    benchmarks = IndustryBenchmarks()
    try:
        industry_type = IndustryType(industry.lower())
        return benchmarks.get_benchmark(industry_type)
    except ValueError:
        return None
