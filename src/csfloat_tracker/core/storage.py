"""SQLite persistence for all tracker state.

One database file in the app data directory holds settings, price history,
watchlists, tracked items, alerts and the portfolio. All access is async
via aiosqlite; rows are returned as plain dicts.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from .paths import db_path

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS price_snapshots (
  id INTEGER PRIMARY KEY,
  market_hash_name TEXT NOT NULL,
  ts TEXT NOT NULL,
  min_price_cents INTEGER,
  avg_price_cents INTEGER,
  median_price_cents INTEGER,
  listing_count INTEGER,
  min_float REAL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_name_ts
  ON price_snapshots(market_hash_name, ts);

CREATE TABLE IF NOT EXISTS watchlists (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist_items (
  id INTEGER PRIMARY KEY,
  watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
  market_hash_name TEXT NOT NULL,
  filters_json TEXT NOT NULL DEFAULT '{}',
  added_at TEXT NOT NULL,
  last_price_cents INTEGER,
  prev_price_cents INTEGER,
  last_checked_at TEXT,
  UNIQUE(watchlist_id, market_hash_name)
);

CREATE TABLE IF NOT EXISTS tracked_items (
  id INTEGER PRIMARY KEY,
  market_hash_name TEXT UNIQUE NOT NULL,
  filters_json TEXT NOT NULL DEFAULT '{}',
  interval_seconds INTEGER NOT NULL DEFAULT 900,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  last_run_at TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY,
  market_hash_name TEXT NOT NULL,
  rule_json TEXT NOT NULL DEFAULT '{}',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  last_triggered_at TEXT,
  trigger_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS alert_events (
  id INTEGER PRIMARY KEY,
  alert_id INTEGER REFERENCES alerts(id) ON DELETE CASCADE,
  ts TEXT NOT NULL,
  listing_id TEXT,
  price_cents INTEGER,
  float_value REAL,
  message TEXT
);

CREATE TABLE IF NOT EXISTS deals (
  id INTEGER PRIMARY KEY,
  listing_id TEXT UNIQUE,
  market_hash_name TEXT NOT NULL,
  ts TEXT NOT NULL,
  price_cents INTEGER,
  reference_price_cents INTEGER,
  discount_pct REAL,
  float_value REAL,
  listing_url TEXT,
  reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_deals_ts ON deals(ts);

CREATE TABLE IF NOT EXISTS inventory_snapshots (
  id INTEGER PRIMARY KEY,
  steam_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  total_value_cents INTEGER NOT NULL,
  item_count INTEGER NOT NULL,
  priced_count INTEGER NOT NULL,
  items_json TEXT NOT NULL,
  context_counts_json TEXT NOT NULL,
  value_by_type_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_inv_steam_ts ON inventory_snapshots(steam_id, ts);

CREATE TABLE IF NOT EXISTS portfolio (
  id INTEGER PRIMARY KEY,
  market_hash_name TEXT NOT NULL,
  buy_price_cents INTEGER NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 1,
  acquired_at TEXT,
  note TEXT,
  created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _rows_to_dicts(cursor: aiosqlite.Cursor, rows: list) -> list[dict[str, Any]]:
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row, strict=False)) for row in rows]


class Storage:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = str(path or db_path())
        self._db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self._db = await aiosqlite.connect(self.path)
        await self._db.executescript(SCHEMA)
        await self._migrate()
        await self._db.commit()

    async def _migrate(self) -> None:
        """Additive column migrations for databases created by older versions."""
        import contextlib

        with contextlib.suppress(Exception):  # "duplicate column name" on fresh DBs
            await self.db.execute("ALTER TABLE deals ADD COLUMN reason TEXT")

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        assert self._db is not None, "Storage not opened"
        return self._db

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        cur = await self.db.execute(sql, params)
        rows = await cur.fetchall()
        return _rows_to_dicts(cur, list(rows))

    async def _fetchone(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        rows = await self._fetchall(sql, params)
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    async def get_setting(self, key: str, default: Any = None) -> Any:
        row = await self._fetchone("SELECT value FROM settings WHERE key=?", (key,))
        return json.loads(row["value"]) if row else default

    async def set_setting(self, key: str, value: Any) -> None:
        await self.db.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )
        await self.db.commit()

    async def all_settings(self) -> dict[str, Any]:
        rows = await self._fetchall("SELECT key,value FROM settings")
        return {r["key"]: json.loads(r["value"]) for r in rows}

    # ------------------------------------------------------------------
    # Price snapshots
    # ------------------------------------------------------------------

    async def add_snapshot(
        self,
        market_hash_name: str,
        *,
        min_price_cents: int | None,
        avg_price_cents: int | None,
        median_price_cents: int | None,
        listing_count: int | None,
        min_float: float | None,
        ts: str | None = None,
    ) -> None:
        await self.db.execute(
            "INSERT INTO price_snapshots"
            "(market_hash_name,ts,min_price_cents,avg_price_cents,median_price_cents,listing_count,min_float)"
            " VALUES(?,?,?,?,?,?,?)",
            (market_hash_name, ts or _now(), min_price_cents, avg_price_cents,
             median_price_cents, listing_count, min_float),
        )
        await self.db.commit()

    async def get_snapshots(
        self, market_hash_name: str, *, since: str | None = None, limit: int = 2000
    ) -> list[dict[str, Any]]:
        if since:
            return await self._fetchall(
                "SELECT * FROM price_snapshots WHERE market_hash_name=? AND ts>=? ORDER BY ts LIMIT ?",
                (market_hash_name, since, limit),
            )
        return await self._fetchall(
            "SELECT * FROM price_snapshots WHERE market_hash_name=? ORDER BY ts LIMIT ?",
            (market_hash_name, limit),
        )

    async def tracked_names_with_history(self) -> list[str]:
        rows = await self._fetchall("SELECT DISTINCT market_hash_name FROM price_snapshots")
        return [r["market_hash_name"] for r in rows]

    # ------------------------------------------------------------------
    # Watchlists
    # ------------------------------------------------------------------

    async def create_watchlist(self, name: str) -> dict[str, Any]:
        cur = await self.db.execute(
            "INSERT INTO watchlists(name,created_at) VALUES(?,?)", (name, _now())
        )
        await self.db.commit()
        return {"id": cur.lastrowid, "name": name}

    async def list_watchlists(self) -> list[dict[str, Any]]:
        return await self._fetchall(
            """SELECT w.*, COUNT(i.id) AS item_count,
                      COALESCE(SUM(i.last_price_cents),0) AS total_cents,
                      COALESCE(SUM(i.prev_price_cents),0) AS prev_total_cents
               FROM watchlists w LEFT JOIN watchlist_items i ON i.watchlist_id=w.id
               GROUP BY w.id ORDER BY w.name"""
        )

    async def get_watchlist(self, watchlist_id: int) -> dict[str, Any] | None:
        wl = await self._fetchone("SELECT * FROM watchlists WHERE id=?", (watchlist_id,))
        if not wl:
            return None
        items = await self._fetchall(
            "SELECT * FROM watchlist_items WHERE watchlist_id=? ORDER BY added_at", (watchlist_id,)
        )
        for it in items:
            it["filters"] = json.loads(it.pop("filters_json") or "{}")
        wl["items"] = items
        return wl

    async def rename_watchlist(self, watchlist_id: int, name: str) -> None:
        await self.db.execute("UPDATE watchlists SET name=? WHERE id=?", (name, watchlist_id))
        await self.db.commit()

    async def delete_watchlist(self, watchlist_id: int) -> None:
        await self.db.execute("DELETE FROM watchlists WHERE id=?", (watchlist_id,))
        await self.db.commit()

    async def add_watchlist_item(
        self, watchlist_id: int, market_hash_name: str, filters: dict | None = None
    ) -> None:
        await self.db.execute(
            "INSERT OR IGNORE INTO watchlist_items(watchlist_id,market_hash_name,filters_json,added_at)"
            " VALUES(?,?,?,?)",
            (watchlist_id, market_hash_name, json.dumps(filters or {}), _now()),
        )
        await self.db.commit()

    async def remove_watchlist_item(self, watchlist_id: int, item_id: int) -> None:
        await self.db.execute(
            "DELETE FROM watchlist_items WHERE id=? AND watchlist_id=?", (item_id, watchlist_id)
        )
        await self.db.commit()

    async def update_watchlist_item_price(self, item_id: int, price_cents: int | None) -> None:
        await self.db.execute(
            """UPDATE watchlist_items
               SET prev_price_cents=COALESCE(last_price_cents, ?),
                   last_price_cents=?, last_checked_at=?
               WHERE id=?""",
            (price_cents, price_cents, _now(), item_id),
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Tracked items (background price recording)
    # ------------------------------------------------------------------

    async def add_tracked_item(
        self, market_hash_name: str, filters: dict | None = None, interval_seconds: int = 900
    ) -> None:
        await self.db.execute(
            """INSERT INTO tracked_items(market_hash_name,filters_json,interval_seconds,created_at)
               VALUES(?,?,?,?)
               ON CONFLICT(market_hash_name) DO UPDATE
               SET interval_seconds=excluded.interval_seconds, active=1,
                   filters_json=excluded.filters_json""",
            (market_hash_name, json.dumps(filters or {}), interval_seconds, _now()),
        )
        await self.db.commit()

    async def list_tracked_items(self, active_only: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM tracked_items"
        if active_only:
            sql += " WHERE active=1"
        rows = await self._fetchall(sql + " ORDER BY market_hash_name")
        for r in rows:
            r["filters"] = json.loads(r.pop("filters_json") or "{}")
        return rows

    async def set_tracked_item_active(self, item_id: int, active: bool) -> None:
        await self.db.execute(
            "UPDATE tracked_items SET active=? WHERE id=?", (1 if active else 0, item_id)
        )
        await self.db.commit()

    async def delete_tracked_item(self, item_id: int) -> None:
        await self.db.execute("DELETE FROM tracked_items WHERE id=?", (item_id,))
        await self.db.commit()

    async def mark_tracked_item_run(self, item_id: int) -> None:
        await self.db.execute(
            "UPDATE tracked_items SET last_run_at=? WHERE id=?", (_now(), item_id)
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    async def create_alert(self, market_hash_name: str, rule: dict) -> dict[str, Any]:
        cur = await self.db.execute(
            "INSERT INTO alerts(market_hash_name,rule_json,created_at) VALUES(?,?,?)",
            (market_hash_name, json.dumps(rule), _now()),
        )
        await self.db.commit()
        return {"id": cur.lastrowid}

    async def list_alerts(self, active_only: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM alerts"
        if active_only:
            sql += " WHERE active=1"
        rows = await self._fetchall(sql + " ORDER BY created_at DESC")
        for r in rows:
            r["rule"] = json.loads(r.pop("rule_json") or "{}")
        return rows

    async def set_alert_active(self, alert_id: int, active: bool) -> None:
        await self.db.execute(
            "UPDATE alerts SET active=? WHERE id=?", (1 if active else 0, alert_id)
        )
        await self.db.commit()

    async def delete_alert(self, alert_id: int) -> None:
        await self.db.execute("DELETE FROM alerts WHERE id=?", (alert_id,))
        await self.db.commit()

    async def record_alert_event(
        self, alert_id: int, *, listing_id: str | None, price_cents: int | None,
        float_value: float | None, message: str,
    ) -> None:
        await self.db.execute(
            "INSERT INTO alert_events(alert_id,ts,listing_id,price_cents,float_value,message)"
            " VALUES(?,?,?,?,?,?)",
            (alert_id, _now(), listing_id, price_cents, float_value, message),
        )
        await self.db.execute(
            "UPDATE alerts SET last_triggered_at=?, trigger_count=trigger_count+1 WHERE id=?",
            (_now(), alert_id),
        )
        await self.db.commit()

    async def list_alert_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return await self._fetchall(
            """SELECT e.*, a.market_hash_name FROM alert_events e
               LEFT JOIN alerts a ON a.id=e.alert_id
               ORDER BY e.ts DESC LIMIT ?""",
            (limit,),
        )

    async def latest_alert_event_listing_ids(self, alert_id: int, limit: int = 50) -> set[str]:
        rows = await self._fetchall(
            "SELECT listing_id FROM alert_events WHERE alert_id=? ORDER BY ts DESC LIMIT ?",
            (alert_id, limit),
        )
        return {r["listing_id"] for r in rows if r["listing_id"]}

    # ------------------------------------------------------------------
    # Deals
    # ------------------------------------------------------------------

    async def record_deal(
        self, *, listing_id: str, market_hash_name: str, price_cents: int,
        reference_price_cents: int, discount_pct: float, float_value: float | None,
        listing_url: str, reason: str | None = None,
    ) -> bool:
        """Insert a deal; returns False when the listing was already recorded."""
        cur = await self.db.execute(
            """INSERT OR IGNORE INTO deals
               (listing_id,market_hash_name,ts,price_cents,reference_price_cents,
                discount_pct,float_value,listing_url,reason)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (listing_id, market_hash_name, _now(), price_cents, reference_price_cents,
             discount_pct, float_value, listing_url, reason),
        )
        await self.db.commit()
        return cur.rowcount > 0

    async def list_deals(self, limit: int = 100) -> list[dict[str, Any]]:
        return await self._fetchall("SELECT * FROM deals ORDER BY ts DESC LIMIT ?", (limit,))

    async def prune_deals(self, keep: int = 500) -> None:
        await self.db.execute(
            "DELETE FROM deals WHERE id NOT IN (SELECT id FROM deals ORDER BY ts DESC LIMIT ?)",
            (keep,),
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Inventory snapshots
    # ------------------------------------------------------------------

    async def save_inventory_snapshot(
        self, steam_id: str, *, total_value_cents: int, item_count: int,
        priced_count: int, items: list[dict], context_counts: dict, value_by_type: dict,
    ) -> None:
        await self.db.execute(
            """INSERT INTO inventory_snapshots
               (steam_id,ts,total_value_cents,item_count,priced_count,
                items_json,context_counts_json,value_by_type_json)
               VALUES(?,?,?,?,?,?,?,?)""",
            (steam_id, _now(), total_value_cents, item_count, priced_count,
             json.dumps(items), json.dumps(context_counts), json.dumps(value_by_type)),
        )
        # Keep history bounded: raw item rows are big, and daily use adds up.
        await self.db.execute(
            """DELETE FROM inventory_snapshots
               WHERE steam_id=? AND id NOT IN (
                 SELECT id FROM inventory_snapshots WHERE steam_id=?
                 ORDER BY ts DESC LIMIT 100)""",
            (steam_id, steam_id),
        )
        await self.db.commit()

    async def get_latest_inventory_snapshot(self, steam_id: str) -> dict[str, Any] | None:
        row = await self._fetchone(
            "SELECT * FROM inventory_snapshots WHERE steam_id=? ORDER BY ts DESC LIMIT 1",
            (steam_id,),
        )
        if not row:
            return None
        row["items"] = json.loads(row.pop("items_json"))
        row["context_counts"] = json.loads(row.pop("context_counts_json"))
        row["value_by_type"] = json.loads(row.pop("value_by_type_json"))
        return row

    async def list_inventory_snapshots(
        self, steam_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Summaries only (no item rows) for the history view, oldest first."""
        rows = await self._fetchall(
            """SELECT id,steam_id,ts,total_value_cents,item_count,priced_count
               FROM inventory_snapshots WHERE steam_id=? ORDER BY ts DESC LIMIT ?""",
            (steam_id, limit),
        )
        return list(reversed(rows))

    # ------------------------------------------------------------------
    # Portfolio
    # ------------------------------------------------------------------

    async def add_portfolio_entry(
        self, market_hash_name: str, buy_price_cents: int, *, quantity: int = 1,
        acquired_at: str | None = None, note: str | None = None,
    ) -> dict[str, Any]:
        cur = await self.db.execute(
            "INSERT INTO portfolio(market_hash_name,buy_price_cents,quantity,acquired_at,note,created_at)"
            " VALUES(?,?,?,?,?,?)",
            (market_hash_name, buy_price_cents, quantity, acquired_at, note, _now()),
        )
        await self.db.commit()
        return {"id": cur.lastrowid}

    async def list_portfolio(self) -> list[dict[str, Any]]:
        return await self._fetchall("SELECT * FROM portfolio ORDER BY created_at DESC")

    async def delete_portfolio_entry(self, entry_id: int) -> None:
        await self.db.execute("DELETE FROM portfolio WHERE id=?", (entry_id,))
        await self.db.commit()
