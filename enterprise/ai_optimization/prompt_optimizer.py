"""Prompt Optimizer Module - Week 55, Builder 5"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class OptimizationTechnique(Enum):
    CHAIN_OF_THOUGHT = "chain_of_thought"
    FEW_SHOT = "few_shot"
    INSTRUCTION_TUNING = "instruction_tuning"
    ZERO_SHOT = "zero_shot"


@dataclass
class OptimizedPrompt:
    original: str
    optimized: str
    technique: OptimizationTechnique
    improvements: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PromptOptimizer:
    def __init__(self):
        self._techniques = {
            OptimizationTechnique.CHAIN_OF_THOUGHT: self._apply_chain_of_thought,
            OptimizationTechnique.FEW_SHOT: self._apply_few_shot,
            OptimizationTechnique.INSTRUCTION_TUNING: self._apply_instruction_tuning,
            OptimizationTechnique.ZERO_SHOT: self._apply_zero_shot,
        }
        self._optimization_history: List[OptimizedPrompt] = []

    def optimize(self, prompt: str, technique: OptimizationTechnique = OptimizationTechnique.CHAIN_OF_THOUGHT) -> OptimizedPrompt:
        optimizer_func = self._techniques.get(technique, self._apply_chain_of_thought)
        optimized, improvements = optimizer_func(prompt)

        result = OptimizedPrompt(
            original=prompt,
            optimized=optimized,
            technique=technique,
            improvements=improvements,
        )
        self._optimization_history.append(result)
        return result

    def _apply_chain_of_thought(self, prompt: str) -> tuple:
        improvements = []
        optimized = prompt

        if "step" not in prompt.lower():
            optimized = f"Let's think step by step.\n{prompt}"
            improvements.append("Added step-by-step thinking")

        if "reasoning" not in prompt.lower():
            optimized += "\n\nPlease provide your reasoning."
            improvements.append("Added reasoning request")

        return optimized, improvements

    def _apply_few_shot(self, prompt: str) -> tuple:
        improvements = []
        examples = """
Example 1:
Input: What is 2+2?
Output: 4

Example 2:
Input: What is the capital of France?
Output: Paris

"""
        optimized = examples + prompt
        improvements.append("Added few-shot examples")
        return optimized, improvements

    def _apply_instruction_tuning(self, prompt: str) -> tuple:
        improvements = []
        optimized = prompt

        if not prompt.strip().endswith('.'):
            optimized = prompt.strip() + '.'

        if "you are" not in prompt.lower():
            optimized = f"You are a helpful assistant.\n\n{optimized}"
            improvements.append("Added role context")

        if "be specific" not in prompt.lower():
            optimized += "\n\nBe specific and detailed in your response."
            improvements.append("Added specificity instruction")

        return optimized, improvements

    def _apply_zero_shot(self, prompt: str) -> tuple:
        improvements = []
        optimized = prompt.strip()

        if not optimized.endswith('?') and 'please' not in optimized.lower():
            optimized = f"Please {optimized.lower()}"
            improvements.append("Added polite request format")

        return optimized, improvements

    def ab_test(self, prompt: str, techniques: List[OptimizationTechnique]) -> Dict[OptimizationTechnique, OptimizedPrompt]:
        results = {}
        for technique in techniques:
            results[technique] = self.optimize(prompt, technique)
        return results

    def get_history(self) -> List[OptimizedPrompt]:
        return self._optimization_history

    def clear_history(self) -> None:
        self._optimization_history.clear()
