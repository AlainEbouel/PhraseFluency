export function Meter({
  value,
  max,
  label,
  tone = "brand",
}: {
  value: number;
  max: number;
  label?: string;
  tone?: "brand" | "good";
}) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className="meter" role="meter" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}>
      {label && <div className="meter-label">{label}</div>}
      <div className="meter-track">
        <div className={`meter-fill meter-fill-${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
