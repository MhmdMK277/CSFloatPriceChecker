# Changelog

## 1.4.0 — 2026-07-18

### Fixed
- **Stale-instance trap**: launching a newly downloaded build while an older
  version was still in the system tray silently opened the old app — making
  new features (like v1.3.0's inventory persistence) look broken. The
  launcher now detects the version mismatch and shows a warning telling you
  to quit the old tray instance first.
- Inventory session restore hardening: a visible "Restoring your last
  session…" state instead of a blank page, errors logged to the console
  instead of swallowed, and manual pastes/uploads now persist even when you
  never clicked Fetch (SteamID derived from the input client-side, with a
  server-side fallback to the remembered id).

### Added
- **Skinport integration** (no key needed): the public price feed is cached
  locally and refreshed in the background. Item pages show a marketplace
  comparison — lowest CSFloat vs Skinport buy price, and net sell payouts
  across six marketplaces with Skinport's tiered fees (12%/9%/6%). The deal
  finder cross-validates every hit ("cheaper on Skinport at $X" / "best
  price across CSFloat + Skinport").
- SkinBaron and Buff163 rows in the fee table; optional CSPriceAPI key
  storage in Settings for future Buff163/SkinBaron/C5Game price data.
- **Pagination + sortable columns** everywhere: inventory items (no more
  200-row cap), deals, alert events, portfolio and watchlists get clickable
  sort headers; big lists page at 25/50/100 rows with the page in the URL.
- Windows SmartScreen notice in the README; SignPath code-signing tracked
  upstream.

## 1.3.0 — 2026-07-17

### Added
- **Inventory persistence**: your SteamID64/profile input is remembered
  (localStorage + backend setting); every successful load saves a snapshot
  to SQLite; returning to the page instantly shows the last valuation with
  its age and an "Inventory value over time" history with per-load deltas.
  If you loaded manually last time, Manual Load starts expanded.
- **Marketplace fee comparison**: every item page shows what you'd receive
  selling at the reference price on CSFloat (2%), Buff163 (2.5%), DMarket
  (~5%), Skinport (12%) and Steam (15%, wallet-locked) — payout methods and
  caveats included. New `GET /api/markets/fees` endpoint.
- **Deal reasons**: the deal finder now explains each hit in trader terms —
  "top 1% float for FT", "costs less than the MW reference", "~$40 in
  stickers included" — in the feed, live toasts and Discord messages.
- **Trader's Guide page**: floats & wear brackets, pattern lore (blue gems,
  Doppler phases, fades), the 7-day market lock and April 2024
  trade-protection, the fee table, how this app prices things, and a
  one-minute API-key walkthrough.
- **First-run onboarding** on the Search page: what works without a key
  (catalog, inventory), how to get a key, where the Guide is.

### Changed
- README rewritten for traders: leads with what the tool does that browsing
  CSFloat.com doesn't.

## 1.2.0 — 2026-07-17

### Added
- **Inventory Manual Load** (SkinSearch-style): open your own inventory JSON
  links in the browser and paste the responses — reliable regardless of
  Steam's server-side rate limiting. Live validation shows the detected item
  count per paste; both inventory contexts (2 tradable, 16 trade-protected
  since Steam's April 2024 update) merge with per-context counts and
  assetid deduplication.
- Inventory input now accepts Steam profile URLs
  (`steamcommunity.com/profiles/<id64>`) as well as raw SteamID64s; custom
  `/id/<name>` URLs get a helpful pointer to steamid.io. Auto-fetch failures
  surface the Manual Load section pre-populated with your personal links.
- Auto-fetch now also attempts the trade-protected context (best effort) and
  flags truncated responses (`more_items`) with advice to raise `count=`.

## 1.1.0 — 2026-07-17

### Added
- **Downloadable desktop app** — single-file executables built with
  PyInstaller (`CSFloatTracker-Windows.exe`, `-Linux`, `-macOS`).
  Double-click → server starts → browser opens. Windows build is windowed
  with a system-tray icon (Open / Quit); launching a second instance just
  opens the browser. Logs rotate in the app-data `logs/` directory.
- `csfloat_tracker.desktop` launcher, `csfloat-tracker.spec`,
  `scripts/build_desktop.py` (frontend build + icon/version-info generation
  + SHA256), `make desktop`, and a `[desktop]` extras group
- Release workflow: tag `v*` → three-platform build → GitHub Release with
  binaries and `SHA256SUMS.txt`
- Bundle-aware path resolution (PyInstaller `sys._MEIPASS`) for the item
  catalog, graffiti supplement and frontend static files

## 1.0.0 — 2026-07-16

Complete renovation of the original CLI/tkinter prototype into a self-hosted
web application.

### Added
- Async CSFloat API client: header-aware per-endpoint rate limiting,
  exponential backoff, TTL caching, typed error hierarchy
- Item catalog built from CSFloat's public schema — 35,000+ market names with
  per-wear reference prices, Doppler-phase merging, vanilla knives, graffiti
  supplement; ships offline baseline, auto-refreshes after 7 days
- Ranked autocomplete (prefix → word-prefix → substring → fuzzy)
- FastAPI backend: search, listings proxy with discount-vs-reference,
  price history, watchlists (+ CSV export), alerts + event log, deal finder,
  Steam inventory valuation, portfolio P&L, settings, item-DB refresh
- Background worker: interval price tracking, once-per-listing alerts,
  below-reference deal scanning, Discord webhook notifications
- WebSocket live events (alerts / deals / snapshots)
- React web UI: dark terminal-inspired design system (light mode included),
  keyboard-first search, TradingView price charts, skeleton loading states,
  responsive to 375 px
- typer CLI: `serve`, `search`, `price`, `refresh-db`, `key`, `status`
- API key storage in the OS keychain (validated before storing)
- SQLite persistence for all state (WAL, app-data directory)
- 80+ tests (~84 % coverage), ruff lint, GitHub Actions CI, Docker +
  docker-compose, Makefile, pre-commit hooks

### Changed
- Prices handled as integer cents internally, rendered as USD in the UI
- The original prototype moved to `legacy/` for reference

### Removed
- tkinter/ttkbootstrap GUI (replaced by the web UI)
- Plaintext `csfloat_config.json` API key storage
- Scattered JSON/CSV state files (replaced by SQLite)
