"""Unit tests for the account registry loader and its configuration."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from security_master.balances.registry import (
    RegistryError,
    load_registry,
    parse_registry,
)

from .balance_support import EXAMPLE_SEED

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.storage]

_GOOD = """
accounts:
  - account_key: "pp:ibkr:0001"  # pragma: allowlist secret -- account key, not a secret
    entity_id: "11111111-1111-4111-8111-111111111111"
    display_name: "Example Brokerage Account"
    category: "Investments"
"""


def test_example_seed_loads_and_is_made_up() -> None:
    registry = load_registry(EXAMPLE_SEED)
    keys = [a.account_key for a in registry.accounts()]
    assert keys == ["pp:bank:0003", "pp:ibkr:0001", "pp:ibkr:0002"]
    first = registry.require("pp:ibkr:0001")
    assert isinstance(first.entity_id, uuid.UUID)
    assert first.display_name == "Example Brokerage Account"
    assert first.category == "Investments"
    assert registry.get("pp:ibkr:9999") is None


def test_require_unknown_key_names_only_the_key() -> None:
    registry = parse_registry(_GOOD)
    with pytest.raises(RegistryError, match=r"pp:ibkr:0009"):
        registry.require("pp:ibkr:0009")


@pytest.mark.parametrize(
    ("mutation", "fragment"),
    [
        (("account_key", "ibkr:0001"), "pp:"),
        (("account_key", "pp:ibkr:12345"), "consecutive digits"),
        (("entity_id", "not-a-uuid"), "valid UUID"),
        (("entity_id", "00000000-0000-0000-0000-000000000000"), "nil UUID"),
        (("category", "Stocks"), "exactly one of"),
        (("display_name", ""), "display_name"),
        (("display_name", "x" * 201), "too long"),
    ],
)
def test_invalid_entries_are_rejected(mutation: tuple[str, str], fragment: str) -> None:
    field, value = mutation
    text = _GOOD.replace(
        {
            "account_key": '"pp:ibkr:0001"',
            "entity_id": '"11111111-1111-4111-8111-111111111111"',
            "category": '"Investments"',
            "display_name": '"Example Brokerage Account"',
        }[field],
        f'"{value}"',
    )
    with pytest.raises(RegistryError, match=fragment):
        parse_registry(text)


def test_missing_entity_id_is_rejected() -> None:
    text = _GOOD.replace('    entity_id: "11111111-1111-4111-8111-111111111111"\n', "")
    with pytest.raises(RegistryError, match="entity_id"):
        parse_registry(text)


def test_duplicate_keys_and_empty_seed_are_rejected() -> None:
    entry = _GOOD.split("accounts:")[1]
    with pytest.raises(RegistryError, match="duplicate"):
        parse_registry("accounts:" + entry + entry)
    for bad in ("", "accounts: []", "- just a list", "accounts: [:"):
        with pytest.raises(RegistryError):
            parse_registry(bad)


def test_path_comes_from_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = tmp_path / "seed.yaml"
    seed.write_text(_GOOD, encoding="utf-8")
    monkeypatch.chdir(tmp_path)  # no .env here
    monkeypatch.setenv("PP_ACCOUNT_REGISTRY_PATH", str(seed))
    assert load_registry().require("pp:ibkr:0001").display_name.startswith("Example")


def test_unset_or_unreadable_path_fails_clearly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PP_ACCOUNT_REGISTRY_PATH", raising=False)
    with pytest.raises(RegistryError, match="not configured"):
        load_registry()
    with pytest.raises(RegistryError, match="could not be read"):
        load_registry(tmp_path / "missing.yaml")
