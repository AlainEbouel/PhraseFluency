import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class TestAttemptStatus(str, enum.Enum):
    __test__ = False  # not a pytest test case despite the name

    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class Test(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "tests"
    __test__ = False  # not a pytest test case despite the name

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)


class TestText(Base):
    __tablename__ = "test_texts"
    __test__ = False  # not a pytest test case despite the name
    __table_args__ = (UniqueConstraint("user_id", "text_id", name="uq_test_texts_user_text"),)

    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tests.id", ondelete="CASCADE"), primary_key=True
    )
    text_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("texts.id"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    consecutive_successes: Mapped[int] = mapped_column(Integer, default=0)
    mastered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class TestAttempt(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "test_attempts"
    __test__ = False  # not a pytest test case despite the name

    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tests.id", ondelete="CASCADE"), index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[TestAttemptStatus] = mapped_column(
        Enum(TestAttemptStatus, name="test_attempt_status"),
        default=TestAttemptStatus.IN_PROGRESS,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    latest_position: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0)
