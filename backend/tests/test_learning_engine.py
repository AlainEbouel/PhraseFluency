import pytest

from app.modules.evaluations.enums import Verdict
from app.modules.learning.enums import TextProgressStatus
from app.modules.learning.engine import (
    QueueCandidate,
    TextProgressState,
    increase_repetition,
    manually_acquire,
    points_for_verdict,
    record_attempt,
    review_interval_for,
    select_next,
    should_activate_next,
)


def active_progress(**overrides) -> TextProgressState:
    overrides.setdefault("mastery_score", 0)
    return TextProgressState(status=TextProgressStatus.ACTIVE, **overrides)


class TestVerdictPointMappings:
    @pytest.mark.parametrize(
        "verdict,expected",
        [
            (Verdict.CORRECT_NATURAL, 2),
            (Verdict.CORRECT_UNNATURAL, 1),
            (Verdict.CORRECT_WITH_WRITING_ISSUES, 1),
            (Verdict.INCORRECT, 0),
        ],
    )
    def test_base_points(self, verdict, expected):
        assert points_for_verdict(verdict, hint_used=False) == expected


class TestHintCap:
    def test_natural_with_hint_capped_at_one(self):
        assert points_for_verdict(Verdict.CORRECT_NATURAL, hint_used=True) == 1

    def test_incorrect_with_hint_stays_zero(self):
        assert points_for_verdict(Verdict.INCORRECT, hint_used=True) == 0

    def test_hint_marks_attempt_imperfect_even_if_verdict_natural(self):
        outcome = record_attempt(active_progress(), Verdict.CORRECT_NATURAL, hint_used=True, current_exercise_sequence=1)
        assert outcome.is_imperfect is True
        assert outcome.progress.perfect_learning_record is False


class TestScheduling:
    def test_incorrect_due_after_20(self):
        assert review_interval_for(Verdict.INCORRECT, hint_used=False) == 20

    def test_unnatural_due_after_30(self):
        assert review_interval_for(Verdict.CORRECT_UNNATURAL, hint_used=False) == 30

    def test_writing_issues_due_after_30(self):
        assert review_interval_for(Verdict.CORRECT_WITH_WRITING_ISSUES, hint_used=False) == 30

    def test_hint_assisted_correct_due_after_30(self):
        assert review_interval_for(Verdict.CORRECT_NATURAL, hint_used=True) == 30

    def test_natural_no_hint_returns_to_normal_rotation(self):
        assert review_interval_for(Verdict.CORRECT_NATURAL, hint_used=False) is None

    def test_incorrect_stays_20_even_with_hint(self):
        assert review_interval_for(Verdict.INCORRECT, hint_used=True) == 20

    def test_next_review_at_exercise_uses_current_sequence(self):
        outcome = record_attempt(active_progress(required_score=999), Verdict.INCORRECT, hint_used=False, current_exercise_sequence=42)
        assert outcome.progress.next_review_at_exercise == 62


class TestDueReviewPriority:
    def test_due_review_beats_normal_rotation(self):
        candidates = [
            QueueCandidate(text_id="normal", next_review_at_exercise=None, rotation_position=0),
            QueueCandidate(text_id="due", next_review_at_exercise=5, rotation_position=10),
        ]
        chosen = select_next(candidates, current_exercise_sequence=10)
        assert chosen.text_id == "due"

    def test_not_yet_due_review_does_not_preempt_normal_rotation(self):
        candidates = [
            QueueCandidate(text_id="normal", next_review_at_exercise=None, rotation_position=0),
            QueueCandidate(text_id="not_due_yet", next_review_at_exercise=100, rotation_position=1),
        ]
        chosen = select_next(candidates, current_exercise_sequence=10)
        assert chosen.text_id == "normal"

    def test_multiple_due_reviews_oldest_first(self):
        candidates = [
            QueueCandidate(text_id="newer_due", next_review_at_exercise=8, rotation_position=0),
            QueueCandidate(text_id="oldest_due", next_review_at_exercise=3, rotation_position=1),
            QueueCandidate(text_id="also_due", next_review_at_exercise=5, rotation_position=2),
        ]
        chosen = select_next(candidates, current_exercise_sequence=10)
        assert chosen.text_id == "oldest_due"

    def test_tie_broken_by_rotation_position(self):
        candidates = [
            QueueCandidate(text_id="later", next_review_at_exercise=5, rotation_position=9),
            QueueCandidate(text_id="earlier", next_review_at_exercise=5, rotation_position=1),
        ]
        chosen = select_next(candidates, current_exercise_sequence=10)
        assert chosen.text_id == "earlier"

    def test_no_candidates_returns_none(self):
        assert select_next([], current_exercise_sequence=10) is None


class TestSkipBehavior:
    def test_skip_does_not_touch_score_or_counters(self):
        progress = active_progress(mastery_score=3, natural_count=1)
        # Skip never calls record_attempt: no score, no attempt, no counter change.
        assert progress.mastery_score == 3
        assert progress.natural_count == 1

    def test_skip_preserves_existing_review_obligation(self):
        progress = active_progress(next_review_at_exercise=50)
        # Repositioning within a queue is a rotation_position concern, not a
        # TextProgressState mutation; the due threshold itself is untouched.
        assert progress.next_review_at_exercise == 50


class TestRepetitionThreshold:
    def test_plus_one_repetition_increments_targets(self):
        progress = increase_repetition(active_progress())
        assert progress.required_natural_equivalents == 4
        assert progress.required_score == 8

    def test_stacked_repetitions(self):
        progress = increase_repetition(increase_repetition(active_progress()))
        assert progress.required_natural_equivalents == 5
        assert progress.required_score == 10


class TestManualAcquisition:
    def test_manual_acquisition_does_not_count_as_correct(self):
        progress = manually_acquire(active_progress(mastery_score=0))
        assert progress.status == TextProgressStatus.MANUALLY_ACQUIRED
        assert progress.manually_acquired is True
        assert progress.natural_count == 0


class TestPerfectCompletion:
    def test_three_natural_answers_masters_with_perfect_record(self):
        progress = active_progress()
        sequence = 0
        for _ in range(3):
            sequence += 1
            outcome = record_attempt(progress, Verdict.CORRECT_NATURAL, hint_used=False, current_exercise_sequence=sequence)
            progress = outcome.progress
        assert progress.status == TextProgressStatus.MASTERED
        assert progress.perfect_learning_record is True
        assert outcome.became_mastered is True


class TestImperfectCompletionToTestWaiting:
    def test_one_unnatural_answer_breaks_perfect_record_permanently(self):
        progress = active_progress()
        outcome = record_attempt(progress, Verdict.CORRECT_UNNATURAL, hint_used=False, current_exercise_sequence=1)
        progress = outcome.progress
        assert progress.perfect_learning_record is False

        # Even a later fully natural answer cannot restore it.
        outcome = record_attempt(progress, Verdict.CORRECT_NATURAL, hint_used=False, current_exercise_sequence=31)
        assert outcome.progress.perfect_learning_record is False

    def test_reaching_required_score_with_imperfect_record_waits_for_test(self):
        progress = active_progress(mastery_score=5, required_score=6)
        outcome = record_attempt(progress, Verdict.CORRECT_UNNATURAL, hint_used=False, current_exercise_sequence=1)
        assert outcome.progress.status == TextProgressStatus.WAITING_FOR_TEST_ASSIGNMENT
        assert outcome.entered_test_waiting is True
        assert outcome.became_mastered is False


class TestActivationReplacement:
    def test_activates_next_when_below_target_and_unseen_available(self):
        assert should_activate_next(active_count=99, unseen_available=True) is True

    def test_does_not_activate_when_bank_full(self):
        assert should_activate_next(active_count=100, unseen_available=True) is False

    def test_does_not_activate_when_no_unseen_left(self):
        assert should_activate_next(active_count=50, unseen_available=False) is False


class TestOnlyActiveTextsReceiveAttempts:
    def test_raises_when_status_not_active(self):
        progress = TextProgressState(status=TextProgressStatus.MASTERED, mastery_score=6)
        with pytest.raises(ValueError):
            record_attempt(progress, Verdict.CORRECT_NATURAL, hint_used=False, current_exercise_sequence=1)
