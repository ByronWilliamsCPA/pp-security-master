# Known Vulnerabilities

Unfixed CVEs are documented here per the global unfixed-CVE policy.
No entry may age past 60 days without reassessment. Review at least every 60 days.

**Last full reassessment:** 2026-06-19. `uv run pip-audit` reports no known
vulnerabilities in the project environment as of this date. Next review due by
2026-08-18.

## Active accepted vulnerabilities

These are not surfaced by `pip-audit` as of the 2026-06-19 reassessment; they are
retained because the affected packages are tooling/transitive and cannot be pinned
through `pyproject.toml`. The `noxfile.py` security session keeps matching
`--ignore-vuln` entries as a defensive guard should the advisory feed resurface them.

| CVE | Package | Severity | Introduced | Last Reviewed | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| GHSA-4xh5-x5gv-qwph | pip 25.2 | Medium | 2026-04-23 | 2026-06-19 | Accepted | pip is a transitive tooling dependency (via pip-api), not a project dependency. pip 25.2 is the latest version the resolver selects; the announced fix (pip 25.3) is not yet resolvable. Upgrade at the next environment refresh once available. |
| GHSA-6vgw-5pg2-w6jp | pip 25.2 | Medium | 2026-04-23 | 2026-06-19 | Accepted | As above; announced fix is pip 26.0, not yet resolvable. |
| GHSA-58qw-9mgm-455v | pip 25.2 | Medium | 2026-04-29 | 2026-06-19 | Accepted | uv migration completed 2026-06-19; pip remains a transitive tooling dependency (via pip-api), not project-controlled. No longer surfaced by pip-audit. |
| PYSEC-2022-42969 | py 1.11.0 | Medium | 2026-04-23 | 2026-06-19 | Accepted | Transitive via interrogate 1.7.0. The ReDoS is in `py.path.svnwc`, which interrogate does not invoke. The `py` library is abandoned; no upstream fix. Reassess if interrogate drops the `py` dependency. |

## Resolved at the 2026-06-19 reassessment

These were newly surfaced by `pip-audit` during reassessment and fixed by upgrading
to the patched versions (landed via dependency PR #57):

| CVE | Package | Resolution |
| --- | --- | --- |
| GHSA-6v7p-g79w-8964 | msgpack 1.1.2 | Upgraded to 1.2.1 (transitive via cachecontrol). |
| GHSA-4xgf-cpjx-pc3j | pydantic-settings 2.14.1 | Upgraded to 2.14.2 (direct dependency). |
