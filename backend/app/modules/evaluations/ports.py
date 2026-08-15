"""Provider-agnostic request/result contracts for EvaluationEngine.

Kept free of any OpenAI-specific types so a future non-OpenAI or hybrid
engine (ADR 0003) can implement the same interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.evaluations.enums import Verdict


@dataclass(frozen=True)
class ReferenceGenerationRequest:
    french_text: str
    exercise_type: str
    difficulty: str
    contexts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PatternSuggestion:
    expression: str
    meaning: str
    example: str


@dataclass(frozen=True)
class ReferenceGenerationResult:
    preferred_translation: str
    alternatives: list[str]
    hints: list[str]
    patterns: list[PatternSuggestion]
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class EvaluationRequest:
    french_text: str
    user_answer: str
    preferred_translation: str
    alternatives: list[str]
    hint_used: bool
    contexts: list[str] = field(default_factory=list)
    previous_verdict: Verdict | None = None


@dataclass(frozen=True)
class EvaluationResult:
    verdict: Verdict
    meaning_preserved: bool
    grammar_correct: bool
    natural_american_english: bool
    writing_issues: list[str]
    corrected_answer: str | None
    feedback: str
    error_categories: list[str]
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class GrammarExplanationRequest:
    french_text: str
    preferred_translation: str
    user_answer: str | None = None


@dataclass(frozen=True)
class GrammarExplanationResult:
    explanation: str
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class WeaknessCategoryContext:
    category: str
    count: int
    example_feedback: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WeaknessSuggestionsRequest:
    categories: list[WeaknessCategoryContext]


@dataclass(frozen=True)
class WeaknessSuggestion:
    category: str
    explanation: str
    suggestion: str


@dataclass(frozen=True)
class WeaknessSuggestionsResult:
    suggestions: list[WeaknessSuggestion]
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
