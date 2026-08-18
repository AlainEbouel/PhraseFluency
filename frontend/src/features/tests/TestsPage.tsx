import { useEffect, useState } from "react";
import { GraduationCap, Lightbulb } from "lucide-react";
import { Link } from "react-router-dom";
import {
  fetchTestDetail,
  fetchTests,
  startTest,
  submitTestAnswer,
} from "../../api/tests";
import type { TestDetail, TestSubmitResult, TestSummary } from "../../api/tests";
import { VerdictBadge } from "../../components/VerdictBadge";
import { DIFFICULTY_LABELS, DIFFICULTY_PILL } from "../../constants/difficulty";
import { useContentFlash } from "../../hooks/useContentFlash";
import { useSoundEffects } from "../../hooks/useSoundEffects";

const STATUS_LABELS: Record<string, string> = {
  AVAILABLE: "Disponible",
  IN_PROGRESS: "En cours",
  COMPLETED: "Complété",
};

export function TestsPage() {
  const [tests, setTests] = useState<TestSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  function reload() {
    fetchTests().then(setTests).catch(() => setTests([]));
  }

  useEffect(() => {
    reload();
  }, []);

  if (selectedId) {
    return (
      <TestDetailView
        testId={selectedId}
        onBack={() => {
          setSelectedId(null);
          reload();
        }}
      />
    );
  }

  return (
    <div className="tests-page">
      <div className="page-header">
        <div>
          <h1>Tests</h1>
          <p className="page-subtitle">Des lots de 25 textes pour mesurer votre rétention.</p>
        </div>
        <Link to="/learn" className="primary-button page-header-cta">
          <GraduationCap /> Continuer l'apprentissage
        </Link>
      </div>
      {tests === null && <p>Chargement...</p>}
      {tests?.length === 0 && (
        <p className="empty-state">
          Aucun test disponible encore. Complétez plus d'exercices d'apprentissage pour débloquer
          votre premier test de 25 textes.
        </p>
      )}
      <div className="test-list">
        {tests?.map((test) => (
          <button key={test.id} className="test-card" onClick={() => setSelectedId(test.id)}>
            <span className="test-card-number">Test #{test.number}</span>
            <span className={`test-card-status status-${test.status.toLowerCase()}`}>
              {STATUS_LABELS[test.status]}
            </span>
            <span className="test-card-progress">
              {test.mastered_count}/{test.total_count} maîtrisés
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function TestDetailView({ testId, onBack }: { testId: string; onBack: () => void }) {
  const [detail, setDetail] = useState<TestDetail | null>(null);
  const [currentTextId, setCurrentTextId] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [submittedAnswer, setSubmittedAnswer] = useState("");
  const [feedback, setFeedback] = useState<TestSubmitResult | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const feedbackFlash = useContentFlash(feedback);
  const { playSound } = useSoundEffects();

  function reload() {
    fetchTestDetail(testId).then(setDetail).catch(() => setError("Impossible de charger le test."));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testId]);

  async function handleStart() {
    try {
      await startTest(testId);
      reload();
    } catch {
      setError("Impossible de démarrer le test.");
    }
  }

  async function handleSubmit() {
    if (!currentTextId || !answer.trim()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await submitTestAnswer(testId, currentTextId, answer, crypto.randomUUID());
      playSound(
        result.verdict === "CORRECT_NATURAL" || result.verdict === "CORRECT_WITH_USAGE_NOTE"
          ? "natural"
          : result.verdict === "INCORRECT"
            ? "incorrect"
            : "unnatural"
      );
      setSubmittedAnswer(answer);
      setFeedback(result);
      setAnswer("");
      reload();
    } catch {
      setError("L'évaluation a échoué. Réessayez.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!detail) {
    return <p>Chargement...</p>;
  }

  const remaining = detail.texts.filter((t) => !t.mastered);
  const hasInProgressAttempt = detail.attempts.some((a) => a.status === "IN_PROGRESS");

  return (
    <div className="test-detail">
      <button type="button" onClick={onBack} className="back-link">
        ← Retour aux tests
      </button>
      <h1>Test #{detail.number}</h1>

      {!hasInProgressAttempt && (
        <button type="button" className="primary-button" onClick={handleStart}>
          {detail.status === "COMPLETED" ? "Recommencer le test" : "Commencer le test"}
        </button>
      )}

      {hasInProgressAttempt && (
        <div className="test-runner">
          <p>{remaining.length} texte(s) restant(s) à maîtriser sur 25.</p>

          {!currentTextId && remaining.length > 0 && (
            <button type="button" onClick={() => setCurrentTextId(remaining[0].text_id)}>
              Continuer avec le prochain texte
            </button>
          )}

          {currentTextId && (
            <div className="exercise-panel">
              <h2 className="french-text">
                {detail.texts.find((t) => t.text_id === currentTextId)?.french_text}
              </h2>
              <textarea
                className="answer-input"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                rows={3}
              />
              <button
                type="button"
                className="primary-button"
                onClick={handleSubmit}
                disabled={isSubmitting || !answer.trim()}
              >
                Soumettre
              </button>

              {feedback && (
                <div className={`feedback-panel${feedbackFlash ? " content-flash" : ""}`}>
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

                  {feedback.usage_note_alternative && (
                    <p className="usage-note">
                      <Lightbulb /> Astuce d'usage : <strong>{feedback.usage_note_alternative}</strong>
                    </p>
                  )}

                  <p>
                    Succès consécutifs : {feedback.consecutive_successes}/2{" "}
                    {feedback.mastered ? "— Maîtrisé !" : ""}
                  </p>
                  {feedback.test_completed && <p className="success-text">Test complété !</p>}
                  <button
                    type="button"
                    onClick={() => {
                      setFeedback(null);
                      const next = remaining.find((t) => t.text_id !== currentTextId);
                      setCurrentTextId(next ? next.text_id : null);
                    }}
                  >
                    Texte suivant
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {error && <p className="error-text">{error}</p>}

      <h3>Les 25 textes</h3>
      <ul className="test-text-list">
        {detail.texts.map((t) => (
          <li key={t.text_id} className={t.mastered ? "mastered" : ""}>
            {t.french_text} — {t.mastered ? "Maîtrisé" : `${t.consecutive_successes}/2`}
          </li>
        ))}
      </ul>
    </div>
  );
}
