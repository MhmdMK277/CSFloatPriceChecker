"""Desktop launcher: local server + auto-opened browser + tray icon.

This is the entry point for the packaged executable. It starts uvicorn on
127.0.0.1, opens the user's default browser once the server is up, and then
parks either in a system-tray icon (Open / Quit) or, when a tray isn't
available, in a plain console loop. The browser is the UI; this process is
just the engine.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
import webbrowser
from logging.handlers import RotatingFileHandler

from .core.paths import data_dir

HOST = "127.0.0.1"
PORT = 8422
URL = f"http://{HOST}:{PORT}"

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    """Log to a rotating file in the data dir; echo to console when visible."""
    log_dir = data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(log_dir / "desktop.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    ]
    if sys.stderr is not None:  # windowed exes have no console streams
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def _running_instance_version() -> str | None:
    """Version of another CSFloat Tracker instance on our port, if any."""
    import json
    import urllib.request

    try:
        with urllib.request.urlopen(f"{URL}/api/status", timeout=1.5) as resp:
            return json.loads(resp.read()).get("version")
    except Exception:
        return None


def _alert_stale_instance(running_version: str, our_version: str) -> None:
    """Warn that an older instance is holding the port.

    Without this, double-clicking a freshly downloaded build while the old
    tray icon is still alive silently opens the OLD app - the user thinks
    they're on the new version and files bugs against it.
    """
    message = (
        f"CSFloat Tracker v{running_version} is already running, but you launched "
        f"v{our_version}.\n\nQuit the old version first (right-click the amber tray "
        "icon -> Quit), then start this one again."
    )
    logger.warning("Stale instance: running=%s launched=%s", running_version, our_version)
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "CSFloat Tracker", 0x30)  # MB_ICONWARNING
    elif sys.stderr is not None:
        print(message, file=sys.stderr)


def _make_server():
    import uvicorn

    from .server.app import create_app

    config = uvicorn.Config(
        create_app(),
        host=HOST,
        port=PORT,
        log_level="info",
        # The frozen app has no console to answer Ctrl+C prompts.
        use_colors=False,
    )
    return uvicorn.Server(config)


def _tray_icon_image():
    """Amber trend-line on navy - drawn at runtime so we need no asset file."""
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, size - 2, size - 2], radius=14, fill=(24, 28, 42, 255))
    d.line([(14, 44), (28, 32), (38, 38), (52, 20)], fill=(232, 168, 76, 255), width=5, joint="curve")
    d.ellipse([48, 16, 56, 24], fill=(232, 168, 76, 255))
    return img


def _run_tray(server, server_thread: threading.Thread) -> bool:
    """Park in a system tray icon. Returns False if a tray isn't available."""
    try:
        import pystray
    except Exception as exc:  # no pystray / no display / no backend
        logger.info("Tray unavailable (%s); falling back to console mode", exc)
        return False

    def open_browser(icon=None, item=None):
        webbrowser.open(URL)

    def quit_app(icon, item=None):
        logger.info("Quit requested from tray")
        server.should_exit = True
        server_thread.join(timeout=10)
        icon.stop()

    icon = pystray.Icon(
        "csfloat-tracker",
        icon=_tray_icon_image(),
        title=f"CSFloat Tracker - running on {URL}",
        menu=pystray.Menu(
            pystray.MenuItem("Open CSFloat Tracker", open_browser, default=True),
            pystray.MenuItem("Quit", quit_app),
        ),
    )
    try:
        icon.run()  # blocks until quit
        return True
    except Exception as exc:
        logger.info("Tray failed to start (%s); falling back to console mode", exc)
        return False


def _run_console(server, server_thread: threading.Thread) -> None:
    print(f"CSFloat Tracker is running on {URL}")
    print("Press Ctrl+C to quit.")
    try:
        while server_thread.is_alive():
            server_thread.join(timeout=0.5)
    except KeyboardInterrupt:
        print("Shutting down…")
    finally:
        server.should_exit = True
        server_thread.join(timeout=10)


def main() -> None:
    from . import __version__

    _setup_logging()

    running = _running_instance_version()
    if running is not None:
        if running != __version__:
            _alert_stale_instance(running, __version__)
        else:
            logger.info("Instance already running; opening the browser instead.")
            webbrowser.open(URL)
        return

    server = _make_server()
    server_thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    server_thread.start()

    # Wait for uvicorn to bind before pointing a browser at it.
    deadline = time.monotonic() + 30
    while not server.started and server_thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.1)

    if not server.started:
        logger.error("Server failed to start; see logs in %s", data_dir() / "logs")
        if sys.stderr is not None:
            print("CSFloat Tracker failed to start. Check the log file in", data_dir() / "logs")
        raise SystemExit(1)

    logger.info("Server up on %s - opening browser", URL)
    webbrowser.open(URL)

    if not _run_tray(server, server_thread):
        _run_console(server, server_thread)

    logger.info("Desktop launcher exited cleanly")


if __name__ == "__main__":
    main()
