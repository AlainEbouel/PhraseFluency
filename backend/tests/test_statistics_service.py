import uuid
from datetime import timedelta

from app.modules.evaluations.enums import AttemptMode, InputMethod, Verdict
from app.modules.evaluations.models import Attempt, Evaluation
from app.modules.learning.enums import TextProgressStatus
from app.modules.learning.models import UserTextProgress
from app.modules.statistics import service
from app.modules.tests.models import Test, TestAttempt, TestAttemptStatus, TestText
from app.modules.texts.models import Difficulty, ExerciseType, Text, TextVersion
from app.modules.texts.service import get_or_create_pattern
from app.modules.users.models import User, UserRole
from app.shared.mixins import utcnow
from app.shared.models import AIOperation, AIUsage


def make_user(db_session) -> User:
    user = User(email=f"{uuid.uuid4()}@phrasefluency.app", password_hash="x", role=UserRole.USER)
    db_session.add(user)
    db_session.flush()
    return user


def make_text_version(db_session, difficulty=Difficulty.B2, contexts=None) -> TextVersion:
    text = Text(source="test")
    db_session.add(text)
    db_session.flush()
    version = TextVersion(
        text_id=text.id,
        french_text=f"Texte {uuid.uuid4()}",
        exercise_type=ExerciseType.TRANSLATION,
        difficulty=difficulty,
        contexts=contexts or [],
    )
    db_session.add(version)
    db_session.flush()
    text.current_version_id = version.id
    db_session.add(text)
    db_session.flush()
    return version


def make_progress(db_session, user, text_version, **overrides) -> UserTextProgress:
    defaults = dict(
        user_id=user.id,
        text_id=text_version.text_id,
        status=TextProgressStatus.ACTIVE,
    )
    defaults.update(overrides)
    progress = UserTextProgress(**defaults)
    db_session.add(progress)
    db_session.flush()
    return progress


def make_attempt(
    db_session,
    user,
    text_version,
    verdict,
    *,
    input_method=InputMethod.KEYBOARD,
    hint_used=False,
    error_categories=None,
    created_at=None,
    mode=AttemptMode.LEARNING,
):
    attempt = Attempt(
        user_id=user.id,
        text_version_id=text_version.id,
        mode=mode,
        sequence_number=1,
        user_answer="answer",
        input_method=input_method,
        hint_used=hint_used,
        max_hint_level=1 if hint_used else 0,
        submission_id=str(uuid.uuid4()),
    )
    if created_at is not None:
        attempt.created_at = created_at
    db_session.add(attempt)
    db_session.flush()

    evaluation = Evaluation(
        attempt_id=attempt.id,
        evaluation_number=1,
        verdict=verdict,
        meaning_preserved=True,
        grammar_correct=True,
        natural_american_english=verdict == Verdict.CORRECT_NATURAL,
        writing_issues=[],
        corrected_answer=None,
        feedback="feedback",
        error_categories=error_categories or [],
        model="gpt-4o-mini",
        prompt_version="evaluation-v1",
    )
    db_session.add(evaluation)
    db_session.flush()

    attempt.active_evaluation_id = evaluation.id
    db_session.add(attempt)
    db_session.flush()
    return attempt, evaluation


class TestDashboard:
    def test_counts_texts_by_status(self, db_session):
        user = make_user(db_session)
        make_progress(db_session, user, make_text_version(db_session), status=TextProgressStatus.MASTERED)
        make_progress(db_session, user, make_text_version(db_session), status=TextProgressStatus.ACTIVE)
        make_progress(db_session, user, make_text_version(db_session), status=TextProgressStatus.ACTIVE)
        make_progress(
            db_session, user, make_text_version(db_session),
            status=TextProgressStatus.WAITING_FOR_TEST_ASSIGNMENT,
        )

        dashboard = service.get_dashboard(db_session, user.id)

        assert dashboard["mastered_count"] == 1
        assert dashboard["active_count"] == 2
        assert dashboard["waiting_for_test_count"] == 1
        assert dashboard["active_target"] == 100

    def test_natural_and_success_rates(self, db_session):
        user = make_user(db_session)
        make_attempt(db_session, user, make_text_version(db_session), Verdict.CORRECT_NATURAL)
        make_attempt(db_session, user, make_text_version(db_session), Verdict.CORRECT_UNNATURAL)
        make_attempt(db_session, user, make_text_version(db_session), Verdict.INCORRECT)

        dashboard = service.get_dashboard(db_session, user.id)

        assert dashboard["natural_answer_rate"] == 1 / 3
        assert dashboard["overall_success_rate"] == 2 / 3

    def test_test_status_breakdown(self, db_session):
        user = make_user(db_session)
        text_versions = [make_text_version(db_session) for _ in range(25)]
        test = Test(user_id=user.id, number=1)
        db_session.add(test)
        db_session.flush()
        for i, tv in enumerate(text_versions):
            db_session.add(TestText(test_id=test.id, text_id=tv.text_id, user_id=user.id, position=i))
        db_session.add(TestAttempt(test_id=test.id, attempt_number=1, status=TestAttemptStatus.COMPLETED, started_at=utcnow(), completed_at=utcnow()))
        db_session.commit()

        dashboard = service.get_dashboard(db_session, user.id)

        assert dashboard["tests_completed"] == 1
        assert dashboard["tests_available"] == 0
        assert dashboard["tests_in_progress"] == 0


class TestDetailedStatistics:
    def test_verdict_counts(self, db_session):
        user = make_user(db_session)
        make_attempt(db_session, user, make_text_version(db_session), Verdict.CORRECT_NATURAL)
        make_attempt(db_session, user, make_text_version(db_session), Verdict.CORRECT_NATURAL)
        make_attempt(db_session, user, make_text_version(db_session), Verdict.INCORRECT)

        stats = service.get_detailed_statistics(db_session, user.id)

        counts = {row["verdict"]: row["count"] for row in stats["verdict_counts"]}
        assert counts["CORRECT_NATURAL"] == 2
        assert counts["INCORRECT"] == 1

    def test_trend_windows_exclude_old_attempts(self, db_session):
        user = make_user(db_session)
        make_attempt(
            db_session, user, make_text_version(db_session), Verdict.CORRECT_NATURAL,
            created_at=utcnow() - timedelta(days=40),
        )
        make_attempt(
            db_session, user, make_text_version(db_session), Verdict.CORRECT_NATURAL,
            created_at=utcnow() - timedelta(days=1),
        )

        stats = service.get_detailed_statistics(db_session, user.id)

        assert stats["trend_7d"]["attempts_count"] == 1
        assert stats["trend_30d"]["attempts_count"] == 1
        assert stats["trend_all_time"]["attempts_count"] == 2

    def test_hardest_texts_ordered_by_incorrect_count(self, db_session):
        user = make_user(db_session)
        easy = make_text_version(db_session)
        hard = make_text_version(db_session)
        make_progress(db_session, user, easy, incorrect_count=1, times_presented=3)
        make_progress(db_session, user, hard, incorrect_count=5, times_presented=6)

        stats = service.get_detailed_statistics(db_session, user.id)

        assert stats["hardest_texts"][0]["text_id"] == hard.text_id
        assert stats["hardest_texts"][0]["incorrect_count"] == 5

    def test_avg_attempts_before_mastery(self, db_session):
        user = make_user(db_session)
        make_progress(db_session, user, make_text_version(db_session), status=TextProgressStatus.MASTERED, times_presented=3)
        make_progress(db_session, user, make_text_version(db_session), status=TextProgressStatus.MASTERED, times_presented=5)
        make_progress(db_session, user, make_text_version(db_session), status=TextProgressStatus.ACTIVE, times_presented=100)

        stats = service.get_detailed_statistics(db_session, user.id)

        assert stats["avg_attempts_before_mastery"] == 4.0

    def test_hint_usage_rate(self, db_session):
        user = make_user(db_session)
        make_progress(db_session, user, make_text_version(db_session), hint_count=1, times_presented=4)
        make_progress(db_session, user, make_text_version(db_session), hint_count=0, times_presented=6)

        stats = service.get_detailed_statistics(db_session, user.id)

        assert stats["hint_usage_rate"] == 1 / 10

    def test_writing_issue_count_summed(self, db_session):
        user = make_user(db_session)
        make_progress(db_session, user, make_text_version(db_session), writing_issue_count=2)
        make_progress(db_session, user, make_text_version(db_session), writing_issue_count=3)

        stats = service.get_detailed_statistics(db_session, user.id)

        assert stats["writing_issue_count"] == 5

    def test_input_method_counts(self, db_session):
        user = make_user(db_session)
        make_attempt(db_session, user, make_text_version(db_session), Verdict.CORRECT_NATURAL, input_method=InputMethod.VOICE)
        make_attempt(db_session, user, make_text_version(db_session), Verdict.CORRECT_NATURAL, input_method=InputMethod.KEYBOARD)
        make_attempt(db_session, user, make_text_version(db_session), Verdict.CORRECT_NATURAL, input_method=InputMethod.KEYBOARD)

        stats = service.get_detailed_statistics(db_session, user.id)

        counts = {row["input_method"]: row["count"] for row in stats["input_method_counts"]}
        assert counts["VOICE"] == 1
        assert counts["KEYBOARD"] == 2

    def test_reevaluation_detects_verdict_change(self, db_session):
        user = make_user(db_session)
        text_version = make_text_version(db_session)
        attempt, first_eval = make_attempt(db_session, user, text_version, Verdict.CORRECT_UNNATURAL)

        second_eval = Evaluation(
            attempt_id=attempt.id, evaluation_number=2, verdict=Verdict.CORRECT_NATURAL,
            meaning_preserved=True, grammar_correct=True, natural_american_english=True,
            writing_issues=[], corrected_answer=None, feedback="f", error_categories=[],
            model="m", prompt_version="v",
        )
        db_session.add(second_eval)
        db_session.flush()
        attempt.active_evaluation_id = second_eval.id
        db_session.add(attempt)
        db_session.commit()

        stats = service.get_detailed_statistics(db_session, user.id)

        assert stats["reevaluation"]["total_reevaluated"] == 1
        assert stats["reevaluation"]["verdict_changed_count"] == 1

    def test_error_category_counts(self, db_session):
        user = make_user(db_session)
        make_attempt(
            db_session, user, make_text_version(db_session), Verdict.INCORRECT,
            error_categories=["VERB_TENSE", "PREPOSITIONS"],
        )
        make_attempt(
            db_session, user, make_text_version(db_session), Verdict.INCORRECT,
            error_categories=["VERB_TENSE"],
        )

        stats = service.get_detailed_statistics(db_session, user.id)

        counts = {row["category"]: row["count"] for row in stats["error_category_counts"]}
        assert counts["VERB_TENSE"] == 2
        assert counts["PREPOSITIONS"] == 1

    def test_performance_by_difficulty(self, db_session):
        user = make_user(db_session)
        make_attempt(db_session, user, make_text_version(db_session, difficulty=Difficulty.B1), Verdict.CORRECT_NATURAL)
        make_attempt(db_session, user, make_text_version(db_session, difficulty=Difficulty.C1), Verdict.INCORRECT)

        stats = service.get_detailed_statistics(db_session, user.id)

        by_difficulty = {row["difficulty"]: row for row in stats["performance_by_difficulty"]}
        assert by_difficulty["B1"]["natural_rate"] == 1.0
        assert by_difficulty["C1"]["natural_rate"] == 0.0

    def test_performance_by_context(self, db_session):
        user = make_user(db_session)
        make_attempt(
            db_session, user, make_text_version(db_session, contexts=["professional"]),
            Verdict.CORRECT_NATURAL,
        )

        stats = service.get_detailed_statistics(db_session, user.id)

        by_context = {row["context"]: row for row in stats["performance_by_context"]}
        assert by_context["professional"]["attempts_count"] == 1

    def test_patterns_encountered_count(self, db_session):
        user = make_user(db_session)
        text_version = make_text_version(db_session)
        get_or_create_pattern(
            db_session, expression="I haven't had a chance to...", meaning="m", example="e",
            text_version=text_version,
        )
        make_attempt(db_session, user, text_version, Verdict.CORRECT_NATURAL)

        stats = service.get_detailed_statistics(db_session, user.id)

        assert stats["patterns_encountered_count"] == 1

    def test_test_performance_aggregates_across_attempts(self, db_session):
        user = make_user(db_session)
        test = Test(user_id=user.id, number=1)
        db_session.add(test)
        db_session.flush()
        db_session.add(TestAttempt(
            test_id=test.id, attempt_number=1, status=TestAttemptStatus.COMPLETED,
            started_at=utcnow(), completed_at=utcnow(), correct_count=25, incorrect_count=3,
        ))
        db_session.add(TestAttempt(
            test_id=test.id, attempt_number=2, status=TestAttemptStatus.IN_PROGRESS,
            started_at=utcnow(), correct_count=5, incorrect_count=1,
        ))
        db_session.commit()

        stats = service.get_detailed_statistics(db_session, user.id)

        assert stats["test_performance"]["tests_completed"] == 1
        assert stats["test_performance"]["total_correct"] == 30
        assert stats["test_performance"]["total_incorrect"] == 4
        assert stats["test_performance"]["retakes_count"] == 1

    def test_ai_usage_summary(self, db_session):
        user = make_user(db_session)
        db_session.add(AIUsage(
            user_id=user.id, operation=AIOperation.EVALUATION, model="gpt-4o-mini",
            input_tokens=100, output_tokens=50, estimated_cost=0.001,
        ))
        db_session.add(AIUsage(
            user_id=user.id, operation=AIOperation.EVALUATION, model="gpt-4o-mini",
            input_tokens=200, output_tokens=60, estimated_cost=0.002,
        ))
        db_session.commit()

        stats = service.get_detailed_statistics(db_session, user.id)

        row = next(r for r in stats["ai_usage"] if r["operation"] == "EVALUATION")
        assert row["count"] == 2
        assert row["input_tokens"] == 300
        assert abs(row["estimated_cost"] - 0.003) < 1e-9

    def test_stats_are_scoped_to_the_requesting_user(self, db_session):
        user_a = make_user(db_session)
        user_b = make_user(db_session)
        make_attempt(db_session, user_a, make_text_version(db_session), Verdict.CORRECT_NATURAL)
        make_attempt(db_session, user_b, make_text_version(db_session), Verdict.INCORRECT)

        stats_a = service.get_detailed_statistics(db_session, user_a.id)

        assert stats_a["trend_all_time"]["attempts_count"] == 1
        assert stats_a["trend_all_time"]["natural_rate"] == 1.0
