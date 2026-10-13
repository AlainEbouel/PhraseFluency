import uuid

import pytest
from sqlalchemy import func, select

from app.modules.evaluations.engine import EvaluationEngine, EvaluationEngineError
from app.modules.evaluations.enums import InputMethod, Verdict
from app.modules.evaluations.models import Attempt, Evaluation
from app.modules.evaluations.ports import (
    EvaluationResult,
    ReferenceGenerationResult,
    SourceTextAssessmentResult,
)
from app.modules.learning import service
from app.modules.learning.enums import TextProgressStatus
from app.modules.learning.models import UserTextProgress
from app.modules.tests.models import Test, TestText
from app.modules.texts.models import Difficulty, ExerciseType, Text, TextVersion
from app.modules.users.models import User, UserRole


class FakeEngine(EvaluationEngine):
    def __init__(self, evaluation_results=None, fail=False, assessment_result=None):
        self.evaluation_results = list(evaluation_results or [])
        self.fail = fail
        self.evaluate_calls = 0
        self.assessment_result = assessment_result
        self.assess_source_text_calls = 0

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

    def generate_weakness_suggestions(self, request):
        raise NotImplementedError

    def assess_source_text(self, request):
        self.assess_source_text_calls += 1
        return self.assessment_result


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
    # All texts made by make_text() below default to B2, so choosing B2
    # here keeps existing activation tests exercising realistic content.
    service.choose_level(db_session, user.id, Difficulty.B2)
    return user


def make_user_without_level(db_session) -> User:
    user = User(email=f"{uuid.uuid4()}@phrasefluency.app", password_hash="x", role=UserRole.USER)
    db_session.add(user)
    db_session.flush()
    return user


def make_text(db_session, french_text=None, difficulty=Difficulty.B2) -> Text:
    text = Text(source="test")
    db_session.add(text)
    db_session.flush()
    version = TextVersion(
        text_id=text.id,
        french_text=french_text or f"Texte {uuid.uuid4()}",
        exercise_type=ExerciseType.TRANSLATION,
        difficulty=difficulty,
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


class TestLevelSelection:
    def test_nothing_activates_before_a_level_is_chosen(self, db_session):
        user = make_user_without_level(db_session)
        make_text(db_session)

        activated = service.activate_up_to_bank_target(db_session, user.id, target=5)

        assert activated == 0

    def test_get_next_exercise_returns_none_before_a_level_is_chosen(self, db_session):
        user = make_user_without_level(db_session)
        make_text(db_session)

        assert service.get_next_exercise(db_session, user) is None

    def test_choosing_a_level_immediately_fills_the_bank(self, db_session):
        user = make_user_without_level(db_session)
        for _ in range(5):
            make_text(db_session, difficulty=Difficulty.B2)

        service.choose_level(db_session, user.id, Difficulty.B2)

        active = db_session.scalars(
            select(UserTextProgress).where(
                UserTextProgress.user_id == user.id, UserTextProgress.status == TextProgressStatus.ACTIVE
            )
        ).all()
        assert len(active) == 5

    def test_bulk_fill_respects_the_tier_ratio_when_supply_is_ample(self, db_session):
        user = make_user_without_level(db_session)
        for _ in range(20):
            make_text(db_session, difficulty=Difficulty.B1)
        for _ in range(20):
            make_text(db_session, difficulty=Difficulty.B2)
        learning_state = service.get_or_create_learning_state(db_session, user.id)
        learning_state.current_level = Difficulty.B1
        learning_state.target_level = Difficulty.B2
        db_session.commit()

        activated = service.activate_up_to_bank_target(db_session, user.id, target=20)

        assert activated == 20
        counts = _active_counts_by_difficulty(db_session, user.id)
        # tier_weights(B1, B2) = {B1: 0.25, B2: 0.75} of 20 slots.
        assert counts == {Difficulty.B1: 5, Difficulty.B2: 15}

    def test_a_dry_tier_falls_back_to_the_other_weighted_tiers(self, db_session):
        user = make_user_without_level(db_session)
        for _ in range(10):
            make_text(db_session, difficulty=Difficulty.B2)
        # No C2 texts at all: tier_weights(B2, C2) = {B2: 0.25, C2: 0.75},
        # so every time C2 is prioritized it must fall through to B2 —
        # target stays within B2's own supply so it never needs the
        # whole-corpus fallback either.
        learning_state = service.get_or_create_learning_state(db_session, user.id)
        learning_state.current_level = Difficulty.B2
        learning_state.target_level = Difficulty.C2
        db_session.commit()

        activated = service.activate_up_to_bank_target(db_session, user.id, target=10)

        assert activated == 10
        counts = _active_counts_by_difficulty(db_session, user.id)
        assert counts == {Difficulty.B2: 10}

    def test_exhausting_all_weighted_tiers_falls_back_to_the_whole_corpus(self, db_session):
        user = make_user_without_level(db_session)
        make_text(db_session, difficulty=Difficulty.A1)  # not one of B2/C1's weighted tiers
        learning_state = service.get_or_create_learning_state(db_session, user.id)
        learning_state.current_level = Difficulty.B2
        learning_state.target_level = Difficulty.C1
        db_session.commit()

        activated = service.activate_up_to_bank_target(db_session, user.id, target=5)

        assert activated == 1
        counts = _active_counts_by_difficulty(db_session, user.id)
        assert counts == {Difficulty.A1: 1}

    def test_replenishment_prefers_the_most_deficient_tier(self, db_session):
        user = make_user_without_level(db_session)
        for _ in range(10):
            make_text(db_session, difficulty=Difficulty.B2)
        for _ in range(10):
            make_text(db_session, difficulty=Difficulty.C1)
        learning_state = service.get_or_create_learning_state(db_session, user.id)
        learning_state.current_level = Difficulty.B2
        learning_state.target_level = Difficulty.C1
        db_session.commit()
        service.activate_up_to_bank_target(db_session, user.id, target=8)
        counts_before = _active_counts_by_difficulty(db_session, user.id)
        assert counts_before == {Difficulty.C1: 6, Difficulty.B2: 2}

        # Free one C1 slot directly (bypassing manually_acquire_text's own
        # default-100 top-up) to isolate exactly one replacement pick.
        one_active_c1 = db_session.scalar(
            select(UserTextProgress)
            .join(Text, Text.id == UserTextProgress.text_id)
            .join(TextVersion, TextVersion.id == Text.current_version_id)
            .where(
                UserTextProgress.user_id == user.id,
                UserTextProgress.status == TextProgressStatus.ACTIVE,
                TextVersion.difficulty == Difficulty.C1,
            )
            .limit(1)
        )
        one_active_c1.status = TextProgressStatus.MASTERED
        db_session.add(one_active_c1)
        db_session.commit()

        # C1 is now furthest below its target share (5 active vs. 6 target
        # at bank size 8), so the single replacement should be C1 again.
        activated = service.activate_up_to_bank_target(db_session, user.id, target=8)

        assert activated == 1
        counts_after = _active_counts_by_difficulty(db_session, user.id)
        assert counts_after == {Difficulty.C1: 6, Difficulty.B2: 2}


def _active_counts_by_difficulty(db_session, user_id) -> dict:
    rows = db_session.execute(
        select(TextVersion.difficulty, func.count())
        .select_from(UserTextProgress)
        .join(Text, Text.id == UserTextProgress.text_id)
        .join(TextVersion, TextVersion.id == Text.current_version_id)
        .where(
            UserTextProgress.user_id == user_id,
            UserTextProgress.status == TextProgressStatus.ACTIVE,
        )
        .group_by(TextVersion.difficulty)
    ).all()
    return dict(rows)


class TestUpdateLevelSettings:
    def test_rejects_current_level_share_above_50_percent(self, db_session):
        user = make_user(db_session)  # current=B2, target=C1 (default), share=0.25

        result = service.update_level_settings(db_session, user.id, current_level_share=0.6)

        assert isinstance(result, service.LevelSettingsRejection)
        assert result.suggested_target_level == Difficulty.B2

    def test_accepts_exactly_50_percent(self, db_session):
        user = make_user(db_session)

        result = service.update_level_settings(db_session, user.id, current_level_share=0.5)

        assert result.current_level_share == 0.5

    def test_collapsing_target_to_current_bypasses_the_share_ceiling(self, db_session):
        user = make_user(db_session)

        result = service.update_level_settings(
            db_session, user.id, target_level=Difficulty.B2, current_level_share=0.9
        )

        assert result.target_level == Difficulty.B2
        assert result.current_level_share == 0.25

    def test_raises_if_target_is_below_current_level(self, db_session):
        user = make_user(db_session)

        with pytest.raises(ValueError):
            service.update_level_settings(db_session, user.id, target_level=Difficulty.A1)

    def test_raises_before_a_current_level_is_chosen(self, db_session):
        user = make_user_without_level(db_session)

        with pytest.raises(ValueError):
            service.update_level_settings(db_session, user.id, target_level=Difficulty.B2)


class TestRebalanceActiveBank:
    def test_fully_evicts_a_tier_left_over_from_a_previous_target(self, db_session):
        # Mirrors a real production bug: a user whose bank was built under
        # the old 3-tier system (current/next/two-up) had B1/B2/C1 all
        # active. Switching target from C1 to B2 makes C1 an "orphaned"
        # tier — not one of the two new weighted tiers at all — which must
        # be fully evicted, not silently left active forever.
        user = make_user_without_level(db_session)
        for _ in range(50):
            make_text(db_session, difficulty=Difficulty.B1)
        for _ in range(100):
            make_text(db_session, difficulty=Difficulty.B2)
        for _ in range(15):
            make_text(db_session, difficulty=Difficulty.C1)
        learning_state = service.get_or_create_learning_state(db_session, user.id)
        learning_state.current_level = Difficulty.B1
        learning_state.target_level = Difficulty.C1
        learning_state.current_level_share = 0.15
        db_session.commit()
        service.activate_up_to_bank_target(db_session, user.id, target=100)
        assert _active_counts_by_difficulty(db_session, user.id).get(Difficulty.C1, 0) > 0

        # Now the user switches their target from C1 to B2.
        learning_state.target_level = Difficulty.B2
        learning_state.current_level_share = 0.25
        db_session.commit()
        service.rebalance_active_bank(db_session, user.id)
        db_session.commit()

        counts_after = _active_counts_by_difficulty(db_session, user.id)
        assert counts_after.get(Difficulty.C1, 0) == 0
        assert set(counts_after) == {Difficulty.B1, Difficulty.B2}
        # Total bank size is preserved — C1's slots moved to B1/B2, not lost.
        assert sum(counts_after.values()) == 100

    def test_evicts_excess_and_backfills_deficient_tier(self, db_session):
        user = make_user_without_level(db_session)
        for _ in range(10):
            make_text(db_session, difficulty=Difficulty.B2)
        for _ in range(10):
            make_text(db_session, difficulty=Difficulty.C1)
        learning_state = service.get_or_create_learning_state(db_session, user.id)
        learning_state.current_level = Difficulty.B2
        learning_state.target_level = Difficulty.C1
        learning_state.current_level_share = 0.5
        db_session.commit()
        service.activate_up_to_bank_target(db_session, user.id, target=10)
        assert _active_counts_by_difficulty(db_session, user.id) == {
            Difficulty.B2: 5,
            Difficulty.C1: 5,
        }

        learning_state.current_level_share = 0.1
        db_session.commit()
        service.rebalance_active_bank(db_session, user.id)
        db_session.commit()

        assert _active_counts_by_difficulty(db_session, user.id) == {
            Difficulty.B2: 1,
            Difficulty.C1: 9,
        }
        benched = db_session.scalars(
            select(UserTextProgress).where(
                UserTextProgress.user_id == user.id,
                UserTextProgress.status == TextProgressStatus.BENCHED,
            )
        ).all()
        assert len(benched) == 4

    def test_protects_the_in_progress_exercise_from_eviction(self, db_session):
        user = make_user_without_level(db_session)
        for _ in range(3):
            make_text(db_session, difficulty=Difficulty.B2)
        make_text(db_session, difficulty=Difficulty.C1)
        learning_state = service.get_or_create_learning_state(db_session, user.id)
        learning_state.current_level = Difficulty.B2
        learning_state.target_level = Difficulty.C1
        learning_state.current_level_share = 0.25
        db_session.commit()
        service.activate_up_to_bank_target(db_session, user.id, target=3)
        protected = db_session.scalars(
            select(UserTextProgress).where(
                UserTextProgress.user_id == user.id, UserTextProgress.status == TextProgressStatus.ACTIVE
            )
        ).first()
        learning_state.current_text_id = protected.text_id
        learning_state.current_level_share = 0.0  # now targets 0% B2, 100% C1
        db_session.commit()

        service.rebalance_active_bank(db_session, user.id)
        db_session.commit()

        refreshed = db_session.get(UserTextProgress, (user.id, protected.text_id))
        assert refreshed.status == TextProgressStatus.ACTIVE

    def test_reactivation_preserves_mastery_score(self, db_session):
        user = make_user_without_level(db_session)
        for _ in range(2):
            make_text(db_session, difficulty=Difficulty.B2)
        make_text(db_session, difficulty=Difficulty.C1)
        learning_state = service.get_or_create_learning_state(db_session, user.id)
        learning_state.current_level = Difficulty.B2
        learning_state.target_level = Difficulty.C1
        learning_state.current_level_share = 1.0  # only B2 has supply at this point anyway
        db_session.commit()
        service.activate_up_to_bank_target(db_session, user.id, target=2)

        rows = db_session.scalars(
            select(UserTextProgress).where(UserTextProgress.user_id == user.id)
        ).all()
        target_row = rows[0]
        target_row.mastery_score = 3
        db_session.add(target_row)
        db_session.commit()

        learning_state.current_level_share = 0.0
        db_session.commit()
        service.rebalance_active_bank(db_session, user.id)
        db_session.commit()

        benched_row = db_session.get(UserTextProgress, (user.id, target_row.text_id))
        assert benched_row.status == TextProgressStatus.BENCHED
        assert benched_row.mastery_score == 3

        learning_state.current_level_share = 1.0
        db_session.commit()
        service.rebalance_active_bank(db_session, user.id)
        db_session.commit()

        reactivated_row = db_session.get(UserTextProgress, (user.id, target_row.text_id))
        assert reactivated_row.status == TextProgressStatus.ACTIVE
        assert reactivated_row.mastery_score == 3


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

    def test_second_due_review_is_deferred_until_the_gap_passes(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        make_text(db_session)
        make_text(db_session)
        service.activate_up_to_bank_target(db_session, user.id, target=3)
        db_session.commit()

        rows = db_session.scalars(
            select(UserTextProgress)
            .where(UserTextProgress.user_id == user.id)
            .order_by(UserTextProgress.rotation_position)
        ).all()
        normal_row, due_a, due_b = rows[0], rows[1], rows[2]
        due_a.next_review_at_exercise = 0
        due_b.next_review_at_exercise = 0
        db_session.add_all([due_a, due_b])
        db_session.commit()

        first = service.get_next_exercise(db_session, user)
        assert first.is_review is True
        served_review_id = first.progress.text_id

        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])
        service.submit_answer(
            db_session, engine, user, text_id=served_review_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()),
        )

        second = service.get_next_exercise(db_session, user)

        assert second.is_review is False
        assert second.progress.text_id == normal_row.text_id


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

    def test_two_natural_answers_masters_the_text(self, db_session):
        # Default required_score is 4 (2 natural-answer equivalents at +2 each).
        user = make_user(db_session)
        make_text(db_session)
        engine = FakeEngine(
            evaluation_results=[
                eval_result(Verdict.CORRECT_NATURAL),
                eval_result(Verdict.CORRECT_NATURAL),
            ]
        )

        result = None
        for _ in range(2):
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

    def test_duplicate_submission_id_does_not_leak_across_users(self, db_session):
        text = make_text(db_session)
        user_a = make_user(db_session)
        user_b = make_user(db_session)
        service.get_next_exercise(db_session, user_a)
        service.get_next_exercise(db_session, user_b)
        engine = FakeEngine(
            evaluation_results=[eval_result(Verdict.CORRECT_NATURAL), eval_result(Verdict.INCORRECT)]
        )
        submission_id = str(uuid.uuid4())

        result_a = service.submit_answer(
            db_session, engine, user_a, text_id=text.id,
            user_answer="user a's answer", input_method=InputMethod.KEYBOARD,
            submission_id=submission_id,
        )
        result_b = service.submit_answer(
            db_session, engine, user_b, text_id=text.id,
            user_answer="user b's answer", input_method=InputMethod.KEYBOARD,
            submission_id=submission_id, finalize=True,
        )

        assert result_a.evaluation.id != result_b.evaluation.id
        assert engine.evaluate_calls == 2
        assert result_a.evaluation.verdict == Verdict.CORRECT_NATURAL
        assert result_b.evaluation.verdict == Verdict.INCORRECT

    def test_incorrect_answer_schedules_review_after_20(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.INCORRECT)])

        result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="wrong", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
            finalize=True,
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
            # One unnatural then two naturals: 1+2+2=5 >= required_score(4),
            # imperfect record -> WAITING_FOR_TEST_ASSIGNMENT.
            engine.evaluation_results = [
                eval_result(Verdict.CORRECT_UNNATURAL),
                eval_result(Verdict.CORRECT_NATURAL),
                eval_result(Verdict.CORRECT_NATURAL),
            ]
            engine.evaluate_calls = 0
            for _ in range(3):
                # finalize=True: this test is about cumulative scoring and
                # test-assignment, not the writing-issue/unnatural retry UX.
                service.submit_answer(
                    db_session, engine, user, text_id=text_id,
                    user_answer="answer", input_method=InputMethod.KEYBOARD,
                    submission_id=str(uuid.uuid4()), finalize=True,
                )

        tests = db_session.scalars(select(Test).where(Test.user_id == user.id)).all()
        assert len(tests) == 1
        test_texts = db_session.scalars(select(TestText).where(TestText.test_id == tests[0].id)).all()
        assert len(test_texts) == 25


class TestSeriesProgress:
    def test_a_committed_answer_advances_the_series(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])

        result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()),
        )

        assert result.series_progress == 1
        assert result.series_goal == 10  # default, set by choose_level in make_user
        assert result.series_success_count == 1
        assert result.series_points == 2
        assert result.series_completed is False

        learning_state = service.get_or_create_learning_state(db_session, user.id)
        assert learning_state.series_progress == 1

    def test_a_pending_retry_offer_does_not_advance_the_series(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_UNNATURAL)])

        result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()),
        )

        assert result.committed is False
        learning_state = service.get_or_create_learning_state(db_session, user.id)
        assert learning_state.series_progress == 0

    def test_reaching_the_goal_completes_and_resets_the_series(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        service.update_series_settings(db_session, user.id, series_goal=2)
        engine = FakeEngine(
            evaluation_results=[eval_result(Verdict.CORRECT_NATURAL), eval_result(Verdict.CORRECT_NATURAL)]
        )

        results = []
        for _ in range(2):
            next_ex = service.get_next_exercise(db_session, user)
            results.append(
                service.submit_answer(
                    db_session, engine, user, text_id=next_ex.progress.text_id,
                    user_answer="answer", input_method=InputMethod.KEYBOARD,
                    submission_id=str(uuid.uuid4()),
                )
            )

        assert results[0].series_completed is False
        assert results[0].series_progress == 1
        assert results[1].series_completed is True
        assert results[1].series_progress == 2  # reported value is pre-reset
        assert results[1].series_success_count == 2
        assert results[1].series_points == 4

        learning_state = service.get_or_create_learning_state(db_session, user.id)
        assert learning_state.series_progress == 0
        assert learning_state.series_success_count == 0
        assert learning_state.series_points == 0

    def test_skip_does_not_advance_the_series(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)

        service.skip_current(db_session, user.id, next_ex.learning_state)

        learning_state = service.get_or_create_learning_state(db_session, user.id)
        assert learning_state.series_progress == 0

    def test_reevaluation_does_not_advance_the_series(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])
        service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()),
        )
        progress_after_submit = service.get_or_create_learning_state(db_session, user.id).series_progress

        engine.evaluation_results = [eval_result(Verdict.CORRECT_NATURAL)]
        engine.evaluate_calls = 0
        service.reevaluate_text(db_session, engine, user, next_ex.progress.text_id)

        learning_state = service.get_or_create_learning_state(db_session, user.id)
        assert learning_state.series_progress == progress_after_submit

    def test_explore_alternative_does_not_advance_the_series(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])

        service.explore_alternative(db_session, engine, user, text.id, "some answer")

        learning_state = service.get_or_create_learning_state(db_session, user.id)
        assert learning_state.series_progress == 0

    def test_replaying_a_submission_id_does_not_advance_the_series_again(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])
        submission_id = str(uuid.uuid4())

        service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD,
            submission_id=submission_id,
        )
        replay = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD,
            submission_id=submission_id,
        )

        assert replay.series_progress == 1
        learning_state = service.get_or_create_learning_state(db_session, user.id)
        assert learning_state.series_progress == 1


class TestUpdateSeriesSettings:
    def test_changing_the_goal_resets_progress(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])
        service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()),
        )

        learning_state = service.update_series_settings(db_session, user.id, series_goal=20)

        assert learning_state.series_goal == 20
        assert learning_state.series_progress == 0
        assert learning_state.series_success_count == 0
        assert learning_state.series_points == 0


class TestWritingIssueUnlimitedRetry:
    def test_does_not_commit_by_default(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_WITH_WRITING_ISSUES)])

        result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="i dont think hes coming", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()),
        )

        assert result.committed is False
        assert result.verdict == Verdict.CORRECT_WITH_WRITING_ISSUES
        assert db_session.scalars(select(Attempt).where(Attempt.user_id == user.id)).all() == []
        progress = db_session.get(UserTextProgress, (user.id, next_ex.progress.text_id))
        assert progress.mastery_score == 0
        assert progress.status == TextProgressStatus.ACTIVE

    def test_can_be_retried_any_number_of_times_without_committing(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(
            evaluation_results=[
                eval_result(Verdict.CORRECT_WITH_WRITING_ISSUES),
                eval_result(Verdict.CORRECT_WITH_WRITING_ISSUES),
                eval_result(Verdict.CORRECT_WITH_WRITING_ISSUES),
            ]
        )

        for _ in range(3):
            result = service.submit_answer(
                db_session, engine, user, text_id=next_ex.progress.text_id,
                user_answer="i dont think hes coming", input_method=InputMethod.KEYBOARD,
                submission_id=str(uuid.uuid4()),
            )
            assert result.committed is False

        progress = db_session.get(UserTextProgress, (user.id, next_ex.progress.text_id))
        assert progress.mastery_score == 0
        assert progress.times_presented == 0

    def test_finalize_commits_the_writing_issue_verdict(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_WITH_WRITING_ISSUES)])

        result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="i dont think hes coming", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()), finalize=True,
        )

        assert result.committed is True
        assert result.points_awarded == 1
        assert result.progress.perfect_learning_record is False

    def test_pending_submission_still_records_ai_usage(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_WITH_WRITING_ISSUES)])

        service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="i dont think hes coming", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()),
        )

        from app.shared.models import AIOperation, AIUsage

        usage = db_session.query(AIUsage).filter_by(
            operation=AIOperation.EVALUATION, user_id=user.id
        ).all()
        assert len(usage) == 1

    def test_pending_submission_does_not_advance_exercise_sequence(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_WITH_WRITING_ISSUES)])
        sequence_before = next_ex.learning_state.exercise_sequence

        service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="i dont think hes coming", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()),
        )

        learning_state = service.get_or_create_learning_state(db_session, user.id)
        assert learning_state.exercise_sequence == sequence_before


class TestUnnaturalAndIncorrectRetryOffers:
    """CORRECT_UNNATURAL and INCORRECT each get up to MAX_RETRIES (2) "want
    to improve?" offers before submit_answer commits unconditionally —
    always giving at least one chance to improve, per product decision."""

    @pytest.mark.parametrize("verdict", [Verdict.CORRECT_UNNATURAL, Verdict.INCORRECT])
    def test_does_not_commit_on_first_try(self, db_session, verdict):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(verdict)])

        result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()),
        )

        assert result.committed is False
        assert db_session.scalars(select(Attempt).where(Attempt.user_id == user.id)).all() == []

    @pytest.mark.parametrize("verdict", [Verdict.CORRECT_UNNATURAL, Verdict.INCORRECT])
    def test_does_not_commit_after_one_retry(self, db_session, verdict):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(verdict)])

        result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()), retry_count=1,
        )

        assert result.committed is False

    @pytest.mark.parametrize(
        "verdict,expected_points",
        [(Verdict.CORRECT_UNNATURAL, 1), (Verdict.INCORRECT, 0)],
    )
    def test_commits_once_max_retries_are_used(self, db_session, verdict, expected_points):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(verdict)])

        result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()), retry_count=2,
        )

        assert result.committed is True
        assert result.points_awarded == expected_points

    def test_finalize_commits_without_needing_max_retries(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_UNNATURAL)])

        result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()), finalize=True,
        )

        assert result.committed is True

    def test_a_writing_issue_verdict_during_the_retry_still_gets_its_own_unlimited_offer(self, db_session):
        # retry_count only forces a commit for CORRECT_UNNATURAL/INCORRECT;
        # a writing-issue verdict on the retry follows its own unlimited
        # rule regardless of how high retry_count already is — writing-
        # issue retries never consume the improve-chance budget.
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_WITH_WRITING_ISSUES)])

        result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="i dont think hes coming", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()), retry_count=2,
        )

        assert result.committed is False


class TestNaturalAlwaysCommitsImmediately:
    def test_natural_commits_without_any_flag(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])

        result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD,
            submission_id=str(uuid.uuid4()),
        )

        assert result.committed is True


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

        assert progress.required_natural_equivalents == 3
        assert progress.required_score == 6

    def test_decrease_repetition_lowers_targets(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        service.increase_repetition_for_text(db_session, user.id, next_ex.progress.text_id)

        progress = service.decrease_repetition_for_text(db_session, user.id, next_ex.progress.text_id)

        assert progress.required_natural_equivalents == 2
        assert progress.required_score == 4

    def test_decrease_repetition_does_not_go_below_the_floor_with_no_prior_increase(
        self, db_session
    ):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)

        progress = service.decrease_repetition_for_text(db_session, user.id, next_ex.progress.text_id)

        assert progress.required_natural_equivalents == 2
        assert progress.required_score == 4

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


class TestDisableTextForUser:
    def test_disabling_an_active_text_backfills_the_bank(self, db_session):
        user = make_user(db_session)
        for _ in range(2):
            make_text(db_session)
        service.activate_up_to_bank_target(db_session, user.id, target=1)
        db_session.commit()
        progress_row = db_session.scalars(
            select(UserTextProgress).where(UserTextProgress.user_id == user.id)
        ).one()

        updated = service.disable_text_for_user(db_session, user.id, progress_row.text_id)

        assert updated.status == TextProgressStatus.DISABLED
        active = db_session.scalars(
            select(UserTextProgress).where(
                UserTextProgress.user_id == user.id, UserTextProgress.status == TextProgressStatus.ACTIVE
            )
        ).all()
        assert len(active) == 1
        assert active[0].text_id != progress_row.text_id

    def test_disabling_a_non_active_text_does_not_trigger_a_backfill(self, db_session):
        user = make_user(db_session)
        for _ in range(3):
            make_text(db_session)
        service.activate_up_to_bank_target(db_session, user.id, target=2)
        db_session.commit()
        active_rows = db_session.scalars(
            select(UserTextProgress).where(
                UserTextProgress.user_id == user.id, UserTextProgress.status == TextProgressStatus.ACTIVE
            )
        ).all()
        mastered, still_active = active_rows[0], active_rows[1]
        # Simulate a text that was already mastered by a prior attempt,
        # bypassing the usual backfill so the active count reflects only
        # `still_active` — isolates whether *this* disable call backfills.
        mastered.status = TextProgressStatus.MASTERED
        db_session.add(mastered)
        db_session.commit()

        updated = service.disable_text_for_user(db_session, user.id, mastered.text_id)

        assert updated.status == TextProgressStatus.DISABLED
        active = db_session.scalars(
            select(UserTextProgress).where(
                UserTextProgress.user_id == user.id, UserTextProgress.status == TextProgressStatus.ACTIVE
            )
        ).all()
        assert [a.text_id for a in active] == [still_active.text_id]

    def test_disabling_a_never_seen_text_creates_a_disabled_row(self, db_session):
        user = make_user_without_level(db_session)
        text = make_text(db_session)
        assert db_session.get(UserTextProgress, (user.id, text.id)) is None

        updated = service.disable_text_for_user(db_session, user.id, text.id)

        assert updated.status == TextProgressStatus.DISABLED
        assert db_session.get(UserTextProgress, (user.id, text.id)) is not None

    def test_disabling_an_already_disabled_text_is_idempotent(self, db_session):
        user = make_user_without_level(db_session)
        text = make_text(db_session)
        service.disable_text_for_user(db_session, user.id, text.id)

        updated = service.disable_text_for_user(db_session, user.id, text.id)

        assert updated.status == TextProgressStatus.DISABLED


def assessment_result(has_normal_meaning: bool) -> SourceTextAssessmentResult:
    return SourceTextAssessmentResult(
        has_normal_meaning=has_normal_meaning,
        explanation="explanation",
        model="gpt-4o-mini",
        prompt_version="text-sensibility-v1",
        input_tokens=1,
        output_tokens=1,
    )


class TestReportText:
    def test_confirmed_report_disables_globally_and_replaces_for_the_user(self, db_session):
        user = make_user(db_session)
        for _ in range(2):
            make_text(db_session)
        service.activate_up_to_bank_target(db_session, user.id, target=1)
        db_session.commit()
        progress_row = db_session.scalars(
            select(UserTextProgress).where(UserTextProgress.user_id == user.id)
        ).one()
        engine = FakeEngine(assessment_result=assessment_result(has_normal_meaning=False))

        result = service.report_text(db_session, engine, user, progress_row.text_id)

        assert result.confirmed is True
        assert engine.assess_source_text_calls == 1
        text = db_session.get(Text, progress_row.text_id)
        assert text.enabled is False
        updated_progress = db_session.get(UserTextProgress, (user.id, progress_row.text_id))
        assert updated_progress.status == TextProgressStatus.DISABLED
        active = db_session.scalars(
            select(UserTextProgress).where(
                UserTextProgress.user_id == user.id, UserTextProgress.status == TextProgressStatus.ACTIVE
            )
        ).all()
        assert len(active) == 1
        assert active[0].text_id != progress_row.text_id

    def test_confirmed_report_clears_it_as_the_current_exercise(self, db_session):
        user = make_user(db_session)
        for _ in range(2):
            make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(assessment_result=assessment_result(has_normal_meaning=False))

        service.report_text(db_session, engine, user, next_ex.progress.text_id)

        learning_state = service.get_or_create_learning_state(db_session, user.id)
        assert learning_state.current_text_id is None

    def test_rejected_report_changes_nothing(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(assessment_result=assessment_result(has_normal_meaning=True))

        result = service.report_text(db_session, engine, user, next_ex.progress.text_id)

        assert result.confirmed is False
        text = db_session.get(Text, next_ex.progress.text_id)
        assert text.enabled is True
        progress = db_session.get(UserTextProgress, (user.id, next_ex.progress.text_id))
        assert progress.status == TextProgressStatus.ACTIVE
        learning_state = service.get_or_create_learning_state(db_session, user.id)
        assert learning_state.current_text_id == next_ex.progress.text_id

    def test_raises_for_an_unknown_text(self, db_session):
        user = make_user(db_session)
        engine = FakeEngine(assessment_result=assessment_result(has_normal_meaning=False))

        with pytest.raises(ValueError):
            service.report_text(db_session, engine, user, uuid.uuid4())


class TestDisableTextGlobally:
    def test_disables_the_text(self, db_session):
        text = make_text(db_session)

        service.disable_text_globally(db_session, text.id)

        db_session.refresh(text)
        assert text.enabled is False

    def test_evicts_an_active_user_with_backfill(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)
        make_text(db_session)  # unseen spare, available to backfill the evicted slot
        progress = UserTextProgress(
            user_id=user.id, text_id=text.id, status=TextProgressStatus.ACTIVE,
            rotation_position=1,
        )
        db_session.add(progress)
        db_session.commit()

        affected = service.disable_text_globally(db_session, text.id)

        assert affected == {user.id}
        db_session.refresh(progress)
        assert progress.status == TextProgressStatus.DISABLED

    def test_evicts_a_user_who_already_mastered_it(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)
        progress = UserTextProgress(
            user_id=user.id, text_id=text.id, status=TextProgressStatus.MASTERED
        )
        db_session.add(progress)
        db_session.commit()

        affected = service.disable_text_globally(db_session, text.id)

        assert affected == {user.id}
        db_session.refresh(progress)
        assert progress.status == TextProgressStatus.DISABLED

    def test_no_progress_rows_affects_no_users(self, db_session):
        text = make_text(db_session)

        affected = service.disable_text_globally(db_session, text.id)

        assert affected == set()


class TestResolveDuplicateTexts:
    def test_disables_every_duplicate_but_the_survivor(self, db_session):
        survivor = make_text(db_session, french_text="Bonjour le monde")
        dupe = make_text(db_session, french_text="  BONJOUR   le monde  ")

        result = service.resolve_duplicate_texts(db_session, Difficulty.B2)

        assert result.groups_resolved == 1
        assert result.texts_disabled == 1
        db_session.refresh(survivor)
        db_session.refresh(dupe)
        assert survivor.enabled is True
        assert dupe.enabled is False

    def test_evicts_an_active_user_with_backfill(self, db_session):
        user = make_user(db_session)
        make_text(db_session, french_text="Bonjour le monde")
        dupe = make_text(db_session, french_text="bonjour le monde")
        make_text(db_session)  # unseen spare, available to backfill the evicted slot
        progress = UserTextProgress(
            user_id=user.id, text_id=dupe.id, status=TextProgressStatus.ACTIVE,
            rotation_position=1,
        )
        db_session.add(progress)
        db_session.commit()

        result = service.resolve_duplicate_texts(db_session, Difficulty.B2)

        assert result.users_affected == 1
        db_session.refresh(progress)
        assert progress.status == TextProgressStatus.DISABLED
        active_ids = {
            row.text_id
            for row in db_session.scalars(
                select(UserTextProgress).where(
                    UserTextProgress.user_id == user.id,
                    UserTextProgress.status == TextProgressStatus.ACTIVE,
                )
            ).all()
        }
        assert dupe.id not in active_ids
        assert len(active_ids) >= 1

    def test_evicts_a_user_who_already_mastered_it(self, db_session):
        user = make_user(db_session)
        make_text(db_session, french_text="Bonjour le monde")
        dupe = make_text(db_session, french_text="bonjour le monde")
        progress = UserTextProgress(
            user_id=user.id, text_id=dupe.id, status=TextProgressStatus.MASTERED
        )
        db_session.add(progress)
        db_session.commit()

        result = service.resolve_duplicate_texts(db_session, Difficulty.B2)

        assert result.users_affected == 1
        db_session.refresh(progress)
        assert progress.status == TextProgressStatus.DISABLED

    def test_scopes_to_the_given_difficulty(self, db_session):
        make_text(db_session, french_text="Bonjour le monde", difficulty=Difficulty.B2)
        c1_survivor = make_text(db_session, french_text="Au revoir", difficulty=Difficulty.C1)
        c1_dupe = make_text(db_session, french_text="au revoir", difficulty=Difficulty.C1)

        result = service.resolve_duplicate_texts(db_session, Difficulty.B2)

        assert result.groups_resolved == 0
        db_session.refresh(c1_survivor)
        db_session.refresh(c1_dupe)
        assert c1_survivor.enabled is True
        assert c1_dupe.enabled is True

    def test_rerunning_is_a_no_op(self, db_session):
        make_text(db_session, french_text="Bonjour le monde")
        make_text(db_session, french_text="bonjour le monde")
        service.resolve_duplicate_texts(db_session, Difficulty.B2)

        result = service.resolve_duplicate_texts(db_session, Difficulty.B2)

        assert result.groups_resolved == 0
        assert result.texts_disabled == 0


class TestUpdateInsertionSettings:
    def test_updates_the_gap(self, db_session):
        user = make_user(db_session)

        learning_state = service.update_insertion_settings(
            db_session, user.id, new_text_insertion_gap=7
        )

        assert learning_state.new_text_insertion_gap == 7

    def test_new_texts_resurface_after_the_configured_gap_instead_of_the_back(self, db_session):
        user = make_user_without_level(db_session)
        for _ in range(10):
            make_text(db_session, difficulty=Difficulty.B2)
        service.update_insertion_settings(db_session, user.id, new_text_insertion_gap=2)
        learning_state = service.get_or_create_learning_state(db_session, user.id)
        learning_state.current_level = Difficulty.B2
        learning_state.target_level = Difficulty.B2
        db_session.commit()
        service.activate_up_to_bank_target(db_session, user.id, target=5)

        # Master the text with the lowest rotation_position (next in line)
        # to free exactly one slot for a single replacement activation.
        evicted = db_session.scalars(
            select(UserTextProgress)
            .where(UserTextProgress.user_id == user.id)
            .order_by(UserTextProgress.rotation_position.asc())
        ).first()
        active_before = db_session.scalars(
            select(UserTextProgress).where(
                UserTextProgress.user_id == user.id,
                UserTextProgress.status == TextProgressStatus.ACTIVE,
                UserTextProgress.text_id != evicted.text_id,
            )
        ).all()
        # Positions get reshuffled by the insertion shift, so identity must
        # be tracked by text_id, not by which position values existed before.
        text_ids_before = {row.text_id for row in active_before}
        positions_before = sorted(row.rotation_position for row in active_before)
        evicted.status = TextProgressStatus.MASTERED
        db_session.add(evicted)
        db_session.commit()

        service.activate_up_to_bank_target(db_session, user.id, target=5)

        # The replacement is the newly-activated text: the one whose
        # text_id wasn't already active before this activation.
        replacement = db_session.scalars(
            select(UserTextProgress).where(
                UserTextProgress.user_id == user.id,
                UserTextProgress.status == TextProgressStatus.ACTIVE,
                UserTextProgress.text_id.not_in(text_ids_before),
            )
        ).one()
        ahead_of_it = sum(1 for p in positions_before if p < replacement.rotation_position)
        assert ahead_of_it <= 2


class TestNaturalCycleSeniorityInvariant:
    def test_a_later_introduced_text_never_gets_its_nth_turn_before_an_earlier_ones(
        self, db_session
    ):
        user = make_user_without_level(db_session)
        # Exactly 4: A, B, C fill the target=3 bank, and the 4th is the only
        # unseen text left for D's backfill once C masters below.
        texts = [make_text(db_session, difficulty=Difficulty.B2) for _ in range(4)]
        service.update_insertion_settings(db_session, user.id, new_text_insertion_gap=1)
        learning_state = service.get_or_create_learning_state(db_session, user.id)
        learning_state.current_level = Difficulty.B2
        learning_state.target_level = Difficulty.B2
        db_session.commit()
        service.activate_up_to_bank_target(db_session, user.id, target=3)

        active_ids = [
            row.text_id
            for row in db_session.scalars(
                select(UserTextProgress).where(
                    UserTextProgress.user_id == user.id,
                    UserTextProgress.status == TextProgressStatus.ACTIVE,
                )
            ).all()
        ]
        a_id, b_id, c_id = active_ids
        # A and B must survive many more natural answers than C without
        # mastering, so raise their bar well past this test's observation
        # window (mastery churn is orthogonal to the invariant under test).
        for _ in range(5):
            service.increase_repetition_for_text(db_session, user.id, a_id)
            service.increase_repetition_for_text(db_session, user.id, b_id)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])

        for text_id in (a_id, b_id):
            service.submit_answer(
                db_session, engine, user, text_id=text_id,
                user_answer="answer", input_method=InputMethod.KEYBOARD,
                submission_id=str(uuid.uuid4()),
            )
        # Two naturals master C (score 2+2 >= required_score 4), which
        # backfills a brand-new text via the gap-aware insertion.
        for _ in range(2):
            service.submit_answer(
                db_session, engine, user, text_id=c_id,
                user_answer="answer", input_method=InputMethod.KEYBOARD,
                submission_id=str(uuid.uuid4()),
            )

        d_id = next(t.id for t in texts if t.id not in (a_id, b_id, c_id))
        for _ in range(5):
            service.increase_repetition_for_text(db_session, user.id, d_id)

        served_order = []
        for _ in range(9):  # 3 full cycles of the {A, D, B} steady-state bank
            next_ex = service.get_next_exercise(db_session, user)
            served_order.append(next_ex.progress.text_id)
            service.submit_answer(
                db_session, engine, user, text_id=next_ex.progress.text_id,
                user_answer="answer", input_method=InputMethod.KEYBOARD,
                submission_id=str(uuid.uuid4()),
            )

        d_occurrences = [i for i, t in enumerate(served_order) if t == d_id]
        # Deliberately out of scope: due-based review (a wrong/hint-assisted
        # answer) can still let a later text jump the queue - only the
        # natural, review-free cycle exercised here must respect seniority.
        assert len(d_occurrences) >= 2
        assert d_occurrences[1] > served_order.index(a_id)
        assert d_occurrences[1] > served_order.index(b_id)


class TestListUserTextBank:
    def test_lists_every_status_for_the_user(self, db_session):
        user = make_user(db_session)
        for _ in range(2):
            make_text(db_session)
        service.activate_up_to_bank_target(db_session, user.id, target=2)
        db_session.commit()
        progress_rows = db_session.scalars(
            select(UserTextProgress).where(UserTextProgress.user_id == user.id)
        ).all()
        service.disable_text_for_user(db_session, user.id, progress_rows[0].text_id)

        rows = service.list_user_text_bank(db_session, user.id)

        assert len(rows) == 2
        statuses = {text_id: status for text_id, _, status, *_ in rows}
        assert statuses[progress_rows[0].text_id] == TextProgressStatus.DISABLED

    def test_search_filters_by_french_text(self, db_session):
        user = make_user(db_session)
        make_text(db_session, french_text="Bonjour le monde")
        make_text(db_session, french_text="Autre chose entièrement")
        service.activate_up_to_bank_target(db_session, user.id, target=2)
        db_session.commit()

        rows = service.list_user_text_bank(db_session, user.id, search="bonjour")

        assert len(rows) == 1
        assert rows[0][1] == "Bonjour le monde"


class TestReevaluate:
    def test_reevaluation_creates_new_evaluation_and_updates_active_pointer(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_UNNATURAL)])

        submit_result = service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
            finalize=True,
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
            finalize=True,
        )
        score_after_submit = db_session.get(UserTextProgress, (user.id, next_ex.progress.text_id)).mastery_score

        engine.evaluation_results = [eval_result(Verdict.CORRECT_NATURAL)]
        engine.evaluate_calls = 0
        service.reevaluate_text(db_session, engine, user, next_ex.progress.text_id)

        score_after_reeval = db_session.get(UserTextProgress, (user.id, next_ex.progress.text_id)).mastery_score
        assert score_after_reeval == score_after_submit == 0


class TestExploreAlternative:
    def test_returns_the_evaluation_verdict_for_the_alternative(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)
        engine = FakeEngine(
            evaluation_results=[eval_result(Verdict.CORRECT_NATURAL, feedback="Great alternative!")]
        )

        result = service.explore_alternative(db_session, engine, user, text.id, "a totally different sentence")

        assert result.verdict == Verdict.CORRECT_NATURAL
        assert result.feedback == "Great alternative!"

    def test_never_creates_an_attempt_or_evaluation(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])

        service.explore_alternative(db_session, engine, user, text.id, "some sentence")

        assert db_session.scalars(select(Attempt)).first() is None
        assert db_session.scalars(select(Evaluation)).first() is None

    def test_never_creates_or_mutates_progress(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.INCORRECT)])

        service.explore_alternative(db_session, engine, user, text.id, "some sentence")

        assert db_session.get(UserTextProgress, (user.id, text.id)) is None

    def test_does_not_affect_progress_from_a_real_submission(self, db_session):
        user = make_user(db_session)
        make_text(db_session)
        next_ex = service.get_next_exercise(db_session, user)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])

        service.submit_answer(
            db_session, engine, user, text_id=next_ex.progress.text_id,
            user_answer="answer", input_method=InputMethod.KEYBOARD, submission_id=str(uuid.uuid4()),
            finalize=True,
        )
        score_after_submit = db_session.get(
            UserTextProgress, (user.id, next_ex.progress.text_id)
        ).mastery_score

        engine.evaluation_results = [eval_result(Verdict.INCORRECT)]
        engine.evaluate_calls = 0
        service.explore_alternative(db_session, engine, user, next_ex.progress.text_id, "a wrong guess")

        score_after_explore = db_session.get(
            UserTextProgress, (user.id, next_ex.progress.text_id)
        ).mastery_score
        assert score_after_explore == score_after_submit

    def test_can_be_called_repeatedly_with_no_accumulating_side_effects(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)
        engine = FakeEngine(
            evaluation_results=[eval_result(Verdict.CORRECT_UNNATURAL), eval_result(Verdict.CORRECT_NATURAL)]
        )

        first = service.explore_alternative(db_session, engine, user, text.id, "first try")
        second = service.explore_alternative(db_session, engine, user, text.id, "second try")

        assert first.verdict == Verdict.CORRECT_UNNATURAL
        assert second.verdict == Verdict.CORRECT_NATURAL
        assert db_session.scalars(select(Attempt)).first() is None
        assert db_session.get(UserTextProgress, (user.id, text.id)) is None

    def test_raises_for_an_unknown_text(self, db_session):
        user = make_user(db_session)
        engine = FakeEngine(evaluation_results=[eval_result(Verdict.CORRECT_NATURAL)])

        with pytest.raises(ValueError):
            service.explore_alternative(db_session, engine, user, uuid.uuid4(), "some sentence")
