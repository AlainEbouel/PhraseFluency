"""OpenAI TextToSpeechProvider / SpeechToTextProvider (architecture.md).

Kept as small, focused provider classes (not behind EvaluationEngine —
audio is a distinct concern per architecture.md's domain services list).
"""

from __future__ import annotations

import logging

from openai import OpenAI, OpenAIError

from app.modules.evaluations.engine import EvaluationEngineError

logger = logging.getLogger(__name__)

DEFAULT_TTS_MODEL = "tts-1"
DEFAULT_VOICE = "alloy"
DEFAULT_STT_MODEL = "whisper-1"


class TextToSpeechProvider:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_TTS_MODEL,
        voice: str = DEFAULT_VOICE,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self.model = model
        self.voice = voice

    def synthesize(self, text: str) -> bytes:
        try:
            response = self._client.audio.speech.create(
                model=self.model, voice=self.voice, input=text, response_format="mp3"
            )
        except OpenAIError as exc:
            logger.warning("OpenAI TTS call failed: %s", exc)
            raise EvaluationEngineError(f"TTS provider failure: {exc}") from exc
        return response.read()


class SpeechToTextProvider:
    def __init__(
        self, api_key: str, model: str = DEFAULT_STT_MODEL, timeout_seconds: float = 30.0
    ) -> None:
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self.model = model

    def transcribe(self, audio_bytes: bytes, filename: str) -> str:
        try:
            result = self._client.audio.transcriptions.create(
                model=self.model,
                file=(filename, audio_bytes),
                language="en",
            )
        except OpenAIError as exc:
            logger.warning("OpenAI STT call failed: %s", exc)
            raise EvaluationEngineError(f"STT provider failure: {exc}") from exc
        return result.text
