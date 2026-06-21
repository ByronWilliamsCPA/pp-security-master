# GICS vs. TRBC vs. CFI for a Portfolio Performance Wrapper: A Taxonomy Decision Guide

> Verified against live primary sources on 2026-06-20 (MSCI/S&P, LSEG, ISO, SIX Group). High-stakes licensing claims confirmed; corrections applied inline.

## TL;DR

- **Use CFI (ISO 10962:2021) as your internal canonical instrument-type model** -- it is the only one of the three that is a free, open ISO standard covering every asset class (equities, debt, funds/ETFs, options, futures, etc.), and the full code list is published free by SIX Group; GICS and TRBC both require paid commercial licenses to redistribute their data inside software.
- **GICS (MSCI/S&P) and TRBC (LSEG) are licensed, proprietary, equity/company-only sector taxonomies.** You cannot legally redistribute their classification data inside an open-source app without a negotiated commercial license, so do not embed them as canonical data -- at most let users map to GICS-style sectors via free third-party fields.
- **For free sector/industry data, layer on open sources** (SEC EDGAR SIC, NAICS, OpenFIGI market sector, and the Weingarden/Federal Reserve GICS-NAICS concordance) and let Portfolio Performance's existing customizable "Taxonomies" feature hold the sector view, while CFI drives the asset-class/instrument-type taxonomy.

## Key Findings

### Licensing -- the unambiguous bottom line

| Taxonomy | Owner | Commercial software / redistribution | Personal / open-source use | Paid license required? |
|---|---|---|---|---|
| **GICS** | MSCI + S&P Dow Jones Indices (joint) | **License required** from S&P DJI/MSCI to display, create derivative works of, or distribute | Free only for individual viewing on already-licensed terminals (e.g., Bloomberg); no free redistribution | **YES** (GICS Direct, priced by client type/size) |
| **TRBC** | LSEG (formerly Refinitiv/Thomson Reuters) | **License required** -- proprietary, delivered via paid LSEG data products | No free/open redistribution license | **YES** (LSEG data subscription) |
| **CFI** | ISO (ISO 10962); SIX = Maintenance Agency; ANNA/NNAs assign codes | **Free** -- code list published free; usable/redistributable in software (no named open-data license; contact <office@cfi-iso.org> before embedding in a distributed app) | **Free** | **NO** -- only the ISO standard *document* PDF costs money (CHF 65) |

The critical distinction for CFI: **the ISO 10962 standard document is copyrighted and sold by ISO, but the actual CFI code set (categories, groups, attributes) was deliberately externalized in the 2021 edition and is published free by SIX Group** (the ISO-appointed Maintenance Agency). Per the ISO 10962:2021 standard text: "The CFI external code list is published in a selection of human-readable and machine-readable data formats [e.g. spreadsheet, PDF, comma-separated values (CSV), JSON-LD, TTL]... The CFI code list has been removed from the specification and moved to an external code list." ISO designed this externalization specifically to allow more timely, open updating of the code values. The ISO product page lists ISO 10962:2021 (Edition 5, published 2021-05-18, only 9 pages) at **CHF 65** (verified 2026-06-20 via multiple standards resellers) -- note this is the *document*, not the code list. National Numbering Agencies (ANNA members) also assign CFI codes to instruments free of charge alongside ISINs at issuance ("The majority of NNAs do not charge for ISIN allocation... The same applies for CFI"). So you can freely use and embed CFI codes and their meanings without buying anything. **Important caveat**: SIX does not attach a named open-data license (CC0, CC-BY) to the downloadable Excel/CSV/JSON-LD/TTL files; if you need a hard redistribution clause before embedding the code list in a distributed application, contact SIX directly at <office@cfi-iso.org> (verified 2026-06-20).

For **GICS**, S&P explicitly states: "A license is required from S&P DJI to display, create derivative works of and/or distribute any product or service that uses, is based upon and/or refers to any S&P DJI and/or index data," and the Information "may not be used to create derivative works... databases... risk models, analytics, software." MSCI's GICS material carries identical restrictions. The subscriber product, GICS Direct (a database of 50,000+ active companies with their GICS codes, jointly run by S&P Financial Services LLC and MSCI), is "priced based on client type and size." For an open-source solo project, embedding GICS data is a real licensing risk. The redistribution prohibition is also confirmed in third-party GICS license terms (e.g., Octus/Reorg): "agree not to redistribute the GICS Service in any form or manner to any third party" (verified 2026-06-20).

For **TRBC**, it is "owned and operated" by LSEG and delivered through paid LSEG products (Workspace, Datastream, Data Library); there is no free redistribution license.

### Ownership (all confirmed)

- **GICS**: Jointly developed (1999) and owned by **MSCI and S&P Dow Jones Indices** (S&P Global). Governance is via a joint GICS Operations Committee with members from both firms. "GICS" is a registered trademark of S&P Global/McGraw Hill Financial and MSCI Inc.
- **TRBC**: Currently owned and maintained by **LSEG (London Stock Exchange Group)**. Lineage: Reuters Business Sector Scheme (RBSS, 2004) → Thomson Reuters Business Classification (2008) → The Refinitiv Business Classification (2020) → LSEG after it acquired Refinitiv (sale closed January 29, 2021, per Thomson Reuters' SEC 6-K). The "TRBC" name was retained.
- **CFI**: The **ISO 10962** standard, current edition **ISO 10962:2021**. Developed under ISO/TC 68. **SIX Financial Information** (on behalf of the Swiss standards body SNV) is the ISO-appointed **Maintenance Agency**; **ANNA (Association of National Numbering Agencies)** and its member National Numbering Agencies assign CFI codes. The 2015 expansion was led by ANNA's Emma Kalliomaki.

### Hierarchy structure

**GICS -- 4 tiers (current, effective close of March 17, 2023):**

- **11 Sectors → 25 Industry Groups → 74 Industries → 163 Sub-Industries**
- 8-digit numeric code; classification assigned at company level (then propagated to that company's equity securities, ADRs, GDRs)
- (The prior September-2018 structure had 11/24/69/158; many secondary sources still cite the old numbers.)

**TRBC -- 5 levels (current TRBC 2020 schema):**

- Economic Sectors → Business Sectors → Industry Groups → Industries → Activities
- **Authoritative count (2020 schema): 10 economic sectors / 33 business sectors / 62 industry groups / 154 industries / 898 activities** (per Wikipedia's TRBC article and the classification.codes directory, verified 2026-06-20). Secondary sources conflict: Fidelity gives "13 economic sectors, 32 business sectors, 61 industry groups, 153 industries, and 895 activities"; AnalystPrep (CFA curriculum) gives "14 economic sectors, 33 business sectors, 154 industries, and 898 sub-sectors." The "13" or "14" economic sector counts likely reflect a different version or a different counting methodology (e.g., including cross-sector groupings). The older TRBC 2012 schema (10/28/54/136/837) is still quoted widely. Treat any secondary-source TRBC count as approximate; use 10/33/62/154/898 as the primary 2020 figure.
- Hierarchical numeric IDs; company assigned to an Activity/Industry, with higher levels derived.

**CFI -- 6-character alphabetic code (ISO 10962):**

- Character 1 = **Category**: ISO 10962:2021 defines **14 categories** (verified 2026-06-20): E=Equity, C=Collective Investment Vehicles, D=Debt, R=Entitlements/rights, O=Listed Options, F=Futures, S=Swaps, H=Non-listed and complex listed options, I=Spot, J=Forwards, K=Strategies, L=Financing, T=Referential instruments, M=Others/Miscellaneous. Categories H, I, J, K, L, T, M were added in the 2019/2021 revisions; any CFI-consuming implementation must handle all 14.
- Character 2 = **Group** within the category (e.g., common/ordinary shares, preferred shares, bonds, money-market instruments, ETFs, standard funds)
- Characters 3--6 = four **Attributes** specific to that group (for shares: voting right, ownership/restrictions, payment status, form; for bonds: interest type, guarantee, redemption, form)
- "X" = not applicable/unknown. A typical registered (common/ordinary) share is represented as **ESVUFR** (R=Registered form); a worked debt example is **DBFUGR** = a fixed-rate, unsecured, callable, registered bond.

### Security types covered

- **GICS**: Equities/companies only. Per the MSCI GICS Methodology: "GICS is not assigned to supranationals, municipals, sovereigns, shell companies, mutual funds, or..." MSCI does provide a fixed-income guideline that propagates a company's GICS to its bonds, but GICS is fundamentally a company/equity taxonomy -- it does not classify ETFs, options, or funds as instrument *types*.
- **TRBC**: Company/equity classification (covers public companies, and per some sources private companies, non-profits, government entities -- hence its extra "Government Activity," "Academic & Educational Services," and "Institutions, Associations & Organizations" sectors). Like GICS, it classifies the *business*, not the instrument type.
- **CFI**: **All financial instrument types** -- equities, debt, collective investment vehicles (funds/ETFs), listed options, futures, swaps, forwards, entitlements/warrants, structured products, financing, referential instruments, and (added in the 2019/2021 revisions) OTC derivatives. This is the only one of the three that answers "what *kind* of instrument is this?"

**This is the crux: GICS/TRBC answer "what sector is this company in?"; CFI answers "what type of instrument is this?" They are complementary, not substitutes.**

### How Portfolio Performance handles taxonomies (integration grounding)

Portfolio Performance ships several predefined, fully customizable "Taxonomies" templates, including:

- **Asset Classes**: Cash, Equity, Debt, Real Estate, Commodity
- **Type of Security**: Stock, Equity Fund, Exchange Traded Fund (ETF), Bond, Stock Option, Index, Currency
- **Industries (GICS, Sectors)**: a GICS *sectors* template (the 11 top-level sectors)
- **Regions** and **Regions (MSCI)**

Every taxonomy is user-editable (add/delete categories via context menu), securities are assigned manually (drag-and-drop or via the security's "Taxonomies" edit tab), a security can belong to multiple taxonomies, and weights can be split across categories. The underlying file is XML; the format the mobile app reads is "binary." A community Python tool (`pp-portfolio-classifier`) already auto-populates PP taxonomies (asset class, sector, region, country) by pulling fund/ETF holdings data (largely Morningstar/Yahoo) -- the closest existing analog to your planned wrapper. Importantly, PP's built-in "Industries (GICS, Sectors)" template uses only the GICS *sector names/structure* (the 11 framework labels), not redistributed GICS company-assignment data -- a useful precedent for what is safe to ship.

### Open / free data sources for sector-style classification

| Source | What it gives | License / terms caveat |
|---|---|---|
| **SEC EDGAR SIC codes** | Each US filer's primary SIC code; free bulk + REST APIs | US government public data, free; SIC is coarse and dated (last revised 1987), US-only |
| **NAICS** | 6-digit industry codes; free from US Census | Public domain; US public companies don't file NAICS with the SEC, so requires a crosswalk |
| **MSCI GICS structural docs** | Sector definitions, methodology PDF, GICS structure XLSX | Some free structural documents confirmed available; specific GICS↔NAICS/ISIC/NACE crosswalk files not confirmed at currently accessible primary URLs (unverified for current availability as of 2026-06-20) |
| **Weingarden/Federal Reserve GICS-NAICS concordance** | Many-to-many mapping: 144 GICS sub-industries ↔ 989 NAICS industries | Freely available; confirmed 2026-06-20 |
| **OpenFIGI (Bloomberg)** | FIGI identifiers + `marketSector` (Equity, Corp, Govt, Mtge, Muni, Pfd, Comdty, Index, Curncy, Money Market) and `securityType` | **Free, public-domain dedicated, no usage restrictions** (verified 2026-06-20): Bloomberg has dedicated FIGI identifiers and associated metadata to the public domain -- "may be freely reproduced, distributed, transmitted, used, modified, built upon, or otherwise exploited by anyone for any purpose, commercial or non-commercial." The MIT label refers to the ASC X9.145 standard *document* wrapper, not the data itself. Unauthenticated API requests are capped at ~25/min; a free API key (registration at <https://www.openfigi.com/api>) unlocks higher limits for bulk ISIN lookups. Not a GICS-style industry sector source. |
| **Financial Modeling Prep (FMP)** | `sector` and `industry` fields per company; free tier | Free tier exists, but "Displaying or redistributing data sourced from FMP requires a specific Data Display and Licensing Agreement"; free plan capped at 500 MB / 30-day bandwidth |
| **yfinance / Yahoo Finance** | `sector`/`industry` per ticker | Unofficial library; Yahoo ToS prohibits automated access/redistribution. Per industry guidance: "Personal and internal research use carries low enforcement risk. Commercial applications that redistribute scraped data... carry meaningfully higher exposure" |
| **ICB (FTSE Russell)** | 4-tier sector benchmark (11 industries / 20 supersectors / 45 sectors / 173 subsectors) | **Also proprietary/licensed** (LSEG/FTSE Russell): "Use and distribution of the LSE Group data requires a licence" -- not a free alternative |
| **Community datasets (GitHub, Wikidata; `pycfi`)** | Various sector mappings; `pycfi` decodes CFI codes across ISO 10962 categories | Variable licenses -- verify each; Wikidata is CC0 but coverage/accuracy is uneven; `pycfi` and `cfi-decoder` are both April 2026 releases and unproven in production (see Caveats) |

Key takeaway: **OpenFIGI is the best truly-free, redistributable (public-domain) source for instrument-type / market-sector data, and it complements CFI well.** For GICS-style *industry* sectors there is no fully free, redistributable, GICS-equivalent dataset -- the closest legal path is SIC/NAICS (free, public) optionally bridged toward GICS sector labels via the Weingarden/Federal Reserve concordance, or letting end users pull their own sector field from FMP/Yahoo under those services' terms.

### Mapping between taxonomies

- **CFI as canonical instrument-type spine + a separate sector taxonomy for equities** is the clean architecture. CFI tells you it's an equity/bond/fund/option; the sector taxonomy (SIC/NAICS/GICS-sector) only needs to be populated for the equity (and equity-fund) subset.
- **Published crosswalks**: MSCI's GICS resource page confirms some free structural documents (sector definitions, methodology PDF, GICS structure XLSX). MSCI GICS↔NAICS (2017), GICS↔ISIC rev. 4, and GICS↔NACE rev. 2 crosswalk files were not confirmed available at currently accessible primary URLs as of 2026-06-20 -- they may require login or may have been removed; treat as **unverified for current availability**. The US Census publishes SIC↔NAICS↔ISIC↔NACE concordances (public domain). The **Alison Weingarden (Federal Reserve) many-to-many GICS/NAICS concordance** (144 GICS sub-industries mapped to 989 NAICS industries) is freely available and is a reliable confirmed substitute. Commercial vendors (classification.codes; S&P's ISCRS) sell GICS/TRBC/ICB crosswalks. TRBC ships "crosswalk tables to over 50 different industry classifications," but those are LSEG-licensed.
- **Practical free chain**: SIC (from EDGAR, free) → NAICS (Census crosswalk, free) → GICS *sector* (Weingarden/Federal Reserve GICS-NAICS concordance, freely available) yields a defensible, fully-free approximate sector for US equities without touching licensed GICS company data.

## Details / Recommendation rationale

The decision hinges on three axes: **licensing risk, completeness across instrument types, and intuitiveness for sector analysis.**

1. **Licensing risk.** For an open-source project that ships/redistributes data, GICS and TRBC are disqualified as *embedded canonical data*: both require negotiated commercial licenses and carry explicit anti-redistribution / anti-derivative-works clauses. CFI carries none of this -- the code list is free, and ISO designed the 2021 externalization specifically to make the code set openly distributable.

2. **Completeness.** A portfolio app holds stocks, ETFs, funds, bonds, options, possibly crypto. Only CFI natively classifies *all* of these by instrument type. GICS/TRBC simply do not model "this is an ETF vs. a bond vs. an option." So even if licensing were free, GICS/TRBC could not serve as a single canonical model for a multi-asset portfolio.

3. **Intuitiveness.** CFI's weakness: it is not built for sector/industry analysis (no "Technology vs. Healthcare" axis), and its 6-letter codes are opaque to end users. GICS sectors are the market-standard mental model investors expect. This is why the recommended design is **two complementary taxonomies**, mirroring how Portfolio Performance itself already separates "Type of Security"/"Asset Classes" from "Industries (GICS, Sectors)."

## Recommendations (staged)

1. **Adopt CFI (ISO 10962:2021) as the canonical instrument-type / asset-class model.**
   - Ingest the free SIX code list (Excel/CSV/JSON-LD/TTL) as your reference data. The publicly accessible direct download is the SIX-hosted Excel file (check <https://www.six-group.com/en/products-services/financial-information/market-reference-data/data-standards.html> for the current file; the 2021-05-07 version is publicly indexed). **Before embedding the code list in a distributed app, contact SIX at <office@cfi-iso.org> to obtain written redistribution confirmation** -- no named open-data license is attached to the file.
   - Use a library like `pycfi` (MIT, GitHub: FinTechFelix/pycfi) to decode codes into human-readable category/group/attributes. **Caveat**: both `pycfi` and the alternative `cfi-decoder` (GPL-3.0, PyPI) were first released April 2026 and are unproven in production. Verify which ISO 10962 edition each covers (2015 vs. 2021, specifically whether all 14 categories are supported) before relying on either. Note that `cfi-decoder`'s GPL-3.0 license may impose copyleft obligations on linking code; confirm with legal counsel if that library is chosen.
   - Map CFI Category → PP's "Asset Classes" (E→Equity, D→Debt, C→funds, etc.) and "Type of Security" templates so the wrapper writes directly into PP's existing taxonomies.
   - Prefer the official CFI assigned by the NNA alongside the ISIN where available; otherwise derive an ISO-compliant CFI from the free code list (note there is no Registration Authority for CFI, so self-derived codes are valid but only NNA-issued ones are "official").

2. **Add a separate, optional "Sector" taxonomy for equities using only free/redistributable data.**
   - Primary free path: SEC EDGAR SIC (free, public) → optionally bridge to NAICS / GICS-sector via the Weingarden/Federal Reserve concordance for a GICS-*style* label. Store the GICS sector *names* (which PP already ships) but populate assignments from free sources, never from licensed GICS data.
   - Use **OpenFIGI** (free, public-domain dedicated) to enrich identifiers and market-sector/instrument metadata -- it pairs naturally with CFI. Obtain a free API key at <https://www.openfigi.com/api> to unlock higher rate limits needed for bulk lookups.

3. **Treat GICS / TRBC / ICB as "bring-your-own-license" optional integrations, not bundled data.**
   - If a user has their own GICS/TRBC entitlement (via a broker or terminal), let them import it; never ship the licensed data in the repository.

4. **For per-user sector enrichment, surface FMP/Yahoo as user-configurable sources with explicit terms warnings**, exactly as the existing `pp-portfolio-classifier` does -- keeping legal responsibility with the end user and out of your redistributed codebase.

**Thresholds that would change this recommendation:**

- You obtain a free/affordable GICS or TRBC redistribution license → add GICS sectors as first-class canonical sector data.
- The app becomes equities-only and never handles bonds/options/funds → CFI's instrument-type advantage shrinks, and a pure free-sector approach (SIC/NAICS) could suffice.
- A fully-free, redistributable GICS-equivalent sector dataset emerges (e.g., a well-maintained CC0 community mapping) → prefer it over the SIC/NAICS bridge for richer sectoring.

## Caveats

- **Structure counts drift.** GICS is reviewed annually and TRBC periodically; secondary sources frequently cite outdated counts (GICS 11/24/69/158 from 2018; TRBC 10/28/54/136/837 from the 2012 schema). Current vs. legacy are flagged above, but verify the live structure files at integration time.
- **TRBC 2020 authoritative count is 10/33/62/154/898** (Wikipedia/classification.codes, verified 2026-06-20). Secondary sources (Fidelity: 13 economic sectors, 895 activities; AnalystPrep: 14 economic sectors, 898 activities) diverge and likely reflect a different version or counting methodology. Treat any secondary-source TRBC count as approximate; use 10/33/62/154/898 as the primary 2020 figure.
- **CFI "free" nuance**: the code list is free to use and SIX publishes it openly, but SIX does not attach a *named* open-data license (e.g., CC-BY) to the CFI list specifically; free redistribution is supported by ISO's deliberate externalization and the agency's free-of-charge mandate (stated verbatim for its sister ISO 4217 currency codes) rather than an explicit per-file license grant. **This is a real legal grey area for distributed software.** If you need a hard redistribution clause, contact SIX at <office@cfi-iso.org> before embedding the code list. The ISO *standard document* remains copyrighted (CHF 65, Edition 5, published 2021-05-18, 9 pages).
- **CFI has 14 categories in ISO 10962:2021**, not the 7 most commonly referenced. Implementations must handle E, C, D, R, O, F, S, H, I, J, K, L, T, M (verified 2026-06-20).
- **pycfi and cfi-decoder are brand-new (April 2026) and unproven.** Neither has confirmed full ISO 10962:2021 (14-category) coverage. `cfi-decoder` is GPL-3.0, which may impose copyleft on linking code. Verify before adopting either as a production dependency.
- **MSCI free GICS crosswalk availability is unverified** for current access (as of 2026-06-20). The Weingarden/Federal Reserve GICS-NAICS concordance is a confirmed free alternative.
- **OpenFIGI is not a sector taxonomy.** Its `marketSector` is asset-class-level (Equity, Corp, Govt, etc.), not industry sectors -- do not mistake it for a GICS substitute.
- **"Free tier" is not "free to redistribute."** FMP and Yahoo both restrict redistribution; their sector data is fine for personal use but should not be baked into a distributed open-source dataset.
- This analysis assumes **redistribution inside a distributed application**. Pure personal, local, non-redistributed use of any of these (even scraped Yahoo sectors) carries materially lower practical risk -- but that is a use-policy judgment, not a license grant.

## Still unverified / open questions

1. **MSCI free GICS-to-NAICS/ISIC/NACE crosswalk files**: The original report asserted MSCI publishes "free GICS↔NAICS (2017), GICS↔ISIC rev. 4, and GICS↔NACE rev. 2 conversion tables." No live primary URL was verified for currently accessible free downloads of these specific files as of 2026-06-20. The Weingarden/Federal Reserve GICS-NAICS concordance is a confirmed free substitute for the NAICS mapping.

2. **GICS "individual terminal viewing" carve-out**: The report states GICS is "Free only for individual viewing on already-licensed terminals (e.g., Bloomberg)." No primary S&P/MSCI license document confirmed this exact carve-out language verbatim. The conclusion (no free redistribution license) is confirmed; the specific "terminal viewing" exception wording is unverified.

3. **TRBC-specific license page**: No LSEG page specifically titled "TRBC Licensing Terms" was fetchable. The conclusion that TRBC requires a paid LSEG subscription is consistent with all available evidence (LSEG's general data policy, TRBC's "Commercial" classification on classification.codes, absence of any free redistribution option), but was confirmed via general LSEG data policy and secondary sources rather than a TRBC-specific terms document.

4. **PP's internal use of GICS sector names**: The claim that Portfolio Performance ships GICS sector labels in its built-in taxonomy without redistributing company-assignment data was not verified from PP source code or official documentation. It is architecturally plausible and consistent with the PP open-source codebase, but a definitive check of the PP XML taxonomy file would be needed to confirm.

5. **SIX CFI code list explicit redistribution terms (decision-relevant)**: No named open-data license (CC0, CC-BY) was found attached to SIX's CFI Excel/CSV downloads. The "free to redistribute" claim rests on inference from ISO design intent and analogy to ISO 4217, not on a confirmed explicit license grant. **Before embedding the CFI code list in a distributed application, contact <office@cfi-iso.org> to obtain written permission.** This is the highest-priority open item for the project's legal posture.

6. **pycfi and cfi-decoder ISO 10962:2021 coverage**: It is unconfirmed whether either library covers all 14 categories of ISO 10962:2021 or only the original 2015 edition categories. Verify before relying on either for instrument types beyond the traditional E/D/C categories.

7. **SIX CFI code list currency**: The publicly linked Excel file is timestamped 2021-05-07. Check the SIX data standards page for a newer file, as the maintenance agency model allows the code list to evolve without a full ISO standard revision.
