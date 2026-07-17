/** App shell: side-rail nav, global search, rate meter, live event toasts. */

import { useCallback, useEffect, useState } from "react";
import { NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { api } from "./api";
import { SearchBox } from "./components/SearchBox";
import { ToastProvider, useToasts } from "./components/Toasts";
import { pct, usd } from "./format";
import { AlertsPage } from "./pages/AlertsPage";
import { DealsPage } from "./pages/DealsPage";
import { GuidePage } from "./pages/GuidePage";
import { InventoryPage } from "./pages/InventoryPage";
import { ItemPage } from "./pages/ItemPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { SearchPage } from "./pages/SearchPage";
import { SettingsPage } from "./pages/SettingsPage";
import { WatchlistsPage } from "./pages/WatchlistsPage";
import type { AppStatus, RateBucket } from "./types";
import { useLiveEvents } from "./ws";

const NAV = [
  { to: "/", label: "Search", icon: "M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14Zm9 16-3.5-3.5" },
  { to: "/watchlists", label: "Watchlists", icon: "M12 4l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 16.4 7.2 18.9l.9-5.4L4.2 9.7l5.4-.8L12 4Z" },
  { to: "/alerts", label: "Alerts", icon: "M12 3a6 6 0 0 1 6 6v3l1.7 3H4.3L6 12V9a6 6 0 0 1 6-6Zm-2 15a2 2 0 0 0 4 0" },
  { to: "/deals", label: "Deal finder", icon: "M4 17l5-5 3 3 8-8M14 7h6v6" },
  { to: "/inventory", label: "Inventory", icon: "M4 8l8-4 8 4v8l-8 4-8-4V8Zm8 0v12M4 8l8 4 8-4" },
  { to: "/portfolio", label: "Portfolio", icon: "M5 20V10m7 10V4m7 16v-7" },
  { to: "/guide", label: "Guide", icon: "M6 4h9a3 3 0 0 1 3 3v13H8a2 2 0 0 0-2 2V4Zm0 16a2 2 0 0 1 2-2h10M10 8h5m-5 4h5" },
  { to: "/settings", label: "Settings", icon: "M12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6Zm8 3-1.5 2.6.5 3-2.9 1-1.7 2.4h-3l-1.7-2.4-2.9-1 .5-3L4 12l1.5-2.6-.5-3 2.9-1L9.5 3h3l1.7 2.4 2.9 1-.5 3L20 12Z" },
];

function Shell() {
  const navigate = useNavigate();
  const { push } = useToasts();
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const [theme, setTheme] = useState<string>(
    () => localStorage.getItem("theme") ?? "dark",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  const loadStatus = useCallback(() => {
    api.status().then(setStatus).catch(() => {});
  }, []);

  useEffect(() => {
    loadStatus();
    const timer = setInterval(loadStatus, 30000);
    return () => clearInterval(timer);
  }, [loadStatus]);

  useLiveEvents((event) => {
    if (event.type === "alert") {
      push({
        kind: "info",
        title: "Alert",
        body: event.data.message,
        href: event.data.url,
      });
    } else if (event.type === "deal") {
      push({
        kind: "deal",
        title: `Deal · ${pct(event.data.discount_pct, false)} below reference`,
        body: `${event.data.market_hash_name} - ${usd(event.data.price_cents)}`,
        href: event.data.url,
      });
    }
  });

  const listingsRate: RateBucket | undefined = status?.rate?.listings;

  return (
    <div className="shell">
      {navOpen && (
        <button className="scrim" aria-label="Close navigation" onClick={() => setNavOpen(false)} />
      )}
      <aside className={`sidebar ${navOpen ? "open" : ""}`}>
        <div className="wordmark">
          CSFloat Tracker <small>v{status?.version ?? "1.0"}</small>
        </div>
        <nav className="nav" aria-label="Main">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => (isActive ? "active" : "")}
              onClick={() => setNavOpen(false)}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
                <path d={item.icon} />
              </svg>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          {status && !status.api_key_set && (
            <NavLink to="/settings" className="link-accent xsmall">
              Set your CSFloat API key →
            </NavLink>
          )}
          {status?.itemdb.stale && (
            <span title="Refresh from Settings">Item DB is stale</span>
          )}
          <button
            className="btn ghost sm"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            style={{ alignSelf: "start" }}
          >
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
        </div>
      </aside>

      <div className="main">
        <div className="topbar">
          <button
            className="btn ghost mobile-nav-toggle"
            aria-label="Open navigation"
            onClick={() => setNavOpen(true)}
          >
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
          <div className="searchbox-wrap searchbox" style={{ display: "contents" }}>
            <SearchBox
              onPick={(item) => navigate(`/item/${encodeURIComponent(item.market_hash_name)}`)}
            />
          </div>
          {listingsRate && listingsRate.limit !== null && (
            <div
              className="rate-meter"
              title={`CSFloat listings bucket: ${listingsRate.remaining}/${listingsRate.limit} left, resets in ${Math.round(listingsRate.resets_in_seconds)}s`}
            >
              <span>API</span>
              <span className="bar">
                <span
                  style={{
                    width: `${Math.round(((listingsRate.remaining ?? 0) / (listingsRate.limit || 1)) * 100)}%`,
                  }}
                />
              </span>
              <span>
                {listingsRate.remaining}/{listingsRate.limit}
              </span>
            </div>
          )}
        </div>

        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/item/:name" element={<ItemPage />} />
          <Route path="/watchlists" element={<WatchlistsPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/deals" element={<DealsPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/portfolio" element={<PortfolioPage />} />
          <Route path="/guide" element={<GuidePage />} />
          <Route path="/settings" element={<SettingsPage onStatusChange={loadStatus} />} />
        </Routes>
      </div>
    </div>
  );
}

export function App() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  );
}
