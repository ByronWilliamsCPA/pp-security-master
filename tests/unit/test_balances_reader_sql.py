"""The read-only reader scripts parse and grant only on ``account_balances``.

The scripts under ``scripts/sql`` need a superuser, so they are not Alembic
migrations and are never run by the test suite. These tests read them as text,
split them into statements, and check that the only privileges they hand out
are SELECT on the balances table and USAGE on its schema. Made-up role names
only; no real credentials appear in any script.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from security_master.storage.balance_models import AccountBalance

pytestmark = [pytest.mark.unit, pytest.mark.storage]

SQL_DIR = Path(__file__).resolve().parents[2] / "scripts" / "sql"
GROUP_SCRIPT = SQL_DIR / "balances_reader_group.sql"
LOGIN_SCRIPT = SQL_DIR / "balances_reader_login.sql"

TABLE = AccountBalance.__tablename__
SCHEMA = AccountBalance.__table__.schema or "public"
GROUP_ROLE = "balances_reader"

_GRANT_TABLE = re.compile(
    rf"^GRANT SELECT ON (?:TABLE )?{SCHEMA}\.{TABLE} TO {GROUP_ROLE}$",
    re.IGNORECASE,
)
_GRANT_SCHEMA = re.compile(
    rf"^GRANT USAGE ON SCHEMA {SCHEMA} TO {GROUP_ROLE}$", re.IGNORECASE
)
_REVOKE_TABLE = re.compile(
    rf"^REVOKE ALL (?:PRIVILEGES )?ON (?:TABLE )?{SCHEMA}\.{TABLE} "
    rf"FROM {GROUP_ROLE}$",
    re.IGNORECASE,
)


def split_statements(text: str) -> list[str]:
    """Split SQL text into statements, whitespace-normalised.

    Handles ``--`` comments, single-quoted strings, dollar-quoted blocks, and
    psql meta-command lines (which start with a backslash and are dropped).

    Args:
        text: The SQL script text.

    Returns:
        The non-empty statements without their trailing semicolon.
    """
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("\\")]
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    in_dollar = False
    i = 0
    source = "\n".join(lines)
    while i < len(source):
        char = source[i]
        if not in_string and not in_dollar and source.startswith("--", i):
            newline = source.find("\n", i)
            i = len(source) if newline == -1 else newline
            continue
        if not in_dollar and char == "'":
            in_string = not in_string
        elif not in_string and source.startswith("$$", i):
            in_dollar = not in_dollar
            current.append("$$")
            i += 2
            continue
        if char == ";" and not in_string and not in_dollar:
            statements.append(" ".join("".join(current).split()))
            current = []
        else:
            current.append(char)
        i += 1
    tail = " ".join("".join(current).split())
    if tail:
        statements.append(tail)
    return [s for s in statements if s]


def _code(path: Path) -> str:
    """Return the script with comments and psql meta-commands removed."""
    return " ".join(split_statements(path.read_text(encoding="utf-8")))


def _do_bodies(statements: list[str]) -> list[str]:
    """Return the text between the dollar quotes of every DO block."""
    bodies: list[str] = []
    for statement in statements:
        if statement.upper().startswith("DO "):
            bodies.extend(re.findall(r"\$\$(.*?)\$\$", statement, re.DOTALL))
    return bodies


def _grant_like(statements: list[str]) -> list[str]:
    return [s for s in statements if re.match(r"^(GRANT|REVOKE)\b", s, re.IGNORECASE)]


def test_table_name_is_still_account_balances() -> None:
    """The script text is pinned to the model; a rename must update both."""
    assert TABLE == "account_balances"
    assert SCHEMA == "public"


@pytest.mark.parametrize("path", [GROUP_SCRIPT, LOGIN_SCRIPT])
def test_scripts_exist_and_parse(path: Path) -> None:
    """Each script exists, is non-empty, and splits into whole statements."""
    assert path.is_file(), f"missing {path}"
    statements = split_statements(path.read_text(encoding="utf-8"))
    assert statements
    # A statement left open by an unbalanced quote would swallow the rest.
    assert all(s.count("'") % 2 == 0 for s in statements)


def test_group_script_creates_a_nologin_role() -> None:
    """The group role cannot log in and is the grant target."""
    text = GROUP_SCRIPT.read_text(encoding="utf-8")
    statements = split_statements(text)
    creates = [s for s in statements if "CREATE ROLE" in s.upper()]
    assert creates, "no CREATE ROLE statement"
    assert all(re.search(r"\bNOLOGIN\b", s, re.IGNORECASE) for s in creates)
    assert all(GROUP_ROLE in s for s in creates)
    assert not any(re.search(r"\bPASSWORD\b", s, re.IGNORECASE) for s in statements)


def test_group_script_grants_select_on_the_balances_table_only() -> None:
    """Every GRANT is SELECT on the table or USAGE on its schema; nothing else."""
    statements = split_statements(GROUP_SCRIPT.read_text(encoding="utf-8"))
    grants = [s for s in statements if s.upper().startswith("GRANT")]
    assert any(_GRANT_TABLE.match(s) for s in grants), "no SELECT grant on the table"
    assert any(_GRANT_SCHEMA.match(s) for s in grants), "no USAGE grant on the schema"
    for statement in grants:
        assert _GRANT_TABLE.match(statement) or _GRANT_SCHEMA.match(statement), (
            f"unexpected grant: {statement}"
        )


def test_group_script_has_no_broad_or_write_privileges() -> None:
    """No write privilege, ALL TABLES, default privileges, or PUBLIC grant."""
    text = GROUP_SCRIPT.read_text(encoding="utf-8")
    statements = split_statements(text)
    for statement in _grant_like(statements):
        upper = statement.upper()
        assert not re.search(
            r"\b(INSERT|UPDATE|DELETE|TRUNCATE|REFERENCES|TRIGGER|CREATE|ALL TABLES"
            r"|ALL SEQUENCES|SEQUENCE)\b",
            upper.replace("REVOKE ALL", ""),
        ), statement
        assert "PUBLIC" not in upper.split(" TO ")[-1].split(" FROM ")[-1], statement
    assert not any("DEFAULT PRIVILEGES" in s.upper() for s in statements)
    for statement in statements:
        if statement.upper().startswith("REVOKE"):
            assert _REVOKE_TABLE.match(statement), f"unexpected revoke: {statement}"


def test_login_template_grants_membership_only() -> None:
    """The login role joins the group role; it holds no table privileges itself."""
    text = LOGIN_SCRIPT.read_text(encoding="utf-8")
    statements = split_statements(text)
    assert not any(s.upper().startswith("GRANT") for s in statements) or all(
        re.match(rf"^GRANT {GROUP_ROLE} TO ", s, re.IGNORECASE)
        for s in statements
        if s.upper().startswith("GRANT")
    )
    creates = [s for s in statements if "CREATE ROLE" in s.upper()]
    assert creates
    assert all(re.search(r"\bLOGIN\b", s, re.IGNORECASE) for s in creates)
    assert all(
        re.search(rf"\bIN ROLE {GROUP_ROLE}\b", s, re.IGNORECASE) for s in creates
    )


def test_no_password_or_host_literal_in_any_script() -> None:
    """The password is set outside the repo; no address or host is written down."""
    for path in (GROUP_SCRIPT, LOGIN_SCRIPT):
        text = path.read_text(encoding="utf-8")
        code = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("--")
        )
        assert not re.search(r"PASSWORD\s+'", code, re.IGNORECASE), path.name
        assert not re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text), path.name


@pytest.mark.parametrize("path", [GROUP_SCRIPT, LOGIN_SCRIPT])
def test_no_default_privileges_in_any_script(path: Path) -> None:
    """Neither script may alter default privileges, at any nesting level."""
    assert "DEFAULT PRIVILEGES" not in _code(path).upper()


def test_do_blocks_only_guard_role_creation() -> None:
    """A DO block may create the role; it may not grant, revoke, or alter."""
    statements = split_statements(GROUP_SCRIPT.read_text(encoding="utf-8"))
    bodies = _do_bodies(statements)
    assert bodies, "expected the role-creation guard"
    forbidden = re.compile(
        r"\b(GRANT|REVOKE|ALTER|DROP|SUPERUSER|INSERT|UPDATE|DELETE|EXECUTE)\b",
        re.IGNORECASE,
    )
    for body in bodies:
        assert not forbidden.search(body), body


def test_every_grant_and_revoke_is_a_top_level_statement() -> None:
    """No GRANT or REVOKE hides inside a DO block or a string."""
    for path in (GROUP_SCRIPT, LOGIN_SCRIPT):
        statements = split_statements(path.read_text(encoding="utf-8"))
        top_level = sum(
            1 for s in statements if re.match(r"^(GRANT|REVOKE)\b", s, re.IGNORECASE)
        )
        anywhere = len(re.findall(r"\b(GRANT|REVOKE)\b", _code(path), re.IGNORECASE))
        assert top_level == anywhere, path.name


def test_login_role_is_explicitly_not_a_superuser() -> None:
    """The login role says NOSUPERUSER and nothing in the script grants SUPERUSER."""
    statements = split_statements(LOGIN_SCRIPT.read_text(encoding="utf-8"))
    creates = [s for s in statements if "CREATE ROLE" in s.upper()]
    assert creates
    assert all(re.search(r"\bNOSUPERUSER\b", s, re.IGNORECASE) for s in creates)
    assert not re.search(r"\bSUPERUSER\b", _code(LOGIN_SCRIPT), re.IGNORECASE)


def test_login_alter_role_only_sets_read_only_default() -> None:
    """The one ALTER ROLE is the read-only session default, and it is present."""
    statements = split_statements(LOGIN_SCRIPT.read_text(encoding="utf-8"))
    alters = [s for s in statements if s.upper().startswith("ALTER ")]
    assert alters, "default_transaction_read_only is not set"
    for statement in alters:
        assert re.match(
            r'^ALTER ROLE :"login_role" SET default_transaction_read_only = on$',
            statement,
            re.IGNORECASE,
        ), statement
