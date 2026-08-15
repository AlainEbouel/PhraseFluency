import pytest
from openai import OpenAIError

from app.modules.evaluations.engine import EvaluationEngineError
from app.modules.evaluations.enums import Verdict
from app.modules.evaluations.error_categories import ErrorCategory
from app.modules.evaluations.openai_engine import (
    OpenAIEvaluationEngine,
    _EvaluationSchema,
    _ExplanationSchema,
    _PatternSchema,
    _ReferenceSchema,
    _WeaknessSuggestionSchema,
    _WeaknessSuggestionsSchema,
)
from app.modules.evaluations.ports import (
    EvaluationRequest,
    GrammarExplanationRequest,
    ReferenceGenerationRequest,
    WeaknessCategoryContext,
    WeaknessSuggestionsRequest,
)


class _FakeUsage:
    def __init__(self, prompt_tokens, completion_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _FakeMessage:
    def __init__(self, parsed=None, refusal=None):
        self.parsed = parsed
        self.refusal = refusal


class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeCompletion:
    def __init__(self, parsed=None, refusal=None, usage=(10, 20)):
        self.choices = [_FakeChoice(_FakeMessage(parsed=parsed, refusal=refusal))]
        self.usage = _FakeUsage(*usage) if usage is not None else None


class _FakeParseEndpoint:
    def __init__(self, result=None, exception=None):
        self._result = result
        self._exception = exception
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self._exception is not None:
            raise self._exception
        return self._result


class _FakeClient:
    def __init__(self, parse_endpoint):
        completions = type("C", (), {"parse": staticmethod(parse_endpoint)})()
        chat = type("Chat", (), {"completions": completions})()
        self.beta = type("Beta", (), {"chat": chat})()


def make_engine(parse_endpoint: _FakeParseEndpoint) -> OpenAIEvaluationEngine:
    engine = OpenAIEvaluationEngine(api_key="sk-test", model="gpt-4o-mini")
    engine._client = _FakeClient(parse_endpoint)
    return engine


def evaluation_request(**overrides) -> EvaluationRequest:
    defaults = dict(
        french_text="Je n'ai pas eu l'occasion de regarder ça.",
        user_answer="I haven't had a chance to look into it.",
        preferred_translation="I haven't had a chance to look into it yet.",
        alternatives=[],
        hint_used=False,
    )
    defaults.update(overrides)
    return EvaluationRequest(**defaults)


class TestGenerateReference:
    def test_happy_path_maps_all_fields(self):
        parsed = _ReferenceSchema(
            preferred_translation="I haven't had a chance to look into it yet.",
            alternatives=["I haven't gotten around to looking into it yet."],
            hints=[
                "Think about something you meant to do but didn't get to.",
                "I haven't had a ___ to look into it.",
                "I haven't had a chance to...",
            ],
            patterns=[
                _PatternSchema(
                    expression="I haven't had a chance to...",
                    meaning="I haven't done X yet",
                    example="I haven't had a chance to call him back.",
                )
            ],
        )
        endpoint = _FakeParseEndpoint(result=_FakeCompletion(parsed=parsed, usage=(50, 30)))
        engine = make_engine(endpoint)

        result = engine.generate_reference(
            ReferenceGenerationRequest(
                french_text="Je n'ai pas eu l'occasion de regarder ça.",
                exercise_type="TRANSLATION",
                difficulty="B2",
            )
        )

        assert result.preferred_translation == parsed.preferred_translation
        assert result.alternatives == parsed.alternatives
        assert result.hints == parsed.hints
        assert len(result.patterns) == 1
        assert result.patterns[0].expression == "I haven't had a chance to..."
        assert result.model == "gpt-4o-mini"
        assert result.prompt_version == "reference-v1"
        assert result.input_tokens == 50
        assert result.output_tokens == 30

    def test_missing_usage_defaults_to_zero_tokens(self):
        parsed = _ReferenceSchema(
            preferred_translation="x", alternatives=[], hints=["a", "b", "c"], patterns=[]
        )
        endpoint = _FakeParseEndpoint(result=_FakeCompletion(parsed=parsed, usage=None))
        engine = make_engine(endpoint)

        result = engine.generate_reference(
            ReferenceGenerationRequest(french_text="x", exercise_type="TRANSLATION", difficulty="B1")
        )

        assert result.input_tokens == 0
        assert result.output_tokens == 0


class TestEvaluate:
    def test_happy_path_maps_verdict(self):
        parsed = _EvaluationSchema(
            verdict=Verdict.CORRECT_NATURAL,
            meaning_preserved=True,
            grammar_correct=True,
            natural_american_english=True,
            writing_issues=[],
            corrected_answer=None,
            feedback="Nicely done.",
            error_categories=[],
        )
        endpoint = _FakeParseEndpoint(result=_FakeCompletion(parsed=parsed))
        engine = make_engine(endpoint)

        result = engine.evaluate(evaluation_request())

        assert result.verdict == Verdict.CORRECT_NATURAL
        assert result.feedback == "Nicely done."
        assert result.error_categories == []
        assert result.prompt_version == "evaluation-v4"

    def test_error_categories_mapped_to_plain_strings(self):
        parsed = _EvaluationSchema(
            verdict=Verdict.INCORRECT,
            meaning_preserved=False,
            grammar_correct=False,
            natural_american_english=False,
            writing_issues=[],
            corrected_answer="corrected",
            feedback="Meaning changed.",
            error_categories=[ErrorCategory.VERB_TENSE, ErrorCategory.PREPOSITIONS],
        )
        endpoint = _FakeParseEndpoint(result=_FakeCompletion(parsed=parsed))
        engine = make_engine(endpoint)

        result = engine.evaluate(evaluation_request())

        assert result.error_categories == ["VERB_TENSE", "PREPOSITIONS"]

    def test_reevaluation_includes_previous_verdict_in_prompt(self):
        parsed = _EvaluationSchema(
            verdict=Verdict.CORRECT_NATURAL,
            meaning_preserved=True,
            grammar_correct=True,
            natural_american_english=True,
            writing_issues=[],
            corrected_answer=None,
            feedback="ok",
            error_categories=[],
        )
        endpoint = _FakeParseEndpoint(result=_FakeCompletion(parsed=parsed))
        engine = make_engine(endpoint)

        engine.evaluate(evaluation_request(previous_verdict=Verdict.CORRECT_UNNATURAL))

        user_message = endpoint.calls[0]["messages"][1]["content"]
        assert "CORRECT_UNNATURAL" in user_message

    def test_no_previous_verdict_omits_reevaluation_addendum(self):
        parsed = _EvaluationSchema(
            verdict=Verdict.CORRECT_NATURAL,
            meaning_preserved=True,
            grammar_correct=True,
            natural_american_english=True,
            writing_issues=[],
            corrected_answer=None,
            feedback="ok",
            error_categories=[],
        )
        endpoint = _FakeParseEndpoint(result=_FakeCompletion(parsed=parsed))
        engine = make_engine(endpoint)

        engine.evaluate(evaluation_request())

        user_message = endpoint.calls[0]["messages"][1]["content"]
        assert "re-evaluation" not in user_message.lower()

    def test_hint_used_flag_is_passed_through(self):
        parsed = _EvaluationSchema(
            verdict=Verdict.CORRECT_NATURAL,
            meaning_preserved=True,
            grammar_correct=True,
            natural_american_english=True,
            writing_issues=[],
            corrected_answer=None,
            feedback="ok",
            error_categories=[],
        )
        endpoint = _FakeParseEndpoint(result=_FakeCompletion(parsed=parsed))
        engine = make_engine(endpoint)

        engine.evaluate(evaluation_request(hint_used=True))

        user_message = endpoint.calls[0]["messages"][1]["content"]
        assert "Hint used before answering: yes" in user_message


class TestGenerateGrammarExplanation:
    def test_happy_path(self):
        parsed = _ExplanationSchema(explanation="Present perfect signals an unfinished timeframe.")
        endpoint = _FakeParseEndpoint(result=_FakeCompletion(parsed=parsed))
        engine = make_engine(endpoint)

        result = engine.generate_grammar_explanation(
            GrammarExplanationRequest(
                french_text="x", preferred_translation="I haven't had a chance to look into it yet."
            )
        )

        assert result.explanation == parsed.explanation
        assert result.prompt_version == "explanation-v1"


class TestGenerateWeaknessSuggestions:
    def test_happy_path_maps_all_fields(self):
        parsed = _WeaknessSuggestionsSchema(
            suggestions=[
                _WeaknessSuggestionSchema(
                    category="WORD_ORDER",
                    explanation="Tu places souvent l'adverbe avant le verbe conjugué.",
                    suggestion="Relis ta phrase en isolant le verbe et l'adverbe.",
                )
            ]
        )
        endpoint = _FakeParseEndpoint(result=_FakeCompletion(parsed=parsed, usage=(40, 25)))
        engine = make_engine(endpoint)

        result = engine.generate_weakness_suggestions(
            WeaknessSuggestionsRequest(
                categories=[
                    WeaknessCategoryContext(
                        category="WORD_ORDER", count=7, example_feedback=["The word order was off."]
                    )
                ]
            )
        )

        assert len(result.suggestions) == 1
        assert result.suggestions[0].category == "WORD_ORDER"
        assert result.suggestions[0].explanation == parsed.suggestions[0].explanation
        assert result.suggestions[0].suggestion == parsed.suggestions[0].suggestion
        assert result.prompt_version == "weakness-v1"
        assert result.input_tokens == 40
        assert result.output_tokens == 25


class TestFailureModes:
    def test_provider_error_raises_engine_error(self):
        endpoint = _FakeParseEndpoint(exception=OpenAIError("connection reset"))
        engine = make_engine(endpoint)

        with pytest.raises(EvaluationEngineError):
            engine.evaluate(evaluation_request())

    def test_refusal_raises_engine_error(self):
        endpoint = _FakeParseEndpoint(
            result=_FakeCompletion(parsed=None, refusal="I can't help with that.")
        )
        engine = make_engine(endpoint)

        with pytest.raises(EvaluationEngineError):
            engine.evaluate(evaluation_request())

    def test_missing_parsed_without_refusal_raises_engine_error(self):
        endpoint = _FakeParseEndpoint(result=_FakeCompletion(parsed=None, refusal=None))
        engine = make_engine(endpoint)

        with pytest.raises(EvaluationEngineError):
            engine.evaluate(evaluation_request())

    def test_provider_error_on_reference_generation_also_raises_engine_error(self):
        endpoint = _FakeParseEndpoint(exception=OpenAIError("boom"))
        engine = make_engine(endpoint)

        with pytest.raises(EvaluationEngineError):
            engine.generate_reference(
                ReferenceGenerationRequest(
                    french_text="x", exercise_type="TRANSLATION", difficulty="B1"
                )
            )
