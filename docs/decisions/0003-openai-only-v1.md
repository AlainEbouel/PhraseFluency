# ADR 0003 - OpenAI-Only Linguistic Engine in V1

## Decision

Use an OpenAI LLM as the sole linguistic evaluation engine in V1.

## Rationale

The product requires semantic equivalence, natural American-English
judgment, multiple valid translations, explanations, and contextual
nuance. A general LLM can cover the complete initial workflow.

## Extensibility

The backend uses an `EvaluationEngine` abstraction so LanguageTool,
DeepL Write, or a hybrid evaluator can be introduced later if benchmark
evidence shows a need.
