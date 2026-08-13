"""Raw CSV/JSON parsing into ImportRow objects (docs/product-requirements.md #17).

Kept separate from validation (engine.py): this module only turns file
bytes into structured rows; it does not judge whether a row is valid.
"""

from __future__ import annotations

import csv
import io
import json

from app.modules.imports.engine import ImportRow


class ImportParseError(ValueError):
    pass


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


def parse_csv(content: bytes) -> list[ImportRow]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportParseError("File is not valid UTF-8 text") from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "french_text" not in reader.fieldnames:
        raise ImportParseError("CSV must include a french_text column")

    rows = []
    for raw in reader:
        rows.append(
            ImportRow(
                french_text=raw.get("french_text") or "",
                difficulty=raw.get("difficulty") or None,
                exercise_type=raw.get("exercise_type") or None,
                contexts=_split_list(raw.get("contexts")),
                grammar_concepts=_split_list(raw.get("grammar_concepts") or raw.get("concepts")),
                skills=_split_list(raw.get("skills")),
            )
        )
    return rows


def parse_json(content: bytes) -> list[ImportRow]:
    try:
        data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportParseError(f"Invalid JSON: {exc}") from exc

    # Accept either a bare array, or a corpus envelope with metadata
    # (name/version/distribution/...) and the rows under a "texts" key —
    # the shape generated for the initial prototype corpus.
    if isinstance(data, dict) and isinstance(data.get("texts"), list):
        data = data["texts"]

    if not isinstance(data, list):
        raise ImportParseError(
            "JSON import must be a top-level array of objects, "
            "or an object with a top-level 'texts' array"
        )

    rows = []
    for raw in data:
        if not isinstance(raw, dict):
            raise ImportParseError("Each JSON import entry must be an object")
        rows.append(
            ImportRow(
                french_text=raw.get("french_text") or "",
                difficulty=raw.get("difficulty"),
                exercise_type=raw.get("exercise_type"),
                contexts=list(raw.get("contexts") or []),
                grammar_concepts=list(raw.get("grammar_concepts") or raw.get("concepts") or []),
                skills=list(raw.get("skills") or []),
            )
        )
    return rows


def parse_file(filename: str, content: bytes) -> list[ImportRow]:
    if filename.lower().endswith(".json"):
        return parse_json(content)
    return parse_csv(content)
