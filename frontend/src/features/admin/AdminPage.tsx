import { useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { GraduationCap } from "lucide-react";
import { Link } from "react-router-dom";
import {
  confirmImport,
  createAdminUser,
  disableText,
  disableUser,
  enableText,
  enableUser,
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
import { useAuth } from "../auth/AuthContext";

type Tab = "texts" | "imports" | "users";

export function AdminPage() {
  const [tab, setTab] = useState<Tab>("texts");

  return (
    <div className="admin-page">
      <div className="page-header">
        <div>
          <h1>Administration</h1>
          <p className="page-subtitle">Contenu, imports et utilisateurs.</p>
        </div>
        <Link to="/learn" className="primary-button page-header-cta">
          <GraduationCap /> Continuer l'apprentissage
        </Link>
      </div>
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
      <div className="card">
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
                <td>
                  <span className={text.enabled ? "pill pill-good" : "pill pill-critical"}>
                    {text.enabled ? "Actif" : "Désactivé"}
                  </span>
                </td>
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
      <div className="card">
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
    </div>
  );
}

function UsersTab() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"USER" | "ADMIN">("USER");
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    fetchAdminUsers().then(setUsers).catch(() => setUsers([]));
  }

  useEffect(() => {
    reload();
  }, []);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setIsCreating(true);
    setError(null);
    try {
      await createAdminUser(email, password, role);
      setEmail("");
      setPassword("");
      setRole("USER");
      reload();
    } catch {
      setError("Impossible de créer ce compte (email déjà utilisé ?).");
    } finally {
      setIsCreating(false);
    }
  }

  async function toggle(user: AdminUser) {
    setError(null);
    try {
      if (user.is_active) {
        await disableUser(user.id);
      } else {
        await enableUser(user.id);
      }
      reload();
    } catch {
      setError("Impossible de modifier le statut de ce compte.");
    }
  }

  return (
    <div>
      <div className="card create-user-card">
        <h2>Créer un compte</h2>
        <form className="create-user-form" onSubmit={handleCreate}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Mot de passe"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <select value={role} onChange={(e) => setRole(e.target.value as "USER" | "ADMIN")}>
            <option value="USER">Utilisateur</option>
            <option value="ADMIN">Admin</option>
          </select>
          <button type="submit" className="primary-button" disabled={isCreating}>
            {isCreating ? "Création..." : "Créer"}
          </button>
        </form>
        {error && <p className="error-text">{error}</p>}
      </div>

      <div className="card">
        <table className="stats-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Rôle</th>
              <th>Statut</th>
              <th>Créé le</th>
              <th>Dernière connexion</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users?.map((user) => (
              <tr key={user.id}>
                <td>{user.email}</td>
                <td>
                  <span className={user.role === "ADMIN" ? "pill pill-brand" : "pill"}>{user.role}</span>
                </td>
                <td>
                  <span className={user.is_active ? "pill pill-good" : "pill pill-critical"}>
                    {user.is_active ? "Actif" : "Désactivé"}
                  </span>
                </td>
                <td>{new Date(user.created_at).toLocaleDateString()}</td>
                <td>{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "—"}</td>
                <td>
                  <button
                    type="button"
                    onClick={() => toggle(user)}
                    disabled={user.id === currentUser?.id}
                    title={user.id === currentUser?.id ? "Vous ne pouvez pas désactiver votre propre compte" : undefined}
                  >
                    {user.is_active ? "Désactiver" : "Activer"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
