/** Single item: catalog metadata, price-history chart, tracking, live listings. */

import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { DiscountBadge } from "../components/Delta";
import { ListingsTable } from "../components/ListingsTable";
import { PriceChart } from "../components/PriceChart";
import { SkeletonRows, SkeletonTiles } from "../components/Skeleton";
import { useToasts } from "../components/Toasts";
import { floatFull, intervalLabel, usd } from "../format";
import type { HistoryResponse, ItemVariant, Listing } from "../types";

const INTERVALS = [60, 300, 900, 3600, 86400];

export function ItemPage() {
  const { name = "" } = useParams();
  const itemName = decodeURIComponent(name);
  const navigate = useNavigate();
  const { push } = useToasts();

  const [variant, setVariant] = useState<ItemVariant | null>(null);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [listings, setListings] = useState<Listing[] | null>(null);
  const [tracking, setTracking] = useState<{ id: number; interval: number } | null>(null);
  const [trackInterval, setTrackInterval] = useState(900);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setVariant(null);
    setHistory(null);
    setListings(null);
    api.itemDetail(itemName).then(setVariant).catch(() => setVariant(null));
    api.history(itemName).then(setHistory).catch(() => {});
    api
      .tracked()
      .then(({ tracked }) => {
        const hit = tracked.find((t) => t.market_hash_name === itemName && t.active);
        setTracking(hit ? { id: hit.id, interval: hit.interval_seconds } : null);
      })
      .catch(() => {});
    try {
      const resp = await api.listings({ name: itemName, sort_by: "lowest_price" });
      setListings(resp.listings);
    } catch (err) {
      setListings([]);
      if (err instanceof ApiError && err.status !== 401) {
        push({ kind: "error", title: "Listings", body: err.message });
      }
    }
  }, [itemName, push]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleTracking = async () => {
    setBusy(true);
    try {
      if (tracking) {
        await api.deleteTracked(tracking.id);
        setTracking(null);
        push({ kind: "info", title: "Tracking", body: `Stopped tracking ${itemName}` });
      } else {
        await api.track(itemName, trackInterval);
        push({
          kind: "info",
          title: "Tracking",
          body: `Recording ${itemName} every ${intervalLabel(trackInterval)}`,
        });
        const { tracked } = await api.tracked();
        const hit = tracked.find((t) => t.market_hash_name === itemName);
        if (hit) setTracking({ id: hit.id, interval: hit.interval_seconds });
      }
    } catch (err) {
      push({
        kind: "error",
        title: "Tracking",
        body: err instanceof ApiError ? err.message : "Failed to update tracking.",
      });
    } finally {
      setBusy(false);
    }
  };

  const summary = history?.summary;

  return (
    <div className="stack fade-in">
      <div className="page-head">
        <div className="row">
          {variant?.image && (
            <img src={variant.image} alt="" style={{ width: 96, height: 72, objectFit: "contain" }} />
          )}
          <div>
            <h1 style={{ overflowWrap: "anywhere" }}>{itemName}</h1>
            <p className="row" style={{ gap: 8 }}>
              {/* Knife/glove paint rarity from the schema confuses players (all knives read
                  as Covert in game), and merged Doppler names span several phases. */}
              {variant?.rarity_name && !["knife", "glove"].includes(variant.item_type) && (
                <span className="badge accent">{variant.rarity_name}</span>
              )}
              {variant?.item_type && <span className="badge">{variant.item_type}</span>}
              {variant?.min_float !== null && variant?.min_float !== undefined && (
                <span className="badge num" title="Possible float range">
                  {variant.min_float}–{variant.max_float}
                </span>
              )}
              {variant?.collection_names?.[0] && (
                <span className="muted xsmall">{variant.collection_names[0]}</span>
              )}
            </p>
          </div>
        </div>
        <div className="row">
          <select
            aria-label="Tracking interval"
            value={trackInterval}
            onChange={(e) => setTrackInterval(Number(e.target.value))}
            disabled={!!tracking}
          >
            {INTERVALS.map((s) => (
              <option key={s} value={s}>
                every {intervalLabel(s)}
              </option>
            ))}
          </select>
          <button
            className={`btn ${tracking ? "" : "primary"}`}
            onClick={toggleTracking}
            disabled={busy}
            data-state={busy ? "loading" : undefined}
          >
            {tracking ? "Stop tracking" : "Track price"}
          </button>
          <a
            className="btn ghost"
            href={`https://csfloat.com/search?market_hash_name=${encodeURIComponent(itemName)}`}
            target="_blank"
            rel="noreferrer"
          >
            CSFloat ↗
          </a>
        </div>
      </div>

      {variant === null && history === null ? (
        <SkeletonTiles />
      ) : (
        <div className="tiles">
          <div className="tile">
            <div className="label">Reference price</div>
            <div className="value">{usd(variant?.reference_price_cents)}</div>
          </div>
          <div className="tile">
            <div className="label">Latest tracked low</div>
            <div className="value">{usd(summary?.latest_cents)}</div>
          </div>
          <div className="tile">
            <div className="label">Tracked range</div>
            <div className="value" style={{ fontSize: "var(--text-md)" }}>
              {summary?.points ? `${usd(summary.lowest_cents)} – ${usd(summary.highest_cents)}` : "—"}
            </div>
          </div>
          <div className="tile">
            <div className="label">Trend</div>
            <div className="value">
              {summary?.trend === "up" ? (
                <span className="delta up">▲ rising</span>
              ) : summary?.trend === "down" ? (
                <span className="delta down">▼ falling</span>
              ) : (
                <span className="delta flat">→ stable</span>
              )}
            </div>
          </div>
        </div>
      )}

      {history && history.snapshots.length > 1 ? (
        <div className="panel">
          <div className="row spread" style={{ marginBottom: 8 }}>
            <h2>Price history</h2>
            <span className="xsmall muted num">{history.snapshots.length} snapshots</span>
          </div>
          <PriceChart snapshots={history.snapshots} />
        </div>
      ) : (
        <div className="panel empty">
          <h3>No price history yet</h3>
          Hit “Track price” and the background worker will record snapshots on your chosen
          interval — the chart appears after two data points.
        </div>
      )}

      <div className="stack" style={{ gap: 8 }}>
        <h2>Live listings — lowest first</h2>
        {listings === null ? (
          <SkeletonRows rows={6} height={52} />
        ) : listings.length > 0 ? (
          <ListingsTable listings={listings} showItemColumn={false} />
        ) : (
          <div className="empty">No active listings found (or the API key isn’t set).</div>
        )}
      </div>

      {listings && listings.length > 0 && listings[0].float_value !== null && (
        <p className="xsmall muted">
          Best float on page: <span className="num">{floatFull(Math.min(...listings.filter((l) => l.float_value !== null).map((l) => l.float_value as number)))}</span>
          {" · "}
          <DiscountBadge value={listings[0].discount_pct} />
          <button className="btn ghost sm" onClick={() => navigate(-1)} style={{ marginLeft: 12 }}>
            ← Back
          </button>
        </p>
      )}
    </div>
  );
}
