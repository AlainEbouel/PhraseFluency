import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import utcnow


class UserWeaknessProfile(Base):
    """Cached AI-generated improvement suggestions for a user's weakest
    error categories. Regenerated only when the top-3 category ranking
    itself changes (see statistics/service.py), not on every new attempt.
    """

    __tablename__ = "user_weakness_profile"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    category_fingerprint: Mapped[str] = mapped_column(String(256))
    suggestions: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
