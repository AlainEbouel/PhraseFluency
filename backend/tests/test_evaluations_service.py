from app.modules.evaluations.engine import EvaluationEngine
from app.modules.evaluations.enums import Verdict
from app.modules.evaluations.ports import (
    EvaluationResult,
    GrammarExplanationResult,
    PatternSuggestion,
    ReferenceGenerationResult,
)
from app.modules.evaluations.service import (
    get_or_create_reference,
    get_or_generate_grammar_explanation,
    run_evaluation,
)
from app.modules.texts.models import Difficulty, ExerciseType, Text, TextVersion
from app.modules.texts.service import get_or_create_pattern
from app.shared.models import AIOperation, AIUsage


class FakeEngine(EvaluationEngine):
    def __init__(
        self,
        reference_result=None,
        evaluation_result=None,
        explanation_result=None,
        weakness_suggestions_result=None,
    ):
        self.reference_result = reference_result
        self.evaluation_result = evaluation_result
        self.explanation_result = explanation_result
        self.weakness_suggestions_result = weakness_suggestions_result
        self.reference_calls = 0
        self.explanation_calls = 0
        self.weakness_suggestions_calls = 0

    def generate_reference(self, request):
        self.reference_calls += 1
        return self.reference_result

    def evaluate(self, request):
        return self.evaluation_result

    def generate_grammar_explanation(self, request):
        self.explanation_calls += 1
        return self.explanation_result

    def generate_weakness_suggestions(self, request):
        self.weakness_suggestions_calls += 1
        return self.weakness_suggestions_result


def make_text_version(db_session, french_text="Je n'ai pas eu l'occasion de regarder ça."):
    text = Text(source="test")
    db_session.add(text)
    db_session.flush()

    version = TextVersion(
        text_id=text.id,
        french_text=french_text,
        exercise_type=ExerciseType.TRANSLATION,
        difficulty=Difficulty.B2,
        contexts=["professional"],
    )
    db_session.add(version)
    db_session.flush()

    text.current_version_id = version.id
    db_session.add(text)
    db_session.flush()
    return version


def reference_result(**overrides):
    defaults = dict(
        preferred_translation="I haven't had a chance to look into it yet.",
        alternatives=["I haven't gotten around to it yet."],
        hints=["clue", "partial", "chunk"],
        patterns=[],
        model="gpt-4o-mini",
        prompt_version="reference-v1",
        input_tokens=40,
        output_tokens=25,
    )
    defaults.update(overrides)
    return ReferenceGenerationResult(**defaults)


class TestGetOrCreateReference:
    def test_creates_and_persists_reference_with_patterns_and_usage(self, db_session):
        version = make_text_version(db_session)
        engine = FakeEngine(
            reference_result=reference_result(
                patterns=[
                    PatternSuggestion(
                        "I haven't had a chance to...", "haven't done X yet", "example"
                    )
                ]
            )
        )

        reference = get_or_create_reference(db_session, engine, version)

        assert reference.preferred_translation == "I haven't had a chance to look into it yet."
        assert reference.patterns == ["I haven't had a chance to..."]

        usage = (
            db_session.query(AIUsage)
            .filter_by(operation=AIOperation.REFERENCE_GENERATION)
            .all()
        )
        assert len(usage) == 1
        assert usage[0].input_tokens == 40
        assert usage[0].output_tokens == 25

    def test_second_call_reuses_cached_reference_without_calling_engine_again(self, db_session):
        version = make_text_version(db_session)
        engine = FakeEngine(reference_result=reference_result())

        first = get_or_create_reference(db_session, engine, version)
        second = get_or_create_reference(db_session, engine, version)

        assert first.id == second.id
        assert engine.reference_calls == 1


class TestGetOrCreatePattern:
    def test_dedups_by_normalized_expression(self, db_session):
        version_a = make_text_version(db_session)
        version_b = make_text_version(db_session)

        pattern_a = get_or_create_pattern(
            db_session,
            expression="I haven't had a chance to...",
            meaning="m",
            example="e",
            text_version=version_a,
        )
        db_session.flush()
        pattern_b = get_or_create_pattern(
            db_session,
            expression="  I HAVEN'T had a chance to...  ",
            meaning="m2",
            example="e2",
            text_version=version_b,
        )
        db_session.flush()

        assert pattern_a.id == pattern_b.id
        assert version_a in pattern_a.related_text_versions
        assert version_b in pattern_a.related_text_versions


class TestGetOrGenerateGrammarExplanation:
    def test_generates_once_and_caches(self, db_session):
        version = make_text_version(db_session)
        engine = FakeEngine(
            reference_result=reference_result(),
            explanation_result=GrammarExplanationResult(
                explanation="Present perfect explanation.",
                model="gpt-4o-mini",
                prompt_version="explanation-v1",
                input_tokens=5,
                output_tokens=15,
            ),
        )
        reference = get_or_create_reference(db_session, engine, version)

        first = get_or_generate_grammar_explanation(db_session, engine, version, reference)
        second = get_or_generate_grammar_explanation(db_session, engine, version, reference)

        assert first == "Present perfect explanation."
        assert second == first
        assert engine.explanation_calls == 1

        usage = (
            db_session.query(AIUsage)
            .filter_by(operation=AIOperation.GRAMMAR_EXPLANATION)
            .all()
        )
        assert len(usage) == 1


class TestRunEvaluation:
    def test_delegates_to_engine_and_returns_result_unpersisted(self, db_session):
        version = make_text_version(db_session)
        engine = FakeEngine(
            reference_result=reference_result(),
            evaluation_result=EvaluationResult(
                verdict=Verdict.CORRECT_NATURAL,
                meaning_preserved=True,
                grammar_correct=True,
                natural_american_english=True,
                writing_issues=[],
                corrected_answer=None,
                feedback="Good.",
                error_categories=[],
                model="gpt-4o-mini",
                prompt_version="evaluation-v1",
                input_tokens=10,
                output_tokens=5,
            ),
        )
        reference = get_or_create_reference(db_session, engine, version)

        result = run_evaluation(
            engine,
            text_version=version,
            reference=reference,
            user_answer="I haven't had a chance to look into it.",
            hint_used=False,
        )

        assert result.verdict == Verdict.CORRECT_NATURAL
        assert result.feedback == "Good."
