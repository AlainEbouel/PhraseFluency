import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.texts.models import Difficulty, ExerciseType, Pattern, Text, TextVersion


def _normalize_expression(expression: str) -> str:
    return " ".join(expression.strip().lower().split())


def get_or_create_pattern(
    db: Session, *, expression: str, meaning: str, example: str, text_version: TextVersion
) -> Pattern:
    """Dedup by normalized expression text (textual, not semantic — same
    policy as import duplicate detection, docs/product-requirements.md #17).
    """
    normalized = _normalize_expression(expression)
    pattern = db.scalar(select(Pattern).where(Pattern.expression == normalized))
    if pattern is None:
        pattern = Pattern(expression=normalized, meaning=meaning, example=example)
        db.add(pattern)

    if text_version not in pattern.related_text_versions:
        pattern.related_text_versions.append(text_version)

    return pattern


def list_texts(
    db: Session, *, search: str | None = None, limit: int = 100, offset: int = 0
) -> list[Text]:
    query = select(Text).order_by(Text.created_at.desc())
    if search:
        query = query.join(TextVersion, Text.current_version_id == TextVersion.id).where(
            TextVersion.french_text.ilike(f"%{search}%")
        )
    return db.scalars(query.limit(limit).offset(offset)).all()


def get_text_with_versions(
    db: Session, text_id: uuid.UUID
) -> tuple[Text, list[TextVersion]] | None:
    text = db.get(Text, text_id)
    if text is None:
        return None
    versions = db.scalars(
        select(TextVersion).where(TextVersion.text_id == text_id).order_by(TextVersion.created_at)
    ).all()
    return text, versions


def set_text_enabled(db: Session, text_id: uuid.UUID, enabled: bool) -> Text:
    text = db.get(Text, text_id)
    if text is None:
        raise ValueError("Text not found")
    text.enabled = enabled
    db.add(text)
    db.commit()
    db.refresh(text)
    return text


def create_new_version(
    db: Session,
    text_id: uuid.UUID,
    *,
    french_text: str,
    difficulty: Difficulty,
    exercise_type: ExerciseType = ExerciseType.TRANSLATION,
    contexts: list[str] | None = None,
    grammar_concepts: list[str] | None = None,
    skills: list[str] | None = None,
) -> TextVersion:
    """Editing creates a new version; historical attempts stay tied to the
    version they actually saw (docs/product-requirements.md #17)."""
    text = db.get(Text, text_id)
    if text is None:
        raise ValueError("Text not found")

    version = TextVersion(
        text_id=text_id,
        french_text=french_text,
        difficulty=difficulty,
        exercise_type=exercise_type,
        contexts=contexts or [],
        grammar_concepts=grammar_concepts or [],
        skills=skills or [],
    )
    db.add(version)
    db.flush()

    text.current_version_id = version.id
    db.add(text)
    db.commit()
    db.refresh(version)
    return version
