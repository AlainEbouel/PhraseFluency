import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class AIOperation(str, enum.Enum):
    REFERENCE_GENERATION = "REFERENCE_GENERATION"
    EVALUATION = "EVALUATION"
    REEVALUATION = "REEVALUATION"
    CHAT = "CHAT"
    GRAMMAR_EXPLANATION = "GRAMMAR_EXPLANATION"
    STT = "STT"
    TTS = "TTS"


class AIUsage(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "ai_usage"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    operation: Mapped[AIOperation] = mapped_column(Enum(AIOperation, name="ai_operation"))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Numeric(10, 6), default=0)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
