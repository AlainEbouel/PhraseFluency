# Linguistic Benchmark

## Purpose

Validate the LLM/prompt against PhraseFluency's exact pedagogical
classifications.

## Initial benchmark

100+ curated cases (104 as of evaluation-v6, after adding the
`CORRECT_WITH_USAGE_NOTE` category below).

Suggested distribution:

-   25 clearly `CORRECT_NATURAL`
-   4 clearly `CORRECT_WITH_USAGE_NOTE` (added in evaluation-v6 — see below)
-   20 `CORRECT_UNNATURAL`
-   15 `CORRECT_WITH_WRITING_ISSUES`
-   25 `INCORRECT`
-   15 difficult/ambiguous edge cases

Include 20+ critical "golden" cases.

### CORRECT_WITH_USAGE_NOTE (evaluation-v6)

A 5th verdict category, added to stop the evaluator from downgrading an
acceptable, understandable answer to `CORRECT_UNNATURAL` just because
another formulation is more frequent or idiomatic. It scores and
progresses identically to `CORRECT_NATURAL` (a full success) but carries
an optional, non-judgmental usage tip.

Because `CORRECT_NATURAL` and `CORRECT_WITH_USAGE_NOTE` are both a full
success, benchmark cases that only assert "this must not be penalized"
(rather than testing the label itself) set
`accepts_either_full_success=True` on the `BenchmarkCase` — either verdict
counts as correct, so the suite doesn't flake between the two whenever the
model's tie-break lands on one or the other. Cases that specifically test
the new category's labeling (e.g. the canonical "accepted to change" vs.
"agreed to change" case) keep the exact expected verdict.

The benchmark also runs a cross-cutting internal-consistency check across
every case (not just the new ones): if `problematic_segment` reappears
inside `corrected_answer` for a `CORRECT_UNNATURAL`/`INCORRECT` verdict,
that is a self-contradiction (the model calling a phrase a problem, then
reusing it unchanged in its own correction) and fails the benchmark run.

## Coverage

Benchmark must cover:

-   natural alternatives different from reference;
-   contractions;
-   American usage;
-   writing-only apostrophe/capitalization issues;
-   tense changes that alter meaning;
-   will/would;
-   present perfect vs simple past;
-   conditionals;
-   modals;
-   prepositions;
-   articles;
-   word order;
-   phrasal verbs;
-   false friends;
-   professional register;
-   informal but valid formulations;
-   question tags;
-   negative/interrogative forms;
-   multi-sentence context;
-   literal French translations;
-   meaning almost preserved but materially changed.

## Acceptance target

Initial target:

-   =95% correct verdicts overall;

-   100% on critical golden cases.

A natural answer incorrectly rejected as `INCORRECT` is more severe than
a natural/unnatural boundary disagreement.

## Evolution

Start with clear rules and limited examples.

If failures are systematic:

1.  analyze failure category;
2.  add or refine prompt rules;
3.  add targeted few-shot benchmark examples where useful;
4.  increment prompt version;
5.  rerun full benchmark;
6.  reject changes that introduce unacceptable regressions.

The benchmark is an automated backend test suite
(`backend/tests/benchmark/`) and must run when the evaluation prompt/model
changes:

    pytest -m benchmark tests/benchmark -q -s

It is excluded from the normal `pytest`/`pytest tests/` run (see the
`benchmark` marker and `addopts` in `backend/pytest.ini`) since it calls the
real OpenAI API — it costs money and takes a few minutes. Every run writes a
full per-case report to `backend/tests/benchmark/reports/latest.txt`
regardless of pass/fail, for the failure-category analysis in step 1 above.
Cases and their expected verdicts live in `backend/tests/benchmark/cases.py`.
