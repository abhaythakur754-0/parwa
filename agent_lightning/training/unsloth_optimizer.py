"""
Unsloth Optimizer for Agent Lightning.

Optimizes training for Unsloth + Colab FREE tier.
Provides memory-efficient training optimizations.

CRITICAL: Designed for Colab FREE tier (T4 GPU, ~15GB VRAM).

Features:
- 4-bit quantization
- Gradient checkpointing
- Memory-efficient attention
- Optimized LoRA settings
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import asyncio

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class OptimizationLevel(str, Enum):
    """Optimization intensity levels."""
    MINIMAL = "minimal"  # Basic optimizations
    STANDARD = "standard"  # Default optimizations
    AGGRESSIVE = "aggressive"  # Maximum memory savings
    COLAB_FREE = "colab_free"  # Optimized for Colab FREE tier


@dataclass
class MemoryProfile:
    """Memory usage profile."""
    total_vram_gb: float = 16.0  # T4 has ~16GB
    model_memory_gb: float = 0.0
    optimizer_memory_gb: float = 0.0
    activation_memory_gb: float = 0.0
    gradient_memory_gb: float = 0.0
    available_memory_gb: float = 16.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_vram_gb": self.total_vram_gb,
            "model_memory_gb": self.model_memory_gb,
            "optimizer_memory_gb": self.optimizer_memory_gb,
            "activation_memory_gb": self.activation_memory_gb,
            "gradient_memory_gb": self.gradient_memory_gb,
            "available_memory_gb": self.available_memory_gb,
            "utilization_percent": (
                (self.total_vram_gb - self.available_memory_gb) /
                self.total_vram_gb * 100
            ) if self.total_vram_gb > 0 else 0
        }


@dataclass
class UnslothConfig:
    """Configuration for Unsloth optimizations."""
    # Model loading
    load_in_4bit: bool = True
    bnb_4bit_compute_dtype: str = "float16"
    bnb_4bit_quant_type: str = "nf4"
    bnb_4bit_use_double_quant: bool = True

    # Attention optimization
    use_flash_attention: bool = True
    use_sdpa: bool = False  # Scaled Dot Product Attention

    # Gradient optimizations
    gradient_checkpointing: bool = True
    gradient_accumulation_steps: int = 4

    # LoRA optimizations
    lora_r: int = 16
    lora_alpha: int = 16
    lora_dropout: float = 0.0
    use_rslora: bool = False  # Rank-stabilized LoRA
    use_qlora: bool = True  # Quantized LoRA

    # Training optimizations
    optim: str = "adamw_8bit"  # 8-bit Adam
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0

    # Target modules for LoRA
    target_modules: List[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ])


class UnslothOptimizer:
    """
    Unsloth Optimization Manager.

    Provides optimizations for efficient training on Colab FREE tier.

    CRITICAL: Designed for T4 GPU with ~16GB VRAM.

    Features:
    - 4-bit quantization (QLoRA)
    - Flash Attention 2 support
    - Gradient checkpointing
    - 8-bit optimizer
    - Memory-efficient training

    Example:
        optimizer = UnslothOptimizer()
        config = optimizer.optimize_for_colab_free()
        memory = optimizer.get_memory_footprint()
    """

    # Colab FREE tier limits
    COLAB_FREE_VRAM_GB = 16.0
    COLAB_FREE_GPU = "T4"

    # Recommended settings for Colab FREE
    COLAB_FREE_CONFIG = UnslothConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype="float16",
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        use_flash_attention=True,
        gradient_checkpointing=True,
        gradient_accumulation_steps=4,
        lora_r=16,
        lora_alpha=16,
        lora_dropout=0.0,
        use_qlora=True,
        optim="adamw_8bit"
    )

    def __init__(
        self,
        optimization_level: OptimizationLevel = OptimizationLevel.COLAB_FREE
    ) -> None:
        """
        Initialize Unsloth Optimizer.

        Args:
            optimization_level: Level of optimization to apply
        """
        self.optimization_level = optimization_level
        self._config = self._get_config_for_level(optimization_level)
        self._memory_profile = MemoryProfile()

        logger.info({
            "event": "unsloth_optimizer_initialized",
            "optimization_level": optimization_level.value,
            "load_in_4bit": self._config.load_in_4bit,
            "flash_attention": self._config.use_flash_attention
        })

    def _get_config_for_level(
        self,
        level: OptimizationLevel
    ) -> UnslothConfig:
        """
        Get config for optimization level.

        Args:
            level: Optimization level

        Returns:
            UnslothConfig for the level
        """
        configs = {
            OptimizationLevel.MINIMAL: UnslothConfig(
                load_in_4bit=True,
                gradient_checkpointing=False,
                use_flash_attention=False
            ),
            OptimizationLevel.STANDARD: UnslothConfig(
                load_in_4bit=True,
                gradient_checkpointing=True,
                use_flash_attention=True
            ),
            OptimizationLevel.AGGRESSIVE: UnslothConfig(
                load_in_4bit=True,
                gradient_checkpointing=True,
                use_flash_attention=True,
                gradient_accumulation_steps=8,
                lora_r=8  # Smaller LoRA rank
            ),
            OptimizationLevel.COLAB_FREE: self.COLAB_FREE_CONFIG
        }
        return configs.get(level, self.COLAB_FREE_CONFIG)

    def apply_optimizations(
        self,
        model_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply Unsloth optimizations to model config.

        Args:
            model_config: Original model configuration

        Returns:
            Optimized model configuration
        """
        optimized = model_config.copy()

        # Apply 4-bit quantization settings
        optimized["load_in_4bit"] = self._config.load_in_4bit
        optimized["bnb_4bit_compute_dtype"] = self._config.bnb_4bit_compute_dtype
        optimized["bnb_4bit_quant_type"] = self._config.bnb_4bit_quant_type
        optimized["bnb_4bit_use_double_quant"] = self._config.bnb_4bit_use_double_quant

        # Apply attention optimizations
        optimized["use_flash_attention"] = self._config.use_flash_attention
        optimized["use_sdpa"] = self._config.use_sdpa

        # Apply gradient optimizations
        optimized["gradient_checkpointing"] = self._config.gradient_checkpointing
        optimized["gradient_accumulation_steps"] = self._config.gradient_accumulation_steps

        # Apply LoRA settings
        optimized["lora_r"] = self._config.lora_r
        optimized["lora_alpha"] = self._config.lora_alpha
        optimized["lora_dropout"] = self._config.lora_dropout
        optimized["use_rslora"] = self._config.use_rslora
        optimized["use_qlora"] = self._config.use_qlora
        optimized["target_modules"] = self._config.target_modules

        # Apply optimizer settings
        optimized["optim"] = self._config.optim
        optimized["weight_decay"] = self._config.weight_decay
        optimized["max_grad_norm"] = self._config.max_grad_norm

        logger.info({
            "event": "optimizations_applied",
            "optimization_level": self.optimization_level.value,
            "load_in_4bit": self._config.load_in_4bit,
            "gradient_checkpointing": self._config.gradient_checkpointing,
            "lora_r": self._config.lora_r
        })

        return optimized

    def get_memory_footprint(self) -> float:
        """
        Get estimated memory footprint in GB.

        Returns:
            Estimated VRAM usage in GB
        """
        # Base model memory (4-bit quantized 7B model)
        base_model_gb = 3.5  # ~3.5GB for 4-bit 7B model

        # LoRA adapter memory
        lora_gb = 0.1 * (self._config.lora_r / 16)  # ~100MB for r=16

        # Optimizer memory (8-bit Adam)
        optimizer_gb = 1.0 if self._config.optim == "adamw_8bit" else 2.0

        # Activation memory (reduced by gradient checkpointing)
        activation_gb = 2.0 if not self._config.gradient_checkpointing else 0.5

        # Gradient memory
        gradient_gb = 0.5

        total = base_model_gb + lora_gb + optimizer_gb + activation_gb + gradient_gb

        self._memory_profile.model_memory_gb = base_model_gb
        self._memory_profile.optimizer_memory_gb = optimizer_gb
        self._memory_profile.activation_memory_gb = activation_gb
        self._memory_profile.gradient_memory_gb = gradient_gb
        self._memory_profile.available_memory_gb = self.COLAB_FREE_VRAM_GB - total

        logger.info({
            "event": "memory_footprint_calculated",
            "total_gb": total,
            "available_gb": self._memory_profile.available_memory_gb
        })

        return total

    def get_memory_profile(self) -> MemoryProfile:
        """
        Get detailed memory profile.

        Returns:
            MemoryProfile with detailed breakdown
        """
        self.get_memory_footprint()  # Update profile
        return self._memory_profile

    def optimize_for_colab_free(self) -> Dict[str, Any]:
        """
        Get optimized settings for Colab FREE tier.

        CRITICAL: This returns settings optimized for T4 GPU with 16GB VRAM.

        Returns:
            Dict with optimized settings
        """
        config = self.apply_optimizations({})

        # Add Colab-specific settings
        config.update({
            "max_seq_length": 2048,  # Balance memory and context
            "batch_size": 2,  # Conservative batch size
            "num_train_epochs": 3,
            "learning_rate": 2e-4,
            "warmup_steps": 5,
            "logging_steps": 10,
            "save_steps": 100,
            "save_total_limit": 2,  # Limit checkpoint storage
            "fp16": True,  # Use mixed precision
            "bf16": False,  # T4 doesn't support bf16
            "optim": "adamw_8bit",
            "weight_decay": 0.01,
            "max_grad_norm": 1.0,
            "dataloader_num_workers": 2,
            "dataloader_pin_memory": True,
            "gradient_checkpointing_kwargs": {
                "use_reentrant": False
            },
            "colab_free_optimized": True,
            "target_vram_gb": 15.0,  # Leave 1GB buffer
        })

        logger.info({
            "event": "colab_free_optimization_applied",
            "estimated_vram_gb": self.get_memory_footprint(),
            "batch_size": config["batch_size"],
            "max_seq_length": config["max_seq_length"]
        })

        return config

    def check_memory_available(
        self,
        required_gb: float
    ) -> Dict[str, Any]:
        """
        Check if required memory is available.

        Args:
            required_gb: Required memory in GB

        Returns:
            Dict with availability status
        """
        available = self._memory_profile.available_memory_gb
        fits = required_gb <= available

        return {
            "required_gb": required_gb,
            "available_gb": available,
            "fits": fits,
            "buffer_gb": available - required_gb if fits else 0,
            "recommendation": (
                "OK to proceed" if fits
                else f"Reduce batch size or sequence length to free "
                     f"{required_gb - available:.1f}GB"
            )
        }

    def get_recommended_batch_size(
        self,
        seq_length: int = 2048
    ) -> int:
        """
        Get recommended batch size for given sequence length.

        Args:
            seq_length: Maximum sequence length

        Returns:
            Recommended batch size
        """
        # Memory increases with sequence length
        # Base batch size for 2048 tokens
        if seq_length <= 1024:
            return 4
        elif seq_length <= 2048:
            return 2
        elif seq_length <= 4096:
            return 1
        else:
            return 1

    def get_config(self) -> UnslothConfig:
        """
        Get current Unsloth configuration.

        Returns:
            Current UnslothConfig
        """
        return self._config

    def get_status(self) -> Dict[str, Any]:
        """
        Get optimizer status.

        Returns:
            Dict with status information
        """
        return {
            "optimization_level": self.optimization_level.value,
            "config": {
                "load_in_4bit": self._config.load_in_4bit,
                "gradient_checkpointing": self._config.gradient_checkpointing,
                "flash_attention": self._config.use_flash_attention,
                "lora_r": self._config.lora_r,
                "optim": self._config.optim
            },
            "memory_profile": self.get_memory_profile().to_dict(),
            "colab_free_compatible": True
        }


def get_unsloth_optimizer(
    level: OptimizationLevel = OptimizationLevel.COLAB_FREE
) -> UnslothOptimizer:
    """
    Get an UnslothOptimizer instance.

    Args:
        level: Optimization level

    Returns:
        UnslothOptimizer instance
    """
    return UnslothOptimizer(optimization_level=level)
