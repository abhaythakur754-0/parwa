"""
Cost Optimizer for Smart Router
Token cost tracking, budget enforcement, and ROI optimization
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BudgetStatus(Enum):
    """Budget status levels"""
    UNLIMITED = "unlimited"
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    EXCEEDED = "exceeded"


@dataclass
class CostRecord:
    """Single cost record"""
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    client_id: str
    session_id: str
    query_type: str


@dataclass
class BudgetInfo:
    """Budget information"""
    client_id: str
    total_budget: float
    used: float
    remaining: float
    period_start: datetime
    period_end: datetime
    status: BudgetStatus


@dataclass
class CostReport:
    """Cost analysis report"""
    total_cost: float
    total_tokens: int
    avg_cost_per_query: float
    cost_by_model: Dict[str, float]
    cost_by_client: Dict[str, float]
    budget_status: Dict[str, BudgetStatus]


class CostOptimizer:
    """
    Optimizes model selection costs.
    Tracks token usage, enforces budgets, and reports ROI.
    """
    
    # Warning thresholds
    WARNING_THRESHOLD = 0.7  # 70% of budget
    CRITICAL_THRESHOLD = 0.9  # 90% of budget
    
    # Model costs per 1k tokens (input/output)
    MODEL_COSTS = {
        'mini': {'input': 0.0001, 'output': 0.0001},
        'mini-pro': {'input': 0.0002, 'output': 0.0002},
        'junior': {'input': 0.001, 'output': 0.002},
        'junior-plus': {'input': 0.002, 'output': 0.004},
        'high': {'input': 0.01, 'output': 0.03},
        'high-reasoning': {'input': 0.02, 'output': 0.06},
    }
    
    def __init__(self):
        self._cost_records: List[CostRecord] = []
        self._budgets: Dict[str, BudgetInfo] = {}
        self._client_usage: Dict[str, float] = {}
        self._initialized = True
    
    def track_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        client_id: str,
        session_id: str,
        query_type: str = "general"
    ) -> CostRecord:
        """
        Track token costs for a query.
        
        Args:
            model: Model name
            input_tokens: Input token count
            output_tokens: Output token count
            client_id: Client identifier
            session_id: Session identifier
            query_type: Type of query
            
        Returns:
            CostRecord
        """
        # Calculate cost
        costs = self.MODEL_COSTS.get(model, {'input': 0.001, 'output': 0.002})
        cost = (
            (input_tokens / 1000) * costs['input'] +
            (output_tokens / 1000) * costs['output']
        )
        
        record = CostRecord(
            timestamp=datetime.now(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            client_id=client_id,
            session_id=session_id,
            query_type=query_type
        )
        
        self._cost_records.append(record)
        
        # Update client usage
        if client_id not in self._client_usage:
            self._client_usage[client_id] = 0
        self._client_usage[client_id] += cost
        
        # Update budget
        self._update_budget_usage(client_id, cost)
        
        logger.debug(f"Tracked cost: ${cost:.4f} for {model}")
        
        return record
    
    def set_budget(
        self,
        client_id: str,
        total_budget: float,
        period_days: int = 30
    ) -> BudgetInfo:
        """
        Set budget for a client.
        
        Args:
            client_id: Client identifier
            total_budget: Total budget amount
            period_days: Budget period in days
            
        Returns:
            BudgetInfo
        """
        now = datetime.now()
        
        budget = BudgetInfo(
            client_id=client_id,
            total_budget=total_budget,
            used=self._client_usage.get(client_id, 0),
            remaining=total_budget - self._client_usage.get(client_id, 0),
            period_start=now,
            period_end=now + timedelta(days=period_days),
            status=BudgetStatus.HEALTHY
        )
        
        self._budgets[client_id] = budget
        
        logger.info(f"Set budget for {client_id}: ${total_budget:.2f}")
        
        return budget
    
    def _update_budget_usage(
        self,
        client_id: str,
        cost: float
    ) -> None:
        """Update budget usage after cost."""
        budget = self._budgets.get(client_id)
        if not budget:
            return
        
        budget.used += cost
        budget.remaining = budget.total_budget - budget.used
        
        # Update status
        usage_ratio = budget.used / budget.total_budget
        
        if usage_ratio >= 1.0:
            budget.status = BudgetStatus.EXCEEDED
        elif usage_ratio >= self.CRITICAL_THRESHOLD:
            budget.status = BudgetStatus.CRITICAL
        elif usage_ratio >= self.WARNING_THRESHOLD:
            budget.status = BudgetStatus.WARNING
        else:
            budget.status = BudgetStatus.HEALTHY
    
    def check_budget(
        self,
        client_id: str,
        estimated_cost: float
    ) -> tuple[bool, BudgetStatus]:
        """
        Check if query is within budget.
        
        Args:
            client_id: Client identifier
            estimated_cost: Estimated query cost
            
        Returns:
            Tuple of (allowed, status)
        """
        budget = self._budgets.get(client_id)
        
        if not budget:
            return True, BudgetStatus.UNLIMITED
        
        if budget.status == BudgetStatus.EXCEEDED:
            return False, budget.status
        
        if budget.remaining < estimated_cost:
            return False, budget.status
        
        return True, budget.status
    
    def get_cost_aware_model(
        self,
        models: List[str],
        client_id: str,
        quality_preference: str = "balanced"
    ) -> str:
        """
        Select model considering cost efficiency.
        
        Args:
            models: List of candidate models
            client_id: Client identifier
            quality_preference: Cost-quality preference (cheap, balanced, quality)
            
        Returns:
            Selected model name
        """
        if not models:
            return 'junior'
        
        budget = self._budgets.get(client_id)
        remaining = budget.remaining if budget else float('inf')
        
        # Filter by budget
        affordable = []
        for model in models:
            cost = self.MODEL_COSTS.get(model, {}).get('input', 0.001)
            if cost * 1000 < remaining:  # Assume ~1000 tokens
                affordable.append(model)
        
        if not affordable:
            # Return cheapest
            return min(models, key=lambda m: self.MODEL_COSTS.get(m, {}).get('input', 1))
        
        # Select based on preference
        if quality_preference == "cheap":
            return min(affordable, key=lambda m: self.MODEL_COSTS.get(m, {}).get('input', 1))
        elif quality_preference == "quality":
            return max(affordable, key=lambda m: self.MODEL_COSTS.get(m, {}).get('input', 0))
        else:
            # Balanced - middle cost
            sorted_models = sorted(
                affordable,
                key=lambda m: self.MODEL_COSTS.get(m, {}).get('input', 0)
            )
            return sorted_models[len(sorted_models) // 2]
    
    def predict_cost(
        self,
        model: str,
        estimated_tokens: int
    ) -> float:
        """
        Predict cost for a query.
        
        Args:
            model: Model name
            estimated_tokens: Estimated total tokens
            
        Returns:
            Predicted cost
        """
        costs = self.MODEL_COSTS.get(model, {'input': 0.001, 'output': 0.002})
        
        # Assume 60% input, 40% output
        input_tokens = estimated_tokens * 0.6
        output_tokens = estimated_tokens * 0.4
        
        return (
            (input_tokens / 1000) * costs['input'] +
            (output_tokens / 1000) * costs['output']
        )
    
    def get_cost_report(
        self,
        client_id: Optional[str] = None,
        days: int = 7
    ) -> CostReport:
        """
        Generate cost report.
        
        Args:
            client_id: Optional client filter
            days: Number of days to include
            
        Returns:
            CostReport
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        # Filter records
        records = [
            r for r in self._cost_records
            if r.timestamp >= cutoff
        ]
        
        if client_id:
            records = [r for r in records if r.client_id == client_id]
        
        # Calculate totals
        total_cost = sum(r.cost for r in records)
        total_tokens = sum(r.input_tokens + r.output_tokens for r in records)
        avg_cost = total_cost / len(records) if records else 0
        
        # By model
        cost_by_model: Dict[str, float] = {}
        for r in records:
            cost_by_model[r.model] = cost_by_model.get(r.model, 0) + r.cost
        
        # By client
        cost_by_client: Dict[str, float] = {}
        for r in records:
            cost_by_client[r.client_id] = cost_by_client.get(r.client_id, 0) + r.cost
        
        # Budget status
        budget_status = {
            cid: budget.status
            for cid, budget in self._budgets.items()
        }
        
        return CostReport(
            total_cost=total_cost,
            total_tokens=total_tokens,
            avg_cost_per_query=avg_cost,
            cost_by_model=cost_by_model,
            cost_by_client=cost_by_client,
            budget_status=budget_status
        )
    
    def calculate_roi(
        self,
        client_id: str,
        resolution_value: float = 10.0
    ) -> Dict[str, Any]:
        """
        Calculate ROI for a client.
        
        Args:
            client_id: Client identifier
            resolution_value: Value of a resolved query
            
        Returns:
            ROI metrics
        """
        records = [r for r in self._cost_records if r.client_id == client_id]
        
        if not records:
            return {'roi': 0, 'total_cost': 0, 'estimated_value': 0}
        
        total_cost = sum(r.cost for r in records)
        
        # Estimate resolved queries (assume 80% resolution rate)
        resolved = len(records) * 0.8
        estimated_value = resolved * resolution_value
        
        roi = (estimated_value - total_cost) / total_cost if total_cost > 0 else 0
        
        return {
            'roi': roi,
            'total_cost': total_cost,
            'estimated_value': estimated_value,
            'query_count': len(records),
            'avg_cost_per_query': total_cost / len(records)
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get optimizer statistics."""
        return {
            'total_records': len(self._cost_records),
            'total_clients': len(self._client_usage),
            'budgets_configured': len(self._budgets),
            'total_cost_tracked': sum(r.cost for r in self._cost_records),
        }
    
    def is_initialized(self) -> bool:
        """Check if optimizer is initialized."""
        return self._initialized
