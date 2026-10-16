"""Account registry: account key to entity UUID and display name.

The registry is loaded from a YAML seed file whose path comes from
configuration (``PP_ACCOUNT_REGISTRY_PATH`` or ``.env``) and lives outside this
repository. It is deliberately not a database table: the entity master is
owned elsewhere and ``legal_entities`` here has integer keys, no UUID, and no
account key, so mirroring the seed into it would create a second entity master.

Seed shape: see ``seeds/account_registry.example.yaml``. Each entry maps an
account key to an entity UUID, a display name, and a category.

Personal accounts point at the owner's ``individual`` entity and joint items at
a ``household`` entity; that choice is made in the seed, not in code.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .rules import (
    BalanceRuleError,
    validate_account_key,
    validate_category,
)

_MAX_DISPLAY_NAME = 200


class RegistryError(ValueError):
    """The account registry seed is missing, unreadable, or invalid."""


class RegistrySettings(BaseSettings):
    """Registry configuration read from the environment or ``.env``.

    Attributes:
        model_config: Pydantic-settings configuration (``PP_`` prefix, env file).
        account_registry_path: Path to the seed YAML, outside the repository.
    """

    model_config = SettingsConfigDict(env_prefix="PP_", env_file=".env", extra="ignore")

    account_registry_path: Path | None = Field(default=None)


@dataclass(frozen=True)
class RegisteredAccount:
    """One mapped account: key, owning entity, display name, and category.

    The field rules are enforced on construction, so an instance is always
    valid however it was built.
    """

    account_key: str
    entity_id: uuid.UUID
    display_name: str
    category: str

    def __post_init__(self) -> None:
        """Validate every field against the account_balances rules.

        Raises:
            RegistryError: When the key or category violates the field rules,
                the entity id is the nil UUID, or the display name is blank or
                longer than 200 characters.
        """
        try:
            validate_account_key(self.account_key)
            validate_category(self.category)
        except BalanceRuleError as exc:
            raise RegistryError(str(exc)) from exc
        if self.entity_id.int == 0:
            msg = f"{self.account_key}: entity_id must not be the nil UUID"
            raise RegistryError(msg)
        if not self.display_name.strip():
            msg = f"{self.account_key}: display_name must not be blank"
            raise RegistryError(msg)
        if len(self.display_name) > _MAX_DISPLAY_NAME:
            msg = f"{self.account_key}: display_name is too long"
            raise RegistryError(msg)


class AccountRegistry:
    """Read-only lookup of mapped accounts by account key."""

    def __init__(self, accounts: list[RegisteredAccount]) -> None:
        """Index accounts by key, refusing duplicates.

        Args:
            accounts: Validated accounts; each key may appear only once.

        Raises:
            RegistryError: When two accounts share a key.
        """
        by_key: dict[str, RegisteredAccount] = {}
        for account in accounts:
            if account.account_key in by_key:
                msg = f"duplicate account key in registry: {account.account_key}"
                raise RegistryError(msg)
            by_key[account.account_key] = account
        self._by_key = by_key

    def get(self, account_key: str) -> RegisteredAccount | None:
        """Return the account for a key, or None when it is not mapped.

        Args:
            account_key: The ``pp:``-prefixed account key.

        Returns:
            The registered account, or None.
        """
        return self._by_key.get(account_key)

    def require(self, account_key: str) -> RegisteredAccount:
        """Return the account for a key or raise a clear error.

        Args:
            account_key: The ``pp:``-prefixed account key.

        Returns:
            The registered account.

        Raises:
            RegistryError: When the key is not in the registry.
        """
        account = self._by_key.get(account_key)
        if account is None:
            msg = f"account {account_key} is not in the account registry"
            raise RegistryError(msg)
        return account

    def accounts(self) -> list[RegisteredAccount]:
        """Return every mapped account, sorted by account key.

        Returns:
            Registered accounts in key order.
        """
        return [self._by_key[k] for k in sorted(self._by_key)]


def resolve_registry_path(explicit: Path | str | None = None) -> Path:
    """Resolve the seed path from an explicit override or configuration.

    Args:
        explicit: A path given on the command line, taking precedence.

    Returns:
        The seed file path.

    Raises:
        RegistryError: When no path is configured.
    """
    if explicit is not None:
        return Path(explicit)
    configured = RegistrySettings().account_registry_path
    if configured is None:
        msg = (
            "account registry path is not configured; set PP_ACCOUNT_REGISTRY_PATH "
            "to a seed file outside the repository"
        )
        raise RegistryError(msg)
    return configured


def _text_field(raw: dict[str, object], name: str, where: str) -> str:
    """Return a required non-empty string field, stripped.

    Args:
        raw: The decoded YAML mapping for one entry.
        name: The field name to read.
        where: Entry label for the error message.

    Returns:
        The stripped string value.

    Raises:
        RegistryError: When the field is absent, not a string, or blank.
    """
    value = raw.get(name)
    if not isinstance(value, str) or not value.strip():
        msg = f"{where} is missing a non-empty string '{name}'"
        raise RegistryError(msg)
    return value.strip()


def _parse_entry(index: int, raw: object) -> RegisteredAccount:
    """Validate one seed entry.

    Args:
        index: Zero-based position in the seed, for error messages.
        raw: The decoded YAML entry.

    Returns:
        The validated account.

    Raises:
        RegistryError: When a field is missing or violates the field rules.
    """
    where = f"registry entry {index + 1}"
    if not isinstance(raw, dict):
        msg = f"{where} must be a mapping"
        raise RegistryError(msg)
    entry = cast("dict[str, object]", raw)
    key_text = _text_field(entry, "account_key", where)
    entity_text = _text_field(entry, "entity_id", where)
    display_name = _text_field(entry, "display_name", where)
    category_text = _text_field(entry, "category", where)
    try:
        entity_id = uuid.UUID(entity_text)
    except ValueError:
        msg = f"{where}: entity_id is not a valid UUID"
        raise RegistryError(msg) from None
    try:
        return RegisteredAccount(key_text, entity_id, display_name, category_text)
    except RegistryError as exc:
        msg = f"{where}: {exc}"
        raise RegistryError(msg) from exc


def parse_registry(text: str) -> AccountRegistry:
    """Parse and validate seed YAML text.

    Args:
        text: The seed file contents.

    Returns:
        The validated registry.

    Raises:
        RegistryError: When the YAML is malformed, has no accounts, contains a
            duplicate account key, or any entry is invalid.
    """
    try:
        data: object = yaml.safe_load(text)
    except yaml.YAMLError:
        msg = "account registry seed is not valid YAML"
        raise RegistryError(msg) from None
    entries: object = (
        cast("dict[str, object]", data).get("accounts")
        if isinstance(data, dict)
        else None
    )
    if not isinstance(entries, list) or not entries:
        msg = "account registry seed must contain a non-empty 'accounts' list"
        raise RegistryError(msg)
    accounts = [
        _parse_entry(i, raw) for i, raw in enumerate(cast("list[object]", entries))
    ]
    return AccountRegistry(accounts)


def load_registry(path: Path | str | None = None) -> AccountRegistry:
    """Load the registry from the configured (or given) seed file.

    Args:
        path: Optional explicit seed path; defaults to configuration.

    Returns:
        The validated registry.

    Raises:
        RegistryError: When the path is unset, unreadable, or the seed is invalid.
    """
    seed_path = resolve_registry_path(path)
    try:
        text = seed_path.read_text(encoding="utf-8")
    except OSError:
        msg = "account registry seed could not be read; check PP_ACCOUNT_REGISTRY_PATH"
        raise RegistryError(msg) from None
    return parse_registry(text)
