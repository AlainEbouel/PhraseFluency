import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Text as TextColumn
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.learning.engine import (
    DEFAULT_REQUIRED_NATURAL_EQUIVALENTS,
    DEFAULT_REQUIRED_SCORE,
)
from app.modules.learning.enums import TextProgressStatus
from app.modules.texts.models import Difficulty


class UserTextProgress(Base):
    __tablename__ = "user_text_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    text_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("texts.id", ondelete="CASCADE"), primary_key=True
    )

    status: Mapped[TextProgressStatus] = mapped_column(
        Enum(TextProgressStatus, name="text_progress_status"),
        default=TextProgressStatus.UNSEEN,
    )
    mastery_score: Mapped[int] = mapped_column(Integer, default=0)
    required_score: Mapped[int] = mapped_column(Integer, default=DEFAULT_REQUIRED_SCORE)
    required_natural_equivalents: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_REQUIRED_NATURAL_EQUIVALENTS
    )
    times_presented: Mapped[int] = mapped_column(Integer, default=0)
    natural_count: Mapped[int] = mapped_column(Integer, default=0)
    unnatural_count: Mapped[int] = mapped_column(Integer, default=0)
    writing_issue_count: Mapped[int] = mapped_column(Integer, default=0)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0)
    hint_count: Mapped[int] = mapped_column(Integer, default=0)
    manually_acquired: Mapped[bool] = mapped_column(Boolean, default=False)
    perfect_learning_record: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    next_review_at_exercise: Mapped[int | None] = mapped_column(Integer, default=None)
    rotation_position: Mapped[int] = mapped_column(Integer, default=0)


class UserLearningState(Base):
    __tablename__ = "user_learning_state"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    exercise_sequence: Mapped[int] = mapped_column(Integer, default=0)
    current_text_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("texts.id"), default=None
    )
    current_draft: Mapped[str | None] = mapped_column(TextColumn, default=None)
    current_hint_level: Mapped[int] = mapped_column(Integer, default=0)
    current_level: Mapped[Difficulty | None] = mapped_column(
        Enum(Difficulty, name="difficulty"), default=None
    )
