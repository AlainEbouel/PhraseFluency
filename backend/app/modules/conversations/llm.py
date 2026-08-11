"""Direct OpenAI chat for the per-text contextual conversation feature.

Not behind EvaluationEngine: chat is free-form Q&A, not a linguistic
evaluation (ADR 0003 scopes EvaluationEngine to evaluation/reference/
explanation). Reuses EvaluationEngineError as the shared "LLM
temporarily unavailable" signal so callers only need one except clause.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from openai import OpenAI, OpenAIError

from app.modules.evaluations.engine import EvaluationEngineError

logger = logging.getLogger(__name__)

CHAT_PROMPT_VERSION = "chat-v1"

SYSTEM_PROMPT = """You are a helpful, encouraging linguistic assistant inside PhraseFluency, \
an app for learning natural American English through French-to-English production practice. \
You are discussing exactly one exercise with the learner.

You may answer questions about alternative formulations, naturalness, nuance, grammar, \
vocabulary, register, context, and pronunciation guidance related to THIS exercise. Stay \
focused on it; if asked something unrelated, briefly redirect to the exercise.

The exercise's accepted evaluation is fixed and shown separately to the learner — you may \
explain and add nuance, but do not contradict or attempt to change the verdict already \
given. Keep answers concise and conversational."""


@dataclass(frozen=True)
class ChatContext:
    french_text: str
    preferred_translation: str
    alternatives: list[str] = field(default_factory=list)
    user_answer: str | None = None
    verdict: str | None = None
    feedback: str | None = None


@dataclass(frozen=True)
class ChatMessageIn:
    role: str  # "USER" | "ASSISTANT"
    content: str


@dataclass(frozen=True)
class ChatReplyResult:
    content: str
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int


def _context_message(context: ChatContext) -> str:
    lines = [
        f"French text: {context.french_text}",
        f"Preferred translation: {context.preferred_translation}",
    ]
    if context.alternatives:
        lines.append(f"Accepted alternatives: {' | '.join(context.alternatives)}")
    if context.user_answer:
        lines.append(f"Learner's answer: {context.user_answer}")
    if context.verdict:
        lines.append(f"Evaluation verdict: {context.verdict}")
    if context.feedback:
        lines.append(f"Feedback already shown to the learner: {context.feedback}")
    return "\n".join(lines)


class ChatEngine:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30.0) -> None:
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self._model = model

    def reply(
        self, context: ChatContext, history: list[ChatMessageIn], question: str
    ) -> ChatReplyResult:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": _context_message(context)},
        ]
        for message in history:
            messages.append(
                {"role": "user" if message.role == "USER" else "assistant", "content": message.content}
            )
        messages.append({"role": "user", "content": question})

        try:
            completion = self._client.chat.completions.create(model=self._model, messages=messages)
        except OpenAIError as exc:
            logger.warning("OpenAI chat call failed: %s", exc)
            raise EvaluationEngineError(f"Chat provider failure: {exc}") from exc

        content = completion.choices[0].message.content
        if not content:
            raise EvaluationEngineError("OpenAI chat response had no content")

        usage = completion.usage
        return ChatReplyResult(
            content=content,
            model=self._model,
            prompt_version=CHAT_PROMPT_VERSION,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
