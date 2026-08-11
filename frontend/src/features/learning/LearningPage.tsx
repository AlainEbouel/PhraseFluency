import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { alternativeAudioUrl, preferredAudioUrl } from "../../api/audio";
import {
  fetchExplanation,
  fetchNextExercise,
  increaseRepetition,
  acquireText,
  reevaluate,
  requestHint,
  saveDraft,
  skipExercise,
  submitAnswer,
  transcribeAudio,
} from "../../api/learning";
import type { Exercise, SubmitResult } from "../../types/learning";
import { AudioButton } from "../../components/AudioButton";
import { ChatPanel } from "../conversations/ChatPanel";
import { useAudioRecorder } from "../../hooks/useAudioRecorder";

const VERDICT_LABELS: Record<string, string> = {
  CORRECT_NATURAL: "Naturel ✓",
  CORRECT_UNNATURAL: "Correct, mais peu naturel",
  CORRECT_WITH_WRITING_ISSUES: "Correct (fautes d'écriture)",
  INCORRECT: "Incorrect",
};

type Phase = "loading" | "no-exercise" | "answering" | "feedback" | "load-error";

export function LearningPage() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [draft, setDraft] = useState("");
  const [hintsRevealed, setHintsRevealed] = useState<string[]>([]);
  const [inputMethod, setInputMethod] = useState<"KEYBOARD" | "VOICE">("KEYBOARD");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<SubmitResult | null>(null);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [showChat, setShowChat] = useState(false);
  const [noExerciseMessage, setNoExerciseMessage] = useState("");
  const draftTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadNext = useCallback(() => {
    setPhase("loading");
    setFeedback(null);
    setExplanation(null);
    setShowChat(false);
    setSubmitError(null);
    fetchNextExercise()
      .then((result) => {
        if ("available" in result && result.available === false) {
          setNoExerciseMessage(result.message);
          setPhase("no-exercise");
          return;
        }
        const ex = result as Exercise;
        setExercise(ex);
        setDraft(ex.draft ?? "");
        setHintsRevealed(ex.hints_revealed);
        setInputMethod("KEYBOARD");
        setPhase("answering");
      })
      .catch(() => setPhase("load-error"));
  }, []);

  useEffect(() => {
    loadNext();
  }, [loadNext]);

  function handleDraftChange(value: string) {
    setDraft(value);
    if (draftTimeoutRef.current) clearTimeout(draftTimeoutRef.current);
    draftTimeoutRef.current = setTimeout(() => {
      void saveDraft(value);
    }, 600);
  }

  const recorder = useAudioRecorder(async (blob) => {
    try {
      const { text } = await transcribeAudio(blob);
      setDraft(text);
      setInputMethod("VOICE");
    } catch {
      setSubmitError("La transcription a échoué. Vous pouvez taper votre réponse.");
    }
  });

  async function handleHint() {
    try {
      const result = await requestHint();
      setHintsRevealed(result.hints_revealed);
    } catch {
      setSubmitError("Impossible de charger l'indice pour le moment.");
    }
  }

  async function handleSubmit() {
    if (!exercise || !draft.trim()) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const submissionId = crypto.randomUUID();
      const result = await submitAnswer(draft, inputMethod, submissionId);
      setFeedback(result);
      setPhase("feedback");
    } catch (err) {
      setSubmitError(
        err instanceof ApiError
          ? err.message
          : "L'évaluation est temporairement indisponible. Réessayez."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSkip() {
    try {
      await skipExercise();
      loadNext();
    } catch {
      setSubmitError("Impossible de passer cet exercice pour le moment.");
    }
  }

  async function handleRepetition() {
    if (!exercise) return;
    try {
      const result = await increaseRepetition(exercise.text_id);
      setExercise({ ...exercise, progress: result.progress });
    } catch {
      setSubmitError("Impossible d'augmenter la répétition pour le moment.");
    }
  }

  async function handleAcquire() {
    if (!exercise) return;
    try {
      await acquireText(exercise.text_id);
      loadNext();
    } catch {
      setSubmitError("Impossible de marquer ce texte comme acquis.");
    }
  }

  async function handleReevaluate() {
    if (!exercise) return;
    try {
      const result = await reevaluate(exercise.text_id);
      setFeedback((prev) =>
        prev
          ? { ...prev, verdict: result.verdict as SubmitResult["verdict"], feedback: result.feedback, corrected_answer: result.corrected_answer }
          : prev
      );
    } catch {
      setSubmitError("La réévaluation a échoué. Réessayez.");
    }
  }

  async function handleExplanation() {
    if (!exercise) return;
    try {
      const result = await fetchExplanation(exercise.text_id);
      setExplanation(result.explanation);
    } catch {
      setSubmitError("L'explication est temporairement indisponible.");
    }
  }

  if (phase === "loading") {
    return <p>Chargement de l'exercice...</p>;
  }

  if (phase === "load-error") {
    return (
      <div>
        <p className="error-text">Impossible de charger l'exercice.</p>
        <button type="button" onClick={loadNext}>
          Réessayer
        </button>
      </div>
    );
  }

  if (phase === "no-exercise") {
    return <p>{noExerciseMessage}</p>;
  }

  if (!exercise) return null;

  const progressLabel = `${exercise.progress.natural_count}/${exercise.progress.required_natural_equivalents}`;

  return (
    <div className="learning-screen">
      {exercise.is_review && <span className="review-badge">Révision</span>}
      <div className="progress-indicator">Progression : {progressLabel}</div>

      <h2 className="french-text">{exercise.french_text}</h2>

      {phase === "answering" && (
        <div className="exercise-panel">
          <textarea
            className="answer-input"
            value={draft}
            onChange={(e) => handleDraftChange(e.target.value)}
            placeholder="Votre traduction en anglais..."
            rows={3}
          />

          <div className="exercise-actions">
            <button
              type="button"
              onClick={recorder.isRecording ? recorder.stop : recorder.start}
              className={recorder.isRecording ? "mic-button recording" : "mic-button"}
            >
              {recorder.isRecording ? "⏹ Arrêter" : "🎤 Dicter"}
            </button>
            <button type="button" onClick={handleHint} disabled={hintsRevealed.length >= 3}>
              Indice ({hintsRevealed.length}/3)
            </button>
            <button type="button" onClick={handleSkip}>
              Passer
            </button>
            <button type="button" onClick={handleRepetition}>
              +1 répétition
            </button>
            <button type="button" onClick={handleAcquire}>
              Marquer comme acquis
            </button>
          </div>

          {recorder.error && <p className="error-text">{recorder.error}</p>}

          {hintsRevealed.length > 0 && (
            <ul className="hints-list">
              {hintsRevealed.map((hint, i) => (
                <li key={i}>{hint}</li>
              ))}
            </ul>
          )}

          {submitError && (
            <p className="error-text">
              {submitError} <button type="button" onClick={handleSubmit}>Réessayer</button>
            </p>
          )}

          <button
            type="button"
            className="primary-button submit-button"
            onClick={handleSubmit}
            disabled={isSubmitting || !draft.trim()}
          >
            {isSubmitting ? "Évaluation..." : "Soumettre"}
          </button>
        </div>
      )}

      {phase === "feedback" && feedback && (
        <div className="feedback-panel">
          <div className={`verdict-badge verdict-${feedback.verdict.toLowerCase()}`}>
            {VERDICT_LABELS[feedback.verdict] ?? feedback.verdict}
          </div>
          <p className="points-awarded">+{feedback.points_awarded} point(s)</p>
          <p className="feedback-text">{feedback.feedback}</p>

          {feedback.corrected_answer && (
            <p className="corrected-answer">
              Forme correcte : <strong>{feedback.corrected_answer}</strong>
            </p>
          )}

          <div className="reference-block">
            <span>{feedback.preferred_translation}</span>
            <AudioButton src={preferredAudioUrl(exercise.text_id)} label={feedback.preferred_translation} />
          </div>

          {feedback.alternatives.map((alt, i) => (
            <div className="reference-block" key={i}>
              <span>{alt}</span>
              <AudioButton src={alternativeAudioUrl(exercise.text_id, i)} label={alt} />
            </div>
          ))}

          {feedback.patterns.length > 0 && (
            <div className="patterns-block">
              <strong>Formulations utiles :</strong>
              <ul>
                {feedback.patterns.map((pattern, i) => (
                  <li key={i}>{pattern}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="feedback-actions">
            <button type="button" onClick={handleExplanation}>
              Pourquoi ?
            </button>
            <button type="button" onClick={handleReevaluate}>
              Réévaluer
            </button>
            <button type="button" onClick={() => setShowChat((v) => !v)}>
              Demander à l'IA
            </button>
            <button type="button" className="primary-button" onClick={loadNext}>
              Suivant
            </button>
          </div>

          {explanation && <p className="explanation-text">{explanation}</p>}
          {showChat && <ChatPanel textId={exercise.text_id} />}
        </div>
      )}
    </div>
  );
}
