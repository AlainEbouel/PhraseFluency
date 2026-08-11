import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.conversations import service
from app.modules.conversations.llm import ChatEngine
from app.modules.conversations.schemas import AskIn, ConversationOut, MessageOut
from app.modules.evaluations.engine import EvaluationEngineError
from app.modules.texts.models import Text
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/texts", tags=["conversations"])

_chat_engine: ChatEngine | None = None


def get_chat_engine() -> ChatEngine:
    global _chat_engine
    if _chat_engine is None:
        settings = get_settings()
        _chat_engine = ChatEngine(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    return _chat_engine


@router.get("/{text_id}/conversation", response_model=ConversationOut)
def get_conversation(
    text_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = service.get_or_create_conversation(db, user.id, text_id)
    messages = service.get_messages(db, conversation.id)
    return ConversationOut(messages=[MessageOut.model_validate(m) for m in messages])


@router.post("/{text_id}/conversation/ask", response_model=MessageOut)
def ask(
    text_id: uuid.UUID,
    payload: AskIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    text = db.get(Text, text_id)
    if text is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Text not found")

    engine = get_chat_engine()
    try:
        message = service.ask(db, engine, user.id, text_id, payload.question)
    except EvaluationEngineError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Chat is temporarily unavailable, please retry: {exc}",
        ) from exc

    return MessageOut.model_validate(message)
