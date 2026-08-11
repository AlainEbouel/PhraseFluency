import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.conversations.llm import ChatContext, ChatEngine, ChatMessageIn
from app.modules.conversations.models import ConversationMessage, MessageRole, TextConversation
from app.modules.evaluations.models import Attempt, Evaluation
from app.modules.texts.models import LinguisticReference, Text, TextVersion
from app.shared.ai_usage import record_ai_usage
from app.shared.mixins import utcnow
from app.shared.models import AIOperation


def get_or_create_conversation(
    db: Session, user_id: uuid.UUID, text_id: uuid.UUID
) -> TextConversation:
    conversation = db.scalar(
        select(TextConversation).where(
            TextConversation.user_id == user_id, TextConversation.text_id == text_id
        )
    )
    if conversation is None:
        conversation = TextConversation(user_id=user_id, text_id=text_id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation


def get_messages(db: Session, conversation_id: uuid.UUID) -> list[ConversationMessage]:
    return db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
    ).all()


def _build_context(db: Session, user_id: uuid.UUID, text_version: TextVersion) -> ChatContext:
    reference = db.scalar(
        select(LinguisticReference).where(LinguisticReference.text_version_id == text_version.id)
    )
    latest_attempt = db.scalar(
        select(Attempt)
        .where(Attempt.user_id == user_id, Attempt.text_version_id == text_version.id)
        .order_by(Attempt.created_at.desc())
        .limit(1)
    )

    user_answer = None
    verdict = None
    feedback = None
    if latest_attempt is not None:
        user_answer = latest_attempt.user_answer
        evaluation = db.get(Evaluation, latest_attempt.active_evaluation_id)
        if evaluation is not None:
            verdict = evaluation.verdict.value
            feedback = evaluation.feedback

    return ChatContext(
        french_text=text_version.french_text,
        preferred_translation=reference.preferred_translation if reference else "",
        alternatives=list(reference.alternatives) if reference else [],
        user_answer=user_answer,
        verdict=verdict,
        feedback=feedback,
    )


def ask(
    db: Session,
    chat_engine: ChatEngine,
    user_id: uuid.UUID,
    text_id: uuid.UUID,
    question: str,
) -> ConversationMessage:
    text = db.get(Text, text_id)
    text_version = db.get(TextVersion, text.current_version_id)

    conversation = get_or_create_conversation(db, user_id, text_id)
    history = [
        ChatMessageIn(role=m.role.value, content=m.content)
        for m in get_messages(db, conversation.id)
    ]
    context = _build_context(db, user_id, text_version)

    result = chat_engine.reply(context, history, question)

    db.add(ConversationMessage(conversation_id=conversation.id, role=MessageRole.USER, content=question))

    assistant_message = ConversationMessage(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=result.content,
        model=result.model,
    )
    db.add(assistant_message)

    conversation.updated_at = utcnow()
    db.add(conversation)

    record_ai_usage(
        db,
        operation=AIOperation.CHAT,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        user_id=user_id,
    )

    db.commit()
    db.refresh(assistant_message)
    return assistant_message
