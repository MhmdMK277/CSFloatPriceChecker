"""Build the desktop executable.

Usage::

    python scripts/build_desktop.py [--skip-frontend]

Steps: build the React frontend, generate the Windows icon + version
resources, run PyInstaller with csfloat-tracker.spec, then rename the output
to a platform-suffixed artifact and print its size and SHA256.
"""

from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from csfloat_tracker import __version__  # noqa: E402


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"→ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd or ROOT, check=True)


def build_frontend() -> None:
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm not found — install Node.js ≥ 20 to build the frontend.")
    frontend = ROOT / "frontend"
    if not (frontend / "node_modules").exists():
        run([npm, "ci"], cwd=frontend)
    run([npm, "run", "build"], cwd=frontend)


def make_icon(out: Path) -> None:
    """Amber trend-line on navy, multi-size .ico — same mark as the tray icon."""
    from PIL import Image, ImageDraw

    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, size - 8, size - 8], radius=56, fill=(24, 28, 42, 255))
    d.line(
        [(56, 176), (112, 128), (152, 152), (208, 80)],
        fill=(232, 168, 76, 255), width=20, joint="curve",
    )
    d.ellipse([192, 64, 224, 96], fill=(232, 168, 76, 255))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"→ icon written to {out}")


def make_version_info(out: Path) -> None:
    parts = [*__version__.split("."), "0", "0", "0"][:3]
    csv = ", ".join(parts) + ", 0"
    out.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({csv}), prodvers=({csv})),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('ProductName', 'CSFloat Tracker'),
      StringStruct('FileDescription', 'CSFloat Tracker — CS2 market intelligence'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('ProductVersion', '{__version__}'),
      StringStruct('LegalCopyright', 'MIT License — github.com/MhmdMK277/CSFloatPriceChecker'),
      StringStruct('OriginalFilename', 'CSFloatTracker.exe')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
    )
    print(f"→ version info written to {out}")


def main() -> None:
    skip_frontend = "--skip-frontend" in sys.argv

    if not skip_frontend:
        build_frontend()
    elif not (ROOT / "frontend" / "dist" / "index.html").exists():
        raise SystemExit("--skip-frontend given but frontend/dist is missing.")

    if sys.platform == "win32":
        make_icon(ROOT / "build" / "icon.ico")
        make_version_info(ROOT / "build" / "version_info.txt")

    run([sys.executable, "-m", "PyInstaller", "csfloat-tracker.spec", "--noconfirm"])

    system = platform.system()
    suffix = {"Windows": "Windows.exe", "Linux": "Linux", "Darwin": "macOS"}[system]
    built = ROOT / "dist" / ("CSFloatTracker.exe" if system == "Windows" else "CSFloatTracker")
    target = ROOT / "dist" / f"CSFloatTracker-{suffix}"
    if target.exists():
        target.unlink()
    built.rename(target)

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (target.parent / f"{target.name}.sha256").write_text(f"{digest}  {target.name}\n")
    print(f"\n✔ {target}")
    print(f"  size:   {target.stat().st_size / 1e6:.1f} MB")
    print(f"  sha256: {digest}")


if __name__ == "__main__":
    main()
