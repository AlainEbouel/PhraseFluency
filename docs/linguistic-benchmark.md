# Linguistic Benchmark

## Purpose

Validate the LLM/prompt against PhraseFluency's exact pedagogical
classifications.

## Initial benchmark

100 curated cases.

Suggested distribution:

-   25 clearly `CORRECT_NATURAL`
-   20 `CORRECT_UNNATURAL`
-   15 `CORRECT_WITH_WRITING_ISSUES`
-   25 `INCORRECT`
-   15 difficult/ambiguous edge cases

Include 20 critical "golden" cases.

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

The benchmark is an automated backend test suite and must run when the
evaluation prompt/model changes.
