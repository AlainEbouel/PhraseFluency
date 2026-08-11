"""EvaluationEngine abstraction (docs/llm-integration.md, ADR 0003).

OpenAI is the only implementation in V1, but the Learning Engine and the
rest of the backend must depend only on this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.evaluations.ports import (
    EvaluationRequest,
    EvaluationResult,
    GrammarExplanationRequest,
    GrammarExplanationResult,
    ReferenceGenerationRequest,
    ReferenceGenerationResult,
)


class EvaluationEngineError(Exception):
    """Timeout, invalid structured output, or provider failure.

    Callers must not award points, advance the queue, or validate the
    attempt when this is raised (docs/llm-integration.md, Failure
    behavior).
    """


class EvaluationEngine(ABC):
    @abstractmethod
    def generate_reference(
        self, request: ReferenceGenerationRequest
    ) -> ReferenceGenerationResult: ...

    @abstractmethod
    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """Evaluate a new attempt, or re-evaluate one when request.previous_verdict is set."""
        ...

    @abstractmethod
    def generate_grammar_explanation(
        self, request: GrammarExplanationRequest
    ) -> GrammarExplanationResult: ...
