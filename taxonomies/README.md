# Portfolio Performance taxonomy files

Importable taxonomy definitions for Portfolio Performance (PP). Full background,
the catalog of every PP taxonomy, and the model-column mapping are in
[`docs/project/PP_TAXONOMY_CATALOG.md`](../docs/project/PP_TAXONOMY_CATALOG.md).

## Files

Each `*.taxonomy.json` file is one PP taxonomy in the schema PP's
`Import taxonomy` feature accepts (`name`, `color`, `categories[]`; each category
has `name`, optional `key`, `color`, and nested `children[]`).

| File | Taxonomy | Nodes |
| --- | --- | --- |
| `brx-plus-byron.taxonomy.json` | BRX-Plus (Byron), custom | 32 |
| `asset-classes.taxonomy.json` | Asset Classes | 5 |
| `industries-gics.taxonomy.json` | Industries (GICS), 4-level | 262 |
| `industries-gics-sectors.taxonomy.json` | Industries (GICS, Sectors) | 11 |
| `asset-allocation.taxonomy.json` | Asset Allocation (Kommer) | 11 |
| `regions-msci.taxonomy.json` | Regions (MSCI) | 100 |
| `type-of-security.taxonomy.json` | Type of Security | 7 |

## Import into Portfolio Performance

1. Open your portfolio in PP.
2. `File > Import > Import taxonomy`.
3. Select a `*.taxonomy.json` file. The taxonomy is added without altering the
   rest of the file. Repeat per taxonomy.

The custom `brx-plus-byron.taxonomy.json` is the one that must be imported. The
six built-ins can instead be created via `File > New > Taxonomy > [template]`.

## Diagrams

PlantUML sources and rendered SVGs are in [`diagrams/`](diagrams):

| Diagram | Shows |
| --- | --- |
| [`brx_plus_taxonomy`](diagrams/brx_plus_taxonomy.svg) | The full BRX-Plus (Byron) custom tree (4 sleeves, 28 leaves) |
| [`taxonomy_landscape`](diagrams/taxonomy_landscape.svg) | All 7 taxonomies in use, built-in vs custom, with levels and node counts |

Regenerate after editing a `.puml`:

```bash
java -jar "$HOME/.cache/plantuml/plantuml.jar" -tsvg taxonomies/diagrams/*.puml
```

## Validate

```bash
python3 scripts/validate_taxonomy_json.py
```

Checks every file against PP's importer contract: required `name`, valid hex
colors, unique classification keys per taxonomy, and (when present) instrument
assignment weights within 0-100 summing to at most 100.

## Scope

Structure only. Security-to-node assignments (the `instruments` block) are
deferred to Phase C, when securities are imported.
