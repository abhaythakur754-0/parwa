#!/usr/bin/env python3
"""
Agent Lightning v2 Training Runner

Full training pipeline orchestration for Agent Lightning v2.

CRITICAL: Trains on collective intelligence data without exposing client data.

Usage:
    python scripts/run_v2_training.py
    python scripts/run_v2_training.py --dry-run
    python scripts/run_v2_training.py --config path/to/config.json
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_lightning.v2.training_executor import (
    TrainingExecutor,
    TrainingStatus,
)
from agent_lightning.v2.collective_trainer import (
    CollectiveTrainer,
    CollectiveTrainingConfig,
)
from agent_lightning.v2.hyperparameter_optimizer import (
    HyperparameterOptimizer,
    OptimizationStrategy,
    HyperparameterConfig,
)
from agent_lightning.v2.training_monitor import TrainingMonitor
from agent_lightning.v2.training_results import (
    TrainingResults,
    create_training_results,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class TrainingPipeline:
    """
    Complete training pipeline for Agent Lightning v2.

    Features:
    - Pre-training validation
    - Training execution
    - Post-training validation
    - Results reporting
    - Dry-run mode for testing
    """

    # Default configuration
    DEFAULT_CONFIG = {
        # Model
        "model_path": "models/base",
        "output_dir": "models/lightning_v2",
        # Training
        "num_epochs": 3,
        "batch_size": 8,
        "learning_rate": 2e-5,
        "warmup_steps": 100,
        # Hyperparameter optimization
        "optimize_hyperparameters": False,
        "optimization_trials": 10,
        # Monitoring
        "enable_monitoring": True,
        "checkpoint_steps": 100,
        # Target
        "target_accuracy": 0.77,
        "baseline_accuracy": 0.72,
        # Collective intelligence
        "use_collective_intelligence": True,
        "collective_samples": 578,
    }

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ):
        """
        Initialize training pipeline.

        Args:
            config: Configuration override
            dry_run: If True, simulate training without actual execution
        """
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.dry_run = dry_run

        self._monitor: Optional[TrainingMonitor] = None
        self._results: Optional[TrainingResults] = None

    def run(self) -> Dict[str, Any]:
        """
        Execute full training pipeline.

        Returns:
            Training results
        """
        training_id = self._generate_training_id()
        start_time = datetime.now()

        logger.info("=" * 60)
        logger.info("Agent Lightning v2 Training Pipeline")
        logger.info(f"Training ID: {training_id}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info("=" * 60)

        try:
            # Phase 1: Pre-training validation
            logger.info("\n[Phase 1] Pre-training Validation")
            pre_validation = self._pre_training_validation()

            if not pre_validation["passed"]:
                raise RuntimeError(
                    f"Pre-training validation failed: {pre_validation['errors']}"
                )

            # Phase 2: Hyperparameter optimization (optional)
            logger.info("\n[Phase 2] Hyperparameter Optimization")
            best_config = self._optimize_hyperparameters()

            # Phase 3: Training execution
            logger.info("\n[Phase 3] Training Execution")
            training_results = self._execute_training(training_id, best_config)

            # Phase 4: Post-training validation
            logger.info("\n[Phase 4] Post-training Validation")
            post_validation = self._post_training_validation(training_results)

            # Phase 5: Results compilation
            logger.info("\n[Phase 5] Results Compilation")
            self._results = self._compile_results(
                training_id,
                training_results,
                start_time,
            )

            return {
                "success": True,
                "training_id": training_id,
                "results": self._results.to_dict() if self._results else None,
                "validation": post_validation,
            }

        except Exception as e:
            logger.error(f"Training pipeline failed: {e}")
            return {
                "success": False,
                "training_id": training_id,
                "error": str(e),
            }

    def _pre_training_validation(self) -> Dict[str, Any]:
        """Validate pre-training conditions"""
        errors = []
        warnings = []

        # Check output directory
        output_dir = self.config["output_dir"]
        if not self.dry_run:
            os.makedirs(output_dir, exist_ok=True)

        # Check collective intelligence data
        if self.config["use_collective_intelligence"]:
            collective_samples = self.config["collective_samples"]
            if collective_samples < 100:
                warnings.append(
                    f"Low collective intelligence samples: {collective_samples}"
                )

        # Check target accuracy is achievable
        target = self.config["target_accuracy"]
        baseline = self.config["baseline_accuracy"]
        if target - baseline > 0.15:  # More than 15% improvement
            warnings.append(
                f"Target improvement may be too aggressive: "
                f"{baseline:.1%} → {target:.1%}"
            )

        passed = len(errors) == 0

        logger.info(f"  Output directory: {output_dir}")
        logger.info(f"  Collective samples: {self.config['collective_samples']}")
        logger.info(f"  Validation: {'PASSED' if passed else 'FAILED'}")

        return {
            "passed": passed,
            "errors": errors,
            "warnings": warnings,
        }

    def _optimize_hyperparameters(self) -> HyperparameterConfig:
        """Run hyperparameter optimization if enabled"""
        if not self.config["optimize_hyperparameters"]:
            logger.info("  Using default hyperparameters")
            return HyperparameterConfig()

        logger.info(
            f"  Running hyperparameter optimization "
            f"({self.config['optimization_trials']} trials)"
        )

        if self.dry_run:
            return HyperparameterConfig()

        optimizer = HyperparameterOptimizer(
            n_trials=self.config["optimization_trials"],
            target_accuracy=self.config["target_accuracy"],
        )

        best_config, best_accuracy = optimizer.optimize()

        logger.info(f"  Best accuracy found: {best_accuracy:.4f}")
        logger.info(f"  Best learning rate: {best_config.learning_rate}")
        logger.info(f"  Best batch size: {best_config.batch_size}")

        return best_config

    def _execute_training(
        self,
        training_id: str,
        config: HyperparameterConfig,
    ) -> Dict[str, Any]:
        """Execute training"""
        if self.dry_run:
            logger.info("  [DRY RUN] Simulating training...")
            return self._simulate_training(training_id, config)

        # Initialize monitor
        if self.config["enable_monitoring"]:
            output_dir = os.path.join(
                self.config["output_dir"],
                training_id,
            )
            self._monitor = TrainingMonitor(output_dir=output_dir)
            self._monitor.start_monitoring()

        # Initialize collective trainer
        collective_config = CollectiveTrainingConfig(
            target_accuracy=self.config["target_accuracy"],
        )
        trainer = CollectiveTrainer(config=collective_config)

        # Execute training
        def on_progress(progress):
            if self._monitor:
                self._monitor.record_step(
                    step=progress.step,
                    epoch=progress.epoch,
                    loss=0.5 - (progress.accuracy - 0.72),  # Approximate
                    accuracy=progress.accuracy,
                )

        results = trainer.train(
            num_epochs=config.num_epochs,
            batch_size=config.batch_size,
            on_progress=on_progress,
        )

        # Stop monitor
        if self._monitor:
            monitor_summary = self._monitor.stop_monitoring()
            results["monitoring"] = monitor_summary

        # Validate privacy
        privacy_validation = trainer.validate_privacy()
        if not all(privacy_validation.values()):
            raise RuntimeError("Privacy validation failed")

        logger.info(f"  Final accuracy: {results['final_accuracy']:.4f}")
        logger.info(f"  Target met: {results['target_met']}")

        return results

    def _simulate_training(
        self,
        training_id: str,
        config: HyperparameterConfig,
    ) -> Dict[str, Any]:
        """Simulate training for dry run"""
        # Simulate improvement
        baseline = self.config["baseline_accuracy"]
        improvement = 0.05 + 0.02 * (config.num_epochs / 3)  # ~5-7% improvement
        final_accuracy = baseline + improvement

        return {
            "total_steps": 500,
            "total_epochs": config.num_epochs,
            "duration_seconds": 60.0,
            "final_accuracy": final_accuracy,
            "industry_accuracies": {
                "ecommerce": final_accuracy + 0.01,
                "saas": final_accuracy + 0.005,
                "healthcare": final_accuracy - 0.01,
                "logistics": final_accuracy,
                "fintech": final_accuracy + 0.008,
            },
            "target_met": final_accuracy >= self.config["target_accuracy"],
            "best_accuracy": final_accuracy,
        }

    def _post_training_validation(
        self,
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate post-training results"""
        errors = []
        warnings = []

        # Check accuracy target
        if not results.get("target_met"):
            warnings.append(
                f"Target accuracy not met: "
                f"{results['final_accuracy']:.1%} < {self.config['target_accuracy']:.1%}"
            )

        # Check industry consistency
        industry_accs = results.get("industry_accuracies", {})
        if industry_accs:
            min_acc = min(industry_accs.values())
            max_acc = max(industry_accs.values())
            spread = max_acc - min_acc

            if spread > 0.05:  # More than 5% spread
                warnings.append(
                    f"High industry accuracy spread: {spread:.1%}"
                )

        passed = len(errors) == 0

        logger.info(f"  Validation: {'PASSED' if passed else 'FAILED'}")

        return {
            "passed": passed,
            "errors": errors,
            "warnings": warnings,
        }

    def _compile_results(
        self,
        training_id: str,
        training_results: Dict[str, Any],
        start_time: datetime,
    ) -> TrainingResults:
        """Compile final results"""
        duration = (datetime.now() - start_time).total_seconds()

        results = create_training_results(
            training_id=training_id,
            final_accuracy=training_results.get("final_accuracy", 0.75),
            total_epochs=training_results.get("total_epochs", 3),
            total_steps=training_results.get("total_steps", 500),
            training_time_seconds=duration,
            config=self.config,
        )

        # Save results
        output_path = os.path.join(
            self.config["output_dir"],
            training_id,
            "training_results.json",
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        results.save(output_path)

        logger.info(f"  Results saved: {output_path}")

        return results

    def _generate_training_id(self) -> str:
        """Generate unique training ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"train_{timestamp}"


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Agent Lightning v2 Training Runner"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration JSON file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate training without actual execution",
    )
    parser.add_argument(
        "--target-accuracy",
        type=float,
        default=0.77,
        help="Target accuracy (default: 0.77)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Number of training epochs (default: 3)",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Run hyperparameter optimization",
    )

    args = parser.parse_args()

    # Load configuration
    config = {}
    if args.config:
        with open(args.config, "r") as f:
            config = json.load(f)

    # Apply command-line overrides
    config["target_accuracy"] = args.target_accuracy
    config["num_epochs"] = args.epochs
    config["optimize_hyperparameters"] = args.optimize

    # Run pipeline
    pipeline = TrainingPipeline(config=config, dry_run=args.dry_run)
    results = pipeline.run()

    # Print summary
    print("\n" + "=" * 60)
    print("Training Summary")
    print("=" * 60)
    print(f"Success: {results['success']}")
    print(f"Training ID: {results['training_id']}")

    if results["success"] and results.get("results"):
        r = results["results"]
        print(f"Final Accuracy: {r['final_accuracy']:.2%}")
        print(f"Improvement: +{r['improvement_percentage']:.1f}%")
        print(f"Target Met: {'YES' if r['target_met'] else 'NO'}")
        print(f"Training Time: {r['total_training_time_seconds']:.1f}s")
    elif results.get("error"):
        print(f"Error: {results['error']}")

    return 0 if results["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
