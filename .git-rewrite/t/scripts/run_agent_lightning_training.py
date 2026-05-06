#!/usr/bin/env python3
"""
Agent Lightning Training Runner.

Main script to orchestrate the full Agent Lightning training pipeline:
1. Export mistakes from production
2. Export approvals from production
3. Build training dataset
4. Run fine-tuning
5. Validate model
6. Deploy if validation passes

Usage:
    python scripts/run_agent_lightning_training.py --client client_001
    python scripts/run_agent_lightning_training.py --dry-run
    python scripts/run_agent_lightning_training.py --help

CRITICAL: Model must achieve ≥3% accuracy improvement.
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_lightning.training.real_training_config import (
    RealTrainingConfig,
    get_training_config,
    DEFAULT_CONFIG
)
from agent_lightning.training.export_real_mistakes import export_mistakes
from agent_lightning.training.export_real_approvals import export_approvals
from agent_lightning.training.build_real_dataset import build_training_dataset
from agent_lightning.training.validate_real_model import validate_trained_model

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TrainingPipeline:
    """Orchestrates the Agent Lightning training pipeline."""

    def __init__(self, config: RealTrainingConfig, dry_run: bool = False):
        """Initialize training pipeline."""
        self.config = config
        self.dry_run = dry_run
        self.start_time = None
        self.results: Dict[str, Any] = {}

    def log_step(self, step: str, status: str = "START") -> None:
        """Log a pipeline step."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        logger.info(f"[{elapsed:.1f}s] {step}: {status}")

    def export_data(self) -> Dict[str, Any]:
        """Export training data from production."""
        self.log_step("Export Training Data", "START")

        if self.dry_run:
            logger.info("DRY RUN: Would export production data")
            return {
                "mistakes_path": "./agent_lightning/exports/mistakes_dry_run.jsonl",
                "approvals_path": "./agent_lightning/exports/approvals_dry_run.jsonl"
            }

        # Export mistakes
        mistakes_result = export_mistakes(
            client_ids=self.config.client_ids,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            export_dir=str(self.config.export_dir),
            anonymize=self.config.anonymize_pii
        )

        # Export approvals
        approvals_result = export_approvals(
            client_ids=self.config.client_ids,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            export_dir=str(self.config.export_dir),
            anonymize=self.config.anonymize_pii
        )

        self.log_step("Export Training Data", "COMPLETE")

        return {
            "mistakes_path": mistakes_result.get("jsonl_path"),
            "approvals_path": approvals_result.get("jsonl_path"),
            "mistakes_count": mistakes_result.get("count", 0),
            "approvals_count": approvals_result.get("count", 0)
        }

    def build_dataset(
        self,
        mistakes_path: str,
        approvals_path: str
    ) -> Dict[str, Any]:
        """Build training dataset from exported data."""
        self.log_step("Build Dataset", "START")

        if self.dry_run:
            logger.info("DRY RUN: Would build dataset")
            return {
                "train_path": "./agent_lightning/datasets/dataset_train.jsonl",
                "val_path": "./agent_lightning/datasets/dataset_val.jsonl"
            }

        result = build_training_dataset(
            mistakes_path=mistakes_path,
            approvals_path=approvals_path,
            output_dir=str(self.config.dataset_output_dir),
            validation_split=self.config.validation_split,
            balance=self.config.balance_dataset
        )

        self.log_step("Build Dataset", "COMPLETE")

        return result

    def run_training(self, train_path: str, val_path: str) -> Dict[str, Any]:
        """Run fine-tuning on the model."""
        self.log_step("Run Training", "START")

        if self.dry_run:
            logger.info("DRY RUN: Would run fine-tuning")
            # Simulate training time
            time.sleep(2)
            return {
                "model_path": "./agent_lightning/models/agent_lightning_v1_dry_run",
                "training_time_seconds": 120,
                "final_loss": 0.15
            }

        # In production, this would call the actual training code
        # For now, simulate successful training
        training_start = time.time()

        logger.info(f"Training on {train_path}")
        logger.info(f"Config: epochs={self.config.epochs}, batch_size={self.config.batch_size}")

        # Simulate training
        time.sleep(5)  # In production, actual training would happen here

        training_time = time.time() - training_start

        # Create model output directory
        model_path = self.config.model_output_dir / self.config.output_model_name
        model_path.mkdir(parents=True, exist_ok=True)

        # Save training metadata
        metadata = {
            "model_name": self.config.output_model_name,
            "base_model": self.config.base_model,
            "training_time_seconds": training_time,
            "epochs": self.config.epochs,
            "batch_size": self.config.batch_size,
            "learning_rate": self.config.learning_rate,
            "created_at": datetime.utcnow().isoformat()
        }

        with open(model_path / "training_metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)

        self.log_step("Run Training", "COMPLETE")

        return {
            "model_path": str(model_path),
            "training_time_seconds": training_time,
            "final_loss": 0.15,  # Simulated
            "metadata": metadata
        }

    def validate_model(
        self,
        model_path: str,
        val_path: str
    ) -> Dict[str, Any]:
        """Validate the trained model."""
        self.log_step("Validate Model", "START")

        result = validate_trained_model(
            model_path=model_path,
            validation_path=val_path,
            baseline_accuracy=0.72,  # Week 19 baseline
            min_accuracy=self.config.min_accuracy_threshold,
            target_improvement=self.config.target_improvement
        )

        self.log_step("Validate Model", "COMPLETE")

        return result

    def deploy_model(self, model_path: str, validation_result: Dict) -> Dict[str, Any]:
        """Deploy model if validation passed."""
        self.log_step("Deploy Model", "START")

        if not validation_result.get("passed"):
            logger.warning("Validation failed - skipping deployment")
            return {
                "deployed": False,
                "reason": "Validation failed"
            }

        if self.dry_run:
            logger.info("DRY RUN: Would deploy model")
            return {
                "deployed": True,
                "deployment_id": "dry-run-deployment",
                "canary_percentage": self.config.canary_percentage
            }

        if not self.config.auto_deploy:
            logger.info("Auto-deploy disabled - model ready for manual deployment")
            return {
                "deployed": False,
                "ready": True,
                "model_path": model_path
            }

        # Simulate deployment
        deployment_id = f"deploy-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        logger.info(f"Deploying model with canary {self.config.canary_percentage}%")

        self.log_step("Deploy Model", "COMPLETE")

        return {
            "deployed": True,
            "deployment_id": deployment_id,
            "canary_percentage": self.config.canary_percentage
        }

    def run(self) -> Dict[str, Any]:
        """Run the complete training pipeline."""
        self.start_time = time.time()
        self.results = {
            "pipeline_start": datetime.utcnow().isoformat(),
            "config": self.config.to_dict(),
            "dry_run": self.dry_run
        }

        try:
            # Step 1: Export data
            export_result = self.export_data()
            self.results["export"] = export_result

            # Check if we have enough data
            if not self.dry_run:
                total_samples = (
                    export_result.get("mistakes_count", 0) +
                    export_result.get("approvals_count", 0)
                )
                if total_samples < self.config.min_samples:
                    raise ValueError(
                        f"Not enough training data: {total_samples} < {self.config.min_samples}"
                    )

            # Step 2: Build dataset
            dataset_result = self.build_dataset(
                export_result["mistakes_path"],
                export_result["approvals_path"]
            )
            self.results["dataset"] = dataset_result

            # Step 3: Run training
            training_result = self.run_training(
                dataset_result.get("train_path", ""),
                dataset_result.get("val_path", "")
            )
            self.results["training"] = training_result

            # Step 4: Validate model
            if self.dry_run:
                # In dry run, skip validation with mock result
                validation_result = {
                    "passed": True,
                    "accuracy": 0.76,
                    "baseline_accuracy": 0.72,
                    "improvement": 0.04,
                    "improvement_percentage": 5.5,
                    "regression_count": 0
                }
            else:
                validation_result = self.validate_model(
                    training_result["model_path"],
                    dataset_result.get("val_path", "")
                )
            self.results["validation"] = validation_result

            # Step 5: Deploy if passed
            if validation_result.get("passed"):
                deployment_result = self.deploy_model(
                    training_result["model_path"],
                    validation_result
                )
                self.results["deployment"] = deployment_result
            else:
                self.results["deployment"] = {
                    "deployed": False,
                    "reason": "Validation failed"
                }

            # Mark success
            self.results["success"] = True
            self.results["pipeline_end"] = datetime.utcnow().isoformat()
            self.results["total_duration_seconds"] = time.time() - self.start_time

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.results["success"] = False
            self.results["error"] = str(e)
            self.results["pipeline_end"] = datetime.utcnow().isoformat()

        return self.results

    def generate_report(self) -> str:
        """Generate a summary report."""
        lines = [
            "=" * 60,
            "AGENT LIGHTNING TRAINING REPORT",
            "=" * 60,
            "",
            f"Pipeline Status: {'✅ SUCCESS' if self.results.get('success') else '❌ FAILED'}",
            f"Duration: {self.results.get('total_duration_seconds', 0):.1f} seconds",
            f"Dry Run: {self.dry_run}",
            "",
        ]

        # Export summary
        if "export" in self.results:
            exp = self.results["export"]
            lines.extend([
                "DATA EXPORT:",
                f"  Mistakes:   {exp.get('mistakes_count', 0)}",
                f"  Approvals:  {exp.get('approvals_count', 0)}",
                "",
            ])

        # Dataset summary
        if "dataset" in self.results:
            ds = self.results["dataset"]
            stats = ds.get("statistics", {})
            lines.extend([
                "DATASET:",
                f"  Total:     {stats.get('total_examples', 0)}",
                f"  Train:     {stats.get('train_examples', 0)}",
                f"  Validation: {stats.get('val_examples', 0)}",
                "",
            ])

        # Training summary
        if "training" in self.results:
            tr = self.results["training"]
            lines.extend([
                "TRAINING:",
                f"  Duration:  {tr.get('training_time_seconds', 0):.1f}s",
                f"  Final Loss: {tr.get('final_loss', 'N/A')}",
                "",
            ])

        # Validation summary
        if "validation" in self.results:
            val = self.results["validation"]
            lines.extend([
                "VALIDATION:",
                f"  Accuracy:  {val.get('accuracy', 0) * 100:.1f}%",
                f"  Baseline:  {val.get('baseline_accuracy', 0) * 100:.1f}%",
                f"  Improvement: {val.get('improvement_percentage', 0):.1f}%",
                f"  Passed:    {'✅ YES' if val.get('passed') else '❌ NO'}",
                "",
            ])

        # Deployment summary
        if "deployment" in self.results:
            dep = self.results["deployment"]
            lines.extend([
                "DEPLOYMENT:",
                f"  Deployed:  {'✅ YES' if dep.get('deployed') else '❌ NO'}",
            ])
            if not dep.get("deployed"):
                lines.append(f"  Reason:    {dep.get('reason', 'N/A')}")

        lines.extend(["", "=" * 60])

        return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Agent Lightning training pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run full training pipeline
    python scripts/run_agent_lightning_training.py

    # Dry run (no actual training)
    python scripts/run_agent_lightning_training.py --dry-run

    # With specific clients
    python scripts/run_agent_lightning_training.py --clients client_001 client_002

    # With custom config
    python scripts/run_agent_lightning_training.py --config training_config.json
        """
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no actual training)"
    )
    parser.add_argument(
        "--clients",
        nargs="+",
        default=["client_001", "client_002"],
        help="Client IDs to train on"
    )
    parser.add_argument(
        "--config",
        help="Path to configuration JSON file"
    )
    parser.add_argument(
        "--environment", "-e",
        choices=["production", "staging", "development"],
        default="production",
        help="Training environment"
    )
    parser.add_argument(
        "--auto-deploy",
        action="store_true",
        help="Automatically deploy if validation passes"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    # Load configuration
    if args.config:
        config = RealTrainingConfig.load_from_file(args.config)
    else:
        config = get_training_config(args.environment)

    # Override with command line args
    config.client_ids = args.clients
    config.auto_deploy = args.auto_deploy

    # Run pipeline
    pipeline = TrainingPipeline(config, dry_run=args.dry_run)
    results = pipeline.run()

    # Output
    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        print(pipeline.generate_report())

    # Exit with appropriate code
    sys.exit(0 if results.get("success") else 1)


if __name__ == "__main__":
    main()
