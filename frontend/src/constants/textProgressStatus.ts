export const TEXT_PROGRESS_STATUS_LABELS: Record<string, string> = {
  UNSEEN: "Jamais vu",
  ACTIVE: "Actif",
  WAITING_FOR_TEST_ASSIGNMENT: "En attente de test",
  TEST_ASSIGNED: "Assigné à un test",
  MASTERED: "Maîtrisé",
  MANUALLY_ACQUIRED: "Acquis manuellement",
  DISABLED: "Désactivé",
  BENCHED: "En pause (niveau)",
};

export const TEXT_PROGRESS_STATUS_PILL: Record<string, string> = {
  MASTERED: "pill-good",
  MANUALLY_ACQUIRED: "pill-good",
  ACTIVE: "pill-brand",
  TEST_ASSIGNED: "pill-brand",
  WAITING_FOR_TEST_ASSIGNMENT: "pill-warning",
  DISABLED: "pill-critical",
  BENCHED: "pill-warning",
  UNSEEN: "pill",
};
