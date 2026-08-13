import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.evaluations.enums import InputMethod, Verdict
from app.modules.tests.models import TestAttemptStatus
from app.modules.texts.models import Difficulty


class TestAttemptOut(BaseModel):
    id: uuid.UUID
    attempt_number: int
    status: TestAttemptStatus
    started_at: datetime
    completed_at: datetime | None
    correct_count: int
    incorrect_count: int

    model_config = {"from_attributes": True}


class TestSummaryOut(BaseModel):
    id: uuid.UUID
    number: int
    status: str
    mastered_count: int
    total_count: int
    latest_attempt: TestAttemptOut | None


class TestTextOut(BaseModel):
    text_id: uuid.UUID
    french_text: str
    position: int
    consecutive_successes: int
    mastered: bool


class TestDetailOut(BaseModel):
    id: uuid.UUID
    number: int
    status: str
    texts: list[TestTextOut]
    attempts: list[TestAttemptOut]


class StartAttemptOut(BaseModel):
    attempt: TestAttemptOut
    is_retake: bool


class TestSubmitIn(BaseModel):
    text_id: uuid.UUID
    user_answer: str
    input_method: InputMethod
    submission_id: str


class TestSubmitOut(BaseModel):
    verdict: Verdict
    feedback: str
    corrected_answer: str | None
    writing_issues: list[str]
    consecutive_successes: int
    mastered: bool
    test_completed: bool
    difficulty: Difficulty
