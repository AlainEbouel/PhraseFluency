import { apiRequest } from "./client";
import type {
  Difficulty,
  Exercise,
  ExploreResult,
  LevelRequired,
  NoExerciseAvailable,
  PendingSubmitResult,
  Progress,
  SubmitResult,
} from "../types/learning";

export function fetchNextExercise(): Promise<Exercise | LevelRequired | NoExerciseAvailable> {
  return apiRequest("/api/v1/learning/next");
}

export function chooseLevel(level: Difficulty): Promise<void> {
  return apiRequest("/api/v1/learning/level", {
    method: "POST",
    body: JSON.stringify({ level }),
  });
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
  submissionId: string,
  options?: { finalize?: boolean; unnaturalRetryUsed?: boolean }
): Promise<SubmitResult | PendingSubmitResult> {
  return apiRequest("/api/v1/learning/submit", {
    method: "POST",
    body: JSON.stringify({
      user_answer: userAnswer,
      input_method: inputMethod,
      submission_id: submissionId,
      finalize: options?.finalize ?? false,
      unnatural_retry_used: options?.unnaturalRetryUsed ?? false,
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
  return apiRequest<{
    verdict: string;
    feedback: string;
    corrected_answer: string | null;
    usage_note_alternative: string | null;
  }>(`/api/v1/learning/${textId}/reevaluate`, { method: "POST" });
}

export function fetchExplanation(textId: string) {
  return apiRequest<{ explanation: string }>(`/api/v1/learning/${textId}/explanation`);
}

export function exploreAlternative(textId: string, userAnswer: string): Promise<ExploreResult> {
  return apiRequest(`/api/v1/learning/${textId}/explore`, {
    method: "POST",
    body: JSON.stringify({ user_answer: userAnswer }),
  });
}

export function transcribeAudio(blob: Blob): Promise<{ text: string }> {
  const formData = new FormData();
  formData.append("file", blob, "recording.webm");
  return apiRequest("/api/v1/audio/transcribe", {
    method: "POST",
    body: formData,
  });
}
