import {
  BarChart3,
  ClipboardCheck,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Settings,
  ShieldCheck,
  User,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";

export function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <div className="app-nav-brand">
          <span className="app-nav-logo">
            <MessageCircle />
          </span>
          PhraseFluency
        </div>
        <NavLink to="/" end className="app-nav-link">
          <LayoutDashboard /> Tableau de bord
        </NavLink>
        <NavLink to="/learn" className="app-nav-link">
          <GraduationCap /> Apprendre
        </NavLink>
        <NavLink to="/tests" className="app-nav-link">
          <ClipboardCheck /> Tests
        </NavLink>
        <NavLink to="/statistics" className="app-nav-link">
          <BarChart3 /> Statistiques
        </NavLink>
        {user?.role === "ADMIN" && (
          <NavLink to="/admin" className="app-nav-link">
            <ShieldCheck /> Admin
          </NavLink>
        )}
        <NavLink to="/settings" className="app-nav-link">
          <Settings /> Réglages
        </NavLink>
        <div className="app-nav-spacer" />
        <span className="app-nav-user">
          <User size={14} /> {user?.email}
        </span>
        <button type="button" className="app-nav-logout" onClick={() => void logout()}>
          <LogOut /> Se déconnecter
        </button>
      </nav>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}
