/** Colored marketplace source tag - every displayed price carries one so
 * there's never ambiguity about which market a number comes from. */

const MARKET_META: Record<string, { label: string; color: string }> = {
  csfloat: { label: "CSFloat", color: "var(--market-csfloat)" },
  skinport: { label: "Skinport", color: "var(--market-skinport)" },
  steam: { label: "Steam", color: "var(--market-steam)" },
  buff163: { label: "Buff163", color: "var(--market-other)" },
  dmarket: { label: "DMarket", color: "var(--market-other)" },
  skinbaron: { label: "SkinBaron", color: "var(--market-other)" },
};

export function MarketTag({ market, small = false }: { market: string; small?: boolean }) {
  const meta = MARKET_META[market] ?? { label: market, color: "var(--market-other)" };
  return (
    <span
      className="market-tag"
      style={{ fontSize: small ? "0.66rem" : undefined }}
      title={`Price source: ${meta.label}`}
    >
      <span className="market-dot" style={{ background: meta.color }} aria-hidden />
      {meta.label}
    </span>
  );
}
