"""Typed errors for the external-API framework."""

from __future__ import annotations


class ExternalAPIError(RuntimeError):
    """A provider call failed after retries; callers degrade rather than crash.

    Attributes:
        provider: Short provider label (e.g. ``"openfigi"``, ``"sec_edgar"``).
    """

    provider: str

    def __init__(self, *, provider: str, message: str) -> None:
        """Build the error.

        Args:
            provider: Short provider label.
            message: Human-readable failure detail.
        """
        self.provider = provider
        super().__init__(f"{provider}: {message}")
