import { VERDICT_ICONS, VERDICT_LABELS } from "../constants/verdicts";

export function VerdictBadge({ verdict }: { verdict: string }) {
  const Icon = VERDICT_ICONS[verdict];
  return (
    <span className={`verdict-badge verdict-${verdict.toLowerCase()}`}>
      {Icon && <Icon />}
      {VERDICT_LABELS[verdict] ?? verdict}
    </span>
  );
}
