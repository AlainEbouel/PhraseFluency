import uuid

from pydantic import BaseModel, Field

from app.modules.evaluations.enums import InputMethod, Verdict
from app.modules.learning.enums import TextProgressStatus
from app.modules.texts.models import Difficulty


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


class LevelRequiredOut(BaseModel):
    requires_level_selection: bool = True


class ChooseLevelIn(BaseModel):
    level: Difficulty


class LevelSettingsIn(BaseModel):
    target_level: Difficulty | None = None
    current_level_share: float | None = Field(default=None, ge=0.0, le=1.0)


class LevelSettingsOut(BaseModel):
    accepted: bool = True
    current_level: Difficulty | None
    target_level: Difficulty | None
    current_level_share: float

    model_config = {"from_attributes": True}


class LevelSettingsRejectedOut(BaseModel):
    accepted: bool = False
    message: str
    suggested_target_level: Difficulty


class DraftIn(BaseModel):
    draft: str


class HintOut(BaseModel):
    hint_level: int
    hints_revealed: list[str]


class SubmitIn(BaseModel):
    user_answer: str
    input_method: InputMethod
    submission_id: str
    # Writing-issue retries are unlimited and never touch this field. A
    # CORRECT_UNNATURAL/INCORRECT verdict gets up to MAX_RETRIES "want to
    # improve?" offers: retry_count is how many of those the client has
    # already used before THIS submission (0 for the original attempt).
    # finalize accepts the current pending result (revealing the answer)
    # without retrying.
    finalize: bool = False
    retry_count: int = Field(default=0, ge=0, le=2)


class SubmitOut(BaseModel):
    committed: bool = True
    verdict: Verdict
    points_awarded: int
    corrected_answer: str | None
    usage_note_alternative: str | None
    feedback: str
    writing_issues: list[str]
    preferred_translation: str
    alternatives: list[str]
    patterns: list[str]
    error_categories: list[str]
    progress: ProgressOut
    new_tests_created: int
    difficulty: Difficulty


class PendingSubmitOut(BaseModel):
    committed: bool = False
    verdict: Verdict
    feedback: str
    writing_issues: list[str]
    difficulty: Difficulty


class RepetitionOut(BaseModel):
    progress: ProgressOut


class AcquireOut(BaseModel):
    progress: ProgressOut


class ReevaluateOut(BaseModel):
    verdict: Verdict
    feedback: str
    corrected_answer: str | None
    usage_note_alternative: str | None


class ExplanationOut(BaseModel):
    explanation: str


class ExploreIn(BaseModel):
    user_answer: str


class ExploreOut(BaseModel):
    """A free, unlimited, zero-consequence check: never touches Attempt,
    Evaluation history, or UserTextProgress — purely exploratory."""

    verdict: Verdict
    meaning_preserved: bool
    corrected_answer: str | None
    usage_note_alternative: str | None
    feedback: str
    writing_issues: list[str]
