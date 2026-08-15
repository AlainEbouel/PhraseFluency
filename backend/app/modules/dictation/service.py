"""DB-aware orchestration for the dictation practice mode.

A fully separate track from learning/ — its own per-text progress and
rotation, no interaction with UserTextProgress/mastery/tests (an explicit
product decision: dictation practice never affects a text's translation
status or vice versa). Reuses select_next (learning/engine.py) since that
function is pure and generic over any (text_id, next_review_at_exercise,
rotation_position) candidates, and get_or_create_reference for content —
the same LinguisticReference.preferred_translation used by the
translation exercise is the dictation ground truth and TTS source.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.dictation.engine import check_transcript
from app.modules.dictation.models import DictationAttempt, UserDictationProgress
from app.modules.evaluations.engine import EvaluationEngine
from app.modules.evaluations.enums import Verdict
from app.modules.evaluations.service import get_or_create_reference
from app.modules.learning.engine import QueueCandidate, review_interval_for, select_next
from app.modules.texts.models import Text, TextVersion
from app.modules.users.models import User
from app.shared.mixins import utcnow

FEEDBACK_BY_VERDICT = {
    Verdict.CORRECT_NATURAL: "Parfait, transcription exacte !",
    Verdict.CORRECT_WITH_WRITING_ISSUES: (
        "Presque : quelques fautes d'orthographe ou de ponctuation."
    ),
    Verdict.INCORRECT: "Ce n'est pas tout à fait ce qui a été dit.",
}


@dataclass(frozen=True)
class DictationExercise:
    text_id: uuid.UUID
    times_presented: int


@dataclass(frozen=True)
class DictationSubmitResult:
    verdict: Verdict
    corrected_answer: str | None
    feedback: str


def _dictation_sequence(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(DictationAttempt)
        .where(DictationAttempt.user_id == user_id)
    )


def _next_rotation_position(db: Session) -> int:
    current_max = db.scalar(select(func.max(UserDictationProgress.rotation_position)))
    return (current_max or 0) + 1


def get_next_dictation_exercise(
    db: Session, engine: EvaluationEngine, user_id: uuid.UUID
) -> DictationExercise | None:
    enabled_text_ids = db.scalars(
        select(Text.id).where(Text.enabled.is_(True), Text.current_version_id.is_not(None))
    ).all()
    if not enabled_text_ids:
        return None

    progress_by_text = {
        row.text_id: row
        for row in db.scalars(
            select(UserDictationProgress).where(
                UserDictationProgress.user_id == user_id,
                UserDictationProgress.text_id.in_(enabled_text_ids),
            )
        ).all()
    }

    candidates = [
        QueueCandidate(
            text_id=str(text_id),
            next_review_at_exercise=(
                progress_by_text[text_id].next_review_at_exercise
                if text_id in progress_by_text
                else None
            ),
            rotation_position=(
                progress_by_text[text_id].rotation_position if text_id in progress_by_text else 0
            ),
        )
        for text_id in enabled_text_ids
    ]
    current_sequence = _dictation_sequence(db, user_id)
    chosen = select_next(candidates, current_sequence, last_review_at_exercise=None)
    if chosen is None:
        return None

    chosen_id = uuid.UUID(chosen.text_id)
    text = db.get(Text, chosen_id)
    text_version = db.get(TextVersion, text.current_version_id)
    # Generated eagerly (not deferred to submit) — the audio route needs
    # this reference to already exist before the learner can listen.
    get_or_create_reference(db, engine, text_version)

    times_presented = progress_by_text[chosen_id].times_presented if chosen_id in progress_by_text else 0
    return DictationExercise(text_id=chosen_id, times_presented=times_presented)


def submit_dictation_answer(
    db: Session,
    engine: EvaluationEngine,
    user: User,
    *,
    text_id: uuid.UUID,
    transcript: str,
    submission_id: str,
) -> DictationSubmitResult:
    existing = db.scalar(
        select(DictationAttempt).where(
            DictationAttempt.user_id == user.id, DictationAttempt.submission_id == submission_id
        )
    )
    if existing is not None:
        return DictationSubmitResult(
            verdict=existing.verdict,
            corrected_answer=existing.corrected_answer,
            feedback=FEEDBACK_BY_VERDICT[existing.verdict],
        )

    text = db.get(Text, text_id)
    if text is None or text.current_version_id is None:
        raise ValueError("Text not found")
    text_version = db.get(TextVersion, text.current_version_id)
    reference = get_or_create_reference(db, engine, text_version)

    verdict, corrected_answer = check_transcript(transcript, reference.preferred_translation)

    progress = db.get(UserDictationProgress, (user.id, text_id))
    if progress is None:
        progress = UserDictationProgress(
            user_id=user.id,
            text_id=text_id,
            times_presented=0,
            correct_count=0,
            writing_issue_count=0,
            incorrect_count=0,
            rotation_position=_next_rotation_position(db),
        )
        db.add(progress)

    progress.times_presented += 1
    if verdict == Verdict.CORRECT_NATURAL:
        progress.correct_count += 1
    elif verdict == Verdict.CORRECT_WITH_WRITING_ISSUES:
        progress.writing_issue_count += 1
    else:
        progress.incorrect_count += 1

    new_sequence = _dictation_sequence(db, user.id) + 1
    interval = review_interval_for(verdict, hint_used=False)
    if interval is None:
        progress.next_review_at_exercise = None
        progress.rotation_position = _next_rotation_position(db)
    else:
        progress.next_review_at_exercise = new_sequence + interval
    progress.last_seen_at = utcnow()
    db.add(progress)

    attempt = DictationAttempt(
        user_id=user.id,
        text_id=text_id,
        user_answer=transcript,
        verdict=verdict,
        corrected_answer=corrected_answer,
        submission_id=submission_id,
    )
    db.add(attempt)
    db.commit()

    return DictationSubmitResult(
        verdict=verdict, corrected_answer=corrected_answer, feedback=FEEDBACK_BY_VERDICT[verdict]
    )
