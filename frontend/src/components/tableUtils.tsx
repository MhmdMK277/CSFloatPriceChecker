/** Reusable table plumbing: client-side sorting + pagination.
 *
 * Usage:
 *   const sort = useSortable<Row>("line_value_cents", "desc");
 *   const paged = usePagination(sort.apply(rows), "inv");
 *   <Th sort={sort} field="quantity">Qty</Th> …
 *   <Pagination state={paged} />
 */

import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

export type SortDir = "asc" | "desc";

export interface SortState<T> {
  field: keyof T | null;
  dir: SortDir;
  toggle: (field: keyof T) => void;
  apply: (rows: T[]) => T[];
}

export function useSortable<T>(initialField: keyof T | null = null, initialDir: SortDir = "desc"): SortState<T> {
  const [field, setField] = useState<keyof T | null>(initialField);
  const [dir, setDir] = useState<SortDir>(initialDir);

  const toggle = (next: keyof T) => {
    if (next === field) {
      setDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setField(next);
      setDir("desc");
    }
  };

  const apply = (rows: T[]): T[] => {
    if (!field) return rows;
    const sorted = [...rows].sort((a, b) => {
      const av = a[field];
      const bv = b[field];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (typeof av === "number" && typeof bv === "number") return av - bv;
      return String(av).localeCompare(String(bv));
    });
    return dir === "asc" ? sorted : sorted.reverse();
  };

  return { field, dir, toggle, apply };
}

/** Sortable header cell with direction indicator. */
export function Th<T>({
  sort,
  field,
  children,
  right = false,
}: {
  sort: SortState<T>;
  field: keyof T;
  children: React.ReactNode;
  right?: boolean;
}) {
  const active = sort.field === field;
  return (
    <th
      className={`sortable ${right ? "right" : ""}`}
      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
      onClick={() => sort.toggle(field)}
    >
      {children}
      <span aria-hidden style={{ opacity: active ? 1 : 0.25, marginLeft: 4 }}>
        {active ? (sort.dir === "asc" ? "▲" : "▼") : "▽"}
      </span>
    </th>
  );
}

export interface PageState<T> {
  rows: T[];       // current page slice
  page: number;    // 1-based
  pages: number;
  total: number;
  from: number;
  to: number;
  size: number;
  setPage: (page: number) => void;
  setSize: (size: number) => void;
}

const PAGE_SIZES = [25, 50, 100];

/** Client-side pagination with the page number reflected in the URL, so the
 * browser back button and shared links behave. `key` namespaces the query
 * param when multiple paginated lists share a page. */
export function usePagination<T>(rows: T[], key = "p"): PageState<T> {
  const [params, setParams] = useSearchParams();
  const [size, setSizeState] = useState(25);
  const param = `${key}page`;
  const rawPage = parseInt(params.get(param) ?? "1") || 1;

  const pages = Math.max(1, Math.ceil(rows.length / size));
  const page = Math.min(Math.max(1, rawPage), pages);

  const setPage = (next: number) => {
    const clamped = Math.min(Math.max(1, next), pages);
    setParams(
      (prev) => {
        if (clamped === 1) prev.delete(param);
        else prev.set(param, String(clamped));
        return prev;
      },
      { replace: false },
    );
  };

  const setSize = (next: number) => {
    setSizeState(next);
    setPage(1);
  };

  const slice = useMemo(
    () => rows.slice((page - 1) * size, page * size),
    [rows, page, size],
  );

  return {
    rows: slice,
    page,
    pages,
    total: rows.length,
    from: rows.length === 0 ? 0 : (page - 1) * size + 1,
    to: Math.min(page * size, rows.length),
    size,
    setPage,
    setSize,
  };
}

export function Pagination<T>({ state, label = "items" }: { state: PageState<T>; label?: string }) {
  if (state.total <= PAGE_SIZES[0]) return null;

  // Window of up to 5 page numbers centred on the current page.
  const start = Math.max(1, Math.min(state.page - 2, state.pages - 4));
  const numbers = Array.from({ length: Math.min(5, state.pages) }, (_, i) => start + i);

  return (
    <div className="row spread pagination" role="navigation" aria-label="Pagination">
      <span className="xsmall muted num">
        Showing {state.from}-{state.to} of {state.total} {label}
      </span>
      <div className="row" style={{ gap: 4 }}>
        <button className="btn sm ghost" disabled={state.page === 1} onClick={() => state.setPage(1)} aria-label="First page">
          «
        </button>
        <button className="btn sm ghost" disabled={state.page === 1} onClick={() => state.setPage(state.page - 1)} aria-label="Previous page">
          ‹
        </button>
        {numbers.map((n) => (
          <button
            key={n}
            className={`btn sm ${n === state.page ? "primary" : "ghost"}`}
            aria-current={n === state.page ? "page" : undefined}
            onClick={() => state.setPage(n)}
          >
            {n}
          </button>
        ))}
        <button className="btn sm ghost" disabled={state.page === state.pages} onClick={() => state.setPage(state.page + 1)} aria-label="Next page">
          ›
        </button>
        <button className="btn sm ghost" disabled={state.page === state.pages} onClick={() => state.setPage(state.pages)} aria-label="Last page">
          »
        </button>
        <select
          aria-label="Rows per page"
          value={state.size}
          onChange={(e) => state.setSize(Number(e.target.value))}
        >
          {PAGE_SIZES.map((s) => (
            <option key={s} value={s}>
              {s} / page
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
