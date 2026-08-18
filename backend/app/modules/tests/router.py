import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.evaluations.engine import EvaluationEngineError
from app.modules.evaluations.service import get_evaluation_engine
from app.modules.tests import service
from app.modules.tests.schemas import (
    StartAttemptOut,
    TestAttemptOut,
    TestDetailOut,
    TestSubmitIn,
    TestSubmitOut,
    TestSummaryOut,
    TestTextOut,
)
from app.modules.texts.models import Text
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/tests", tags=["tests"])


def _status_from_latest(latest) -> str:
    if latest is None:
        return "AVAILABLE"
    if latest.status.value == "COMPLETED":
        return "COMPLETED"
    return "IN_PROGRESS"


@router.get("", response_model=list[TestSummaryOut])
def list_tests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = service.list_tests_for_user(db, user.id)
    return [
        TestSummaryOut(
            id=test.id,
            number=test.number,
            status=_status_from_latest(latest),
            mastered_count=mastered_count,
            total_count=25,
            latest_attempt=TestAttemptOut.model_validate(latest) if latest else None,
        )
        for test, latest, mastered_count in rows
    ]


@router.get("/{test_id}", response_model=TestDetailOut)
def test_detail(
    test_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    test = service.get_test_for_user(db, user.id, test_id)
    if test is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test not found")

    test_texts = service.get_test_texts(db, test_id)
    text_lookup = {t.id: t for t in db.query(Text).filter(Text.id.in_([tt.text_id for tt in test_texts]))}

    attempts = service.get_test_attempts(db, test_id)
    latest = attempts[-1] if attempts else None

    return TestDetailOut(
        id=test.id,
        number=test.number,
        status=_status_from_latest(latest),
        texts=[
            TestTextOut(
                text_id=tt.text_id,
                french_text=text_lookup[tt.text_id].current_version.french_text,
                position=tt.position,
                consecutive_successes=tt.consecutive_successes,
                mastered=tt.mastered_at is not None,
            )
            for tt in test_texts
        ],
        attempts=[TestAttemptOut.model_validate(a) for a in attempts],
    )


@router.post("/{test_id}/start", response_model=StartAttemptOut)
def start_test(
    test_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    test = service.get_test_for_user(db, user.id, test_id)
    if test is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test not found")

    attempt, is_retake = service.start_or_resume_attempt(db, test)
    return StartAttemptOut(attempt=TestAttemptOut.model_validate(attempt), is_retake=is_retake)


@router.post("/{test_id}/submit", response_model=TestSubmitOut)
def submit_test(
    test_id: uuid.UUID,
    payload: TestSubmitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    test = service.get_test_for_user(db, user.id, test_id)
    if test is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test not found")

    engine = get_evaluation_engine()
    try:
        result = service.submit_test_answer(
            db,
            engine,
            user,
            test=test,
            text_id=payload.text_id,
            user_answer=payload.user_answer,
            input_method=payload.input_method,
            submission_id=payload.submission_id,
        )
    except EvaluationEngineError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Evaluation is temporarily unavailable, please retry: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    return TestSubmitOut(
        verdict=result.evaluation.verdict,
        feedback=result.evaluation.feedback,
        corrected_answer=result.evaluation.corrected_answer,
        usage_note_alternative=result.evaluation.usage_note_alternative,
        writing_issues=list(result.evaluation.writing_issues),
        consecutive_successes=result.consecutive_successes,
        mastered=result.mastered,
        test_completed=result.test_completed,
        difficulty=result.difficulty,
    )
