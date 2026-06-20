# ADR-015: Classification Source Coverage and Tier-4 Manual Scope

**Date**: 2026-06-20
**Status**: Accepted
**Deciders**: Byron, Development Team
**Consulted**: ADR-003 (Securities Master Data Sourcing Hierarchy), `docs/research/taxonomy-gics-trbc-cfi-decision.md`, `docs/project/PP_TAXONOMY_CATALOG.md`, `docs/project/TAXONOMY_GUIDE.md`
**Informed**: Classifier, Storage, and Patch layers

## Context

ADR-003 defines a four-tier sourcing hierarchy (PP native, pp-portfolio-classifier,
external APIs, manual) but does not answer two questions that Phase D3 (the manual
Tier-4 fallback) depends on:

1. **Which asset classes can be classified automatically, and which can only be
   classified manually?** Without that map, the manual tier cannot be scoped or
   sized; it risks being built either too broad (duplicating automatable work) or
   too narrow (leaving real gaps unhandled).
2. **What classification data may a redistributed open-source project legally
   ship?** GICS and TRBC are proprietary, and embedding their assignment data
   carries licensing risk. This constrains *which mechanism* (shippable seed file
   vs user-local entry) is legal for each asset class.

This ADR records the coverage map and the licensing posture, both grounded in
primary-source research verified on 2026-06-20, and fixes the scope of Tier-4
manual classification. It does not design the Tier-4 mechanism itself; that is
deferred to the D3 design and a follow-up ADR.

## Decision

### 1. Portfolio Performance is a destination, not a classification source

PP ships taxonomy *structures* (the 11 GICS sector labels, asset-class,
type-of-security, region templates) but never populates security-to-node
*assignments* automatically. Per `PP_TAXONOMY_CATALOG.md` (sourced from PP's
`github.com/buchen/portfolio`), assignments are the consuming application's
responsibility, written back via the taxonomy JSON `instruments` block
(matched ISIN then ticker then WKN then name). Therefore there is no "PP API
coverage" to wait on: every classification assignment is this project's to
produce, from Tiers 2-4, then sync into PP.

### 2. Coverage map by asset class (BRX-Plus sleeve)

The target model is BRX-Plus (`TAXONOMY_GUIDE.md`): Equity, Fixed Income,
Alternatives, Cash. Coverage of *classification assignments* by sleeve:

| BRX-Plus sleeve | Identifier | Instrument type | Sector / classification source | Automatable? | Tier 4 (manual)? |
| --- | --- | --- | --- | --- | --- |
| Equity, US listed | ISIN/ticker | CFI / OpenFIGI / PP template | SIC -> NAICS -> GICS-sector concordance (free, approximate, US-centric) or user-configured FMP/Yahoo | Mostly automated | Overrides only |
| Equity, intl listed | ISIN/ticker | CFI / OpenFIGI | Weak free coverage | Partial | Some manual |
| Equity, funds/ETFs | ISIN/ticker | CFI (cat. C) / PP | pp-portfolio-classifier look-through (holdings) | Automated (user pull) | Low |
| Fixed Income, bonds | ISIN | CFI (cat. D) / OpenFIGI | GICS bond propagation is licensed; free sector is thin | Partial | Some manual |
| Alternatives, commodities | usually ISIN | CFI / OpenFIGI `Comdty` | No industry sector applies | Partial | Mapping |
| Alternatives, crypto | often no ISIN | CFI fits awkwardly | No external taxonomy classifies crypto | No | Yes, standardized mapping |
| Alternatives, private markets | no ticker | none | none | No | Yes, manual |
| Cash | pseudo (e.g. `USD`) | trivial | trivial | Semi | Manual to Cash sleeve |

**Tier-4 manual scope is therefore the Alternatives sleeve plus cash plus
overrides:** crypto (standardized mapping), private markets (manual entry),
cash classification, and occasional manual correction of an automated listed
classification.

### 3. Licensing posture for shippable classification data

Per the verified taxonomy decision guide:

- **GICS / TRBC are licensed and proprietary.** The project may ship the GICS
  sector *names/structure* (PP already does, and `taxonomies/industries-gics-sectors.taxonomy.json`
  re-authors the 11 framework labels), but must **not** redistribute GICS or
  TRBC *assignment data* (identifier to sector) inside the repository.
- **CFI (ISO 10962:2021) is the canonical instrument-type spine.** It is free,
  open, and the only one of the three standards that classifies every asset
  class by instrument type.
- **Free, redistributable sector data** comes from OpenFIGI (`marketSector`,
  public-domain) plus the SIC -> NAICS -> GICS-sector concordance. FMP and Yahoo
  sector fields are personal-use / user-configured only, never bundled.

### 4. Mechanism is constrained by both asset class and legal posture

- **Crypto** classification is the user's own scheme (BTC / ETH / Diversified),
  so it carries no licensing risk and may ship as a version-controlled seed
  mapping file.
- **GICS sector assignments for listed equities** must stay user-local (entered
  per user into their own database), never a bundled dataset, because a
  committed ISIN-to-GICS-sector file would redistribute GICS-derived data.
- **Private-market and override** assignments are inherently per-user and ad-hoc,
  so they belong on an interactive (CLI) path.

## Consequences

- **Phase D3 is now bounded:** it implements Tier-4 manual classification for the
  Alternatives sleeve plus cash plus overrides, not generic "GICS-L1 for
  everything." The roadmap's "manual GICS-L1 classification" wording is narrowed
  accordingly.
- **A provenance and override-lock model is required** on `securities_master`
  before automated tiers land, so a later automated run cannot silently overwrite
  a human classification (ADR-003 section 4.3). The current schema has only a
  single row-level `data_source` string and no per-classification provenance or
  lock; closing that gap is the load-bearing part of D3.
- **CFI instrument-type ingestion and the free-source sector pipeline**
  (OpenFIGI + SIC/NAICS concordance) become defined future-tier work, replacing
  the implicit assumption that GICS data would be sourced directly.
- **The taxonomy reference data** (`taxonomies/*.taxonomy.json`,
  `PP_TAXONOMY_CATALOG.md`, the decision guide, and `scripts/validate_taxonomy_json.py`)
  is the durable foundation this ADR rests on and is committed alongside it.

<!-- RAD markers -->
- `#CRITICAL` (security/financial: licensing): shipping GICS or TRBC assignment
  data in the repository is a redistribution-license violation.
  `#VERIFY` keep all bundled taxonomy files to framework labels only; route any
  GICS-sector *assignment* through user-local entry; add a CI check that no
  committed `taxonomies/` or seed file contains identifier-to-licensed-sector rows.
- `#ASSUME` (external resource): the CFI code list is freely redistributable based
  on ISO externalization intent, but SIX attaches no named open-data license.
  `#VERIFY` obtain written redistribution confirmation from `office@cfi-iso.org`
  before embedding the CFI code list in the distributed app (highest-priority
  open legal item per the decision guide).

## References

- ADR-003: Securities Master Data Sourcing Hierarchy (the four-tier model this ADR scopes)
- `docs/research/taxonomy-gics-trbc-cfi-decision.md`: licensing and free-source analysis (verified 2026-06-20)
- `docs/project/PP_TAXONOMY_CATALOG.md`: PP taxonomy capabilities and import mechanisms
- `docs/project/TAXONOMY_GUIDE.md`: BRX-Plus classification intent
- `docs/project/ROADMAP_2026-06-19.md`: Phase D3 definition
