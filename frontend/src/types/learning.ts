export type TextProgressStatus =
  | "UNSEEN"
  | "ACTIVE"
  | "WAITING_FOR_TEST_ASSIGNMENT"
  | "TEST_ASSIGNED"
  | "MASTERED"
  | "MANUALLY_ACQUIRED"
  | "DISABLED";

export type Verdict =
  | "CORRECT_NATURAL"
  | "CORRECT_UNNATURAL"
  | "CORRECT_WITH_WRITING_ISSUES"
  | "INCORRECT";

export interface Progress {
  status: TextProgressStatus;
  mastery_score: number;
  required_score: number;
  required_natural_equivalents: number;
  natural_count: number;
  unnatural_count: number;
  writing_issue_count: number;
  incorrect_count: number;
  hint_count: number;
  perfect_learning_record: boolean;
}

export interface Exercise {
  text_id: string;
  french_text: string;
  is_review: boolean;
  draft: string | null;
  hint_level: number;
  hints_revealed: string[];
  progress: Progress;
}

export interface NoExerciseAvailable {
  available: false;
  message: string;
}

export interface SubmitResult {
  verdict: Verdict;
  points_awarded: number;
  corrected_answer: string | null;
  feedback: string;
  preferred_translation: string;
  alternatives: string[];
  patterns: string[];
  error_categories: string[];
  progress: Progress;
  new_tests_created: number;
}
