/** Alert rules + the alert event log. */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { SearchBox } from "../components/SearchBox";
import { SkeletonRows } from "../components/Skeleton";
import { Pagination, usePagination } from "../components/tableUtils";
import { useToasts } from "../components/Toasts";
import { floatShort, timeAgo, usd } from "../format";
import type { Alert, AlertEvent, ItemVariant } from "../types";

export function AlertsPage() {
  const { push } = useToasts();
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [item, setItem] = useState<ItemVariant | null>(null);
  const [maxPrice, setMaxPrice] = useState("");
  const [maxFloat, setMaxFloat] = useState("");
  const [minFloat, setMinFloat] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [a, e] = await Promise.all([api.alerts(), api.alertEvents(500)]);
    setAlerts(a.alerts);
    setEvents(e.events);
  }, []);
  const eventPages = usePagination(events, "ev");

  useEffect(() => {
    load().catch(() => setAlerts([]));
  }, [load]);

  const create = async () => {
    if (!item) return;
    const rule: Alert["rule"] = {};
    if (maxPrice) rule.max_price_cents = Math.round(parseFloat(maxPrice) * 100);
    if (maxFloat) rule.max_float = parseFloat(maxFloat);
    if (minFloat) rule.min_float = parseFloat(minFloat);
    if (Object.keys(rule).length === 0) {
      push({ kind: "error", title: "Alerts", body: "Set at least one condition (price or float)." });
      return;
    }
    setBusy(true);
    try {
      await api.createAlert(item.market_hash_name, rule);
      setItem(null);
      setMaxPrice("");
      setMaxFloat("");
      setMinFloat("");
      await load();
      push({ kind: "info", title: "Alerts", body: `Watching ${item.market_hash_name}` });
    } catch (err) {
      push({
        kind: "error",
        title: "Alerts",
        body: err instanceof ApiError ? err.message : "Could not create the alert.",
      });
    } finally {
      setBusy(false);
    }
  };

  const ruleText = (rule: Alert["rule"]) => {
    const parts: string[] = [];
    if (rule.max_price_cents !== undefined) parts.push(`price ≤ ${usd(rule.max_price_cents)}`);
    if (rule.max_float !== undefined) parts.push(`float ≤ ${rule.max_float}`);
    if (rule.min_float !== undefined) parts.push(`float ≥ ${rule.min_float}`);
    if (rule.type) parts.push(rule.type.replace("_", " "));
    return parts.join(" · ") || "any listing";
  };

  return (
    <div className="stack fade-in">
      <div className="page-head">
        <div>
          <h1>Alerts</h1>
          <p>
            The worker checks every active rule about once a minute and fires once per
            listing — in-app, and to Discord if a webhook is set.
          </p>
        </div>
      </div>

      <div className="panel stack">
        <h2>New alert</h2>
        <SearchBox onPick={setItem} placeholder="Which item should trigger the alert?" />
        {item && (
          <div className="filters" style={{ marginBottom: 0 }}>
            <strong style={{ alignSelf: "center", overflowWrap: "anywhere" }}>
              {item.market_hash_name}
            </strong>
            <div className="field" style={{ width: 130 }}>
              <label>Price below ($)</label>
              <input
                className="num"
                type="number"
                min="0"
                placeholder="e.g. 25"
                value={maxPrice}
                onChange={(e) => setMaxPrice(e.target.value)}
              />
            </div>
            <div className="field" style={{ width: 130 }}>
              <label>Float below</label>
              <input
                className="num"
                type="number"
                step="0.001"
                min="0"
                max="1"
                placeholder="e.g. 0.01"
                value={maxFloat}
                onChange={(e) => setMaxFloat(e.target.value)}
              />
            </div>
            <div className="field" style={{ width: 130 }}>
              <label>Float above</label>
              <input
                className="num"
                type="number"
                step="0.001"
                min="0"
                max="1"
                placeholder="optional"
                value={minFloat}
                onChange={(e) => setMinFloat(e.target.value)}
              />
            </div>
            <button className="btn primary" onClick={create} disabled={busy}>
              Create alert
            </button>
          </div>
        )}
      </div>

      {alerts === null ? (
        <SkeletonRows rows={4} height={44} />
      ) : alerts.length === 0 ? (
        <div className="empty">
          <h3>No alerts yet</h3>
          “Tell me when a Karambit Doppler FN goes under $1,100” — that kind of thing.
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Item</th>
                <th>Rule</th>
                <th className="right">Fired</th>
                <th className="right">Last</th>
                <th>Status</th>
                <th aria-label="actions" />
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => (
                <tr key={alert.id}>
                  <td>
                    <Link to={`/item/${encodeURIComponent(alert.market_hash_name)}`} className="link-accent">
                      {alert.market_hash_name}
                    </Link>
                  </td>
                  <td className="small muted">{ruleText(alert.rule)}</td>
                  <td className="right num">{alert.trigger_count}</td>
                  <td className="right xsmall muted num">{timeAgo(alert.last_triggered_at)}</td>
                  <td>
                    <span className={`badge ${alert.active ? "up" : ""}`}>
                      {alert.active ? "active" : "paused"}
                    </span>
                  </td>
                  <td className="right">
                    <div className="row" style={{ justifyContent: "flex-end", gap: 4 }}>
                      <button
                        className="btn sm ghost"
                        onClick={async () => {
                          await api.setAlertActive(alert.id, !alert.active);
                          await load();
                        }}
                      >
                        {alert.active ? "Pause" : "Resume"}
                      </button>
                      <button
                        className="btn sm ghost danger"
                        onClick={async () => {
                          await api.deleteAlert(alert.id);
                          await load();
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {events.length > 0 && (
        <div className="stack" style={{ gap: 8 }}>
          <h2>Recent triggers</h2>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Item</th>
                  <th className="right">Price</th>
                  <th className="right">Float</th>
                  <th aria-label="link" />
                </tr>
              </thead>
              <tbody>
                {eventPages.rows.map((event) => (
                  <tr key={event.id}>
                    <td className="xsmall muted num">{timeAgo(event.ts)}</td>
                    <td>{event.market_hash_name}</td>
                    <td className="right num">{usd(event.price_cents)}</td>
                    <td className="right num">{floatShort(event.float_value)}</td>
                    <td className="right">
                      {event.listing_id && (
                        <a
                          className="btn sm ghost"
                          href={`https://csfloat.com/item/${event.listing_id}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open ↗
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination state={eventPages} label="events" />
        </div>
      )}
    </div>
  );
}
