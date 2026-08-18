import { useCallback, useEffect, useRef, useState } from "react";
import { Lightbulb } from "lucide-react";
import { ApiError } from "../../api/client";
import { alternativeAudioUrl, preferredAudioUrl } from "../../api/audio";
import { fetchNextDictation, submitDictationAnswer } from "../../api/dictation";
import type { DictationExercise, DictationSubmitResult } from "../../api/dictation";
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
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { CopyButton } from "../../components/CopyButton";
import { Meter } from "../../components/Meter";
import { VerdictBadge } from "../../components/VerdictBadge";
import { ChatPanel } from "../conversations/ChatPanel";
import { useAuth } from "../auth/AuthContext";
import { useAudioRecorder } from "../../hooks/useAudioRecorder";
import { useContentFlash } from "../../hooks/useContentFlash";
import { useSoundEffects } from "../../hooks/useSoundEffects";
import { DIFFICULTY_LABELS, DIFFICULTY_PILL } from "../../constants/difficulty";

type ExerciseKind = "translation" | "dictation";

function pickExerciseKind(preferences: Record<string, unknown> | undefined): ExerciseKind {
  const translationEnabled = preferences?.translation_enabled !== false;
  const dictationEnabled = preferences?.dictation_enabled === true;
  if (translationEnabled && dictationEnabled) {
    return Math.random() < 0.5 ? "translation" : "dictation";
  }
  return dictationEnabled ? "dictation" : "translation";
}

const SELECTABLE_LEVELS: Difficulty[] = ["A1", "A2", "B1", "B2", "C1", "C2"];

type Phase =
  | "loading"
  | "needs-level"
  | "no-exercise"
  | "answering"
  | "pending-writing-issue"
  | "pending-retry-offer"
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
  const [retryCount, setRetryCount] = useState(0);
  const [exploreInput, setExploreInput] = useState("");
  const [exploreResult, setExploreResult] = useState<ExploreResult | null>(null);
  const [isExploring, setIsExploring] = useState(false);
  const [exploreError, setExploreError] = useState<string | null>(null);
  const [isChoosingLevel, setIsChoosingLevel] = useState(false);
  const [levelError, setLevelError] = useState<string | null>(null);
  const [showAcquireConfirm, setShowAcquireConfirm] = useState(false);
  const [exerciseKind, setExerciseKind] = useState<ExerciseKind>("translation");
  const [dictationExercise, setDictationExercise] = useState<DictationExercise | null>(null);
  const [dictationTranscript, setDictationTranscript] = useState("");
  const [dictationResult, setDictationResult] = useState<DictationSubmitResult | null>(null);
  const [isDictationSubmitting, setIsDictationSubmitting] = useState(false);
  const [dictationError, setDictationError] = useState<string | null>(null);
  const { user } = useAuth();
  const draftTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const explanationRef = useRef<HTMLDivElement | null>(null);
  const chatRef = useRef<HTMLDivElement | null>(null);

  const feedbackFlash = useContentFlash(feedback);
  const pendingResultFlash = useContentFlash(pendingResult);
  const exploreResultFlash = useContentFlash(exploreResult);
  const dictationResultFlash = useContentFlash(dictationResult);
  const { playSound } = useSoundEffects();

  useEffect(() => {
    if (explanation) {
      explanationRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [explanation]);

  useEffect(() => {
    if (showChat) {
      chatRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [showChat]);

  const loadNext = useCallback(() => {
    setPhase("loading");
    setFeedback(null);
    setPendingResult(null);
    setExplanation(null);
    setShowChat(false);
    setSubmitError(null);
    setRepetitionMessage(null);
    setHintsDisabledForRetry(false);
    setRetryCount(0);
    setExploreInput("");
    setExploreResult(null);
    setExploreError(null);
    setDictationTranscript("");
    setDictationResult(null);
    setDictationError(null);

    const kind = pickExerciseKind(user?.preferences);
    setExerciseKind(kind);

    if (kind === "dictation") {
      fetchNextDictation()
        .then((result) => {
          if ("available" in result && result.available === false) {
            setNoExerciseMessage(result.message);
            setPhase("no-exercise");
            return;
          }
          setDictationExercise(result as DictationExercise);
          setPhase("answering");
        })
        .catch(() => setPhase("load-error"));
      return;
    }

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
  }, [user]);

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
        retryCount,
      });
      setSubmittedAnswer(draft);
      if (result.committed) {
        playSound(
          result.verdict === "CORRECT_NATURAL" || result.verdict === "CORRECT_WITH_USAGE_NOTE"
            ? "natural"
            : result.verdict === "INCORRECT"
              ? "incorrect"
              : "unnatural"
        );
        setFeedback(result);
        setPendingResult(null);
        setHintsDisabledForRetry(false);
        setRetryCount(0);
        setPhase("feedback");
      } else {
        playSound("pending");
        setPendingResult(result);
        setPhase(
          result.verdict === "CORRECT_WITH_WRITING_ISSUES"
            ? "pending-writing-issue"
            : "pending-retry-offer"
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

  async function handleDictationSubmit() {
    if (!dictationExercise || !dictationTranscript.trim()) return;
    setIsDictationSubmitting(true);
    setDictationError(null);
    try {
      const submissionId = crypto.randomUUID();
      const result = await submitDictationAnswer(
        dictationExercise.text_id,
        dictationTranscript,
        submissionId
      );
      playSound(
        result.verdict === "CORRECT_NATURAL" || result.verdict === "CORRECT_WITH_USAGE_NOTE"
          ? "natural"
          : result.verdict === "INCORRECT"
            ? "incorrect"
            : "unnatural"
      );
      setDictationResult(result);
      setPhase("feedback");
    } catch (err) {
      setDictationError(
        err instanceof ApiError
          ? err.message
          : "L'évaluation est temporairement indisponible. Réessayez."
      );
    } finally {
      setIsDictationSubmitting(false);
    }
  }

  function handleRetryWritingIssue() {
    setPendingResult(null);
    setSubmitError(null);
    setPhase("answering");
  }

  function handleRetry() {
    if (!pendingResult) return;
    const next = retryCount + 1;
    setPendingResult(null);
    setSubmitError(null);
    setRetryCount(next);
    setHintsDisabledForRetry(next >= 2 ? true : pendingResult.verdict === "CORRECT_UNNATURAL");
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
    setShowAcquireConfirm(false);
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
      const applyResult = () => {
        setFeedback((prev) =>
          prev
            ? {
                ...prev,
                verdict: result.verdict as SubmitResult["verdict"],
                feedback: result.feedback,
                corrected_answer: result.corrected_answer,
              }
            : prev
        );
      };
      // Scrolling and the content-flash animation both signal "this is new" —
      // running them at the same time makes the flash fade out mid-scroll,
      // where it's barely noticeable. Scroll first, flash once the view is
      // settled (skip the wait entirely if we're already near the top).
      if (window.scrollY > 40) {
        window.scrollTo({ top: 0, behavior: "smooth" });
        setTimeout(applyResult, 400);
      } else {
        applyResult();
      }
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

  if (exerciseKind === "dictation") {
    if (!dictationExercise && phase !== "feedback") return null;

    return (
      <div className={`learning-screen${phase === "feedback" ? " learning-screen-wide" : ""}`}>
        <h2 className="french-text">🎧 Compréhension orale</h2>

        {phase === "answering" && dictationExercise && (
          <div className="exercise-panel">
            <p className="explore-hint">
              Écoute la phrase et transcris-la exactement, avec la bonne orthographe.
            </p>
            <AudioButton src={preferredAudioUrl(dictationExercise.text_id)} label="la phrase" />

            <textarea
              className="answer-input"
              value={dictationTranscript}
              onChange={(e) => setDictationTranscript(e.target.value)}
              placeholder="Ce que tu as entendu..."
              rows={3}
            />

            <div className="exercise-actions">
              <button type="button" onClick={loadNext}>
                Passer
              </button>
            </div>

            {dictationError && (
              <p className="error-text">
                {dictationError}{" "}
                <button type="button" onClick={handleDictationSubmit}>
                  Réessayer
                </button>
              </p>
            )}

            <button
              type="button"
              className="primary-button submit-button"
              onClick={handleDictationSubmit}
              disabled={isDictationSubmitting || !dictationTranscript.trim()}
            >
              {isDictationSubmitting ? "Évaluation..." : "Soumettre"}
            </button>
          </div>
        )}

        {phase === "feedback" && dictationResult && (
          <div className={`feedback-panel${dictationResultFlash ? " content-flash" : ""}`}>
            <div className="feedback-badges">
              <VerdictBadge verdict={dictationResult.verdict} />
            </div>

            <div className="your-answer-block">
              <span className="your-answer-label">Ta transcription</span>
              <p className="your-answer-text">{dictationTranscript}</p>
            </div>

            <p className="feedback-text">{dictationResult.feedback}</p>

            {dictationResult.corrected_answer && (
              <p className="corrected-answer">
                Transcription exacte : <strong>{dictationResult.corrected_answer}</strong>
              </p>
            )}

            <div className="feedback-actions">
              <button type="button" className="primary-button" onClick={loadNext}>
                Suivant
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (!exercise) return null;

  return (
    <div className={`learning-screen${phase === "feedback" ? " learning-screen-wide" : ""}`}>
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

      {(phase === "pending-writing-issue" || phase === "pending-retry-offer") &&
        pendingResult && (
          <div
            className={`feedback-panel pending-panel${pendingResultFlash ? " content-flash" : ""}`}
          >
            <div className="feedback-badges">
              <VerdictBadge verdict={pendingResult.verdict} />
            </div>

            <div className="your-answer-block">
              <span className="your-answer-label">Votre réponse</span>
              <p className="your-answer-text">{submittedAnswer}</p>
            </div>

            {phase === "pending-retry-offer" && (
              <p className="feedback-text">
                {pendingResult.verdict === "INCORRECT"
                  ? "Ta réponse ne correspond pas encore au sens voulu."
                  : "Ça se comprend, mais voici une formulation plus naturelle."}
              </p>
            )}
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
                    onClick={handleRetry}
                    disabled={isSubmitting}
                  >
                    {pendingResult.verdict === "INCORRECT" ? "Réessayer" : "Améliorer ma réponse"}
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
        <div className="feedback-layout">
          <div className={`feedback-panel${feedbackFlash ? " content-flash" : ""}`}>
            <div className="feedback-badges">
              <VerdictBadge verdict={feedback.verdict} />
              <span className={`pill ${DIFFICULTY_PILL[feedback.difficulty] ?? "pill"}`}>
                {DIFFICULTY_LABELS[feedback.difficulty] ?? feedback.difficulty}
              </span>
            </div>

            <div className="your-answer-block">
              <span className="your-answer-label">Votre réponse</span>
              <p className="your-answer-text">
                {submittedAnswer} <CopyButton text={submittedAnswer} label="votre réponse" />
              </p>
              <button type="button" className="reevaluate-button" onClick={handleReevaluate}>
                Réévaluer
              </button>
            </div>

            <p className="points-awarded">+{feedback.points_awarded} point(s)</p>
            <p className="feedback-text">{feedback.feedback}</p>

            {feedback.corrected_answer && (
              <p className="corrected-answer">
                Forme correcte : <strong>{feedback.corrected_answer}</strong>
                <CopyButton text={feedback.corrected_answer} label="la forme correcte" />
                {feedback.writing_issues.length > 0 && (
                  <span className="writing-issues-detail">
                    {" "}
                    ({feedback.writing_issues.join(" · ")})
                  </span>
                )}
              </p>
            )}

            {feedback.usage_note_alternative && (
              <p className="usage-note">
                <Lightbulb /> Astuce d'usage : <strong>{feedback.usage_note_alternative}</strong>
                <CopyButton text={feedback.usage_note_alternative} label="la remarque d'usage" />
              </p>
            )}

            <span className="reference-heading">Traduction recommandée</span>
            <div className="reference-block reference-block-preferred">
              <span>{feedback.preferred_translation}</span>
              <AudioButton src={preferredAudioUrl(exercise.text_id)} label={feedback.preferred_translation} />
              <CopyButton text={feedback.preferred_translation} label="la traduction recommandée" />
            </div>

            {feedback.alternatives.length > 0 && (
              <span className="reference-heading">Alternatives naturelles</span>
            )}
            {feedback.alternatives.map((alt, i) => (
              <div className="reference-block" key={i}>
                <span>{alt}</span>
                <AudioButton src={alternativeAudioUrl(exercise.text_id, i)} label={alt} />
                <CopyButton text={alt} label="cette alternative" />
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
              {feedback.progress.status === "ACTIVE" && (
                <>
                  <button type="button" onClick={handleRepetition}>
                    +1 répétition
                  </button>
                  <button type="button" onClick={() => setShowAcquireConfirm(true)}>
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

            {showAcquireConfirm && (
              <ConfirmDialog
                title="Marquer ce texte comme acquis ?"
                message="Ce texte ne sera plus jamais proposé en révision, même si vous ne l'avez pas encore répété naturellement le nombre de fois requis. Cette action est définitive."
                confirmLabel="Marquer comme acquis"
                onConfirm={handleAcquire}
                onCancel={() => setShowAcquireConfirm(false)}
              />
            )}
          </div>

          <div className="feedback-sidebar">
            {explanation && (
              <div className="card explanation-card" ref={explanationRef}>
                <span className="reference-heading">Pourquoi ?</span>
                <p className="explanation-text">{explanation}</p>
              </div>
            )}

            {showChat && (
              <div className="card chat-card" ref={chatRef}>
                <ChatPanel textId={exercise.text_id} />
              </div>
            )}

            <div className="card explore-panel">
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
                <div className={`explore-result${exploreResultFlash ? " content-flash" : ""}`}>
                  <VerdictBadge verdict={exploreResult.verdict} />
                  <p className="feedback-text">{exploreResult.feedback}</p>
                  {exploreResult.corrected_answer && (
                    <p className="corrected-answer">
                      Forme correcte : <strong>{exploreResult.corrected_answer}</strong>
                      <CopyButton text={exploreResult.corrected_answer} label="la forme correcte" />
                    </p>
                  )}
                  {exploreResult.usage_note_alternative && (
                    <p className="usage-note">
                      <Lightbulb /> Astuce d'usage :{" "}
                      <strong>{exploreResult.usage_note_alternative}</strong>
                      <CopyButton text={exploreResult.usage_note_alternative} label="la remarque d'usage" />
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
