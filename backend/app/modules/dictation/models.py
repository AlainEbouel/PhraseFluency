import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text as TextColumn,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.evaluations.enums import Verdict
from app.shared.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class UserDictationProgress(Base):
    """A fully separate practice track from UserTextProgress — no shared
    mastery, status, or rotation with the translation exercise. A text
    keeps recycling through dictation indefinitely; there is no terminal
    "mastered" state here.
    """

    __tablename__ = "user_dictation_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    text_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("texts.id", ondelete="CASCADE"), primary_key=True
    )
    times_presented: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    writing_issue_count: Mapped[int] = mapped_column(Integer, default=0)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0)
    next_review_at_exercise: Mapped[int | None] = mapped_column(Integer, default=None)
    rotation_position: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class DictationAttempt(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """No separate Evaluation table: grading is a deterministic string
    comparison (dictation/engine.py), not an LLM judgment call, so there
    is no "re-evaluate" concept to support.
    """

    __tablename__ = "dictation_attempts"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "submission_id", name="uq_dictation_attempts_user_submission"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    text_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("texts.id"), index=True
    )
    user_answer: Mapped[str] = mapped_column(TextColumn)
    verdict: Mapped[Verdict] = mapped_column(Enum(Verdict, name="verdict"))
    corrected_answer: Mapped[str | None] = mapped_column(TextColumn, default=None)
    submission_id: Mapped[str] = mapped_column(String(64), index=True)
