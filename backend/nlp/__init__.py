"""
PARWA NLP Module.

Natural Language Processing for command parsing and intent classification.
Provides structured command extraction from natural language text.

Features:
- Command parsing from natural language
- Intent classification
- Entity extraction
- Agent provisioning commands
"""
from backend.nlp.command_parser import (
    CommandParser,
    ParsedCommand,
    IntentType,
)

__all__ = [
    "CommandParser",
    "ParsedCommand",
    "IntentType",
]
