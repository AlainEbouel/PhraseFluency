import uuid

from sqlalchemy import select

from app.modules.evaluations.engine import EvaluationEngine, EvaluationEngineError
from app.modules.evaluations.enums import InputMethod, Verdict
from app.modules.evaluations.models import Attempt
from app.modules.evaluations.ports import EvaluationResult, ReferenceGenerationResult
from app.modules.tests import service
from app.modules.tests.models import Test, TestAttemptStatus, TestText
from app.modules.texts.models import Difficulty, ExerciseType, Text, TextVersion
from app.modules.users.models import User, UserRole


class FakeEngine(EvaluationEngine):
    def __init__(self, evaluation_results=None, fail=False):
        self.evaluation_results = list(evaluation_results or [])
        self.fail = fail
        self.evaluate_calls = 0

    def generate_reference(self, request):
        return ReferenceGenerationResult(
            preferred_translation="I haven't had a chance to look into it yet.",
            alternatives=[],
            hints=["a", "b", "c"],
            patterns=[],
            model="gpt-4o-mini",
            prompt_version="reference-v1",
            input_tokens=1,
            output_tokens=1,
        )

    def evaluate(self, request):
        self.evaluate_calls += 1
        if self.fail:
            raise EvaluationEngineError("boom")
        return self.evaluation_results[min(self.evaluate_calls - 1, len(self.evaluation_results) - 1)]

    def generate_grammar_explanation(self, request):
        raise NotImplementedError

    def generate_weakness_suggestions(self, request):
        raise NotImplementedError


def eval_result(verdict: Verdict, **overrides) -> EvaluationResult:
    defaults = dict(
        verdict=verdict,
        meaning_preserved=True,
        grammar_correct=True,
        natural_american_english=verdict
        in (Verdict.CORRECT_NATURAL, Verdict.CORRECT_WITH_USAGE_NOTE),
        problematic_segment=None,
        writing_issues=[],
        corrected_answer=None,
        usage_note_alternative=None,
        feedback="feedback",
        error_categories=[],
        model="gpt-4o-mini",
        prompt_version="evaluation-v1",
        input_tokens=10,
        output_tokens=5,
    )
    defaults.update(overrides)
    return EvaluationResult(**defaults)


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


def make_test_with_texts(db_session, user, count=25):
    texts = [make_text(db_session) for _ in range(count)]
    test = Test(user_id=user.id, number=1)
    db_session.add(test)
    db_session.flush()
    for position, text in enumerate(texts):
        db_session.add(
            TestText(test_id=test.id, text_id=text.id, user_id=user.id, position=position)
        )
    db_session.flush()
    return test, texts


class TestListAndDetail:
    def test_list_shows_available_before_any_attempt(self, db_session):
        user = make_user(db_session)
        test, _ = make_test_with_texts(db_session, user, count=25)

        rows = service.list_tests_for_user(db_session, user.id)

        assert len(rows) == 1
        result_test, latest, mastered_count = rows[0]
        assert result_test.id == test.id
        assert latest is None
        assert mastered_count == 0

    def test_get_test_texts_ordered_by_position(self, db_session):
        user = make_user(db_session)
        test, texts = make_test_with_texts(db_session, user, count=3)

        test_texts = service.get_test_texts(db_session, test.id)

        assert [tt.text_id for tt in test_texts] == [t.id for t in texts]


class TestStartOrResumeAttempt:
    def test_first_start_creates_attempt_number_one(self, db_session):
        user = make_user(db_session)
        test, _ = make_test_with_texts(db_session, user, count=25)

        attempt, is_retake = service.start_or_resume_attempt(db_session, test)

        assert attempt.attempt_number == 1
        assert is_retake is False
        assert attempt.status == TestAttemptStatus.IN_PROGRESS

    def test_resumes_in_progress_attempt_without_creating_a_new_one(self, db_session):
        user = make_user(db_session)
        test, _ = make_test_with_texts(db_session, user, count=25)
        first, _ = service.start_or_resume_attempt(db_session, test)

        second, is_retake = service.start_or_resume_attempt(db_session, test)

        assert second.id == first.id
        assert is_retake is False

    def test_retake_after_completion_creates_new_attempt_and_resets_progress(self, db_session):
        user = make_user(db_session)
        test, texts = make_test_with_texts(db_session, user, count=25)
        attempt, _ = service.start_or_resume_attempt(db_session, test)

        test_text = db_session.get(TestText, (test.id, texts[0].id))
        test_text.consecutive_successes = 2
        test_text.mastered_at = attempt.started_at
        db_session.add(test_text)
        attempt.status = TestAttemptStatus.COMPLETED
        db_session.add(attempt)
        db_session.commit()

        retake, is_retake = service.start_or_resume_attempt(db_session, test)

        assert retake.attempt_number == 2
        assert is_retake is True
        refreshed = db_session.get(TestText, (test.id, texts[0].id))
        assert refreshed.consecutive_successes == 0
        assert refreshed.mastered_at is None


class TestSubmitTestAnswer:
    def test_two_consecutive_natural_masters_the_text(self, db_session):
        user = make_user(db_session)
        test, texts = make_test_with_texts(db_session, user, count=25)
        service.start_or_resume_attempt(db_session, test)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])

        r1 = service.submit_test_answer(
            db_session, engine, user, test=test, text_id=texts[0].id,
            user_answer="a", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
        )
        assert r1.mastered is False
        assert r1.consecutive_successes == 1

        r2 = service.submit_test_answer(
            db_session, engine, user, test=test, text_id=texts[0].id,
            user_answer="a", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
        )
        assert r2.mastered is True
        assert r2.consecutive_successes == 2

    def test_unnatural_does_not_count_and_resets(self, db_session):
        user = make_user(db_session)
        test, texts = make_test_with_texts(db_session, user, count=25)
        service.start_or_resume_attempt(db_session, test)
        engine = FakeEngine(
            evaluation_results=[eval_result(Verdict.CORRECT_NATURAL), eval_result(Verdict.CORRECT_UNNATURAL)]
        )

        service.submit_test_answer(
            db_session, engine, user, test=test, text_id=texts[0].id,
            user_answer="a", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
        )
        r2 = service.submit_test_answer(
            db_session, engine, user, test=test, text_id=texts[0].id,
            user_answer="a", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
        )

        assert r2.consecutive_successes == 0
        assert r2.mastered is False

    def test_all_25_mastered_completes_the_attempt(self, db_session):
        user = make_user(db_session)
        test, texts = make_test_with_texts(db_session, user, count=25)
        service.start_or_resume_attempt(db_session, test)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])

        result = None
        for text in texts:
            for _ in range(2):
                engine.evaluate_calls = 0
                result = service.submit_test_answer(
                    db_session, engine, user, test=test, text_id=text.id,
                    user_answer="a", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
                )

        assert result.test_completed is True
        attempt = service.get_test_attempts(db_session, test.id)[0]
        assert attempt.status == TestAttemptStatus.COMPLETED
        assert attempt.completed_at is not None

    def test_duplicate_submission_id_replays_without_double_counting(self, db_session):
        user = make_user(db_session)
        test, texts = make_test_with_texts(db_session, user, count=25)
        service.start_or_resume_attempt(db_session, test)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])
        submission_id = str(uuid.uuid4())

        first = service.submit_test_answer(
            db_session, engine, user, test=test, text_id=texts[0].id,
            user_answer="a", input_method=InputMethod.KEYBOARD, submission_id=submission_id,
        )
        second = service.submit_test_answer(
            db_session, engine, user, test=test, text_id=texts[0].id,
            user_answer="a", input_method=InputMethod.KEYBOARD, submission_id=submission_id,
        )

        assert first.evaluation.id == second.evaluation.id
        assert engine.evaluate_calls == 1

    def test_duplicate_submission_id_does_not_leak_across_users(self, db_session):
        user_a = make_user(db_session)
        test_a, texts_a = make_test_with_texts(db_session, user_a, count=25)
        service.start_or_resume_attempt(db_session, test_a)
        user_b = make_user(db_session)
        test_b, texts_b = make_test_with_texts(db_session, user_b, count=25)
        service.start_or_resume_attempt(db_session, test_b)
        engine = FakeEngine(
            evaluation_results=[eval_result(Verdict.CORRECT_NATURAL), eval_result(Verdict.INCORRECT)]
        )
        submission_id = str(uuid.uuid4())

        result_a = service.submit_test_answer(
            db_session, engine, user_a, test=test_a, text_id=texts_a[0].id,
            user_answer="a", input_method=InputMethod.KEYBOARD, submission_id=submission_id,
        )
        result_b = service.submit_test_answer(
            db_session, engine, user_b, test=test_b, text_id=texts_b[0].id,
            user_answer="b", input_method=InputMethod.KEYBOARD, submission_id=submission_id,
        )

        assert result_a.evaluation.id != result_b.evaluation.id
        assert engine.evaluate_calls == 2
        assert result_a.evaluation.verdict == Verdict.CORRECT_NATURAL
        assert result_b.evaluation.verdict == Verdict.INCORRECT

    def test_submitting_without_in_progress_attempt_raises(self, db_session):
        user = make_user(db_session)
        test, texts = make_test_with_texts(db_session, user, count=25)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])

        try:
            service.submit_test_answer(
                db_session, engine, user, test=test, text_id=texts[0].id,
                user_answer="a", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
            )
            assert False, "expected ValueError"
        except ValueError:
            pass

    def test_engine_failure_does_not_create_attempt(self, db_session):
        user = make_user(db_session)
        test, texts = make_test_with_texts(db_session, user, count=25)
        service.start_or_resume_attempt(db_session, test)
        engine = FakeEngine(fail=True)

        try:
            service.submit_test_answer(
                db_session, engine, user, test=test, text_id=texts[0].id,
                user_answer="a", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
            )
            assert False, "expected EvaluationEngineError"
        except EvaluationEngineError:
            pass

        attempts = db_session.scalars(select(Attempt).where(Attempt.user_id == user.id)).all()
        assert attempts == []
