import uuid

from pydantic import BaseModel


class ImportRowIn(BaseModel):
    french_text: str
    difficulty: str | None = None
    exercise_type: str | None = None
    contexts: list[str] = []
    grammar_concepts: list[str] = []
    skills: list[str] = []


class ImportRowPreview(BaseModel):
    row_number: int
    french_text: str
    difficulty: str
    exercise_type: str
    contexts: list[str]
    grammar_concepts: list[str]
    skills: list[str]
    status: str
    errors: list[str]


class ImportPreviewOut(BaseModel):
    filename: str
    rows: list[ImportRowPreview]
    total_rows: int
    valid_count: int
    duplicate_count: int
    invalid_count: int


class ImportConfirmIn(BaseModel):
    filename: str
    rows: list[ImportRowIn]


class ImportConfirmOut(BaseModel):
    import_batch_id: uuid.UUID
    total_rows: int
    imported_count: int
    duplicate_count: int
    rejected_count: int
