import pytest

from app.modules.evaluations.enums import Verdict
from app.modules.learning.enums import TextProgressStatus
from app.modules.learning.engine import (
    QueueCandidate,
    TextProgressState,
    increase_repetition,
    is_imperfect,
    manually_acquire,
    points_for_verdict,
    prioritized_tiers,
    record_attempt,
    review_interval_for,
    select_next,
    should_activate_next,
    tier_weights,
)
from app.modules.texts.models import Difficulty


def active_progress(**overrides) -> TextProgressState:
    overrides.setdefault("mastery_score", 0)
    return TextProgressState(status=TextProgressStatus.ACTIVE, **overrides)


class TestVerdictPointMappings:
    @pytest.mark.parametrize(
        "verdict,expected",
        [
            (Verdict.CORRECT_NATURAL, 2),
            (Verdict.CORRECT_WITH_USAGE_NOTE, 2),
            (Verdict.CORRECT_UNNATURAL, 1),
            (Verdict.CORRECT_WITH_WRITING_ISSUES, 1),
            (Verdict.INCORRECT, 0),
        ],
    )
    def test_base_points(self, verdict, expected):
        assert points_for_verdict(verdict, hint_used=False) == expected


class TestUsageNoteScoresLikeNatural:
    """CORRECT_WITH_USAGE_NOTE is a full success (product decision): it must
    score, schedule, and count exactly like CORRECT_NATURAL everywhere."""

    def test_same_points_with_and_without_hint(self):
        for hint_used in (True, False):
            assert points_for_verdict(Verdict.CORRECT_WITH_USAGE_NOTE, hint_used) == points_for_verdict(
                Verdict.CORRECT_NATURAL, hint_used
            )

    def test_not_imperfect_without_hint(self):
        assert is_imperfect(Verdict.CORRECT_WITH_USAGE_NOTE, hint_used=False) is False

    def test_imperfect_with_hint_like_natural(self):
        assert is_imperfect(Verdict.CORRECT_WITH_USAGE_NOTE, hint_used=True) is is_imperfect(
            Verdict.CORRECT_NATURAL, hint_used=True
        )

    def test_same_review_interval_as_natural(self):
        for hint_used in (True, False):
            assert review_interval_for(Verdict.CORRECT_WITH_USAGE_NOTE, hint_used) == review_interval_for(
                Verdict.CORRECT_NATURAL, hint_used
            )

    def test_counts_toward_natural_count(self):
        outcome = record_attempt(
            active_progress(), Verdict.CORRECT_WITH_USAGE_NOTE, hint_used=False, current_exercise_sequence=1
        )
        assert outcome.progress.natural_count == 1

    def test_two_usage_note_answers_masters_with_perfect_record(self):
        progress = active_progress()
        sequence = 0
        for _ in range(2):
            sequence += 1
            outcome = record_attempt(
                progress, Verdict.CORRECT_WITH_USAGE_NOTE, hint_used=False, current_exercise_sequence=sequence
            )
            progress = outcome.progress
        assert progress.status == TextProgressStatus.MASTERED
        assert progress.perfect_learning_record is True


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


class TestReviewSpacing:
    def test_due_review_deferred_when_gap_not_yet_satisfied(self):
        candidates = [
            QueueCandidate(text_id="normal", next_review_at_exercise=None, rotation_position=0),
            QueueCandidate(text_id="due", next_review_at_exercise=5, rotation_position=10),
        ]
        # Last review was 3 exercises ago; the 10-exercise gap isn't met yet.
        chosen = select_next(candidates, current_exercise_sequence=10, last_review_at_exercise=7)
        assert chosen.text_id == "normal"

    def test_due_review_served_once_gap_is_satisfied(self):
        candidates = [
            QueueCandidate(text_id="normal", next_review_at_exercise=None, rotation_position=0),
            QueueCandidate(text_id="due", next_review_at_exercise=5, rotation_position=10),
        ]
        chosen = select_next(candidates, current_exercise_sequence=10, last_review_at_exercise=0)
        assert chosen.text_id == "due"

    def test_gap_boundary_is_inclusive(self):
        candidates = [
            QueueCandidate(text_id="normal", next_review_at_exercise=None, rotation_position=0),
            QueueCandidate(text_id="due", next_review_at_exercise=5, rotation_position=10),
        ]
        # Exactly MIN_EXERCISES_BETWEEN_REVIEWS (10) since the last review.
        chosen = select_next(candidates, current_exercise_sequence=10, last_review_at_exercise=0)
        assert chosen.text_id == "due"

    def test_gate_is_skipped_when_a_due_review_is_the_only_content(self):
        candidates = [QueueCandidate(text_id="due", next_review_at_exercise=5, rotation_position=10)]
        chosen = select_next(candidates, current_exercise_sequence=10, last_review_at_exercise=9)
        assert chosen.text_id == "due"

    def test_multiple_due_reviews_stay_deferred_together(self):
        candidates = [
            QueueCandidate(text_id="normal", next_review_at_exercise=None, rotation_position=0),
            QueueCandidate(text_id="due_a", next_review_at_exercise=1, rotation_position=1),
            QueueCandidate(text_id="due_b", next_review_at_exercise=2, rotation_position=2),
        ]
        chosen = select_next(candidates, current_exercise_sequence=10, last_review_at_exercise=8)
        assert chosen.text_id == "normal"

    def test_no_prior_review_does_not_block(self):
        candidates = [
            QueueCandidate(text_id="normal", next_review_at_exercise=None, rotation_position=0),
            QueueCandidate(text_id="due", next_review_at_exercise=5, rotation_position=10),
        ]
        chosen = select_next(candidates, current_exercise_sequence=10, last_review_at_exercise=None)
        assert chosen.text_id == "due"


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
        assert progress.required_natural_equivalents == 3
        assert progress.required_score == 6

    def test_stacked_repetitions(self):
        progress = increase_repetition(increase_repetition(active_progress()))
        assert progress.required_natural_equivalents == 4
        assert progress.required_score == 8


class TestManualAcquisition:
    def test_manual_acquisition_does_not_count_as_correct(self):
        progress = manually_acquire(active_progress(mastery_score=0))
        assert progress.status == TextProgressStatus.MANUALLY_ACQUIRED
        assert progress.manually_acquired is True
        assert progress.natural_count == 0


class TestPerfectCompletion:
    def test_two_natural_answers_masters_with_perfect_record(self):
        # Default required_score is 4 (2 natural-answer equivalents at +2 each).
        progress = active_progress()
        sequence = 0
        for _ in range(2):
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


class TestTierWeights:
    def test_two_distinct_tiers_with_default_share(self):
        weights = tier_weights(Difficulty.B2, Difficulty.C1)

        assert weights == {Difficulty.B2: 0.25, Difficulty.C1: 0.75}

    def test_custom_share_is_respected(self):
        weights = tier_weights(Difficulty.A1, Difficulty.B1, current_level_share=0.4)

        assert weights == {Difficulty.A1: 0.4, Difficulty.B1: 0.6}

    def test_collapses_to_a_single_tier_when_target_equals_current(self):
        weights = tier_weights(Difficulty.B2, Difficulty.B2, current_level_share=0.4)

        assert weights == {Difficulty.B2: 1.0}

    @pytest.mark.parametrize(
        "current,target",
        [(Difficulty.A1, Difficulty.A2), (Difficulty.B2, Difficulty.C2), (Difficulty.C2, Difficulty.C2)],
    )
    def test_weights_always_sum_to_one(self, current, target):
        assert sum(tier_weights(current, target).values()) == pytest.approx(1.0)


class TestPrioritizedTiers:
    def test_orders_by_weight_when_bank_is_empty(self):
        weights = {Difficulty.B2: 0.15, Difficulty.C1: 0.75, Difficulty.C2: 0.10}

        order = prioritized_tiers(weights, active_counts={})

        assert order == [Difficulty.C1, Difficulty.B2, Difficulty.C2]

    def test_prefers_the_tier_furthest_below_its_target_share(self):
        weights = {Difficulty.B2: 0.15, Difficulty.C1: 0.75, Difficulty.C2: 0.10}
        active_counts = {Difficulty.B2: 15, Difficulty.C1: 60, Difficulty.C2: 10}

        order = prioritized_tiers(weights, active_counts)

        assert order[0] == Difficulty.C1

    def test_a_single_collapsed_tier_returns_just_that_tier(self):
        order = prioritized_tiers({Difficulty.C2: 1.0}, active_counts={Difficulty.C2: 50})

        assert order == [Difficulty.C2]
