"""Crypto seed loader + bulk apply by symbol."""

import pytest
from sqlalchemy.orm import Session

from security_master.classifier.crypto_seed import apply_crypto_seed, load_crypto_seed
from security_master.storage.models import SecurityMaster

pytestmark = [pytest.mark.unit, pytest.mark.classifier]


def test_load_crypto_seed_parses_symbols() -> None:
    seed = load_crypto_seed()
    assert seed.by_symbol["BTC"] == "AC.ALTS.CRYPTO.BTC"
    assert seed.default == "AC.ALTS.CRYPTO.DIV"


def test_apply_crypto_seed_assigns_known_symbol(sqlite_session: Session) -> None:
    sec = SecurityMaster(name="Bitcoin", symbol="BTC")
    sqlite_session.add(sec)
    sqlite_session.commit()
    count = apply_crypto_seed(sqlite_session, classified_by="byron")
    sqlite_session.refresh(sec)
    assert count == 1
    assert sec.brx_plus == "AC.ALTS.CRYPTO.BTC"
    assert sec.classification_locked is True


def test_apply_crypto_seed_uses_default_for_unknown(sqlite_session: Session) -> None:
    sec = SecurityMaster(name="Solana", symbol="SOL")
    sqlite_session.add(sec)
    sqlite_session.commit()
    apply_crypto_seed(sqlite_session, classified_by="byron", symbols=["SOL"])
    sqlite_session.refresh(sec)
    assert sec.brx_plus == "AC.ALTS.CRYPTO.DIV"


def test_apply_crypto_seed_skips_locked_rows(sqlite_session: Session) -> None:
    sec = SecurityMaster(name="Bitcoin", symbol="BTC", classification_locked=True)
    sqlite_session.add(sec)
    sqlite_session.commit()
    count = apply_crypto_seed(sqlite_session, classified_by="byron")
    assert count == 0
