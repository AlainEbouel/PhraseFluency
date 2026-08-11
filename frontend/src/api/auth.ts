import { apiRequest } from "./client";
import type { User } from "../types/user";

export function login(email: string, password: string): Promise<User> {
  return apiRequest<User>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout(): Promise<void> {
  return apiRequest<void>("/api/v1/auth/logout", { method: "POST" });
}

export function fetchCurrentUser(): Promise<User> {
  return apiRequest<User>("/api/v1/auth/me");
}
