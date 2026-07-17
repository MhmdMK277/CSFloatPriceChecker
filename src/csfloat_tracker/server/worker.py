"""Background worker: price tracking, alert checking and deal finding.

A single asyncio loop ticks every ``TICK_SECONDS`` and runs whichever jobs
are due. All CSFloat access flows through the shared rate-limited client;
when the limiter reports exhaustion the cycle simply skips and retries on
a later tick, so background work can never lock out interactive use for
long.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

import httpx

from ..core.errors import CSFloatError, RateLimitError
from ..core.skinport import MIN_REFRESH_SECONDS, fetch_skinport_items
from ..core.stats import deal_reason, discount_pct, summarize_listings
from .deps import AppContext

logger = logging.getLogger(__name__)

TICK_SECONDS = 15.0
ALERT_INTERVAL = 60.0


class Worker:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._stop = asyncio.Event()
        self._last_alert_run = 0.0
        self._last_deal_run = 0.0
        self._last_skinport_run = 0.0

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        logger.info("Background worker started")
        while not self._stop.is_set():
            try:
                await self.tick()
            except Exception:
                logger.exception("Worker tick failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=TICK_SECONDS)
        logger.info("Background worker stopped")

    async def tick(self) -> None:
        now = asyncio.get_event_loop().time()
        # Skinport needs no key and other features degrade gracefully around it.
        if self._last_skinport_run == 0.0 or now - self._last_skinport_run >= MIN_REFRESH_SECONDS:
            self._last_skinport_run = now
            await self._refresh_skinport()
        if not self.ctx.client.api_key:
            return  # everything below talks to CSFloat
        await self._run_due_tracking()
        if now - self._last_alert_run >= ALERT_INTERVAL:
            self._last_alert_run = now
            await self._check_alerts()
        config = await self.ctx.storage.get_setting("deal_finder", {})
        if config.get("enabled") and now - self._last_deal_run >= config.get("interval_seconds", 120):
            self._last_deal_run = now
            await self._scan_deals(config)

    # ------------------------------------------------------------------
    # Skinport price feed
    # ------------------------------------------------------------------

    async def _refresh_skinport(self) -> None:
        try:
            rows = await fetch_skinport_items()
            if rows:
                await self.ctx.storage.replace_skinport_prices(rows)
        except CSFloatError as exc:
            logger.info("Skinport refresh skipped: %s", exc.message)
        except Exception:
            logger.exception("Skinport refresh failed")

    # ------------------------------------------------------------------
    # Price tracking
    # ------------------------------------------------------------------

    async def _run_due_tracking(self) -> None:
        items = await self.ctx.storage.list_tracked_items(active_only=True)
        now = datetime.now(UTC)
        for item in items:
            last = item.get("last_run_at")
            if last:
                elapsed = (now - datetime.fromisoformat(last)).total_seconds()
                if elapsed < item["interval_seconds"]:
                    continue
            try:
                await self._snapshot_item(item)
            except RateLimitError:
                logger.info("Rate limited; deferring remaining tracking to next tick")
                return
            except CSFloatError as exc:
                logger.warning("Tracking %s failed: %s", item["market_hash_name"], exc.message)

    async def _snapshot_item(self, item: dict) -> None:
        filters = {
            k: v for k, v in (item.get("filters") or {}).items()
            if k in ("min_float", "max_float", "category", "type")
        }
        page = await self.ctx.client.get_listings(
            market_hash_name=item["market_hash_name"],
            sort_by="lowest_price",
            limit=50,
            **filters,
        )
        summary = summarize_listings(page.listings)
        await self.ctx.storage.add_snapshot(item["market_hash_name"], **summary)
        await self.ctx.storage.mark_tracked_item_run(item["id"])
        await self.ctx.ws.broadcast("snapshot", {
            "market_hash_name": item["market_hash_name"], **summary,
        })

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    async def _check_alerts(self) -> None:
        alerts = await self.ctx.storage.list_alerts(active_only=True)
        for alert in alerts:
            try:
                await self._check_alert(alert)
            except RateLimitError:
                return
            except CSFloatError as exc:
                logger.warning("Alert %s check failed: %s", alert["id"], exc.message)

    async def _check_alert(self, alert: dict) -> None:
        rule = alert["rule"]
        params: dict = {
            "market_hash_name": alert["market_hash_name"],
            "sort_by": "lowest_price",
            "limit": 20,
        }
        if rule.get("max_price_cents") is not None:
            params["max_price"] = rule["max_price_cents"]
        if rule.get("min_float") is not None:
            params["min_float"] = rule["min_float"]
        if rule.get("max_float") is not None:
            params["max_float"] = rule["max_float"]
        if rule.get("type"):
            params["type"] = rule["type"]
        if rule.get("category"):
            params["category"] = {"normal": 1, "stattrak": 2, "souvenir": 3}[rule["category"]]

        page = await self.ctx.client.get_listings(**params)
        if not page.listings:
            return
        seen = await self.ctx.storage.latest_alert_event_listing_ids(alert["id"])
        for listing in page.listings:
            if listing.id in seen:
                continue
            if not self._matches(rule, listing):
                continue
            message = (
                f"{listing.market_hash_name} listed at ${listing.price_usd:.2f}"
                + (f" (float {listing.float_value:.6f})" if listing.float_value is not None else "")
            )
            await self.ctx.storage.record_alert_event(
                alert["id"],
                listing_id=listing.id,
                price_cents=listing.price_cents,
                float_value=listing.float_value,
                message=message,
            )
            payload = {
                "alert_id": alert["id"],
                "market_hash_name": listing.market_hash_name,
                "price_cents": listing.price_cents,
                "float_value": listing.float_value,
                "url": listing.url,
                "message": message,
            }
            await self.ctx.ws.broadcast("alert", payload)
            await self._notify_discord(f"🔔 **Alert** - {message}\n{listing.url}")

    @staticmethod
    def _matches(rule: dict, listing) -> bool:
        if rule.get("max_price_cents") is not None and listing.price_cents > rule["max_price_cents"]:
            return False
        fv = listing.float_value
        if rule.get("max_float") is not None and (fv is None or fv > rule["max_float"]):
            return False
        return not (
            rule.get("min_float") is not None and (fv is None or fv < rule["min_float"])
        )

    # ------------------------------------------------------------------
    # Deal finder
    # ------------------------------------------------------------------

    async def _scan_deals(self, config: dict) -> None:
        try:
            page = await self.ctx.client.get_listings(
                sort_by="most_recent", limit=50, type="buy_now"
            )
        except CSFloatError as exc:
            logger.warning("Deal scan failed: %s", exc.message)
            return

        threshold = config.get("min_discount_pct", 15.0)
        min_price = config.get("min_price_cents", 500)
        max_price = config.get("max_price_cents")
        found = 0
        for listing in page.listings:
            if listing.price_cents < min_price:
                continue
            if max_price and listing.price_cents > max_price:
                continue
            ref = listing.reference_price_cents
            if not ref:
                variant = self.ctx.itemdb.lookup(listing.market_hash_name)
                ref = variant.reference_price_cents if variant else None
            if not ref:
                continue
            pct = discount_pct(listing.price_cents, ref)
            if pct < threshold:
                continue
            reason = deal_reason(listing, self.ctx.itemdb)
            # Cross-market sanity check: a "deal" that's above Skinport's
            # everyday price isn't one; genuinely beating both markets is
            # worth calling out.
            skinport = await self.ctx.storage.get_skinport_price(listing.market_hash_name)
            if skinport:
                if skinport["min_price_cents"] < listing.price_cents:
                    cross = f"note: cheaper on Skinport at ${skinport['min_price_cents'] / 100:.2f}"
                else:
                    cross = "best price across CSFloat + Skinport"
                reason = f"{reason} · {cross}" if reason else cross
            is_new = await self.ctx.storage.record_deal(
                listing_id=listing.id,
                market_hash_name=listing.market_hash_name,
                price_cents=listing.price_cents,
                reference_price_cents=ref,
                discount_pct=pct,
                float_value=listing.float_value,
                listing_url=listing.url,
                reason=reason,
            )
            if is_new:
                found += 1
                payload = {
                    "market_hash_name": listing.market_hash_name,
                    "price_cents": listing.price_cents,
                    "reference_price_cents": ref,
                    "discount_pct": pct,
                    "reason": reason,
                    "url": listing.url,
                }
                await self.ctx.ws.broadcast("deal", payload)
                extra = f"\n{reason}" if reason else ""
                await self._notify_discord(
                    f"💰 **Deal** - {listing.market_hash_name} at "
                    f"${listing.price_usd:.2f} ({pct:.1f}% below reference){extra}\n{listing.url}"
                )
        if found:
            await self.ctx.storage.prune_deals()
            logger.info("Deal scan recorded %d new deals", found)

    # ------------------------------------------------------------------

    async def _notify_discord(self, content: str) -> None:
        prefs = await self.ctx.storage.get_setting("preferences", {})
        url = prefs.get("discord_webhook_url")
        if not url:
            return
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                await http.post(url, json={"content": content})
        except httpx.HTTPError as exc:
            logger.warning("Discord webhook failed: %s", exc)
