"""FastAPI application factory.

``create_app()`` wires storage, the item database, the CSFloat client and
the background worker together, mounts the REST API under ``/api`` and
serves the built frontend (when present) at ``/``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..core.errors import CSFloatError
from .deps import AppContext
from .routes import api_router
from .worker import Worker

logger = logging.getLogger(__name__)


def _frontend_dist() -> Path | None:
    import os

    from ..core.paths import bundle_dir

    frozen = bundle_dir()
    candidates = [
        Path(os.environ["CSFLOAT_TRACKER_STATIC"]) if os.environ.get("CSFLOAT_TRACKER_STATIC") else None,
        (frozen / "static") if frozen else None,  # PyInstaller bundle
        Path(__file__).resolve().parent.parent / "static",  # packaged wheel
        Path(__file__).resolve().parents[3] / "frontend" / "dist",  # repo checkout
    ]
    for c in candidates:
        if c and (c / "index.html").exists():
            return c
    return None


def create_app(*, ctx: AppContext | None = None, start_worker: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.ctx = ctx or await AppContext.create()
        worker = Worker(app.state.ctx)
        worker_task: asyncio.Task | None = None
        refresh_task: asyncio.Task | None = None
        if start_worker:
            worker_task = asyncio.create_task(worker.run())
            # Refresh the item DB in the background if it's stale; never
            # block startup on the network.
            refresh_task = asyncio.create_task(
                app.state.ctx.itemdb.ensure_fresh(app.state.ctx.client)
            )
        app.state.worker = worker
        try:
            yield
        finally:
            worker.stop()
            for task in (worker_task, refresh_task):
                if task:
                    task.cancel()
                    with contextlib.suppress(Exception):
                        await task
            await app.state.ctx.close()

    app = FastAPI(
        title="CSFloat Tracker",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    @app.exception_handler(CSFloatError)
    async def csfloat_error_handler(_, exc: CSFloatError):
        payload = {"error": exc.message}
        if hasattr(exc, "retry_after"):
            payload["retry_after"] = exc.retry_after
        return JSONResponse(status_code=exc.status or 500, content=payload)

    app.include_router(api_router, prefix="/api")

    @app.websocket("/api/ws")
    async def websocket_endpoint(ws: WebSocket):
        manager = app.state.ctx.ws
        await manager.connect(ws)
        try:
            while True:
                await ws.receive_text()  # keepalive pings from the client
        except WebSocketDisconnect:
            manager.disconnect(ws)

    dist = _frontend_dist()
    if dist:
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
        index = dist / "index.html"

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            # Client-side routes (e.g. /settings) all resolve to the SPA shell;
            # real files in dist (favicons etc.) are served directly.
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
                return FileResponse(candidate)
            return FileResponse(index)
    else:

        @app.get("/")
        async def index_placeholder():
            return {
                "app": "CSFloat Tracker",
                "version": __version__,
                "note": "Frontend not built. Run `npm run build` in frontend/, or use /api/docs.",
            }

    return app


def main() -> None:
    """Entry point for `python -m csfloat_tracker.server.app`."""
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(), host="127.0.0.1", port=8422)


if __name__ == "__main__":
    main()
