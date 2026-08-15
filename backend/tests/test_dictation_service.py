import uuid

from sqlalchemy import select

from app.modules.dictation import service
from app.modules.dictation.models import DictationAttempt, UserDictationProgress
from app.modules.evaluations.engine import EvaluationEngine
from app.modules.evaluations.enums import Verdict
from app.modules.evaluations.ports import ReferenceGenerationResult
from app.modules.texts.models import Difficulty, ExerciseType, Text, TextVersion
from app.modules.users.models import User, UserRole

REFERENCE_TEXT = "I haven't had a chance to look into it yet."


class FakeEngine(EvaluationEngine):
    def __init__(self):
        self.generate_reference_calls = 0

    def generate_reference(self, request):
        self.generate_reference_calls += 1
        return ReferenceGenerationResult(
            preferred_translation=REFERENCE_TEXT,
            alternatives=[],
            hints=[],
            patterns=[],
            model="gpt-4o-mini",
            prompt_version="reference-v1",
            input_tokens=1,
            output_tokens=1,
        )

    def evaluate(self, request):
        raise NotImplementedError

    def generate_grammar_explanation(self, request):
        raise NotImplementedError

    def generate_weakness_suggestions(self, request):
        raise NotImplementedError


def make_user(db_session) -> User:
    user = User(email=f"{uuid.uuid4()}@phrasefluency.app", password_hash="x", role=UserRole.USER)
    db_session.add(user)
    db_session.flush()
    return user


def make_text(db_session, french_text=None) -> Text:
    text = Text(source="test")
    db_session.add(text)
    db_session.flush()
    version = TextVersion(
        text_id=text.id,
        french_text=french_text or f"Texte {uuid.uuid4()}",
        exercise_type=ExerciseType.TRANSLATION,
        difficulty=Difficulty.B2,
        contexts=[],
    )
    db_session.add(version)
    db_session.flush()
    text.current_version_id = version.id
    db_session.add(text)
    db_session.flush()
    return text


class TestGetNextDictationExercise:
    def test_returns_none_when_no_texts_exist(self, db_session):
        user = make_user(db_session)

        assert service.get_next_dictation_exercise(db_session, FakeEngine(), user.id) is None

    def test_picks_a_text_and_generates_its_reference(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)
        engine = FakeEngine()

        exercise = service.get_next_dictation_exercise(db_session, engine, user.id)

        assert exercise is not None
        assert exercise.text_id == text.id
        assert exercise.times_presented == 0
        assert engine.generate_reference_calls == 1

    def test_prefers_a_never_presented_text_over_one_already_seen(self, db_session):
        user = make_user(db_session)
        seen_text = make_text(db_session)
        unseen_text = make_text(db_session)
        db_session.add(
            UserDictationProgress(
                user_id=user.id, text_id=seen_text.id, times_presented=3, rotation_position=1
            )
        )
        db_session.commit()

        exercise = service.get_next_dictation_exercise(db_session, FakeEngine(), user.id)

        assert exercise.text_id == unseen_text.id


class TestSubmitDictationAnswer:
    def test_perfect_transcript_is_correct_natural(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)
        engine = FakeEngine()

        result = service.submit_dictation_answer(
            db_session,
            engine,
            user,
            text_id=text.id,
            transcript=REFERENCE_TEXT,
            submission_id="sub-1",
        )

        assert result.verdict == Verdict.CORRECT_NATURAL
        assert result.corrected_answer is None
        progress = db_session.get(UserDictationProgress, (user.id, text.id))
        assert progress.times_presented == 1
        assert progress.correct_count == 1
        assert progress.next_review_at_exercise is None

    def test_wrong_transcript_is_incorrect_and_schedules_a_review(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)

        result = service.submit_dictation_answer(
            db_session,
            FakeEngine(),
            user,
            text_id=text.id,
            transcript="Something completely different.",
            submission_id="sub-1",
        )

        assert result.verdict == Verdict.INCORRECT
        assert result.corrected_answer == REFERENCE_TEXT
        progress = db_session.get(UserDictationProgress, (user.id, text.id))
        assert progress.incorrect_count == 1
        assert progress.next_review_at_exercise is not None

    def test_repeated_submission_id_is_idempotent(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)

        first = service.submit_dictation_answer(
            db_session,
            FakeEngine(),
            user,
            text_id=text.id,
            transcript=REFERENCE_TEXT,
            submission_id="dup",
        )
        second = service.submit_dictation_answer(
            db_session,
            FakeEngine(),
            user,
            text_id=text.id,
            transcript=REFERENCE_TEXT,
            submission_id="dup",
        )

        assert first.verdict == second.verdict == Verdict.CORRECT_NATURAL
        attempts = db_session.scalars(
            select(DictationAttempt).where(DictationAttempt.submission_id == "dup")
        ).all()
        assert len(attempts) == 1
        progress = db_session.get(UserDictationProgress, (user.id, text.id))
        assert progress.times_presented == 1

    def test_does_not_touch_translation_progress(self, db_session):
        """Explicit product decision: dictation is a fully separate track."""
        from app.modules.learning.models import UserTextProgress

        user = make_user(db_session)
        text = make_text(db_session)

        service.submit_dictation_answer(
            db_session,
            FakeEngine(),
            user,
            text_id=text.id,
            transcript=REFERENCE_TEXT,
            submission_id="sub-1",
        )

        assert db_session.get(UserTextProgress, (user.id, text.id)) is None
