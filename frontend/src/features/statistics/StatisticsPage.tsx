import { useEffect, useState } from "react";
import { Lightbulb } from "lucide-react";
import { fetchDetailedStatistics, fetchWeaknessProfile } from "../../api/statistics";
import type { DetailedStatistics, WeaknessProfile } from "../../api/statistics";
import { Meter } from "../../components/Meter";
import { ERROR_CATEGORY_LABELS } from "../../constants/errorCategories";
import { useContentFlash } from "../../hooks/useContentFlash";

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

const STATUS_PILL: Record<string, string> = {
  MASTERED: "pill-good",
  MANUALLY_ACQUIRED: "pill-good",
  ACTIVE: "pill-brand",
  TEST_ASSIGNED: "pill-brand",
  WAITING_FOR_TEST_ASSIGNMENT: "pill-warning",
  DISABLED: "pill-critical",
  UNSEEN: "pill",
};

const VERDICT_PILL: Record<string, string> = {
  CORRECT_NATURAL: "pill-good",
  CORRECT_UNNATURAL: "pill-warning",
  CORRECT_WITH_WRITING_ISSUES: "pill-serious",
  INCORRECT: "pill-critical",
};

export function StatisticsPage() {
  const [stats, setStats] = useState<DetailedStatistics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [weaknessProfile, setWeaknessProfile] = useState<WeaknessProfile | null>(null);
  const [weaknessError, setWeaknessError] = useState<string | null>(null);
  const weaknessFlash = useContentFlash(weaknessProfile);

  useEffect(() => {
    fetchDetailedStatistics()
      .then(setStats)
      .catch(() => setError("Impossible de charger les statistiques."));
  }, []);

  useEffect(() => {
    fetchWeaknessProfile()
      .then(setWeaknessProfile)
      .catch(() => setWeaknessError("Impossible de charger ton profil de faiblesses pour l'instant."));
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!stats) return <p>Chargement...</p>;

  const maxWeaknessCount = weaknessProfile?.weaknesses[0]?.count ?? 0;

  return (
    <div className="statistics-page">
      <div className="page-header">
        <h1>Statistiques détaillées</h1>
        <p className="page-subtitle">Votre historique d'apprentissage, en détail.</p>
      </div>

      <div className={`card${weaknessFlash ? " content-flash" : ""}`}>
        <h2>Points faibles</h2>
        {weaknessProfile === null && weaknessError === null && <p>Chargement...</p>}
        {weaknessError && <p className="error-text">{weaknessError}</p>}
        {weaknessProfile && !weaknessProfile.has_enough_data && (
          <p className="empty-state">
            Pas encore assez de réponses pour dresser ton profil de faiblesses. Continue à
            t'exercer, il se construira au fur et à mesure.
          </p>
        )}
        {weaknessProfile && weaknessProfile.has_enough_data && (
          <>
            <ul className="kv-list">
              {weaknessProfile.weaknesses.map((w) => (
                <li className="kv-row" key={w.category}>
                  <span className="kv-row-label">
                    {ERROR_CATEGORY_LABELS[w.category] ?? w.category}
                  </span>
                  <Meter value={w.count} max={maxWeaknessCount} tone="brand" />
                  <span className="kv-row-value">{w.count}</span>
                </li>
              ))}
            </ul>
            <div className="weakness-suggestions">
              {weaknessProfile.suggestions.map((s) => (
                <div className="weakness-suggestion-card" key={s.category}>
                  <h3>{ERROR_CATEGORY_LABELS[s.category] ?? s.category}</h3>
                  <p>{s.explanation}</p>
                  <p className="weakness-suggestion-tip">
                    <Lightbulb /> {s.suggestion}
                  </p>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="card">
        <h2>Tendances</h2>
        <table className="stats-table">
          <thead>
            <tr>
              <th></th>
              <th>Tentatives</th>
              <th>Taux naturel</th>
              <th>Taux de réussite</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>7 jours</td>
              <td>{stats.trend_7d.attempts_count}</td>
              <td>{pct(stats.trend_7d.natural_rate)}</td>
              <td>{pct(stats.trend_7d.success_rate)}</td>
            </tr>
            <tr>
              <td>30 jours</td>
              <td>{stats.trend_30d.attempts_count}</td>
              <td>{pct(stats.trend_30d.natural_rate)}</td>
              <td>{pct(stats.trend_30d.success_rate)}</td>
            </tr>
            <tr>
              <td>Total</td>
              <td>{stats.trend_all_time.attempts_count}</td>
              <td>{pct(stats.trend_all_time.natural_rate)}</td>
              <td>{pct(stats.trend_all_time.success_rate)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="card-grid">
        <div className="card">
          <h2>Répartition par statut</h2>
          <ul className="kv-list">
            {stats.status_counts.map((row) => (
              <li className="kv-row" key={row.status}>
                <span className={`pill ${STATUS_PILL[row.status] ?? "pill"}`}>{row.status}</span>
                <span className="kv-row-value">{row.count}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h2>Répartition des verdicts</h2>
          <ul className="kv-list">
            {stats.verdict_counts.map((row) => (
              <li className="kv-row" key={row.verdict}>
                <span className={`pill ${VERDICT_PILL[row.verdict] ?? "pill"}`}>{row.verdict}</span>
                <span className="kv-row-value">{row.count}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h2>Performance par difficulté</h2>
          {stats.performance_by_difficulty.length === 0 && (
            <p className="empty-state">Pas encore de données.</p>
          )}
          <ul className="kv-list">
            {stats.performance_by_difficulty.map((row) => (
              <li className="kv-row" key={row.difficulty}>
                <span className="kv-row-label">{row.difficulty}</span>
                <Meter value={row.natural_rate * 100} max={100} tone="good" />
                <span className="kv-row-value">{pct(row.natural_rate)}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h2>Performance par contexte</h2>
          {stats.performance_by_context.length === 0 && (
            <p className="empty-state">Pas encore de données.</p>
          )}
          <ul className="kv-list">
            {stats.performance_by_context.map((row) => (
              <li className="kv-row" key={row.context}>
                <span className="kv-row-label">{row.context}</span>
                <Meter value={row.natural_rate * 100} max={100} tone="good" />
                <span className="kv-row-value">{pct(row.natural_rate)}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h2>Voix vs clavier</h2>
          <ul className="kv-list">
            {stats.input_method_counts.map((row) => (
              <li className="kv-row" key={row.input_method}>
                <span className="kv-row-label">{row.input_method}</span>
                <span className="kv-row-value">{row.count}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h2>Performance aux tests</h2>
          <ul className="kv-list">
            <li className="kv-row">
              <span className="kv-row-label">Tests complétés</span>
              <span className="kv-row-value">{stats.test_performance.tests_completed}</span>
            </li>
            <li className="kv-row">
              <span className="kv-row-label">Réponses correctes</span>
              <span className="pill pill-good">{stats.test_performance.total_correct}</span>
            </li>
            <li className="kv-row">
              <span className="kv-row-label">Réponses incorrectes</span>
              <span className="pill pill-critical">{stats.test_performance.total_incorrect}</span>
            </li>
            <li className="kv-row">
              <span className="kv-row-label">Reprises (retakes)</span>
              <span className="kv-row-value">{stats.test_performance.retakes_count}</span>
            </li>
          </ul>
        </div>

        <div className="card">
          <h2>Divers</h2>
          <ul className="kv-list">
            <li className="kv-row">
              <span className="kv-row-label">Tentatives moyennes avant maîtrise</span>
              <span className="kv-row-value">
                {stats.avg_attempts_before_mastery !== null
                  ? stats.avg_attempts_before_mastery.toFixed(1)
                  : "—"}
              </span>
            </li>
            <li className="kv-row">
              <span className="kv-row-label">Usage des indices</span>
              <span className="kv-row-value">{pct(stats.hint_usage_rate)}</span>
            </li>
            <li className="kv-row">
              <span className="kv-row-label">Fautes d'écriture</span>
              <span className="kv-row-value">{stats.writing_issue_count}</span>
            </li>
            <li className="kv-row">
              <span className="kv-row-label">Formulations rencontrées</span>
              <span className="pill pill-brand">{stats.patterns_encountered_count}</span>
            </li>
            <li className="kv-row">
              <span className="kv-row-label">Réévaluations</span>
              <span className="kv-row-value">
                {stats.reevaluation.total_reevaluated} ({stats.reevaluation.verdict_changed_count}{" "}
                changé(s))
              </span>
            </li>
          </ul>
        </div>

        <div className="card">
          <h2>Textes les plus difficiles</h2>
          {stats.hardest_texts.length === 0 && <p className="empty-state">Aucun pour l'instant.</p>}
          <ul className="kv-list">
            {stats.hardest_texts.map((t) => (
              <li className="kv-row" key={t.text_id}>
                <span className="kv-row-label">{t.french_text}</span>
                <span className="pill pill-critical">
                  {t.incorrect_count}/{t.times_presented}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="card">
        <h2>Usage de l'IA</h2>
        <table className="stats-table">
          <thead>
            <tr>
              <th>Opération</th>
              <th>Nombre</th>
              <th>Coût estimé</th>
            </tr>
          </thead>
          <tbody>
            {stats.ai_usage.map((row) => (
              <tr key={row.operation}>
                <td>{row.operation}</td>
                <td>{row.count}</td>
                <td>${row.estimated_cost.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
