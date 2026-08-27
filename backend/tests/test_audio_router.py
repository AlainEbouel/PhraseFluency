from app.modules.audio import router as audio_router


class TestTtsVoicePool:
    def test_pool_has_four_distinct_profiles(self):
        pool = audio_router._get_tts_pool()
        assert set(pool) == set(audio_router.TTS_VOICE_PROFILES)
        assert len(audio_router.TTS_VOICE_PROFILES) == 4

    def test_pool_is_memoized_across_calls(self):
        assert audio_router._get_tts_pool() is audio_router._get_tts_pool()

    def test_pick_is_deterministic_when_random_choice_is_mocked(self, monkeypatch):
        monkeypatch.setattr(audio_router.random, "choice", lambda seq: "nova")
        assert audio_router._pick_tts_provider().voice == "nova"

    def test_repeated_picks_can_produce_more_than_one_distinct_voice(self):
        # Probabilistic but effectively never flaky: with 4 equally-likely
        # profiles, P(all 200 picks identical) = (1/4)**199.
        voices = {audio_router._pick_tts_provider().voice for _ in range(200)}
        assert len(voices) > 1
