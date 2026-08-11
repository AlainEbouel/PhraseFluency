"""DB-aware orchestration around EvaluationEngine.

Reference generation and grammar explanations are global, shared content
independent of any specific attempt, so they are generated, cached, and
committed immediately here. Evaluating an attempt is intentionally left
as a pure call-and-map (no persistence): architecture.md requires
Attempt + Evaluation + UserTextProgress to commit atomically, which is
the learning submit flow's responsibility, not this module's.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.evaluations.engine import EvaluationEngine
from app.modules.evaluations.enums import Verdict
from app.modules.evaluations.openai_engine import OpenAIEvaluationEngine
from app.modules.evaluations.ports import (
    EvaluationRequest,
    EvaluationResult,
    GrammarExplanationRequest,
    ReferenceGenerationRequest,
)
from app.modules.texts.models import LinguisticReference, TextVersion
from app.modules.texts.service import get_or_create_pattern
from app.shared.ai_usage import record_ai_usage
from app.shared.models import AIOperation

_engine: EvaluationEngine | None = None


def get_evaluation_engine() -> EvaluationEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = OpenAIEvaluationEngine(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    return _engine


def get_or_create_reference(
    db: Session, engine: EvaluationEngine, text_version: TextVersion
) -> LinguisticReference:
    existing = db.scalar(
        select(LinguisticReference).where(
            LinguisticReference.text_version_id == text_version.id
        )
    )
    if existing is not None:
        return existing

    result = engine.generate_reference(
        ReferenceGenerationRequest(
            french_text=text_version.french_text,
            exercise_type=text_version.exercise_type.value,
            difficulty=text_version.difficulty.value,
            contexts=list(text_version.contexts),
        )
    )

    reference = LinguisticReference(
        text_version_id=text_version.id,
        preferred_translation=result.preferred_translation,
        alternatives=result.alternatives,
        hints=result.hints,
        patterns=[pattern.expression for pattern in result.patterns],
        model=result.model,
        prompt_version=result.prompt_version,
    )
    db.add(reference)

    for pattern in result.patterns:
        get_or_create_pattern(
            db,
            expression=pattern.expression,
            meaning=pattern.meaning,
            example=pattern.example,
            text_version=text_version,
        )

    record_ai_usage(
        db,
        operation=AIOperation.REFERENCE_GENERATION,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )

    db.commit()
    db.refresh(reference)
    return reference


def run_evaluation(
    engine: EvaluationEngine,
    *,
    text_version: TextVersion,
    reference: LinguisticReference,
    user_answer: str,
    hint_used: bool,
    previous_verdict: Verdict | None = None,
) -> EvaluationResult:
    return engine.evaluate(
        EvaluationRequest(
            french_text=text_version.french_text,
            contexts=list(text_version.contexts),
            user_answer=user_answer,
            preferred_translation=reference.preferred_translation,
            alternatives=list(reference.alternatives),
            hint_used=hint_used,
            previous_verdict=previous_verdict,
        )
    )


def get_or_generate_grammar_explanation(
    db: Session,
    engine: EvaluationEngine,
    text_version: TextVersion,
    reference: LinguisticReference,
    user_answer: str | None = None,
) -> str:
    if reference.grammar_explanation:
        return reference.grammar_explanation

    result = engine.generate_grammar_explanation(
        GrammarExplanationRequest(
            french_text=text_version.french_text,
            preferred_translation=reference.preferred_translation,
            user_answer=user_answer,
        )
    )

    reference.grammar_explanation = result.explanation
    db.add(reference)

    record_ai_usage(
        db,
        operation=AIOperation.GRAMMAR_EXPLANATION,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )

    db.commit()
    return reference.grammar_explanation
