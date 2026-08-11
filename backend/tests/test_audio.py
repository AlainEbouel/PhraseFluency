import uuid

from app.modules.audio import service
from app.modules.audio.models import AudioAsset
from app.modules.audio.storage import LocalFilesystemAudioStorage
from app.modules.users.models import User, UserRole
from app.shared.models import AIOperation, AIUsage


class FakeTTS:
    def __init__(self, voice="alloy", model="tts-1"):
        self.voice = voice
        self.model = model
        self.calls: list[str] = []

    def synthesize(self, text: str) -> bytes:
        self.calls.append(text)
        return f"audio-bytes-for:{text}".encode("utf-8")


class FakeSTT:
    def __init__(self, text: str, model="whisper-1"):
        self.text = text
        self.model = model
        self.calls: list[bytes] = []

    def transcribe(self, audio_bytes: bytes, filename: str) -> str:
        self.calls.append(audio_bytes)
        return self.text


def make_user(db_session) -> User:
    user = User(email=f"{uuid.uuid4()}@phrasefluency.app", password_hash="x", role=UserRole.USER)
    db_session.add(user)
    db_session.flush()
    return user


class TestLocalFilesystemAudioStorage:
    def test_round_trips_bytes(self, tmp_path):
        storage = LocalFilesystemAudioStorage(str(tmp_path))
        storage.save("clip.mp3", b"some-audio-bytes")

        assert storage.exists("clip.mp3") is True
        assert storage.read("clip.mp3") == b"some-audio-bytes"

    def test_missing_key_does_not_exist(self, tmp_path):
        storage = LocalFilesystemAudioStorage(str(tmp_path))
        assert storage.exists("missing.mp3") is False

    def test_sanitizes_path_traversal_attempts(self, tmp_path):
        storage = LocalFilesystemAudioStorage(str(tmp_path))
        storage.save("../../etc/evil.mp3", b"x")

        # Must land inside base_path, not escape it.
        written_files = list(tmp_path.iterdir())
        assert len(written_files) == 1
        assert written_files[0].parent == tmp_path


class TestGetOrCreateAudio:
    def test_synthesizes_and_persists_on_first_call(self, db_session, tmp_path):
        storage = LocalFilesystemAudioStorage(str(tmp_path))
        tts = FakeTTS()

        asset = service.get_or_create_audio(db_session, tts, storage, "Hello there.")

        assert isinstance(asset, AudioAsset)
        assert asset.english_text == "Hello there."
        assert asset.provider == "openai"
        assert storage.read(asset.storage_key) == b"audio-bytes-for:Hello there."
        assert tts.calls == ["Hello there."]

    def test_second_call_with_same_text_and_voice_reuses_cached_asset(self, db_session, tmp_path):
        storage = LocalFilesystemAudioStorage(str(tmp_path))
        tts = FakeTTS()

        first = service.get_or_create_audio(db_session, tts, storage, "Hello there.")
        second = service.get_or_create_audio(db_session, tts, storage, "Hello there.")

        assert first.id == second.id
        assert tts.calls == ["Hello there."]  # only synthesized once

    def test_different_voice_creates_a_separate_asset(self, db_session, tmp_path):
        storage = LocalFilesystemAudioStorage(str(tmp_path))
        tts_a = FakeTTS(voice="alloy")
        tts_b = FakeTTS(voice="nova")

        asset_a = service.get_or_create_audio(db_session, tts_a, storage, "Hello there.")
        asset_b = service.get_or_create_audio(db_session, tts_b, storage, "Hello there.")

        assert asset_a.id != asset_b.id

    def test_records_ai_usage_only_on_first_synthesis(self, db_session, tmp_path):
        storage = LocalFilesystemAudioStorage(str(tmp_path))
        tts = FakeTTS()

        service.get_or_create_audio(db_session, tts, storage, "Hello there.")
        service.get_or_create_audio(db_session, tts, storage, "Hello there.")

        usage = db_session.query(AIUsage).filter_by(operation=AIOperation.TTS).all()
        assert len(usage) == 1
        assert usage[0].input_tokens == len("Hello there.")


class TestTranscribe:
    def test_returns_transcribed_text_and_records_usage(self, db_session):
        user = make_user(db_session)
        stt = FakeSTT(text="I haven't had a chance to look into it.")

        text = service.transcribe(db_session, stt, user.id, b"fake-audio-bytes", "recording.webm")

        assert text == "I haven't had a chance to look into it."
        assert stt.calls == [b"fake-audio-bytes"]

        usage = (
            db_session.query(AIUsage)
            .filter_by(operation=AIOperation.STT, user_id=user.id)
            .all()
        )
        assert len(usage) == 1
