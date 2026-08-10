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

`CORRECT_NATURAL` requires:

-   meaning preserved;
-   no meaningful spoken grammar error;
-   formulation a native American English speaker could naturally use in
    context;
-   appropriate register;
-   no awkward literal French translation;
-   not unnecessarily formal;
-   contractions accepted/preferred when natural.

Do not downgrade an answer merely because another wording is preferred.

`CORRECT_UNNATURAL` is reserved for wording that is understandable and
substantially correct but genuinely stiff, literal, unusual, or unlikely
in normal American usage.

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
