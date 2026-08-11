import uuid

import pytest
from openai import OpenAIError

from app.modules.conversations.llm import ChatContext, ChatEngine, ChatMessageIn
from app.modules.conversations.models import MessageRole
from app.modules.conversations.service import ask, get_messages, get_or_create_conversation
from app.modules.evaluations.engine import EvaluationEngineError
from app.modules.texts.models import Difficulty, ExerciseType, Text, TextVersion
from app.modules.users.models import User, UserRole


class _FakeUsage:
    def __init__(self, prompt_tokens, completion_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content, usage=(20, 10)):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage(*usage) if usage is not None else None


class _FakeCreateEndpoint:
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
    def __init__(self, create_endpoint):
        completions = type("C", (), {"create": staticmethod(create_endpoint)})()
        self.chat = type("Chat", (), {"completions": completions})()


def make_chat_engine(create_endpoint: _FakeCreateEndpoint) -> ChatEngine:
    engine = ChatEngine(api_key="sk-test", model="gpt-4o-mini")
    engine._client = _FakeClient(create_endpoint)
    return engine


def make_user(db_session) -> User:
    user = User(email=f"{uuid.uuid4()}@phrasefluency.app", password_hash="x", role=UserRole.USER)
    db_session.add(user)
    db_session.flush()
    return user


def make_text(db_session) -> Text:
    text = Text(source="test")
    db_session.add(text)
    db_session.flush()
    version = TextVersion(
        text_id=text.id,
        french_text=f"Texte {uuid.uuid4()}",
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


class TestChatEngine:
    def test_reply_maps_content_and_tokens(self):
        endpoint = _FakeCreateEndpoint(result=_FakeCompletion("Here's a nuance point."))
        engine = make_chat_engine(endpoint)

        result = engine.reply(
            ChatContext(french_text="x", preferred_translation="y"), [], "Why is this natural?"
        )

        assert result.content == "Here's a nuance point."
        assert result.input_tokens == 20
        assert result.output_tokens == 10

    def test_history_is_forwarded_with_correct_roles(self):
        endpoint = _FakeCreateEndpoint(result=_FakeCompletion("ok"))
        engine = make_chat_engine(endpoint)

        engine.reply(
            ChatContext(french_text="x", preferred_translation="y"),
            [ChatMessageIn(role="USER", content="first question"), ChatMessageIn(role="ASSISTANT", content="first answer")],
            "second question",
        )

        sent = endpoint.calls[0]["messages"]
        roles = [m["role"] for m in sent]
        assert roles == ["system", "system", "user", "assistant", "user"]

    def test_context_included_in_system_message(self):
        endpoint = _FakeCreateEndpoint(result=_FakeCompletion("ok"))
        engine = make_chat_engine(endpoint)

        engine.reply(
            ChatContext(
                french_text="Bonjour",
                preferred_translation="Hello",
                user_answer="Hi there",
                verdict="CORRECT_NATURAL",
            ),
            [],
            "question",
        )

        context_message = endpoint.calls[0]["messages"][1]["content"]
        assert "Bonjour" in context_message
        assert "Hi there" in context_message
        assert "CORRECT_NATURAL" in context_message

    def test_provider_error_raises_evaluation_engine_error(self):
        endpoint = _FakeCreateEndpoint(exception=OpenAIError("boom"))
        engine = make_chat_engine(endpoint)

        with pytest.raises(EvaluationEngineError):
            engine.reply(ChatContext(french_text="x", preferred_translation="y"), [], "question")

    def test_empty_content_raises_evaluation_engine_error(self):
        endpoint = _FakeCreateEndpoint(result=_FakeCompletion(None))
        engine = make_chat_engine(endpoint)

        with pytest.raises(EvaluationEngineError):
            engine.reply(ChatContext(french_text="x", preferred_translation="y"), [], "question")


class TestConversationService:
    def test_get_or_create_conversation_is_idempotent(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)

        first = get_or_create_conversation(db_session, user.id, text.id)
        second = get_or_create_conversation(db_session, user.id, text.id)

        assert first.id == second.id

    def test_ask_persists_user_and_assistant_messages_in_order(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)
        endpoint = _FakeCreateEndpoint(result=_FakeCompletion("That's a great question!"))
        engine = make_chat_engine(endpoint)

        reply = ask(db_session, engine, user.id, text.id, "Why not use 'yet'?")

        assert reply.role == MessageRole.ASSISTANT
        assert reply.content == "That's a great question!"

        conversation = get_or_create_conversation(db_session, user.id, text.id)
        messages = get_messages(db_session, conversation.id)
        assert [m.role for m in messages] == [MessageRole.USER, MessageRole.ASSISTANT]
        assert messages[0].content == "Why not use 'yet'?"

    def test_second_question_includes_first_exchange_as_history(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)
        endpoint = _FakeCreateEndpoint(result=_FakeCompletion("first answer"))
        engine = make_chat_engine(endpoint)
        ask(db_session, engine, user.id, text.id, "first question")

        endpoint._result = _FakeCompletion("second answer")
        ask(db_session, engine, user.id, text.id, "second question")

        sent_messages = endpoint.calls[-1]["messages"]
        contents = [m["content"] for m in sent_messages]
        assert "first question" in contents
        assert "first answer" in contents

    def test_provider_failure_does_not_persist_any_message(self, db_session):
        user = make_user(db_session)
        text = make_text(db_session)
        endpoint = _FakeCreateEndpoint(exception=OpenAIError("boom"))
        engine = make_chat_engine(endpoint)

        with pytest.raises(EvaluationEngineError):
            ask(db_session, engine, user.id, text.id, "question")

        conversation = get_or_create_conversation(db_session, user.id, text.id)
        assert get_messages(db_session, conversation.id) == []
