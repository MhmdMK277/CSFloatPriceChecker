/** Color-coded price movement with a directional glyph (never color alone). */

import { pct, usd } from "../format";

export function Delta({
  current,
  previous,
}: {
  current: number | null;
  previous: number | null;
}) {
  if (current === null || previous === null || previous === 0) {
    return <span className="delta flat">-</span>;
  }
  const diff = current - previous;
  const cls = diff > 0 ? "up" : diff < 0 ? "down" : "flat";
  const glyph = diff > 0 ? "▲" : diff < 0 ? "▼" : "•";
  return (
    <span className={`delta ${cls}`}>
      {glyph} {usd(Math.abs(diff))} ({pct((diff / previous) * 100)})
    </span>
  );
}

export function DiscountBadge({ value }: { value: number | null }) {
  if (value === null || Math.abs(value) < 0.05) return null;
  const cls = value > 0 ? "up" : "down";
  const label = value > 0 ? `${value.toFixed(1)}% below ref` : `${Math.abs(value).toFixed(1)}% above ref`;
  return <span className={`badge ${cls}`}>{label}</span>;
}
