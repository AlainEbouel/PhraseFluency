# Learning Engine Specification

## Purpose

The Learning Engine owns all deterministic pedagogical rules. It must
not depend on React or on a specific LLM provider.

## Core values

Default:

-   `required_natural_equivalents = 2`
-   `required_score = 4`
-   natural = +2
-   imperfect correct = +1
-   incorrect = +0

`+1 repetition` increments:

-   natural-equivalent target by 1;
-   score target by 2.

## Attempt classification

`CORRECT_NATURAL` - +2 unless a hint was used, then +1. - normal
rotation.

`CORRECT_UNNATURAL` - +1. - imperfect learning record. - due after 30
submitted exercises.

`CORRECT_WITH_WRITING_ISSUES` - +1. - imperfect learning record. - due
using the imperfect-success interval.

`INCORRECT` - +0. - imperfect learning record. - due after 20 submitted
exercises.

Hint used: - marks learning record imperfect; - caps otherwise-correct
result at +1.

## Queue model

Each user has:

-   normal active rotation;
-   due review queue;
-   current exercise sequence;
-   exercise sequence at which a review was last served.

Selection priority:

1.  oldest due review, but only if at least `min_review_gap` (10)
    exercises have passed since the last review was served — reviews
    are injected one at a time rather than all at once when several
    fall due together; a deferred review stays due and is reconsidered
    on the next call. This gap is skipped only when a due review is
    the sole content left to serve (nothing normal to fall back to).
2.  next normal rotation item.

Every successfully evaluated/submitted exercise increments the global
exercise sequence.

Skip: - no score; - no attempt; - move current item to end of its
applicable queue; - preserve any existing review obligation.

## Completion of initial learning

When mastery score reaches required score:

-   if `perfect_learning_record == true`: transition to `MASTERED`;
-   otherwise: transition to `WAITING_FOR_TEST_ASSIGNMENT`.

If a reserve text exists, activate the next unseen text so the active
bank remains at 100 where possible. Selection is difficulty-weighted
around the user's chosen level (see "Level selection and the weighted
active bank" below).

Manual acquisition: - transition out of active learning; - record
`manually_acquired = true`; - do not count as correct; - replace with
next unseen text (same difficulty-weighted selection).

## Level selection and the weighted active bank

On first use, a user chooses their current CEFR level (A1-C2). Nothing
activates into their bank before this choice is made — `GET
/api/v1/learning/next` signals that a level is required instead of
serving an exercise or the empty-bank message.

Once chosen, the 100-text active bank is composed around three tiers
relative to that level:

-   15% at the chosen level itself;
-   75% at the next level up (the aspirational target);
-   10% two levels up.

Levels past C2 clamp to C2; if two tiers clamp to the same level their
shares merge (e.g. a C1 choice yields 15% C1 / 85% C2; a C2 choice
yields 100% C2).

As texts leave the active bank (mastered, disabled, manually acquired),
each replacement is chosen to reduce whichever tier is furthest below
its target share of the current bank size, not on a fixed schedule -
this keeps the composition self-correcting rather than drifting.

If a tier has no unseen text left, the next most-deficient tier is
tried instead. If all three weighted tiers are exhausted, selection
falls back to the oldest unseen text in the whole corpus, regardless of
difficulty, exactly as it did before this feature existed.

Choosing a level is currently a one-time action (no self-service
"change my level" flow yet); already-active texts are never
retroactively reshuffled when a level is chosen or the bank tops up.

## Test assignment

Eligible waiting texts are grouped in sets of exactly 25.

For each group:

-   create one immutable Test;
-   assign 25 unique texts;
-   a user/text pair may belong to only one Test;
-   remaining count \<25 stays waiting.

## Test mastery

For the initial test mastery process:

-   each text tracks `consecutive_test_successes`;
-   correct -\> increment;
-   incorrect -\> reset to 0;
-   reaching 2 -\> text mastered within Test.

A Test is complete when all 25 texts satisfy the test mastery condition.

## Retakes

A completed Test can be retaken.

-   create a new TestAttempt;
-   use the same immutable 25 texts;
-   present all 25;
-   preserve previous attempts;
-   retake results measure retention and do not reactivate main learning
    state.

## Required automated tests

At minimum test:

-   all verdict point mappings;
-   hint cap;
-   +20 scheduling;
-   +30 scheduling;
-   due-review priority;
-   multiple due reviews oldest-first;
-   due reviews deferred until the minimum gap since the last one served;
-   the gap is skipped when a due review is the only content left;
-   reviews increment exercise sequence;
-   skip behavior;
-   +1 repetition threshold;
-   manual acquisition;
-   perfect completion;
-   imperfect completion to test waiting;
-   activation replacement;
-   exact 25 test assignment;
-   no text in multiple tests;
-   consecutive test successes;
-   reset on test failure;
-   retake immutability;
-   idempotent submission behavior.
