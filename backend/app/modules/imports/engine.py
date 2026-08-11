"""Pure import validation/dedup rules (docs/product-requirements.md #17).

No FastAPI or SQLAlchemy imports — the set of existing normalized texts
is passed in rather than queried here, so this stays DB-free and
testable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.texts.models import Difficulty, ExerciseType

VALID_DIFFICULTIES = {d.value for d in Difficulty}
VALID_EXERCISE_TYPES = {e.value for e in ExerciseType}
DEFAULT_DIFFICULTY = Difficulty.B2.value
DEFAULT_EXERCISE_TYPE = ExerciseType.TRANSLATION.value


def normalize_french_text(text: str) -> str:
    return " ".join(text.strip().casefold().split())


@dataclass(frozen=True)
class ImportRow:
    french_text: str
    difficulty: str | None = None
    exercise_type: str | None = None
    contexts: list[str] = field(default_factory=list)
    grammar_concepts: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RowResult:
    row_number: int
    french_text: str
    difficulty: str
    exercise_type: str
    contexts: list[str]
    grammar_concepts: list[str]
    skills: list[str]
    status: str  # "VALID" | "DUPLICATE" | "INVALID"
    errors: list[str]


def validate_and_dedupe_rows(
    rows: list[ImportRow], existing_normalized_texts: set[str]
) -> list[RowResult]:
    seen_in_batch: set[str] = set()
    results: list[RowResult] = []

    for row_number, row in enumerate(rows, start=1):
        errors: list[str] = []

        french_text = (row.french_text or "").strip()
        if not french_text:
            errors.append("french_text is required")

        difficulty = (row.difficulty or DEFAULT_DIFFICULTY).strip().upper()
        if difficulty not in VALID_DIFFICULTIES:
            errors.append(f"difficulty must be one of {sorted(VALID_DIFFICULTIES)}")

        exercise_type = (row.exercise_type or DEFAULT_EXERCISE_TYPE).strip().upper()
        if exercise_type not in VALID_EXERCISE_TYPES:
            errors.append(f"exercise_type must be one of {sorted(VALID_EXERCISE_TYPES)}")

        contexts = list(row.contexts)
        grammar_concepts = list(row.grammar_concepts)
        skills = list(row.skills)

        if errors:
            results.append(
                RowResult(
                    row_number, french_text, difficulty, exercise_type,
                    contexts, grammar_concepts, skills, "INVALID", errors,
                )
            )
            continue

        normalized = normalize_french_text(french_text)
        if normalized in existing_normalized_texts or normalized in seen_in_batch:
            results.append(
                RowResult(
                    row_number, french_text, difficulty, exercise_type,
                    contexts, grammar_concepts, skills, "DUPLICATE", [],
                )
            )
            continue

        seen_in_batch.add(normalized)
        results.append(
            RowResult(
                row_number, french_text, difficulty, exercise_type,
                contexts, grammar_concepts, skills, "VALID", [],
            )
        )

    return results
