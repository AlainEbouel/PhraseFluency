"""OpenAI implementation of EvaluationEngine (docs/llm-integration.md, ADR 0003)."""

from __future__ import annotations

import logging

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field

from app.modules.evaluations.engine import EvaluationEngine, EvaluationEngineError
from app.modules.evaluations.enums import Verdict
from app.modules.evaluations.error_categories import ErrorCategory
from app.modules.evaluations.ports import (
    EvaluationRequest,
    EvaluationResult,
    GrammarExplanationRequest,
    GrammarExplanationResult,
    PatternSuggestion,
    ReferenceGenerationRequest,
    ReferenceGenerationResult,
)
from app.modules.evaluations.prompts import (
    EVALUATION_PROMPT_VERSION,
    EVALUATION_SYSTEM_PROMPT,
    EXPLANATION_PROMPT_VERSION,
    EXPLANATION_SYSTEM_PROMPT,
    REFERENCE_PROMPT_VERSION,
    REFERENCE_SYSTEM_PROMPT,
    build_evaluation_user_prompt,
    build_explanation_user_prompt,
    build_reference_user_prompt,
)

logger = logging.getLogger(__name__)


class _PatternSchema(BaseModel):
    expression: str
    meaning: str
    example: str


class _ReferenceSchema(BaseModel):
    preferred_translation: str
    alternatives: list[str] = Field(max_length=2)
    hints: list[str] = Field(min_length=3, max_length=3)
    patterns: list[_PatternSchema] = Field(max_length=3)


class _EvaluationSchema(BaseModel):
    verdict: Verdict
    meaning_preserved: bool
    grammar_correct: bool
    natural_american_english: bool
    writing_issues: list[str]
    corrected_answer: str | None
    feedback: str
    error_categories: list[ErrorCategory]


class _ExplanationSchema(BaseModel):
    explanation: str


class OpenAIEvaluationEngine(EvaluationEngine):
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30.0) -> None:
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self._model = model

    def generate_reference(
        self, request: ReferenceGenerationRequest
    ) -> ReferenceGenerationResult:
        completion = self._parse(
            system_prompt=REFERENCE_SYSTEM_PROMPT,
            user_prompt=build_reference_user_prompt(request),
            schema=_ReferenceSchema,
        )
        parsed = self._require_parsed(completion)
        return ReferenceGenerationResult(
            preferred_translation=parsed.preferred_translation,
            alternatives=list(parsed.alternatives),
            hints=list(parsed.hints),
            patterns=[
                PatternSuggestion(p.expression, p.meaning, p.example) for p in parsed.patterns
            ],
            model=self._model,
            prompt_version=REFERENCE_PROMPT_VERSION,
            input_tokens=completion.usage.prompt_tokens if completion.usage else 0,
            output_tokens=completion.usage.completion_tokens if completion.usage else 0,
        )

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        completion = self._parse(
            system_prompt=EVALUATION_SYSTEM_PROMPT,
            user_prompt=build_evaluation_user_prompt(request),
            schema=_EvaluationSchema,
        )
        parsed = self._require_parsed(completion)
        return EvaluationResult(
            verdict=parsed.verdict,
            meaning_preserved=parsed.meaning_preserved,
            grammar_correct=parsed.grammar_correct,
            natural_american_english=parsed.natural_american_english,
            writing_issues=list(parsed.writing_issues),
            corrected_answer=parsed.corrected_answer,
            feedback=parsed.feedback,
            error_categories=[c.value for c in parsed.error_categories],
            model=self._model,
            prompt_version=EVALUATION_PROMPT_VERSION,
            input_tokens=completion.usage.prompt_tokens if completion.usage else 0,
            output_tokens=completion.usage.completion_tokens if completion.usage else 0,
        )

    def generate_grammar_explanation(
        self, request: GrammarExplanationRequest
    ) -> GrammarExplanationResult:
        completion = self._parse(
            system_prompt=EXPLANATION_SYSTEM_PROMPT,
            user_prompt=build_explanation_user_prompt(request),
            schema=_ExplanationSchema,
        )
        parsed = self._require_parsed(completion)
        return GrammarExplanationResult(
            explanation=parsed.explanation,
            model=self._model,
            prompt_version=EXPLANATION_PROMPT_VERSION,
            input_tokens=completion.usage.prompt_tokens if completion.usage else 0,
            output_tokens=completion.usage.completion_tokens if completion.usage else 0,
        )

    def _parse(self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]):
        try:
            return self._client.beta.chat.completions.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=schema,
            )
        except OpenAIError as exc:
            # Covers timeouts, connection/rate-limit/server errors, and the
            # SDK's own length/content-filter/invalid-JSON parse failures.
            logger.warning("OpenAI call failed: %s", exc)
            raise EvaluationEngineError(f"OpenAI provider failure: {exc}") from exc

    @staticmethod
    def _require_parsed(completion):
        choice = completion.choices[0]
        if choice.message.refusal:
            raise EvaluationEngineError(f"OpenAI refused the request: {choice.message.refusal}")
        parsed = choice.message.parsed
        if parsed is None:
            raise EvaluationEngineError("OpenAI response did not include parsed structured output")
        return parsed
