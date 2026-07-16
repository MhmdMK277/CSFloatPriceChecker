/** Steam inventory valuation: SteamID64 fetch or JSON upload. */

import { useState } from "react";
import { api, ApiError } from "../api";
import { SkeletonRows, SkeletonTiles } from "../components/Skeleton";
import { useToasts } from "../components/Toasts";
import { usd } from "../format";
import type { InventoryResponse } from "../types";

export function InventoryPage() {
  const { push } = useToasts();
  const [steamId, setSteamId] = useState("");
  const [result, setResult] = useState<InventoryResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchSteam = async () => {
    if (!/^\d{17}$/.test(steamId.trim())) {
      push({ kind: "error", title: "Inventory", body: "Enter a 17-digit SteamID64." });
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      setResult(await api.inventorySteam(steamId.trim()));
    } catch (err) {
      push({
        kind: "error",
        title: "Inventory",
        body: err instanceof ApiError ? err.message : "Could not fetch that inventory.",
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

  return (
    <div className="stack fade-in">
      <div className="page-head">
        <div>
          <h1>Inventory value</h1>
          <p>
            Priced against CSFloat reference prices — instant, no API budget spent. Inventory
            must be public for the SteamID route.
          </p>
        </div>
      </div>

      <div className="panel filters" style={{ marginBottom: 0 }}>
        <div className="field" style={{ flex: "1 1 260px", maxWidth: 380 }}>
          <label>SteamID64</label>
          <input
            className="num"
            type="text"
            inputMode="numeric"
            placeholder="7656119…"
            value={steamId}
            onChange={(e) => setSteamId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchSteam()}
          />
        </div>
        <button className="btn primary" onClick={fetchSteam} disabled={loading}>
          Fetch inventory
        </button>
        <span className="muted small" style={{ alignSelf: "center" }}>
          or
        </span>
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

      {loading && (
        <>
          <SkeletonTiles />
          <SkeletonRows rows={8} height={46} />
        </>
      )}

      {result && (
        <>
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
