"""
Batch Client Setup Script
Onboard multiple clients efficiently
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    client_id: str
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class SetupResult:
    client_id: str
    success: bool
    message: str
    files_created: List[str] = field(default_factory=list)


class BatchClientSetup:
    def __init__(self, base_path: str = "clients"):
        self.base_path = Path(base_path)
        
    def validate_client_config(self, config: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []
        
        required_fields = ["client_id", "client_name", "industry", "variant"]
        for f in required_fields:
            if f not in config:
                errors.append(f"Missing required field: {f}")
        
        if "client_id" in config and not config["client_id"].startswith("client_"):
            errors.append("client_id must start with 'client_'")
        
        valid_variants = ["parwa_junior", "parwa_mid", "parwa_high"]
        if "variant" in config and config["variant"] not in valid_variants:
            errors.append(f"Invalid variant. Must be one of: {valid_variants}")
        
        return ValidationResult(
            client_id=config.get("client_id", "unknown"),
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def validate_existing_client(self, client_id: str) -> ValidationResult:
        config_path = self.base_path / client_id / "config.py"
        
        if not config_path.exists():
            return ValidationResult(
                client_id=client_id,
                is_valid=False,
                errors=[f"Client config not found: {config_path}"]
            )
        
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("config", config_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, "config"):
                config = {
                    "client_id": getattr(module.config, "client_id", ""),
                    "client_name": getattr(module.config, "client_name", ""),
                    "industry": getattr(module.config, "industry", ""),
                    "variant": getattr(module.config, "variant", "")
                }
                return self.validate_client_config(config)
            
            return ValidationResult(client_id=client_id, is_valid=True, warnings=["Config loaded but could not validate all fields"])
        except Exception as e:
            return ValidationResult(client_id=client_id, is_valid=False, errors=[f"Failed to load config: {str(e)}"])
    
    def create_client_directory(self, client_id: str) -> bool:
        client_path = self.base_path / client_id
        
        if client_path.exists():
            logger.info(f"Directory already exists: {client_path}")
            return True
        
        try:
            client_path.mkdir(parents=True, exist_ok=True)
            (client_path / "knowledge_base").mkdir(exist_ok=True)
            logger.info(f"Created directory: {client_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create directory: {e}")
            return False
    
    def initialize_knowledge_base(self, client_id: str, faqs: List[Dict]) -> bool:
        kb_path = self.base_path / client_id / "knowledge_base" / "faq.json"
        
        try:
            faq_data = {
                "client_id": client_id,
                "created_at": datetime.now().isoformat(),
                "faqs": faqs
            }
            
            with open(kb_path, 'w') as f:
                json.dump(faq_data, f, indent=2)
            
            logger.info(f"Created knowledge base: {kb_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create knowledge base: {e}")
            return False
    
    def create_monitoring_dashboard(self, client_id: str) -> Dict[str, Any]:
        return {
            "dashboard": {
                "title": f"{client_id} Dashboard",
                "panels": [
                    {"title": "Ticket Volume", "type": "graph", "metrics": ["tickets.total", "tickets.resolved"]},
                    {"title": "Response Time", "type": "gauge", "metrics": ["response.avg_ms", "response.p95_ms"]},
                    {"title": "Accuracy", "type": "gauge", "metrics": ["accuracy.rate"]}
                ]
            }
        }
    
    def generate_setup_report(self, results: List[SetupResult]) -> Dict[str, Any]:
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_clients": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "clients": [{"client_id": r.client_id, "success": r.success, "message": r.message} for r in results]
        }
    
    def setup_batch(self, clients: List[Dict[str, Any]]) -> List[SetupResult]:
        results = []
        
        for client in clients:
            client_id = client.get("client_id")
            
            if not client_id:
                results.append(SetupResult(client_id="unknown", success=False, message="Missing client_id"))
                continue
            
            validation = self.validate_client_config(client)
            if not validation.is_valid:
                results.append(SetupResult(client_id=client_id, success=False, message=f"Validation failed: {validation.errors}"))
                continue
            
            if not self.create_client_directory(client_id):
                results.append(SetupResult(client_id=client_id, success=False, message="Failed to create directory"))
                continue
            
            files_created = []
            if "faqs" in client:
                if self.initialize_knowledge_base(client_id, client["faqs"]):
                    files_created.append("knowledge_base/faq.json")
            
            results.append(SetupResult(client_id=client_id, success=True, message="Client setup complete", files_created=files_created))
        
        return results


def validate_batch(clients: List[str], base_path: str = "clients") -> List[ValidationResult]:
    setup = BatchClientSetup(base_path)
    return [setup.validate_existing_client(cid) for cid in clients]


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch Client Setup")
    parser.add_argument("--validate", nargs="+", help="Validate existing clients")
    parser.add_argument("--report", action="store_true", help="Generate setup report")
    args = parser.parse_args()
    
    if args.validate:
        results = validate_batch(args.validate)
        for result in results:
            status = "✅ VALID" if result.is_valid else "❌ INVALID"
            print(f"{result.client_id}: {status}")
            if result.errors:
                for error in result.errors:
                    print(f"  Error: {error}")
    
    if args.report:
        setup = BatchClientSetup()
        report = setup.generate_setup_report([])
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
