import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { Mic, MessageCircle, Sparkles, TrendingUp } from "lucide-react";
import { ApiError } from "../../api/client";
import { useAuth } from "./AuthContext";

export function LoginPage() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (user) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Connexion impossible.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-showcase">
        <span className="auth-showcase-logo">
          <MessageCircle />
        </span>
        <h1>PhraseFluency</h1>
        <p className="auth-showcase-tagline">
          Apprends à parler un anglais américain naturel, phrase après phrase.
        </p>
        <ul className="auth-showcase-features">
          <li>
            <Sparkles /> Retour instantané par IA
          </li>
          <li>
            <Mic /> Pratique à l'écrit et à l'oral
          </li>
          <li>
            <TrendingUp /> Progression adaptée à ton niveau
          </li>
        </ul>
      </div>
      <div className="auth-form-side">
        <form className="auth-card" onSubmit={handleSubmit}>
          <h1>Connexion</h1>
          <p className="auth-subtitle">Connectez-vous pour continuer votre apprentissage.</p>

          <label htmlFor="email">Adresse e-mail</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <label htmlFor="password">Mot de passe</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {error && <p className="auth-error" role="alert">{error}</p>}

          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Connexion..." : "Se connecter"}
          </button>
        </form>
      </div>
    </div>
  );
}
