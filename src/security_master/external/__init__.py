"""External-API integration framework (ADR-005, minimal).

Synchronous OpenFIGI + SEC EDGAR clients behind an on-disk response cache with
retry/backoff, rate limiting, and graceful degradation. All network I/O is
isolated here so the classifier consumes validated value objects only.
"""
