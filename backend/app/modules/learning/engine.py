"""Deterministic pedagogical rules (docs/learning-engine.md).

Pure Python: no FastAPI, SQLAlchemy, or LLM-provider imports. Persistence
and orchestration live in service.py.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.modules.evaluations.enums import Verdict
from app.modules.learning.enums import TextProgressStatus
from app.modules.texts.models import Difficulty

NATURAL_POINTS = 2
IMPERFECT_POINTS = 1
INCORRECT_POINTS = 0
HINT_CAPPED_POINTS = 1

DEFAULT_REQUIRED_NATURAL_EQUIVALENTS = 2
DEFAULT_REQUIRED_SCORE = 4
REPETITION_NATURAL_EQUIVALENT_INCREMENT = 1
REPETITION_SCORE_INCREMENT = 2

REVIEW_INTERVAL_INCORRECT = 20
REVIEW_INTERVAL_IMPERFECT = 30
MIN_EXERCISES_BETWEEN_REVIEWS = 10

DEFAULT_ACTIVE_BANK_SIZE = 100

CEFR_ORDER = [
    Difficulty.A1,
    Difficulty.A2,
    Difficulty.B1,
    Difficulty.B2,
    Difficulty.C1,
    Difficulty.C2,
]
TIER_WEIGHTS = (0.15, 0.75, 0.10)  # current level, next level up, two up

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


def tier_weights(current_level: Difficulty) -> dict[Difficulty, float]:
    """Target share of the active bank for the user's level and the two above.

    Levels past C2 clamp to C2; when two tiers clamp to the same level
    their weights merge (e.g. current=C1 -> {C1: 0.15, C2: 0.85};
    current=C2 -> {C2: 1.0}).
    """
    start = CEFR_ORDER.index(current_level)
    weights: dict[Difficulty, float] = {}
    for offset, weight in zip(range(3), TIER_WEIGHTS):
        level = CEFR_ORDER[min(start + offset, len(CEFR_ORDER) - 1)]
        weights[level] = weights.get(level, 0.0) + weight
    return weights


def prioritized_tiers(
    weights: dict[Difficulty, float], active_counts: dict[Difficulty, int]
) -> list[Difficulty]:
    """Weighted tiers ordered most-under-served-first.

    Deficit is each tier's target share of the (hypothetically +1) active
    bank minus how many of that difficulty are active now. Ties keep a
    stable order (target level before the tiers around it would only tie
    at bank size 0, where weight order already prioritizes correctly).
    """
    total_active = sum(active_counts.get(level, 0) for level in weights)

    def deficit(level: Difficulty) -> float:
        return weights[level] * (total_active + 1) - active_counts.get(level, 0)

    return sorted(weights, key=deficit, reverse=True)


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
    candidates: list[QueueCandidate],
    current_exercise_sequence: int,
    last_review_at_exercise: int | None = None,
    min_review_gap: int = MIN_EXERCISES_BETWEEN_REVIEWS,
) -> QueueCandidate | None:
    """Oldest due review first, else the fairest normal-rotation item.

    Due reviews are injected one at a time: once a review has been
    served, another one only becomes eligible after min_review_gap
    further exercises, even if several texts are simultaneously due
    (they stay due and get picked up on a later call). The gap is
    skipped only when a due review is the sole content left to serve.
    """
    due = [
        c
        for c in candidates
        if c.next_review_at_exercise is not None
        and c.next_review_at_exercise <= current_exercise_sequence
    ]
    normal = [c for c in candidates if c.next_review_at_exercise is None]

    gap_satisfied = (
        last_review_at_exercise is None
        or current_exercise_sequence - last_review_at_exercise >= min_review_gap
    )

    if due and (gap_satisfied or not normal):
        return min(due, key=lambda c: (c.next_review_at_exercise, c.rotation_position))

    if normal:
        return min(normal, key=lambda c: c.rotation_position)
    return None
