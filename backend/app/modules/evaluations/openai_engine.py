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
    WeaknessSuggestion,
    WeaknessSuggestionsRequest,
    WeaknessSuggestionsResult,
)
from app.modules.evaluations.prompts import (
    EVALUATION_PROMPT_VERSION,
    EVALUATION_SYSTEM_PROMPT,
    EXPLANATION_PROMPT_VERSION,
    EXPLANATION_SYSTEM_PROMPT,
    REFERENCE_PROMPT_VERSION,
    REFERENCE_SYSTEM_PROMPT,
    WEAKNESS_SUGGESTIONS_PROMPT_VERSION,
    WEAKNESS_SUGGESTIONS_SYSTEM_PROMPT,
    build_evaluation_user_prompt,
    build_explanation_user_prompt,
    build_reference_user_prompt,
    build_weakness_suggestions_user_prompt,
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
    # Field order matters: structured-output generation fills fields in
    # the order declared, so reasoning-oriented fields come BEFORE
    # verdict — forcing the model to think the case through instead of
    # committing to a verdict first and rationalizing it afterward.
    meaning_preserved: bool
    grammar_correct: bool
    natural_american_english: bool
    problematic_segment: str | None
    consistency_check: str
    verdict: Verdict
    usage_note_alternative: str | None
    writing_issues: list[str]
    corrected_answer: str | None
    feedback: str
    error_categories: list[ErrorCategory]


class _ExplanationSchema(BaseModel):
    explanation: str


class _WeaknessSuggestionSchema(BaseModel):
    category: str
    explanation: str
    suggestion: str


class _WeaknessSuggestionsSchema(BaseModel):
    suggestions: list[_WeaknessSuggestionSchema]


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

        # Defensive guard, not just a prompt instruction: a usage note is
        # never a correction, regardless of what the model returned.
        corrected_answer = parsed.corrected_answer
        if parsed.verdict == Verdict.CORRECT_WITH_USAGE_NOTE and corrected_answer is not None:
            logger.warning(
                "Evaluation returned CORRECT_WITH_USAGE_NOTE with a non-null "
                "corrected_answer; dropping it (a usage note is not a correction)."
            )
            corrected_answer = None

        # Observability only (never mutates the verdict): flag the exact
        # contradiction this prompt is designed to prevent — a segment
        # named as the problem reappearing in its own proposed fix. Requires
        # a multi-word segment: a single flagged word (e.g. "worry" in a
        # dropped-negation case) will always survive an otherwise-correct
        # fix like "Don't worry...", which isn't a real contradiction.
        if (
            parsed.verdict in (Verdict.CORRECT_UNNATURAL, Verdict.INCORRECT)
            and parsed.problematic_segment
            and len(parsed.problematic_segment.split()) > 1
            and corrected_answer
            and parsed.problematic_segment.lower() in corrected_answer.lower()
        ):
            logger.warning(
                "Possible evaluation self-inconsistency: problematic_segment %r "
                "reappears in corrected_answer %r for verdict %s",
                parsed.problematic_segment,
                corrected_answer,
                parsed.verdict,
            )

        return EvaluationResult(
            verdict=parsed.verdict,
            meaning_preserved=parsed.meaning_preserved,
            grammar_correct=parsed.grammar_correct,
            natural_american_english=parsed.natural_american_english,
            writing_issues=list(parsed.writing_issues),
            corrected_answer=corrected_answer,
            problematic_segment=parsed.problematic_segment,
            usage_note_alternative=parsed.usage_note_alternative,
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

    def generate_weakness_suggestions(
        self, request: WeaknessSuggestionsRequest
    ) -> WeaknessSuggestionsResult:
        completion = self._parse(
            system_prompt=WEAKNESS_SUGGESTIONS_SYSTEM_PROMPT,
            user_prompt=build_weakness_suggestions_user_prompt(request),
            schema=_WeaknessSuggestionsSchema,
        )
        parsed = self._require_parsed(completion)
        return WeaknessSuggestionsResult(
            suggestions=[
                WeaknessSuggestion(s.category, s.explanation, s.suggestion)
                for s in parsed.suggestions
            ],
            model=self._model,
            prompt_version=WEAKNESS_SUGGESTIONS_PROMPT_VERSION,
            input_tokens=completion.usage.prompt_tokens if completion.usage else 0,
            output_tokens=completion.usage.completion_tokens if completion.usage else 0,
        )

    def _parse(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel], temperature: float = 0.0
    ):
        try:
            return self._client.beta.chat.completions.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=schema,
                temperature=temperature,
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
