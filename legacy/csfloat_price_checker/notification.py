"""Desktop notification helper for CSFloat price checker."""

try:
    from plyer import notification
except Exception:  # pragma: no cover - plyer might not be available
    notification = None


def show_desktop_notification(skin_name: str, listing: dict) -> None:
    """Show a desktop notification for a matching skin listing.

    Parameters
    ----------
    skin_name: str
        The name of the skin being alerted.
    listing: dict
        A dictionary containing at least ``price`` and ``float`` keys.
    """
    if notification is None:
        return

    price = listing.get("price")
    flt = listing.get("float")
    try:
        price_text = f"${float(price):.2f}" if price is not None else "Unknown price"
    except Exception:
        price_text = str(price)
    try:
        float_text = f"{float(flt):.4f}" if flt is not None else "Unknown float"
    except Exception:
        float_text = str(flt)

    notification.notify(
        title="Skin Alert!",
        message=f"{skin_name} found for {price_text} with float {float_text}",
        timeout=10,
    )
