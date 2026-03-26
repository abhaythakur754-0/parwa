"""
Per-Client Accuracy - Calculate and track per-client accuracy metrics.

CRITICAL: Each client's accuracy is calculated independently.
No cross-client data is exposed in metrics.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of accuracy metrics"""
    RESOLUTION_RATE = "resolution_rate"
    FIRST_CONTACT_RESOLUTION = "first_contact_resolution"
    ESCALATION_RATE = "escalation_rate"
    CUSTOMER_SATISFACTION = "customer_satisfaction"
    RESPONSE_QUALITY = "response_quality"
    FAQ_MATCH_RATE = "faq_match_rate"


@dataclass
class ClientMetrics:
    """
    Accuracy metrics for a single client.
    
    CRITICAL: Contains only aggregated metrics, no customer data.
    """
    client_id: str
    industry: str
    variant: str
    timestamp: datetime
    
    # Core accuracy metrics
    overall_accuracy: float
    resolution_rate: float
    first_contact_resolution: float
    escalation_rate: float
    customer_satisfaction: float
    response_quality: float
    faq_match_rate: float
    
    # Improvement tracking
    baseline_accuracy: float
    improvement_percentage: float
    improvement_trend: str  # "improving", "stable", "declining"
    
    # Additional metrics
    total_tickets_processed: int
    total_resolved: int
    total_escalated: int
    avg_response_time_ms: float
    
    # Compliance (for healthcare/fintech)
    compliance_score: Optional[float] = None
    hipaa_compliant: bool = False
    pci_dss_compliant: bool = False
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "client_id": self.client_id,
            "industry": self.industry,
            "variant": self.variant,
            "timestamp": self.timestamp.isoformat(),
            "overall_accuracy": self.overall_accuracy,
            "resolution_rate": self.resolution_rate,
            "first_contact_resolution": self.first_contact_resolution,
            "escalation_rate": self.escalation_rate,
            "customer_satisfaction": self.customer_satisfaction,
            "response_quality": self.response_quality,
            "faq_match_rate": self.faq_match_rate,
            "baseline_accuracy": self.baseline_accuracy,
            "improvement_percentage": self.improvement_percentage,
            "improvement_trend": self.improvement_trend,
            "total_tickets_processed": self.total_tickets_processed,
            "total_resolved": self.total_resolved,
            "total_escalated": self.total_escalated,
            "avg_response_time_ms": self.avg_response_time_ms,
            "compliance_score": self.compliance_score,
            "hipaa_compliant": self.hipaa_compliant,
            "pci_dss_compliant": self.pci_dss_compliant,
            "metadata": self.metadata,
        }

    def meets_target(self, target_accuracy: float = 0.77) -> bool:
        """Check if metrics meet target accuracy"""
        return self.overall_accuracy >= target_accuracy


class PerClientAccuracy:
    """
    Calculate and manage per-client accuracy metrics.
    
    Supports all 5 clients with industry-specific metrics:
    - Client 001: E-commerce
    - Client 002: SaaS
    - Client 003: Healthcare (HIPAA)
    - Client 004: Logistics
    - Client 005: FinTech (PCI DSS)
    """

    # Industry-specific baselines
    INDUSTRY_BASELINES = {
        "ecommerce": {
            "resolution_rate": 0.75,
            "faq_match_rate": 0.80,
            "customer_satisfaction": 0.85,
        },
        "saas": {
            "resolution_rate": 0.78,
            "faq_match_rate": 0.82,
            "customer_satisfaction": 0.83,
        },
        "healthcare": {
            "resolution_rate": 0.70,
            "faq_match_rate": 0.75,
            "customer_satisfaction": 0.80,
        },
        "logistics": {
            "resolution_rate": 0.72,
            "faq_match_rate": 0.77,
            "customer_satisfaction": 0.82,
        },
        "fintech": {
            "resolution_rate": 0.76,
            "faq_match_rate": 0.79,
            "customer_satisfaction": 0.84,
        },
    }

    # Client configurations
    CLIENT_CONFIGS = {
        "client_001": {
            "industry": "ecommerce",
            "variant": "parwa_junior",
            "hipaa_required": False,
            "pci_dss_required": False,
        },
        "client_002": {
            "industry": "saas",
            "variant": "parwa_high",
            "hipaa_required": False,
            "pci_dss_required": False,
        },
        "client_003": {
            "industry": "healthcare",
            "variant": "parwa_high",
            "hipaa_required": True,
            "pci_dss_required": False,
        },
        "client_004": {
            "industry": "logistics",
            "variant": "parwa_junior",
            "hipaa_required": False,
            "pci_dss_required": False,
        },
        "client_005": {
            "industry": "fintech",
            "variant": "parwa_high",
            "hipaa_required": False,
            "pci_dss_required": True,
        },
    }

    def __init__(self):
        """Initialize per-client accuracy tracker"""
        self._metrics_history: Dict[str, List[ClientMetrics]] = {
            client_id: [] for client_id in self.CLIENT_CONFIGS
        }

    def calculate_metrics(
        self,
        client_id: str,
        resolution_rate: float,
        first_contact_resolution: float,
        escalation_rate: float,
        customer_satisfaction: float,
        response_quality: float,
        faq_match_rate: float,
        total_tickets: int,
        total_resolved: int,
        total_escalated: int,
        avg_response_time_ms: float,
        baseline_accuracy: Optional[float] = None,
    ) -> ClientMetrics:
        """
        Calculate comprehensive metrics for a client.

        Args:
            client_id: Client identifier
            resolution_rate: Rate of successful resolutions
            first_contact_resolution: FCR rate
            escalation_rate: Rate of escalations
            customer_satisfaction: CSAT score
            response_quality: Response quality score
            faq_match_rate: FAQ matching rate
            total_tickets: Total tickets processed
            total_resolved: Total resolved tickets
            total_escalated: Total escalated tickets
            avg_response_time_ms: Average response time in ms
            baseline_accuracy: Optional client-specific baseline

        Returns:
            ClientMetrics object
        """
        if client_id not in self.CLIENT_CONFIGS:
            raise ValueError(f"Unknown client: {client_id}")

        config = self.CLIENT_CONFIGS[client_id]
        industry = config["industry"]

        # Get industry baseline
        industry_baseline = self.INDUSTRY_BASELINES.get(industry, {})
        default_baseline = baseline_accuracy or 0.72

        # Calculate overall accuracy (weighted average)
        overall_accuracy = self._calculate_overall_accuracy(
            resolution_rate=resolution_rate,
            first_contact_resolution=first_contact_resolution,
            customer_satisfaction=customer_satisfaction,
            response_quality=response_quality,
            faq_match_rate=faq_match_rate,
            industry=industry,
        )

        # Calculate improvement
        improvement = ((overall_accuracy - default_baseline) / default_baseline) * 100

        # Determine improvement trend
        trend = self._determine_trend(client_id, improvement)

        # Create metrics object
        metrics = ClientMetrics(
            client_id=client_id,
            industry=industry,
            variant=config["variant"],
            timestamp=datetime.now(),
            overall_accuracy=overall_accuracy,
            resolution_rate=resolution_rate,
            first_contact_resolution=first_contact_resolution,
            escalation_rate=escalation_rate,
            customer_satisfaction=customer_satisfaction,
            response_quality=response_quality,
            faq_match_rate=faq_match_rate,
            baseline_accuracy=default_baseline,
            improvement_percentage=improvement,
            improvement_trend=trend,
            total_tickets_processed=total_tickets,
            total_resolved=total_resolved,
            total_escalated=total_escalated,
            avg_response_time_ms=avg_response_time_ms,
            hipaa_compliant=config["hipaa_required"],
            pci_dss_compliant=config["pci_dss_required"],
        )

        # Store in history
        self._metrics_history[client_id].append(metrics)

        logger.info(
            f"Calculated metrics for {client_id}: "
            f"accuracy={overall_accuracy:.2%}, improvement={improvement:.2f}%"
        )

        return metrics

    def get_client_metrics(self, client_id: str) -> Optional[ClientMetrics]:
        """Get latest metrics for a client"""
        history = self._metrics_history.get(client_id, [])
        return history[-1] if history else None

    def get_all_client_metrics(self) -> Dict[str, Optional[ClientMetrics]]:
        """Get latest metrics for all clients"""
        return {
            client_id: self.get_client_metrics(client_id)
            for client_id in self.CLIENT_CONFIGS
        }

    def get_metrics_history(
        self,
        client_id: str,
        limit: int = 10
    ) -> List[ClientMetrics]:
        """Get metrics history for a client"""
        return self._metrics_history.get(client_id, [])[-limit:]

    def compare_to_industry_baseline(
        self,
        metrics: ClientMetrics
    ) -> Dict[str, Any]:
        """
        Compare client metrics to industry baseline.

        Args:
            metrics: Client metrics to compare

        Returns:
            Dict with comparison results
        """
        industry_baseline = self.INDUSTRY_BASELINES.get(metrics.industry, {})

        comparison = {}
        for key, baseline_value in industry_baseline.items():
            current_value = getattr(metrics, key, None)
            if current_value is not None:
                diff = current_value - baseline_value
                comparison[key] = {
                    "baseline": baseline_value,
                    "current": current_value,
                    "difference": diff,
                    "above_baseline": diff > 0,
                }

        return comparison

    def _calculate_overall_accuracy(
        self,
        resolution_rate: float,
        first_contact_resolution: float,
        customer_satisfaction: float,
        response_quality: float,
        faq_match_rate: float,
        industry: str,
    ) -> float:
        """
        Calculate weighted overall accuracy.

        Weights are industry-specific.
        """
        # Industry-specific weights
        weights = {
            "ecommerce": {
                "resolution_rate": 0.30,
                "first_contact_resolution": 0.20,
                "customer_satisfaction": 0.25,
                "response_quality": 0.15,
                "faq_match_rate": 0.10,
            },
            "saas": {
                "resolution_rate": 0.25,
                "first_contact_resolution": 0.20,
                "customer_satisfaction": 0.20,
                "response_quality": 0.20,
                "faq_match_rate": 0.15,
            },
            "healthcare": {
                "resolution_rate": 0.35,
                "first_contact_resolution": 0.15,
                "customer_satisfaction": 0.20,
                "response_quality": 0.20,
                "faq_match_rate": 0.10,
            },
            "logistics": {
                "resolution_rate": 0.30,
                "first_contact_resolution": 0.20,
                "customer_satisfaction": 0.20,
                "response_quality": 0.15,
                "faq_match_rate": 0.15,
            },
            "fintech": {
                "resolution_rate": 0.25,
                "first_contact_resolution": 0.20,
                "customer_satisfaction": 0.25,
                "response_quality": 0.20,
                "faq_match_rate": 0.10,
            },
        }

        industry_weights = weights.get(industry, weights["ecommerce"])

        overall = (
            resolution_rate * industry_weights["resolution_rate"] +
            first_contact_resolution * industry_weights["first_contact_resolution"] +
            customer_satisfaction * industry_weights["customer_satisfaction"] +
            response_quality * industry_weights["response_quality"] +
            faq_match_rate * industry_weights["faq_match_rate"]
        )

        return round(overall, 4)

    def _determine_trend(
        self,
        client_id: str,
        current_improvement: float
    ) -> str:
        """Determine improvement trend for a client"""
        history = self._metrics_history.get(client_id, [])
        
        if len(history) < 1:
            return "stable"
        
        previous_improvement = history[-1].improvement_percentage
        diff = current_improvement - previous_improvement
        
        if diff > 0.1:  # 0.1% improvement
            return "improving"
        elif diff < -0.1:  # 0.1% decline
            return "declining"
        else:
            return "stable"


def calculate_client_accuracy(
    client_id: str,
    resolution_rate: float,
    first_contact_resolution: float,
    escalation_rate: float,
    customer_satisfaction: float,
    response_quality: float,
    faq_match_rate: float,
    total_tickets: int,
    total_resolved: int,
    total_escalated: int,
    avg_response_time_ms: float,
) -> ClientMetrics:
    """
    Convenience function to calculate client accuracy.

    Args:
        client_id: Client identifier
        resolution_rate: Rate of successful resolutions
        first_contact_resolution: FCR rate
        escalation_rate: Rate of escalations
        customer_satisfaction: CSAT score
        response_quality: Response quality score
        faq_match_rate: FAQ matching rate
        total_tickets: Total tickets processed
        total_resolved: Total resolved tickets
        total_escalated: Total escalated tickets
        avg_response_time_ms: Average response time in ms

    Returns:
        ClientMetrics object
    """
    tracker = PerClientAccuracy()
    return tracker.calculate_metrics(
        client_id=client_id,
        resolution_rate=resolution_rate,
        first_contact_resolution=first_contact_resolution,
        escalation_rate=escalation_rate,
        customer_satisfaction=customer_satisfaction,
        response_quality=response_quality,
        faq_match_rate=faq_match_rate,
        total_tickets=total_tickets,
        total_resolved=total_resolved,
        total_escalated=total_escalated,
        avg_response_time_ms=avg_response_time_ms,
    )
