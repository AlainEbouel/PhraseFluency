"""Pure text-identity rules (duplicate detection), shared by import-time
validation and the admin duplicate-cleanup action.

No FastAPI or SQLAlchemy imports — callers pass in the rows to compare.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


def normalize_french_text(text: str) -> str:
    return " ".join(text.strip().casefold().split())


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
