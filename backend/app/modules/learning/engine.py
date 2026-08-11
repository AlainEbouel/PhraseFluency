"""Deterministic pedagogical rules (docs/learning-engine.md).

Pure Python: no FastAPI, SQLAlchemy, or LLM-provider imports. Persistence
and orchestration live in service.py.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.modules.evaluations.enums import Verdict
from app.modules.learning.enums import TextProgressStatus

NATURAL_POINTS = 2
IMPERFECT_POINTS = 1
INCORRECT_POINTS = 0
HINT_CAPPED_POINTS = 1

DEFAULT_REQUIRED_NATURAL_EQUIVALENTS = 3
DEFAULT_REQUIRED_SCORE = 6
REPETITION_NATURAL_EQUIVALENT_INCREMENT = 1
REPETITION_SCORE_INCREMENT = 2

REVIEW_INTERVAL_INCORRECT = 20
REVIEW_INTERVAL_IMPERFECT = 30

DEFAULT_ACTIVE_BANK_SIZE = 100

_BASE_POINTS = {
    Verdict.CORRECT_NATURAL: NATURAL_POINTS,
    Verdict.CORRECT_UNNATURAL: IMPERFECT_POINTS,
    Verdict.CORRECT_WITH_WRITING_ISSUES: IMPERFECT_POINTS,
    Verdict.INCORRECT: INCORRECT_POINTS,
}


def points_for_verdict(verdict: Verdict, hint_used: bool) -> int:
    points = _BASE_POINTS[verdict]
    if hint_used:
        points = min(points, HINT_CAPPED_POINTS)
    return points


def is_imperfect(verdict: Verdict, hint_used: bool) -> bool:
    return hint_used or verdict != Verdict.CORRECT_NATURAL


def review_interval_for(verdict: Verdict, hint_used: bool) -> int | None:
    """Exercises-count interval after which a text becomes due again.

    None means the text returns through the normal active rotation
    instead of being scheduled as a review (a fully natural, hint-free
    answer).
    """
    if verdict == Verdict.INCORRECT:
        return REVIEW_INTERVAL_INCORRECT
    if hint_used or verdict in (
        Verdict.CORRECT_UNNATURAL,
        Verdict.CORRECT_WITH_WRITING_ISSUES,
    ):
        return REVIEW_INTERVAL_IMPERFECT
    return None


@dataclass(frozen=True)
class TextProgressState:
    status: TextProgressStatus
    mastery_score: int
    required_score: int = DEFAULT_REQUIRED_SCORE
    required_natural_equivalents: int = DEFAULT_REQUIRED_NATURAL_EQUIVALENTS
    times_presented: int = 0
    natural_count: int = 0
    unnatural_count: int = 0
    writing_issue_count: int = 0
    incorrect_count: int = 0
    hint_count: int = 0
    manually_acquired: bool = False
    perfect_learning_record: bool = True
    next_review_at_exercise: int | None = None
    rotation_position: int = 0


@dataclass(frozen=True)
class AttemptOutcome:
    progress: TextProgressState
    points_awarded: int
    is_imperfect: bool
    became_mastered: bool
    entered_test_waiting: bool


def record_attempt(
    progress: TextProgressState,
    verdict: Verdict,
    hint_used: bool,
    current_exercise_sequence: int,
) -> AttemptOutcome:
    if progress.status != TextProgressStatus.ACTIVE:
        raise ValueError("Only ACTIVE texts can receive a learning attempt")

    points = points_for_verdict(verdict, hint_used)
    imperfect = is_imperfect(verdict, hint_used)
    interval = review_interval_for(verdict, hint_used)

    new_score = progress.mastery_score + points
    new_perfect = progress.perfect_learning_record and not imperfect
    completes_learning = new_score >= progress.required_score

    if completes_learning:
        new_status = (
            TextProgressStatus.MASTERED
            if new_perfect
            else TextProgressStatus.WAITING_FOR_TEST_ASSIGNMENT
        )
        next_review = None
    else:
        new_status = TextProgressStatus.ACTIVE
        next_review = (
            current_exercise_sequence + interval if interval is not None else None
        )

    new_progress = replace(
        progress,
        status=new_status,
        mastery_score=new_score,
        times_presented=progress.times_presented + 1,
        natural_count=progress.natural_count
        + (1 if verdict == Verdict.CORRECT_NATURAL else 0),
        unnatural_count=progress.unnatural_count
        + (1 if verdict == Verdict.CORRECT_UNNATURAL else 0),
        writing_issue_count=progress.writing_issue_count
        + (1 if verdict == Verdict.CORRECT_WITH_WRITING_ISSUES else 0),
        incorrect_count=progress.incorrect_count
        + (1 if verdict == Verdict.INCORRECT else 0),
        hint_count=progress.hint_count + (1 if hint_used else 0),
        perfect_learning_record=new_perfect,
        next_review_at_exercise=next_review,
    )

    return AttemptOutcome(
        progress=new_progress,
        points_awarded=points,
        is_imperfect=imperfect,
        became_mastered=completes_learning and new_perfect,
        entered_test_waiting=completes_learning and not new_perfect,
    )


def increase_repetition(progress: TextProgressState) -> TextProgressState:
    return replace(
        progress,
        required_natural_equivalents=progress.required_natural_equivalents
        + REPETITION_NATURAL_EQUIVALENT_INCREMENT,
        required_score=progress.required_score + REPETITION_SCORE_INCREMENT,
    )


def manually_acquire(progress: TextProgressState) -> TextProgressState:
    return replace(
        progress,
        status=TextProgressStatus.MANUALLY_ACQUIRED,
        manually_acquired=True,
        next_review_at_exercise=None,
    )


def should_activate_next(
    active_count: int,
    unseen_available: bool,
    target_active_count: int = DEFAULT_ACTIVE_BANK_SIZE,
) -> bool:
    return unseen_available and active_count < target_active_count


@dataclass(frozen=True)
class QueueCandidate:
    text_id: str
    next_review_at_exercise: int | None
    rotation_position: int


def select_next(
    candidates: list[QueueCandidate], current_exercise_sequence: int
) -> QueueCandidate | None:
    """Oldest due review first, else the fairest normal-rotation item."""
    due = [
        c
        for c in candidates
        if c.next_review_at_exercise is not None
        and c.next_review_at_exercise <= current_exercise_sequence
    ]
    if due:
        return min(due, key=lambda c: (c.next_review_at_exercise, c.rotation_position))

    normal = [c for c in candidates if c.next_review_at_exercise is None]
    if normal:
        return min(normal, key=lambda c: c.rotation_position)
    return None
