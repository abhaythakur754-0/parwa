"""
Regression Detector for Agent Lightning 94% Accuracy.

Detects accuracy regressions and triggers alerts.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
import json

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RegressionResult:
    """Result of regression detection."""
    has_regression: bool
    baseline_accuracy: float
    current_accuracy: float
    regression_magnitude: float
    affected_categories: List[str] = field(default_factory=list)
    detected_at: str = ""
    
    def __post_init__(self):
        if not self.detected_at:
            self.detected_at = datetime.now(timezone.utc).isoformat()


class RegressionDetector:
    """
    Detects accuracy regressions in Agent Lightning.
    
    Features:
    - Baseline comparison
    - Automatic regression alerts
    - Historical tracking
    - Category-level detection
    """
    
    REGRESSION_THRESHOLD = 0.02  # 2% drop triggers regression
    
    def __init__(
        self,
        baseline_path: Optional[Path] = None,
        history_path: Optional[Path] = None
    ):
        """Initialize regression detector."""
        self.baseline_path = baseline_path
        self.history_path = history_path
        self._baseline: Dict[str, float] = {}
        self._history: List[Dict[str, Any]] = []
        
        if baseline_path and baseline_path.exists():
            self._load_baseline()
    
    def set_baseline(
        self,
        overall_accuracy: float,
        category_accuracies: Optional[Dict[str, float]] = None
    ) -> None:
        """Set baseline accuracy metrics."""
        self._baseline = {
            "overall": overall_accuracy,
            "categories": category_accuracies or {},
            "set_at": datetime.now(timezone.utc).isoformat()
        }
        
        if self.baseline_path:
            self._save_baseline()
        
        logger.info({
            "event": "baseline_set",
            "overall_accuracy": overall_accuracy
        })
    
    def check_regression(
        self,
        current_accuracy: float,
        category_accuracies: Optional[Dict[str, float]] = None
    ) -> RegressionResult:
        """
        Check for accuracy regression.
        
        Args:
            current_accuracy: Current overall accuracy
            category_accuracies: Current per-category accuracies
            
        Returns:
            RegressionResult with details
        """
        baseline_overall = self._baseline.get("overall", current_accuracy)
        baseline_categories = self._baseline.get("categories", {})
        category_accuracies = category_accuracies or {}
        
        # Check overall regression
        regression_magnitude = baseline_overall - current_accuracy
        has_regression = regression_magnitude > self.REGRESSION_THRESHOLD
        
        # Check category-level regressions
        affected_categories = []
        for cat, baseline_acc in baseline_categories.items():
            current_acc = category_accuracies.get(cat, baseline_acc)
            if baseline_acc - current_acc > self.REGRESSION_THRESHOLD:
                affected_categories.append(cat)
        
        result = RegressionResult(
            has_regression=has_regression,
            baseline_accuracy=baseline_overall,
            current_accuracy=current_accuracy,
            regression_magnitude=regression_magnitude,
            affected_categories=affected_categories
        )
        
        # Record in history
        self._history.append({
            "timestamp": result.detected_at,
            "current_accuracy": current_accuracy,
            "has_regression": has_regression,
            "regression_magnitude": regression_magnitude
        })
        
        if has_regression:
            logger.warning({
                "event": "regression_detected",
                "baseline": baseline_overall,
                "current": current_accuracy,
                "magnitude": regression_magnitude,
                "affected_categories": affected_categories
            })
        
        return result
    
    def get_trend(self, window: int = 10) -> Dict[str, Any]:
        """Get accuracy trend over recent history."""
        if len(self._history) < 2:
            return {"trend": "stable", "data": []}
        
        recent = self._history[-window:]
        accuracies = [h["current_accuracy"] for h in recent]
        
        if len(accuracies) < 2:
            return {"trend": "stable", "data": accuracies}
        
        # Calculate trend direction
        first_half = sum(accuracies[:len(accuracies)//2]) / (len(accuracies)//2)
        second_half = sum(accuracies[len(accuracies)//2:]) / (len(accuracies) - len(accuracies)//2)
        
        if second_half > first_half + 0.01:
            trend = "improving"
        elif second_half < first_half - 0.01:
            trend = "declining"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "data": accuracies,
            "average": sum(accuracies) / len(accuracies)
        }
    
    def should_rollback(self) -> bool:
        """Determine if rollback is needed."""
        if not self._history:
            return False
        
        # Check last 3 results for consistent regression
        recent = self._history[-3:]
        if len(recent) < 3:
            return False
        
        regression_count = sum(1 for h in recent if h.get("has_regression", False))
        return regression_count >= 2
    
    def _load_baseline(self) -> None:
        """Load baseline from file."""
        try:
            with open(self.baseline_path, 'r') as f:
                self._baseline = json.load(f)
        except Exception as e:
            logger.error({"event": "baseline_load_error", "error": str(e)})
    
    def _save_baseline(self) -> None:
        """Save baseline to file."""
        try:
            with open(self.baseline_path, 'w') as f:
                json.dump(self._baseline, f, indent=2)
        except Exception as e:
            logger.error({"event": "baseline_save_error", "error": str(e)})
