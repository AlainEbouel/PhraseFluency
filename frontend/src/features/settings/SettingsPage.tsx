import { useEffect, useState } from "react";
import {
  fetchInsertionSettings,
  fetchLevelSettings,
  fetchSeriesSettings,
  updateInsertionSettings,
  updateLevelSettings,
  updateSeriesSettings,
} from "../../api/learning";
import { updatePreferences } from "../../api/users";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DIFFICULTY_LABELS } from "../../constants/difficulty";
import type {
  Difficulty,
  InsertionSettings,
  LevelSettings,
  SeriesSettings,
} from "../../types/learning";
import { useAuth } from "../auth/AuthContext";

const LEVEL_ORDER: Difficulty[] = ["A1", "A2", "B1", "B2", "C1", "C2"];
const SERIES_GOAL_OPTIONS = [5, 10, 15, 20, 25, 30];
const MIN_INSERTION_GAP = 0;
const MAX_INSERTION_GAP = 20;

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
  const [draftTargetLevel, setDraftTargetLevel] = useState<Difficulty | null>(null);
  const [draftCurrentLevelShare, setDraftCurrentLevelShare] = useState<number | null>(null);

  const [seriesSettings, setSeriesSettings] = useState<SeriesSettings | null>(null);
  const [seriesSettingsError, setSeriesSettingsError] = useState<string | null>(null);
  const [isSavingSeriesSettings, setIsSavingSeriesSettings] = useState(false);
  const [draftSeriesGoal, setDraftSeriesGoal] = useState<number | null>(null);

  const [insertionSettings, setInsertionSettings] = useState<InsertionSettings | null>(null);
  const [insertionSettingsError, setInsertionSettingsError] = useState<string | null>(null);
  const [isSavingInsertionSettings, setIsSavingInsertionSettings] = useState(false);
  const [draftInsertionGap, setDraftInsertionGap] = useState<number | null>(null);

  const [pendingConfirm, setPendingConfirm] = useState<{
    message: string;
    onConfirm: () => void;
  } | null>(null);

  useEffect(() => {
    fetchLevelSettings()
      .then(setLevelSettings)
      .catch(() => setLevelSettingsError("Impossible de charger les réglages de niveau."));
  }, []);

  useEffect(() => {
    fetchSeriesSettings()
      .then(setSeriesSettings)
      .catch(() => setSeriesSettingsError("Impossible de charger l'objectif de série."));
  }, []);

  useEffect(() => {
    fetchInsertionSettings()
      .then(setInsertionSettings)
      .catch(() => setInsertionSettingsError("Impossible de charger ce réglage."));
  }, []);

  // Drafts mirror the saved value on load and after every successful
  // apply, so "dirty" always means "differs from what's actually saved".
  useEffect(() => {
    if (levelSettings) {
      setDraftTargetLevel(levelSettings.target_level ?? levelSettings.current_level);
      setDraftCurrentLevelShare(levelSettings.current_level_share);
    }
  }, [levelSettings]);

  useEffect(() => {
    if (seriesSettings) setDraftSeriesGoal(seriesSettings.series_goal);
  }, [seriesSettings]);

  useEffect(() => {
    if (insertionSettings) setDraftInsertionGap(insertionSettings.new_text_insertion_gap);
  }, [insertionSettings]);

  async function saveSeriesGoal(goal: number) {
    setSeriesSettingsError(null);
    setIsSavingSeriesSettings(true);
    try {
      const result = await updateSeriesSettings(goal);
      setSeriesSettings(result);
    } catch {
      setSeriesSettingsError("Impossible de mettre à jour l'objectif pour l'instant.");
    } finally {
      setIsSavingSeriesSettings(false);
    }
  }

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

  async function saveInsertionGap(gap: number) {
    setInsertionSettingsError(null);
    setIsSavingInsertionSettings(true);
    try {
      const result = await updateInsertionSettings(gap);
      setInsertionSettings(result);
    } catch {
      setInsertionSettingsError("Impossible de mettre à jour ce réglage pour l'instant.");
    } finally {
      setIsSavingInsertionSettings(false);
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

  const levelDirty =
    levelSettings != null &&
    draftTargetLevel != null &&
    draftCurrentLevelShare != null &&
    (draftTargetLevel !== (levelSettings.target_level ?? levelSettings.current_level) ||
      Math.round(draftCurrentLevelShare * 100) !== Math.round(levelSettings.current_level_share * 100));

  const seriesDirty =
    seriesSettings != null && draftSeriesGoal != null && draftSeriesGoal !== seriesSettings.series_goal;

  const insertionDirty =
    insertionSettings != null &&
    draftInsertionGap != null &&
    draftInsertionGap !== insertionSettings.new_text_insertion_gap;

  function applyLevelSettings(targetLevel: Difficulty, currentLevelShare: number) {
    setPendingConfirm({
      message: `Le niveau visé passera à ${DIFFICULTY_LABELS[targetLevel]}, avec ${Math.round(
        currentLevelShare * 100
      )}% d'exercices à ton niveau actuel. Ce réglage s'applique immédiatement.`,
      onConfirm: () => saveLevelSettings({ targetLevel, currentLevelShare }),
    });
  }

  function applySeriesGoal() {
    if (draftSeriesGoal == null) return;
    setPendingConfirm({
      message: `L'objectif de série passera à ${draftSeriesGoal} question(s) par série.`,
      onConfirm: () => saveSeriesGoal(draftSeriesGoal),
    });
  }

  function applyInsertionGap() {
    if (draftInsertionGap == null) return;
    setPendingConfirm({
      message:
        draftInsertionGap === 0
          ? "Les nouveaux textes seront proposés immédiatement, sans attendre."
          : `Les nouveaux textes réapparaîtront après ${draftInsertionGap} autre(s) texte(s) au lieu du fond de la file.`,
      onConfirm: () => saveInsertionGap(draftInsertionGap),
    });
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

      {seriesSettings && draftSeriesGoal != null && (
        <div className="card">
          <h2>Objectif quotidien</h2>
          <p className="explore-hint">
            Tes exercices sont regroupés en séries de mini-objectifs — un récapitulatif
            s'affiche à la fin de chaque série. L'ordre et la banque de textes ne changent
            pas, c'est juste un repère pour avancer par petites étapes.
          </p>
          <ul className="kv-list">
            <li className="kv-row">
              <span className="kv-row-label">Questions par série</span>
              <select
                value={draftSeriesGoal}
                disabled={isSavingSeriesSettings}
                onChange={(e) => setDraftSeriesGoal(Number(e.target.value))}
              >
                {SERIES_GOAL_OPTIONS.map((goal) => (
                  <option key={goal} value={goal}>
                    {goal}
                  </option>
                ))}
              </select>
            </li>
          </ul>
          <button
            type="button"
            className="primary-button"
            disabled={!seriesDirty || isSavingSeriesSettings}
            onClick={applySeriesGoal}
          >
            Appliquer
          </button>
          {seriesSettingsError && <p className="error-text">{seriesSettingsError}</p>}
        </div>
      )}

      {levelSettings &&
        levelSettings.current_level &&
        draftTargetLevel != null &&
        draftCurrentLevelShare != null && (
          <div className="card">
            <h2>Niveau d'apprentissage</h2>
            <p className="explore-hint">
              Ta banque d'exercices mélange ton niveau actuel ({DIFFICULTY_LABELS[levelSettings.current_level]})
              et le niveau que tu vises.
            </p>
            <ul className="kv-list">
              <li className="kv-row">
                <span className="kv-row-label">Niveau visé</span>
                <select
                  value={draftTargetLevel}
                  disabled={isSavingLevelSettings}
                  onChange={(e) => setDraftTargetLevel(e.target.value as Difficulty)}
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
                  Part du niveau actuel : {Math.round(draftCurrentLevelShare * 100)}%
                </span>
                <input
                  type="range"
                  min={0}
                  max={50}
                  step={5}
                  value={Math.round(draftCurrentLevelShare * 100)}
                  disabled={isSavingLevelSettings || draftTargetLevel === levelSettings.current_level}
                  onChange={(e) => setDraftCurrentLevelShare(Number(e.target.value) / 100)}
                />
              </li>
            </ul>
            <button
              type="button"
              className="primary-button"
              disabled={!levelDirty || isSavingLevelSettings}
              onClick={() => applyLevelSettings(draftTargetLevel, draftCurrentLevelShare)}
            >
              Appliquer
            </button>
            {levelSettingsNotice && (
              <p className="error-text">
                {levelSettingsNotice.message}{" "}
                <button
                  type="button"
                  onClick={() =>
                    applyLevelSettings(levelSettingsNotice.suggestedTargetLevel, draftCurrentLevelShare)
                  }
                >
                  Viser {DIFFICULTY_LABELS[levelSettingsNotice.suggestedTargetLevel]}
                </button>
              </p>
            )}
            {levelSettingsError && <p className="error-text">{levelSettingsError}</p>}
          </div>
        )}

      {insertionSettings && draftInsertionGap != null && (
        <div className="card">
          <h2>Nouveauté dans la file</h2>
          <p className="explore-hint">
            Quand un texte est acquis, désactivé ou remplacé, son remplaçant peut être injecté
            tôt dans la file plutôt que d'attendre le fond. Ce réglage définit après combien
            d'autres textes actifs il ressort.
          </p>
          <ul className="kv-list">
            <li className="kv-row">
              <span className="kv-row-label">Nouveaux textes après</span>
              <input
                type="number"
                min={MIN_INSERTION_GAP}
                max={MAX_INSERTION_GAP}
                value={draftInsertionGap}
                disabled={isSavingInsertionSettings}
                onChange={(e) =>
                  setDraftInsertionGap(
                    Math.min(MAX_INSERTION_GAP, Math.max(MIN_INSERTION_GAP, Number(e.target.value)))
                  )
                }
              />
            </li>
          </ul>
          <button
            type="button"
            className="primary-button"
            disabled={!insertionDirty || isSavingInsertionSettings}
            onClick={applyInsertionGap}
          >
            Appliquer
          </button>
          {insertionSettingsError && <p className="error-text">{insertionSettingsError}</p>}
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

      {pendingConfirm && (
        <ConfirmDialog
          title="Confirmer ce changement ?"
          message={pendingConfirm.message}
          confirmLabel="Appliquer"
          onConfirm={() => {
            const { onConfirm } = pendingConfirm;
            setPendingConfirm(null);
            onConfirm();
          }}
          onCancel={() => setPendingConfirm(null)}
        />
      )}
    </div>
  );
}
