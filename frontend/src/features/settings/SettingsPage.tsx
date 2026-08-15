import { useState } from "react";
import { updatePreferences } from "../../api/users";
import { useAuth } from "../auth/AuthContext";

function boolPref(preferences: Record<string, unknown>, key: string, fallback: boolean): boolean {
  const value = preferences[key];
  return typeof value === "boolean" ? value : fallback;
}

export function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  if (!user) return null;

  const translationEnabled = boolPref(user.preferences, "translation_enabled", true);
  const dictationEnabled = boolPref(user.preferences, "dictation_enabled", false);
  const soundEffectsEnabled = boolPref(user.preferences, "sound_effects_enabled", true);

  async function save(update: Record<string, boolean>) {
    setError(null);
    setIsSaving(true);
    try {
      await updatePreferences(update);
      await refreshUser();
    } catch {
      setError("Impossible d'activer au moins un mode : garde au moins la traduction ou la compréhension orale.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <div>
          <h1>Réglages</h1>
          <p className="page-subtitle">Personnalise tes exercices et les effets sonores.</p>
        </div>
      </div>

      <div className="card">
        <h2>Modes de pratique</h2>
        <p className="explore-hint">
          Active un seul mode, ou les deux — dans ce cas, les exercices s'alternent dans un ordre
          aléatoire.
        </p>
        <ul className="kv-list">
          <li className="kv-row">
            <span className="kv-row-label">Traduction</span>
            <label className="settings-toggle">
              <input
                type="checkbox"
                checked={translationEnabled}
                disabled={isSaving}
                onChange={(e) => save({ translation_enabled: e.target.checked })}
              />
            </label>
          </li>
          <li className="kv-row">
            <span className="kv-row-label">Compréhension orale</span>
            <label className="settings-toggle">
              <input
                type="checkbox"
                checked={dictationEnabled}
                disabled={isSaving}
                onChange={(e) => save({ dictation_enabled: e.target.checked })}
              />
            </label>
          </li>
        </ul>
        {error && <p className="error-text">{error}</p>}
      </div>

      <div className="card">
        <h2>Effets sonores</h2>
        <ul className="kv-list">
          <li className="kv-row">
            <span className="kv-row-label">Sons lors de la correction</span>
            <label className="settings-toggle">
              <input
                type="checkbox"
                checked={soundEffectsEnabled}
                disabled={isSaving}
                onChange={(e) => save({ sound_effects_enabled: e.target.checked })}
              />
            </label>
          </li>
        </ul>
      </div>
    </div>
  );
}
