/** Steam inventory valuation.
 *
 * Steam rate-limits server-side inventory fetches hard (April 2024 update),
 * so the page offers three routes: auto-fetch by profile URL / SteamID64,
 * SkinSearch-style manual paste of the inventory JSON (reliable), and a raw
 * JSON dump upload.
 */

import { useMemo, useState } from "react";
import { api, ApiError } from "../api";
import { SkeletonRows, SkeletonTiles } from "../components/Skeleton";
import { useToasts } from "../components/Toasts";
import { usd } from "../format";
import type { InventoryResponse } from "../types";

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
  const [input, setInput] = useState("");
  const [steamId, setSteamId] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [manualOpen, setManualOpen] = useState(false);
  const [tradablePaste, setTradablePaste] = useState("");
  const [protectedPaste, setProtectedPaste] = useState("");
  const [result, setResult] = useState<InventoryResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const tradableParsed = useMemo(() => validatePaste(tradablePaste), [tradablePaste]);
  const protectedParsed = useMemo(() => validatePaste(protectedPaste), [protectedPaste]);
  const canLoadManual =
    (tradableParsed?.data && !tradableParsed.error) ||
    (protectedParsed?.data && !protectedParsed.error);

  const fetchAuto = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setResult(null);
    setFetchError(null);
    try {
      const resp = await api.inventorySteam(input.trim());
      setSteamId(resp.steam_id);
      if (resp.inventory) {
        setResult(resp.inventory);
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
    setResult(null);
    try {
      const resp = await api.inventoryManual(
        tradableParsed?.error ? null : (tradableParsed?.data ?? null),
        protectedParsed?.error ? null : (protectedParsed?.data ?? null),
      );
      setResult(resp);
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
    setResult(null);
    try {
      const parsed = JSON.parse(await file.text());
      setResult(await api.inventoryUpload(parsed));
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

  const counts = result?.context_counts;
  const contextNote =
    counts && counts.trade_protected > 0
      ? `${result!.item_count} items (${counts.tradable} tradable + ${counts.trade_protected} trade-protected)`
      : null;

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
          {contextNote && <p className="small muted">{contextNote}</p>}
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
                  <th>Item</th>
                  <th className="right">Qty</th>
                  <th className="right">Each</th>
                  <th className="right">Line total</th>
                </tr>
              </thead>
              <tbody>
                {result.items.slice(0, 200).map((row) => (
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
          {result.items.length > 200 && (
            <p className="xsmall muted">Showing the 200 most valuable lines of {result.items.length}.</p>
          )}
        </>
      )}
    </div>
  );
}
