import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.conversations.models import MessageRole


class MessageOut(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AskIn(BaseModel):
    question: str


class ConversationOut(BaseModel):
    messages: list[MessageOut]
