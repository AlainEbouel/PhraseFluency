import { useEffect, useState } from "react";
import { fetchLevelSettings, updateLevelSettings } from "../../api/learning";
import { updatePreferences } from "../../api/users";
import { DIFFICULTY_LABELS } from "../../constants/difficulty";
import type { Difficulty, LevelSettings } from "../../types/learning";
import { useAuth } from "../auth/AuthContext";

const LEVEL_ORDER: Difficulty[] = ["A1", "A2", "B1", "B2", "C1", "C2"];

function boolPref(preferences: Record<string, unknown>, key: string, fallback: boolean): boolean {
  const value = preferences[key];
  return typeof value === "boolean" ? value : fallback;
}

export function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [levelSettings, setLevelSettings] = useState<LevelSettings | null>(null);
  const [levelSettingsError, setLevelSettingsError] = useState<string | null>(null);
  const [levelSettingsNotice, setLevelSettingsNotice] = useState<{
    message: string;
    suggestedTargetLevel: Difficulty;
  } | null>(null);
  const [isSavingLevelSettings, setIsSavingLevelSettings] = useState(false);

  useEffect(() => {
    fetchLevelSettings()
      .then(setLevelSettings)
      .catch(() => setLevelSettingsError("Impossible de charger les réglages de niveau."));
  }, []);

  async function saveLevelSettings(update: { targetLevel?: Difficulty; currentLevelShare?: number }) {
    setLevelSettingsError(null);
    setLevelSettingsNotice(null);
    setIsSavingLevelSettings(true);
    try {
      const result = await updateLevelSettings(update);
      if (result.accepted) {
        setLevelSettings(result);
      } else {
        setLevelSettingsNotice({
          message: result.message,
          suggestedTargetLevel: result.suggested_target_level,
        });
      }
    } catch {
      setLevelSettingsError("Impossible de mettre à jour les réglages de niveau pour l'instant.");
    } finally {
      setIsSavingLevelSettings(false);
    }
  }

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

      {levelSettings && levelSettings.current_level && (
        <div className="card">
          <h2>Niveau d'apprentissage</h2>
          <p className="explore-hint">
            Ta banque d'exercices mélange ton niveau actuel ({DIFFICULTY_LABELS[levelSettings.current_level]})
            et le niveau que tu vises. Le changement s'applique immédiatement.
          </p>
          <ul className="kv-list">
            <li className="kv-row">
              <span className="kv-row-label">Niveau visé</span>
              <select
                value={levelSettings.target_level ?? levelSettings.current_level}
                disabled={isSavingLevelSettings}
                onChange={(e) => saveLevelSettings({ targetLevel: e.target.value as Difficulty })}
              >
                {LEVEL_ORDER.filter(
                  (level) => LEVEL_ORDER.indexOf(level) >= LEVEL_ORDER.indexOf(levelSettings.current_level!)
                ).map((level) => (
                  <option key={level} value={level}>
                    {DIFFICULTY_LABELS[level]}
                  </option>
                ))}
              </select>
            </li>
            <li className="kv-row">
              <span className="kv-row-label">
                Part du niveau actuel : {Math.round(levelSettings.current_level_share * 100)}%
              </span>
              <input
                type="range"
                min={0}
                max={50}
                step={5}
                value={Math.round(levelSettings.current_level_share * 100)}
                disabled={isSavingLevelSettings || levelSettings.target_level === levelSettings.current_level}
                onChange={(e) => saveLevelSettings({ currentLevelShare: Number(e.target.value) / 100 })}
              />
            </li>
          </ul>
          {levelSettingsNotice && (
            <p className="error-text">
              {levelSettingsNotice.message}{" "}
              <button
                type="button"
                onClick={() => saveLevelSettings({ targetLevel: levelSettingsNotice.suggestedTargetLevel })}
              >
                Viser {DIFFICULTY_LABELS[levelSettingsNotice.suggestedTargetLevel]}
              </button>
            </p>
          )}
          {levelSettingsError && <p className="error-text">{levelSettingsError}</p>}
        </div>
      )}

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
