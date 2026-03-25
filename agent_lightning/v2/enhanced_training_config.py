"""
Enhanced Training Configuration for Agent Lightning v2

This module provides enhanced training configuration that supports:
- Collective intelligence data from multiple clients
- Multi-client training settings
- Industry-specific fine-tuning options
- Enhanced validation thresholds (target 77%+ accuracy)
- Cross-client generalization testing
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Literal
from enum import Enum


class TrainingMode(Enum):
    STANDARD = "standard"
    COLLECTIVE = "collective"
    INDUSTRY_SPECIFIC = "industry_specific"
    HYBRID = "hybrid"


class ValidationStrategy(Enum):
    HOLDOUT = "holdout"
    CROSS_VALIDATION = "cross_validation"
    TEMPORAL = "temporal"
    CLIENT_STRATIFIED = "client_stratified"


@dataclass
class DataConfig:
    """Data configuration for training"""
    min_samples: int = 500
    max_samples: int = 10000
    validation_split: float = 0.2
    test_split: float = 0.1
    balance_strategy: str = "stratified"  # stratified, oversample, undersample
    anonymize_phi: bool = True
    remove_client_identifiers: bool = True


@dataclass
class ModelConfig:
    """Model architecture configuration"""
    base_model: str = "gpt-4-turbo"
    fine_tuning_method: str = "lora"  # lora, full, prefix
    learning_rate: float = 1e-5
    epochs: int = 3
    batch_size: int = 16
    warmup_steps: int = 100
    weight_decay: float = 0.01
    max_seq_length: int = 4096


@dataclass
class CollectiveIntelligenceConfig:
    """Collective intelligence integration config"""
    enabled: bool = True
    pattern_sharing: bool = True
    knowledge_federation: bool = True
    privacy_preserving: bool = True
    min_clients_for_pattern: int = 3
    pattern_confidence_threshold: float = 0.85
    differential_privacy_epsilon: float = 1.0


@dataclass
class IndustryWeights:
    """Industry-specific training weights"""
    ecommerce: float = 1.0
    saas: float = 1.0
    healthcare: float = 1.2  # Higher weight for healthcare accuracy
    logistics: float = 1.0
    fintech: float = 1.1


@dataclass
class ValidationThresholds:
    """Validation thresholds for model acceptance"""
    min_accuracy: float = 0.77  # 77% target
    min_accuracy_improvement: float = 0.03  # 3% improvement over baseline
    max_hallucination_rate: float = 0.02
    max_response_time_ms: int = 500
    min_safety_score: float = 0.99
    max_regression_rate: float = 0.01


@dataclass
class EnhancedTrainingConfig:
    """Main enhanced training configuration for Agent Lightning v2"""
    
    # Version info
    version: str = "2.0.0"
    config_name: str = "enhanced_v2_default"
    
    # Training mode
    training_mode: TrainingMode = TrainingMode.COLLECTIVE
    
    # Data settings
    data: DataConfig = field(default_factory=DataConfig)
    
    # Model settings
    model: ModelConfig = field(default_factory=ModelConfig)
    
    # Collective intelligence
    collective: CollectiveIntelligenceConfig = field(default_factory=CollectiveIntelligenceConfig)
    
    # Industry weights
    industry_weights: IndustryWeights = field(default_factory=IndustryWeights)
    
    # Validation
    validation: ValidationThresholds = field(default_factory=ValidationThresholds)
    
    # Validation strategy
    validation_strategy: ValidationStrategy = ValidationStrategy.CLIENT_STRATIFIED
    
    # Client participation
    participating_clients: List[str] = field(default_factory=lambda: [
        "client_001",  # Acme E-commerce
        "client_002",  # TechStart SaaS
        "client_003",  # MediCare Health (HIPAA)
        "client_004",  # FastFreight Logistics
        "client_005"   # PayFlow FinTech
    ])
    
    # Training schedule
    training_schedule: Dict[str, Any] = field(default_factory=lambda: {
        "frequency": "weekly",
        "min_new_samples": 100,
        "auto_trigger_threshold": 0.02,  # Retrain if accuracy drops 2%
        "max_training_hours": 24
    })
    
    # Output settings
    output_dir: str = "models/agent_lightning_v2"
    checkpoint_dir: str = "checkpoints/v2"
    log_dir: str = "logs/training_v2"
    
    # Safety settings
    safety_checks_enabled: bool = True
    content_filter_enabled: bool = True
    pii_detection_enabled: bool = True
    hipaa_mode: bool = True  # Enable HIPAA-compliant training


def get_enhanced_config(
    mode: str = "collective",
    target_accuracy: float = 0.77
) -> EnhancedTrainingConfig:
    """Get enhanced training configuration with specified mode"""
    
    config = EnhancedTrainingConfig()
    
    # Set training mode
    mode_mapping = {
        "standard": TrainingMode.STANDARD,
        "collective": TrainingMode.COLLECTIVE,
        "industry_specific": TrainingMode.INDUSTRY_SPECIFIC,
        "hybrid": TrainingMode.HYBRID
    }
    config.training_mode = mode_mapping.get(mode, TrainingMode.COLLECTIVE)
    
    # Adjust thresholds based on target
    config.validation.min_accuracy = target_accuracy
    
    return config


def get_industry_config(industry: str) -> EnhancedTrainingConfig:
    """Get industry-specific training configuration"""
    
    config = get_enhanced_config()
    
    if industry == "healthcare":
        config.model.max_seq_length = 8192  # Longer for medical context
        config.validation.min_accuracy = 0.85  # Higher for healthcare
        config.data.anonymize_phi = True
        config.hipaa_mode = True
        config.industry_weights.healthcare = 1.5
        
    elif industry == "fintech":
        config.validation.min_accuracy = 0.90  # Highest for financial
        config.safety_checks_enabled = True
        config.content_filter_enabled = True
        config.industry_weights.fintech = 1.3
        
    elif industry == "saas":
        config.industry_weights.saas = 1.2
        
    elif industry == "ecommerce":
        config.industry_weights.ecommerce = 1.0
        
    elif industry == "logistics":
        config.industry_weights.logistics = 1.0
    
    return config


def validate_config(config: EnhancedTrainingConfig) -> tuple[bool, List[str]]:
    """Validate training configuration"""
    errors = []
    
    if config.data.validation_split + config.data.test_split >= 0.5:
        errors.append("Validation + test split must be < 50%")
    
    if config.validation.min_accuracy < 0.5:
        errors.append("Minimum accuracy must be >= 50%")
    
    if config.model.learning_rate > 1e-3:
        errors.append("Learning rate too high, max 1e-3")
    
    if len(config.participating_clients) < 2 and config.training_mode == TrainingMode.COLLECTIVE:
        errors.append("Collective training requires at least 2 clients")
    
    return len(errors) == 0, errors
