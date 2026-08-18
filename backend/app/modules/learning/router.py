import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.evaluations.engine import EvaluationEngineError
from app.modules.evaluations.models import Attempt
from app.modules.evaluations.service import (
    get_evaluation_engine,
    get_or_create_reference,
    get_or_generate_grammar_explanation,
)
from app.modules.learning import service
from app.modules.learning.schemas import (
    AcquireOut,
    ChooseLevelIn,
    DraftIn,
    ExerciseOut,
    ExplanationOut,
    ExploreIn,
    ExploreOut,
    HintOut,
    LevelRequiredOut,
    NoExerciseAvailableOut,
    PendingSubmitOut,
    ProgressOut,
    ReevaluateOut,
    RepetitionOut,
    SubmitIn,
    SubmitOut,
)
from app.modules.texts.models import Text, TextVersion
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/learning", tags=["learning"])


def _progress_out(row) -> ProgressOut:
    return ProgressOut.model_validate(row)


@router.post("/level", status_code=status.HTTP_204_NO_CONTENT)
def choose_level(
    payload: ChooseLevelIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service.choose_level(db, user.id, payload.level)


@router.get("/next", response_model=ExerciseOut | LevelRequiredOut | NoExerciseAvailableOut)
def next_exercise(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    learning_state = service.get_or_create_learning_state(db, user.id)
    db.commit()
    if learning_state.current_level is None:
        return LevelRequiredOut()

    next_ex = service.get_next_exercise(db, user)
    if next_ex is None:
        return NoExerciseAvailableOut(
            message="No exercise available yet. Import or unlock more texts to continue learning."
        )

    text = db.get(Text, next_ex.progress.text_id)
    text_version = db.get(TextVersion, text.current_version_id)
    engine = get_evaluation_engine()
    reference = get_or_create_reference(db, engine, text_version)

    hint_level = next_ex.learning_state.current_hint_level
    return ExerciseOut(
        text_id=next_ex.progress.text_id,
        french_text=text_version.french_text,
        is_review=next_ex.is_review,
        draft=next_ex.learning_state.current_draft,
        hint_level=hint_level,
        hints_revealed=list(reference.hints[:hint_level]),
        progress=_progress_out(next_ex.progress),
    )


@router.put("/draft", status_code=status.HTTP_204_NO_CONTENT)
def save_draft(
    payload: DraftIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    learning_state = service.get_or_create_learning_state(db, user.id)
    if learning_state.current_text_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No exercise is currently in progress")
    service.save_draft(db, learning_state, payload.draft)


@router.post("/hint", response_model=HintOut)
def request_hint(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    learning_state = service.get_or_create_learning_state(db, user.id)
    if learning_state.current_text_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No exercise is currently in progress")

    text = db.get(Text, learning_state.current_text_id)
    text_version = db.get(TextVersion, text.current_version_id)
    engine = get_evaluation_engine()
    reference = get_or_create_reference(db, engine, text_version)

    learning_state = service.request_hint(db, learning_state, reference)
    hint_level = learning_state.current_hint_level
    return HintOut(hint_level=hint_level, hints_revealed=list(reference.hints[:hint_level]))


@router.post("/skip", status_code=status.HTTP_204_NO_CONTENT)
def skip(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    learning_state = service.get_or_create_learning_state(db, user.id)
    service.skip_current(db, user.id, learning_state)


@router.post("/submit", response_model=SubmitOut | PendingSubmitOut)
def submit(
    payload: SubmitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    learning_state = service.get_or_create_learning_state(db, user.id)
    if learning_state.current_text_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No exercise is currently in progress")

    engine = get_evaluation_engine()
    try:
        result = service.submit_answer(
            db,
            engine,
            user,
            text_id=learning_state.current_text_id,
            user_answer=payload.user_answer,
            input_method=payload.input_method,
            submission_id=payload.submission_id,
            finalize=payload.finalize,
            unnatural_retry_used=payload.unnatural_retry_used,
        )
    except EvaluationEngineError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Evaluation is temporarily unavailable, please retry: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    if not result.committed:
        return PendingSubmitOut(
            verdict=result.verdict,
            feedback=result.feedback,
            writing_issues=result.writing_issues,
            difficulty=result.difficulty,
        )

    return SubmitOut(
        verdict=result.evaluation.verdict,
        points_awarded=result.points_awarded,
        corrected_answer=result.evaluation.corrected_answer,
        usage_note_alternative=result.evaluation.usage_note_alternative,
        feedback=result.evaluation.feedback,
        writing_issues=list(result.evaluation.writing_issues),
        preferred_translation=result.reference.preferred_translation,
        alternatives=list(result.reference.alternatives),
        patterns=list(result.reference.patterns),
        error_categories=list(result.evaluation.error_categories),
        progress=_progress_out(result.progress),
        new_tests_created=result.new_tests_created,
        difficulty=result.difficulty,
    )


@router.post("/{text_id}/repetition", response_model=RepetitionOut)
def increase_repetition(
    text_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        progress = service.increase_repetition_for_text(db, user.id, text_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return RepetitionOut(progress=_progress_out(progress))


@router.post("/{text_id}/acquire", response_model=AcquireOut)
def acquire(
    text_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        progress = service.manually_acquire_text(db, user.id, text_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AcquireOut(progress=_progress_out(progress))


@router.post("/{text_id}/reevaluate", response_model=ReevaluateOut)
def reevaluate(
    text_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    engine = get_evaluation_engine()
    try:
        evaluation = service.reevaluate_text(db, engine, user, text_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except EvaluationEngineError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Re-evaluation is temporarily unavailable, please retry: {exc}",
        ) from exc
    return ReevaluateOut(
        verdict=evaluation.verdict,
        feedback=evaluation.feedback,
        corrected_answer=evaluation.corrected_answer,
        usage_note_alternative=evaluation.usage_note_alternative,
    )


@router.get("/{text_id}/explanation", response_model=ExplanationOut)
def explanation(
    text_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    text = db.get(Text, text_id)
    if text is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Text not found")
    text_version = db.get(TextVersion, text.current_version_id)
    engine = get_evaluation_engine()
    reference = get_or_create_reference(db, engine, text_version)

    latest = db.scalar(
        select(Attempt)
        .where(Attempt.user_id == user.id, Attempt.text_version_id == text_version.id)
        .order_by(Attempt.created_at.desc())
        .limit(1)
    )
    latest_attempt_answer = latest.user_answer if latest is not None else None

    try:
        text_explanation = get_or_generate_grammar_explanation(
            db, engine, text_version, reference, latest_attempt_answer
        )
    except EvaluationEngineError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Explanation is temporarily unavailable, please retry: {exc}",
        ) from exc

    return ExplanationOut(explanation=text_explanation)


@router.post("/{text_id}/explore", response_model=ExploreOut)
def explore(
    text_id: uuid.UUID,
    payload: ExploreIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Check an arbitrary alternative answer, purely out of curiosity.

    Never touches Attempt/Evaluation history or UserTextProgress — the
    score, schedule, and mastery record are completely unaffected,
    however many times this is called (explicit product decision).
    """
    engine = get_evaluation_engine()
    try:
        result = service.explore_alternative(db, engine, user, text_id, payload.user_answer)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except EvaluationEngineError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"This check is temporarily unavailable, please retry: {exc}",
        ) from exc

    return ExploreOut(
        verdict=result.verdict,
        meaning_preserved=result.meaning_preserved,
        corrected_answer=result.corrected_answer,
        usage_note_alternative=result.usage_note_alternative,
        feedback=result.feedback,
        writing_issues=list(result.writing_issues),
    )
