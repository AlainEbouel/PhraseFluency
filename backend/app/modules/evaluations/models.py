import uuid

from sqlalchemy import ARRAY, Boolean, Enum, ForeignKey, Integer, String, Text as TextColumn
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.evaluations.enums import AttemptMode, InputMethod, Verdict
from app.shared.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class Attempt(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "attempts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    text_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("text_versions.id"), index=True
    )
    mode: Mapped[AttemptMode] = mapped_column(Enum(AttemptMode, name="attempt_mode"))
    sequence_number: Mapped[int] = mapped_column(Integer)
    user_answer: Mapped[str] = mapped_column(TextColumn)
    input_method: Mapped[InputMethod] = mapped_column(
        Enum(InputMethod, name="input_method")
    )
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False)
    max_hint_level: Mapped[int] = mapped_column(Integer, default=0)
    active_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluations.id", use_alter=True, name="fk_attempts_active_evaluation_id"),
        default=None,
    )
    submission_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)


class Evaluation(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "evaluations"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attempts.id", ondelete="CASCADE"), index=True
    )
    evaluation_number: Mapped[int] = mapped_column(Integer)
    verdict: Mapped[Verdict] = mapped_column(Enum(Verdict, name="verdict"))
    meaning_preserved: Mapped[bool] = mapped_column(Boolean)
    grammar_correct: Mapped[bool] = mapped_column(Boolean)
    natural_american_english: Mapped[bool] = mapped_column(Boolean)
    writing_issues: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    corrected_answer: Mapped[str | None] = mapped_column(TextColumn, default=None)
    feedback: Mapped[str] = mapped_column(TextColumn)
    error_categories: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
