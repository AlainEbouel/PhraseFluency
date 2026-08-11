import { useEffect, useState } from "react";
import type { ChangeEvent } from "react";
import {
  confirmImport,
  disableText,
  enableText,
  fetchAdminTexts,
  fetchAdminUsers,
  fetchImportBatches,
  previewImport,
} from "../../api/admin";
import type {
  AdminTextSummary,
  AdminUser,
  ImportBatch,
  ImportPreview,
} from "../../api/admin";

type Tab = "texts" | "imports" | "users";

export function AdminPage() {
  const [tab, setTab] = useState<Tab>("texts");

  return (
    <div className="admin-page">
      <h1>Administration</h1>
      <div className="admin-tabs">
        <button className={tab === "texts" ? "active" : ""} onClick={() => setTab("texts")}>
          Textes
        </button>
        <button className={tab === "imports" ? "active" : ""} onClick={() => setTab("imports")}>
          Imports
        </button>
        <button className={tab === "users" ? "active" : ""} onClick={() => setTab("users")}>
          Utilisateurs
        </button>
      </div>

      {tab === "texts" && <TextsTab />}
      {tab === "imports" && <ImportsTab />}
      {tab === "users" && <UsersTab />}
    </div>
  );
}

function TextsTab() {
  const [texts, setTexts] = useState<AdminTextSummary[] | null>(null);
  const [search, setSearch] = useState("");

  function reload() {
    fetchAdminTexts(search || undefined).then(setTexts).catch(() => setTexts([]));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function toggle(text: AdminTextSummary) {
    if (text.enabled) {
      await disableText(text.id);
    } else {
      await enableText(text.id);
    }
    reload();
  }

  return (
    <div>
      <div className="admin-search-row">
        <input
          type="text"
          placeholder="Rechercher un texte français..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && reload()}
        />
        <button type="button" onClick={reload}>
          Rechercher
        </button>
      </div>
      <table className="stats-table">
        <thead>
          <tr>
            <th>Texte français</th>
            <th>Difficulté</th>
            <th>Type</th>
            <th>Statut</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {texts?.map((text) => (
            <tr key={text.id}>
              <td>{text.french_text}</td>
              <td>{text.difficulty}</td>
              <td>{text.exercise_type}</td>
              <td>{text.enabled ? "Actif" : "Désactivé"}</td>
              <td>
                <button type="button" onClick={() => toggle(text)}>
                  {text.enabled ? "Désactiver" : "Activer"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ImportsTab() {
  const [batches, setBatches] = useState<ImportBatch[] | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    fetchImportBatches().then(setBatches).catch(() => setBatches([]));
  }

  useEffect(() => {
    reload();
  }, []);

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    try {
      const result = await previewImport(file);
      setPreview(result);
    } catch {
      setError("Aperçu de l'import impossible. Vérifiez le format du fichier (CSV/JSON).");
    }
  }

  async function handleConfirm() {
    if (!preview) return;
    setIsImporting(true);
    try {
      await confirmImport(
        preview.filename,
        preview.rows.filter((r) => r.status !== "INVALID")
      );
      setPreview(null);
      reload();
    } catch {
      setError("La confirmation de l'import a échoué.");
    } finally {
      setIsImporting(false);
    }
  }

  return (
    <div>
      <h2>Importer des textes (CSV/JSON)</h2>
      <input type="file" accept=".csv,.json" onChange={handleFileChange} />
      {error && <p className="error-text">{error}</p>}

      {preview && (
        <div className="import-preview">
          <p>
            {preview.valid_count} valide(s) · {preview.duplicate_count} doublon(s) ·{" "}
            {preview.invalid_count} invalide(s) sur {preview.total_rows}
          </p>
          <ul className="import-preview-list">
            {preview.rows.map((row) => (
              <li key={row.row_number} className={`import-row-${row.status.toLowerCase()}`}>
                {row.french_text || "(vide)"} — {row.status}
                {row.errors.length > 0 && ` (${row.errors.join(", ")})`}
              </li>
            ))}
          </ul>
          <button type="button" className="primary-button" onClick={handleConfirm} disabled={isImporting}>
            {isImporting ? "Import..." : `Confirmer l'import de ${preview.valid_count} texte(s)`}
          </button>
        </div>
      )}

      <h2>Historique des imports</h2>
      <table className="stats-table">
        <thead>
          <tr>
            <th>Fichier</th>
            <th>Total</th>
            <th>Importés</th>
            <th>Doublons</th>
            <th>Rejetés</th>
          </tr>
        </thead>
        <tbody>
          {batches?.map((batch) => (
            <tr key={batch.id}>
              <td>{batch.filename}</td>
              <td>{batch.total_rows}</td>
              <td>{batch.imported_count}</td>
              <td>{batch.duplicate_count}</td>
              <td>{batch.rejected_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UsersTab() {
  const [users, setUsers] = useState<AdminUser[] | null>(null);

  useEffect(() => {
    fetchAdminUsers().then(setUsers).catch(() => setUsers([]));
  }, []);

  return (
    <table className="stats-table">
      <thead>
        <tr>
          <th>Email</th>
          <th>Rôle</th>
          <th>Créé le</th>
          <th>Dernière connexion</th>
        </tr>
      </thead>
      <tbody>
        {users?.map((user) => (
          <tr key={user.id}>
            <td>{user.email}</td>
            <td>{user.role}</td>
            <td>{new Date(user.created_at).toLocaleDateString()}</td>
            <td>{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
