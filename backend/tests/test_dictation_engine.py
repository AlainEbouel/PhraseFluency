from app.modules.dictation.engine import check_transcript
from app.modules.evaluations.enums import Verdict


class TestCheckTranscript:
    def test_exact_match_is_correct_natural(self):
        verdict, corrected = check_transcript(
            "I need to check that first.", "I need to check that first."
        )
        assert verdict == Verdict.CORRECT_NATURAL
        assert corrected is None

    def test_extra_whitespace_only_is_correct_natural(self):
        verdict, corrected = check_transcript(
            "  I need to check   that first. ", "I need to check that first."
        )
        assert verdict == Verdict.CORRECT_NATURAL
        assert corrected is None

    def test_capitalization_only_diff_is_writing_issue(self):
        verdict, corrected = check_transcript(
            "i need to check that first.", "I need to check that first."
        )
        assert verdict == Verdict.CORRECT_WITH_WRITING_ISSUES
        assert corrected == "I need to check that first."

    def test_missing_apostrophe_is_writing_issue(self):
        verdict, corrected = check_transcript("I dont think hes coming.", "I don't think he's coming.")
        assert verdict == Verdict.CORRECT_WITH_WRITING_ISSUES
        assert corrected == "I don't think he's coming."

    def test_single_word_misspelling_is_writing_issue(self):
        verdict, corrected = check_transcript(
            "I havent had time to reveiw it.", "I haven't had time to review it."
        )
        assert verdict == Verdict.CORRECT_WITH_WRITING_ISSUES
        assert corrected == "I haven't had time to review it."

    def test_wrong_word_is_incorrect(self):
        verdict, corrected = check_transcript(
            "I need to verify that tomorrow.", "I need to check that first."
        )
        assert verdict == Verdict.INCORRECT
        assert corrected == "I need to check that first."

    def test_missing_word_is_incorrect(self):
        verdict, corrected = check_transcript("I need to check first.", "I need to check that first.")
        assert verdict == Verdict.INCORRECT
        assert corrected == "I need to check that first."

    def test_unrelated_sentence_is_incorrect(self):
        verdict, corrected = check_transcript(
            "The weather is nice today.", "I need to check that first."
        )
        assert verdict == Verdict.INCORRECT
        assert corrected == "I need to check that first."
