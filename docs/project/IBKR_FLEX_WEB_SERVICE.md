# IBKR Flex Web Service Import

`pp-master fetch-ibkr-flex` downloads a Flex Query statement from the IBKR
Flex Web Service, archives it under `data/raw/ibkr/YYYYMMDD/`, and imports it
with the same parsers `import-broker` uses. It replaces the manual "run the
query in Account Management, download the XML, run `import-broker`" loop.

## One-time IBKR setup

1. In IBKR Portal, open **Performance & Reports > Flex Queries** and create an
   **Activity Flex Query** with format **XML**. Include the sections the
   importer reads:
   - Trades
   - Cash Transactions
   - Corporate Actions
   - Transfers
   - Open Positions (refreshes the holdings snapshot on every fetch)
2. Set date format `yyyyMMdd` and a period (for a nightly job, "Last Business
   Day" or "Last 7 Days"; overlap is safe because imports skip stored rows).
3. Note the numeric **Query ID**.
4. Under **Flex Queries > Flex Web Service Configuration**, enable the service
   and generate a **token**. Pick the longest lifetime you are comfortable
   rotating, and restrict it to your server's IP if it is static.

For an advisor or master account, one query can cover every linked client
account; each statement row carries its `accountId`.

## Configuration

Add to `.env` (never commit it):

```bash
IBKR_FLEX_TOKEN=<token>
IBKR_FLEX_QUERY_ID=<query id>
# Optional
IBKR_FLEX_RAW_DIR=data/raw/ibkr
IBKR_FLEX_POLL_INTERVAL_SECONDS=5
IBKR_FLEX_MAX_POLLS=20
```

## Usage

```bash
# Fetch with the query's saved period, archive, and import
uv run pp-master fetch-ibkr-flex

# Back-fill a range (at most 365 days per request)
uv run pp-master fetch-ibkr-flex --from-date 2026-01-01 --to-date 2026-06-30

# Download and archive only
uv run pp-master fetch-ibkr-flex --no-import --query-id 123456
```

Nightly cron example (after IBKR finishes end-of-day processing):

```cron
30 6 * * 2-6 cd /opt/pp-security-master && uv run pp-master fetch-ibkr-flex
```

## Errors

| IBKR code | Meaning | Behavior |
| --- | --- | --- |
| 1019, 1018, 1009, 1001, 1004-1008, 1021 | Generating, throttled, or busy | Polled automatically |
| 1012 | Token expired | Fails; generate a new token |
| 1013 | IP restriction | Fails; check the token's IP allowlist |
| 1014 | Invalid query | Fails; check `IBKR_FLEX_QUERY_ID` |
| 1015 | Invalid token | Fails; check `IBKR_FLEX_TOKEN` |

## Security notes

- The token is held as a `SecretStr`, sent only over https, and never included
  in error messages.
- The GetStatement URL returned by IBKR is accepted only on an
  `interactivebrokers.com` host before the token is sent to it.
- Archived statements are written owner-only (`0600`) under the gitignored
  `data/` directory; the settings validator rejects a raw directory outside it.
