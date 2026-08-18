from app.modules.evaluations.enums import Verdict
from app.modules.tests.engine import (
    TestTextState,
    apply_test_response,
    group_into_tests,
    is_test_complete,
    start_attempt,
)


class TestExactTwentyFiveAssignment:
    def test_exactly_25_forms_one_group(self):
        ids = [f"t{i}" for i in range(25)]
        groups, remainder = group_into_tests(ids)
        assert len(groups) == 1
        assert len(groups[0]) == 25
        assert remainder == []

    def test_fewer_than_25_all_remain_waiting(self):
        ids = [f"t{i}" for i in range(24)]
        groups, remainder = group_into_tests(ids)
        assert groups == []
        assert len(remainder) == 24

    def test_60_forms_two_groups_with_10_remaining(self):
        ids = [f"t{i}" for i in range(60)]
        groups, remainder = group_into_tests(ids)
        assert len(groups) == 2
        assert all(len(g) == 25 for g in groups)
        assert len(remainder) == 10


class TestNoTextInMultipleTests:
    def test_groups_partition_input_without_duplicates(self):
        ids = [f"t{i}" for i in range(75)]
        groups, remainder = group_into_tests(ids)
        seen = [tid for group in groups for tid in group] + remainder
        assert sorted(seen) == sorted(ids)
        assert len(set(seen)) == len(ids)


class TestConsecutiveTestSuccesses:
    def test_two_consecutive_natural_masters_the_text(self):
        state = TestTextState()
        state = apply_test_response(state, Verdict.CORRECT_NATURAL)
        assert state.mastered is False
        assert state.consecutive_successes == 1
        state = apply_test_response(state, Verdict.CORRECT_NATURAL)
        assert state.mastered is True
        assert state.consecutive_successes == 2

    def test_only_correct_natural_counts_as_success(self):
        state = TestTextState()
        state = apply_test_response(state, Verdict.CORRECT_UNNATURAL)
        assert state.consecutive_successes == 0
        state = apply_test_response(state, Verdict.CORRECT_WITH_WRITING_ISSUES)
        assert state.consecutive_successes == 0

    def test_usage_note_counts_as_success_like_natural(self):
        state = TestTextState()
        state = apply_test_response(state, Verdict.CORRECT_WITH_USAGE_NOTE)
        assert state.consecutive_successes == 1
        state = apply_test_response(state, Verdict.CORRECT_WITH_USAGE_NOTE)
        assert state.mastered is True


class TestResetOnTestFailure:
    def test_incorrect_resets_consecutive_counter(self):
        state = TestTextState(consecutive_successes=1)
        state = apply_test_response(state, Verdict.INCORRECT)
        assert state.consecutive_successes == 0
        assert state.mastered is False

    def test_unnatural_after_one_success_resets_too(self):
        state = TestTextState(consecutive_successes=1)
        state = apply_test_response(state, Verdict.CORRECT_UNNATURAL)
        assert state.consecutive_successes == 0

    def test_mastered_text_ignores_further_responses(self):
        state = TestTextState(consecutive_successes=2, mastered=True)
        state = apply_test_response(state, Verdict.INCORRECT)
        assert state.mastered is True
        assert state.consecutive_successes == 2


class TestCompletion:
    def test_complete_only_when_all_25_mastered(self):
        mastered = [TestTextState(consecutive_successes=2, mastered=True) for _ in range(24)]
        pending = TestTextState(consecutive_successes=1, mastered=False)
        assert is_test_complete(mastered + [pending]) is False
        assert is_test_complete(mastered + [TestTextState(consecutive_successes=2, mastered=True)]) is True


class TestRetakeImmutability:
    def test_first_attempt_is_not_a_retake(self):
        attempt = start_attempt(previous_attempt_number=None)
        assert attempt.attempt_number == 1
        assert attempt.is_retake is False

    def test_second_attempt_is_a_retake_with_incremented_number(self):
        attempt = start_attempt(previous_attempt_number=1)
        assert attempt.attempt_number == 2
        assert attempt.is_retake is True

    def test_retake_does_not_require_or_mutate_the_original_text_group(self):
        ids = [f"t{i}" for i in range(25)]
        groups, _ = group_into_tests(ids)
        original = list(groups[0])
        start_attempt(previous_attempt_number=1)
        assert groups[0] == original
