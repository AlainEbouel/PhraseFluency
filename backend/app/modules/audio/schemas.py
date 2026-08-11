from pydantic import BaseModel


class TranscriptionOut(BaseModel):
    text: str
