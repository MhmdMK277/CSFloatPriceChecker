/** Steam inventory valuation.
 *
 * Steam rate-limits server-side inventory fetches hard (April 2024 update),
 * so the page offers three routes: auto-fetch by profile URL / SteamID64,
 * SkinSearch-style manual paste of the inventory JSON (reliable), and a raw
 * JSON dump upload.
 */

import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import { SkeletonRows, SkeletonTiles } from "../components/Skeleton";
import { MarketTag } from "../components/MarketTag";
import { Pagination, Th, usePagination, useSortable } from "../components/tableUtils";
import { useToasts } from "../components/Toasts";
import { timeAgo, usd } from "../format";
import type { InventoryHistoryEntry, InventoryResponse, InventoryRow } from "../types";

const STEAM_ID_LS_KEY = "csfloat_steam_id";

/** In-memory page state that survives route changes.
 *
 * React Router unmounts the page on navigation; rebuilding purely from the
 * backend makes "come back to a blank page" possible whenever that round
 * trip hiccups. This cache guarantees the loaded inventory reappears
 * instantly and unconditionally within the app session — the backend
 * snapshot only needs to cover restarts. */
interface InventoryPageCache {
  input: string;
  steamId: string | null;
  manualOpen: boolean;
  tradablePaste: string;
  protectedPaste: string;
  result: InventoryResponse | null;
  resultTs: string | null;
  history: InventoryHistoryEntry[];
}

let pageCache: InventoryPageCache | null = null;

const TRADE_PROTECTED_INFO =
  "Since Steam's April 2024 update, items received in a trade are trade-protected " +
  "for 10 days and live in a separate inventory section (context 16). Without this, " +
  "recently traded items would be missing from your total.";

function inventoryUrl(steamId: string, context: 2 | 16): string {
  return `https://steamcommunity.com/inventory/${steamId}/730/${context}?l=english&count=999`;
}

/** Validate pasted inventory JSON; returns a parse result for live feedback. */
function validatePaste(raw: string): { data?: unknown; count?: number; error?: string } | null {
  if (!raw.trim()) return null;
  try {
    const data = JSON.parse(raw);
    if (data && typeof data === "object" && Array.isArray((data as { assets?: unknown }).assets)) {
      return { data, count: (data as { assets: unknown[] }).assets.length };
    }
    if (data && typeof data === "object" && (data as { total_inventory_count?: number }).total_inventory_count === 0) {
      return { data, count: 0 };
    }
    return { error: "Valid JSON, but not a Steam inventory response (no \"assets\" array)." };
  } catch {
    return { error: "Not valid JSON — copy the entire response body from the browser tab." };
  }
}

function PasteBox({
  label,
  value,
  onChange,
  link,
  hint,
  info,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  link: string | null;
  hint: string;
  info?: string;
}) {
  const parsed = validatePaste(value);
  return (
    <div className="field" style={{ flex: "1 1 340px" }}>
      <label>
        {label}
        {info && (
          <span
            title={info}
            aria-label={info}
            style={{ cursor: "help", marginLeft: 6, opacity: 0.8 }}
          >
            ⓘ
          </span>
        )}
      </label>
      <p className="xsmall muted" style={{ margin: "0 0 4px" }}>
        {hint}{" "}
        {link ? (
          <a className="link-accent" href={link} target="_blank" rel="noreferrer">
            Open your inventory JSON ↗
          </a>
        ) : (
          <span>Enter your SteamID64 above to generate the link.</span>
        )}
      </p>
      <textarea
        className="num paste-box"
        rows={5}
        spellCheck={false}
        placeholder='Paste here — starts with {"assets":[{"appid":730,"contextid":…'
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={parsed?.error ? true : undefined}
      />
      {parsed?.error && <span className="xsmall" style={{ color: "var(--color-danger)" }}>✗ {parsed.error}</span>}
      {parsed && !parsed.error && (
        <span className="xsmall" style={{ color: "var(--color-up)" }}>
          ✓ {parsed.count} item{parsed.count === 1 ? "" : "s"} detected
        </span>
      )}
    </div>
  );
}

export function InventoryPage() {
  const { push } = useToasts();
  const [input, setInput] = useState(
    () => pageCache?.input ?? localStorage.getItem(STEAM_ID_LS_KEY) ?? "",
  );
  const [steamId, setSteamId] = useState<string | null>(
    () => pageCache?.steamId ?? localStorage.getItem(STEAM_ID_LS_KEY),
  );
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [manualOpen, setManualOpen] = useState(() => pageCache?.manualOpen ?? false);
  const [tradablePaste, setTradablePaste] = useState(() => pageCache?.tradablePaste ?? "");
  const [protectedPaste, setProtectedPaste] = useState(() => pageCache?.protectedPaste ?? "");
  const [result, setResult] = useState<InventoryResponse | null>(() => pageCache?.result ?? null);
  const [resultTs, setResultTs] = useState<string | null>(() => pageCache?.resultTs ?? null);
  const [history, setHistory] = useState<InventoryHistoryEntry[]>(() => pageCache?.history ?? []);
  const [loading, setLoading] = useState(false);
  // The in-memory cache renders instantly; only a truly cold visit shows the
  // restoring state while we ask the backend for the last snapshot.
  const [restoring, setRestoring] = useState(pageCache === null);

  // Keep the cache current — runs after every render, plain assignment.
  useEffect(() => {
    pageCache = {
      input, steamId, manualOpen, tradablePaste, protectedPaste,
      result, resultTs, history,
    };
  });

  // Cold start (no in-memory state): restore the last session from the
  // backend — remembered id, preferred method, latest snapshot.
  useEffect(() => {
    if (pageCache?.result) {
      // Warm revisit: state already on screen; just refresh history quietly.
      api
        .inventoryHistory()
        .then((h) => setHistory(h.snapshots))
        .catch((err) => console.error("inventoryHistory failed:", err));
      return;
    }
    api
      .inventorySession()
      .then((session) => {
        if (session.steam_id) {
          setSteamId(session.steam_id);
          localStorage.setItem(STEAM_ID_LS_KEY, session.steam_id);
          setInput((current) => current || session.steam_id!);
        }
        if (session.method === "manual") setManualOpen(true);
        if (session.latest) {
          setResult(session.latest);
          setResultTs(session.latest.ts);
        }
      })
      .catch((err) => console.error("inventorySession failed:", err))
      .finally(() => setRestoring(false));
    api
      .inventoryHistory()
      .then((h) => setHistory(h.snapshots))
      .catch((err) => console.error("inventoryHistory failed:", err));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Best-effort SteamID from the raw input, so manual loads persist even
   * when the user never clicked Fetch this session. */
  const clientSteamId = (): string | null => {
    const trimmed = input.trim().replace(/\/+$/, "");
    if (/^\d{17}$/.test(trimmed)) return trimmed;
    const m = trimmed.match(/steamcommunity\.com\/profiles\/(\d{17})/);
    return m ? m[1] : null;
  };

  const remember = (id: string | null) => {
    setSteamId(id);
    if (id) localStorage.setItem(STEAM_ID_LS_KEY, id);
  };

  const afterLoad = (resp: InventoryResponse) => {
    setResult(resp);
    setResultTs(null);
    api.inventoryHistory().then((h) => setHistory(h.snapshots)).catch(() => {});
  };

  const tradableParsed = useMemo(() => validatePaste(tradablePaste), [tradablePaste]);
  const protectedParsed = useMemo(() => validatePaste(protectedPaste), [protectedPaste]);
  const canLoadManual =
    (tradableParsed?.data && !tradableParsed.error) ||
    (protectedParsed?.data && !protectedParsed.error);

  const fetchAuto = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setFetchError(null);
    try {
      const resp = await api.inventorySteam(input.trim());
      if (resp.steam_id) remember(resp.steam_id);
      if (resp.inventory) {
        afterLoad(resp.inventory);
        setManualOpen(false);
      } else {
        setFetchError(resp.error ?? "Fetch failed.");
        // Rate limited or blocked: hand the user the reliable path, pre-populated.
        setManualOpen(true);
      }
    } catch (err) {
      setFetchError(err instanceof ApiError ? err.message : "Fetch failed.");
      setManualOpen(true);
    } finally {
      setLoading(false);
    }
  };

  const loadManual = async () => {
    setLoading(true);
    try {
      const effectiveId = steamId ?? clientSteamId();
      if (effectiveId) remember(effectiveId);
      const resp = await api.inventoryManual(
        tradableParsed?.error ? null : (tradableParsed?.data ?? null),
        protectedParsed?.error ? null : (protectedParsed?.data ?? null),
        effectiveId,
      );
      afterLoad(resp);
    } catch (err) {
      push({
        kind: "error",
        title: "Manual load",
        body: err instanceof ApiError ? err.message : "Could not parse the pasted inventory.",
      });
    } finally {
      setLoading(false);
    }
  };

  const uploadFile = async (file: File) => {
    setLoading(true);
    try {
      const parsed = JSON.parse(await file.text());
      afterLoad(await api.inventoryUpload(parsed, steamId ?? clientSteamId()));
    } catch (err) {
      push({
        kind: "error",
        title: "Inventory",
        body:
          err instanceof ApiError
            ? err.message
            : "That file doesn’t look like a Steam inventory JSON dump.",
      });
    } finally {
      setLoading(false);
    }
  };

  const itemSort = useSortable<InventoryRow>("line_value_cents", "desc");
  const sortedItems = useMemo(
    () => itemSort.apply(result?.items ?? []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [result, itemSort.field, itemSort.dir],
  );
  const itemPages = usePagination(sortedItems, "inv");

  const counts = result?.context_counts;
  const contextNote =
    counts && counts.trade_protected > 0
      ? `${result!.item_count} items (${counts.tradable} tradable + ${counts.trade_protected} trade-protected)`
      : null;
  const historyDelta =
    history.length >= 2
      ? history[history.length - 1].total_value_cents - history[0].total_value_cents
      : null;

  if (restoring) {
    return (
      <div className="stack fade-in">
        <div className="page-head">
          <div>
            <h1>Inventory value</h1>
            <p>Restoring your last session…</p>
          </div>
        </div>
        <SkeletonTiles />
        <SkeletonRows rows={6} height={46} />
      </div>
    );
  }

  return (
    <div className="stack fade-in">
      <div className="page-head">
        <div>
          <h1>Inventory value</h1>
          <p>
            Priced against CSFloat reference prices — instant, no API budget spent. Your
            inventory must be public.
          </p>
        </div>
      </div>

      <div className="panel stack">
        <div className="filters" style={{ marginBottom: 0 }}>
          <div className="field" style={{ flex: "1 1 320px", maxWidth: 520 }}>
            <label>Steam profile URL or SteamID64</label>
            <input
              type="text"
              placeholder="https://steamcommunity.com/profiles/7656119… or 7656119…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && fetchAuto()}
            />
          </div>
          <button
            className="btn primary"
            onClick={fetchAuto}
            disabled={loading || !input.trim()}
            data-state={loading ? "loading" : undefined}
          >
            {loading ? "Fetching…" : "Fetch inventory"}
          </button>
          <label className="btn" style={{ cursor: "pointer" }}>
            Upload JSON dump
            <input
              type="file"
              accept=".json,application/json"
              style={{ display: "none" }}
              onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])}
            />
          </label>
        </div>
        {fetchError && (
          <p className="small" style={{ color: "var(--color-danger)" }}>
            {fetchError}
          </p>
        )}
        {!manualOpen && (
          <button
            className="btn ghost sm"
            style={{ alignSelf: "start" }}
            onClick={() => setManualOpen(true)}
          >
            Having trouble? Load manually →
          </button>
        )}
      </div>

      {manualOpen && (
        <div className="panel stack fade-in" aria-label="Manual load">
          <h2>Manual load</h2>
          <p className="small muted" style={{ maxWidth: "72ch" }}>
            Since April 2024, Steam strictly limits how often inventories can be fetched by
            apps. Opening the links below in your own browser works reliably because you’re
            authenticated with Steam directly — select all (<span className="num">Ctrl+A</span>),
            copy (<span className="num">Ctrl+C</span>), and paste the response here.
          </p>
          <div className="row" style={{ alignItems: "stretch" }}>
            <PasteBox
              label="Tradable items"
              hint="Your regular inventory."
              link={steamId ? inventoryUrl(steamId, 2) : null}
              value={tradablePaste}
              onChange={setTradablePaste}
            />
            <PasteBox
              label="Trade-protected items (optional)"
              hint="Items traded in the last 10 days won’t appear in the tradable list."
              info={TRADE_PROTECTED_INFO}
              link={steamId ? inventoryUrl(steamId, 16) : null}
              value={protectedPaste}
              onChange={setProtectedPaste}
            />
          </div>
          {!steamId && (
            <p className="xsmall muted">
              Tip: enter your SteamID64 or profile URL above and hit “Fetch inventory” once —
              even if the fetch fails, it fills in your personal links here.
            </p>
          )}
          <button
            className="btn primary"
            style={{ alignSelf: "start" }}
            onClick={loadManual}
            disabled={!canLoadManual || loading}
            data-state={loading ? "loading" : undefined}
          >
            {loading ? "Loading…" : "Load inventory"}
          </button>
        </div>
      )}

      {loading && (
        <>
          <SkeletonTiles />
          <SkeletonRows rows={8} height={46} />
        </>
      )}

      {result && (
        <>
          <div className="row" style={{ gap: 8 }}>
            {resultTs ? (
              <span className="badge" title={resultTs}>
                saved snapshot · updated {timeAgo(resultTs)} — refresh above for current values
              </span>
            ) : (
              <span className="badge up">freshly loaded</span>
            )}
            {contextNote && <span className="small muted">{contextNote}</span>}
          </div>
          {result.truncated && (
            <p className="small" style={{ color: "var(--color-accent)" }}>
              Steam returned only part of this inventory. Change{" "}
              <span className="num">count=999</span> in the link to a higher value (max 2000)
              and paste again to capture everything.
            </p>
          )}
          <div className="tiles">
            <div className="tile">
              <div className="label">Total value</div>
              <div className="value">{usd(result.total_value_cents)}</div>
            </div>
            <div className="tile">
              <div className="label">Items</div>
              <div className="value">{result.item_count}</div>
            </div>
            <div className="tile">
              <div className="label">Priced</div>
              <div className="value">
                {result.priced_count}
                <span className="muted" style={{ fontSize: "var(--text-sm)" }}>
                  {" "}/ {result.priced_count + result.unpriced_count}
                </span>
              </div>
            </div>
            {Object.entries(result.value_by_type)
              .slice(0, 3)
              .map(([type, cents]) => (
                <div className="tile" key={type}>
                  <div className="label">{type.replace("_", " ")}</div>
                  <div className="value">{usd(cents)}</div>
                </div>
              ))}
          </div>

          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <Th sort={itemSort} field="market_hash_name">Item</Th>
                  <Th sort={itemSort} field="quantity" right>Qty</Th>
                  <Th sort={itemSort} field="reference_price_cents" right>
                    Each · <MarketTag market="csfloat" small />
                  </Th>
                  <Th sort={itemSort} field="line_value_cents" right>Line total</Th>
                </tr>
              </thead>
              <tbody>
                {itemPages.rows.map((row) => (
                  <tr key={row.market_hash_name}>
                    <td>
                      <div className="cell-item">
                        {row.image && <img src={row.image} alt="" loading="lazy" />}
                        <div style={{ minWidth: 0 }}>
                          <div className="name">{row.market_hash_name}</div>
                          <div className="sub">
                            {row.rarity_name ?? row.item_type}
                            {!row.marketable && " · not marketable"}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="right num">{row.quantity}</td>
                    <td className="right num">{usd(row.reference_price_cents)}</td>
                    <td className="right num" style={{ fontWeight: 600 }}>
                      {usd(row.line_value_cents)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination state={itemPages} label="items" />
        </>
      )}

      {history.length >= 2 && (
        <div className="panel stack" aria-label="Inventory history">
          <div className="row spread">
            <h2>Inventory value over time</h2>
            {historyDelta !== null && (
              <span
                className={`delta ${historyDelta > 0 ? "up" : historyDelta < 0 ? "down" : "flat"}`}
              >
                {historyDelta > 0 ? "▲" : historyDelta < 0 ? "▼" : "•"} {usd(Math.abs(historyDelta))}{" "}
                since {timeAgo(history[0].ts)}
              </span>
            )}
          </div>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>When</th>
                  <th className="right">Total value</th>
                  <th className="right">Items</th>
                  <th className="right">Change</th>
                </tr>
              </thead>
              <tbody>
                {[...history].reverse().map((snap, i, arr) => {
                  const prev = arr[i + 1];
                  const diff = prev ? snap.total_value_cents - prev.total_value_cents : null;
                  return (
                    <tr key={snap.ts}>
                      <td className="xsmall muted num" title={snap.ts}>
                        {timeAgo(snap.ts)}
                      </td>
                      <td className="right num" style={{ fontWeight: 600 }}>
                        {usd(snap.total_value_cents)}
                      </td>
                      <td className="right num">{snap.item_count}</td>
                      <td className="right">
                        {diff === null || diff === 0 ? (
                          <span className="delta flat">—</span>
                        ) : (
                          <span className={`delta ${diff > 0 ? "up" : "down"}`}>
                            {diff > 0 ? "▲" : "▼"} {usd(Math.abs(diff))}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
