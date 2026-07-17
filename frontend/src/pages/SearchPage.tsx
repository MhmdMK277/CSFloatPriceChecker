/** Market search: filters + live listings from CSFloat. */

import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { ListingsTable } from "../components/ListingsTable";
import { SearchBox } from "../components/SearchBox";
import { SkeletonRows } from "../components/Skeleton";
import { useToasts } from "../components/Toasts";
import { usd } from "../format";
import type { ItemVariant, Listing, ListingsResponse } from "../types";

const WEARS = ["FN", "MW", "FT", "WW", "BS"] as const;
const SORTS: [string, string][] = [
  ["lowest_price", "Lowest price"],
  ["highest_price", "Highest price"],
  ["lowest_float", "Lowest float"],
  ["highest_float", "Highest float"],
  ["most_recent", "Most recent"],
  ["best_deal", "Best deal"],
];

interface Filters {
  wear: string | null;
  category: string | null;
  sort_by: string;
  type: string | null;
  min_float: string;
  max_float: string;
  min_price: string;
  max_price: string;
}

const DEFAULT_FILTERS: Filters = {
  wear: null,
  category: null,
  sort_by: "lowest_price",
  type: null,
  min_float: "",
  max_float: "",
  min_price: "",
  max_price: "",
};

export function SearchPage() {
  const navigate = useNavigate();
  const { push } = useToasts();
  const [item, setItem] = useState<ItemVariant | null>(null);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [listings, setListings] = useState<Listing[]>([]);
  const [summary, setSummary] = useState<ListingsResponse["summary"] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);

  // First-run guidance: shown until a key exists or the user dismisses it.
  useEffect(() => {
    if (localStorage.getItem("onboarding_dismissed")) return;
    api
      .status()
      .then((s) => setShowOnboarding(!s.api_key_set))
      .catch(() => {});
  }, []);

  const dismissOnboarding = () => {
    localStorage.setItem("onboarding_dismissed", "1");
    setShowOnboarding(false);
  };

  const set = (patch: Partial<Filters>) => setFilters((f) => ({ ...f, ...patch }));

  const buildParams = useCallback(
    (withCursor: string | null) => ({
      name: item?.market_hash_name,
      wear: filters.wear,
      category: filters.category,
      sort_by: filters.sort_by,
      type: filters.type,
      min_float: filters.min_float || null,
      max_float: filters.max_float || null,
      min_price: filters.min_price ? Math.round(parseFloat(filters.min_price) * 100) : null,
      max_price: filters.max_price ? Math.round(parseFloat(filters.max_price) * 100) : null,
      cursor: withCursor,
    }),
    [item, filters],
  );

  const runSearch = useCallback(
    async (append = false) => {
      setLoading(true);
      setSearched(true);
      try {
        const resp = await api.listings(buildParams(append ? cursor : null));
        setListings((prev) => (append ? [...prev, ...resp.listings] : resp.listings));
        setSummary(resp.summary);
        setCursor(resp.cursor);
      } catch (err) {
        const message = err instanceof ApiError ? err.message : "Search failed.";
        push({ kind: "error", title: "Search", body: message });
        if (!append) {
          setListings([]);
          setSummary(null);
        }
      } finally {
        setLoading(false);
      }
    },
    [buildParams, cursor, push],
  );

  return (
    <div className="stack fade-in">
      <div className="page-head">
        <div>
          <h1>Market search</h1>
          <p>Live CSFloat listings - pick an item, tune the filters, hit search.</p>
        </div>
      </div>

      {showOnboarding && (
        <div className="panel stack" style={{ borderColor: "var(--color-accent)" }}>
          <div className="row spread">
            <h2>New here? Two minutes to full power</h2>
            <button className="btn ghost sm" onClick={dismissOnboarding} aria-label="Dismiss">
              Dismiss ✕
            </button>
          </div>
          <ol className="small" style={{ margin: 0, paddingLeft: "1.3em", lineHeight: 1.9 }}>
            <li>
              <strong>Works right now, no account:</strong> search the 35,000-item catalog above,
              and value your whole Steam inventory on the{" "}
              <Link className="link-accent" to="/inventory">Inventory</Link> page.
            </li>
            <li>
              <strong>For live listings, price tracking and the deal finder</strong>, grab a free
              CSFloat API key (Steam sign-in → Developers tab → new key) and paste it in{" "}
              <Link className="link-accent" to="/settings">Settings</Link>. It stays on your machine.
            </li>
            <li>
              New to floats, patterns or marketplace fees? The{" "}
              <Link className="link-accent" to="/guide">Guide</Link> explains the whole game in
              five minutes.
            </li>
          </ol>
        </div>
      )}

      <div className="panel stack">
        <SearchBox
          onPick={(picked) => {
            setItem(picked);
            setListings([]);
            setSummary(null);
            setSearched(false);
          }}
          placeholder="Pick an item to search listings for…"
        />
        {item && (
          <div className="row spread">
            <div className="row">
              {item.image && (
                <img src={item.image} alt="" style={{ width: 64, height: 48, objectFit: "contain" }} />
              )}
              <div>
                <strong>{item.market_hash_name}</strong>
                <div className="xsmall muted">
                  {item.rarity_name && <span>{item.rarity_name} · </span>}
                  {item.collection_names?.[0]}
                  {item.reference_price_cents ? (
                    <span>
                      {" "}· ref <span className="num">{usd(item.reference_price_cents)}</span>
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
            <button
              className="btn ghost sm"
              onClick={() => navigate(`/item/${encodeURIComponent(item.market_hash_name)}`)}
            >
              Item page →
            </button>
          </div>
        )}

        <div className="filters">
          <div className="field">
            <label>Wear</label>
            <div className="seg" role="group" aria-label="Wear filter">
              {WEARS.map((w) => (
                <button
                  key={w}
                  className={filters.wear === w ? "on" : ""}
                  onClick={() => set({ wear: filters.wear === w ? null : w })}
                >
                  {w}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            <label>Category</label>
            <div className="seg" role="group" aria-label="Category filter">
              {(["normal", "stattrak", "souvenir"] as const).map((c) => (
                <button
                  key={c}
                  className={filters.category === c ? "on" : ""}
                  onClick={() => set({ category: filters.category === c ? null : c })}
                >
                  {c === "stattrak" ? "ST™" : c === "souvenir" ? "Souv." : "Normal"}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            <label>Listing</label>
            <div className="seg" role="group" aria-label="Listing type">
              {(["buy_now", "auction"] as const).map((t) => (
                <button
                  key={t}
                  className={filters.type === t ? "on" : ""}
                  onClick={() => set({ type: filters.type === t ? null : t })}
                >
                  {t === "buy_now" ? "Buy now" : "Auction"}
                </button>
              ))}
            </div>
          </div>
          <div className="field" style={{ width: 110 }}>
            <label>Float min</label>
            <input
              className="num"
              type="number"
              step="0.001"
              min="0"
              max="1"
              placeholder="0.00"
              value={filters.min_float}
              onChange={(e) => set({ min_float: e.target.value })}
            />
          </div>
          <div className="field" style={{ width: 110 }}>
            <label>Float max</label>
            <input
              className="num"
              type="number"
              step="0.001"
              min="0"
              max="1"
              placeholder="1.00"
              value={filters.max_float}
              onChange={(e) => set({ max_float: e.target.value })}
            />
          </div>
          <div className="field" style={{ width: 110 }}>
            <label>$ min</label>
            <input
              className="num"
              type="number"
              min="0"
              placeholder="0"
              value={filters.min_price}
              onChange={(e) => set({ min_price: e.target.value })}
            />
          </div>
          <div className="field" style={{ width: 110 }}>
            <label>$ max</label>
            <input
              className="num"
              type="number"
              min="0"
              placeholder="∞"
              value={filters.max_price}
              onChange={(e) => set({ max_price: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Sort</label>
            <select value={filters.sort_by} onChange={(e) => set({ sort_by: e.target.value })}>
              {SORTS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <button
            className="btn primary"
            onClick={() => runSearch(false)}
            data-state={loading ? "loading" : undefined}
            disabled={loading}
          >
            {loading ? "Searching…" : "Search listings"}
          </button>
        </div>
      </div>

      {summary && summary.listing_count > 0 && (
        <div className="tiles">
          <div className="tile">
            <div className="label">Lowest</div>
            <div className="value">{usd(summary.min_price_cents)}</div>
          </div>
          <div className="tile">
            <div className="label">Median</div>
            <div className="value">{usd(summary.median_price_cents)}</div>
          </div>
          <div className="tile">
            <div className="label">Average</div>
            <div className="value">{usd(summary.avg_price_cents)}</div>
          </div>
          <div className="tile">
            <div className="label">Results</div>
            <div className="value">{listings.length}</div>
          </div>
        </div>
      )}

      {loading && listings.length === 0 ? (
        <SkeletonRows rows={8} height={52} />
      ) : listings.length > 0 ? (
        <>
          <ListingsTable listings={listings} />
          {cursor && (
            <button
              className="btn"
              style={{ alignSelf: "center" }}
              onClick={() => runSearch(true)}
              disabled={loading}
              data-state={loading ? "loading" : undefined}
            >
              {loading ? "Loading…" : "Load more"}
            </button>
          )}
        </>
      ) : searched && !loading ? (
        <div className="empty">
          <h3>No listings matched</h3>
          Loosen the float or price range, or try a different wear.
        </div>
      ) : (
        <div className="empty">
          <h3>Search the CS2 market</h3>
          Type <span className="num">/</span> to search - autocomplete covers skins, knives,
          gloves, stickers, cases, charms and more.
        </div>
      )}
    </div>
  );
}
