# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the CSFloat Tracker desktop app.

Build via scripts/build_desktop.py (it builds the frontend and generates the
icon/version resources first), or directly:

    pyinstaller csfloat-tracker.spec --noconfirm
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH)

if not (ROOT / "frontend" / "dist" / "index.html").exists():
    raise SystemExit("frontend/dist is missing - run `npm run build` in frontend/ first.")

datas = [
    (str(ROOT / "data" / "cs2_items.json"), "data"),
    (str(ROOT / "data" / "graffiti.json"), "data"),
    (str(ROOT / "frontend" / "dist"), "static"),
]

hiddenimports = [
    # uvicorn loads its loop/protocol/lifespan classes from strings
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    # keyring discovers platform backends dynamically
    "keyring.backends.Windows",
    "keyring.backends.macOS",
    "keyring.backends.SecretService",
    "keyring.backends.chainer",
    "keyring.backends.fail",
    "aiosqlite",
]
if sys.platform == "win32":
    hiddenimports += ["pystray._win32", "win32ctypes.core"]
elif sys.platform == "darwin":
    hiddenimports += ["pystray._darwin"]

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "respx", "ruff"],
    noarchive=False,
)

pyz = PYZ(a.pure)

_icon = ROOT / "build" / "icon.ico"
_version_file = ROOT / "build" / "version_info.txt"

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="CSFloatTracker",
    debug=False,
    strip=False,
    upx=False,
    # Windows: windowed app parked in the system tray (logs go to the data
    # dir). Linux/macOS: console binary - tray backends vary too much there.
    console=(sys.platform != "win32"),
    icon=str(_icon) if sys.platform == "win32" and _icon.exists() else None,
    version=str(_version_file) if sys.platform == "win32" and _version_file.exists() else None,
)
