# LLM Integration

## V1 principle

OpenAI is the only linguistic engine in V1.

It is hidden behind an `EvaluationEngine` abstraction so a future hybrid
engine can be added without rewriting the Learning Engine.

## Responsibilities

The LLM may:

-   generate linguistic references;
-   evaluate answers;
-   re-evaluate contested answers;
-   generate optional grammar explanations;
-   identify reusable patterns;
-   answer contextual chat questions;
-   optionally provide STT/TTS through configured providers.

The LLM does not own deterministic progression rules.

## Reference generation

Input:

-   French Text/version;
-   exercise context;
-   target language rules.

Output schema should include:

-   preferred_translation;
-   up to 2 common alternatives;
-   grammar concepts;
-   contexts/skills;
-   progressive hints;
-   useful patterns;
-   optional explanation data.

Target:

-   natural American English;
-   conversational/professional usage;
-   contractions when natural;
-   avoid British-targeted recommendations;
-   preserve full context.

Persist and reuse references.

Store:

-   model;
-   prompt_version;
-   generated_at.

## Evaluation

Input:

-   French source/context;
-   user's English answer;
-   preferred translation;
-   alternatives;
-   evaluation rules;
-   hint-used flag.

Expected structured fields:

-   verdict;
-   meaning_preserved;
-   grammar_correct;
-   natural_american_english;
-   writing_issues\[\];
-   corrected_answer;
-   concise feedback;
-   error_categories\[\].

The backend maps verdicts to points.

## Naturalness standard

The governing question for `CORRECT_NATURAL` vs. `CORRECT_UNNATURAL` is
acceptability, not optimality: not "is this the single most natural way
to say it?" but "is this a normally acceptable way to say it in
American English in this context, without notable oddness or
problematic ambiguity?" The burden of proof is on `CORRECT_UNNATURAL`;
when genuinely unsure, choose `CORRECT_NATURAL`.

`CORRECT_NATURAL` requires:

-   meaning preserved;
-   no meaningful spoken grammar error;
-   formulation a native American English speaker could normally,
    acceptably use in context;
-   no awkward literal French translation;
-   contractions accepted/preferred when natural.

This is the default verdict. A wording being less frequent, more
formal/informal, or simply not the reference/preferred translation is
never on its own a reason to downgrade (e.g. "check" vs. "verify",
"start" vs. "begin", "I think" vs. "I believe" are all
`CORRECT_NATURAL`). The same applies across regional varieties: a
formulation characteristic of British (or other) English that is
widely understood and normally used in American contexts, with no
resulting ambiguity, is still `CORRECT_NATURAL` — at most an
informative aside in feedback ("Correct. More typical of British
English; in American English, 'X' is more common."), never a
deduction.

`CORRECT_UNNATURAL` is reserved for wording that is grammatically
acceptable and understandable but has a genuine, nameable usage
problem in this specific context — not merely a less frequent or less
preferred choice:

-   a substantially mismatched/inappropriate register for the
    situation; or
-   genuine oddness to a native ear in this specific situation, beyond
    being merely less common; or
-   a real risk that a listener would understand something importantly
    different from what the learner intended (e.g. "I'll investigate
    it" for an intended "I'll check" — "investigate" implies looking
    into a problem/incident, which the context doesn't support).

"A more common word/phrasing exists" is never sufficient justification
by itself for `CORRECT_UNNATURAL`.

This leniency is about *how* something is phrased (register, frequency,
dialect) when the underlying meaning is unchanged — never a license to
excuse a word choice that changes what is actually being described. If
the learner's specific word would make a native listener believe
something different happened, was requested, or was meant than what the
source implies, that is a meaning problem (`INCORRECT`), not a
naturalness problem, no matter how fluent and grammatical the sentence
otherwise reads. This is common with French-English false friends —
"assist" for "attend" (assister à), "actually" for "currently"
(actuellement), "spare" for "save up" (économiser) — or a swapped
near-opposite like "forgot bringing" instead of "forgot to bring"
(reverses whether the item was brought at all). A sentence can be
perfectly well-formed and still `INCORRECT` if it says the wrong thing
(added after the first linguistic-benchmark run, `evaluation-v4`, found
the model under-using `INCORRECT` for exactly this pattern — see
docs/linguistic-benchmark.md).

## Writing-only standard

Errors that would not appear as spoken-language errors may produce
`CORRECT_WITH_WRITING_ISSUES`.

Example:

`i dont think hes coming`

The corrected writing must be shown.

## Re-evaluation

A re-evaluation:

-   creates a new Evaluation;
-   receives previous verdict/context;
-   reassesses independently;
-   explicitly checks whether the answer was merely different rather
    than unnatural;
-   may become the active evaluation.

Never erase the previous evaluation.

## Contextual chat

Chat context may include:

-   current Text;
-   user answer;
-   active evaluation;
-   reference formulations;
-   relevant previous messages.

Do not include user identity information.

Chat does not automatically modify accepted references or progress.

## Grammar explanations

Detailed explanations are generated only when requested or pre-generated
intentionally.

They are hidden by default in UX and cached for reuse.

## Prompt versioning

Version independently where useful:

-   reference prompt;
-   evaluation prompt;
-   re-evaluation prompt;
-   chat/explanation prompt.

Persist prompt version with outputs.

## Determinism

All structured-output calls use `temperature=0` (`OpenAIEvaluationEngine._parse`).
Without it, the linguistic benchmark showed real run-to-run verdict flips on
identical boundary-case inputs — the same learner answer re-evaluated could
get a different verdict purely from sampling noise, not reconsideration.
`temperature=0` is not a full determinism guarantee (the OpenAI API can still
vary slightly at the infrastructure level) but sharply reduces it in
practice.

## Caching

Persist global reusable linguistic references.

Exact normalized duplicate answers may reuse evaluation results only
when the product rules explicitly allow it. Avoid home-grown semantic
similarity caching.

Provider prompt caching may be used where available.

## Failure behavior

On timeout, invalid structured output, provider failure, or unavailable
evaluation:

-   do not award points;
-   do not advance queue;
-   do not validate attempt;
-   preserve draft;
-   show Retry.

## AI usage

Record operation/model/token/cost metadata for future economics and
operational analysis.
