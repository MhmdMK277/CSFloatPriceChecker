/** Portfolio: buys vs current reference value, P&L and ROI. */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { SearchBox } from "../components/SearchBox";
import { SkeletonRows } from "../components/Skeleton";
import { Pagination, Th, usePagination, useSortable } from "../components/tableUtils";
import { useToasts } from "../components/Toasts";
import { pct, usd } from "../format";
import type { ItemVariant, PortfolioEntry, PortfolioResponse } from "../types";

export function PortfolioPage() {
  const { push } = useToasts();
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [item, setItem] = useState<ItemVariant | null>(null);
  const [buyPrice, setBuyPrice] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [note, setNote] = useState("");

  const load = useCallback(() => api.portfolio().then(setPortfolio), []);

  useEffect(() => {
    load().catch(() => setPortfolio(null));
  }, [load]);

  const add = async () => {
    if (!item || !buyPrice) return;
    try {
      await api.addPortfolio({
        market_hash_name: item.market_hash_name,
        buy_price_cents: Math.round(parseFloat(buyPrice) * 100),
        quantity: Math.max(1, parseInt(quantity) || 1),
        note: note || undefined,
      });
      setItem(null);
      setBuyPrice("");
      setQuantity("1");
      setNote("");
      await load();
    } catch (err) {
      push({
        kind: "error",
        title: "Portfolio",
        body: err instanceof ApiError ? err.message : "Could not add the entry.",
      });
    }
  };

  const totalPnl = portfolio?.total_pnl_cents ?? null;
  const sort = useSortable<PortfolioEntry>("pnl_cents", "desc");
  const sortedEntries = useMemo(
    () => sort.apply(portfolio?.entries ?? []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [portfolio, sort.field, sort.dir],
  );
  const pages = usePagination(sortedEntries, "pf");

  return (
    <div className="stack fade-in">
      <div className="page-head">
        <div>
          <h1>Portfolio</h1>
          <p>Log what you paid; current value uses CSFloat reference prices.</p>
        </div>
      </div>

      <div className="panel stack">
        <SearchBox onPick={setItem} placeholder="Add a purchase…" />
        {item && (
          <div className="filters" style={{ marginBottom: 0 }}>
            <strong style={{ alignSelf: "center", overflowWrap: "anywhere" }}>
              {item.market_hash_name}
            </strong>
            <div className="field" style={{ width: 130 }}>
              <label>Buy price ($)</label>
              <input
                className="num"
                type="number"
                min="0"
                step="0.01"
                value={buyPrice}
                onChange={(e) => setBuyPrice(e.target.value)}
              />
            </div>
            <div className="field" style={{ width: 90 }}>
              <label>Qty</label>
              <input
                className="num"
                type="number"
                min="1"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
              />
            </div>
            <div className="field" style={{ flex: "1 1 160px" }}>
              <label>Note</label>
              <input
                type="text"
                placeholder="optional"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
            <button className="btn primary" onClick={add} disabled={!buyPrice}>
              Add entry
            </button>
          </div>
        )}
      </div>

      {portfolio === null ? (
        <SkeletonRows rows={5} height={46} />
      ) : (
        <>
          <div className="tiles">
            <div className="tile">
              <div className="label">Cost basis</div>
              <div className="value">{usd(portfolio.total_cost_cents)}</div>
            </div>
            <div className="tile">
              <div className="label">Current value</div>
              <div className="value">{usd(portfolio.total_value_cents)}</div>
            </div>
            <div className="tile">
              <div className="label">Unrealized P&amp;L</div>
              <div className="value">
                {totalPnl === null ? (
                  "-"
                ) : (
                  <span className={`delta ${totalPnl > 0 ? "up" : totalPnl < 0 ? "down" : "flat"}`}>
                    {totalPnl > 0 ? "▲" : totalPnl < 0 ? "▼" : "•"} {usd(Math.abs(totalPnl))}
                  </span>
                )}
              </div>
            </div>
            <div className="tile">
              <div className="label">Positions</div>
              <div className="value">{portfolio.entries.length}</div>
            </div>
          </div>

          {portfolio.entries.length === 0 ? (
            <div className="empty">
              <h3>Nothing logged yet</h3>
              Add your buys above to see live P&amp;L against the market.
            </div>
          ) : (
            <>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <Th sort={sort} field="market_hash_name">Item</Th>
                    <Th sort={sort} field="quantity" right>Qty</Th>
                    <Th sort={sort} field="buy_price_cents" right>Paid</Th>
                    <Th sort={sort} field="current_price_cents" right>Now</Th>
                    <Th sort={sort} field="pnl_cents" right>P&amp;L</Th>
                    <Th sort={sort} field="roi_pct" right>ROI</Th>
                    <th aria-label="actions" />
                  </tr>
                </thead>
                <tbody>
                  {pages.rows.map((entry) => (
                    <tr key={entry.id}>
                      <td>
                        <Link
                          to={`/item/${encodeURIComponent(entry.market_hash_name)}`}
                          className="link-accent"
                        >
                          {entry.market_hash_name}
                        </Link>
                        {entry.note && <div className="sub xsmall muted">{entry.note}</div>}
                      </td>
                      <td className="right num">{entry.quantity}</td>
                      <td className="right num">{usd(entry.buy_price_cents)}</td>
                      <td className="right num">{usd(entry.current_price_cents)}</td>
                      <td className="right">
                        {entry.pnl_cents === null ? (
                          <span className="delta flat">-</span>
                        ) : (
                          <span
                            className={`delta ${entry.pnl_cents > 0 ? "up" : entry.pnl_cents < 0 ? "down" : "flat"}`}
                          >
                            {entry.pnl_cents > 0 ? "▲" : entry.pnl_cents < 0 ? "▼" : "•"}{" "}
                            {usd(Math.abs(entry.pnl_cents))}
                          </span>
                        )}
                      </td>
                      <td className="right num">{entry.roi_pct !== null ? pct(entry.roi_pct) : "-"}</td>
                      <td className="right">
                        <button
                          className="btn sm ghost danger"
                          onClick={async () => {
                            await api.deletePortfolio(entry.id);
                            await load();
                          }}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination state={pages} label="positions" />
            </>
          )}
        </>
      )}
    </div>
  );
}
