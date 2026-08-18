"""DB-aware orchestration of the learning loop.

Wires the pure Learning Engine (engine.py) and the EvaluationEngine to
persistence. submit_answer is the one place Attempt + Evaluation +
UserTextProgress (+ possible Test assignment) commit together in a
single transaction (architecture.md, Reliability: atomic persistence).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.evaluations.engine import EvaluationEngine
from app.modules.evaluations.enums import AttemptMode, InputMethod, Verdict
from app.modules.evaluations.models import Attempt, Evaluation
from app.modules.evaluations.ports import EvaluationResult
from app.modules.evaluations.service import get_or_create_reference, run_evaluation
from app.modules.learning.engine import (
    CEFR_ORDER,
    DEFAULT_ACTIVE_BANK_SIZE,
    DEFAULT_CURRENT_LEVEL_SHARE,
    MAX_CURRENT_LEVEL_SHARE,
    MAX_RETRIES,
    QueueCandidate,
    TextProgressState,
    bench,
    disable,
    increase_repetition,
    manually_acquire,
    points_for_verdict,
    prioritized_tiers,
    reactivate,
    record_attempt,
    select_next,
    should_activate_next,
    tier_weights,
)
from app.modules.learning.enums import TextProgressStatus
from app.modules.learning.models import UserLearningState, UserTextProgress
from app.modules.tests.models import Test
from app.modules.tests.service import assign_new_tests_if_ready
from app.modules.texts.models import Difficulty, LinguisticReference, Text, TextVersion
from app.modules.users.models import User
from app.shared.ai_usage import record_ai_usage
from app.shared.mixins import utcnow
from app.shared.models import AIOperation


def _to_domain(row: UserTextProgress) -> TextProgressState:
    return TextProgressState(
        status=row.status,
        mastery_score=row.mastery_score,
        required_score=row.required_score,
        required_natural_equivalents=row.required_natural_equivalents,
        times_presented=row.times_presented,
        natural_count=row.natural_count,
        unnatural_count=row.unnatural_count,
        writing_issue_count=row.writing_issue_count,
        incorrect_count=row.incorrect_count,
        hint_count=row.hint_count,
        manually_acquired=row.manually_acquired,
        perfect_learning_record=row.perfect_learning_record,
        next_review_at_exercise=row.next_review_at_exercise,
        rotation_position=row.rotation_position,
    )


def _apply_domain(row: UserTextProgress, state: TextProgressState) -> None:
    row.status = state.status
    row.mastery_score = state.mastery_score
    row.required_score = state.required_score
    row.required_natural_equivalents = state.required_natural_equivalents
    row.times_presented = state.times_presented
    row.natural_count = state.natural_count
    row.unnatural_count = state.unnatural_count
    row.writing_issue_count = state.writing_issue_count
    row.incorrect_count = state.incorrect_count
    row.hint_count = state.hint_count
    row.manually_acquired = state.manually_acquired
    row.perfect_learning_record = state.perfect_learning_record
    row.next_review_at_exercise = state.next_review_at_exercise
    row.rotation_position = state.rotation_position


def get_or_create_learning_state(db: Session, user_id: uuid.UUID) -> UserLearningState:
    state = db.get(UserLearningState, user_id)
    if state is None:
        state = UserLearningState(user_id=user_id)
        db.add(state)
        db.flush()
    return state


def choose_level(db: Session, user_id: uuid.UUID, level: Difficulty) -> UserLearningState:
    """Set the user's current CEFR level (once, at onboarding) and fill their bank."""
    learning_state = get_or_create_learning_state(db, user_id)
    learning_state.current_level = level
    if learning_state.target_level is None:
        idx = CEFR_ORDER.index(level)
        learning_state.target_level = CEFR_ORDER[min(idx + 1, len(CEFR_ORDER) - 1)]
    db.add(learning_state)
    db.flush()
    activate_up_to_bank_target(db, user_id)
    db.commit()
    return learning_state


@dataclass(frozen=True)
class LevelSettingsRejection:
    """current_level_share would exceed MAX_CURRENT_LEVEL_SHARE while the
    target level still differs from the current one — a soft reject the
    router turns into a message + a button to apply suggested_target_level,
    not a raw validation error."""

    message: str
    suggested_target_level: Difficulty


def update_level_settings(
    db: Session,
    user_id: uuid.UUID,
    *,
    target_level: Difficulty | None = None,
    current_level_share: float | None = None,
) -> UserLearningState | LevelSettingsRejection:
    learning_state = get_or_create_learning_state(db, user_id)
    if learning_state.current_level is None:
        raise ValueError("Choose a current level before adjusting level settings")

    new_target = target_level if target_level is not None else learning_state.target_level
    new_share = (
        current_level_share if current_level_share is not None else learning_state.current_level_share
    )

    if new_target is not None and CEFR_ORDER.index(new_target) < CEFR_ORDER.index(
        learning_state.current_level
    ):
        raise ValueError("Target level cannot be below the current level")

    collapsed = new_target == learning_state.current_level
    if not collapsed and new_share > MAX_CURRENT_LEVEL_SHARE:
        return LevelSettingsRejection(
            message=(
                "La part du niveau actuel ne peut pas dépasser 50 % tant que le "
                "niveau visé diffère du niveau actuel."
            ),
            suggested_target_level=learning_state.current_level,
        )

    learning_state.target_level = new_target
    learning_state.current_level_share = (
        DEFAULT_CURRENT_LEVEL_SHARE if collapsed else new_share
    )
    db.add(learning_state)
    db.flush()

    rebalance_active_bank(db, user_id)
    db.commit()
    db.refresh(learning_state)
    return learning_state


def _next_rotation_position(db: Session, user_id: uuid.UUID) -> int:
    current_max = db.scalar(
        select(func.max(UserTextProgress.rotation_position)).where(
            UserTextProgress.user_id == user_id
        )
    )
    return (current_max or 0) + 1


def _active_count(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(UserTextProgress)
        .where(UserTextProgress.user_id == user_id, UserTextProgress.status == TextProgressStatus.ACTIVE)
    )


def activate_up_to_bank_target(
    db: Session, user_id: uuid.UUID, target: int = DEFAULT_ACTIVE_BANK_SIZE
) -> int:
    """Top up the active bank with unseen texts (does not commit).

    Selection is difficulty-weighted around the user's chosen level (see
    docs/learning-engine.md); nothing activates until a level is chosen.
    """
    learning_state = get_or_create_learning_state(db, user_id)
    current_level = learning_state.current_level
    target_level = learning_state.target_level
    current_level_share = learning_state.current_level_share
    activated = 0
    while should_activate_next(
        _active_count(db, user_id),
        _has_unseen_text(db, user_id, current_level, target_level, current_level_share),
        target,
    ):
        candidate = _next_unseen_text(db, user_id, current_level, target_level, current_level_share)
        if candidate is None:
            break
        progress = UserTextProgress(
            user_id=user_id,
            text_id=candidate.id,
            status=TextProgressStatus.ACTIVE,
            first_seen_at=utcnow(),
            rotation_position=_next_rotation_position(db, user_id),
        )
        db.add(progress)
        db.flush()
        activated += 1
    return activated


def _seen_text_ids_subquery(user_id: uuid.UUID):
    return select(UserTextProgress.text_id).where(UserTextProgress.user_id == user_id)


def _has_unseen_text(
    db: Session,
    user_id: uuid.UUID,
    current_level: Difficulty | None,
    target_level: Difficulty | None,
    current_level_share: float,
) -> bool:
    return (
        _next_unseen_text(db, user_id, current_level, target_level, current_level_share)
        is not None
    )


def _active_counts_by_difficulty(db: Session, user_id: uuid.UUID) -> dict[Difficulty, int]:
    rows = db.execute(
        select(TextVersion.difficulty, func.count())
        .select_from(UserTextProgress)
        .join(Text, Text.id == UserTextProgress.text_id)
        .join(TextVersion, TextVersion.id == Text.current_version_id)
        .where(
            UserTextProgress.user_id == user_id,
            UserTextProgress.status == TextProgressStatus.ACTIVE,
        )
        .group_by(TextVersion.difficulty)
    ).all()
    return dict(rows)


def _next_unseen_text_at_difficulty(
    db: Session, user_id: uuid.UUID, difficulty: Difficulty
) -> Text | None:
    return db.scalar(
        select(Text)
        .join(TextVersion, Text.current_version_id == TextVersion.id)
        .where(
            Text.enabled.is_(True),
            Text.current_version_id.is_not(None),
            Text.id.not_in(_seen_text_ids_subquery(user_id)),
            TextVersion.difficulty == difficulty,
        )
        .order_by(Text.created_at)
        .limit(1)
    )


def _next_unseen_text_any_difficulty(db: Session, user_id: uuid.UUID) -> Text | None:
    return db.scalar(
        select(Text)
        .where(
            Text.enabled.is_(True),
            Text.current_version_id.is_not(None),
            Text.id.not_in(_seen_text_ids_subquery(user_id)),
        )
        .order_by(Text.created_at)
        .limit(1)
    )


def _next_unseen_text(
    db: Session,
    user_id: uuid.UUID,
    current_level: Difficulty | None,
    target_level: Difficulty | None,
    current_level_share: float,
) -> Text | None:
    if current_level is None or target_level is None:
        return None

    weights = tier_weights(current_level, target_level, current_level_share)
    active_counts = _active_counts_by_difficulty(db, user_id)
    for difficulty in prioritized_tiers(weights, active_counts):
        candidate = _next_unseen_text_at_difficulty(db, user_id, difficulty)
        if candidate is not None:
            return candidate

    # All weighted tiers are exhausted: draw from whatever remains.
    return _next_unseen_text_any_difficulty(db, user_id)


def _active_texts_at_difficulty_for_eviction(
    db: Session,
    user_id: uuid.UUID,
    difficulty: Difficulty,
    exclude_text_id: uuid.UUID | None,
    limit: int,
) -> list[UserTextProgress]:
    """Least-progressed-first: protects texts closer to mastery from
    having their momentum interrupted by a tier rebalance."""
    query = (
        select(UserTextProgress)
        .join(Text, Text.id == UserTextProgress.text_id)
        .join(TextVersion, TextVersion.id == Text.current_version_id)
        .where(
            UserTextProgress.user_id == user_id,
            UserTextProgress.status == TextProgressStatus.ACTIVE,
            TextVersion.difficulty == difficulty,
        )
    )
    if exclude_text_id is not None:
        query = query.where(UserTextProgress.text_id != exclude_text_id)
    return list(
        db.scalars(
            query.order_by(
                UserTextProgress.mastery_score.asc(), UserTextProgress.first_seen_at.asc()
            ).limit(limit)
        ).all()
    )


def _benched_texts_at_difficulty(
    db: Session, user_id: uuid.UUID, difficulty: Difficulty, limit: int
) -> list[UserTextProgress]:
    """Most-progressed-first: bring back the texts closest to mastery
    before pulling in a brand-new, never-seen text."""
    return list(
        db.scalars(
            select(UserTextProgress)
            .join(Text, Text.id == UserTextProgress.text_id)
            .join(TextVersion, TextVersion.id == Text.current_version_id)
            .where(
                UserTextProgress.user_id == user_id,
                UserTextProgress.status == TextProgressStatus.BENCHED,
                TextVersion.difficulty == difficulty,
            )
            .order_by(
                UserTextProgress.mastery_score.desc(), UserTextProgress.last_seen_at.desc()
            )
            .limit(limit)
        ).all()
    )


def rebalance_active_bank(db: Session, user_id: uuid.UUID) -> None:
    """Converge the active bank's composition to the current
    (current_level, target_level, current_level_share) split immediately.

    Invoked right after a level-settings change, not on every /next call —
    composition only needs to move when the ratio itself moves. Swaps
    ACTIVE<->BENCHED so bank size stays the same when possible; texts
    benched here keep every counter (mastery_score, natural_count, etc.)
    untouched, so a later reactivation resumes exactly where they left
    off. Does not commit — the caller does.
    """
    learning_state = get_or_create_learning_state(db, user_id)
    if learning_state.current_level is None or learning_state.target_level is None:
        return

    weights = tier_weights(
        learning_state.current_level, learning_state.target_level, learning_state.current_level_share
    )
    active_counts = _active_counts_by_difficulty(db, user_id)
    total_active = sum(active_counts.get(level, 0) for level in weights)
    if total_active == 0:
        return

    tiers = list(weights)
    target_counts: dict[Difficulty, int] = {}
    allocated = 0
    for level in tiers[:-1]:
        target_counts[level] = int(weights[level] * total_active)
        allocated += target_counts[level]
    target_counts[tiers[-1]] = total_active - allocated  # remainder, sums exactly

    protected_text_id = learning_state.current_text_id

    over = {
        level: active_counts.get(level, 0) - target_counts[level]
        for level in tiers
        if active_counts.get(level, 0) > target_counts[level]
    }
    under = {
        level: target_counts[level] - active_counts.get(level, 0)
        for level in tiers
        if active_counts.get(level, 0) < target_counts[level]
    }

    for level, excess in over.items():
        for row in _active_texts_at_difficulty_for_eviction(
            db, user_id, level, protected_text_id, excess
        ):
            _apply_domain(row, bench(_to_domain(row)))
            db.add(row)
    db.flush()

    for level, deficit in under.items():
        remaining = deficit
        for row in _benched_texts_at_difficulty(db, user_id, level, remaining):
            _apply_domain(row, reactivate(_to_domain(row)))
            db.add(row)
            remaining -= 1
        db.flush()
        while remaining > 0:
            candidate = _next_unseen_text_at_difficulty(db, user_id, level)
            if candidate is None:
                break
            db.add(
                UserTextProgress(
                    user_id=user_id,
                    text_id=candidate.id,
                    status=TextProgressStatus.ACTIVE,
                    first_seen_at=utcnow(),
                    rotation_position=_next_rotation_position(db, user_id),
                )
            )
            db.flush()
            remaining -= 1

    # Degenerate case (a tier ran out of both benched and unseen supply):
    # let the normal top-up path fill any still-missing slots — capped at
    # the ORIGINAL total, never growing the bank as a rebalance side effect.
    activate_up_to_bank_target(db, user_id, target=total_active)


@dataclass(frozen=True)
class NextExercise:
    progress: UserTextProgress
    learning_state: UserLearningState
    is_review: bool


def get_next_exercise(db: Session, user: User) -> NextExercise | None:
    activate_up_to_bank_target(db, user.id)
    db.commit()

    learning_state = get_or_create_learning_state(db, user.id)

    active_rows = db.scalars(
        select(UserTextProgress).where(
            UserTextProgress.user_id == user.id, UserTextProgress.status == TextProgressStatus.ACTIVE
        )
    ).all()
    if not active_rows:
        return None

    candidates = [
        QueueCandidate(
            text_id=str(row.text_id),
            next_review_at_exercise=row.next_review_at_exercise,
            rotation_position=row.rotation_position,
        )
        for row in active_rows
    ]
    chosen = select_next(
        candidates, learning_state.exercise_sequence, learning_state.last_review_at_exercise
    )
    if chosen is None:
        return None

    row_by_id = {str(row.text_id): row for row in active_rows}
    progress_row = row_by_id[chosen.text_id]

    if learning_state.current_text_id != progress_row.text_id:
        learning_state.current_text_id = progress_row.text_id
        learning_state.current_draft = None
        learning_state.current_hint_level = 0
        if progress_row.next_review_at_exercise is not None:
            learning_state.last_review_at_exercise = learning_state.exercise_sequence
        db.add(learning_state)
        db.commit()

    return NextExercise(
        progress=progress_row,
        learning_state=learning_state,
        is_review=progress_row.next_review_at_exercise is not None,
    )


def save_draft(db: Session, learning_state: UserLearningState, draft: str) -> None:
    learning_state.current_draft = draft
    db.add(learning_state)
    db.commit()


def request_hint(
    db: Session, learning_state: UserLearningState, reference: LinguisticReference
) -> UserLearningState:
    max_level = len(reference.hints)
    if learning_state.current_hint_level < max_level:
        learning_state.current_hint_level += 1
        db.add(learning_state)
        db.commit()
    return learning_state


def skip_current(db: Session, user_id: uuid.UUID, learning_state: UserLearningState) -> None:
    if learning_state.current_text_id is not None:
        progress = db.get(UserTextProgress, (user_id, learning_state.current_text_id))
        if progress is not None:
            progress.rotation_position = _next_rotation_position(db, user_id)
            db.add(progress)

    learning_state.current_text_id = None
    learning_state.current_draft = None
    learning_state.current_hint_level = 0
    db.add(learning_state)
    db.commit()


@dataclass(frozen=True)
class SubmitResult:
    evaluation: Evaluation
    reference: LinguisticReference
    progress: UserTextProgress
    points_awarded: int
    new_tests_created: int
    difficulty: Difficulty
    committed: bool = True


@dataclass(frozen=True)
class PendingSubmitResult:
    """Not yet committed: no Attempt/Evaluation/progress side effects.

    Returned for CORRECT_WITH_WRITING_ISSUES (unlimited free retries) and
    for CORRECT_UNNATURAL/INCORRECT's "want to improve?" offer, given up
    to MAX_RETRIES times. All withhold the reference answer until a
    finalize=True call (or MAX_RETRIES is reached) commits it, so
    retrying never costs points or advances the queue.
    """

    verdict: Verdict
    feedback: str
    writing_issues: list[str]
    difficulty: Difficulty
    committed: bool = False


def _submit_result_from_existing_attempt(db: Session, attempt: Attempt) -> SubmitResult:
    evaluation = db.get(Evaluation, attempt.active_evaluation_id)
    text_version = db.get(TextVersion, attempt.text_version_id)
    reference = db.scalar(
        select(LinguisticReference).where(LinguisticReference.text_version_id == text_version.id)
    )
    progress = db.get(UserTextProgress, (attempt.user_id, text_version.text_id))
    return SubmitResult(
        evaluation=evaluation,
        reference=reference,
        progress=progress,
        points_awarded=points_for_verdict(evaluation.verdict, attempt.hint_used),
        new_tests_created=0,
        difficulty=text_version.difficulty,
    )


def submit_answer(
    db: Session,
    engine: EvaluationEngine,
    user: User,
    *,
    text_id: uuid.UUID,
    user_answer: str,
    input_method: InputMethod,
    submission_id: str,
    finalize: bool = False,
    retry_count: int = 0,
) -> SubmitResult | PendingSubmitResult:
    existing_attempt = db.scalar(
        select(Attempt).where(
            Attempt.submission_id == submission_id, Attempt.user_id == user.id
        )
    )
    if existing_attempt is not None:
        return _submit_result_from_existing_attempt(db, existing_attempt)

    progress = db.get(UserTextProgress, (user.id, text_id))
    if progress is None or progress.status != TextProgressStatus.ACTIVE:
        raise ValueError("Text is not currently active for this user")

    text = db.get(Text, text_id)
    text_version = db.get(TextVersion, text.current_version_id)
    reference = get_or_create_reference(db, engine, text_version)

    learning_state = get_or_create_learning_state(db, user.id)
    hint_used = learning_state.current_hint_level > 0

    # May raise EvaluationEngineError: nothing below has executed yet, so
    # no Attempt/Evaluation/progress mutation happens on failure — the
    # draft was already persisted separately by the autosave endpoint.
    result = run_evaluation(
        engine,
        text_version=text_version,
        reference=reference,
        user_answer=user_answer,
        hint_used=hint_used,
    )

    # Real API cost is recorded regardless of whether this round commits —
    # cost tracking is an operational concern, not a pedagogical one.
    record_ai_usage(
        db,
        operation=AIOperation.EVALUATION,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        user_id=user.id,
    )

    should_commit = (
        result.verdict in (Verdict.CORRECT_NATURAL, Verdict.CORRECT_WITH_USAGE_NOTE)
        or finalize
        or (
            result.verdict in (Verdict.CORRECT_UNNATURAL, Verdict.INCORRECT)
            and retry_count >= MAX_RETRIES
        )
    )

    if not should_commit:
        # Writing-issue retries are unlimited; CORRECT_UNNATURAL/INCORRECT
        # get up to MAX_RETRIES "want to improve?" offers (product
        # decision) before committing unconditionally. No Attempt/
        # Evaluation/progress side effects until finalized.
        db.commit()
        return PendingSubmitResult(
            verdict=result.verdict,
            feedback=result.feedback,
            writing_issues=list(result.writing_issues),
            difficulty=text_version.difficulty,
        )

    new_sequence = learning_state.exercise_sequence + 1

    attempt = Attempt(
        user_id=user.id,
        text_version_id=text_version.id,
        mode=AttemptMode.LEARNING,
        sequence_number=new_sequence,
        user_answer=user_answer,
        input_method=input_method,
        hint_used=hint_used,
        max_hint_level=learning_state.current_hint_level,
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
        problematic_segment=result.problematic_segment,
        usage_note_alternative=result.usage_note_alternative,
        feedback=result.feedback,
        error_categories=result.error_categories,
        model=result.model,
        prompt_version=result.prompt_version,
    )
    db.add(evaluation)
    db.flush()

    attempt.active_evaluation_id = evaluation.id
    db.add(attempt)

    outcome = record_attempt(_to_domain(progress), result.verdict, hint_used, new_sequence)
    _apply_domain(progress, outcome.progress)
    if progress.status == TextProgressStatus.ACTIVE and progress.next_review_at_exercise is None:
        # Natural, hint-free answer: text returns through the normal
        # rotation rather than staying at the front of the queue.
        progress.rotation_position = _next_rotation_position(db, user.id)
    if progress.first_seen_at is None:
        progress.first_seen_at = utcnow()
    progress.last_seen_at = utcnow()
    db.add(progress)

    learning_state.exercise_sequence = new_sequence
    learning_state.current_text_id = None
    learning_state.current_draft = None
    learning_state.current_hint_level = 0
    db.add(learning_state)

    new_tests: list[Test] = []
    if outcome.became_mastered or outcome.entered_test_waiting:
        activate_up_to_bank_target(db, user.id)
    if outcome.entered_test_waiting:
        new_tests = assign_new_tests_if_ready(db, user.id)

    db.commit()
    db.refresh(progress)

    return SubmitResult(
        evaluation=evaluation,
        reference=reference,
        progress=progress,
        points_awarded=outcome.points_awarded,
        new_tests_created=len(new_tests),
        difficulty=text_version.difficulty,
    )


def increase_repetition_for_text(
    db: Session, user_id: uuid.UUID, text_id: uuid.UUID
) -> UserTextProgress:
    progress = db.get(UserTextProgress, (user_id, text_id))
    if progress is None:
        raise ValueError("No progress found for this text")
    _apply_domain(progress, increase_repetition(_to_domain(progress)))
    db.add(progress)
    db.commit()
    return progress


def manually_acquire_text(db: Session, user_id: uuid.UUID, text_id: uuid.UUID) -> UserTextProgress:
    progress = db.get(UserTextProgress, (user_id, text_id))
    if progress is None or progress.status != TextProgressStatus.ACTIVE:
        raise ValueError("Only an active text can be manually acquired")
    _apply_domain(progress, manually_acquire(_to_domain(progress)))
    db.add(progress)
    activate_up_to_bank_target(db, user_id)
    db.commit()
    return progress


def list_user_text_bank(
    db: Session, user_id: uuid.UUID, search: str | None = None
) -> list[tuple[uuid.UUID, str, TextProgressStatus, int, int, int]]:
    query = (
        select(
            UserTextProgress.text_id,
            TextVersion.french_text,
            UserTextProgress.status,
            UserTextProgress.natural_count,
            UserTextProgress.incorrect_count,
            UserTextProgress.times_presented,
        )
        .join(Text, Text.id == UserTextProgress.text_id)
        .join(TextVersion, TextVersion.id == Text.current_version_id)
        .where(UserTextProgress.user_id == user_id)
        .order_by(TextVersion.french_text)
    )
    if search:
        query = query.where(TextVersion.french_text.ilike(f"%{search}%"))
    return list(db.execute(query).all())


def disable_text_for_user(db: Session, user_id: uuid.UUID, text_id: uuid.UUID) -> UserTextProgress:
    """Permanently hide a text from one user's bank (admin action, no undo).

    A replacement is pulled in from the general bank when the disabled text
    was occupying an active slot; otherwise there is nothing to replenish.
    """
    progress = db.get(UserTextProgress, (user_id, text_id))
    if progress is None:
        progress = UserTextProgress(user_id=user_id, text_id=text_id, status=TextProgressStatus.DISABLED)
        db.add(progress)
        db.commit()
        return progress
    if progress.status == TextProgressStatus.DISABLED:
        return progress
    was_active = progress.status == TextProgressStatus.ACTIVE
    _apply_domain(progress, disable(_to_domain(progress)))
    db.add(progress)
    if was_active:
        activate_up_to_bank_target(db, user_id)
    db.commit()
    return progress


def get_user_text_bank_item(
    db: Session, user_id: uuid.UUID, text_id: uuid.UUID
) -> tuple[uuid.UUID, str, TextProgressStatus, int, int, int] | None:
    return db.execute(
        select(
            UserTextProgress.text_id,
            TextVersion.french_text,
            UserTextProgress.status,
            UserTextProgress.natural_count,
            UserTextProgress.incorrect_count,
            UserTextProgress.times_presented,
        )
        .join(Text, Text.id == UserTextProgress.text_id)
        .join(TextVersion, TextVersion.id == Text.current_version_id)
        .where(UserTextProgress.user_id == user_id, UserTextProgress.text_id == text_id)
    ).first()


def reevaluate_text(
    db: Session, engine: EvaluationEngine, user: User, text_id: uuid.UUID
) -> Evaluation:
    latest_attempt = db.scalar(
        select(Attempt)
        .join(TextVersion, Attempt.text_version_id == TextVersion.id)
        .where(Attempt.user_id == user.id, TextVersion.text_id == text_id)
        .order_by(Attempt.created_at.desc())
        .limit(1)
    )
    if latest_attempt is None:
        raise ValueError("No attempt found for this text")

    previous_evaluation = db.get(Evaluation, latest_attempt.active_evaluation_id)
    text_version = db.get(TextVersion, latest_attempt.text_version_id)
    reference = get_or_create_reference(db, engine, text_version)

    result = run_evaluation(
        engine,
        text_version=text_version,
        reference=reference,
        user_answer=latest_attempt.user_answer,
        hint_used=latest_attempt.hint_used,
        previous_verdict=previous_evaluation.verdict,
    )

    evaluation_number = (
        db.scalar(
            select(func.max(Evaluation.evaluation_number)).where(
                Evaluation.attempt_id == latest_attempt.id
            )
        )
        or 0
    )

    new_evaluation = Evaluation(
        attempt_id=latest_attempt.id,
        evaluation_number=evaluation_number + 1,
        verdict=result.verdict,
        meaning_preserved=result.meaning_preserved,
        grammar_correct=result.grammar_correct,
        natural_american_english=result.natural_american_english,
        writing_issues=result.writing_issues,
        corrected_answer=result.corrected_answer,
        problematic_segment=result.problematic_segment,
        usage_note_alternative=result.usage_note_alternative,
        feedback=result.feedback,
        error_categories=result.error_categories,
        model=result.model,
        prompt_version=result.prompt_version,
    )
    db.add(new_evaluation)
    db.flush()

    latest_attempt.active_evaluation_id = new_evaluation.id
    db.add(latest_attempt)

    record_ai_usage(
        db,
        operation=AIOperation.REEVALUATION,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        user_id=user.id,
    )

    db.commit()
    return new_evaluation


def explore_alternative(
    db: Session, engine: EvaluationEngine, user: User, text_id: uuid.UUID, user_answer: str
) -> EvaluationResult:
    """Check an arbitrary alternative answer, purely out of curiosity.

    Never touches Attempt/Evaluation history or UserTextProgress — the
    score, schedule, and mastery record are unaffected, however many
    times this is called (explicit product decision: "sans conséquence").
    """
    text = db.get(Text, text_id)
    if text is None:
        raise ValueError("Text not found")
    text_version = db.get(TextVersion, text.current_version_id)
    reference = get_or_create_reference(db, engine, text_version)

    result = run_evaluation(
        engine,
        text_version=text_version,
        reference=reference,
        user_answer=user_answer,
        hint_used=False,
    )

    record_ai_usage(
        db,
        operation=AIOperation.EVALUATION,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        user_id=user.id,
    )
    db.commit()
    return result
