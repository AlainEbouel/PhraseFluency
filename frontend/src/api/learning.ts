import { apiRequest } from "./client";
import type { Exercise, NoExerciseAvailable, Progress, SubmitResult } from "../types/learning";

export function fetchNextExercise(): Promise<Exercise | NoExerciseAvailable> {
  return apiRequest("/api/v1/learning/next");
}

export function saveDraft(draft: string): Promise<void> {
  return apiRequest("/api/v1/learning/draft", {
    method: "PUT",
    body: JSON.stringify({ draft }),
  });
}

export function requestHint(): Promise<{ hint_level: number; hints_revealed: string[] }> {
  return apiRequest("/api/v1/learning/hint", { method: "POST" });
}

export function submitAnswer(
  userAnswer: string,
  inputMethod: "KEYBOARD" | "VOICE",
  submissionId: string
): Promise<SubmitResult> {
  return apiRequest("/api/v1/learning/submit", {
    method: "POST",
    body: JSON.stringify({
      user_answer: userAnswer,
      input_method: inputMethod,
      submission_id: submissionId,
    }),
  });
}

export function skipExercise(): Promise<void> {
  return apiRequest("/api/v1/learning/skip", { method: "POST" });
}

export function increaseRepetition(textId: string): Promise<{ progress: Progress }> {
  return apiRequest(`/api/v1/learning/${textId}/repetition`, { method: "POST" });
}

export function acquireText(textId: string): Promise<{ progress: Progress }> {
  return apiRequest(`/api/v1/learning/${textId}/acquire`, { method: "POST" });
}

export function reevaluate(textId: string) {
  return apiRequest<{ verdict: string; feedback: string; corrected_answer: string | null }>(
    `/api/v1/learning/${textId}/reevaluate`,
    { method: "POST" }
  );
}

export function fetchExplanation(textId: string) {
  return apiRequest<{ explanation: string }>(`/api/v1/learning/${textId}/explanation`);
}

export function transcribeAudio(blob: Blob): Promise<{ text: string }> {
  const formData = new FormData();
  formData.append("file", blob, "recording.webm");
  return apiRequest("/api/v1/audio/transcribe", {
    method: "POST",
    body: formData,
  });
}
