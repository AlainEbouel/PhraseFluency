# Functional Data Model

This is a conceptual model; exact SQL design may evolve without changing
domain semantics.

## User

-   id
-   email
-   password_hash
-   role: USER \| ADMIN
-   created_at
-   last_login_at
-   preferences

## Text

Global/shared content.

-   id
-   current_version_id
-   source
-   enabled
-   created_at

## TextVersion

-   id
-   text_id
-   french_text
-   exercise_type: TRANSLATION \| SITUATIONAL
-   difficulty: A1 \| A2 \| B1 \| B2 \| C1 \| C2
-   contexts\[\]
-   grammar_concepts\[\]
-   skills\[\]
-   created_at

Historical attempts reference the exact version seen.

## LinguisticReference

Shared/global per TextVersion.

-   text_version_id
-   preferred_translation
-   alternatives\[\]
-   hints\[\]
-   grammar_explanation
-   patterns\[\]
-   model
-   prompt_version
-   generated_at

## Pattern

-   id
-   expression
-   meaning
-   example
-   related_text_versions\[\]

## UserTextProgress

-   user_id
-   text_id
-   status
-   mastery_score
-   required_score
-   required_natural_equivalents
-   times_presented
-   natural_count
-   unnatural_count
-   writing_issue_count
-   incorrect_count
-   hint_count
-   manually_acquired
-   perfect_learning_record
-   first_seen_at
-   last_seen_at
-   next_review_at_exercise

Possible statuses:

-   UNSEEN
-   ACTIVE
-   WAITING_FOR_TEST_ASSIGNMENT
-   TEST_ASSIGNED
-   MASTERED
-   MANUALLY_ACQUIRED
-   DISABLED

`DISABLED` is admin-only and permanent: an admin can hide a specific text
from one user's bank (from any status, including one they've never seen),
and the active bank automatically backfills the slot from the general pool
if the text was `ACTIVE`. There is no undo, matching `MANUALLY_ACQUIRED`.

## UserLearningState

-   user_id
-   exercise_sequence
-   normal_rotation_position/current queue state
-   current_text_id
-   current_draft
-   current_hint_level
-   current_level: A1 \| A2 \| B1 \| B2 \| C1 \| C2 \| null (chosen once,
    at onboarding; null blocks all activation until set)
-   last_review_at_exercise: exercise sequence value at which a due
    review was last served (null if none yet); gates how soon the next
    one can be injected

## Attempt

-   id
-   user_id
-   text_version_id
-   mode: LEARNING \| TEST \| RETAKE
-   sequence_number
-   user_answer
-   input_method: KEYBOARD \| VOICE
-   hint_used
-   max_hint_level
-   active_evaluation_id
-   created_at
-   submission_id (idempotency)

## Evaluation

-   id
-   attempt_id
-   evaluation_number
-   verdict
-   meaning_preserved
-   grammar_correct
-   natural_american_english
-   writing_issues\[\]
-   corrected_answer
-   feedback
-   error_categories\[\]
-   model
-   prompt_version
-   created_at

## Test

Immutable set of 25 texts.

-   id
-   user_id
-   number
-   created_at

## TestText

-   test_id
-   text_id
-   position
-   consecutive_successes
-   mastered_at

Constraint: `(user_id, text_id)` can belong to only one Test.

## TestAttempt

-   id
-   test_id
-   attempt_number
-   status
-   started_at
-   completed_at
-   latest_position
-   aggregate result counts

## TextConversation

-   id
-   user_id
-   text_id
-   created_at
-   updated_at

## ConversationMessage

-   id
-   conversation_id
-   role
-   content
-   model
-   created_at

## ImportBatch

-   id
-   filename
-   imported_by
-   imported_at
-   total_rows
-   imported_count
-   duplicate_count
-   rejected_count

## AudioAsset

-   id
-   content_hash
-   english_text
-   language = en-US
-   voice
-   provider
-   storage_key
-   generated_at

## AIUsage

-   id
-   user_id nullable where appropriate
-   operation
-   model
-   input_tokens
-   output_tokens
-   estimated_cost
-   created_at

Operations include:

-   REFERENCE_GENERATION
-   EVALUATION
-   REEVALUATION
-   CHAT
-   GRAMMAR_EXPLANATION
-   STT
-   TTS

## FeatureFlag

Simple future-ready feature controls.

-   key
-   enabled
-   optional scope/config
