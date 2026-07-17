/** Display formatting: money, floats, deltas, relative time. */

export const usd = (cents: number | null | undefined): string => {
  if (cents === null || cents === undefined) return "-";
  return (cents / 100).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

/** Full-precision float display; CS2 floats matter to many decimal places. */
export const floatFull = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return "-";
  return value.toFixed(14).replace(/0+$/, "").replace(/\.$/, ".0");
};

export const floatShort = (value: number | null | undefined): string =>
  value === null || value === undefined ? "-" : value.toFixed(6);

export const pct = (value: number | null | undefined, signed = true): string => {
  if (value === null || value === undefined) return "-";
  const sign = signed && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
};

export const timeAgo = (iso: string | null | undefined): string => {
  if (!iso) return "-";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "-";
  const seconds = Math.max(0, (Date.now() - then) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
};

export const WEAR_NAMES: Record<string, string> = {
  FN: "Factory New",
  MW: "Minimal Wear",
  FT: "Field-Tested",
  WW: "Well-Worn",
  BS: "Battle-Scarred",
};

export const intervalLabel = (seconds: number): string =>
  ({ 60: "1 min", 300: "5 min", 900: "15 min", 3600: "1 hour", 86400: "daily" })[seconds] ??
  `${seconds}s`;
