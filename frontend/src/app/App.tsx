import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AdminRoute } from "../features/auth/AdminRoute";
import { AuthProvider } from "../features/auth/AuthContext";
import { LoginPage } from "../features/auth/LoginPage";
import { ProtectedRoute } from "../features/auth/ProtectedRoute";
import { AdminPage } from "../features/admin/AdminPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { LearningPage } from "../features/learning/LearningPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { StatisticsPage } from "../features/statistics/StatisticsPage";
import { TestsPage } from "../features/tests/TestsPage";
import { AppLayout } from "./AppLayout";

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="learn" element={<LearningPage />} />
            <Route path="tests" element={<TestsPage />} />
            <Route path="statistics" element={<StatisticsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route
              path="admin"
              element={
                <AdminRoute>
                  <AdminPage />
                </AdminRoute>
              }
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
