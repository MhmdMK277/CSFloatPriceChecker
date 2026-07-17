"""Terminal interface for power users - same core as the web app.

Examples::

    csfloat-tracker serve                       # start the web app
    csfloat-tracker key set                     # store your API key
    csfloat-tracker search "ak redline"         # autocomplete lookup
    csfloat-tracker price "AK-47 | Redline (Field-Tested)" --max-float 0.2
    csfloat-tracker refresh-db                  # rebuild the item catalog
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .core import secrets
from .core.client import CSFloatClient
from .core.errors import CSFloatError
from .core.itemdb import ItemDatabase

app = typer.Typer(
    name="csfloat-tracker",
    help="CS2 market intelligence for CSFloat - web app, tracker and CLI.",
    no_args_is_help=True,
    add_completion=False,
)
key_app = typer.Typer(help="Manage the CSFloat API key.", no_args_is_help=True)
app.add_typer(key_app, name="key")

console = Console()


def _load_itemdb() -> ItemDatabase:
    db = ItemDatabase()
    if not db.load():
        console.print("[red]No item database found.[/] Run [bold]csfloat-tracker refresh-db[/] first.")
        raise typer.Exit(1)
    return db


def _run(coro):
    try:
        return asyncio.run(coro)
    except CSFloatError as exc:
        console.print(f"[red]Error:[/] {exc.message}")
        raise typer.Exit(1) from exc


@app.command()
def version() -> None:
    """Print the version."""
    console.print(f"csfloat-tracker {__version__}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address (0.0.0.0 for LAN/Docker)."),
    port: int = typer.Option(8422, help="Port for the web app."),
) -> None:
    """Start the web app (UI + REST API + background worker)."""
    import uvicorn

    from .server.app import create_app

    console.print(f"[bold]CSFloat Tracker[/] v{__version__} → http://{host}:{port}")
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


@app.command()
def search(
    query: str = typer.Argument(..., help="Item name fragment, typos welcome."),
    limit: int = typer.Option(10, help="Max results."),
) -> None:
    """Search the item catalog (offline, instant)."""
    db = _load_itemdb()
    results = db.search(query, limit=limit)
    if not results:
        console.print("No matches.")
        raise typer.Exit()
    table = Table(box=None, header_style="bold cyan")
    table.add_column("Item")
    table.add_column("Type")
    table.add_column("Ref. price", justify="right")
    for v in results:
        ref = f"${v.reference_price_cents / 100:,.2f}" if v.reference_price_cents else "-"
        table.add_row(v.market_hash_name, v.item_type, ref)
    console.print(table)


@app.command()
def price(
    name: str = typer.Argument(..., help="Exact market_hash_name (use `search` to find it)."),
    min_float: float | None = typer.Option(None, help="Minimum float."),
    max_float: float | None = typer.Option(None, help="Maximum float."),
    limit: int = typer.Option(10, help="Listings to show."),
    auctions: bool = typer.Option(False, "--auctions", help="Include auctions."),
) -> None:
    """Live lowest-price listings for an item (requires API key)."""
    api_key = secrets.get_api_key()
    if not api_key:
        console.print("[red]No API key.[/] Run [bold]csfloat-tracker key set[/] first.")
        raise typer.Exit(1)

    async def go():
        async with CSFloatClient(api_key=api_key) as client:
            return await client.get_listings(
                market_hash_name=name,
                sort_by="lowest_price",
                limit=limit,
                min_float=min_float,
                max_float=max_float,
                type=None if auctions else "buy_now",
            )

    page = _run(go())
    if not page.listings:
        console.print("No active listings matched.")
        raise typer.Exit()

    table = Table(title=name, header_style="bold cyan")
    table.add_column("Price", justify="right", style="bold")
    table.add_column("Float", justify="right")
    table.add_column("Type")
    table.add_column("Seller")
    table.add_column("Link", overflow="fold")
    for listing in page.listings:
        table.add_row(
            f"${listing.price_usd:,.2f}",
            f"{listing.float_value:.6f}" if listing.float_value is not None else "-",
            listing.type,
            listing.seller.username if listing.seller and listing.seller.username else "-",
            listing.url,
        )
    console.print(table)


@app.command("refresh-db")
def refresh_db() -> None:
    """Rebuild the item catalog from CSFloat's public schema."""
    db = ItemDatabase()
    db.load()

    async def go():
        async with CSFloatClient(api_key=secrets.get_api_key()) as client:
            return await db.refresh(client)

    with console.status("Fetching schema from CSFloat…"):
        stats = _run(go())
    console.print(
        f"[green]Done.[/] {stats['market_names']:,} market names "
        f"from {stats['base_items']:,} base items."
    )


@app.command()
def status() -> None:
    """Show catalog and key status."""
    db = ItemDatabase()
    loaded = db.load()
    key = secrets.get_api_key()
    console.print(f"API key: {'[green]set[/] (' + secrets.storage_backend() + ')' if key else '[red]not set[/]'}")
    if loaded:
        stats = db.stats()
        staleness = "[yellow]stale[/]" if stats["stale"] else "[green]fresh[/]"
        console.print(
            f"Item DB: {stats['market_names']:,} names · generated {stats['generated_at']} · {staleness}"
        )
    else:
        console.print("Item DB: [red]missing[/] - run refresh-db")


@key_app.command("set")
def key_set() -> None:
    """Validate and store your CSFloat API key (prompted, hidden input)."""
    value = typer.prompt("CSFloat API key (Profile → Developer)", hide_input=True).strip()
    if len(value) < 8:
        console.print("[red]That doesn't look like a key.[/]")
        raise typer.Exit(1)

    async def go():
        async with CSFloatClient(api_key=value) as client:
            return await client.validate_key()

    profile = _run(go())
    backend = secrets.set_api_key(value)
    who = profile.get("username") if profile else None
    console.print(f"[green]Key validated[/]{f' as {who}' if who else ''} and stored in the {backend}.")


@key_app.command("delete")
def key_delete() -> None:
    """Remove the stored API key."""
    secrets.delete_api_key()
    console.print("Key removed.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
