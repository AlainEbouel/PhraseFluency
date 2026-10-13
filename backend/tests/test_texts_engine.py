import uuid

from app.modules.texts.engine import group_duplicates, normalize_french_text


class TestNormalizeFrenchText:
    def test_trims_and_collapses_whitespace(self):
        assert normalize_french_text("  Bonjour   le monde  ") == "bonjour le monde"

    def test_is_case_insensitive(self):
        assert normalize_french_text("Bonjour") == normalize_french_text("BONJOUR")


class TestGroupDuplicates:
    def test_no_duplicates_returns_no_groups(self):
        a, b = uuid.uuid4(), uuid.uuid4()
        groups = group_duplicates([(a, "Bonjour"), (b, "Au revoir")])
        assert groups == []

    def test_one_group_keeps_the_first_as_survivor(self):
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        groups = group_duplicates(
            [(a, "Bonjour le monde"), (b, "Au revoir"), (c, "  BONJOUR   le monde  ")]
        )
        assert len(groups) == 1
        assert groups[0].survivor_id == a
        assert groups[0].duplicate_ids == [c]
        assert groups[0].french_text == "Bonjour le monde"

    def test_multiple_independent_groups(self):
        a1, a2, b1, b2 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        groups = group_duplicates(
            [(a1, "Bonjour"), (b1, "Au revoir"), (a2, "bonjour"), (b2, "AU REVOIR")]
        )
        assert {g.survivor_id for g in groups} == {a1, b1}
        assert {g.duplicate_ids[0] for g in groups} == {a2, b2}
