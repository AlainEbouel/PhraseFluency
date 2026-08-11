import { useEffect, useState } from "react";
import { fetchDetailedStatistics } from "../../api/statistics";
import type { DetailedStatistics } from "../../api/statistics";

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function StatisticsPage() {
  const [stats, setStats] = useState<DetailedStatistics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDetailedStatistics()
      .then(setStats)
      .catch(() => setError("Impossible de charger les statistiques."));
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!stats) return <p>Chargement...</p>;

  return (
    <div className="statistics-page">
      <h1>Statistiques détaillées</h1>

      <section>
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
      </section>

      <section>
        <h2>Répartition par statut</h2>
        <ul>
          {stats.status_counts.map((row) => (
            <li key={row.status}>
              {row.status}: {row.count}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Répartition des verdicts</h2>
        <ul>
          {stats.verdict_counts.map((row) => (
            <li key={row.verdict}>
              {row.verdict}: {row.count}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Textes les plus difficiles</h2>
        {stats.hardest_texts.length === 0 && <p>Aucun pour l'instant.</p>}
        <ul>
          {stats.hardest_texts.map((t) => (
            <li key={t.text_id}>
              {t.french_text} — {t.incorrect_count} incorrecte(s) sur {t.times_presented}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Performance par difficulté</h2>
        <ul>
          {stats.performance_by_difficulty.map((row) => (
            <li key={row.difficulty}>
              {row.difficulty}: {pct(row.natural_rate)} naturel sur {row.attempts_count} tentative(s)
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Performance par contexte</h2>
        <ul>
          {stats.performance_by_context.map((row) => (
            <li key={row.context}>
              {row.context}: {pct(row.natural_rate)} naturel sur {row.attempts_count} tentative(s)
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Divers</h2>
        <ul>
          <li>
            Attempts moyens avant maîtrise :{" "}
            {stats.avg_attempts_before_mastery !== null
              ? stats.avg_attempts_before_mastery.toFixed(1)
              : "—"}
          </li>
          <li>Usage des indices : {pct(stats.hint_usage_rate)}</li>
          <li>Fautes d'écriture : {stats.writing_issue_count}</li>
          <li>Formulations rencontrées : {stats.patterns_encountered_count}</li>
          <li>
            Réévaluations : {stats.reevaluation.total_reevaluated} (dont{" "}
            {stats.reevaluation.verdict_changed_count} avec changement de verdict)
          </li>
        </ul>
      </section>

      <section>
        <h2>Voix vs clavier</h2>
        <ul>
          {stats.input_method_counts.map((row) => (
            <li key={row.input_method}>
              {row.input_method}: {row.count}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Performance aux tests</h2>
        <ul>
          <li>Tests complétés : {stats.test_performance.tests_completed}</li>
          <li>Réponses correctes : {stats.test_performance.total_correct}</li>
          <li>Réponses incorrectes : {stats.test_performance.total_incorrect}</li>
          <li>Reprises (retakes) : {stats.test_performance.retakes_count}</li>
        </ul>
      </section>

      <section>
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
      </section>
    </div>
  );
}
