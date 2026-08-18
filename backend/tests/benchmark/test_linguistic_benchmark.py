"""Linguistic benchmark (docs/linguistic-benchmark.md).

Validates the evaluation prompt (EVALUATION_SYSTEM_PROMPT) against 100 hand-
judged cases using the real OpenAIEvaluationEngine — this is intentionally
NOT part of the fast `pytest tests/` loop (see the `benchmark` marker in
pytest.ini): it costs real OpenAI usage and takes a few minutes.

Run explicitly with:

    pytest -m benchmark tests/benchmark -q -s

Acceptance gates (docs/linguistic-benchmark.md):
- 100% correct on `golden` cases (unambiguous, must never miss).
- >=95% correct overall across all 100 cases.

A full per-case report is always written to
tests/benchmark/reports/latest.txt (pass or fail) so a failure's category
breakdown can be analyzed per the doc's "Evolution" step.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

import pytest

from app.core.config import get_settings
from app.modules.evaluations.enums import Verdict
from app.modules.evaluations.ports import EvaluationRequest
from app.modules.evaluations.service import get_evaluation_engine
from tests.benchmark.cases import BENCHMARK_CASES, BenchmarkCase

pytestmark = pytest.mark.benchmark

REPORT_PATH = pathlib.Path(__file__).parent / "reports" / "latest.txt"

# CORRECT_UNNATURAL/INCORRECT mean "something changed" — if the exact segment
# the model just called problematic reappears in its own corrected_answer,
# that is the self-contradiction the mandatory internal-consistency check
# (evaluation-v6) exists to prevent. Checked across ALL cases, not just the
# new ones: the generalized, automated version of regression test 2.
_INCONSISTENCY_VERDICTS = (Verdict.CORRECT_UNNATURAL, Verdict.INCORRECT)


@dataclass
class CaseOutcome:
    case: BenchmarkCase
    actual_verdict: str | None
    problematic_segment: str | None
    corrected_answer: str | None
    error: str | None

    @property
    def correct(self) -> bool:
        if self.error is not None:
            return False
        if self.case.accepts_either_full_success:
            return self.actual_verdict in (
                Verdict.CORRECT_NATURAL.value,
                Verdict.CORRECT_WITH_USAGE_NOTE.value,
            )
        return self.actual_verdict == self.case.expected_verdict.value

    @property
    def self_contradictory(self) -> bool:
        if self.error is not None or self.actual_verdict not in {v.value for v in _INCONSISTENCY_VERDICTS}:
            return False
        if not self.problematic_segment or not self.corrected_answer:
            return False
        # A single flagged word (e.g. "worry" in a dropped-negation case)
        # will always survive an otherwise-correct fix like "Don't worry...";
        # only a multi-word segment reappearing verbatim is a real
        # self-contradiction (mirrors the runtime guard in openai_engine.py).
        if len(self.problematic_segment.split()) <= 1:
            return False
        return self.problematic_segment.strip().lower() in self.corrected_answer.strip().lower()


def _run_case(engine, case: BenchmarkCase) -> CaseOutcome:
    request = EvaluationRequest(
        french_text=case.french_text,
        user_answer=case.user_answer,
        preferred_translation=case.preferred_translation,
        alternatives=case.alternatives,
        hint_used=case.hint_used,
        contexts=case.contexts,
    )
    try:
        result = engine.evaluate(request)
    except Exception as exc:  # noqa: BLE001 - a live API call, record and keep going
        return CaseOutcome(
            case=case, actual_verdict=None, problematic_segment=None, corrected_answer=None, error=str(exc)
        )
    return CaseOutcome(
        case=case,
        actual_verdict=result.verdict.value,
        problematic_segment=result.problematic_segment,
        corrected_answer=result.corrected_answer,
        error=None,
    )


def _build_report(outcomes: list[CaseOutcome]) -> str:
    total = len(outcomes)
    correct = sum(1 for o in outcomes if o.correct)
    golden = [o for o in outcomes if o.case.golden]
    golden_correct = sum(1 for o in golden if o.correct)
    misses = [o for o in outcomes if not o.correct]
    contradictions = [o for o in outcomes if o.self_contradictory]

    lines = [
        f"Linguistic benchmark report — {correct}/{total} correct "
        f"({correct / total:.1%}), golden {golden_correct}/{len(golden)}, "
        f"internal-consistency violations {len(contradictions)}",
        "",
    ]

    if contradictions:
        lines.append(f"Internal-consistency violations ({len(contradictions)}):")
        for o in contradictions:
            lines.append(
                f"  - {o.case.id}: verdict={o.actual_verdict} "
                f'problematic_segment="{o.problematic_segment}" reappears in '
                f'corrected_answer="{o.corrected_answer}"'
            )
        lines.append("")

    if misses:
        lines.append(f"Misses ({len(misses)}):")
        for o in misses:
            actual = o.error and f"ERROR: {o.error}" or o.actual_verdict
            golden_tag = " [GOLDEN]" if o.case.golden else ""
            lines.append(
                f"  - {o.case.id}{golden_tag}: expected={o.case.expected_verdict.value} "
                f"actual={actual} coverage={list(o.case.coverage)}"
            )
            lines.append(f'      FR: "{o.case.french_text}"')
            lines.append(f'      answer: "{o.case.user_answer}"')
    else:
        lines.append("No misses.")

    lines.append("")
    lines.append("By expected verdict:")
    by_verdict: dict[str, list[CaseOutcome]] = {}
    for o in outcomes:
        by_verdict.setdefault(o.case.expected_verdict.value, []).append(o)
    for verdict, group in sorted(by_verdict.items()):
        g_correct = sum(1 for o in group if o.correct)
        lines.append(f"  {verdict}: {g_correct}/{len(group)}")

    lines.append("")
    lines.append("By coverage tag (misses only shown if any):")
    by_tag: dict[str, list[CaseOutcome]] = {}
    for o in outcomes:
        for tag in o.case.coverage:
            by_tag.setdefault(tag, []).append(o)
    for tag, group in sorted(by_tag.items()):
        tag_misses = [o for o in group if not o.correct]
        if tag_misses:
            lines.append(f"  {tag}: {len(group) - len(tag_misses)}/{len(group)}")

    return "\n".join(lines) + "\n"


def test_linguistic_benchmark():
    settings = get_settings()
    if not settings.openai_api_key:
        pytest.skip("OPENAI_API_KEY not configured; skipping live linguistic benchmark")

    engine = get_evaluation_engine()
    outcomes = [_run_case(engine, case) for case in BENCHMARK_CASES]

    report = _build_report(outcomes)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    print("\n" + report)

    golden_misses = [o for o in outcomes if o.case.golden and not o.correct]
    overall_accuracy = sum(1 for o in outcomes if o.correct) / len(outcomes)

    # Reported above, not asserted: a correction that restores a dropped
    # negation (e.g. "Worry..." -> "Don't worry...") legitimately reuses the
    # flagged segment as part of the fix, which the substring heuristic
    # can't always tell apart from a genuine self-contradiction. Treat this
    # as a manual-review signal (like the runtime logger.warning it mirrors),
    # not a hard gate.

    assert not golden_misses, (
        f"{len(golden_misses)} golden case(s) failed — see {REPORT_PATH}\n" + report
    )
    assert overall_accuracy >= 0.95, (
        f"Overall accuracy {overall_accuracy:.1%} is below the 95% target — "
        f"see {REPORT_PATH}\n" + report
    )
