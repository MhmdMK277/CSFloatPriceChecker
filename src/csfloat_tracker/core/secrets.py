"""API key storage in the OS keychain, with a guarded file fallback.

The key never leaves the machine. Preferred backend is the platform
keychain via ``keyring`` (Windows Credential Manager, macOS Keychain,
Secret Service on Linux). When no keychain is available (e.g. headless
Docker), we fall back to a file in the app data directory with owner-only
permissions and report the storage method so the UI can say so.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import stat

from .paths import data_dir

logger = logging.getLogger(__name__)

SERVICE = "csfloat-tracker"
ACCOUNT = "csfloat-api-key"
FALLBACK_FILE = "secrets.json"


def _keyring():
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring

        if isinstance(keyring.get_keyring(), FailKeyring):
            return None
        return keyring
    except Exception:
        return None


def _fallback_path():
    return data_dir() / FALLBACK_FILE


def get_api_key() -> str | None:
    kr = _keyring()
    if kr:
        try:
            key = kr.get_password(SERVICE, ACCOUNT)
            if key:
                return key
        except Exception as exc:
            logger.warning("Keyring read failed: %s", exc)
    path = _fallback_path()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh).get(ACCOUNT)
        except (ValueError, OSError) as exc:
            logger.warning("Secret file read failed: %s", exc)
    return None


def set_api_key(key: str) -> str:
    """Store the key; returns the backend used ('keychain' or 'file')."""
    kr = _keyring()
    if kr:
        try:
            kr.set_password(SERVICE, ACCOUNT, key)
            # Remove any stale fallback copy so there is a single source of truth.
            _fallback_path().unlink(missing_ok=True)
            return "keychain"
        except Exception as exc:
            logger.warning("Keyring write failed, using file fallback: %s", exc)
    path = _fallback_path()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({ACCOUNT: key}, fh)
    if os.name == "posix":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return "file"


def delete_api_key() -> None:
    kr = _keyring()
    if kr:
        with contextlib.suppress(Exception):
            kr.delete_password(SERVICE, ACCOUNT)
    _fallback_path().unlink(missing_ok=True)


def storage_backend() -> str:
    """Where a key would be (or is) stored: 'keychain' or 'file'."""
    return "keychain" if _keyring() else "file"
