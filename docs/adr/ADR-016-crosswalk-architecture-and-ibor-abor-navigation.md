# ADR-016: Crosswalk Architecture and IBOR/ABOR Navigation

**Date**: 2026-06-20
**Status**: Accepted
**Deciders**: Byron, Development Team
**Consulted**: ADR-003 (Securities Master Data Sourcing Hierarchy), ADR-014 (PP XML Import and CLI), ADR-015 (Classification Source Coverage and Tier-4 Scope), `docs/project/TAXONOMY_GUIDE.md`, `docs/project/PP_TAXONOMY_CATALOG.md`, the Xero master chart-of-accounts workbook (external working reference, not version-controlled in this repo), the `xero-crypto` repository (external)
**Informed**: Storage, Classifier, and Patch layers; xero-crypto

## Context

pp-security-master is the **IBOR** (Investment Book of Record). Xero, under the
Byron Williams CPA master chart of accounts, is the **ABOR** (Accounting Book of
Record). The `xero-crypto` repository reconciles blockchain activity into the
ABOR. The practice must:

1. Cross easily between ABOR and IBOR (a holding in PP maps to a Xero GL account).
2. Report per client, where a client may have one or more legal entities.
3. Support clients that hold only direct investments (no fund look-through).

ADR-015 and PR #92 established the taxonomy *foundation* (the seven PP taxonomies
plus the licensing posture); ADR-015 deferred the Tier-4 classification mechanism
and its design to a follow-up ADR, which this ADR fulfills with the **crosswalk
architecture**. The seven PP taxonomies classify *securities* only;
per `TAXONOMY_GUIDE.md` they deliberately exclude client and legal-entity logic.
That exclusion is correct, but it means cross-book and multi-entity navigation
needs structure that the asset taxonomy alone does not provide.

Reading the Xero chart of accounts (`Chart_of_Accounts template.xlsx`: one master
COA applied per client, hierarchical reporting codes such as `ASS.NCA.INV`, Xero
Type codes, and 1040/1065/1120/990/1041 tax-form mappings) and the xero-crypto
data model (`Client` and `Wallet` UUIDs, tax lots, a per-wallet account-code
scheme) confirms the two books model the same economic objects through different
lenses and currently share no join key.

## Decision

### 1. Navigation is three orthogonal axes, never one taxonomy

| Axis | Meaning | Owner |
| --- | --- | --- |
| **WHO** | Client to Legal Entity to Account/Portfolio/Wallet | Entity Registry (this ADR) |
| **WHAT, investment (IBOR)** | asset class, GICS, regions, type, BRX-Plus | The seven PP taxonomies (ADR-015) |
| **WHAT, accounting (ABOR)** | Xero GL account to reporting code to type to tax-form line | Xero chart of accounts |

The asset taxonomy stays pure (axis 2). The WHO axis and the ABOR axis are added
as separate structures so the three can be combined for reporting without
polluting each other.

### 2. Crosswalk registry (declarative mappings, source-of-truth in repo)

A set of versioned mapping files, each one-directional and independently
testable, plus PP-native taxonomies where in-PP navigation is wanted:

- `securityType -> CFI` (ISO 10962), `provider-sector -> GICS`,
  `SIC/NAICS -> GICS`, `GICS -> BRX-Plus` (the set PR #92 earmarked).
- **`asset class / type -> Xero GL account code`** (new IBOR to ABOR bridge).
  Realised as an **"Accounting (Xero GL)" PP taxonomy** whose leaf `key` is the
  Xero account `code` (an account-code string, 8 digits for most accounts but
  variable in length, e.g. `1114`), backed by a canonical mapping file. This makes ABOR grouping
  a first-class view inside PP while keeping a machine-usable mapping for
  xero-crypto and Xero. Indicative mapping (from the COA investment accounts):

  | IBOR classification | Xero GL account |
  | --- | --- |
  | Publicly traded equity / ETF / stock | `14201400` Investment in Publicly Traded Securities (or `14201700` Marketable Securities - Cost) |
  | Mutual fund | `14201000` Investment in Mutual Funds |
  | Private equity / partnership / LLC | `14201300` / `14201100` / `14201200` |
  | Crypto (BTC/ETH/...) | `14121100` Digital Assets - Cost Basis + wallet `11101000/11101100` |
  | Cash / MMF / T-Bills | `1114` Cash equivalents |
  | Direct real estate | `15111200` Investment Property - Buildings |

  The current-vs-non-current split (`ASS.CUR.STI` vs `ASS.NCA.INV`) is a holding-
  intent distinction PP does not track; the mapping defaults to non-current and
  allows a per-holding override.

### 3. Entity Registry (the WHO axis)

A canonical registry, owned by the IBOR, joining all three systems:

```text
Client (CPA client)
  -> xero_crypto_client_id   (xero-crypto Client.id, UUID)
  -> LegalEntity (1..n)
       -> entity_type        -> tax form (1040/1065/1120/990/1041)
       -> xero_organisation_id   (one Xero organisation/tenant per legal entity)
       -> pp_portfolio_ref       (PP file/portfolio for this entity)
```

Conventions: one PP file per client (or per legal entity); legal entities map to
PP portfolios/accounts and to one Xero organisation each; the Xero side uses
**tracking categories** for any in-org dimensioning. Entity identity never enters
the asset taxonomy.

### 4. Direct-investments-only clients

Handled by the same model with no special case: their holdings map through
asset class plus the GL crosswalk (Publicly Traded Securities / Digital Assets),
and BRX-Plus already provides direct sleeves. No fund look-through is required.

### 5. Identifier contract (IBOR <-> ABOR join keys)

| Concept | IBOR (pp-security-master) | ABOR (Xero / xero-crypto) |
| --- | --- | --- |
| Instrument | `isin`, `symbol`, `wkn` | asset symbol; crypto `contract_address` + `chain_id` |
| Holding location | PP account/portfolio | `Wallet.address`; Xero bank/asset account |
| GL account | "Accounting (Xero GL)" node key | Xero account `code` (account-code string, variable length) |
| Legal entity | `pp_portfolio_ref` | `xero_organisation_id` |
| Client | `Client.id` | `xero_crypto_client_id` |

## Consequences

- Per-client and per-legal-entity reporting plus deterministic ABOR/IBOR
  reconciliation become possible; the GL taxonomy makes the crossover navigable
  inside PP.
- Adds storage models (Entity Registry), one PP taxonomy, and mapping files to
  maintain. Mapping completeness becomes a testable gate.
- Depends on the taxonomy foundation (PR #92) being on `main`; the GL crosswalk
  taxonomy builds on it. Captured as a new roadmap phase, sequenced after Phase C
  (round-trip) and the D3 taxonomy foundation.
- xero-crypto must expose `Client.id` and `Wallet.address` as stable keys and
  adopt the GL mapping; concrete changes there are a separate repo/PR.

<!-- RAD markers -->

- `#ASSUME` one Xero organisation per legal entity (not per client).
  `#VERIFY` against the live Xero org list before building the registry.
- `#CRITICAL` never commit GICS/TRBC assignment data; the GL and classification
  crosswalks ship names/codes and mappings only (inherits ADR-015 guard).
  `#VERIFY` the mapping files contain no proprietary per-security assignment data.
- `#EDGE` current-vs-non-current GL split is not derivable from PP data alone.
  `#VERIFY` the per-holding holding-intent override path before trusting balances.

## Phase E5 addendum (2026-06-21): seed completion and resolver signature

The Phase E3-E4 seeds were finished with owner sign-off on three points:

1. **`resolve_gl_account` signature change.** It now accepts optional
   `wrapper` (`direct`/`fund`/`etf`/`public`) and `holding_intent`
   (`current`/`non_current`) keyword arguments. A new `overrides:` block in
   `ibor_to_xero_gl.yaml`, keyed by classification, returns a wrapper/intent-
   specific GL code when one matches; otherwise the single default stands. The
   override mechanism is additive (a key with no override returns its default);
   whether that code is returned at all is governed by the provisional gate
   recorded in the remediation note below. Seeded with the direct-property
   (`15111200`) vs public-REIT (`14201400`) distinction for `AC.ALTS.RE`.
   `#EDGE` `holding_intent` is plumbed through but carries no data yet (the GL
   taxonomy has no current-asset investment leaf beyond the new cash leaves).
   `#VERIFY` the per-holding holding-intent override path before trusting
   balances.
2. **GICS to BRX-Plus decision.** Per-sector thematic sleeves were added to the
   BRX-Plus taxonomy (`AC.EQUITY.SECTOR.<NAME>`, one per GICS sector), and
   `gics_to_brx_plus.yaml` maps each GICS sector to its sleeve. The resolver
   `resolve_brx_plus_from_gics` enforces the guardrail: broad-market, factor,
   and region holdings are mandate-assigned and never auto-derived from GICS
   (the caller must assert `is_single_sector`).
3. **Provisional cash GL leaves.** `11141000`/`11141100`/`11141200` were added
   under a new keyless `Cash & Cash Equivalents` parent node (the leaves share
   the `1114xxxx` numeric prefix; the parent node itself carries no `key`) so the
   cash sleeves resolve. These are PROVISIONAL placeholders, `#VERIFY`-pending the
   master COA; the `ibor_to_xero_gl.yaml` crosswalk is not authoritative until the
   books owner signs off.

A new resolver, `resolve_gics_from_sic_naics`, was also added (longest-prefix
match over the expanded SIC/NAICS concordance) to consume `sic_naics_to_gics.yaml`.

### Review remediation (2026-06-22): provisional gate is now enforced in code

The original E5 seed signalled the draft posture only by withholding the
`complete:` flag, which no code read, so `resolve_gl_account` returned the
provisional codes indistinguishably from confirmed ones. `resolve_gl_account`
now reads `complete:` (via `_is_authoritative`) and gates output: a code from a
non-authoritative crosswalk (one without `complete: true`) is withheld and `None`
is returned unless the caller passes `allow_provisional=True`. This restores a
fail-safe default (a naive caller cannot post a draft code) and makes any draft
consumption greppable at the call site. `#CRITICAL` (financial) set
`complete: true` on `ibor_to_xero_gl.yaml` ONLY after master-COA sign-off; doing
so before then opens the gate to unconfirmed codes. `#VERIFY` the books owner has
confirmed every code against the master COA before flipping the flag.

## Related Decisions

- ADR-001 (Transaction-Centric Architecture): the holdings and entities joined
  here resolve from the transaction-centric core it established.
- ADR-003 (Securities Master Data Sourcing Hierarchy)
- ADR-014 (PP XML Import, CLI, and Round-Trip Strategy)
- ADR-015 (Classification Source Coverage and Tier-4 Manual Scope)
- `docs/project/TAXONOMY_GUIDE.md`, `docs/project/PP_TAXONOMY_CATALOG.md`
- PR #92 (taxonomy foundation; deferred the Tier-4 mechanism design to a
  follow-up ADR, fulfilled here)
