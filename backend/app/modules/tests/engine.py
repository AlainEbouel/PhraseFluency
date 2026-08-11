"""Deterministic test-bank rules (docs/learning-engine.md, section: Tests).

Pure Python: no FastAPI, SQLAlchemy, or LLM-provider imports.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.modules.evaluations.enums import Verdict

TEST_SIZE = 25
CONSECUTIVE_SUCCESSES_TO_MASTER = 2


def group_into_tests(eligible_text_ids: list[str]) -> tuple[list[list[str]], list[str]]:
    """Split eligible waiting texts into complete groups of TEST_SIZE.

    Input order is preserved (callers pass texts ordered oldest-eligible
    first). Returns (full_groups, remainder) where remainder stays
    waiting until it can form a full group.
    """
    full_group_count = len(eligible_text_ids) // TEST_SIZE
    groups = [
        eligible_text_ids[i * TEST_SIZE : (i + 1) * TEST_SIZE]
        for i in range(full_group_count)
    ]
    remainder = eligible_text_ids[full_group_count * TEST_SIZE :]
    return groups, remainder


def counts_as_test_success(verdict: Verdict) -> bool:
    """Only a fully natural answer advances test mastery (product decision).

    CORRECT_UNNATURAL and CORRECT_WITH_WRITING_ISSUES are "correct" for
    learning-engine scoring but do not count here.
    """
    return verdict == Verdict.CORRECT_NATURAL


@dataclass(frozen=True)
class TestTextState:
    __test__ = False  # not a pytest test case despite the name prefix

    consecutive_successes: int = 0
    mastered: bool = False


def apply_test_response(state: TestTextState, verdict: Verdict) -> TestTextState:
    if state.mastered:
        return state
    successes = (
        state.consecutive_successes + 1 if counts_as_test_success(verdict) else 0
    )
    return replace(
        state,
        consecutive_successes=successes,
        mastered=successes >= CONSECUTIVE_SUCCESSES_TO_MASTER,
    )


def is_test_complete(states: list[TestTextState]) -> bool:
    return all(s.mastered for s in states)


@dataclass(frozen=True)
class TestAttemptState:
    __test__ = False  # not a pytest test case despite the name prefix

    attempt_number: int
    is_retake: bool


def start_attempt(previous_attempt_number: int | None) -> TestAttemptState:
    if previous_attempt_number is None:
        return TestAttemptState(attempt_number=1, is_retake=False)
    return TestAttemptState(attempt_number=previous_attempt_number + 1, is_retake=True)
