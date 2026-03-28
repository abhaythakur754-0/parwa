"""Test Agent Lightning 91% accuracy."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class Test91Accuracy:
    """Test Agent Lightning achieves 91% accuracy."""

    def test_accuracy_at_least_91(self):
        """Test overall accuracy >= 91%."""
        from agent_lightning.training.training_run_week30 import run_week30_training
        result = run_week30_training()
        assert result.accuracy >= 0.91

    def test_all_category_specialists_above_90(self):
        """Test all category specialists > 90%."""
        from agent_lightning.training.training_run_week30 import run_week30_training
        result = run_week30_training()
        for specialist, acc in result.category_specialists.items():
            assert acc >= 0.90, f"{specialist} accuracy {acc:.1%} < 90%"

    def test_training_examples_sufficient(self):
        """Test sufficient training examples."""
        from agent_lightning.training.training_run_week30 import run_week30_training
        result = run_week30_training()
        assert result.training_examples >= 4000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
