import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.audio import service
from app.modules.audio.providers import SpeechToTextProvider, TextToSpeechProvider
from app.modules.audio.schemas import TranscriptionOut
from app.modules.audio.storage import AudioStorage, LocalFilesystemAudioStorage
from app.modules.auth.dependencies import get_current_user
from app.modules.evaluations.engine import EvaluationEngineError
from app.modules.texts.models import LinguisticReference, Pattern, Text
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/audio", tags=["audio"])

_tts: TextToSpeechProvider | None = None
_stt: SpeechToTextProvider | None = None
_storage: AudioStorage | None = None


def get_tts_provider() -> TextToSpeechProvider:
    global _tts
    if _tts is None:
        settings = get_settings()
        _tts = TextToSpeechProvider(
            api_key=settings.openai_api_key,
            voice=settings.tts_voice,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    return _tts


def get_stt_provider() -> SpeechToTextProvider:
    global _stt
    if _stt is None:
        settings = get_settings()
        _stt = SpeechToTextProvider(
            api_key=settings.openai_api_key, timeout_seconds=settings.openai_timeout_seconds
        )
    return _stt


def get_audio_storage() -> AudioStorage:
    global _storage
    if _storage is None:
        settings = get_settings()
        _storage = LocalFilesystemAudioStorage(settings.audio_storage_path)
    return _storage


def _get_reference_for_text(db: Session, text_id: uuid.UUID) -> LinguisticReference | None:
    text = db.get(Text, text_id)
    if text is None or text.current_version_id is None:
        return None
    return db.scalar(
        select(LinguisticReference).where(
            LinguisticReference.text_version_id == text.current_version_id
        )
    )


def _serve(db: Session, text: str) -> Response:
    tts = get_tts_provider()
    storage = get_audio_storage()
    try:
        asset = service.get_or_create_audio(db, tts, storage, text)
        audio_bytes = service.read_audio_bytes(storage, asset)
    except EvaluationEngineError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Audio is temporarily unavailable, please retry: {exc}",
        ) from exc
    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.get("/reference/{text_id}/preferred")
def preferred_audio(
    text_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    reference = _get_reference_for_text(db, text_id)
    if reference is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No reference found for this text")
    return _serve(db, reference.preferred_translation)


@router.get("/reference/{text_id}/alternative/{index}")
def alternative_audio(
    text_id: uuid.UUID,
    index: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    reference = _get_reference_for_text(db, text_id)
    if reference is None or index >= len(reference.alternatives):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alternative not found")
    return _serve(db, reference.alternatives[index])


@router.get("/pattern/{pattern_id}")
def pattern_audio(
    pattern_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    pattern = db.get(Pattern, pattern_id)
    if pattern is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pattern not found")
    return _serve(db, pattern.example)


@router.post("/transcribe", response_model=TranscriptionOut)
async def transcribe(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    audio_bytes = await file.read()
    stt = get_stt_provider()
    try:
        text = service.transcribe(db, stt, user.id, audio_bytes, file.filename or "recording.webm")
    except EvaluationEngineError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Transcription is temporarily unavailable, please retry: {exc}",
        ) from exc
    return TranscriptionOut(text=text)
