import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.learning.enums import TextProgressStatus
from app.modules.texts.models import Difficulty, ExerciseType
from app.modules.users.models import UserRole


class TextSummaryOut(BaseModel):
    id: uuid.UUID
    french_text: str
    difficulty: Difficulty
    exercise_type: ExerciseType
    enabled: bool
    created_at: datetime


class TextVersionOut(BaseModel):
    id: uuid.UUID
    french_text: str
    difficulty: Difficulty
    exercise_type: ExerciseType
    contexts: list[str]
    grammar_concepts: list[str]
    skills: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class TextDetailOut(BaseModel):
    id: uuid.UUID
    enabled: bool
    current_version: TextVersionOut
    version_history: list[TextVersionOut]


class UpdateTextVersionIn(BaseModel):
    french_text: str
    difficulty: Difficulty
    exercise_type: ExerciseType = ExerciseType.TRANSLATION
    contexts: list[str] = []
    grammar_concepts: list[str] = []
    skills: list[str] = []


class ImportBatchOut(BaseModel):
    id: uuid.UUID
    filename: str
    imported_by: uuid.UUID
    created_at: datetime
    total_rows: int
    imported_count: int
    duplicate_count: int
    rejected_count: int

    model_config = {"from_attributes": True}


class UserSummaryOut(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class UserTextBankItemOut(BaseModel):
    text_id: uuid.UUID
    french_text: str
    status: TextProgressStatus
    natural_count: int
    incorrect_count: int
    times_presented: int
