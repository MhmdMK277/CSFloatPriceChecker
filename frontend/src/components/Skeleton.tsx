/** Shimmer placeholders — used instead of spinners for all loading states. */

export function SkeletonRows({ rows = 6, height = 38 }: { rows?: number; height?: number }) {
  return (
    <div className="stack" style={{ gap: 8 }} aria-hidden>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton" style={{ height }} />
      ))}
    </div>
  );
}

export function SkeletonTiles({ count = 4 }: { count?: number }) {
  return (
    <div className="tiles" aria-hidden>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="skeleton" style={{ height: 72 }} />
      ))}
    </div>
  );
}
