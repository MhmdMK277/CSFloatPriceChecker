"""REST API route modules, aggregated under /api."""

from fastapi import APIRouter

from . import alerts, deals, history, inventory, listings, portfolio, search, settings, watchlists

api_router = APIRouter()
api_router.include_router(search.router, tags=["search"])
api_router.include_router(listings.router, tags=["listings"])
api_router.include_router(history.router, tags=["history"])
api_router.include_router(watchlists.router, tags=["watchlists"])
api_router.include_router(alerts.router, tags=["alerts"])
api_router.include_router(inventory.router, tags=["inventory"])
api_router.include_router(portfolio.router, tags=["portfolio"])
api_router.include_router(deals.router, tags=["deals"])
api_router.include_router(settings.router, tags=["settings"])
