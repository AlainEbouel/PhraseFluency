from app.modules.audio.providers import SpeechToTextProvider, VERBATIM_STYLE_PROMPT


class _FakeTranscription:
    def __init__(self, text: str):
        self.text = text


class _FakeCreateEndpoint:
    def __init__(self, text: str = "some transcript"):
        self._text = text
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeTranscription(self._text)


class _FakeClient:
    def __init__(self, create_endpoint: _FakeCreateEndpoint):
        transcriptions = type("Transcriptions", (), {"create": staticmethod(create_endpoint)})()
        audio = type("Audio", (), {"transcriptions": transcriptions})()
        self.audio = audio


class TestSpeechToTextProvider:
    def test_transcribe_passes_the_verbatim_style_prompt(self):
        endpoint = _FakeCreateEndpoint()
        provider = SpeechToTextProvider(api_key="sk-test")
        provider._client = _FakeClient(endpoint)

        result = provider.transcribe(b"fake-audio-bytes", "recording.webm")

        assert result == "some transcript"
        assert len(endpoint.calls) == 1
        assert endpoint.calls[0]["prompt"] == VERBATIM_STYLE_PROMPT
        assert endpoint.calls[0]["language"] == "en"
