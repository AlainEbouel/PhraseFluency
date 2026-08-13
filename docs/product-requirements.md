# Product Requirements

## 1. Product vision

PhraseFluency helps users acquire natural American English by repeatedly
producing useful English formulations from contextual prompts. The
primary objective is fluency and automatic production, not explicit
grammar study.

The learning philosophy is:

-   practice first;
-   exposure to natural formulations;
-   repeated production;
-   reuse of useful language chunks in different contexts;
-   audio reinforcement;
-   grammar/explanations available on demand;
-   gradual movement from French-to-English translation toward
    situation-to-English production.

The initial user is the creator of the application. The product must
nevertheless be multi-user from V1 so it can later be shared and
potentially commercialized without rebuilding its foundations.

## 2. Accounts

V1 authentication:

-   email + password;
-   secure password hashing;
-   login/logout;
-   USER and ADMIN roles;
-   no password reset email in initial V1;
-   architecture must allow password recovery/email verification later.

All progress, attempts, tests, chats, drafts, statistics, and
preferences are isolated per user.

## 3. Content

The learning unit is called a **Text**.

A Text can contain:

-   one French sentence when sufficient context exists;
-   multiple French sentences when context is required.

Future exercise types:

-   `TRANSLATION`: French text -\> English production;
-   `SITUATIONAL`: situation/intention -\> English production.

V1 begins primarily with `TRANSLATION`, while the model must support
`SITUATIONAL`.

## 4. Active learning bank

-   Each user has up to 100 active texts.
-   Texts are presented fairly through a normal rotation queue.
-   Learning concepts/topics are mixed rather than taught in sequential
    grammar units.
-   On first use, a user chooses their current CEFR level (A1-C2);
    nothing activates into their bank before this choice is made.
-   The active bank is composed with a fixed ratio around that choice:
    15% at the chosen level, 75% at the next level up, 10% two levels
    up (clamped/merged at the C2 ceiling); see docs/learning-engine.md.
-   When an active text is acquired, it is replaced keeping that same
    ratio, falling back to any remaining unseen content once the
    weighted tiers are exhausted.
-   Imported texts begin as `UNSEEN`.

## 5. Response workflow

For each exercise:

1.  Display the French text.
2.  User types or dictates an English answer.
3.  Speech transcription is inserted into an editable text field.
4.  Transcription is never submitted automatically.
5.  User may request progressive hints.
6.  User submits.
7.  Backend requests LLM evaluation.
8.  If evaluation fails, no learning state changes and the user cannot
    advance.
9.  On success, evaluation and progress are persisted atomically.
10. Show feedback, recommended formulation, up to two common
    alternatives, audio, useful patterns, optional grammar explanation,
    contextual chat, and re-evaluation.
11. User explicitly selects Next.

## 6. Evaluation verdicts

-   `CORRECT_NATURAL`
-   `CORRECT_UNNATURAL`
-   `CORRECT_WITH_WRITING_ISSUES`
-   `INCORRECT`

Base points:

-   natural: 2;
-   unnatural: 1;
-   writing issues only: 1;
-   incorrect: 0.

If any hint was used during the attempt, the maximum award is 1 point.

Writing-only issues include mistakes that do not represent an error in
spoken production, such as missing apostrophes or capitalization.
Example:

`i dont think hes coming`

is treated as `CORRECT_WITH_WRITING_ISSUES`, not fully natural/correct.
The correctly written form must be shown.

## 7. Mastery

Default learning requirement:

-   2 natural-answer equivalents;
-   represented internally as 4 mastery points.

A natural answer contributes 2 points; a correct but
unnatural/writing-issue/help-assisted answer contributes 1 point.

The user may increase the required mastery for a specific text using
`+1 repetition`.

Example:

-   default: 2 natural equivalents / 4 points;
-   +1: 3 equivalents / 6 points;
-   +2: 4 equivalents / 8 points.

The UI must visibly show progress such as `1/2`, with a presentation
capable of representing half-progress when needed.

The user can mark any text as acquired immediately. Manual acquisition
is recorded separately and never counted as a successful answer.

## 8. Scheduling

-   Incorrect answer: text becomes due again after 20 submitted
    exercises.
-   Correct but unnatural: due after 30 submitted exercises.
-   Correct with writing issues: treat as a one-point imperfect success
    and schedule using the imperfect-success rule.
-   Hint-assisted correct answer: one-point imperfect success and
    schedule using the imperfect-success rule.
-   Correct natural answer: returns through normal active rotation.
-   Every submitted exercise counts toward the +20/+30 counters,
    including reviews.
-   If several reviews are due, oldest due review is served first.
-   Skip does not change score or create a linguistic attempt; it moves
    the text to the end of its applicable queue while preserving
    pedagogical obligations.

## 9. Perfect learning record and test eligibility

A text can leave initial learning in two ways:

### Perfect record

If the text satisfies its full required number of successes with no
imperfect event, it is directly mastered.

The required count respects any manual `+1 repetition` increases.

### Imperfect record

If its initial learning history contains an incorrect answer, unnatural
answer, writing-only issue, or hint-assisted success, it enters the test
pool after meeting its learning mastery threshold.

`perfect_learning_record` becomes false permanently for that learning
phase once an imperfect event occurs.

## 10. Tests

-   A Test contains exactly 25 unique texts.
-   A text can belong to one and only one Test for a given user.
-   Texts may be randomized when assigned within a Test.
-   Once assigned, Test membership is permanent.
-   No test is available until 25 eligible texts exist.
-   Waiting texts remain unassigned until 25 can form a new Test.
-   Test composition never changes.
-   Completed tests remain fully viewable.
-   Users can inspect the content and history of every text in a test.
-   A completed test can be retaken.
-   A retake creates a new `TestAttempt`; it does not create a new Test.
-   The displayed status of a Test reflects its latest attempt.
-   Historical attempts remain preserved.

During the initial mastery phase of a Test, a text requires 2 correct
consecutive test responses to be considered mastered in that test. An
incorrect response resets the consecutive-success counter.

A voluntary retake of a completed Test presents all 25 texts again and
is primarily a retention measurement. It does not reactivate texts in
the main learning bank.

## 11. Hints

Hints are progressive and formulation-oriented rather than
grammar-label-oriented.

Example progression:

1.  conceptual clue;
2.  partial formulation;
3.  stronger language chunk.

Once any hint is requested, the attempt is capped at 1 point regardless
of how many hint levels are opened.

## 12. Grammar explanations

Grammar and linguistic explanations should often be available but hidden
by default behind an action such as `Why?`.

The normal feedback should remain concise and acquisition-oriented. A
user who explicitly opens the explanation may receive a detailed
explanation with examples.

Generated explanations should be cached/persisted for reuse.

## 13. Useful patterns/chunks

The LLM identifies reusable natural chunks such as:

-   `I haven't had a chance to...`
-   `I was wondering if...`
-   `As far as I know...`
-   `It looks like...`

Patterns can be shared across related texts and surfaced in
statistics/search. They do not become a separate grammar curriculum.

## 14. Audio and speech

Audio applies only to English content supplied by the application.

Audio must be available for:

-   recommended answer;
-   each common alternative;
-   useful English patterns/examples where appropriate.

No French TTS is required. No automatic TTS is required for the user's
own submitted answer.

The recommended answer can autoplay after evaluation; this is a user
preference and is ON by default.

`Repeat aloud` is available after correction. V1 does not need complex
pronunciation scoring.

Speech-to-text flow:

microphone -\> transcription -\> editable field -\> user review -\>
Submit.

## 15. Contextual AI chat

Each Text has an optional contextual conversation with the LLM.

The chat knows the relevant text, answer, verdict, recommendations, and
prior conversation. It supports questions about:

-   alternative formulations;
-   naturalness;
-   nuance;
-   grammar;
-   vocabulary;
-   register;
-   context;
-   pronunciation guidance.

Chat messages never automatically change learning progress or accepted
references.

Chat history is autosaved and remains accessible after mastery and from
completed tests.

## 16. Re-evaluation

A user can contest an evaluation.

Re-evaluation:

-   is a new evaluation record;
-   receives the previous verdict as context;
-   reassesses independently;
-   specifically avoids treating "different from preferred translation"
    as "unnatural";
-   can replace the active verdict;
-   preserves all previous evaluations for audit/statistics.

## 17. Imports

Support CSV and JSON.

Minimum required field:

-   `french_text`.

Optional metadata can include difficulty, contexts, concepts, skills,
etc.

Import flow:

upload -\> validate -\> normalize -\> detect duplicates -\> preview -\>
confirm import.

Duplicate detection is textual/normalized, not semantic.

Import results report imported, skipped duplicates, and invalid rows.

Texts can be disabled. Existing history is preserved.

Editing a previously used text creates a new content version so
historical attempts remain tied to the version actually seen.

## 18. Autosave

There is no general user-facing Save button.

Persist automatically:

-   drafts;
-   hints opened;
-   submitted attempts;
-   progress;
-   queue state;
-   test progress;
-   chat;
-   preferences;
-   manual mastery changes;
-   repetition requirement changes;
-   imports and administrative actions.

A draft does not count as an attempt.

If persistence fails, the UI must not pretend the action succeeded.

## 19. Statistics

Dashboard summary:

-   overall mastered progress;
-   active texts;
-   test-bank/test availability;
-   natural answer rate;
-   overall success rate;
-   recent trend.

Detailed statistics include:

-   unseen/active/mastered/manual/test states;
-   verdict distributions;
-   7-day, 30-day, all-time trends;
-   hardest texts;
-   attempts before mastery;
-   hint usage;
-   writing-only issues;
-   voice vs keyboard input;
-   re-evaluation frequency and changed verdicts;
-   recurring error categories;
-   performance by grammar concept/context/difficulty;
-   patterns encountered;
-   test/retake performance;
-   AI usage metrics.

Manual acquisition is never counted as a correct response.

## 20. Search

Users can search learned content by:

-   French text;
-   preferred English translation;
-   alternatives;
-   useful patterns.

Search is read-only and does not affect learning progress.

## 21. UX expectations

The UI must be:

-   polished;
-   modern;
-   professional;
-   visually cohesive;
-   responsive on desktop/tablet/mobile;
-   appropriate for a commercial-quality adult learning product.

Avoid a generic prototype/Bootstrap appearance.

The design system must define reusable typography, spacing, components,
states, motion, forms, cards, badges, charts, and accessibility
behavior.

Gamification should remain restrained and adult/professional.
