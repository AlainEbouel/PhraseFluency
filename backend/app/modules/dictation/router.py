from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.dictation import service
from app.modules.dictation.schemas import (
    DictationExerciseOut,
    DictationSubmitIn,
    DictationSubmitOut,
    DictationUnavailableOut,
)
from app.modules.evaluations.engine import EvaluationEngineError
from app.modules.evaluations.service import get_evaluation_engine
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/dictation", tags=["dictation"])


@router.get("/next", response_model=DictationExerciseOut | DictationUnavailableOut)
def next_exercise(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    engine = get_evaluation_engine()
    try:
        exercise = service.get_next_dictation_exercise(db, engine, user.id)
    except EvaluationEngineError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Dictation is temporarily unavailable, please retry: {exc}",
        ) from exc
    if exercise is None:
        return DictationUnavailableOut()
    return DictationExerciseOut(text_id=exercise.text_id, times_presented=exercise.times_presented)


@router.post("/submit", response_model=DictationSubmitOut)
def submit(
    payload: DictationSubmitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    engine = get_evaluation_engine()
    try:
        result = service.submit_dictation_answer(
            db,
            engine,
            user,
            text_id=payload.text_id,
            transcript=payload.user_answer,
            submission_id=payload.submission_id,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except EvaluationEngineError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Dictation is temporarily unavailable, please retry: {exc}",
        ) from exc
    return DictationSubmitOut(
        verdict=result.verdict, corrected_answer=result.corrected_answer, feedback=result.feedback
    )
