import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { alternativeAudioUrl, preferredAudioUrl } from "../../api/audio";
import {
  chooseLevel,
  exploreAlternative,
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
import type {
  Difficulty,
  Exercise,
  ExploreResult,
  PendingSubmitResult,
  SubmitResult,
} from "../../types/learning";
import { AudioButton } from "../../components/AudioButton";
import { Meter } from "../../components/Meter";
import { VerdictBadge } from "../../components/VerdictBadge";
import { ChatPanel } from "../conversations/ChatPanel";
import { useAudioRecorder } from "../../hooks/useAudioRecorder";
import { DIFFICULTY_LABELS, DIFFICULTY_PILL } from "../../constants/difficulty";

const SELECTABLE_LEVELS: Difficulty[] = ["A1", "A2", "B1", "B2", "C1", "C2"];

type Phase =
  | "loading"
  | "needs-level"
  | "no-exercise"
  | "answering"
  | "pending-writing-issue"
  | "pending-unnatural-offer"
  | "feedback"
  | "load-error";

export function LearningPage() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [draft, setDraft] = useState("");
  const [hintsRevealed, setHintsRevealed] = useState<string[]>([]);
  const [inputMethod, setInputMethod] = useState<"KEYBOARD" | "VOICE">("KEYBOARD");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<SubmitResult | null>(null);
  const [pendingResult, setPendingResult] = useState<PendingSubmitResult | null>(null);
  const [submittedAnswer, setSubmittedAnswer] = useState("");
  const [explanation, setExplanation] = useState<string | null>(null);
  const [showChat, setShowChat] = useState(false);
  const [noExerciseMessage, setNoExerciseMessage] = useState("");
  const [repetitionMessage, setRepetitionMessage] = useState<string | null>(null);
  const [hintsDisabledForRetry, setHintsDisabledForRetry] = useState(false);
  const [unnaturalRetryUsed, setUnnaturalRetryUsed] = useState(false);
  const [exploreInput, setExploreInput] = useState("");
  const [exploreResult, setExploreResult] = useState<ExploreResult | null>(null);
  const [isExploring, setIsExploring] = useState(false);
  const [exploreError, setExploreError] = useState<string | null>(null);
  const [isChoosingLevel, setIsChoosingLevel] = useState(false);
  const [levelError, setLevelError] = useState<string | null>(null);
  const draftTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadNext = useCallback(() => {
    setPhase("loading");
    setFeedback(null);
    setPendingResult(null);
    setExplanation(null);
    setShowChat(false);
    setSubmitError(null);
    setRepetitionMessage(null);
    setHintsDisabledForRetry(false);
    setUnnaturalRetryUsed(false);
    setExploreInput("");
    setExploreResult(null);
    setExploreError(null);
    fetchNextExercise()
      .then((result) => {
        if ("requires_level_selection" in result) {
          setPhase("needs-level");
          return;
        }
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

  async function handleChooseLevel(level: Difficulty) {
    setIsChoosingLevel(true);
    setLevelError(null);
    try {
      await chooseLevel(level);
      loadNext();
    } catch {
      setLevelError("Impossible d'enregistrer ce niveau pour le moment. Réessayez.");
    } finally {
      setIsChoosingLevel(false);
    }
  }

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

  async function performSubmit(finalize: boolean) {
    if (!exercise || !draft.trim() || recorder.isRecording) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const submissionId = crypto.randomUUID();
      const result = await submitAnswer(draft, inputMethod, submissionId, {
        finalize,
        unnaturalRetryUsed,
      });
      setSubmittedAnswer(draft);
      if (result.committed) {
        setFeedback(result);
        setPendingResult(null);
        setHintsDisabledForRetry(false);
        setUnnaturalRetryUsed(false);
        setPhase("feedback");
      } else {
        setPendingResult(result);
        setPhase(
          result.verdict === "CORRECT_WITH_WRITING_ISSUES"
            ? "pending-writing-issue"
            : "pending-unnatural-offer"
        );
      }
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

  function handleSubmit() {
    return performSubmit(false);
  }

  function handleFinalize() {
    return performSubmit(true);
  }

  function handleRetryWritingIssue() {
    setPendingResult(null);
    setSubmitError(null);
    setPhase("answering");
  }

  function handleImproveUnnatural() {
    setPendingResult(null);
    setSubmitError(null);
    setHintsDisabledForRetry(true);
    setUnnaturalRetryUsed(true);
    setPhase("answering");
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
      setRepetitionMessage(
        `Répétition augmentée : ${result.progress.required_natural_equivalents} réponses naturelles requises maintenant.`
      );
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

  async function handleExplore() {
    if (!exercise || !exploreInput.trim()) return;
    setIsExploring(true);
    setExploreError(null);
    try {
      const result = await exploreAlternative(exercise.text_id, exploreInput);
      setExploreResult(result);
    } catch {
      setExploreError("Cette vérification est temporairement indisponible.");
    } finally {
      setIsExploring(false);
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

  if (phase === "needs-level") {
    return (
      <div className="level-picker card">
        <h2>Quel est ton niveau actuel ?</h2>
        <p className="explore-hint">
          Choisis ton niveau CEFR pour commencer. Tes premiers exercices seront
          adaptés autour de ce niveau.
        </p>
        <div className="level-picker-options">
          {SELECTABLE_LEVELS.map((level) => (
            <button
              key={level}
              type="button"
              className={`pill ${DIFFICULTY_PILL[level]} level-picker-option`}
              onClick={() => handleChooseLevel(level)}
              disabled={isChoosingLevel}
            >
              {DIFFICULTY_LABELS[level] ?? level}
            </button>
          ))}
        </div>
        {levelError && <p className="error-text">{levelError}</p>}
      </div>
    );
  }

  if (phase === "no-exercise") {
    return <p>{noExerciseMessage}</p>;
  }

  if (!exercise) return null;

  return (
    <div className="learning-screen">
      {exercise.is_review && <span className="review-badge">Révision</span>}
      <Meter
        value={exercise.progress.natural_count}
        max={exercise.progress.required_natural_equivalents}
        label={`Progression : ${exercise.progress.natural_count}/${exercise.progress.required_natural_equivalents}`}
        tone="good"
      />

      <h2 className="french-text">{exercise.french_text}</h2>

      {phase === "answering" && (
        <div className="exercise-panel">
          {hintsDisabledForRetry && (
            <p className="retry-hint-notice">
              Tentative d'amélioration : aucun indice n'est proposé pour cette tentative.
            </p>
          )}

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
            {!hintsDisabledForRetry && (
              <button type="button" onClick={handleHint} disabled={hintsRevealed.length >= 3}>
                Indice ({hintsRevealed.length}/3)
              </button>
            )}
            <button type="button" onClick={handleSkip}>
              Passer
            </button>
            <button type="button" onClick={handleRepetition}>
              +1 répétition
            </button>
          </div>

          {recorder.error && <p className="error-text">{recorder.error}</p>}
          {repetitionMessage && <p className="success-text">{repetitionMessage}</p>}

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

          {recorder.isRecording && (
            <p className="retry-hint-notice">
              Arrêtez la dictée avant de soumettre votre réponse.
            </p>
          )}

          <button
            type="button"
            className="primary-button submit-button"
            onClick={handleSubmit}
            disabled={isSubmitting || !draft.trim() || recorder.isRecording}
          >
            {isSubmitting ? "Évaluation..." : "Soumettre"}
          </button>
        </div>
      )}

      {(phase === "pending-writing-issue" || phase === "pending-unnatural-offer") &&
        pendingResult && (
          <div className="feedback-panel pending-panel">
            <div className="feedback-badges">
              <VerdictBadge verdict={pendingResult.verdict} />
            </div>

            <div className="your-answer-block">
              <span className="your-answer-label">Votre réponse</span>
              <p className="your-answer-text">{submittedAnswer}</p>
            </div>

            <p className="feedback-text">{pendingResult.feedback}</p>

            {pendingResult.writing_issues.length > 0 && (
              <ul className="hints-list">
                {pendingResult.writing_issues.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            )}

            {submitError && <p className="error-text">{submitError}</p>}

            <div className="feedback-actions">
              {phase === "pending-writing-issue" ? (
                <>
                  <button
                    type="button"
                    className="primary-button"
                    onClick={handleRetryWritingIssue}
                    disabled={isSubmitting}
                  >
                    Corriger et réessayer
                  </button>
                  <button type="button" onClick={handleFinalize} disabled={isSubmitting}>
                    Voir la réponse
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    className="primary-button"
                    onClick={handleImproveUnnatural}
                    disabled={isSubmitting}
                  >
                    Améliorer ma réponse
                  </button>
                  <button type="button" onClick={handleFinalize} disabled={isSubmitting}>
                    Continuer sans changer
                  </button>
                </>
              )}
            </div>
          </div>
        )}

      {phase === "feedback" && feedback && (
        <div className="feedback-panel">
          <div className="feedback-badges">
            <VerdictBadge verdict={feedback.verdict} />
            <span className={`pill ${DIFFICULTY_PILL[feedback.difficulty] ?? "pill"}`}>
              {DIFFICULTY_LABELS[feedback.difficulty] ?? feedback.difficulty}
            </span>
          </div>

          <div className="your-answer-block">
            <span className="your-answer-label">Votre réponse</span>
            <p className="your-answer-text">{submittedAnswer}</p>
          </div>

          <p className="points-awarded">+{feedback.points_awarded} point(s)</p>
          <p className="feedback-text">{feedback.feedback}</p>

          {feedback.corrected_answer && (
            <p className="corrected-answer">
              Forme correcte : <strong>{feedback.corrected_answer}</strong>
              {feedback.writing_issues.length > 0 && (
                <span className="writing-issues-detail">
                  {" "}
                  ({feedback.writing_issues.join(" · ")})
                </span>
              )}
            </p>
          )}

          <span className="reference-heading">Traduction recommandée</span>
          <div className="reference-block reference-block-preferred">
            <span>{feedback.preferred_translation}</span>
            <AudioButton src={preferredAudioUrl(exercise.text_id)} label={feedback.preferred_translation} />
          </div>

          {feedback.alternatives.length > 0 && (
            <span className="reference-heading">Alternatives naturelles</span>
          )}
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

          <div className="explore-panel">
            <span className="reference-heading">Essayer une autre formulation</span>
            <p className="explore-hint">
              Curieux si une autre phrase aurait aussi été acceptée ? Testez-la ici,
              sans conséquence : cela ne change rien à votre score.
            </p>
            <textarea
              className="answer-input explore-input"
              value={exploreInput}
              onChange={(e) => setExploreInput(e.target.value)}
              placeholder="Une autre formulation en anglais..."
              rows={2}
            />
            {exploreError && <p className="error-text">{exploreError}</p>}
            <button
              type="button"
              onClick={handleExplore}
              disabled={isExploring || !exploreInput.trim()}
            >
              {isExploring ? "Vérification..." : "Vérifier cette formulation"}
            </button>

            {exploreResult && (
              <div className="explore-result">
                <VerdictBadge verdict={exploreResult.verdict} />
                <p className="feedback-text">{exploreResult.feedback}</p>
                {exploreResult.corrected_answer && (
                  <p className="corrected-answer">
                    Forme correcte : <strong>{exploreResult.corrected_answer}</strong>
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="feedback-actions">
            <button type="button" onClick={handleExplanation}>
              Pourquoi ?
            </button>
            <button type="button" onClick={handleReevaluate}>
              Réévaluer
            </button>
            {feedback.progress.status === "ACTIVE" && (
              <>
                <button type="button" onClick={handleRepetition}>
                  +1 répétition
                </button>
                <button type="button" onClick={handleAcquire}>
                  Marquer comme acquis
                </button>
              </>
            )}
            <button type="button" onClick={() => setShowChat((v) => !v)}>
              Demander à l'IA
            </button>
            <button type="button" className="primary-button" onClick={loadNext}>
              Suivant
            </button>
          </div>

          {repetitionMessage && <p className="success-text">{repetitionMessage}</p>}
          {explanation && <p className="explanation-text">{explanation}</p>}
          {showChat && <ChatPanel textId={exercise.text_id} />}
        </div>
      )}
    </div>
  );
}
