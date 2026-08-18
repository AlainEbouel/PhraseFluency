import { AlertTriangle, CheckCircle2, Lightbulb, PenLine, XCircle } from "lucide-react";

// A status color never carries meaning alone: each verdict always pairs an
// icon with its label (dataviz skill, status palette mitigation rule).
export const VERDICT_LABELS: Record<string, string> = {
  CORRECT_NATURAL: "Naturel",
  CORRECT_WITH_USAGE_NOTE: "Correct (remarque d'usage)",
  CORRECT_UNNATURAL: "Correct, mais peu naturel",
  CORRECT_WITH_WRITING_ISSUES: "Correct (fautes d'écriture)",
  INCORRECT: "Incorrect",
};

export const VERDICT_ICONS: Record<string, typeof CheckCircle2> = {
  CORRECT_NATURAL: CheckCircle2,
  CORRECT_WITH_USAGE_NOTE: Lightbulb,
  CORRECT_UNNATURAL: AlertTriangle,
  CORRECT_WITH_WRITING_ISSUES: PenLine,
  INCORRECT: XCircle,
};
