"""On-disk SQLite response cache for external-API calls.

#CRITICAL (licensing, ADR-015): this cache stores RAW provider JSON keyed by
identifier at runtime, in a gitignored data dir (``data/`` and ``*.sqlite3`` are
both ignored). It is never committed, and being a SQLite file it is invisible to
``scripts/check_no_licensed_assignments.py`` (which parses only YAML/JSON).
#VERIFY the cache_path stays under a gitignored directory.
"""

from __future__ import annotations

import sqlite3
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_SECONDS_PER_DAY = 86_400


class ResponseCache:
    """A keyed, TTL-bounded cache of raw provider responses on disk."""

    def __init__(self, path: Path, *, ttl_days: int) -> None:
        """Open (creating if needed) the SQLite cache at ``path``.

        Args:
            path: SQLite file path. Parent directories are created.
            ttl_days: Entry lifetime in days.
        """
        self._ttl_seconds = ttl_days * _SECONDS_PER_DAY
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS response_cache ("
            "provider TEXT NOT NULL, request_key TEXT NOT NULL, "
            "body TEXT NOT NULL, fetched_at REAL NOT NULL, "
            "PRIMARY KEY (provider, request_key))"
        )
        self._conn.commit()

    def get(
        self, provider: str, request_key: str, *, now: float | None = None
    ) -> str | None:
        """Return a fresh cached body, or ``None`` if absent or expired.

        Args:
            provider: Provider label.
            request_key: Provider-scoped request key.
            now: Override clock (seconds); defaults to ``time.time()``.

        Returns:
            The cached body string, or ``None``.
        """
        clock = time.time() if now is None else now
        row = self._conn.execute(
            "SELECT body, fetched_at FROM response_cache "
            "WHERE provider = ? AND request_key = ?",
            (provider, request_key),
        ).fetchone()
        if row is None:
            return None
        body, fetched_at = row
        if clock - float(fetched_at) > self._ttl_seconds:
            return None
        return str(body)

    def store(
        self, provider: str, request_key: str, body: str, *, now: float | None = None
    ) -> None:
        """Insert or replace a cached body.

        Args:
            provider: Provider label.
            request_key: Provider-scoped request key.
            body: Raw response body to cache.
            now: Override clock (seconds); defaults to ``time.time()``.
        """
        clock = time.time() if now is None else now
        self._conn.execute(
            "INSERT OR REPLACE INTO response_cache "
            "(provider, request_key, body, fetched_at) VALUES (?, ?, ?, ?)",
            (provider, request_key, body, clock),
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()
