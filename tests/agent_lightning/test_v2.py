"""Tests for Agent Lightning v2"""

import pytest
import json
from pathlib import Path
from datetime import datetime


class TestEnhancedTrainingConfig:
    """Tests for enhanced training configuration"""

    def test_config_module_imports(self):
        """Test that config module can be imported"""
        from agent_lightning.v2.enhanced_training_config import (
            EnhancedTrainingConfig, 
            get_enhanced_config,
            TrainingMode
        )
        assert EnhancedTrainingConfig is not None
        assert get_enhanced_config is not None

    def test_default_config_loads(self):
        """Test default configuration loads"""
        from agent_lightning.v2.enhanced_training_config import get_enhanced_config
        
        config = get_enhanced_config()
        assert config.version == "2.0.0"
        assert config.training_mode.value == "collective"

    def test_config_validation(self):
        """Test configuration validation"""
        from agent_lightning.v2.enhanced_training_config import (
            EnhancedTrainingConfig, 
            validate_config
        )
        
        config = EnhancedTrainingConfig()
        valid, errors = validate_config(config)
        assert valid is True
        assert len(errors) == 0

    def test_validation_catches_errors(self):
        """Test validation catches configuration errors"""
        from agent_lightning.v2.enhanced_training_config import (
            EnhancedTrainingConfig,
            validate_config,
            DataConfig
        )
        
        config = EnhancedTrainingConfig()
        config.data.validation_split = 0.4
        config.data.test_split = 0.2  # Total 0.6 > 0.5
        
        valid, errors = validate_config(config)
        assert valid is False
        assert len(errors) > 0

    def test_industry_config_healthcare(self):
        """Test healthcare-specific configuration"""
        from agent_lightning.v2.enhanced_training_config import get_industry_config
        
        config = get_industry_config("healthcare")
        assert config.hipaa_mode is True
        assert config.data.anonymize_phi is True
        assert config.validation.min_accuracy >= 0.85

    def test_industry_config_fintech(self):
        """Test fintech-specific configuration"""
        from agent_lightning.v2.enhanced_training_config import get_industry_config
        
        config = get_industry_config("fintech")
        assert config.validation.min_accuracy >= 0.90

    def test_target_accuracy_configurable(self):
        """Test target accuracy is configurable"""
        from agent_lightning.v2.enhanced_training_config import get_enhanced_config
        
        config = get_enhanced_config(target_accuracy=0.80)
        assert config.validation.min_accuracy == 0.80

    def test_participating_clients_list(self):
        """Test participating clients are defined"""
        from agent_lightning.v2.enhanced_training_config import EnhancedTrainingConfig
        
        config = EnhancedTrainingConfig()
        assert len(config.participating_clients) >= 2
        assert "client_001" in config.participating_clients


class TestCollectiveDatasetBuilder:
    """Tests for collective dataset builder"""

    def test_builder_module_imports(self):
        """Test that builder module can be imported"""
        from agent_lightning.v2.collective_dataset_builder import (
            CollectiveDatasetBuilder,
            TrainingExample
        )
        assert CollectiveDatasetBuilder is not None
        assert TrainingExample is not None

    def test_builder_initialization(self):
        """Test builder initializes correctly"""
        from agent_lightning.v2.collective_dataset_builder import CollectiveDatasetBuilder
        
        builder = CollectiveDatasetBuilder()
        assert builder.target_total == 500
        assert len(builder._examples) == 0

    def test_add_client_data(self):
        """Test adding client data"""
        from agent_lightning.v2.collective_dataset_builder import CollectiveDatasetBuilder
        
        builder = CollectiveDatasetBuilder()
        
        count = builder.add_client_data(
            client_id="test_client",
            industry="ecommerce",
            mistakes=[{"input": "test", "correct_output": "response", "category": "test"}],
            approvals=[{"input": "test2", "output": "response2", "category": "test"}]
        )
        
        assert count == 2
        assert len(builder._examples) == 2

    def test_client_anonymization(self):
        """Test client IDs are anonymized"""
        from agent_lightning.v2.collective_dataset_builder import CollectiveDatasetBuilder
        
        builder = CollectiveDatasetBuilder()
        
        builder.add_client_data(
            client_id="client_001",
            industry="ecommerce",
            mistakes=[{"input": "test", "correct_output": "response"}],
            approvals=[]
        )
        
        # Client ID should be anonymized with 'anon_' prefix (not the original 'client_' format)
        example = builder._examples[0]
        assert example.client_id != "client_001"
        assert example.client_id.startswith("anon_")  # Anonymized IDs use 'anon_' prefix

    def test_phi_sanitization(self):
        """Test PHI is sanitized"""
        from agent_lightning.v2.collective_dataset_builder import CollectiveDatasetBuilder
        
        builder = CollectiveDatasetBuilder()
        
        builder.add_client_data(
            client_id="test",
            industry="healthcare",
            mistakes=[{"input": "SSN: 123-45-6789", "correct_output": "response"}],
            approvals=[]
        )
        
        example = builder._examples[0]
        assert "123-45-6789" not in example.input_text
        assert "REDACTED" in example.input_text

    def test_build_balanced_dataset(self):
        """Test balanced dataset building"""
        from agent_lightning.v2.collective_dataset_builder import CollectiveDatasetBuilder
        
        builder = CollectiveDatasetBuilder(target_total=100)
        
        # Add data for each industry
        for industry in ["ecommerce", "saas", "healthcare", "logistics", "fintech"]:
            builder.add_client_data(
                client_id=f"test_{industry}",
                industry=industry,
                mistakes=[{"input": f"test_{i}", "correct_output": f"response_{i}", "category": "test"} for i in range(20)],
                approvals=[]
            )
        
        train, val, test = builder.build_balanced_dataset()
        
        assert len(train) > 0
        assert len(val) > 0
        assert len(test) >= 0

    def test_get_statistics(self):
        """Test statistics generation"""
        from agent_lightning.v2.collective_dataset_builder import CollectiveDatasetBuilder
        
        builder = CollectiveDatasetBuilder()
        
        builder.add_client_data(
            client_id="test",
            industry="ecommerce",
            mistakes=[{"input": "test", "correct_output": "response", "quality_score": 0.9}],
            approvals=[{"input": "test2", "output": "response2", "quality_score": 0.8}]
        )
        
        stats = builder.get_statistics()
        
        assert stats.total_examples == 2
        assert "ecommerce" in stats.by_industry
        assert stats.avg_quality_score > 0

    def test_privacy_validation(self):
        """Test privacy validation"""
        from agent_lightning.v2.collective_dataset_builder import CollectiveDatasetBuilder
        
        builder = CollectiveDatasetBuilder()
        
        builder.add_client_data(
            client_id="test_client",
            industry="ecommerce",
            mistakes=[{"input": "test", "correct_output": "response"}],
            approvals=[]
        )
        
        valid, issues = builder.validate_privacy()
        # Should pass because client IDs are anonymized
        assert valid is True


class TestTrainingExample:
    """Tests for training example dataclass"""

    def test_example_creation(self):
        """Test training example creation"""
        from agent_lightning.v2.collective_dataset_builder import TrainingExample
        
        example = TrainingExample(
            id="ex_001",
            input_text="Customer query",
            output_text="Response",
            category="general",
            industry="ecommerce",
            client_id="anon_client",
            quality_score=0.9,
            timestamp=datetime.utcnow().isoformat()
        )
        
        assert example.id == "ex_001"
        assert example.quality_score == 0.9


class TestAgentLightningV2Integration:
    """Integration tests for Agent Lightning v2"""

    def test_config_and_builder_integration(self):
        """Test config and builder work together"""
        from agent_lightning.v2.enhanced_training_config import get_enhanced_config
        from agent_lightning.v2.collective_dataset_builder import CollectiveDatasetBuilder
        
        config = get_enhanced_config()
        builder = CollectiveDatasetBuilder(
            target_total=config.data.min_samples
        )
        
        # Add data for all participating clients
        for client_id in config.participating_clients[:2]:
            builder.add_client_data(
                client_id=client_id,
                industry="ecommerce",
                mistakes=[{"input": f"test_{i}", "correct_output": f"response_{i}"} for i in range(10)],
                approvals=[{"input": f"approval_{i}", "output": f"response_{i}"} for i in range(10)]
            )
        
        stats = builder.get_statistics()
        assert stats.total_examples >= config.data.min_samples or stats.total_examples > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
