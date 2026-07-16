"""Exception hierarchy for CSFloat Tracker.

Every error carries a short, user-presentable ``message`` so API routes and
the CLI can surface failures without leaking stack traces.
"""

from __future__ import annotations


class CSFloatError(Exception):
    """Base class for all tracker errors."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class AuthError(CSFloatError):
    """The CSFloat API rejected our credentials (401/403)."""

    def __init__(self, message: str = "CSFloat rejected the API key. Check it in Settings.") -> None:
        super().__init__(message, status=401)


class NotFoundError(CSFloatError):
    """The requested resource does not exist (404)."""

    def __init__(self, message: str = "Resource not found on CSFloat.") -> None:
        super().__init__(message, status=404)


class RateLimitError(CSFloatError):
    """We exhausted the rate limit and could not wait it out."""

    def __init__(self, retry_after: float, message: str | None = None) -> None:
        msg = message or f"CSFloat rate limit reached. Try again in {int(retry_after)}s."
        super().__init__(msg, status=429)
        self.retry_after = retry_after


class UpstreamError(CSFloatError):
    """CSFloat returned a server error or malformed payload."""

    def __init__(self, message: str = "CSFloat returned an unexpected response.", *, status: int | None = 502) -> None:
        super().__init__(message, status=status)


class NetworkError(CSFloatError):
    """We could not reach CSFloat at all."""

    def __init__(self, message: str = "Could not reach CSFloat. Check your connection.") -> None:
        super().__init__(message, status=503)
