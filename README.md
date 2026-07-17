# CSFloat Tracker

**Self-hosted CS2 market intelligence for [CSFloat](https://csfloat.com).**
Search 35,000+ items with instant autocomplete, track prices over time, build
watchlists, get alerted on floats and price drops, snipe below-market deals,
and value your whole Steam inventory — from a fast web UI or your terminal.

![CI](https://github.com/MhmdMK277/CSFloatPriceChecker/actions/workflows/ci.yml/badge.svg)

| Market search with autocomplete | Item page with tracking |
| --- | --- |
| ![Search with autocomplete](docs/screenshots/search-autocomplete.jpg) | ![Item page](docs/screenshots/item-page.jpg) |

## Features

- **Live market search** — wear, float range, price range, StatTrak™/Souvenir,
  buy-now/auction, six sort orders. Every listing shows its float (full
  precision), stickers, paint seed, seller stats and how far below CSFloat's
  reference price it sits.
- **Always-fresh item catalog** — 35,000+ market names built from CSFloat's
  public schema (skins, knives with Doppler-phase awareness, gloves, stickers,
  patches, charms, cases, agents, music kits, graffiti…). Auto-refreshes when
  older than 7 days; one click / one command to refresh manually. A baseline
  ships with the repo so search works offline.
- **Price tracking & history** — track any item at 1 min → daily intervals.
  The background worker records lowest/average/median price, listing count and
  best float into SQLite; the item page renders it with TradingView charts.
- **Watchlists** — named groups with per-item lowest price, change since the
  last check and the group total. One-click refresh, CSV/JSON export.
- **Alerts** — "below $X", "float under 0.01", or both. Fires once per
  listing, logs every trigger, notifies in-app and optionally via Discord
  webhook.
- **Deal finder (sniper mode)** — continuously scans the newest listings and
  flags anything priced ≥ N % below its reference price, with a budget cap.
- **Inventory pricing** — paste your Steam profile URL or SteamID64, or use
  the SkinSearch-style **Manual Load**: open your own inventory JSON in the
  browser (bypasses Steam's aggressive rate limiting) and paste it in, with
  both the tradable and the post-April-2024 trade-protected contexts merged.
  Total value and per-item breakdown appear instantly, zero API budget spent.
- **Portfolio** — log your buys, see unrealized P&L and ROI against current
  reference prices.
- **A real terminal CLI** — `search`, `price`, `refresh-db`, `key`, `serve`.

## Quick start

### Download (easiest)

Grab the latest `CSFloatTracker-Windows.exe` from [Releases](../../releases),
double-click it, and your browser opens automatically. No Python, no Node, no
terminal — just paste your CSFloat API key in Settings and go. A tray icon
(amber trend-line) holds the *Open* and *Quit* actions; your data lives in
`%APPDATA%\csfloat-tracker` between runs.

Linux and macOS builds are also available on the Releases page (console
binaries — `Ctrl+C` to quit).

### Docker (one command)

```bash
git clone https://github.com/MhmdMK277/CSFloatPriceChecker.git
cd CSFloatPriceChecker
docker compose up --build
```

Open **http://localhost:8422**, go to *Settings*, paste your CSFloat API key.

### From source

Requirements: Python ≥ 3.11, Node ≥ 20. [`uv`](https://docs.astral.sh/uv/) recommended.

```bash
git clone https://github.com/MhmdMK277/CSFloatPriceChecker.git
cd CSFloatPriceChecker

# backend
uv venv .venv && uv pip install -e ".[dev]" --python .venv

# frontend
cd frontend && npm install && npm run build && cd ..

# run
.venv/bin/csfloat-tracker serve        # Windows: .venv\Scripts\csfloat-tracker serve
```

Or, with `make`: `make setup && make serve` (dev mode with hot reload: `make dev`).

### Getting a CSFloat API key

1. Sign in at [csfloat.com](https://csfloat.com)
2. **Profile → Developer → New API key**
3. Paste it into *Settings* in the web UI (or run `csfloat-tracker key set`)

The key is validated against CSFloat before being stored **in your OS
keychain** (Windows Credential Manager / macOS Keychain / Secret Service).
Where no keychain exists (e.g. Docker), it falls back to an owner-only file in
the app data directory. It is never written to the repo, logs, or any third
party.

## CLI

```text
csfloat-tracker serve                                 # web app + worker
csfloat-tracker search "kara dopp"                    # offline catalog search
csfloat-tracker price "AK-47 | Redline (Field-Tested)" --max-float 0.2
csfloat-tracker refresh-db                            # rebuild the catalog
csfloat-tracker key set | delete                      # manage the API key
csfloat-tracker status                                # catalog + key health
```

## How it stays fresh

The old prototype shipped a static item list that rotted within months. The
tracker instead rebuilds its catalog from `GET /api/v1/schema` — CSFloat's own
item database including per-wear reference prices — and expands it into every
purchasable market name (StatTrak™, Souvenir, wears, vanilla knives; Doppler
phases collapse into their shared market name with the cheapest phase as the
conservative reference). Reference prices power the deal finder, inventory
valuation and portfolio P&L without burning rate limit on `/listings`.

## Rate limits

All CSFloat access flows through one client that reads the
`X-RateLimit-*` headers, spaces requests per endpoint bucket, backs off
exponentially on 429/5xx, and defers background work (tracking, alerts, deal
scans) whenever interactive use needs the budget. The current bucket state is
always visible in the top bar.

## Project layout

```
├── src/csfloat_tracker/
│   ├── core/        # API client, item catalog, search, SQLite, secrets, stats
│   ├── server/      # FastAPI app, REST routes, WebSocket, background worker
│   └── cli.py       # typer CLI
├── frontend/        # Vite + React + TS web UI
├── data/            # shipped item catalog baseline (+ graffiti supplement)
├── tests/           # pytest suite (unit + API integration)
├── scripts/         # catalog generator
└── legacy/          # the original CLI/tkinter prototype, kept for reference
```

More detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Contributing

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). The short version:
`make setup`, `make test`, `make lint`, conventional commits.

## Non-goals

No auto-buy/sell bot, no scraping that violates CSFloat's ToS, no external
services receiving your API key, no crypto.

## License

[MIT](LICENSE). Not affiliated with CSFloat or Valve. CS2 item names and
images belong to their respective owners.
