/** Deal finder (sniper mode): config + rolling feed of below-reference listings. */

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import { SkeletonRows } from "../components/Skeleton";
import { MarketTag } from "../components/MarketTag";
import { Pagination, Th, usePagination, useSortable } from "../components/tableUtils";
import { useToasts } from "../components/Toasts";
import { floatShort, timeAgo, usd } from "../format";
import type { Deal, DealConfig } from "../types";

export function DealsPage() {
  const { push } = useToasts();
  const [config, setConfig] = useState<DealConfig | null>(null);
  const [deals, setDeals] = useState<Deal[] | null>(null);
  const [saving, setSaving] = useState(false);
  const sort = useSortable<Deal>("ts", "desc");
  const sortedDeals = useMemo(
    () => sort.apply(deals ?? []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [deals, sort.field, sort.dir],
  );
  const pages = usePagination(sortedDeals, "deals");

  const load = useCallback(async () => {
    const [c, d] = await Promise.all([api.dealConfig(), api.deals()]);
    setConfig(c);
    setDeals(d.deals);
  }, []);

  useEffect(() => {
    load().catch(() => {
      setDeals([]);
    });
    const timer = setInterval(() => api.deals().then((d) => setDeals(d.deals)).catch(() => {}), 30000);
    return () => clearInterval(timer);
  }, [load]);

  const save = async (patch: Partial<DealConfig>) => {
    if (!config) return;
    const next = { ...config, ...patch };
    setConfig(next);
    setSaving(true);
    try {
      await api.setDealConfig(next);
    } catch (err) {
      push({
        kind: "error",
        title: "Deal finder",
        body: err instanceof ApiError ? err.message : "Could not save the config.",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="stack fade-in">
      <div className="page-head">
        <div>
          <h1>Deal finder</h1>
          <p>
            Scans the newest listings and flags anything priced well below CSFloat’s own
            reference price for that item and wear.
          </p>
        </div>
        {config && (
          <button
            className={`btn ${config.enabled ? "" : "primary"}`}
            onClick={() => save({ enabled: !config.enabled })}
            disabled={saving}
          >
            {config.enabled ? "Stop scanning" : "Start scanning"}
          </button>
        )}
      </div>

      {config && (
        <div className="panel filters" style={{ marginBottom: 0 }}>
          <div className="field" style={{ width: 150 }}>
            <label>Min discount (%)</label>
            <input
              className="num"
              type="number"
              min="1"
              max="90"
              value={config.min_discount_pct}
              onChange={(e) => save({ min_discount_pct: Number(e.target.value) || 15 })}
            />
          </div>
          <div className="field" style={{ width: 150 }}>
            <label>Min price ($)</label>
            <input
              className="num"
              type="number"
              min="0"
              value={config.min_price_cents / 100}
              onChange={(e) => save({ min_price_cents: Math.round(Number(e.target.value) * 100) })}
            />
          </div>
          <div className="field" style={{ width: 150 }}>
            <label>Max price ($, blank = ∞)</label>
            <input
              className="num"
              type="number"
              min="0"
              value={config.max_price_cents !== null ? config.max_price_cents / 100 : ""}
              onChange={(e) =>
                save({
                  max_price_cents: e.target.value ? Math.round(Number(e.target.value) * 100) : null,
                })
              }
            />
          </div>
          <div className="field">
            <label>Scan every</label>
            <select
              value={config.interval_seconds}
              onChange={(e) => save({ interval_seconds: Number(e.target.value) })}
            >
              <option value={60}>1 min</option>
              <option value={120}>2 min</option>
              <option value={300}>5 min</option>
              <option value={600}>10 min</option>
            </select>
          </div>
          <span className={`badge ${config.enabled ? "up" : ""}`} style={{ alignSelf: "center" }}>
            {config.enabled ? "scanning" : "paused"}
          </span>
        </div>
      )}

      {deals === null ? (
        <SkeletonRows rows={7} height={46} />
      ) : deals.length === 0 ? (
        <div className="empty">
          <h3>No deals recorded yet</h3>
          Turn scanning on and give it a few minutes - hits also arrive as live toasts.
        </div>
      ) : (
        <>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <Th sort={sort} field="ts">Found</Th>
                <Th sort={sort} field="market_hash_name">Item</Th>
                <Th sort={sort} field="price_cents" right>
                  Price · <MarketTag market="csfloat" small />
                </Th>
                <th className="right">
                  Reference · <MarketTag market="csfloat" small />
                </th>
                <Th sort={sort} field="discount_pct" right>Discount</Th>
                <th className="right">Float</th>
                <th aria-label="link" />
              </tr>
            </thead>
            <tbody>
              {pages.rows.map((deal) => (
                <tr key={deal.id}>
                  <td className="xsmall muted num">{timeAgo(deal.ts)}</td>
                  <td style={{ overflowWrap: "anywhere" }}>
                    {deal.market_hash_name}
                    {deal.reason && (
                      <div className="xsmall" style={{ color: "var(--color-accent)" }}>
                        {deal.reason}
                      </div>
                    )}
                  </td>
                  <td className="right num" style={{ fontWeight: 600 }}>
                    {usd(deal.price_cents)}
                  </td>
                  <td className="right num muted">{usd(deal.reference_price_cents)}</td>
                  <td className="right">
                    <span className="badge up">−{deal.discount_pct.toFixed(1)}%</span>
                  </td>
                  <td className="right num">{floatShort(deal.float_value)}</td>
                  <td className="right">
                    <a className="btn sm ghost" href={deal.listing_url} target="_blank" rel="noreferrer">
                      Open ↗
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination state={pages} label="deals" />
        </>
      )}
    </div>
  );
}
