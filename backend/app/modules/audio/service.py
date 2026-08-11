import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audio.models import AudioAsset
from app.modules.audio.providers import SpeechToTextProvider, TextToSpeechProvider
from app.modules.audio.storage import AudioStorage
from app.shared.ai_usage import record_ai_usage
from app.shared.models import AIOperation


def _content_hash(text: str, voice: str) -> str:
    return hashlib.sha256(f"{voice}:{text}".encode("utf-8")).hexdigest()


def get_or_create_audio(
    db: Session,
    tts: TextToSpeechProvider,
    storage: AudioStorage,
    text: str,
) -> AudioAsset:
    """Persist and reuse audio by (voice, text) content hash — English
    app-supplied content only (docs/product-requirements.md #14)."""
    content_hash = _content_hash(text, tts.voice)
    existing = db.scalar(select(AudioAsset).where(AudioAsset.content_hash == content_hash))
    if existing is not None:
        return existing

    audio_bytes = tts.synthesize(text)
    storage_key = f"{content_hash}.mp3"
    storage.save(storage_key, audio_bytes)

    asset = AudioAsset(
        content_hash=content_hash,
        english_text=text,
        language="en-US",
        voice=tts.voice,
        provider="openai",
        storage_key=storage_key,
    )
    db.add(asset)

    record_ai_usage(
        db,
        operation=AIOperation.TTS,
        model=tts.model,
        input_tokens=len(text),
        output_tokens=0,
    )

    db.commit()
    db.refresh(asset)
    return asset


def read_audio_bytes(storage: AudioStorage, asset: AudioAsset) -> bytes:
    return storage.read(asset.storage_key)


def transcribe(
    db: Session,
    stt: SpeechToTextProvider,
    user_id: uuid.UUID,
    audio_bytes: bytes,
    filename: str,
) -> str:
    text = stt.transcribe(audio_bytes, filename)

    record_ai_usage(
        db,
        operation=AIOperation.STT,
        model=stt.model,
        input_tokens=0,
        output_tokens=0,
        user_id=user_id,
    )
    db.commit()

    return text
