export type UserRole = "USER" | "ADMIN";

export interface User {
  id: string;
  email: string;
  role: UserRole;
  created_at: string;
  last_login_at: string | null;
  preferences: Record<string, unknown>;
}
