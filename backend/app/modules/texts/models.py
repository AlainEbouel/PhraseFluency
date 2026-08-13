import enum
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, Enum, ForeignKey, String, Table, Text as TextColumn, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin, utcnow


class ExerciseType(str, enum.Enum):
    TRANSLATION = "TRANSLATION"
    SITUATIONAL = "SITUATIONAL"


class Difficulty(str, enum.Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class Text(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "texts"

    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("text_versions.id", use_alter=True, name="fk_texts_current_version_id"),
        default=None,
    )
    source: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    current_version: Mapped["TextVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )


class TextVersion(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "text_versions"

    text_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("texts.id", ondelete="CASCADE"), index=True
    )
    french_text: Mapped[str] = mapped_column(TextColumn)
    exercise_type: Mapped[ExerciseType] = mapped_column(
        Enum(ExerciseType, name="exercise_type"), default=ExerciseType.TRANSLATION
    )
    difficulty: Mapped[Difficulty] = mapped_column(Enum(Difficulty, name="difficulty"))
    contexts: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    grammar_concepts: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)


class LinguisticReference(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "linguistic_references"

    text_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("text_versions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    preferred_translation: Mapped[str] = mapped_column(TextColumn)
    alternatives: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    hints: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    grammar_explanation: Mapped[str | None] = mapped_column(TextColumn, default=None)
    patterns: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    generated_at: Mapped[datetime] = mapped_column(default=utcnow)


pattern_text_versions = Table(
    "pattern_text_versions",
    Base.metadata,
    Column("pattern_id", UUID(as_uuid=True), ForeignKey("patterns.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "text_version_id",
        UUID(as_uuid=True),
        ForeignKey("text_versions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Pattern(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "patterns"

    expression: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    meaning: Mapped[str] = mapped_column(TextColumn)
    example: Mapped[str] = mapped_column(TextColumn)

    related_text_versions: Mapped[list["TextVersion"]] = relationship(
        secondary=pattern_text_versions
    )
