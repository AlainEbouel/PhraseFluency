import { apiRequest } from "./client";

export interface AdminTextSummary {
  id: string;
  french_text: string;
  difficulty: string;
  exercise_type: string;
  enabled: boolean;
  created_at: string;
}

export interface AdminTextVersion {
  id: string;
  french_text: string;
  difficulty: string;
  exercise_type: string;
  contexts: string[];
  grammar_concepts: string[];
  skills: string[];
  created_at: string;
}

export interface AdminTextDetail {
  id: string;
  enabled: boolean;
  current_version: AdminTextVersion;
  version_history: AdminTextVersion[];
}

export interface ImportBatch {
  id: string;
  filename: string;
  imported_by: string;
  created_at: string;
  total_rows: number;
  imported_count: number;
  duplicate_count: number;
  rejected_count: number;
}

export interface AdminUser {
  id: string;
  email: string;
  role: "USER" | "ADMIN";
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export function fetchAdminTexts(search?: string): Promise<AdminTextSummary[]> {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  return apiRequest(`/api/v1/admin/texts${query}`);
}

export function fetchAdminTextDetail(textId: string): Promise<AdminTextDetail> {
  return apiRequest(`/api/v1/admin/texts/${textId}`);
}

export function disableText(textId: string): Promise<AdminTextDetail> {
  return apiRequest(`/api/v1/admin/texts/${textId}/disable`, { method: "PATCH" });
}

export function enableText(textId: string): Promise<AdminTextDetail> {
  return apiRequest(`/api/v1/admin/texts/${textId}/enable`, { method: "PATCH" });
}

export function fetchImportBatches(): Promise<ImportBatch[]> {
  return apiRequest("/api/v1/admin/import-batches");
}

export function fetchAdminUsers(): Promise<AdminUser[]> {
  return apiRequest("/api/v1/admin/users");
}

export function createAdminUser(
  email: string,
  password: string,
  role: "USER" | "ADMIN"
): Promise<AdminUser> {
  return apiRequest("/api/v1/admin/users", {
    method: "POST",
    body: JSON.stringify({ email, password, role }),
  });
}

export function disableUser(userId: string): Promise<AdminUser> {
  return apiRequest(`/api/v1/admin/users/${userId}/disable`, { method: "PATCH" });
}

export function enableUser(userId: string): Promise<AdminUser> {
  return apiRequest(`/api/v1/admin/users/${userId}/enable`, { method: "PATCH" });
}

export interface AdminUserTextBankItem {
  text_id: string;
  french_text: string;
  status: string;
  natural_count: number;
  incorrect_count: number;
  times_presented: number;
}

export function fetchAdminUserTextBank(
  userId: string,
  search?: string
): Promise<AdminUserTextBankItem[]> {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  return apiRequest(`/api/v1/admin/users/${userId}/texts${query}`);
}

export function disableTextForUser(
  userId: string,
  textId: string
): Promise<AdminUserTextBankItem> {
  return apiRequest(`/api/v1/admin/users/${userId}/texts/${textId}/disable`, { method: "PATCH" });
}

export interface ImportRowPreview {
  row_number: number;
  french_text: string;
  difficulty: string;
  exercise_type: string;
  contexts: string[];
  grammar_concepts: string[];
  skills: string[];
  status: "VALID" | "DUPLICATE" | "INVALID";
  errors: string[];
}

export interface ImportPreview {
  filename: string;
  rows: ImportRowPreview[];
  total_rows: number;
  valid_count: number;
  duplicate_count: number;
  invalid_count: number;
}

export function previewImport(file: File): Promise<ImportPreview> {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest("/api/v1/imports/preview", { method: "POST", body: formData });
}

export function confirmImport(filename: string, rows: ImportRowPreview[]) {
  return apiRequest("/api/v1/imports/confirm", {
    method: "POST",
    body: JSON.stringify({
      filename,
      rows: rows.map((r) => ({
        french_text: r.french_text,
        difficulty: r.difficulty,
        exercise_type: r.exercise_type,
        contexts: r.contexts,
        grammar_concepts: r.grammar_concepts,
        skills: r.skills,
      })),
    }),
  });
}
