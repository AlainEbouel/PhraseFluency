import uuid
from datetime import timedelta

from app.modules.evaluations.engine import EvaluationEngine
from app.modules.evaluations.enums import AttemptMode, InputMethod, Verdict
from app.modules.evaluations.models import Attempt, Evaluation
from app.modules.evaluations.ports import WeaknessSuggestion, WeaknessSuggestionsResult
from app.modules.learning.enums import TextProgressStatus
from app.modules.learning.models import UserTextProgress
from app.modules.statistics import service
from app.modules.statistics.models import UserWeaknessProfile
from app.modules.tests.models import Test, TestAttempt, TestAttemptStatus, TestText
from app.modules.texts.models import Difficulty, ExerciseType, Text, TextVersion
from app.modules.texts.service import get_or_create_pattern
from app.modules.users.models import User, UserRole
from app.shared.mixins import utcnow
from app.shared.models import AIOperation, AIUsage


class FakeEngine(EvaluationEngine):
    def __init__(self, weakness_suggestions_result=None):
        self.weakness_suggestions_result = weakness_suggestions_result
        self.weakness_suggestions_calls = 0
        self.last_request = None

    def generate_reference(self, request):
        raise NotImplementedError

    def evaluate(self, request):
        raise NotImplementedError

    def generate_grammar_explanation(self, request):
        raise NotImplementedError

    def generate_weakness_suggestions(self, request):
        self.weakness_suggestions_calls += 1
        self.last_request = request
        return self.weakness_suggestions_result


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
        natural_american_english=verdict in (Verdict.CORRECT_NATURAL, Verdict.CORRECT_WITH_USAGE_NOTE),
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

    def test_usage_note_counts_as_natural_like_correct_natural(self, db_session):
        user = make_user(db_session)
        make_attempt(db_session, user, make_text_version(db_session), Verdict.CORRECT_WITH_USAGE_NOTE)
        make_attempt(db_session, user, make_text_version(db_session), Verdict.CORRECT_UNNATURAL)

        dashboard = service.get_dashboard(db_session, user.id)

        assert dashboard["natural_answer_rate"] == 1 / 2

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


class TestTopErrorCategories:
    def test_ranks_by_count_descending(self, db_session):
        user = make_user(db_session)
        make_attempt(
            db_session, user, make_text_version(db_session), Verdict.INCORRECT,
            error_categories=["WORD_ORDER"],
        )
        make_attempt(
            db_session, user, make_text_version(db_session), Verdict.INCORRECT,
            error_categories=["WORD_ORDER", "REGISTER"],
        )
        make_attempt(
            db_session, user, make_text_version(db_session), Verdict.INCORRECT,
            error_categories=["WORD_ORDER"],
        )

        top = service.top_error_categories(db_session, user.id)

        assert top[0] == {"category": "WORD_ORDER", "count": 3}
        assert top[1] == {"category": "REGISTER", "count": 1}

    def test_respects_the_limit(self, db_session):
        user = make_user(db_session)
        for category in ["WORD_ORDER", "REGISTER", "VERB_TENSE", "PREPOSITIONS"]:
            make_attempt(
                db_session, user, make_text_version(db_session), Verdict.INCORRECT,
                error_categories=[category],
            )

        top = service.top_error_categories(db_session, user.id, limit=2)

        assert len(top) == 2

    def test_no_tagged_evaluations_returns_empty(self, db_session):
        user = make_user(db_session)
        make_attempt(db_session, user, make_text_version(db_session), Verdict.CORRECT_NATURAL)

        assert service.top_error_categories(db_session, user.id) == []

    def test_scoped_to_the_requesting_user(self, db_session):
        user_a = make_user(db_session)
        user_b = make_user(db_session)
        make_attempt(
            db_session, user_a, make_text_version(db_session), Verdict.INCORRECT,
            error_categories=["WORD_ORDER"],
        )
        make_attempt(
            db_session, user_b, make_text_version(db_session), Verdict.INCORRECT,
            error_categories=["REGISTER"],
        )

        top = service.top_error_categories(db_session, user_a.id)

        assert top == [{"category": "WORD_ORDER", "count": 1}]


class TestGetOrGenerateWeaknessProfile:
    def test_insufficient_data_skips_the_llm_call(self, db_session):
        user = make_user(db_session)
        make_attempt(db_session, user, make_text_version(db_session), Verdict.CORRECT_NATURAL)
        engine = FakeEngine()

        profile = service.get_or_generate_weakness_profile(db_session, engine, user)

        assert profile == {"has_enough_data": False, "weaknesses": [], "suggestions": []}
        assert engine.weakness_suggestions_calls == 0

    def test_generates_and_caches_suggestions(self, db_session):
        user = make_user(db_session)
        make_attempt(
            db_session, user, make_text_version(db_session), Verdict.INCORRECT,
            error_categories=["WORD_ORDER"],
        )
        engine = FakeEngine(
            weakness_suggestions_result=WeaknessSuggestionsResult(
                suggestions=[
                    WeaknessSuggestion(
                        category="WORD_ORDER", explanation="...", suggestion="..."
                    )
                ],
                model="gpt-4o-mini",
                prompt_version="weakness-v1",
                input_tokens=10,
                output_tokens=5,
            )
        )

        profile = service.get_or_generate_weakness_profile(db_session, engine, user)

        assert profile["has_enough_data"] is True
        assert profile["weaknesses"] == [{"category": "WORD_ORDER", "count": 1}]
        assert profile["suggestions"] == [
            {"category": "WORD_ORDER", "explanation": "...", "suggestion": "..."}
        ]
        assert engine.weakness_suggestions_calls == 1
        cached = db_session.get(UserWeaknessProfile, user.id)
        assert cached is not None
        assert cached.category_fingerprint == "WORD_ORDER"

    def test_cache_hit_when_ranking_is_unchanged(self, db_session):
        user = make_user(db_session)
        make_attempt(
            db_session, user, make_text_version(db_session), Verdict.INCORRECT,
            error_categories=["WORD_ORDER"],
        )
        engine = FakeEngine(
            weakness_suggestions_result=WeaknessSuggestionsResult(
                suggestions=[WeaknessSuggestion("WORD_ORDER", "e1", "s1")],
                model="gpt-4o-mini", prompt_version="weakness-v1",
                input_tokens=10, output_tokens=5,
            )
        )
        service.get_or_generate_weakness_profile(db_session, engine, user)

        # A second, otherwise-identical-ranking attempt shouldn't change
        # the fingerprint (still just WORD_ORDER as the sole category).
        make_attempt(
            db_session, user, make_text_version(db_session), Verdict.INCORRECT,
            error_categories=["WORD_ORDER"],
        )
        profile = service.get_or_generate_weakness_profile(db_session, engine, user)

        assert engine.weakness_suggestions_calls == 1  # not called again
        assert profile["suggestions"] == [
            {"category": "WORD_ORDER", "explanation": "e1", "suggestion": "s1"}
        ]

    def test_regenerates_when_the_top_categories_change(self, db_session):
        user = make_user(db_session)
        make_attempt(
            db_session, user, make_text_version(db_session), Verdict.INCORRECT,
            error_categories=["WORD_ORDER"],
        )
        engine = FakeEngine(
            weakness_suggestions_result=WeaknessSuggestionsResult(
                suggestions=[WeaknessSuggestion("WORD_ORDER", "e1", "s1")],
                model="gpt-4o-mini", prompt_version="weakness-v1",
                input_tokens=10, output_tokens=5,
            )
        )
        service.get_or_generate_weakness_profile(db_session, engine, user)

        # A brand new category takes over as the (sole) top category.
        for _ in range(5):
            make_attempt(
                db_session, user, make_text_version(db_session), Verdict.INCORRECT,
                error_categories=["REGISTER"],
            )
        engine.weakness_suggestions_result = WeaknessSuggestionsResult(
            suggestions=[
                WeaknessSuggestion("REGISTER", "e2", "s2"),
                WeaknessSuggestion("WORD_ORDER", "e1b", "s1b"),
            ],
            model="gpt-4o-mini", prompt_version="weakness-v1",
            input_tokens=10, output_tokens=5,
        )

        profile = service.get_or_generate_weakness_profile(db_session, engine, user)

        assert engine.weakness_suggestions_calls == 2
        assert {s["category"] for s in profile["suggestions"]} == {"REGISTER", "WORD_ORDER"}

    def test_grounds_the_request_in_recent_feedback_for_each_category(self, db_session):
        user = make_user(db_session)
        make_attempt(
            db_session, user, make_text_version(db_session), Verdict.INCORRECT,
            error_categories=["WORD_ORDER"],
        )
        engine = FakeEngine(
            weakness_suggestions_result=WeaknessSuggestionsResult(
                suggestions=[WeaknessSuggestion("WORD_ORDER", "e", "s")],
                model="gpt-4o-mini", prompt_version="weakness-v1",
                input_tokens=10, output_tokens=5,
            )
        )

        service.get_or_generate_weakness_profile(db_session, engine, user)

        assert engine.last_request.categories[0].category == "WORD_ORDER"
        assert engine.last_request.categories[0].example_feedback == ["feedback"]
