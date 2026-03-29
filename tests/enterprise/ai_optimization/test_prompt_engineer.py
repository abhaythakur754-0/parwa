"""Tests for Prompt Engineer Module - Week 55, Builder 5"""
import pytest
from datetime import datetime

from enterprise.ai_optimization.prompt_optimizer import (
    PromptOptimizer, OptimizedPrompt, OptimizationTechnique
)
from enterprise.ai_optimization.few_shot_manager import (
    FewShotManager, Example, ExampleSelectionStrategy
)
from enterprise.ai_optimization.prompt_templates import (
    PromptTemplate, TemplateVariable, TemplateRegistry, TemplateType, create_template
)


class TestPromptOptimizer:
    def test_init(self):
        optimizer = PromptOptimizer()
        assert len(optimizer._techniques) == 4

    def test_optimize_chain_of_thought(self):
        optimizer = PromptOptimizer()
        result = optimizer.optimize("What is 2+2?", OptimizationTechnique.CHAIN_OF_THOUGHT)
        assert result.technique == OptimizationTechnique.CHAIN_OF_THOUGHT
        assert "step" in result.optimized.lower()

    def test_optimize_few_shot(self):
        optimizer = PromptOptimizer()
        result = optimizer.optimize("What is 3+3?", OptimizationTechnique.FEW_SHOT)
        assert result.technique == OptimizationTechnique.FEW_SHOT
        assert "Example" in result.optimized

    def test_optimize_instruction_tuning(self):
        optimizer = PromptOptimizer()
        result = optimizer.optimize("solve the problem", OptimizationTechnique.INSTRUCTION_TUNING)
        assert result.technique == OptimizationTechnique.INSTRUCTION_TUNING

    def test_optimize_zero_shot(self):
        optimizer = PromptOptimizer()
        result = optimizer.optimize("calculate the sum", OptimizationTechnique.ZERO_SHOT)
        assert result.technique == OptimizationTechnique.ZERO_SHOT

    def test_ab_test(self):
        optimizer = PromptOptimizer()
        results = optimizer.ab_test(
            "Test prompt",
            [OptimizationTechnique.CHAIN_OF_THOUGHT, OptimizationTechnique.FEW_SHOT]
        )
        assert len(results) == 2

    def test_get_history(self):
        optimizer = PromptOptimizer()
        optimizer.optimize("test1")
        optimizer.optimize("test2")
        history = optimizer.get_history()
        assert len(history) == 2

    def test_clear_history(self):
        optimizer = PromptOptimizer()
        optimizer.optimize("test")
        optimizer.clear_history()
        assert len(optimizer.get_history()) == 0


class TestOptimizedPrompt:
    def test_init(self):
        prompt = OptimizedPrompt(
            original="original",
            optimized="optimized",
            technique=OptimizationTechnique.CHAIN_OF_THOUGHT,
        )
        assert prompt.original == "original"
        assert prompt.optimized == "optimized"


class TestFewShotManager:
    def test_init(self):
        manager = FewShotManager()
        assert manager.default_strategy == ExampleSelectionStrategy.SIMILARITY
        assert len(manager.examples) == 0

    def test_add_example(self):
        manager = FewShotManager()
        example = manager.add_example("What is 1+1?", "2")
        assert len(manager.examples) == 1
        assert example.input == "What is 1+1?"

    def test_add_examples(self):
        manager = FewShotManager()
        count = manager.add_examples([("Q1", "A1"), ("Q2", "A2")])
        assert count == 2
        assert len(manager.examples) == 2

    def test_get_examples_random(self):
        manager = FewShotManager()
        for i in range(10):
            manager.add_example(f"Q{i}", f"A{i}")
        examples = manager.get_examples(count=3, strategy=ExampleSelectionStrategy.RANDOM)
        assert len(examples) == 3

    def test_get_examples_sequential(self):
        manager = FewShotManager()
        for i in range(10):
            manager.add_example(f"Q{i}", f"A{i}")
        examples = manager.get_examples(count=3, strategy=ExampleSelectionStrategy.SEQUENTIAL)
        assert len(examples) == 3
        assert examples[0].input == "Q0"

    def test_get_examples_similarity(self):
        manager = FewShotManager()
        manager.add_examples([("What is math?", "Math is science"), ("How to cook?", "Use recipes")])
        examples = manager.get_examples(count=1, strategy=ExampleSelectionStrategy.SIMILARITY, query="math question")
        assert len(examples) == 1

    def test_set_example_count(self):
        manager = FewShotManager()
        manager.set_example_count(5)
        assert manager._example_count == 5

    def test_remove_example(self):
        manager = FewShotManager()
        manager.add_example("Q1", "A1")
        assert manager.remove_example(0)
        assert len(manager.examples) == 0

    def test_clear_examples(self):
        manager = FewShotManager()
        manager.add_example("Q1", "A1")
        manager.clear_examples()
        assert len(manager.examples) == 0

    def test_format_examples(self):
        manager = FewShotManager()
        manager.add_example("Q1", "A1")
        formatted = manager.format_examples()
        assert "Input: Q1" in formatted
        assert "Output: A1" in formatted

    def test_count(self):
        manager = FewShotManager()
        manager.add_examples([("Q1", "A1"), ("Q2", "A2")])
        assert manager.count() == 2


class TestExample:
    def test_init(self):
        example = Example(input="test input", output="test output")
        assert example.input == "test input"
        assert example.output == "test output"

    def test_to_dict(self):
        example = Example(input="test", output="result", metadata={"key": "value"})
        d = example.to_dict()
        assert d["input"] == "test"
        assert d["output"] == "result"


class TestPromptTemplate:
    def test_init(self):
        template = PromptTemplate(
            name="test",
            template="Hello {name}!",
            variables=[TemplateVariable(name="name")],
        )
        assert template.name == "test"

    def test_render(self):
        template = PromptTemplate(
            name="test",
            template="Hello {name}!",
            variables=[TemplateVariable(name="name")],
        )
        result = template.render(name="World")
        assert result == "Hello World!"

    def test_render_with_default(self):
        template = PromptTemplate(
            name="test",
            template="Hello {name}!",
            variables=[TemplateVariable(name="name", default="User")],
        )
        result = template.render()
        assert result == "Hello User!"

    def test_extract_variables(self):
        template = PromptTemplate(
            name="test",
            template="{greeting} {name}!",
            variables=[],
        )
        vars = template.extract_variables()
        assert "greeting" in vars
        assert "name" in vars


class TestTemplateRegistry:
    def test_init(self):
        registry = TemplateRegistry()
        assert len(registry.templates) >= 3

    def test_register(self):
        registry = TemplateRegistry()
        template = PromptTemplate(name="custom", template="Custom: {input}")
        registry.register(template)
        assert "custom" in registry.templates

    def test_unregister(self):
        registry = TemplateRegistry()
        registry.register(PromptTemplate(name="temp", template="test"))
        assert registry.unregister("temp")
        assert "temp" not in registry.templates

    def test_get(self):
        registry = TemplateRegistry()
        template = registry.get("chat")
        assert template is not None

    def test_render(self):
        registry = TemplateRegistry()
        result = registry.render("qa", question="What is AI?")
        assert "What is AI?" in result

    def test_list_templates(self):
        registry = TemplateRegistry()
        templates = registry.list_templates()
        assert len(templates) >= 3

    def test_get_by_type(self):
        registry = TemplateRegistry()
        system_templates = registry.get_by_type(TemplateType.SYSTEM)
        assert len(system_templates) >= 1


class TestCreateTemplate:
    def test_create_template(self):
        template = create_template("test", "Hello {name}!", {"name": "World"})
        assert template.name == "test"
        assert len(template.variables) == 1

    def test_create_template_auto_extract(self):
        template = create_template("test", "Hello {name} from {place}!")
        assert len(template.variables) == 2
