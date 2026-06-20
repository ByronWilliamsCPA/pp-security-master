# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this repository,
**please do not open a public issue**.
Instead, report it privately using GitHub's Private Vulnerability Reporting feature:
[Report a vulnerability](https://github.com/ByronWilliamsCPA/pp-security-master/security/advisories/new) <!-- pragma: allowlist secret -->

Fill in the details and submit. All reports are kept confidential.

For urgent matters, you may also contact <byronawilliams@gmail.com>.

## Response Timeline

We commit to acknowledging all vulnerability reports within 14 days of submission
(typically within 5 business days).

- **Acknowledgment:** within 5 business days (no later than 14 days)
- **Fix released:** within 30 days of acknowledgment
- **Emergency patch:** sooner for critical severity

## Supported Versions

This project is currently pre-release. Only the latest commit on `main` receives
security fixes.

| Version  | Status       |
|----------|--------------|
| main     | Supported    |
| older    | Not supported |

## Security Surface

This repository contains a security-master service for Portfolio Performance: a
Python application that parses broker-supplied XML and CSV files, classifies
securities via external APIs (OpenFIGI), and persists results in PostgreSQL 17.

Primary security concerns and mitigations:

- **XML/broker-file parsing (supply-chain injection):** All XML parsing uses
  `defusedxml`; entity expansion and external DTD loading are disabled by default.
- **SQL injection:** All database access uses SQLAlchemy ORM with parameterized
  queries; raw SQL is prohibited in production code paths.
- **Supply-chain attacks via dependencies:** Dependencies are pinned via `uv.lock`;
  GitHub Actions are SHA-pinned; Renovate manages automated dependency updates.
- **Credential exposure:** Secrets (API keys, database credentials) are loaded
  exclusively from environment variables. Secret scanning is active on every push
  via GitGuardian and GitHub secret scanning.
- **Dependency CVEs:** `pip-audit` runs on every CI build. Accepted exceptions are
  documented in `docs/known-vulnerabilities.md` with a 60-day reassessment deadline.
- **Prompt injection (LLM tooling):** Agent tooling treats external file content and
  GitHub issue bodies as untrusted data per OWASP LLM01 guidance.

## Security Practices

- **Static Analysis** with CodeQL, Ruff, and Bandit
- **Dependency Scanning** with pip-audit on every CI run
- **Secrets Detection** with GitGuardian and GitHub secret scanning on every push
- **Pinned GitHub Actions** using immutable commit SHAs

## CVE and Advisory Workflow

1. **Request a CVE** for issues rated Moderate or above.
2. **Draft and publish an advisory** in the Security tab.
3. **Document in** `docs/known-vulnerabilities.md` until resolved.
4. **Include remediation steps** in release notes.

## Disclosure Policy

We follow coordinated disclosure principles. Once a fix is available, we will
publish details in our Security Advisories page. If you wish to receive credit
for responsibly disclosing a vulnerability, please let us know; otherwise
credit will be anonymous.

Last updated: 2026-06-19
