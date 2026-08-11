import uuid

from pydantic import BaseModel

from app.modules.evaluations.enums import InputMethod, Verdict
from app.modules.learning.enums import TextProgressStatus


class ProgressOut(BaseModel):
    status: TextProgressStatus
    mastery_score: int
    required_score: int
    required_natural_equivalents: int
    natural_count: int
    unnatural_count: int
    writing_issue_count: int
    incorrect_count: int
    hint_count: int
    perfect_learning_record: bool

    model_config = {"from_attributes": True}


class ExerciseOut(BaseModel):
    text_id: uuid.UUID
    french_text: str
    is_review: bool
    draft: str | None
    hint_level: int
    hints_revealed: list[str]
    progress: ProgressOut


class NoExerciseAvailableOut(BaseModel):
    available: bool = False
    message: str


class DraftIn(BaseModel):
    draft: str


class HintOut(BaseModel):
    hint_level: int
    hints_revealed: list[str]


class SubmitIn(BaseModel):
    user_answer: str
    input_method: InputMethod
    submission_id: str


class SubmitOut(BaseModel):
    verdict: Verdict
    points_awarded: int
    corrected_answer: str | None
    feedback: str
    preferred_translation: str
    alternatives: list[str]
    patterns: list[str]
    error_categories: list[str]
    progress: ProgressOut
    new_tests_created: int


class RepetitionOut(BaseModel):
    progress: ProgressOut


class AcquireOut(BaseModel):
    progress: ProgressOut


class ReevaluateOut(BaseModel):
    verdict: Verdict
    feedback: str
    corrected_answer: str | None


class ExplanationOut(BaseModel):
    explanation: str
