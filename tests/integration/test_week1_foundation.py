import os
import pytest
import yaml

# Define the root of the project to check paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

def test_monorepo_directory_structure():
    """Verify that all required top-level and essential sub-directories exist."""
    required_dirs = [
        "frontend",
        "backend",
        "worker",
        "shared",
        "shared/core_functions",
        "docs",
        "docs/bdd_scenarios",
        "docs/architecture_decisions",
        "docs/weekly_logs", 
        "legal",
        "feature_flags",
        "tests",
        "tests/unit",
        "tests/integration",
        "tests/e2e",
        "tests/performance",
        "tests/security"
    ]
    
    for relative_path in required_dirs:
        dir_path = os.path.join(PROJECT_ROOT, relative_path)
        assert os.path.isdir(dir_path), f"CRITICAL: Missing directory {relative_path}"

def test_docker_compose_configuration():
    """Parse docker-compose.yml and verify the 5 required services exist."""
    docker_file = os.path.join(PROJECT_ROOT, "docker-compose.yml")
    assert os.path.isfile(docker_file), "Missing docker-compose.yml"
    
    with open(docker_file, 'r', encoding="utf-8") as f:
        compose_data = yaml.safe_load(f)
        
    assert "services" in compose_data, "docker-compose.yml has no 'services' block"
    services = compose_data["services"]
    
    expected_services = ["frontend", "backend", "worker", "db", "redis"]
    for svc in expected_services:
        assert svc in services, f"Missing required Docker service: {svc}"

def test_core_functions_module_imports():
    """Verify that all 5 core python modules built this week can be imported."""
    
    try:
        from shared.core_functions import config
        from shared.core_functions import logger
        from shared.core_functions import security
        from shared.core_functions import ai_safety
        from shared.core_functions import compliance
        from shared.core_functions import audit_trail
        from shared.core_functions import pricing_optimizer
    except ImportError as e:
        pytest.fail(f"Failed to import a core python module: {e}")

def test_feature_flags_exist():
    """Verify the 3 pricing tier JSON configs exist."""
    flags_dir = os.path.join(PROJECT_ROOT, "feature_flags")
    
    assert os.path.isfile(os.path.join(flags_dir, "mini_parwa_flags.json"))
    assert os.path.isfile(os.path.join(flags_dir, "parwa_flags.json"))
    assert os.path.isfile(os.path.join(flags_dir, "parwa_high_flags.json"))

def test_legal_and_bdd_docs_exist():
    """Verify all 9 Markdown documents (Legal, BDD, ADRs) from Week 1 exist."""
    
    legal_dir = os.path.join(PROJECT_ROOT, "legal")
    assert os.path.isfile(os.path.join(legal_dir, "privacy_policy.md"))
    assert os.path.isfile(os.path.join(legal_dir, "terms_of_service.md"))
    assert os.path.isfile(os.path.join(legal_dir, "data_processing_agreement.md"))
    assert os.path.isfile(os.path.join(legal_dir, "liability_limitations.md"))
    assert os.path.isfile(os.path.join(legal_dir, "tcpa_compliance_guide.md"))
    
    bdd_dir = os.path.join(PROJECT_ROOT, "docs", "bdd_scenarios")
    assert os.path.isfile(os.path.join(bdd_dir, "mini_parwa_bdd.md"))
    assert os.path.isfile(os.path.join(bdd_dir, "parwa_bdd.md"))
    assert os.path.isfile(os.path.join(bdd_dir, "parwa_high_bdd.md"))
    
    adr_dir = os.path.join(PROJECT_ROOT, "docs", "architecture_decisions")
    assert os.path.isfile(os.path.join(adr_dir, "001_monorepo_choice.md"))
    assert os.path.isfile(os.path.join(adr_dir, "002_smart_router_design.md"))
    assert os.path.isfile(os.path.join(adr_dir, "003_agent_lightning.md"))
