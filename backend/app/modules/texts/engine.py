"""Pure text-identity rules (duplicate detection), shared by import-time
validation and the admin duplicate-cleanup action.

No FastAPI or SQLAlchemy imports — callers pass in the rows to compare.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def normalize_french_text(text: str) -> str:
    return " ".join(text.strip().casefold().split())


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]


@dataclass(frozen=True)
class DuplicateGroup:
    french_text: str
    survivor_id: uuid.UUID
    duplicate_ids: list[uuid.UUID]


def group_duplicates(entries: list[tuple[uuid.UUID, str]]) -> list[DuplicateGroup]:
    """Groups entries sharing the same normalized french_text.

    `entries` must already be ordered oldest-first; the first occurrence of
    each normalized text survives, the rest are flagged as duplicates —
    same "first occurrence wins" rule as import-time batch dedup.
    """
    by_normalized: dict[str, list[tuple[uuid.UUID, str]]] = {}
    for text_id, french_text in entries:
        by_normalized.setdefault(normalize_french_text(french_text), []).append(
            (text_id, french_text)
        )

    groups = []
    for items in by_normalized.values():
        if len(items) > 1:
            survivor_id, survivor_text = items[0]
            groups.append(
                DuplicateGroup(
                    french_text=survivor_text,
                    survivor_id=survivor_id,
                    duplicate_ids=[text_id for text_id, _ in items[1:]],
                )
            )
    return groups


@dataclass(frozen=True)
class SharedSentenceGroup:
    sentence: str
    text_ids: list[uuid.UUID]


def group_by_shared_sentence(entries: list[tuple[uuid.UUID, str]]) -> list[SharedSentenceGroup]:
    """Groups texts that share at least one complete, normalized sentence -
    not a substring match. A text contributing the same sentence twice only
    counts once per group."""
    by_sentence: dict[str, list[tuple[uuid.UUID, str]]] = {}
    for text_id, french_text in entries:
        for sentence in split_sentences(french_text):
            by_sentence.setdefault(normalize_french_text(sentence), []).append((text_id, sentence))

    groups = []
    for items in by_sentence.values():
        distinct_ids = list(dict.fromkeys(text_id for text_id, _ in items))
        if len(distinct_ids) > 1:
            groups.append(SharedSentenceGroup(sentence=items[0][1], text_ids=distinct_ids))
    return groups
