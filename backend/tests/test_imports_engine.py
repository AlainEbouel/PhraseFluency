from app.modules.imports.engine import ImportRow, normalize_french_text, validate_and_dedupe_rows
from app.modules.imports.parsing import ImportParseError, parse_csv, parse_json


class TestNormalizeFrenchText:
    def test_trims_and_collapses_whitespace(self):
        assert normalize_french_text("  Bonjour   le monde  ") == "bonjour le monde"

    def test_is_case_insensitive(self):
        assert normalize_french_text("Bonjour") == normalize_french_text("BONJOUR")


class TestValidateAndDedupeRows:
    def test_missing_french_text_is_invalid(self):
        results = validate_and_dedupe_rows([ImportRow(french_text="")], existing_normalized_texts=set())
        assert results[0].status == "INVALID"
        assert "french_text is required" in results[0].errors

    def test_invalid_difficulty_is_rejected(self):
        results = validate_and_dedupe_rows(
            [ImportRow(french_text="Bonjour", difficulty="Z9")], existing_normalized_texts=set()
        )
        assert results[0].status == "INVALID"

    def test_missing_difficulty_defaults_to_b2(self):
        results = validate_and_dedupe_rows([ImportRow(french_text="Bonjour")], existing_normalized_texts=set())
        assert results[0].status == "VALID"
        assert results[0].difficulty == "B2"

    def test_missing_exercise_type_defaults_to_translation(self):
        results = validate_and_dedupe_rows([ImportRow(french_text="Bonjour")], existing_normalized_texts=set())
        assert results[0].exercise_type == "TRANSLATION"

    def test_duplicate_against_existing_texts(self):
        results = validate_and_dedupe_rows(
            [ImportRow(french_text="Bonjour le monde")],
            existing_normalized_texts={"bonjour le monde"},
        )
        assert results[0].status == "DUPLICATE"

    def test_duplicate_within_same_batch_keeps_first_only(self):
        rows = [ImportRow(french_text="Bonjour"), ImportRow(french_text="  BONJOUR  ")]
        results = validate_and_dedupe_rows(rows, existing_normalized_texts=set())
        assert results[0].status == "VALID"
        assert results[1].status == "DUPLICATE"

    def test_row_numbers_are_one_indexed_and_ordered(self):
        rows = [ImportRow(french_text="a"), ImportRow(french_text="b")]
        results = validate_and_dedupe_rows(rows, existing_normalized_texts=set())
        assert [r.row_number for r in results] == [1, 2]

    def test_contexts_and_skills_pass_through(self):
        results = validate_and_dedupe_rows(
            [ImportRow(french_text="Bonjour", contexts=["professional"], skills=["listening"])],
            existing_normalized_texts=set(),
        )
        assert results[0].contexts == ["professional"]
        assert results[0].skills == ["listening"]


class TestParseCsv:
    def test_parses_minimal_column(self):
        content = "french_text\nBonjour le monde\n".encode("utf-8")
        rows = parse_csv(content)
        assert len(rows) == 1
        assert rows[0].french_text == "Bonjour le monde"

    def test_parses_semicolon_separated_lists(self):
        content = (
            "french_text,contexts,skills\n"
            "Bonjour,professional;meeting,listening;speaking\n"
        ).encode("utf-8")
        rows = parse_csv(content)
        assert rows[0].contexts == ["professional", "meeting"]
        assert rows[0].skills == ["listening", "speaking"]

    def test_concepts_alias_maps_to_grammar_concepts(self):
        content = "french_text,concepts\nBonjour,present_perfect\n".encode("utf-8")
        rows = parse_csv(content)
        assert rows[0].grammar_concepts == ["present_perfect"]

    def test_missing_french_text_column_raises(self):
        content = "some_other_column\nvalue\n".encode("utf-8")
        try:
            parse_csv(content)
            assert False, "expected ImportParseError"
        except ImportParseError:
            pass


class TestParseJson:
    def test_parses_array_of_objects(self):
        content = b'[{"french_text": "Bonjour", "difficulty": "B1"}]'
        rows = parse_json(content)
        assert len(rows) == 1
        assert rows[0].french_text == "Bonjour"
        assert rows[0].difficulty == "B1"

    def test_non_array_top_level_raises(self):
        content = b'{"french_text": "Bonjour"}'
        try:
            parse_json(content)
            assert False, "expected ImportParseError"
        except ImportParseError:
            pass

    def test_concepts_alias_maps_to_grammar_concepts(self):
        content = b'[{"french_text": "Bonjour", "concepts": ["present_perfect"]}]'
        rows = parse_json(content)
        assert rows[0].grammar_concepts == ["present_perfect"]
