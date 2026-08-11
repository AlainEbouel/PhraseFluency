import uuid

from sqlalchemy import select

from app.modules.evaluations.engine import EvaluationEngine, EvaluationEngineError
from app.modules.evaluations.enums import InputMethod, Verdict
from app.modules.evaluations.models import Attempt, Evaluation
from app.modules.evaluations.ports import EvaluationResult, ReferenceGenerationResult
from app.modules.learning import service
from app.modules.learning.enums import TextProgressStatus
from app.modules.learning.models import UserTextProgress
from app.modules.tests.models import Test, TestText
from app.modules.texts.models import Difficulty, ExerciseType, Text
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
            hints=["clue", "partial", "chunk"],
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
        result = self.evaluation_results[min(self.evaluate_calls - 1, len(self.evaluation_results) - 1)]
        return result

    def generate_grammar_explanation(self, request):
        raise NotImplementedError


def eval_result(verdict: Verdict, **overrides) -> EvaluationResult:
    defaults = dict(
        verdict=verdict,
        meaning_preserved=True,
        grammar_correct=True,
        natural_american_english=verdict == Verdict.CORRECT_NATURAL,
        writing_issues=[],
        corrected_answer=None,
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
    from app.modules.texts.models import TextVersion

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


class TestActiveBankBootstrap:
    def test_activates_up_to_target_when_texts_available(self, db_session):
        user = make_user(db_session)
        for _ in range(5):
            make_text(db_session)

        activated = service.activate_up_to_bank_target(db_session, user.id, target=3)

        assert activated == 3
        active = db_session.scalars(
            select(UserTextProgress).where(
                UserTextProgress.user_id == user.id, UserTextProgress.status == TextProgressStatus.ACTIVE
            )
        ).all()
        assert len(active) == 3

    def test_stops_when_no_unseen_text_left(self, db_session):
        user = make_user(db_session)
        make_text(db_session)

        activated = service.activate_up_to_bank_target(db_session, user.id, target=5)

        assert activated == 1

    def test_is_idempotent_when_already_at_target(self, db_session):
        user = make_user(db_session)
        for _ in range(3):
            make_text(db_session)
        service.activate_up_to_bank_target(db_session, user.id, target=3)

        activated_again = service.activate_up_to_bank_target(db_session, user.id, target=3)

        assert activated_again == 0


class TestGetNextExercise:
    def test_returns_none_when_no_texts_exist(self, db_session):
        user = make_user(db_session)
        assert service.get_next_exercise(db_session, user) is None

    def test_returns_an_active_text_and_resets_draft_on_switch(self, db_session):
        user = make_user(db_session)
        make_text(db_session)

        next_ex = service.get_next_exercise(db_session, user)

        assert next_ex is not None
        assert next_ex.progress.status == TextProgressStatus.ACTIVE
        assert next_ex.learning_state.current_text_id == next_ex.progress.text_id
        assert next_ex.learning_state.current_draft is None

    def test_due_review_takes_priority_over_normal_rotation(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        make_text(db_session)
        service.activate_up_to_bank_target(db_session, user.id, target=2)
        db_session.commit()

        rows = db_session.scalars(
            select(UserTextProgress).where(UserTextProgress.user_id == user.id)
        ).all()
        due_row, normal_row = rows[0], rows[1]
        due_row.next_review_at_exercise = 0  # already due
        db_session.add(due_row)
        db_session.commit()

        next_ex = service.get_next_exercise(db_session, user)

        assert next_ex.progress.text_id == due_row.text_id
        assert next_ex.is_review is True


class TestSubmitAnswer:
    def test_natural_answer_awards_two_points_and_stays_active_until_mastered(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])

        result = service.submit_answer(
            db_session,
            engine,
            user,
            text_id=next_ex.progress.text_id,
            user_answer="I haven't had a chance to look into it yet.",
            input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()),
        )

        assert result.points_awarded == 2
        assert result.progress.mastery_score == 2
        assert result.progress.status == TextProgressStatus.ACTIVE

    def test_three_natural_answers_masters_the_text(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        engine = FakeEngine(
            evaluation_results=[
                eval_result(Verdict.CORRECT_NATURAL),
                eval_result(Verdict.CORRECT_NATURAL),
                eval_result(Verdict.CORRECT_NATURAL),
            ]
        )

        result = None
        for _ in range(3):
            next_ex = service.get_next_exercise(db_session, user)
            result = service.submit_answer(
                db_session,
                engine,
                user,
                text_id=next_ex.progress.text_id,
                user_answer="I haven't had a chance to look into it yet.",
                input_method=InputMethod.KEYBOARD,
                submission_id=str(uuid.uuid4()),
            )

        assert result.progress.status == TextProgressStatus.MASTERED
        assert result.progress.perfect_learning_record is True

    def test_engine_failure_does_not_create_attempt_or_change_progress(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(fail=True)

        try:
            service.submit_answer(
                db_session,
                engine,
                user,
                text_id=next_ex.progress.text_id,
                user_answer="whatever",
                input_method=InputMethod.KEYBOARD,
                submission_id=str(uuid.uuid4()),
            )
            assert False, "expected EvaluationEngineError"
        except EvaluationEngineError:
            pass

        attempts = db_session.scalars(select(Attempt).where(Attempt.user_id == user.id)).all()
        assert attempts == []
        progress = db_session.get(UserTextProgress, (user.id, next_ex.progress.text_id))
        assert progress.mastery_score == 0
        assert progress.status == TextProgressStatus.ACTIVE

    def test_duplicate_submission_id_replays_without_double_scoring(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])
        submission_id = str(uuid.uuid4())

        first = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD, submission_id=submission_id,
        )
        second = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD, submission_id=submission_id,
        )

        assert first.evaluation.id == second.evaluation.id
        assert engine.evaluate_calls == 1
        progress = db_session.get(UserTextProgress, (user.id, next_ex.progress.text_id))
        assert progress.mastery_score == 2

    def test_incorrect_answer_schedules_review_after_20(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.INCORRECT)])

        result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="wrong", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
        )

        assert result.progress.next_review_at_exercise == 21  # sequence starts at 0, this is exercise #1

    def test_hint_used_caps_points_at_one_even_for_natural_verdict(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        text = db_session.get(Text, next_ex.progress.text_id)
        from app.modules.texts.models import TextVersion

        text_version = db_session.get(TextVersion, text.current_version_id)

        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])
        reference = None
        from app.modules.evaluations.service import get_or_create_reference

        reference = get_or_create_reference(db_session, engine, text_version)
        service.request_hint(db_session, next_ex.learning_state, reference)

        result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
        )

        assert result.points_awarded == 1

    def test_reaching_required_score_with_imperfect_record_creates_test_after_25(self, db_session):
        user = make_user(db_session)
        text_ids = [make_text(db_session).id for _ in range(25)]
        service.activate_up_to_bank_target(db_session, user.id, target=25)
        db_session.commit()
        engine = FakeEngine()

        # Directly targets each known text_id rather than going through
        # get_next_exercise, so this test doesn't depend on rotation order.
        for text_id in text_ids:
            # One unnatural then three naturals: 1+2+2+2=7 >= required_score(6),
            # imperfect record -> WAITING_FOR_TEST_ASSIGNMENT.
            engine.evaluation_results = [
                eval_result(Verdict.CORRECT_UNNATURAL),
                eval_result(Verdict.CORRECT_NATURAL),
                eval_result(Verdict.CORRECT_NATURAL),
                eval_result(Verdict.CORRECT_NATURAL),
            ]
            engine.evaluate_calls = 0
            for _ in range(4):
                service.submit_answer(
                    db_session, engine, user, text_id=text_id,
                    user_answer="answer", input_method=InputMethod.KEYBOARD,
                    submission_id=str(uuid.uuid4()),
                )

        tests = db_session.scalars(select(Test).where(Test.user_id == user.id)).all()
        assert len(tests) == 1
        test_texts = db_session.scalars(select(TestText).where(TestText.test_id == tests[0].id)).all()
        assert len(test_texts) == 25


class TestSkip:
    def test_skip_clears_current_text_without_scoring(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)

        service.skip_current(db_session, user.id, next_ex.learning_state)

        learning_state = service.get_or_create_learning_state(db_session, user.id)
        assert learning_state.current_text_id is None
        progress = db_session.get(UserTextProgress, (user.id, next_ex.progress.text_id))
        assert progress.mastery_score == 0
        assert progress.status == TextProgressStatus.ACTIVE


class TestRepetitionAndAcquisition:
    def test_increase_repetition_raises_targets(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)

        progress = service.increase_repetition_for_text(db_session, user.id, next_ex.progress.text_id)

        assert progress.required_natural_equivalents == 4
        assert progress.required_score == 8

    def test_manual_acquisition_does_not_count_as_correct_and_backfills_bank(self, db_session):
        user = make_user(db_session)
        for _ in range(2):
            make_text(db_session)
        service.activate_up_to_bank_target(db_session, user.id, target=1)
        db_session.commit()
        progress_row = db_session.scalars(
            select(UserTextProgress).where(UserTextProgress.user_id == user.id)
        ).one()

        updated = service.manually_acquire_text(db_session, user.id, progress_row.text_id)

        assert updated.status == TextProgressStatus.MANUALLY_ACQUIRED
        assert updated.manually_acquired is True
        assert updated.natural_count == 0

        # A reserve text existed, so the bank backfills the vacated slot.
        active = db_session.scalars(
            select(UserTextProgress).where(
                UserTextProgress.user_id == user.id, UserTextProgress.status == TextProgressStatus.ACTIVE
            )
        ).all()
        assert len(active) == 1
        assert active[0].text_id != progress_row.text_id


class TestReevaluate:
    def test_reevaluation_creates_new_evaluation_and_updates_active_pointer(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_UNNATURAL)])

        submit_result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
        )
        original_evaluation_id = submit_result.evaluation.id

        engine.evaluation_results = [eval_result(Verdict.CORRECT_NATURAL)]
        engine.evaluate_calls = 0
        new_evaluation = service.reevaluate_text(db_session, engine, user, next_ex.progress.text_id)

        assert new_evaluation.id != original_evaluation_id
        assert new_evaluation.verdict == Verdict.CORRECT_NATURAL
        assert new_evaluation.evaluation_number == 2

        old_evaluation = db_session.get(Evaluation, original_evaluation_id)
        assert old_evaluation is not None  # preserved for audit

        attempt = db_session.get(Attempt, submit_result.evaluation.attempt_id)
        assert attempt.active_evaluation_id == new_evaluation.id

    def test_reevaluation_does_not_retroactively_change_mastery_score(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.INCORRECT)])

        service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
        )
        score_after_submit = db_session.get(UserTextProgress, (user.id, next_ex.progress.text_id)).mastery_score

        engine.evaluation_results = [eval_result(Verdict.CORRECT_NATURAL)]
        engine.evaluate_calls = 0
        service.reevaluate_text(db_session, engine, user, next_ex.progress.text_id)

        score_after_reeval = db_session.get(UserTextProgress, (user.id, next_ex.progress.text_id)).mastery_score
        assert score_after_reeval == score_after_submit == 0
