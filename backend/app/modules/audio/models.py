from sqlalchemy import String, Text as TextColumn
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class AudioAsset(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "audio_assets"

    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    english_text: Mapped[str] = mapped_column(TextColumn)
    language: Mapped[str] = mapped_column(String(8), default="en-US")
    voice: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32))
    storage_key: Mapped[str] = mapped_column(String(512))
