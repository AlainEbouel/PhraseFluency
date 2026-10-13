import uuid

from app.modules.texts.engine import (
    group_by_shared_sentence,
    group_duplicates,
    normalize_french_text,
    split_sentences,
)


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


class TestSplitSentences:
    def test_splits_on_terminal_punctuation(self):
        assert split_sentences("Bonjour le monde. Il fait beau!") == [
            "Bonjour le monde.",
            "Il fait beau!",
        ]

    def test_trims_extra_whitespace(self):
        assert split_sentences("  Bonjour.   Au revoir.  ") == ["Bonjour.", "Au revoir."]

    def test_no_terminal_punctuation_is_one_sentence(self):
        assert split_sentences("Bonjour le monde") == ["Bonjour le monde"]

    def test_question_mark(self):
        assert split_sentences("Comment vas-tu? Je vais bien.") == [
            "Comment vas-tu?",
            "Je vais bien.",
        ]


class TestGroupBySharedSentence:
    def test_no_shared_sentence_returns_no_groups(self):
        a, b = uuid.uuid4(), uuid.uuid4()
        groups = group_by_shared_sentence([(a, "Bonjour. Ça va."), (b, "Au revoir. À bientôt.")])
        assert groups == []

    def test_two_texts_sharing_one_sentence_form_a_group(self):
        a, b = uuid.uuid4(), uuid.uuid4()
        groups = group_by_shared_sentence(
            [(a, "Il fait beau aujourd'hui. Je vais à la plage."), (b, "Il fait beau aujourd'hui. Je reste à la maison.")]
        )
        assert len(groups) == 1
        assert set(groups[0].text_ids) == {a, b}
        assert groups[0].sentence == "Il fait beau aujourd'hui."

    def test_normalization_applies_case_and_whitespace(self):
        a, b = uuid.uuid4(), uuid.uuid4()
        groups = group_by_shared_sentence(
            [(a, "Bonjour le monde. Suite A."), (b, "  BONJOUR   le monde.  Suite B.")]
        )
        assert len(groups) == 1
        assert set(groups[0].text_ids) == {a, b}

    def test_more_than_two_texts_in_one_group(self):
        a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        common = "Marie va au marché le samedi matin."
        groups = group_by_shared_sentence(
            [
                (a, f"{common} Elle achète des pommes."),
                (b, f"{common} Elle achète du pain."),
                (c, f"{common} Elle rencontre une amie."),
                (d, f"{common} Elle rentre à pied."),
            ]
        )
        assert len(groups) == 1
        assert set(groups[0].text_ids) == {a, b, c, d}

    def test_a_single_text_is_not_grouped_with_itself(self):
        a = uuid.uuid4()
        groups = group_by_shared_sentence([(a, "Bonjour. Bonjour.")])
        assert groups == []
