# UI/UX Specification

## Product design direction

PhraseFluency should look like a polished commercial learning product,
not an internal tool or prototype.

Design qualities:

-   adult;
-   premium;
-   calm;
-   modern;
-   professional;
-   focused;
-   spacious;
-   responsive;
-   accessible.

Use a coherent design system. Avoid excessive gamification.

## Main navigation

-   Dashboard
-   Learn
-   Tests
-   Texts
-   Statistics
-   Account
-   Admin (ADMIN only)
-   Logout

## Authentication

Screens:

-   Sign in
-   Create account

V1: - email/password only.

Future-ready: - password recovery; - verification; - OAuth/MFA.

## Dashboard

Show:

-   mastered / target;
-   100 active status;
-   waiting/test counts;
-   available tests;
-   natural answer rate;
-   recent performance trend;
-   Continue Learning;
-   Start/Continue Test where available.

If no test exists:

"No test available yet. Complete more learning exercises to unlock your
first 25-text test."

## Learning screen

Before submission:

-   current progress indicator;
-   French Text;
-   response textarea;
-   microphone;
-   progressive hint;
-   Submit;
-   Skip;
-   `+1 repetition`;
-   Mark as acquired.

Do not display CEFR level or grammar topic before answering.

After successful evaluation:

-   human-readable verdict;
-   awarded progress;
-   user's answer;
-   corrected form if needed;
-   recommended American-English formulation;
-   up to two common alternatives;
-   independent audio control per English formulation;
-   useful pattern(s);
-   Repeat aloud;
-   Why?/Grammar explanation;
-   Re-evaluate;
-   Ask AI;
-   Next.

Recommended answer autoplay: - configurable; - ON by default.

No automatic Next.

## Hints

Progressive disclosure.

Prefer formulation/context clues over labels such as "use present
perfect."

Once opened, visually indicate that the attempt is hint-assisted.

## Tests

Tests screen groups:

-   Available
-   In progress
-   Completed

Each Test displays:

-   Test number;
-   25-text membership;
-   latest status;
-   latest progress;
-   attempt history.

Test detail allows viewing all 25 texts and filtering:

-   All
-   Remaining
-   Mastered
-   Difficult

Completed tests remain viewable and have `Retake test`.

## Text detail

Read-only learning history plus allowed management actions.

Show:

-   French text/version;
-   preferred translation;
-   alternatives;
-   useful patterns;
-   status;
-   mastery requirement;
-   attempts;
-   verdict history;
-   hints;
-   test membership;
-   contextual chat.

Actions where allowed:

-   Ask AI
-   Disable
-   Edit/version
-   Mark acquired
-   Increase repetition requirement

## Statistics

Dashboard-like overview plus detailed charts/tables for:

-   verdicts;
-   recent vs historical performance;
-   error categories;
-   concepts;
-   CEFR level;
-   difficult texts;
-   hints;
-   writing issues;
-   input method;
-   re-evaluation;
-   test retention;
-   useful patterns.

## Search

Search across:

-   French;
-   preferred English;
-   alternatives;
-   patterns.

Viewing search results never changes progression.

## Autosave UX

Do not ask users to save routine state.

Provide subtle states where useful:

-   Saving...
-   Saved
-   Retry required

Never display success if persistence failed.

## Responsive behavior

Desktop is first-class, but tablet/mobile must be fully usable.

Mobile should particularly support:

-   microphone input;
-   one-handed primary actions;
-   readable feedback;
-   audio playback;
-   short learning bursts.

## Accessibility

Design-system components should support:

-   keyboard navigation;
-   visible focus;
-   semantic controls;
-   adequate contrast;
-   screen-reader labels;
-   reduced-motion preference where appropriate.
