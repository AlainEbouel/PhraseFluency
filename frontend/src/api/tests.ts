import { apiRequest } from "./client";

export interface TestAttempt {
  id: string;
  attempt_number: number;
  status: "IN_PROGRESS" | "COMPLETED";
  started_at: string;
  completed_at: string | null;
  correct_count: number;
  incorrect_count: number;
}

export interface TestSummary {
  id: string;
  number: number;
  status: "AVAILABLE" | "IN_PROGRESS" | "COMPLETED";
  mastered_count: number;
  total_count: number;
  latest_attempt: TestAttempt | null;
}

export interface TestTextItem {
  text_id: string;
  french_text: string;
  position: number;
  consecutive_successes: number;
  mastered: boolean;
}

export interface TestDetail {
  id: string;
  number: number;
  status: string;
  texts: TestTextItem[];
  attempts: TestAttempt[];
}

export interface TestSubmitResult {
  verdict: string;
  feedback: string;
  corrected_answer: string | null;
  consecutive_successes: number;
  mastered: boolean;
  test_completed: boolean;
}

export function fetchTests(): Promise<TestSummary[]> {
  return apiRequest("/api/v1/tests");
}

export function fetchTestDetail(testId: string): Promise<TestDetail> {
  return apiRequest(`/api/v1/tests/${testId}`);
}

export function startTest(testId: string): Promise<{ attempt: TestAttempt; is_retake: boolean }> {
  return apiRequest(`/api/v1/tests/${testId}/start`, { method: "POST" });
}

export function submitTestAnswer(
  testId: string,
  textId: string,
  userAnswer: string,
  submissionId: string
): Promise<TestSubmitResult> {
  return apiRequest(`/api/v1/tests/${testId}/submit`, {
    method: "POST",
    body: JSON.stringify({
      text_id: textId,
      user_answer: userAnswer,
      input_method: "KEYBOARD",
      submission_id: submissionId,
    }),
  });
}
