import { apiRequest } from "./client";

export interface DictationExercise {
  text_id: string;
  times_presented: number;
}

export interface DictationUnavailable {
  available: false;
  message: string;
}

export interface DictationSubmitResult {
  verdict: string;
  corrected_answer: string | null;
  feedback: string;
}

export function fetchNextDictation(): Promise<DictationExercise | DictationUnavailable> {
  return apiRequest("/api/v1/dictation/next");
}

export function submitDictationAnswer(
  textId: string,
  userAnswer: string,
  submissionId: string
): Promise<DictationSubmitResult> {
  return apiRequest("/api/v1/dictation/submit", {
    method: "POST",
    body: JSON.stringify({ text_id: textId, user_answer: userAnswer, submission_id: submissionId }),
  });
}
