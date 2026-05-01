# Architecture Documentation Design

> **Status**: Approved
> **Date**: 2026-05-01
> **Phase**: Pre-implementation spec
> **Supersedes**: N/A

---

## Context

The pp-security-master repository has 13 Architecture Decision Records (ADR-001 through ADR-013)
describing a comprehensive financial data platform, but no dedicated architecture documentation.
The existing `schema_exports/` directory contains a single PlantUML ER diagram. All other
architectural knowledge lives only in the ADRs and in `CLAUDE.md`.

The current codebase implements roughly 10% of the full system vision: the `storage/` module
(models, mappers, validators, views, schema export), the `patch/` module (PP XML export), and
a stub `cli.py`. The `extractor/`, `classifier/`, FastAPI service, Redis cache, background workers,
observability stack, and analytics engine are all planned but not yet built.

This spec defines the architecture documentation set that will serve as the canonical living
reference for the full system, capturing both what is built today and the design intent for
what will be built.

---

## Goals

1. Produce a documentation set that serves all three audiences simultaneously: personal reference,
   open-source contributors, and public GitHub readers.
2. Document the current implemented architecture accurately so contributors can read the code
   against the docs and find them consistent.
3. Document planned architecture as explicit stubs so the vision is captured and future feature
   branches have a precise target to fill in.
4. Cross-reference all 13 ADRs from the relevant documentation sections.
5. Use diagrams as the primary communication tool, backed by one-paragraph narrative per component.

---

## Approach

**C4-Layered Document Set** organized by zoom level: system context (Level 1) → internal
components (Level 2) → data model, data flows, deployment, and operational concerns as
peer documents.

**Diagram formats:**

- PlantUML for complex structural diagrams (ER, component architecture, deployment topology,
  observability stack, integration tier hierarchy): stored as `.puml` source files in
  `docs/architecture/diagrams/` and rendered via CI or locally.
- Mermaid for flow and sequence diagrams: embedded inline in the `.md` files so they render
  natively on GitHub without additional tooling.

**Stub convention:** Every planned-but-not-yet-implemented component or flow uses a consistent
blockquote callout:

```markdown
> **Planned:** This component is not yet implemented. It is scheduled for Phase [N]
> per [ADR-XXX: Title].
```

This keeps the docs honest, signals the implementation status to contributors, and gives future
feature branches a precise anchor to replace when they ship.

---

## Document Structure

All architecture documentation lives under `docs/architecture/`. The `schema_exports/` directory
is preserved as-is; the new `diagrams/er-schema.puml` supersedes `schema_exports/security_master_schema.puml`
as the canonical ER source but does not delete it (the schema export pipeline in
`storage/schema_export.py` continues to generate `schema_exports/` output).

```text
docs/architecture/
├── README.md                    # Index and audience reading guide
├── 01-system-context.md         # C4 Level 1: external actors and system boundary
├── 02-components.md             # C4 Level 2: internal modules and services
├── 03-data-model.md             # Full ER diagram and schema narrative
├── 04-data-flows.md             # All 8 data flows with diagrams
├── 05-deployment.md             # Unraid infrastructure topology
├── 06-integrations.md           # External API tier hierarchy and caching strategy
├── 07-observability.md          # Metrics, logging, tracing, and alerting stack
├── 08-security.md               # Authentication, RBAC, encryption, audit logging
└── diagrams/
    ├── components.puml           # Component architecture (PlantUML)
    ├── er-schema.puml            # Entity relationships: full vision (PlantUML)
    ├── deployment.puml           # Unraid deployment topology (PlantUML)
    ├── integration-tiers.puml    # 4-tier API sourcing hierarchy (PlantUML)
    └── observability.puml        # Observability stack (PlantUML, stub)
```

---

## Diagram Inventory

13 diagrams in total. Status indicates whether the diagram can be built from current code
("Current") or must be authored from ADR design intent ("Planned stub").

| # | Diagram | Format | Home file | Status |
|---|---------|--------|-----------|--------|
| 1 | System Context | Mermaid inline | `01-system-context.md` | Current |
| 2 | Component Architecture | PlantUML | `diagrams/components.puml` → `02-components.md` | Current + stubs |
| 3 | Entity Relationship | PlantUML | `diagrams/er-schema.puml` → `03-data-model.md` | Update existing |
| 4 | PP Sync / Patch Flow | Mermaid inline | `04-data-flows.md` | Current |
| 5 | Institution Import Pipeline | Mermaid inline | `04-data-flows.md` | Planned stub |
| 6 | Classification Cascade (4-tier) | Mermaid inline | `04-data-flows.md` | Planned stub |
| 7 | PP Backup / Restore Bidirectional | Mermaid inline | `04-data-flows.md` | Planned stub |
| 8 | Quantitative Analytics Pipeline | Mermaid inline | `04-data-flows.md` | Planned stub |
| 9 | Data Quality Monitoring Flow | Mermaid inline | `04-data-flows.md` | Planned stub |
| 10 | AI / LLM Integration Flow | Mermaid inline | `04-data-flows.md` | Planned stub |
| 11 | Integration Tier Hierarchy | PlantUML | `diagrams/integration-tiers.puml` → `06-integrations.md` | Planned stub |
| 12 | Deployment Topology | PlantUML | `diagrams/deployment.puml` → `05-deployment.md` | Current |
| 13 | Observability Stack | PlantUML | `diagrams/observability.puml` → `07-observability.md` | Planned stub |

**Summary:** 4 current, 8 planned stubs, 1 update-existing.

---

## Per-Document Content Outline

### README.md

- One-paragraph system mission statement.
- Audience map table: public reader (start at 01), contributor (01, 02, 03), maintainer (all).
- Phase status table: which components are current vs. planned.
- Links to all 8 architecture docs and all 13 ADRs.

No diagram.

---

### 01-system-context.md

**Diagram:** Mermaid C4 context diagram showing all external actors inside and outside the
system boundary.

**Narrative covers:**

- Why this service exists (problem statement: retail PP has no programmatic access to its own data).
- System boundary: pp-security-master as the central hub.
- External actors (10+): Portfolio Performance (import source and export destination), Kubera
  (real-time aggregator for reconciliation), Wells Fargo / Interactive Brokers / AltoIRA
  (broker data sources), OpenFIGI / Alpha Vantage / Financial Modeling Prep (classification APIs),
  pp-portfolio-classifier / ppxml2db (open-source libraries), Cloudflare Zero Trust (auth),
  PromptCraft AI agent (consumer).
- One paragraph per major external relationship.

**ADR cross-references:** ADR-001, ADR-002, ADR-008.

---

### 02-components.md

**Diagram:** PlantUML component diagram (C4 Level 2) showing all internal services and their
interfaces.

**Narrative covers one paragraph per module:**

*Current (built):*

- `cli.py`: main entry point, command routing.
- `storage/`: SQLAlchemy models, session management, mappers, validators, views, schema export.
- `patch/pp_xml_export.py`: writes security classifications back to Portfolio Performance XML/JSON.

*Planned stubs:*

- `extractor/`: broker file parsers: PP XML, IBKR Flex Query XML, Wells Fargo CSV, AltoIRA PDF.
- `classifier/`: 4-tier classification engine: fund.py, equity.py, bond.py, fallback/manual queue.
- FastAPI service layer: REST API for external consumers and the LLM integration.
- Background worker cluster: async API classification, batch transaction processing.
- Redis cache: multi-level caching for external API responses.

**ADR cross-references:** ADR-001, ADR-003, ADR-005, ADR-007, ADR-009, ADR-013.

---

### 03-data-model.md

**Diagram:** PlantUML ER diagram: updated from `schema_exports/security_master_schema.puml` to
include the full vision schema grouped by domain.

**Narrative covers:**

*Current tables (4):*

- `securities_master`: core security reference with GICS, MSCI, TRBC, BRX-Plus taxonomy fields,
  pricing data, data quality score (0.00–1.00).
- `kubera_sheets` / `kubera_sections` / `kubera_holdings`: hierarchical Kubera position data
  mapping to PP groups and accounts.
- `holding_comparisons`: PP vs. Kubera variance analysis with configurable tolerance thresholds.

*Planned table groups (stubs):*

- `transactions_wells_fargo`, `transactions_interactive_brokers`, `transactions_altoira`,
  `transactions_kubera`: institution-specific transaction imports.
- `pp_client_config`, `pp_accounts`, `pp_portfolios`, `pp_account_transactions`,
  `pp_portfolio_transactions`, `pp_transaction_units`, `pp_security_prices`, `pp_settings`,
  `pp_bookmarks`: full Portfolio Performance backup restoration tables (ADR-002).
- `reporting_metrics`, `reconciliation_runs`, `duplicate_candidates`: data quality
  tracking tables.
- Consolidated views: `v_holdings_by_group`, `v_holdings_by_account`,
  `v_transactions_consolidated`.

**ADR cross-references:** ADR-001, ADR-002, ADR-004, ADR-012.

---

### 04-data-flows.md

**Diagrams:** 7 Mermaid inline diagrams, each followed by a narrative paragraph. One
additional flow (Reporting Export) is described in prose only and cross-linked to ADR-012
and `07-observability.md`.

**Flow inventory:**

1. **PP Sync / Patch Flow** (Current): DB → `patch/pp_xml_export.py` → Portfolio Performance
   XML/JSON. The only currently implemented outbound flow.
2. **Institution Import Pipeline** (Stub): Broker file (PP XML / IBKR Flex XML / Wells CSV /
   AltoIRA PDF) → extractor → institution transaction table → data quality validation →
   consolidated views.
3. **4-Tier Classification Cascade** (Stub): new security → Tier 1 (PP native APIs) →
   Tier 2a (pp-portfolio-classifier for funds/ETFs) / Tier 2b (BlackRock holdings for iShares) →
   Tier 3 (OpenFIGI → Alpha Vantage → FMP) → Tier 4 (manual queue) → confidence score →
   `securities_master`.
4. **PP Backup / Restore** (Stub): bidirectional: PP XML → `pp_*` tables (import) and
   `pp_*` tables → PP XML generator (export/restore). Disaster recovery path.
5. **Quantitative Analytics Pipeline** (Stub): portfolio positions + price history →
   risk metrics (Sharpe, Treynor, Alpha/Beta, Max Drawdown) → Monte Carlo simulation
   (10,000 paths) → portfolio optimization → results storage → API exposure.
6. **Data Quality Monitoring** (Stub): automated daily checks: completeness scan,
   deduplication, position reconciliation (PP vs. Kubera), price staleness → results
   dashboard → exception workflow.
7. **AI / LLM Integration** (Stub): DB portfolio data → LLM-optimized ETL → token-efficient
   JSON schemas → Redis cache → secure read-only API → PromptCraft agent → portfolio insights.
8. **Reporting Export** (Stub): prose only, cross-linked to ADR-012. Excel/PDF/JSON report
   generation with 7-year compliance archive.

**ADR cross-references:** ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-009, ADR-012, ADR-013.

---

### 05-deployment.md

**Diagram:** PlantUML deployment diagram showing the Unraid containerized topology.

**Narrative covers:**

- Unraid home lab as the deployment target.
- Containerized services: PostgreSQL 17, Redis, FastAPI, background workers.
- PostgreSQL tuning: 8 GB shared buffers, 24 GB effective cache size, SSD-optimized.
- Three-tier storage: NVMe cache pool (hot data: DB files, logs, active processing),
  HDD array (archive: raw broker files, exports), backup pool (30-day local retention).
- Offsite backup via Rclone (1-year retention).
- Env var reference table: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_ECHO`.
- Connection pooling: `pool_pre_ping=True`, `pool_recycle=300`.
- 99.9% uptime target.

**ADR cross-references:** ADR-007.

---

### 06-integrations.md

**Diagram:** PlantUML tier hierarchy diagram showing the 4-tier classification sourcing
cascade with associated APIs, rate limits, and cost per tier.

**Narrative covers:**

- **Tier 1** (PP native APIs and community data): highest confidence, zero API cost.
- **Tier 2** (pp-portfolio-classifier for ETFs/funds, BlackRock quarterly holdings): high
  confidence, open-source, zero API cost.
- **Tier 3** (OpenFIGI 250 req/hr free, Alpha Vantage 25 req/day free, FMP 250 req/day free):
  medium confidence, free tier sufficient for personal use.
- **Tier 4** (manual classification queue): lowest confidence, UI-driven.
- Circuit breaker pattern for external API fault tolerance.
- Multi-level caching strategy: in-memory (Redis, short TTL), database (90-day TTL),
  file (1-year retention).
- Cost management target: $200–500/month external API budget.
- External library integration: pp-portfolio-classifier and ppxml2db as git subtrees (ADR-008).

**ADR cross-references:** ADR-003, ADR-005, ADR-008.

---

### 07-observability.md

**Diagram:** PlantUML stack diagram showing the four observability pillars and their
data flows.

**Narrative covers:**

- **Metrics**: Prometheus collection → four Grafana dashboards: Executive (portfolio overview),
  Operations (system health), Development (API latency, test coverage), Business Intelligence
  (classification accuracy).
- **Logging**: structured JSON log format → ELK stack (Elasticsearch, Logstash, Kibana).
- **Tracing**: OpenTelemetry instrumentation → Jaeger distributed trace visualization.
- **Alerting**: AlertManager → tiered notification: Critical (email + Slack + PagerDuty),
  High (email + Slack), Medium (Slack), Low (log only).
- SLOs: mean time to detection < 5 minutes, false positive rate < 5%.
- Health check endpoints: liveness, readiness, detailed diagnostic.

> **Planned:** Entire observability stack is not yet implemented. Planned per ADR-011.

**ADR cross-references:** ADR-011.

---

### 08-security.md

No diagram. Full narrative document.

**Narrative covers:**

- **Authentication**: Cloudflare Zero Trust as the network-level perimeter. JWT tokens for
  session management with configurable expiry.
- **Authorization**: RBAC with three roles: Admin (full read/write, schema changes),
  Analyst (read/write data, no schema), Read-Only (query access only: used by AI integration).
- **Encryption**: PostgreSQL Transparent Data Encryption (TDE) at rest. TLS 1.3 in transit.
- **Secrets management**: environment variables loaded from `.env`, GPG-encrypted before
  archiving. No secrets in code or git history.
- **Audit logging**: all data mutations logged with actor, timestamp, operation, before/after
  values. 7-year retention for financial compliance.
- **Dependency security**: `pip-audit` on every CI run. Known CVEs documented in
  `docs/known-vulnerabilities.md` per global standard.

> **Planned:** Cloudflare Zero Trust integration, TDE, and full audit logging are not yet
> implemented. Planned per ADR-006.

**ADR cross-references:** ADR-006.

---

## Maintenance Contract

Architecture docs must be updated in the same PR as any of the following changes:

- New module or service added to `src/`
- New database table or view added in a migration
- New external API or library integration added
- Infrastructure change to the Unraid deployment
- A planned stub section becomes implemented code

The `diagram-maintenance` skill assists with PlantUML diagram updates when invoked after
source files change.

---

## Out of Scope

This spec governs the architecture documentation set only. It does not define:

- The implementation of any planned component (extractor, classifier, FastAPI, etc.)
- Database migration scripts for the planned tables
- CI/CD pipeline changes to render PlantUML diagrams
- Changes to the existing `schema_exports/` generation pipeline

---

## Success Criteria

- `docs/architecture/` directory created with all 9 files (README + 8 topic docs).
- All 13 diagrams authored (4 current from code, 8 planned stubs from ADR intent,
  1 updated from existing `.puml`).
- Every doc cross-references its relevant ADRs via footer links.
- All planned stubs use the consistent `> **Planned:**` blockquote callout.
- `docs/architecture/README.md` audience map correctly routes all three reader types.
- Pre-commit passes on all new files (markdownlint, no-em-dash, yamllint where applicable).
