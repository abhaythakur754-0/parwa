"""
Active Learning Module for Agent Lightning.

Enables continuous model improvement through intelligent sample
selection and human feedback integration.

Components:
- UncertaintySampler: Identifies low-confidence predictions
- SampleSelector: Prioritizes high-value training samples
- FeedbackCollector: Gathers human corrections
- ModelUpdater: Applies incremental updates
"""

from agent_lightning.training.active_learning.uncertainty_sampler import (
    UncertaintySampler,
    SamplingStrategy,
    UncertaintyResult,
)
from agent_lightning.training.active_learning.sample_selector import (
    SampleSelector,
    SelectionConfig,
    SelectedSample,
)
from agent_lightning.training.active_learning.feedback_collector import (
    FeedbackCollector,
    FeedbackItem,
    FeedbackPriority,
    FeedbackQuality,
)
from agent_lightning.training.active_learning.model_updater import (
    ModelUpdater,
    UpdateResult,
    UpdateConfig,
)


__all__ = [
    "UncertaintySampler",
    "SamplingStrategy",
    "UncertaintyResult",
    "SampleSelector",
    "SelectionConfig",
    "SelectedSample",
    "FeedbackCollector",
    "FeedbackItem",
    "FeedbackPriority",
    "FeedbackQuality",
    "ModelUpdater",
    "UpdateResult",
    "UpdateConfig",
]
