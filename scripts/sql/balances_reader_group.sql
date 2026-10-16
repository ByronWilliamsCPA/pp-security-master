-- Read-only group role for the account balances table.
--
-- Run ONCE per database, as a superuser (or a role with CREATEROLE and
-- ownership of the table), connected to the Security Master database:
--
--   psql "<admin connection string>" -v ON_ERROR_STOP=1 \
--        -f scripts/sql/balances_reader_group.sql
--
-- This is a script and not an Alembic migration on purpose: creating roles
-- needs elevated rights that the application's own database user should not
-- have, and roles are cluster-wide, not part of one database's schema history.
--
-- What it does:
--   * creates the NOLOGIN group role balances_reader (nobody can sign in as it);
--   * grants it SELECT on public.account_balances and nothing else;
--   * grants it USAGE on schema public, which SELECT needs to resolve the name.
--
-- It does NOT grant on any other table, view, sequence, or schema, and it sets
-- no default privileges, so tables added by later migrations stay invisible to
-- the reader. Safe to re-run: the REVOKE resets the table privileges first.
--
-- Login roles are created separately (balances_reader_login.sql) so each remote
-- reader gets its own name and password, both kept outside the repository.
-- Connecting needs CONNECT on the database; PostgreSQL grants that to PUBLIC by
-- default. If your cluster revoked it, grant CONNECT to balances_reader by hand.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'balances_reader') THEN
        CREATE ROLE balances_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

REVOKE ALL ON TABLE public.account_balances FROM balances_reader;

GRANT USAGE ON SCHEMA public TO balances_reader;
GRANT SELECT ON TABLE public.account_balances TO balances_reader;
