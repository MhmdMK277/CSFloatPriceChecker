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


def get_secret(account: str) -> str | None:
    kr = _keyring()
    if kr:
        try:
            key = kr.get_password(SERVICE, account)
            if key:
                return key
        except Exception as exc:
            logger.warning("Keyring read failed: %s", exc)
    path = _fallback_path()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh).get(account)
        except (ValueError, OSError) as exc:
            logger.warning("Secret file read failed: %s", exc)
    return None


def set_secret(account: str, value: str) -> str:
    """Store a named secret; returns the backend used ('keychain' or 'file')."""
    kr = _keyring()
    if kr:
        try:
            kr.set_password(SERVICE, account, value)
            _remove_from_fallback(account)
            return "keychain"
        except Exception as exc:
            logger.warning("Keyring write failed, using file fallback: %s", exc)
    path = _fallback_path()
    data: dict = {}
    if path.exists():
        with contextlib.suppress(ValueError, OSError):
            data = json.loads(path.read_text(encoding="utf-8"))
    data[account] = value
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    if os.name == "posix":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return "file"


def delete_secret(account: str) -> None:
    kr = _keyring()
    if kr:
        with contextlib.suppress(Exception):
            kr.delete_password(SERVICE, account)
    _remove_from_fallback(account)


def _remove_from_fallback(account: str) -> None:
    path = _fallback_path()
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop(account, None)
        if data:
            path.write_text(json.dumps(data), encoding="utf-8")
        else:
            path.unlink()
    except (ValueError, OSError) as exc:
        logger.warning("Secret file update failed: %s", exc)


# CSFloat API key — the original, most-used secret keeps its short helpers.

def get_api_key() -> str | None:
    return get_secret(ACCOUNT)


def set_api_key(key: str) -> str:
    return set_secret(ACCOUNT, key)


def delete_api_key() -> None:
    delete_secret(ACCOUNT)


def storage_backend() -> str:
    """Where a key would be (or is) stored: 'keychain' or 'file'."""
    return "keychain" if _keyring() else "file"
