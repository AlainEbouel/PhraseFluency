import uuid

from pydantic import BaseModel

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


class DraftIn(BaseModel):
    draft: str


class HintOut(BaseModel):
    hint_level: int
    hints_revealed: list[str]


class SubmitIn(BaseModel):
    user_answer: str
    input_method: InputMethod
    submission_id: str
    # Writing-issue retries are unlimited and never need this flag. An
    # unnatural verdict gets exactly one "want to improve?" offer: the
    # client sets this once that one retry has been used, and finalize
    # to accept the current result (revealing the answer) without retrying.
    finalize: bool = False
    unnatural_retry_used: bool = False


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
