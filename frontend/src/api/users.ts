import { apiRequest } from "./client";
import type { User } from "../types/user";

export interface PreferencesUpdate {
  translation_enabled?: boolean;
  dictation_enabled?: boolean;
  sound_effects_enabled?: boolean;
}

export function updatePreferences(update: PreferencesUpdate): Promise<User> {
  return apiRequest("/api/v1/users/me/preferences", {
    method: "PATCH",
    body: JSON.stringify(update),
  });
}
