# Learning Engine Specification

## Purpose

The Learning Engine owns all deterministic pedagogical rules. It must
not depend on React or on a specific LLM provider.

## Core values

Default:

-   `required_natural_equivalents = 3`
-   `required_score = 6`
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
-   current exercise sequence.

Selection priority:

1.  oldest due review;
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
bank remains at 100 where possible.

Manual acquisition: - transition out of active learning; - record
`manually_acquired = true`; - do not count as correct; - replace with
next unseen text.

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
