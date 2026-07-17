<div align="center">

# CSFloat Tracker

**Free, open-source CS2 market intelligence that runs on your own PC.**

Deal sniping with reasons, rate-limit-proof inventory valuation, price history,
watchlists, alerts, and marketplace fee comparison. No account. No subscription.
Your data never leaves your machine.

[![CI](https://github.com/MhmdMK277/CSFloatPriceChecker/actions/workflows/ci.yml/badge.svg)](https://github.com/MhmdMK277/CSFloatPriceChecker/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/MhmdMK277/CSFloatPriceChecker)](https://github.com/MhmdMK277/CSFloatPriceChecker/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/MhmdMK277/CSFloatPriceChecker/total)](https://github.com/MhmdMK277/CSFloatPriceChecker/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[**Download**](https://github.com/MhmdMK277/CSFloatPriceChecker/releases/latest) ·
[Report a bug](https://github.com/MhmdMK277/CSFloatPriceChecker/issues) ·
[Architecture](docs/ARCHITECTURE.md) ·
[Contributing](CONTRIBUTING.md)

<img src="docs/screenshots/search-autocomplete.jpg" alt="Searching 35,000+ CS2 items with instant autocomplete" width="80%">

</div>

## Table of contents

- [Why this exists](#why-this-exists)
- [Features](#features)
- [Quick start](#quick-start)
- [First run](#first-run)
- [How the data works](#how-the-data-works)
- [FAQ](#faq)
- [Contributing](#contributing)
- [License](#license)

## Why this exists

CSFloat.com is where the listings live. This tool is what watches them for you,
around the clock:

- **Deals with reasons.** Not just "18% below reference" but "top 1% float for
  FT", "costs less than the MW reference", "$40 in stickers included". Hits
  arrive as notifications the moment they appear, before they are gone.
- **Cross-market prices.** Skinport's live feed is built in (no key needed).
  Every item page shows the lowest CSFloat and Skinport buy price side by side,
  and what you would actually pocket selling on six marketplaces after fees.
- **Price history nobody else keeps for you.** Track any skin from 1-minute to
  daily intervals in your own local database. Inventory value is snapshotted on
  every load, so "up $31 since last week" is one glance away.
- **Inventory valuation that works.** Steam has rate-limited inventory fetches
  into the ground since April 2024. The Manual Load flow sidesteps it: open two
  links in your own browser, paste, done. Trade-protected items included.
- **Yours.** MIT-licensed, runs locally, SQLite you can open yourself, no
  telemetry. The only account involved is your own free CSFloat API key,
  stored in your OS keychain.

New to floats, patterns, or trade locks? The built-in **Guide** page explains
the whole game in five minutes.

## Features

| Page | What it does for you |
| --- | --- |
| **Search** | Autocomplete over 35,000+ market names. Wear, float, price and category filters. Full-precision floats, paint seeds, stickers, seller stats, discount vs reference on every listing. |
| **Deal finder** | Continuous scan of new listings against reference prices, with the reason each deal is a deal and a Skinport cross-check. Thresholds and budget caps you control. |
| **Inventory** | Profile-URL import, rate-limit-proof Manual Load (tradable + trade-protected), instant valuation, value-over-time history. Remembers everything between visits. |
| **Watchlists** | Named groups with per-item change and group totals. One-click refresh. CSV export. |
| **Alerts** | Price and float rules checked every minute. In-app toasts, optional Discord webhook, full trigger log. |
| **Portfolio** | Log your buys, see unrealized P&L and ROI against current prices. |
| **Guide** | Floats, wear brackets, blue gems, Doppler phases, trade locks, marketplace fees. Plain language. |
| **CLI** | `csfloat-tracker search / price / refresh-db / serve` for terminal people. |

## Quick start

### Option 1: Download (recommended)

1. Grab `CSFloatTracker-Windows.exe` from the
   [latest release](https://github.com/MhmdMK277/CSFloatPriceChecker/releases/latest)
   (Linux and macOS builds are there too).
2. Double-click it. Your browser opens to the app automatically.
3. That's it. A tray icon holds the Open and Quit actions, and your data
   persists in `%APPDATA%\csfloat-tracker` between runs.

> **Windows SmartScreen:** the app is not code-signed yet, so Windows may show
> "Windows protected your PC" on first launch. Click **More info**, then
> **Run anyway**. This happens once. You can verify your download against the
> SHA256 checksums published with each release; free code signing via SignPath
> Foundation is [in progress](https://github.com/MhmdMK277/CSFloatPriceChecker/issues/40).

### Option 2: Docker

```bash
git clone https://github.com/MhmdMK277/CSFloatPriceChecker.git
cd CSFloatPriceChecker
docker compose up --build
# open http://localhost:8422
```

### Option 3: From source

Requires Python 3.11+ and Node 20+. [`uv`](https://docs.astral.sh/uv/) recommended.

```bash
git clone https://github.com/MhmdMK277/CSFloatPriceChecker.git
cd CSFloatPriceChecker
uv venv .venv && uv pip install -e ".[dev]" --python .venv
cd frontend && npm install && npm run build && cd ..
.venv/bin/csfloat-tracker serve    # Windows: .venv\Scripts\csfloat-tracker serve
```

Or with make: `make setup && make serve` (`make dev` for hot reload).

## First run

Search, the item catalog, and inventory valuation work immediately with no
account or key.

For live listings, price tracking, alerts, and the deal finder, add a free
CSFloat API key (takes about a minute):

1. Sign in at [csfloat.com](https://csfloat.com) with Steam.
2. Click your avatar, then **Developers**, and create a new API key.
3. Paste it into **Settings** in the app.

The key is validated against CSFloat before being stored in your OS keychain
(Windows Credential Manager, macOS Keychain, or Secret Service). It is never
written to a plain file you might accidentally share, and never sent anywhere
except csfloat.com.

## How the data works

- **Item catalog:** rebuilt from CSFloat's public schema (per-wear reference
  prices included) and auto-refreshed when older than 7 days. No stale item
  lists.
- **Live listings:** CSFloat's market API through a rate-limit-aware client
  that reads the limit headers, backs off politely, and shows its remaining
  budget in the top bar.
- **Skinport prices:** the public Skinport feed, cached locally and refreshed
  in the background. No key required.
- **Everything else:** one SQLite database in your app-data directory. Open it
  yourself if you like.

Full design details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## FAQ

<details>
<summary><b>Is this a trading bot?</b></summary>

No. It never buys, sells, or trades on your behalf. It is a price checker,
tracker, and alerting tool only.
</details>

<details>
<summary><b>Does my API key or inventory data leave my machine?</b></summary>

No. The key lives in your OS keychain and is only ever sent to csfloat.com.
All state is stored in a local SQLite database. There is no telemetry.
</details>

<details>
<summary><b>Why does inventory import ask me to paste JSON?</b></summary>

Steam heavily rate-limits automated inventory fetches (since April 2024).
Opening your own inventory JSON in your browser works reliably because you are
authenticated with Steam directly. The app gives you the exact links to open
and merges both inventory sections, including trade-protected items.
</details>

<details>
<summary><b>Where do the prices come from?</b></summary>

Live listings and reference prices come from CSFloat. Skinport prices come
from Skinport's public API. Every price in the UI is labeled with its source.
Reference prices are fair-value estimates, not guaranteed sale prices.
</details>

## Contributing

Pull requests are welcome. The short version: `make setup`, `make test`
(119 tests), `make lint`, conventional commits. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the ground rules and where things go.

## License

[MIT](LICENSE). Not affiliated with CSFloat, Skinport, or Valve. CS2 item
names and images belong to their respective owners.
