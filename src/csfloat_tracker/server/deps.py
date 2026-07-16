"""Application context shared across routes and background workers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from fastapi import Request

from ..core import secrets
from ..core.client import CSFloatClient
from ..core.itemdb import ItemDatabase
from ..core.storage import Storage
from .ws import WSManager

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    storage: Storage
    itemdb: ItemDatabase
    client: CSFloatClient
    ws: WSManager = field(default_factory=WSManager)

    @classmethod
    async def create(
        cls,
        *,
        storage: Storage | None = None,
        itemdb: ItemDatabase | None = None,
        client: CSFloatClient | None = None,
    ) -> AppContext:
        storage = storage or Storage()
        await storage.open()
        itemdb = itemdb or ItemDatabase()
        itemdb.load()
        client = client or CSFloatClient(api_key=secrets.get_api_key())
        return cls(storage=storage, itemdb=itemdb, client=client)

    async def close(self) -> None:
        await self.client.close()
        await self.storage.close()

    def set_api_key(self, key: str | None) -> None:
        self.client.api_key = key


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx
