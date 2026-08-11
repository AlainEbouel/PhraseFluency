import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDashboard } from "../../api/statistics";
import type { Dashboard } from "../../api/statistics";

export function DashboardPage() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboard()
      .then(setDashboard)
      .catch(() => setError("Impossible de charger le tableau de bord."));
  }, []);

  if (error) {
    return <p className="error-text">{error}</p>;
  }

  if (!dashboard) {
    return <p>Chargement...</p>;
  }

  return (
    <div className="dashboard">
      <h1>Tableau de bord</h1>

      <div className="stat-tile-row">
        <div className="stat-tile">
          <div className="stat-tile-value">{dashboard.mastered_count}</div>
          <div className="stat-tile-label">Textes maîtrisés</div>
        </div>
        <div className="stat-tile">
          <div className="stat-tile-value">
            {dashboard.active_count}/{dashboard.active_target}
          </div>
          <div className="stat-tile-label">Banque active</div>
        </div>
        <div className="stat-tile">
          <div className="stat-tile-value">{Math.round(dashboard.natural_answer_rate * 100)}%</div>
          <div className="stat-tile-label">Taux de naturel</div>
        </div>
        <div className="stat-tile">
          <div className="stat-tile-value">{Math.round(dashboard.overall_success_rate * 100)}%</div>
          <div className="stat-tile-label">Taux de réussite</div>
        </div>
      </div>

      <div className="dashboard-actions">
        <Link to="/learn" className="primary-button">
          Continuer l'apprentissage
        </Link>
        {dashboard.tests_available > 0 || dashboard.tests_in_progress > 0 ? (
          <Link to="/tests" className="secondary-button">
            {dashboard.tests_in_progress > 0 ? "Continuer un test" : "Commencer un test"}
          </Link>
        ) : (
          <p className="dashboard-hint">
            Aucun test disponible pour l'instant. Complétez plus d'exercices pour débloquer votre
            premier test de 25 textes.
          </p>
        )}
      </div>

      <div className="dashboard-secondary-row">
        <span>{dashboard.waiting_for_test_count} texte(s) en attente d'assignation à un test</span>
        <span>
          {dashboard.tests_completed} test(s) complété(s) · {dashboard.tests_in_progress} en cours
        </span>
      </div>
    </div>
  );
}
