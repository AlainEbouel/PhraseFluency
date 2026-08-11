import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";

export function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <div className="app-nav-brand">PhraseFluency</div>
        <NavLink to="/" end className="app-nav-link">
          Tableau de bord
        </NavLink>
        <NavLink to="/learn" className="app-nav-link">
          Apprendre
        </NavLink>
        <NavLink to="/tests" className="app-nav-link">
          Tests
        </NavLink>
        <NavLink to="/statistics" className="app-nav-link">
          Statistiques
        </NavLink>
        {user?.role === "ADMIN" && (
          <NavLink to="/admin" className="app-nav-link">
            Admin
          </NavLink>
        )}
        <div className="app-nav-spacer" />
        <span className="app-nav-user">{user?.email}</span>
        <button type="button" className="app-nav-logout" onClick={() => void logout()}>
          Se déconnecter
        </button>
      </nav>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}
