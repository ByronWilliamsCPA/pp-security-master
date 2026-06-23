"""On-disk SQLite response cache for external-API calls.

#CRITICAL (licensing, ADR-015): this cache stores RAW provider JSON keyed by
identifier at runtime, in a gitignored data dir (``data/`` and ``*.sqlite3`` are
both ignored). It is never committed, and being a SQLite file it is invisible to
``scripts/check_no_licensed_assignments.py`` (which parses only YAML/JSON).
#VERIFY the cache_path stays under a gitignored directory: enforced by
``ExternalAPISettings._cache_path_must_be_gitignored`` (settings.py), which
rejects any path not covered by a ``.sqlite3`` suffix or a ``data/`` segment.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_LOGGER = logging.getLogger(__name__)
_SECONDS_PER_DAY = 86_400


class ResponseCache:
    """A keyed, TTL-bounded cache of raw provider responses on disk."""

    def __init__(self, path: Path, *, ttl_days: int) -> None:
        """Open (creating if needed) the SQLite cache at ``path``.

        Args:
            path: SQLite file path. Parent directories are created.
            ttl_days: Entry lifetime in days (must be positive).

        Raises:
            ValueError: If ``ttl_days`` is not positive (a non-positive TTL would
                expire every entry immediately, silently disabling the cache).
        """
        if ttl_days <= 0:
            msg = f"ttl_days must be positive, got {ttl_days}"
            raise ValueError(msg)
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
        try:
            row = self._conn.execute(
                "SELECT body, fetched_at FROM response_cache "
                "WHERE provider = ? AND request_key = ?",
                (provider, request_key),
            ).fetchone()
        except sqlite3.Error as exc:
            # The cache is an optimization, not a source of truth: a read failure
            # (locked db, disk I/O error, corruption) degrades to a miss so the
            # caller re-fetches rather than crashing the batch.
            _LOGGER.warning(
                "cache read failed for %s/%s: %s", provider, request_key, exc
            )
            return None
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
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO response_cache "
                "(provider, request_key, body, fetched_at) VALUES (?, ?, ?, ?)",
                (provider, request_key, body, clock),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            # A write failure (disk full, locked db) degrades to a no-op store:
            # the value simply will not be cached, which is preferable to
            # aborting classification.
            _LOGGER.warning(
                "cache write failed for %s/%s: %s", provider, request_key, exc
            )

    def invalidate(self, provider: str, request_key: str) -> None:
        """Delete a cached entry, e.g. a poisoned non-JSON body.

        Args:
            provider: Provider label.
            request_key: Provider-scoped request key.
        """
        try:
            self._conn.execute(
                "DELETE FROM response_cache WHERE provider = ? AND request_key = ?",
                (provider, request_key),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            _LOGGER.warning(
                "cache invalidate failed for %s/%s: %s", provider, request_key, exc
            )

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()
