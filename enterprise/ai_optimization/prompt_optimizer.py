"""
Prompt Optimization Engine for Week 55 Advanced AI Optimization.

This module provides comprehensive prompt optimization capabilities including
chain-of-thought reasoning, few-shot learning optimization, and instruction
tuning with A/B testing support.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import hashlib
import json
import random
import re
import uuid


class OptimizationTechnique(Enum):
    """Available prompt optimization techniques."""
    CHAIN_OF_THOUGHT = "chain_of_thought"
    FEW_SHOT = "few_shot"
    INSTRUCTION_TUNING = "instruction_tuning"
    SELF_CONSISTENCY = "self_consistency"
    TREE_OF_THOUGHTS = "tree_of_thoughts"
    STEP_BACK = "step_back"


class OptimizationStatus(Enum):
    """Status of optimization process."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Improvement:
    """Represents a single improvement made during optimization."""
    technique: OptimizationTechnique
    description: str
    before: str
    after: str
    rationale: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OptimizedPrompt:
    """Container for optimized prompt results."""
    original: str
    optimized: str
    improvements: List[Improvement] = field(default_factory=list)
    techniques_applied: List[OptimizationTechnique] = field(default_factory=list)
    optimization_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "original": self.original,
            "optimized": self.optimized,
            "improvements": [
                {
                    "technique": imp.technique.value,
                    "description": imp.description,
                    "before": imp.before,
                    "after": imp.after,
                    "rationale": imp.rationale,
                    "timestamp": imp.timestamp.isoformat()
                }
                for imp in self.improvements
            ],
            "techniques_applied": [t.value for t in self.techniques_applied],
            "optimization_score": self.optimization_score,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }
    
    def get_improvement_count(self) -> int:
        """Get the number of improvements made."""
        return len(self.improvements)


@dataclass
class ABTestResult:
    """Result of an A/B test comparison."""
    test_id: str
    variant_a: str
    variant_b: str
    metric_name: str
    score_a: float
    score_b: float
    winner: Optional[str]
    confidence: float
    sample_size: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ABTest:
    """A/B test configuration and results."""
    test_id: str
    name: str
    variant_a: str
    variant_b: str
    metrics: List[str] = field(default_factory=list)
    results: List[ABTestResult] = field(default_factory=list)
    status: OptimizationStatus = OptimizationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def add_result(self, result: ABTestResult) -> None:
        """Add a test result."""
        self.results.append(result)
    
    def get_winner(self) -> Optional[str]:
        """Determine the overall winner based on results."""
        if not self.results:
            return None
        
        wins_a = sum(1 for r in self.results if r.winner == "A")
        wins_b = sum(1 for r in self.results if r.winner == "B")
        
        return "A" if wins_a > wins_b else "B" if wins_b > wins_a else None


class PromptOptimizer:
    """
    Main prompt optimization engine with support for multiple optimization
    techniques and A/B testing.
    """
    
    def __init__(
        self,
        default_techniques: Optional[List[OptimizationTechnique]] = None,
        enable_ab_testing: bool = True
    ):
        """
        Initialize the prompt optimizer.
        
        Args:
            default_techniques: Default optimization techniques to apply
            enable_ab_testing: Whether to enable A/B testing capabilities
        """
        self.default_techniques = default_techniques or [
            OptimizationTechnique.CHAIN_OF_THOUGHT,
            OptimizationTechnique.FEW_SHOT,
            OptimizationTechnique.INSTRUCTION_TUNING
        ]
        self.enable_ab_testing = enable_ab_testing
        self._optimization_history: List[OptimizedPrompt] = []
        self._ab_tests: Dict[str, ABTest] = {}
        self._technique_handlers: Dict[OptimizationTechnique, Callable] = {
            OptimizationTechnique.CHAIN_OF_THOUGHT: self._apply_chain_of_thought,
            OptimizationTechnique.FEW_SHOT: self._apply_few_shot,
            OptimizationTechnique.INSTRUCTION_TUNING: self._apply_instruction_tuning,
            OptimizationTechnique.SELF_CONSISTENCY: self._apply_self_consistency,
            OptimizationTechnique.TREE_OF_THOUGHTS: self._apply_tree_of_thoughts,
            OptimizationTechnique.STEP_BACK: self._apply_step_back
        }
    
    def optimize(
        self,
        prompt: str,
        techniques: Optional[List[OptimizationTechnique]] = None,
        context: Optional[Dict[str, Any]] = None,
        max_improvements: int = 5
    ) -> OptimizedPrompt:
        """
        Optimize a prompt using specified techniques.
        
        Args:
            prompt: The original prompt to optimize
            techniques: Specific techniques to apply (uses defaults if None)
            context: Additional context for optimization
            max_improvements: Maximum number of improvements to apply
            
        Returns:
            OptimizedPrompt with the optimized version and improvements
        """
        techniques = techniques or self.default_techniques
        context = context or {}
        
        optimized_prompt = OptimizedPrompt(original=prompt, optimized=prompt)
        
        for technique in techniques:
            if len(optimized_prompt.improvements) >= max_improvements:
                break
            
            handler = self._technique_handlers.get(technique)
            if handler:
                improvement = handler(prompt, optimized_prompt.optimized, context)
                if improvement:
                    optimized_prompt.optimized = improvement.after
                    optimized_prompt.improvements.append(improvement)
                    optimized_prompt.techniques_applied.append(technique)
        
        optimized_prompt.optimization_score = self._calculate_score(
            prompt, optimized_prompt.optimized
        )
        
        self._optimization_history.append(optimized_prompt)
        
        return optimized_prompt
    
    def _apply_chain_of_thought(
        self,
        original: str,
        current: str,
        context: Dict[str, Any]
    ) -> Optional[Improvement]:
        """Apply chain-of-thought reasoning to the prompt."""
        # Check if already has reasoning instructions
        reasoning_patterns = [
            r"step.?by.?step",
            r"think.?through",
            r"let's think",
            r"reasoning",
            r"first.*then.*finally"
        ]
        
        for pattern in reasoning_patterns:
            if re.search(pattern, current, re.IGNORECASE):
                return None
        
        cot_prefix = "Let's think through this step by step:\n\n"
        cot_suffix = "\n\nPlease provide your reasoning for each step before giving the final answer."
        
        improved = cot_prefix + current + cot_suffix
        
        return Improvement(
            technique=OptimizationTechnique.CHAIN_OF_THOUGHT,
            description="Added chain-of-thought reasoning instructions",
            before=current,
            after=improved,
            rationale="Encourages step-by-step reasoning for better accuracy"
        )
    
    def _apply_few_shot(
        self,
        original: str,
        current: str,
        context: Dict[str, Any]
    ) -> Optional[Improvement]:
        """Apply few-shot learning examples to the prompt."""
        examples = context.get("few_shot_examples", [])
        
        if not examples:
            # Check if prompt already has examples
            if "example" in current.lower() or "for instance" in current.lower():
                return None
            
            # Add placeholder for examples
            example_section = "\n\nHere are some examples to guide you:\n\n"
            example_section += "Example 1:\n[Input]: <sample input>\n[Output]: <sample output>\n\n"
            example_section += "Now, please complete the following:\n"
            
            improved = current + example_section
        else:
            example_section = "\n\nHere are some examples:\n\n"
            for i, example in enumerate(examples[:3], 1):
                example_section += f"Example {i}:\n"
                example_section += f"[Input]: {example.get('input', 'N/A')}\n"
                example_section += f"[Output]: {example.get('output', 'N/A')}\n\n"
            example_section += "Now, please complete the following:\n"
            
            improved = current + example_section
        
        return Improvement(
            technique=OptimizationTechnique.FEW_SHOT,
            description="Added few-shot learning examples",
            before=current,
            after=improved,
            rationale="Few-shot examples help the model understand the expected format and style"
        )
    
    def _apply_instruction_tuning(
        self,
        original: str,
        current: str,
        context: Dict[str, Any]
    ) -> Optional[Improvement]:
        """Apply instruction tuning improvements."""
        improvements_made = []
        improved = current
        
        # Add clear role if not present
        role_patterns = [r"you are", r"as a", r"your role", r"act as"]
        has_role = any(re.search(p, improved, re.IGNORECASE) for p in role_patterns)
        
        if not has_role:
            role_prefix = "You are an expert assistant. "
            improved = role_prefix + improved
            improvements_made.append("Added clear role definition")
        
        # Add output format if not specified
        format_patterns = [r"format:", r"output format", r"response format", r"structure"]
        has_format = any(re.search(p, improved, re.IGNORECASE) for p in format_patterns)
        
        if not has_format:
            format_suffix = "\n\nPlease format your response clearly and concisely."
            improved = improved + format_suffix
            improvements_made.append("Added output format guidance")
        
        if improvements_made:
            return Improvement(
                technique=OptimizationTechnique.INSTRUCTION_TUNING,
                description="Applied instruction tuning: " + ", ".join(improvements_made),
                before=current,
                after=improved,
                rationale="Clear instructions improve model understanding and output quality"
            )
        
        return None
    
    def _apply_self_consistency(
        self,
        original: str,
        current: str,
        context: Dict[str, Any]
    ) -> Optional[Improvement]:
        """Apply self-consistency prompting."""
        consistency_suffix = (
            "\n\n"
            "Consider multiple approaches to solving this problem. "
            "Compare the different solutions and identify the most consistent answer. "
            "Show your reasoning for selecting the best approach."
        )
        
        improved = current + consistency_suffix
        
        return Improvement(
            technique=OptimizationTechnique.SELF_CONSISTENCY,
            description="Added self-consistency instructions",
            before=current,
            after=improved,
            rationale="Self-consistency improves reliability by comparing multiple reasoning paths"
        )
    
    def _apply_tree_of_thoughts(
        self,
        original: str,
        current: str,
        context: Dict[str, Any]
    ) -> Optional[Improvement]:
        """Apply tree-of-thoughts prompting."""
        tot_suffix = (
            "\n\n"
            "Explore multiple solution paths:\n"
            "1. Generate 3 different approaches\n"
            "2. Evaluate the merits of each approach\n"
            "3. Select the best approach based on your evaluation\n"
            "4. Provide the final solution using the selected approach"
        )
        
        improved = current + tot_suffix
        
        return Improvement(
            technique=OptimizationTechnique.TREE_OF_THOUGHTS,
            description="Added tree-of-thoughts exploration",
            before=current,
            after=improved,
            rationale="Tree-of-thoughts enables systematic exploration of solution space"
        )
    
    def _apply_step_back(
        self,
        original: str,
        current: str,
        context: Dict[str, Any]
    ) -> Optional[Improvement]:
        """Apply step-back prompting."""
        stepback_prefix = (
            "Before diving into the specifics, let's consider the broader context:\n\n"
            "1. What is the underlying concept or principle here?\n"
            "2. What prior knowledge is relevant?\n"
            "3. What are the key assumptions?\n\n"
            "Now, let's proceed with the specific task:\n\n"
        )
        
        improved = stepback_prefix + current
        
        return Improvement(
            technique=OptimizationTechnique.STEP_BACK,
            description="Added step-back prompting for broader context",
            before=current,
            after=improved,
            rationale="Step-back prompting helps establish context before problem-solving"
        )
    
    def _calculate_score(self, original: str, optimized: str) -> float:
        """Calculate optimization score based on various metrics."""
        score = 0.0
        
        # Length score (not too short, not too long)
        length_ratio = len(optimized) / max(len(original), 1)
        if 1.0 <= length_ratio <= 3.0:
            score += 0.2
        elif length_ratio < 1.0 or length_ratio > 5.0:
            score -= 0.1
        
        # Clarity indicators
        clarity_patterns = [
            r"step.?by.?step",
            r"for example",
            r"specifically",
            r"clearly",
            r"first.*then",
            r"please"
        ]
        clarity_count = sum(
            1 for p in clarity_patterns
            if re.search(p, optimized, re.IGNORECASE)
        )
        score += min(clarity_count * 0.1, 0.3)
        
        # Structure indicators
        structure_patterns = [r"\n\n", r"\d+\.", r"-", r"\*"]
        structure_count = sum(
            1 for p in structure_patterns
            if re.search(p, optimized)
        )
        score += min(structure_count * 0.1, 0.3)
        
        # Specificity
        if "you are" in optimized.lower():
            score += 0.1
        if "format" in optimized.lower():
            score += 0.1
        
        return min(max(score, 0.0), 1.0)
    
    def create_ab_test(
        self,
        name: str,
        variant_a: str,
        variant_b: str,
        metrics: Optional[List[str]] = None
    ) -> ABTest:
        """
        Create an A/B test to compare two prompt variants.
        
        Args:
            name: Name of the test
            variant_a: First prompt variant
            variant_b: Second prompt variant
            metrics: Metrics to compare (default: accuracy, latency, clarity)
            
        Returns:
            ABTest configuration object
        """
        test_id = str(uuid.uuid4())
        metrics = metrics or ["accuracy", "latency", "clarity"]
        
        ab_test = ABTest(
            test_id=test_id,
            name=name,
            variant_a=variant_a,
            variant_b=variant_b,
            metrics=metrics
        )
        
        self._ab_tests[test_id] = ab_test
        return ab_test
    
    def run_ab_test(
        self,
        test_id: str,
        evaluator: Optional[Callable[[str], Dict[str, float]]] = None
    ) -> ABTestResult:
        """
        Run an A/B test and return results.
        
        Args:
            test_id: ID of the test to run
            evaluator: Optional custom evaluator function
            
        Returns:
            ABTestResult with comparison metrics
        """
        ab_test = self._ab_tests.get(test_id)
        if not ab_test:
            raise ValueError(f"A/B test {test_id} not found")
        
        ab_test.status = OptimizationStatus.IN_PROGRESS
        
        # Default evaluator simulates metric scoring
        if evaluator is None:
            def default_evaluator(prompt: str) -> Dict[str, float]:
                return {
                    "accuracy": random.uniform(0.6, 1.0),
                    "latency": random.uniform(0.5, 2.0),
                    "clarity": random.uniform(0.5, 1.0)
                }
            evaluator = default_evaluator
        
        results_a = evaluator(ab_test.variant_a)
        results_b = evaluator(ab_test.variant_b)
        
        # Compare for each metric
        for metric in ab_test.metrics:
            score_a = results_a.get(metric, 0.0)
            score_b = results_b.get(metric, 0.0)
            
            # For latency, lower is better
            if metric == "latency":
                winner = "A" if score_a < score_b else "B" if score_b < score_a else None
            else:
                winner = "A" if score_a > score_b else "B" if score_b > score_a else None
            
            confidence = abs(score_a - score_b) / max(max(score_a, score_b), 0.01)
            
            result = ABTestResult(
                test_id=test_id,
                variant_a=ab_test.variant_a,
                variant_b=ab_test.variant_b,
                metric_name=metric,
                score_a=score_a,
                score_b=score_b,
                winner=winner,
                confidence=confidence,
                sample_size=1
            )
            ab_test.add_result(result)
        
        ab_test.status = OptimizationStatus.COMPLETED
        ab_test.completed_at = datetime.utcnow()
        
        return ab_test.results[-1]
    
    def get_ab_test(self, test_id: str) -> Optional[ABTest]:
        """Get an A/B test by ID."""
        return self._ab_tests.get(test_id)
    
    def list_ab_tests(self) -> List[ABTest]:
        """List all A/B tests."""
        return list(self._ab_tests.values())
    
    def get_optimization_history(self) -> List[OptimizedPrompt]:
        """Get the history of all optimizations."""
        return self._optimization_history.copy()
    
    def register_technique_handler(
        self,
        technique: OptimizationTechnique,
        handler: Callable[[str, str, Dict[str, Any]], Optional[Improvement]]
    ) -> None:
        """
        Register a custom handler for an optimization technique.
        
        Args:
            technique: The technique to register for
            handler: Function that takes (original, current, context) and returns Improvement
        """
        self._technique_handlers[technique] = handler
    
    def batch_optimize(
        self,
        prompts: List[str],
        techniques: Optional[List[OptimizationTechnique]] = None
    ) -> List[OptimizedPrompt]:
        """
        Optimize multiple prompts in batch.
        
        Args:
            prompts: List of prompts to optimize
            techniques: Techniques to apply
            
        Returns:
            List of OptimizedPrompt results
        """
        return [
            self.optimize(prompt, techniques)
            for prompt in prompts
        ]
    
    def compare_prompts(
        self,
        prompt_a: str,
        prompt_b: str,
        criteria: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Compare two prompts and provide analysis.
        
        Args:
            prompt_a: First prompt
            prompt_b: Second prompt
            criteria: Comparison criteria
            
        Returns:
            Dictionary with comparison analysis
        """
        criteria = criteria or ["length", "clarity", "specificity", "structure"]
        
        comparison = {
            "prompt_a": prompt_a,
            "prompt_b": prompt_b,
            "criteria": {}
        }
        
        for criterion in criteria:
            if criterion == "length":
                comparison["criteria"]["length"] = {
                    "a": len(prompt_a),
                    "b": len(prompt_b),
                    "winner": "A" if len(prompt_a) < len(prompt_b) else "B"
                }
            elif criterion == "clarity":
                score_a = self._calculate_clarity_score(prompt_a)
                score_b = self._calculate_clarity_score(prompt_b)
                comparison["criteria"]["clarity"] = {
                    "a": score_a,
                    "b": score_b,
                    "winner": "A" if score_a > score_b else "B"
                }
            elif criterion == "specificity":
                score_a = self._calculate_specificity_score(prompt_a)
                score_b = self._calculate_specificity_score(prompt_b)
                comparison["criteria"]["specificity"] = {
                    "a": score_a,
                    "b": score_b,
                    "winner": "A" if score_a > score_b else "B"
                }
            elif criterion == "structure":
                score_a = self._calculate_structure_score(prompt_a)
                score_b = self._calculate_structure_score(prompt_b)
                comparison["criteria"]["structure"] = {
                    "a": score_a,
                    "b": score_b,
                    "winner": "A" if score_a > score_b else "B"
                }
        
        return comparison
    
    def _calculate_clarity_score(self, prompt: str) -> float:
        """Calculate clarity score for a prompt."""
        score = 0.5
        clarity_indicators = [
            "please", "specifically", "for example", "clearly",
            "step by step", "first", "then", "finally"
        ]
        for indicator in clarity_indicators:
            if indicator in prompt.lower():
                score += 0.05
        return min(score, 1.0)
    
    def _calculate_specificity_score(self, prompt: str) -> float:
        """Calculate specificity score for a prompt."""
        score = 0.5
        specificity_indicators = [
            "you are", "your role", "format", "structure",
            "must", "should", "ensure", "include"
        ]
        for indicator in specificity_indicators:
            if indicator in prompt.lower():
                score += 0.05
        return min(score, 1.0)
    
    def _calculate_structure_score(self, prompt: str) -> float:
        """Calculate structure score for a prompt."""
        score = 0.5
        # Count paragraphs
        paragraphs = prompt.count("\n\n")
        score += min(paragraphs * 0.1, 0.2)
        # Count numbered items
        numbered = len(re.findall(r"\d+\.", prompt))
        score += min(numbered * 0.05, 0.15)
        # Count bullet points
        bullets = prompt.count("-") + prompt.count("*")
        score += min(bullets * 0.02, 0.15)
        return min(score, 1.0)
