"""
Model Optimizer for Agent Lightning 94% Training.

Provides hyperparameter optimization and model tuning.
"""
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field
import json

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OptimizationConfig:
    """Configuration for model optimization."""
    max_iterations: int = 50
    early_stopping_patience: int = 5
    learning_rate_range: Tuple[float, float] = (1e-5, 1e-2)
    batch_size_options: List[int] = field(default_factory=lambda: [16, 32, 64])
    dropout_range: Tuple[float, float] = (0.1, 0.5)
    target_accuracy: float = 0.94


@dataclass
class OptimizationResult:
    """Result of optimization run."""
    best_params: Dict[str, Any]
    best_accuracy: float
    iterations: int
    improvement: float
    optimized_at: str = ""
    
    def __post_init__(self):
        if not self.optimized_at:
            self.optimized_at = datetime.now(timezone.utc).isoformat()


class ModelOptimizer:
    """
    Model hyperparameter optimizer for Agent Lightning.
    
    Features:
    - Hyperparameter search
    - Learning rate scheduling
    - Regularization tuning
    - Early stopping
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        """Initialize optimizer with configuration."""
        self.config = config or OptimizationConfig()
        self._best_params: Dict[str, Any] = {}
        self._best_accuracy: float = 0.0
        self._history: List[Dict[str, Any]] = []
    
    def optimize(
        self,
        train_fn: Callable,
        eval_fn: Callable,
        param_space: Optional[Dict[str, Any]] = None
    ) -> OptimizationResult:
        """
        Run hyperparameter optimization.
        
        Args:
            train_fn: Training function
            eval_fn: Evaluation function
            param_space: Parameter search space
            
        Returns:
            OptimizationResult with best parameters
        """
        param_space = param_space or self._get_default_param_space()
        
        best_params = {}
        best_accuracy = 0.0
        no_improvement_count = 0
        
        for iteration in range(self.config.max_iterations):
            # Sample parameters
            params = self._sample_params(param_space)
            
            try:
                # Train and evaluate
                train_fn(**params)
                accuracy = eval_fn()
                
                # Track history
                self._history.append({
                    "iteration": iteration,
                    "params": params,
                    "accuracy": accuracy
                })
                
                # Update best
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_params = params.copy()
                    no_improvement_count = 0
                    
                    logger.info({
                        "event": "optimization_improvement",
                        "iteration": iteration,
                        "accuracy": accuracy,
                        "params": params
                    })
                else:
                    no_improvement_count += 1
                
                # Early stopping
                if no_improvement_count >= self.config.early_stopping_patience:
                    logger.info({
                        "event": "early_stopping",
                        "iteration": iteration,
                        "best_accuracy": best_accuracy
                    })
                    break
                
                # Target reached
                if best_accuracy >= self.config.target_accuracy:
                    logger.info({
                        "event": "target_reached",
                        "accuracy": best_accuracy
                    })
                    break
                    
            except Exception as e:
                logger.error({
                    "event": "optimization_error",
                    "iteration": iteration,
                    "error": str(e)
                })
        
        self._best_params = best_params
        self._best_accuracy = best_accuracy
        
        return OptimizationResult(
            best_params=best_params,
            best_accuracy=best_accuracy,
            iterations=len(self._history),
            improvement=best_accuracy - self._history[0]["accuracy"] if self._history else 0.0
        )
    
    def _get_default_param_space(self) -> Dict[str, Any]:
        """Get default parameter search space."""
        return {
            "learning_rate": {
                "type": "log_uniform",
                "min": self.config.learning_rate_range[0],
                "max": self.config.learning_rate_range[1]
            },
            "batch_size": {
                "type": "choice",
                "options": self.config.batch_size_options
            },
            "dropout": {
                "type": "uniform",
                "min": self.config.dropout_range[0],
                "max": self.config.dropout_range[1]
            },
            "hidden_size": {
                "type": "choice",
                "options": [128, 256, 512]
            },
            "num_layers": {
                "type": "choice",
                "options": [2, 3, 4]
            }
        }
    
    def _sample_params(self, param_space: Dict[str, Any]) -> Dict[str, Any]:
        """Sample parameters from search space."""
        import random
        
        params = {}
        
        for name, spec in param_space.items():
            param_type = spec.get("type", "choice")
            
            if param_type == "choice":
                options = spec.get("options", [])
                params[name] = random.choice(options) if options else None
            
            elif param_type == "uniform":
                min_val = spec.get("min", 0)
                max_val = spec.get("max", 1)
                params[name] = min_val + random.random() * (max_val - min_val)
            
            elif param_type == "log_uniform":
                import math
                min_val = spec.get("min", 1e-5)
                max_val = spec.get("max", 1e-2)
                log_min = math.log(min_val)
                log_max = math.log(max_val)
                params[name] = math.exp(log_min + random.random() * (log_max - log_min))
            
            elif param_type == "int":
                min_val = spec.get("min", 1)
                max_val = spec.get("max", 10)
                params[name] = random.randint(min_val, max_val)
        
        return params
    
    def get_best_params(self) -> Dict[str, Any]:
        """Get best parameters found."""
        return self._best_params.copy()
    
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """Get full optimization history."""
        return self._history.copy()


class LearningRateScheduler:
    """Learning rate scheduler with warmup and decay."""
    
    def __init__(
        self,
        initial_lr: float = 1e-3,
        warmup_steps: int = 100,
        decay_type: str = "cosine",
        total_steps: int = 1000
    ):
        """Initialize scheduler."""
        self.initial_lr = initial_lr
        self.warmup_steps = warmup_steps
        self.decay_type = decay_type
        self.total_steps = total_steps
        self._current_step = 0
    
    def step(self) -> float:
        """Get learning rate for current step."""
        self._current_step += 1
        
        if self._current_step <= self.warmup_steps:
            # Warmup phase
            return self.initial_lr * (self._current_step / self.warmup_steps)
        
        progress = (self._current_step - self.warmup_steps) / (self.total_steps - self.warmup_steps)
        progress = min(1.0, progress)
        
        if self.decay_type == "cosine":
            import math
            return self.initial_lr * (0.5 * (1 + math.cos(math.pi * progress)))
        elif self.decay_type == "linear":
            return self.initial_lr * (1 - progress)
        elif self.decay_type == "exponential":
            return self.initial_lr * (0.95 ** (progress * 100))
        
        return self.initial_lr
    
    def reset(self) -> None:
        """Reset scheduler."""
        self._current_step = 0


def optimize_hyperparameters(
    train_fn: Callable,
    eval_fn: Callable,
    config: Optional[OptimizationConfig] = None
) -> OptimizationResult:
    """
    Quick function to optimize hyperparameters.
    
    Args:
        train_fn: Training function
        eval_fn: Evaluation function
        config: Optional optimization config
        
    Returns:
        OptimizationResult
    """
    optimizer = ModelOptimizer(config)
    return optimizer.optimize(train_fn, eval_fn)
