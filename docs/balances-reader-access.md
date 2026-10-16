# Read-only access to account balances

How to give a remote reader (a dashboard, a report job, another service) read
access to the `account_balances` table and nothing else.

Every value below in angle brackets is a placeholder. Do not commit real host
names, addresses, role names, or passwords to this repository.

## What the reader can see

The reader role gets `SELECT` on `public.account_balances` and `USAGE` on the
`public` schema (needed for `SELECT` to resolve the table name). It has no
access to any other table, including the transactions, positions, and entity
tables, and no write privilege of any kind. Tables added by later migrations
stay hidden from it, because the scripts set no default privileges.

The table holds balance values, so treat the reader's credentials as sensitive.

## Create the roles (operator, once)

Roles need a superuser, so this is a script and not a migration. Run both
files as a superuser against the Security Master database.

1. Create the group role. It is `NOLOGIN`, so nobody signs in as it directly:

   ```bash
   psql "<admin connection string>" -v ON_ERROR_STOP=1 \
     -f scripts/sql/balances_reader_group.sql
   ```

2. Create one login role per reader. The login name is passed on the command
   line; the password is typed at a prompt and never stored in a file:

   ```bash
   psql "<admin connection string>" -v ON_ERROR_STOP=1 \
     -v login_role=<reader_login_name> \
     -f scripts/sql/balances_reader_login.sql
   ```

   The login role only joins `balances_reader`, is limited to a few
   connections, and starts every session read-only. Keep its password in the
   reader's own secret store, outside this repository.

To remove a reader, run `DROP ROLE <reader_login_name>;`.

## Require TLS on the server

A reader must never connect in clear text. On the PostgreSQL server:

1. Turn on TLS in `postgresql.conf` with a certificate and key from your own
   certificate authority: `ssl = on`, `ssl_cert_file`, `ssl_key_file`.
2. In `pg_hba.conf`, allow the reader with a `hostssl` line. A `hostssl`
   line matches only TLS connections, so a clear-text attempt from this role
   matches no line and is refused (do not add a plain `host` line for it):

   ```text
   hostssl  <db-name>  <reader_login_name>  <reader-source-network>  scram-sha-256
   ```

   Use `scram-sha-256` (not `md5` or `trust`) and keep the source network as
   narrow as the reader allows. Reload the server after editing.
3. Do not publish the database port to the open internet. Reach it over a
   private network or tunnel, and filter by source at the firewall too.

## Connect from the reader

Use certificate verification, not just encryption. `sslmode=verify-full`
checks that the server certificate chains to a CA you trust and that its name
matches the host you dialed.

```text
postgresql://<reader_login_name>@<db-host>:<db-port>/<db-name>?sslmode=verify-full&sslrootcert=<path-to-ca-certificate>
```

Supply the password outside the connection string, from the reader's secret
store, for example through a `.pgpass` file with mode `0600` or the
`PGPASSWORD` variable set by the reader's runtime:

```bash
psql "postgresql://<reader_login_name>@<db-host>:<db-port>/<db-name>?sslmode=verify-full&sslrootcert=<path-to-ca-certificate>" \
  -c "SELECT account_key, as_of, value, currency FROM account_balances ORDER BY as_of DESC LIMIT 5;"
```

`<db-host>` must match a name in the server certificate. If the connection is
refused with an SSL error, fix the certificate or CA path; do not fall back to
`sslmode=require` or `prefer`.

## Checks after setup

Run these as the reader. The first should return rows; the rest should fail
with `permission denied` or a read-only error:

```sql
SELECT count(*) FROM account_balances;
SELECT count(*) FROM transactions_interactive_brokers;
INSERT INTO account_balances (account_key) VALUES ('pp:example:0001');
```

From the admin connection, `\dp account_balances` lists the table privileges;
`balances_reader` should show `r` (select) only.

## Column contract

The table's columns and constraints are defined in
`src/security_master/storage/balance_models.py` and the migration
`sql/versions/a1c4e7b90d21_account_balances.py`. `value` is `NUMERIC(18,2)` and
`currency` is a separate three-letter code, so read both together and never
parse the value as a floating-point number.
