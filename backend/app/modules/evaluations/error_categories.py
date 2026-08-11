"""Closed vocabulary for Evaluation.error_categories.

A fixed set keeps statistics ("recurring error categories", "performance
by grammar concept") comparable across evaluations. Modeled as an Enum
so OpenAI structured outputs can enforce it at generation time rather
than requiring post-hoc validation (docs/linguistic-benchmark.md
coverage areas).
"""

import enum


class ErrorCategory(str, enum.Enum):
    VERB_TENSE = "VERB_TENSE"
    MODAL_VERBS = "MODAL_VERBS"
    CONDITIONALS = "CONDITIONALS"
    PREPOSITIONS = "PREPOSITIONS"
    ARTICLES = "ARTICLES"
    WORD_ORDER = "WORD_ORDER"
    PHRASAL_VERBS = "PHRASAL_VERBS"
    FALSE_FRIENDS = "FALSE_FRIENDS"
    REGISTER = "REGISTER"
    AGREEMENT = "AGREEMENT"
    VOCABULARY_CHOICE = "VOCABULARY_CHOICE"
    PUNCTUATION_OR_CAPITALIZATION = "PUNCTUATION_OR_CAPITALIZATION"
    OTHER = "OTHER"


ERROR_CATEGORIES: list[str] = [category.value for category in ErrorCategory]
