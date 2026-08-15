import uuid

from pydantic import BaseModel

from app.modules.evaluations.enums import Verdict


class DictationExerciseOut(BaseModel):
    text_id: uuid.UUID
    times_presented: int


class DictationUnavailableOut(BaseModel):
    available: bool = False
    message: str = "Aucun texte disponible pour la dictée pour le moment."


class DictationSubmitIn(BaseModel):
    text_id: uuid.UUID
    user_answer: str
    submission_id: str


class DictationSubmitOut(BaseModel):
    verdict: Verdict
    corrected_answer: str | None
    feedback: str
