"""Pure Python: no FastAPI, SQLAlchemy, or LLM-provider imports.

Dictation grading is a deterministic string comparison, not a linguistic
judgment call (ADR 0003 scopes EvaluationEngine to genuine naturalness/
meaning judgment, which doesn't apply here — there's exactly one correct
transcription). Persistence and orchestration live in service.py.
"""

from __future__ import annotations

import difflib
import re

from app.modules.evaluations.enums import Verdict

WRITING_ISSUE_SIMILARITY_THRESHOLD = 0.85


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _strip_punctuation_casefold(text: str) -> str:
    return re.sub(r"[^\w\s']", "", text).casefold()


def check_transcript(transcript: str, reference: str) -> tuple[Verdict, str | None]:
    """Compare a dictation transcript to the reference sentence.

    CORRECT_NATURAL: exact match. CORRECT_WITH_WRITING_ISSUES: only
    capitalization/punctuation differ, or the words match closely enough
    (same word count, high similarity) to read as spelling slips.
    INCORRECT: otherwise (wrong/missing/extra words).
    """
    normalized_transcript = _normalize_whitespace(transcript)
    normalized_reference = _normalize_whitespace(reference)
    if normalized_transcript == normalized_reference:
        return Verdict.CORRECT_NATURAL, None

    loose_transcript = _strip_punctuation_casefold(normalized_transcript)
    loose_reference = _strip_punctuation_casefold(normalized_reference)
    if loose_transcript == loose_reference:
        return Verdict.CORRECT_WITH_WRITING_ISSUES, reference

    same_word_count = len(loose_transcript.split()) == len(loose_reference.split())
    similarity = difflib.SequenceMatcher(None, loose_transcript, loose_reference).ratio()
    if same_word_count and similarity >= WRITING_ISSUE_SIMILARITY_THRESHOLD:
        return Verdict.CORRECT_WITH_WRITING_ISSUES, reference

    return Verdict.INCORRECT, reference
