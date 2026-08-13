import random
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.evaluations.engine import EvaluationEngine
from app.modules.evaluations.enums import AttemptMode
from app.modules.evaluations.models import Attempt, Evaluation
from app.modules.evaluations.service import get_or_create_reference, run_evaluation
from app.modules.learning.enums import TextProgressStatus
from app.modules.learning.models import UserTextProgress
from app.modules.tests.engine import (
    TestTextState,
    apply_test_response,
    counts_as_test_success,
    group_into_tests,
    is_test_complete,
    start_attempt,
)
from app.modules.tests.models import Test, TestAttempt, TestAttemptStatus, TestText
from app.modules.texts.models import Difficulty, Text, TextVersion
from app.modules.users.models import User
from app.shared.ai_usage import record_ai_usage
from app.shared.mixins import utcnow
from app.shared.models import AIOperation


def assign_new_tests_if_ready(db: Session, user_id: uuid.UUID) -> list[Test]:
    """Group WAITING_FOR_TEST_ASSIGNMENT texts into immutable 25-text Tests.

    Does not commit — the caller (learning submit flow) persists this as
    part of one atomic transaction (architecture.md, Reliability).
    """
    waiting = db.scalars(
        select(UserTextProgress)
        .where(
            UserTextProgress.user_id == user_id,
            UserTextProgress.status == TextProgressStatus.WAITING_FOR_TEST_ASSIGNMENT,
        )
        .order_by(UserTextProgress.last_seen_at)
    ).all()

    text_ids = [str(progress.text_id) for progress in waiting]
    groups, _remainder = group_into_tests(text_ids)
    if not groups:
        return []

    progress_by_text_id = {str(progress.text_id): progress for progress in waiting}
    last_number = db.scalar(select(func.max(Test.number)).where(Test.user_id == user_id)) or 0

    created_tests: list[Test] = []
    for offset, group in enumerate(groups, start=1):
        shuffled = list(group)
        random.shuffle(shuffled)

        test = Test(user_id=user_id, number=last_number + offset)
        db.add(test)
        db.flush()

        for position, text_id_str in enumerate(shuffled):
            text_id = uuid.UUID(text_id_str)
            db.add(
                TestText(test_id=test.id, text_id=text_id, user_id=user_id, position=position)
            )
            progress_by_text_id[text_id_str].status = TextProgressStatus.TEST_ASSIGNED

        created_tests.append(test)

    return created_tests


def _latest_attempt(db: Session, test_id: uuid.UUID) -> TestAttempt | None:
    return db.scalar(
        select(TestAttempt)
        .where(TestAttempt.test_id == test_id)
        .order_by(TestAttempt.attempt_number.desc())
        .limit(1)
    )


def list_tests_for_user(
    db: Session, user_id: uuid.UUID
) -> list[tuple[Test, TestAttempt | None, int]]:
    tests = db.scalars(select(Test).where(Test.user_id == user_id).order_by(Test.number)).all()
    results = []
    for test in tests:
        latest = _latest_attempt(db, test.id)
        mastered_count = db.scalar(
            select(func.count())
            .select_from(TestText)
            .where(TestText.test_id == test.id, TestText.mastered_at.is_not(None))
        )
        results.append((test, latest, mastered_count))
    return results


def get_test_for_user(db: Session, user_id: uuid.UUID, test_id: uuid.UUID) -> Test | None:
    return db.scalar(select(Test).where(Test.id == test_id, Test.user_id == user_id))


def get_test_texts(db: Session, test_id: uuid.UUID) -> list[TestText]:
    return db.scalars(
        select(TestText).where(TestText.test_id == test_id).order_by(TestText.position)
    ).all()


def get_test_attempts(db: Session, test_id: uuid.UUID) -> list[TestAttempt]:
    return db.scalars(
        select(TestAttempt)
        .where(TestAttempt.test_id == test_id)
        .order_by(TestAttempt.attempt_number)
    ).all()


def start_or_resume_attempt(db: Session, test: Test) -> tuple[TestAttempt, bool]:
    """Returns (attempt, is_retake). Resets per-text progress on a fresh
    attempt so a retake presents all 25 texts unmastered again — historical
    Attempt/Evaluation rows from prior attempts are untouched.
    """
    latest = _latest_attempt(db, test.id)
    if latest is not None and latest.status == TestAttemptStatus.IN_PROGRESS:
        return latest, False

    attempt_state = start_attempt(latest.attempt_number if latest is not None else None)

    attempt = TestAttempt(
        test_id=test.id,
        attempt_number=attempt_state.attempt_number,
        status=TestAttemptStatus.IN_PROGRESS,
        started_at=utcnow(),
    )
    db.add(attempt)

    for test_text in get_test_texts(db, test.id):
        test_text.consecutive_successes = 0
        test_text.mastered_at = None
        db.add(test_text)

    db.commit()
    db.refresh(attempt)
    return attempt, attempt_state.is_retake


@dataclass(frozen=True)
class TestSubmitResult:
    evaluation: Evaluation
    consecutive_successes: int
    mastered: bool
    test_completed: bool
    difficulty: Difficulty


def submit_test_answer(
    db: Session,
    engine: EvaluationEngine,
    user: User,
    *,
    test: Test,
    text_id: uuid.UUID,
    user_answer: str,
    input_method,
    submission_id: str,
) -> TestSubmitResult:
    existing_attempt = db.scalar(
        select(Attempt).where(
            Attempt.submission_id == submission_id, Attempt.user_id == user.id
        )
    )
    if existing_attempt is not None:
        evaluation = db.get(Evaluation, existing_attempt.active_evaluation_id)
        test_text = db.get(TestText, (test.id, text_id))
        test_attempt = _latest_attempt(db, test.id)
        existing_text_version = db.get(TextVersion, existing_attempt.text_version_id)
        return TestSubmitResult(
            evaluation=evaluation,
            consecutive_successes=test_text.consecutive_successes,
            mastered=test_text.mastered_at is not None,
            test_completed=test_attempt.status == TestAttemptStatus.COMPLETED,
            difficulty=existing_text_version.difficulty,
        )

    test_attempt = _latest_attempt(db, test.id)
    if test_attempt is None or test_attempt.status != TestAttemptStatus.IN_PROGRESS:
        raise ValueError("No in-progress attempt for this test")

    test_text = db.get(TestText, (test.id, text_id))
    if test_text is None:
        raise ValueError("Text does not belong to this test")

    text = db.get(Text, text_id)
    text_version = db.get(TextVersion, text.current_version_id)
    reference = get_or_create_reference(db, engine, text_version)

    result = run_evaluation(
        engine,
        text_version=text_version,
        reference=reference,
        user_answer=user_answer,
        hint_used=False,
    )

    attempt = Attempt(
        user_id=user.id,
        text_version_id=text_version.id,
        mode=AttemptMode.RETAKE if test_attempt.attempt_number > 1 else AttemptMode.TEST,
        sequence_number=0,  # not meaningful outside the learning rotation
        user_answer=user_answer,
        input_method=input_method,
        hint_used=False,
        max_hint_level=0,
        submission_id=submission_id,
    )
    db.add(attempt)
    db.flush()

    evaluation = Evaluation(
        attempt_id=attempt.id,
        evaluation_number=1,
        verdict=result.verdict,
        meaning_preserved=result.meaning_preserved,
        grammar_correct=result.grammar_correct,
        natural_american_english=result.natural_american_english,
        writing_issues=result.writing_issues,
        corrected_answer=result.corrected_answer,
        feedback=result.feedback,
        error_categories=result.error_categories,
        model=result.model,
        prompt_version=result.prompt_version,
    )
    db.add(evaluation)
    db.flush()

    attempt.active_evaluation_id = evaluation.id
    db.add(attempt)

    previous_state = TestTextState(
        consecutive_successes=test_text.consecutive_successes,
        mastered=test_text.mastered_at is not None,
    )
    new_state = apply_test_response(previous_state, result.verdict)
    test_text.consecutive_successes = new_state.consecutive_successes
    if new_state.mastered and not previous_state.mastered:
        test_text.mastered_at = utcnow()
    db.add(test_text)

    if counts_as_test_success(result.verdict):
        test_attempt.correct_count += 1
    else:
        test_attempt.incorrect_count += 1
    test_attempt.latest_position = test_text.position
    db.add(test_attempt)

    all_states = [
        TestTextState(
            consecutive_successes=t.consecutive_successes, mastered=t.mastered_at is not None
        )
        for t in get_test_texts(db, test.id)
    ]
    if is_test_complete(all_states) and test_attempt.status != TestAttemptStatus.COMPLETED:
        test_attempt.status = TestAttemptStatus.COMPLETED
        test_attempt.completed_at = utcnow()
        db.add(test_attempt)

    record_ai_usage(
        db,
        operation=AIOperation.EVALUATION,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        user_id=user.id,
    )

    db.commit()
    db.refresh(test_text)
    db.refresh(test_attempt)

    return TestSubmitResult(
        evaluation=evaluation,
        consecutive_successes=test_text.consecutive_successes,
        mastered=test_text.mastered_at is not None,
        test_completed=test_attempt.status == TestAttemptStatus.COMPLETED,
        difficulty=text_version.difficulty,
    )
