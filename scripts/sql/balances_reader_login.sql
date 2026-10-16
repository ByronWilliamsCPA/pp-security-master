-- TEMPLATE: one login role for one remote reader of account_balances.
--
-- Run as a superuser, after balances_reader_group.sql, once per reader, with
-- the login name passed as a psql variable (no name is stored in the repo):
--
--   psql "<admin connection string>" -v ON_ERROR_STOP=1 \
--        -v login_role=<reader_login_name> \
--        -f scripts/sql/balances_reader_login.sql
--
-- The password is never written in this file or on a command line. The
-- \password meta-command at the end prompts for it on your terminal and sends
-- only a hash to the server, so it stays out of the repository, the shell
-- history, and the server log. Store the password in the reader's own secret
-- store, outside this repository.
--
-- The login role holds no privileges of its own; it only joins the group role.
-- The grant on account_balances (in balances_reader_group.sql) is the access
-- control. Nothing else in this file restricts what the role may do.
--
-- Not idempotent: CREATE ROLE fails if the login role already exists, so
-- re-running this file for an existing reader stops with an error. To rotate
-- that reader's password, connect as a superuser and run only:
--   \password <reader_login_name>
-- To revoke access, drop the role (DROP ROLE <reader_login_name>).

CREATE ROLE :"login_role"
    LOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE
    CONNECTION LIMIT 5
    IN ROLE balances_reader;

-- A default, not a control: sessions of this role start read-only, which
-- blocks accidental writes. A session can switch it off with
-- SET default_transaction_read_only = off, so it never replaces the grant.
ALTER ROLE :"login_role" SET default_transaction_read_only = on;

\password :login_role
