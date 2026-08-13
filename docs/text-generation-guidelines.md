# Text Generation Guidelines

## Goal

Generate content that develops spontaneous, natural American English for
professional and everyday communication.

Avoid grammar-drill sequencing. The experience should resemble
immersion: varied concepts appear naturally and unpredictably.

## Initial prototype

Generate 100 texts only after the application and generation rules are
ready.

After validation, generate the real initial corpus of 500 texts.

Additional corpora can later be generated/imported as CSV or JSON.

## CEFR distribution

The app now supports the full CEFR scale (A1-C2; see
docs/learning-engine.md, "Level selection and the weighted active
bank"), since each user's active bank is composed around whichever
level they choose. The distribution below was the target for the
initial prototype batch (B1/B2/C1 only, written before level selection
existed) and is kept here as a historical baseline; future generation
batches should extend coverage to A1, A2, and C2 as well so the
weighted selection has real content to draw from at every level,
rather than immediately falling back to whatever's available.

Initial batch, for every 100 texts:

-   B1: 15%
-   B2: 70%
-   C1: 15%

For 500:

-   B1: 75
-   B2: 350
-   C1: 75

B1 should consolidate useful structures that need automaticity.

B2 is the core acquisition target.

C1 should add nuance and flexibility, not obscure academic vocabulary.

CEFR level is metadata and is not shown before answering.

## Context distribution guideline

Initial target:

-   40% general professional situations;
-   20% technical/project situations;
-   20% everyday English useful around work;
-   20% general life situations outside work.

Technical content should support natural professional English, not turn
the corpus into a DevOps vocabulary course.

## Structural diversity

Deliberately mix:

-   affirmative;
-   negative;
-   direct questions;
-   indirect questions;
-   question tags;
-   imperatives;
-   conditionals;
-   hypothetical statements;
-   comparisons;
-   polite requests;
-   suggestions;
-   assumptions;
-   disagreement;
-   confirmation;
-   uncertainty;
-   explanations;
-   justifications;
-   past narratives;
-   future plans;
-   reported speech;
-   reactions/responses.

Combine dimensions rather than isolating one grammar rule per text.

## Grammar/language diversity

Include natural exposure to:

-   present/past/future forms;
-   present perfect;
-   modal verbs;
-   conditionals;
-   reported speech;
-   relative clauses;
-   indirect questions;
-   phrasal verbs;
-   prepositions;
-   articles;
-   idiomatic expressions;
-   contractions;
-   workplace politeness;
-   hedging/nuance;
-   common American conversational chunks.

## Length

Mix:

-   short: roughly 8-15 words;
-   medium: roughly 15-25 words;
-   contextual: 2-3 short sentences where needed.

Multi-sentence texts exist to provide context, not to create long
translation paragraphs.

## Ambiguity

Avoid French prompts that cannot reasonably determine intended English
meaning.

When ambiguity would exist, provide enough context in the Text.

## Naturalness

Prompts should lead to multiple plausible English formulations where
reasonable.

Do not design exercises that merely test one vocabulary word.

Avoid artificial corporate jargon.

Prefer situations people would actually say in meetings, calls, chats,
workplace conversations, and daily life.

## Chunk reuse

Avoid superficial duplicate texts, but deliberately reuse important
structures across different contexts.

Example progression:

-   `I haven't had a chance to look into it yet.`
-   `I haven't had a chance to talk to him about it.`
-   `We haven't had a chance to test that solution yet.`

The goal is unconscious reuse/automaticity.

## Metadata

Each generated Text may include:

-   french_text;
-   difficulty;
-   contexts\[\];
-   grammar_concepts\[\];
-   skills\[\];
-   exercise_type.

Metadata is for analytics and content quality, not for determining
exercise order.

## Future situational exercises

Prepare for prompts where the learner receives a situation/intention
rather than a French sentence to translate.

Goal:

French -\> English production eventually supplemented by
Situation/intention -\> English production.

This supports direct English production without mental translation.
