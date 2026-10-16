# Deployment examples

These files are examples. Nothing in the build, the tests, or CI installs or
runs them. Copy one out, replace every placeholder, and review it before use.
They contain no hostnames, addresses, credentials, or real paths.

## systemd: nightly import and totals

`systemd/pp-master-nightly.service` and `systemd/pp-master-nightly.timer` run
the nightly job in a fixed order, so the totals always see the day's data:

1. `pp-master import-broker` (activity Flex export: trades and CashReport)
2. `pp-master reconcile-positions` (OpenPosition Flex export)
3. `pp-master nightly-totals`

`nightly-totals` joins positions and cash on one exact report date, so both
imports come first. The timer starts the run at 00:30 America/Los_Angeles and
the service caps it at 45 minutes, so it ends before 02:00 Pacific.

The unit takes its database settings from an environment file kept outside the
repository (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`,
`PP_ACCOUNT_REGISTRY_PATH`, plus the two Flex file paths), so it assumes no
particular host name. Run it on the machine that holds the database or on any
machine that can reach it.

### Hosts without systemd (for example Unraid)

Unraid's base system does not use systemd, so the unit files cannot be
installed there as they are. Run the same three commands in the same order from
whatever scheduler the host has (the User Scripts plugin, cron, or a container
scheduler), and stop at the first failure, for example in a shell script with
`set -e`. Keep the 00:30 America/Los_Angeles start and the 45 minute cap.
