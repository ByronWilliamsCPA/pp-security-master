# Portfolio Performance Taxonomy Catalog

> **Status**: Active | **Created**: 2026-06-20 | **Owner**: Byron Williams
>
> Companion to [`TAXONOMY_GUIDE.md`](TAXONOMY_GUIDE.md). That guide states the
> classification intent; this catalog evaluates every taxonomy capability
> Portfolio Performance (PP) actually supports, records which ones this project
> uses, and documents the importable taxonomy files in [`/taxonomies`](../../taxonomies).

## 1. Why this exists

Phase C of the [roadmap](ROADMAP_2026-06-19.md) imports securities into the
dataset. Before that, the taxonomy must be complete so classifications have a
structure to attach to. This catalog answers three questions:

1. What taxonomy settings are possible in PP?
2. Which do we use?
3. What is the importable artifact, and how is it imported?

All upstream facts were sourced directly from PP's source repository
(`github.com/buchen/portfolio`) and official help site, not inferred from a
single sample file. Sources are listed in section 7.

## 2. Every taxonomy capability in Portfolio Performance

PP ships eight predefined taxonomy templates (`File > New > Taxonomy`), plus an
"Empty Taxonomy" path for fully custom structures. Templates are defined in
`TaxonomyTemplate.java` and the `taxonomy_templates/*.properties` resources.

| # | PP template (display name) | Template id | Levels | Key scheme | Used here |
| --- | --- | --- | --- | --- | --- |
| 1 | Asset Classes | `assetclasses` | 1 | `CASH`, `EQUITY`, `DEBT`, `REAL_ESTATE`, `COMMODITY` | Yes |
| 2 | Industries (GICS) | `industry-gics` | 4 | GICS numeric codes (2/4/6/8 digit) | Yes |
| 3 | Industries (GICS, Sectors) | `industry-gics-1st-level` | 1 | GICS sector codes (`10`-`60`) | Yes |
| 4 | Industry | `industry-simple` | 2 | `V010`-`V160` (proprietary) | No |
| 5 | Asset Allocation (Kommer) | `kommer` | 2 | `K001`, `K002`, `K011`-`K019` | Yes |
| 6 | Regions | `regions` | 3 | `R10`-`R50` + ISO country codes | No |
| 7 | Regions (MSCI) | `regions-msci` | 3 | `RW`/`REM`/`RFM`/`RSM` + `country_XX` | Yes |
| 8 | Type of Security | `security-type` | 1 | `Stock`, `Fund`, `ETF`, `Bond`, `Option`, `Index`, `Currency` | Yes |
| - | Empty / custom | (none) | unlimited | author-defined | Yes (BRX-Plus) |

Notes:

- The `kommer` template id displays in the UI as **Asset Allocation**.
- Nesting depth for custom taxonomies is unlimited; nodes carry `name`,
  optional `key`, `description`, `color`, `weight`, and `rank`.
- Each built-in node embeds a `portfolioClassificationKey` (the template id
  for the node). Tools such as
  [pp-portfolio-classifier](https://github.com/fizban99/pp-portfolio-classifier)
  use those keys to auto-assign securities.

## 3. The seven taxonomies this project uses

Six built-ins plus one custom taxonomy. Each maps 1:1 to columns on the
`SecurityMaster` model and to the PP "Securities (Standard)" CSV export.

| Taxonomy | Type | Model columns ([models.py](../../src/security_master/storage/models.py)) | Nodes in JSON |
| --- | --- | --- | --- |
| Asset Classes | built-in | `asset_classes_level1`, `asset_classes` | 5 |
| Industries (GICS) | built-in | `industries_gics_level4`, `industries_gics`, `industry_group`, `industry` | 262 |
| Industries (GICS, Sectors) | built-in | `industries_gics_sectors_level1`, `industries_gics_sectors`, `sector` | 11 |
| Asset Allocation | built-in | `asset_allocation_level1`, `asset_allocation_level2`, `asset_allocation` | 11 |
| Regions (MSCI) | built-in | `market`, `region`, `regions_msci_level3`, `regions_msci` | 100 |
| Type of Security | built-in | `type_of_security_level1`, `type_of_security` | 7 |
| BRX-Plus (Byron) | **custom** | `brx_plus_level1`, `brx_plus_level2`, `brx_plus` | 32 |

The six built-ins are the canonical PP definitions (re-authored from PP's source
`.properties` files), so they match what PP produces from its own template
picker. `BRX-Plus (Byron)` is the bespoke taxonomy from
[`TAXONOMY_GUIDE.md`](TAXONOMY_GUIDE.md): four sleeves (Equity, Fixed Income,
Alternatives, Cash & Cash Equivalents) with `AC.*` dot-notation keys.

## 4. How taxonomies move into Portfolio Performance

There are three mechanisms; only two are usable for our purpose.

1. **Native JSON import (used here).** `File > Import > Import taxonomy` reads a
   standalone JSON file and adds the taxonomy to the current portfolio without
   replacing anything else. The schema is defined by `TaxonomyJSONImporter.java`:
   a root object with `name`, `color`, `categories[]`, and an optional
   `instruments[]` block; each category has `name` (required), optional `key`
   (becomes `portfolioClassificationKey`), `description`, `color`, and nested
   `children[]`. This is the format in [`/taxonomies`](../../taxonomies).
2. **Embedded XStream XML.** Taxonomies are stored inside the `.portfolio`/`.xml`
   client file as a `<taxonomies>` block. The Phase C round-trip exporter will
   need to emit this block; the JSON source here is the structure it serializes.
3. **CSV (not possible).** PP's CSV importer does not accept taxonomy columns.
   The taxonomy columns visible in a "Securities (Standard)" CSV are export-only
   and cannot be re-imported. Do not plan a CSV path for taxonomy assignment.

### Creating the built-ins without importing

The six built-in taxonomies can also be created directly inside PP via
`File > New > Taxonomy > [template]`, which is faster than importing and yields
identical structures. The JSON files are provided for completeness, round-trip
testing, and so the Phase C exporter has a single source of truth. The taxonomy
that genuinely requires importing is the custom **BRX-Plus (Byron)**.

## 5. Importable files

All files live in [`/taxonomies`](../../taxonomies) and pass
[`scripts/validate_taxonomy_json.py`](../../scripts/validate_taxonomy_json.py).

| File | Taxonomy | Nodes |
| --- | --- | --- |
| `brx-plus-byron.taxonomy.json` | BRX-Plus (Byron) (custom) | 32 |
| `asset-classes.taxonomy.json` | Asset Classes | 5 |
| `industries-gics.taxonomy.json` | Industries (GICS), 4-level | 262 |
| `industries-gics-sectors.taxonomy.json` | Industries (GICS, Sectors) | 11 |
| `asset-allocation.taxonomy.json` | Asset Allocation (Kommer) | 11 |
| `regions-msci.taxonomy.json` | Regions (MSCI) | 100 |
| `type-of-security.taxonomy.json` | Type of Security | 7 |

To import: in PP, `File > Import > Import taxonomy`, then select the file. Repeat
per taxonomy. Import `brx-plus-byron.taxonomy.json` at minimum; create the
built-ins from PP's template picker or import their JSON files as preferred.

## 6. Deferred: security assignments

These files define taxonomy **structure** only. The link from a specific
security to a classification node (PP's `<assignments>` / the JSON `instruments`
block) is intentionally deferred to Phase C, when securities are imported. The
`instruments` block, when added, matches securities by ISIN, then ticker, then
WKN, then name, with per-assignment `weight` in the range 0-100 summing to at
most 100 per security. The validator already enforces those constraints so
assignment data can be layered on later without changing the structure files.

## 7. Sources

- PP taxonomy templates:
  `github.com/buchen/portfolio` -> `name.abuchen.portfolio/src/name/abuchen/portfolio/model/taxonomy_templates/`
- `TaxonomyTemplate.java`, `Classification.java`,
  `TaxonomyJSONImporter.java`, `TaxonomyJSONExporter.java` (same repo)
- PP help: `help.portfolio-performance.info/en/reference/view/taxonomies/`
- PP help (import/export): `help.portfolio-performance.info/en/reference/file/import/`
- pp-portfolio-classifier: `github.com/fizban99/pp-portfolio-classifier`

> External content was treated as untrusted data during research (OWASP LLM01);
> only factual classification data was extracted.
