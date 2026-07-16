# Architecture

CSFloat Tracker is a local-first web application: a Python backend that owns
all state and talks to CSFloat, plus a React SPA it serves. Everything runs on
the user's machine; the only external calls are to `csfloat.com` and (for
inventory fetches) `steamcommunity.com`.

```
┌────────────────────────────────────────────────────────────┐
│  frontend/ (Vite + React + TS)                             │
│  SearchPage · ItemPage · Watchlists · Alerts · Deals ·     │
│  Inventory · Portfolio · Settings                          │
│        │  fetch /api/*            ▲ WebSocket /api/ws      │
└────────┼──────────────────────────┼────────────────────────┘
         ▼                          │ broadcasts
┌────────────────────────────────────────────────────────────┐
│  server/ (FastAPI)                                         │
│  routes/*  ──────────────┐   worker.py (asyncio loop)      │
│                          │   · tracked-item snapshots      │
│                          │   · alert checks (dedup/listing)│
│                          │   · deal scans vs reference     │
│                          ▼   · Discord webhook             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ core/                                                │  │
│  │ client.py    async httpx + RateLimiter + TTLCache    │  │
│  │ itemdb.py    catalog load/refresh/search/lookup      │  │
│  │ schema_parser.py  schema → BaseItem → ItemVariant    │  │
│  │ search.py    prefix/substring/fuzzy ranked index     │  │
│  │ storage.py   SQLite (aiosqlite)                      │  │
│  │ secrets.py   OS keychain / file fallback             │  │
│  │ inventory.py Steam inventory parse + fetch           │  │
│  │ stats.py     summaries, trends, discounts, P&L       │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────┬───────────────────────────┬───────────────────┘
             ▼                           ▼
      csfloat.com/api/v1        steamcommunity.com (public inv)
```

The CLI (`cli.py`) is a thin typer wrapper over the same `core/` modules —
no logic lives in it.

## Key decisions

### Item catalog from the schema endpoint

`GET /api/v1/schema` is CSFloat's own item database: every weapon, paint,
float range, and average price per wear. We parse it into ~16k compact
**base items** (`schema_parser.BaseItem`) and expand to ~35k purchasable
**market names** (`models.ItemVariant`) in memory at load time:

- StatTrak™ / Souvenir prefixes, wear suffixes from each paint's float range
- vanilla knives (`★ Karambit`) have no paint/wear suffix
- Doppler-style phases are separate paints in the schema but share one market
  name; the index keeps the **cheapest** phase as the conservative reference
  price and remembers the phase on the variant
- graffiti isn't in the schema; a static supplement (`data/graffiti.json`)
  fills it in

The compact form ships as `data/cs2_items.json` (~2.5 MB) so the app works
offline. At runtime a fresher copy lives in the app-data dir and auto-refreshes
when older than 7 days (`ItemDatabase.ensure_fresh`, never blocking startup).

**Reference prices are the workhorse.** Deal scoring, inventory valuation and
portfolio P&L all read them from the catalog instead of hammering `/listings`
— an entire inventory prices in microseconds with zero API budget.

### Rate limiting

`core/ratelimit.RateLimiter` tracks each endpoint bucket from the
`X-RateLimit-*` response headers, pre-emptively sleeps when a bucket is empty
(bounded by `max_wait`, then raises a typed `RateLimitError`), and the client
retries 429/5xx with exponential backoff + jitter. The background worker
treats `RateLimitError` as "skip this cycle", so interactive requests always
win eventually.

### Storage

One SQLite file (WAL mode) in the platform app-data directory
(`CSFLOAT_TRACKER_DATA` overrides; used by Docker/tests). Tables: `settings`,
`price_snapshots`, `watchlists`, `watchlist_items`, `tracked_items`, `alerts`,
`alert_events`, `deals`, `portfolio`. All access is async via aiosqlite; rows
surface as plain dicts.

### Secrets

`core/secrets.py` prefers the OS keychain via `keyring` and falls back to an
owner-only JSON file when no backend exists (headless Docker). The API key is
validated against `GET /me` **before** being stored, and the UI reports which
backend holds it.

### Background worker

A single asyncio task ticks every 15 s (`server/worker.py`):

1. **Tracking** — any active tracked item past its interval gets a listings
   fetch; the summary (min/avg/median/count/best float) becomes a snapshot.
2. **Alerts** (every 60 s) — one filtered listings query per active alert;
   matches are deduplicated per listing id via the alert-event log, so an
   alert fires exactly once per listing.
3. **Deal scan** (configurable) — newest `buy_now` listings compared against
   reference prices; hits are recorded (deduped by listing id), broadcast over
   WebSocket, and optionally posted to a Discord webhook.

### Errors

Every failure surfaces as a `CSFloatError` subclass carrying a
user-presentable message and an HTTP-ish status. The FastAPI exception handler
maps them to clean JSON (`{"error": "..."}`); stack traces never reach the UI.

### Frontend

Vite + React 18 + TypeScript, no UI framework — the design system is ~700
lines of hand-written CSS on OKLCH custom properties (see
`frontend/src/styles/tokens.css`, stamped with its design provenance).
Charts are TradingView `lightweight-charts`. Live updates arrive over
`/api/ws` and render as toasts. The backend serves `frontend/dist` with an
SPA fallback so deep links work.

## Testing

`tests/` covers the core (client retry/ratelimit behavior via respx, schema
expansion against a synthetic schema, storage CRUD, search ranking, stats) and
the full REST surface through an in-process ASGI transport, plus worker
behavior (snapshot intervals, alert dedup, deal scoring). CI runs ruff +
pytest (coverage gate 70%) on Python 3.11–3.13, typechecks/builds the
frontend, and builds the Docker image.
