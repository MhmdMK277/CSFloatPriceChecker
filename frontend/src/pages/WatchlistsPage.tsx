/** Watchlists: named groups with totals, per-item deltas, refresh and export. */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { Delta } from "../components/Delta";
import { SearchBox } from "../components/SearchBox";
import { SkeletonRows } from "../components/Skeleton";
import { useToasts } from "../components/Toasts";
import { timeAgo, usd } from "../format";
import type { WatchlistDetail, WatchlistSummary } from "../types";

export function WatchlistsPage() {
  const { push } = useToasts();
  const [lists, setLists] = useState<WatchlistSummary[] | null>(null);
  const [selected, setSelected] = useState<WatchlistDetail | null>(null);
  const [newName, setNewName] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const loadLists = useCallback(async (selectId?: number) => {
    const { watchlists } = await api.watchlists();
    setLists(watchlists);
    if (selectId ?? watchlists[0]?.id) {
      const detail = await api.watchlist(selectId ?? watchlists[0].id);
      setSelected(detail);
    } else {
      setSelected(null);
    }
  }, []);

  useEffect(() => {
    loadLists().catch(() => setLists([]));
  }, [loadLists]);

  const create = async () => {
    if (!newName.trim()) return;
    try {
      const { id } = await api.createWatchlist(newName.trim());
      setNewName("");
      await loadLists(id);
    } catch (err) {
      push({
        kind: "error",
        title: "Watchlists",
        body: err instanceof ApiError ? err.message : "Could not create the watchlist.",
      });
    }
  };

  const refresh = async () => {
    if (!selected) return;
    setRefreshing(true);
    try {
      const detail = await api.refreshWatchlist(selected.id);
      setSelected(detail);
      const { watchlists } = await api.watchlists();
      setLists(watchlists);
      if (detail.errors?.length) {
        push({ kind: "error", title: "Refresh", body: detail.errors[0] });
      }
    } catch (err) {
      push({
        kind: "error",
        title: "Refresh",
        body: err instanceof ApiError ? err.message : "Refresh failed.",
      });
    } finally {
      setRefreshing(false);
    }
  };

  const total = selected?.items.reduce((sum, i) => sum + (i.last_price_cents ?? 0), 0) ?? 0;
  const prevTotal = selected?.items.reduce((sum, i) => sum + (i.prev_price_cents ?? 0), 0) ?? 0;

  return (
    <div className="stack fade-in">
      <div className="page-head">
        <div>
          <h1>Watchlists</h1>
          <p>Group items, refresh their lowest prices in one click, export as CSV.</p>
        </div>
        <div className="row">
          <input
            type="text"
            placeholder="New watchlist name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && create()}
          />
          <button className="btn primary" onClick={create} disabled={!newName.trim()}>
            Create
          </button>
        </div>
      </div>

      {lists === null ? (
        <SkeletonRows rows={4} height={44} />
      ) : lists.length === 0 ? (
        <div className="empty">
          <h3>No watchlists yet</h3>
          Create one above — “Dream Loadout”, “Investments”, whatever you’re tracking.
        </div>
      ) : (
        <>
          <div className="row" role="tablist" aria-label="Watchlists">
            {lists.map((wl) => (
              <button
                key={wl.id}
                role="tab"
                aria-selected={selected?.id === wl.id}
                className={`btn sm ${selected?.id === wl.id ? "primary" : ""}`}
                onClick={() => api.watchlist(wl.id).then(setSelected)}
              >
                {wl.name} · {wl.item_count}
              </button>
            ))}
          </div>

          {selected && (
            <div className="panel stack">
              <div className="row spread">
                <div className="row" style={{ gap: 18 }}>
                  <h2>{selected.name}</h2>
                  <span className="num" style={{ fontSize: "var(--text-lg)", fontWeight: 600 }}>
                    {usd(total)}
                  </span>
                  <Delta current={total} previous={prevTotal || null} />
                </div>
                <div className="row">
                  <button
                    className="btn"
                    onClick={refresh}
                    disabled={refreshing || selected.items.length === 0}
                    data-state={refreshing ? "loading" : undefined}
                  >
                    {refreshing ? "Refreshing…" : "Refresh prices"}
                  </button>
                  <a className="btn ghost" href={`/api/watchlists/${selected.id}/export?fmt=csv`}>
                    Export CSV
                  </a>
                  <button
                    className="btn ghost danger"
                    onClick={async () => {
                      await api.deleteWatchlist(selected.id);
                      await loadLists();
                    }}
                  >
                    Delete
                  </button>
                </div>
              </div>

              <SearchBox
                placeholder="Add an item to this watchlist…"
                onPick={async (item) => {
                  await api.addWatchlistItem(selected.id, item.market_hash_name);
                  setSelected(await api.watchlist(selected.id));
                }}
              />

              {selected.items.length === 0 ? (
                <div className="empty">Empty — add items with the search box above.</div>
              ) : (
                <div className="table-wrap">
                  <table className="data">
                    <thead>
                      <tr>
                        <th>Item</th>
                        <th className="right">Lowest price</th>
                        <th className="right">Change</th>
                        <th className="right">Checked</th>
                        <th aria-label="actions" />
                      </tr>
                    </thead>
                    <tbody>
                      {selected.items.map((item) => (
                        <tr key={item.id}>
                          <td>
                            <Link
                              to={`/item/${encodeURIComponent(item.market_hash_name)}`}
                              className="link-accent"
                            >
                              {item.market_hash_name}
                            </Link>
                          </td>
                          <td className="right num" style={{ fontWeight: 600 }}>
                            {usd(item.last_price_cents)}
                          </td>
                          <td className="right">
                            <Delta current={item.last_price_cents} previous={item.prev_price_cents} />
                          </td>
                          <td className="right xsmall muted num">{timeAgo(item.last_checked_at)}</td>
                          <td className="right">
                            <button
                              className="btn sm ghost danger"
                              aria-label={`Remove ${item.market_hash_name}`}
                              onClick={async () => {
                                await api.removeWatchlistItem(selected.id, item.id);
                                setSelected(await api.watchlist(selected.id));
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
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
