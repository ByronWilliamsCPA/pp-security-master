# IBOR/ABOR Identifier Contract

> **Status**: Active | **Created**: 2026-06-21 | **Owner**: Byron Williams
>
> Implements ADR-016 section 5 (Phase E4). Defines the keys that join the IBOR
> (pp-security-master), the ABOR (Xero), and xero-crypto so a holding can be
> traced across all three. The executable half is
> [`src/security_master/crosswalk.py`](../../src/security_master/crosswalk.py)
> and the Entity Registry models in
> [`storage/entity.py`](../../src/security_master/storage/entity.py).

## Join keys

| Concept | IBOR (pp-security-master) | ABOR (Xero / xero-crypto) | Join |
| --- | --- | --- | --- |
| Client | `Client.id` | `xero_crypto` `Client.id` | `Client.xero_crypto_client_id` |
| Legal entity | `LegalEntity` | Xero organisation (tenant) | `LegalEntity.xero_organisation_id` |
| Holding location | PP account/portfolio | `Wallet.address`; Xero bank/asset account | `LegalEntity.pp_portfolio_ref` |
| GL account | "Accounting (Xero GL)" node key | Xero account `code` (8-digit) | `crosswalk.resolve_gl_account()` |
| Instrument | `isin`, `symbol`, `wkn` | asset symbol; crypto `contract_address` + `chain_id` | symbol / ISIN match |

## Resolution rules

- **Holding to GL account**: `resolve_gl_account(brx_plus_key=, type_of_security=)`.
  BRX-Plus key wins; Type of Security is the fallback; `None` means unresolved
  (e.g. the cash sleeves pending GL codes). Holding-intent (current vs
  non-current) is a per-holding override, not derivable from PP data.
- **Instrument type to CFI**: `resolve_cfi_category(type_of_security)` returns
  the ISO 10962 category letter.
- **Provider sector to GICS**: `resolve_gics_from_provider(sector)` (Morningstar
  scheme).
- **Instrument matching** (when assignments are synced into PP): ISIN, then
  ticker, then WKN, then name, per the PP taxonomy JSON importer.

## What xero-crypto must expose

For the contract to hold, xero-crypto must keep these stable and queryable:

- `Client.id` (UUID) recorded in the IBOR as `Client.xero_crypto_client_id`.
- `Wallet.address` (immutable on-chain address) as the holding-location key.
- One Xero organisation per legal entity, its OrganisationID recorded as
  `LegalEntity.xero_organisation_id`.

Concrete changes inside xero-crypto are a separate repository and PR; this
document is the contract they target.

## Direct-investments-only clients

Such a client has `Client.direct_investments_only = true` and holdings that
resolve through asset class plus the GL crosswalk (Publicly Traded Securities /
Digital Assets) with no fund look-through. No special handling is required.
