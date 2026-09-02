# Repository Rulesets Configuration

This document outlines the repository rulesets configuration for pp-security-master, based on successful patterns from PromptCraft.

> **Note (2026-09):** `.github/workflows/codeql.yml` and its config
> (`.github/codeql/codeql-config.yml`) were removed: GitHub now bills
> Advanced Security / Code Security, so CodeQL code scanning and SARIF
> ingestion into the Security tab no longer function. Every reference to
> `CodeQL Security Analysis / Analyze (python)` below is stale. Live
> required status checks (verified via `gh api
> repos/ByronWilliamsCPA/pp-security-master/branches/main/protection`) are
> `CI Gate`, `Security Gate Validation`, `Dependency & Standards
> Validation`, and `Check REUSE Compliance`; CodeQL was not among them, so
> this removal does not block merges. This document also predates the
> current CI setup in other respects (it still describes Poetry and
> PostgreSQL integration tests); a full refresh is out of scope for this
> change.

## Current Ruleset Requirements

### Branch Protection (Main Branch)

The `main` branch is protected with the following requirements:

#### Required Status Checks

- **CI / CI Success** - Full CI pipeline must pass
- **CodeQL Security Analysis / Analyze (python)** - Security analysis must complete successfully

#### Branch Protection Rules

- ✅ Require branches to be up to date before merging
- ✅ Require status checks to pass before merging
- ✅ Require conversation resolution before merging
- ✅ Restrict pushes that create files larger than 100MB
- ❌ Allow force pushes (disabled for safety)
- ❌ Allow deletions (disabled for safety)

### Workflow Requirements

#### CI Pipeline (`ci.yml`)

Must complete successfully with all jobs passing:

- **Setup Dependencies** - Poetry installation and caching
- **Unit Tests** - Python 3.11 and 3.12 matrix
- **Integration Tests** - With PostgreSQL 17 service
- **Quality Checks** - Linting, formatting, type checking
- **Security Scan** - Bandit and safety checks (continue-on-error)

#### CodeQL Analysis (`codeql.yml`)

Must complete security analysis:

- **Language**: Python
- **Queries**: Security and quality focused
- **Configuration**: Custom config at `.github/codeql/codeql-config.yml`
- **Triggers**: Push to main, PRs to main, weekly schedule

## Configuration Steps

### 1. Repository Settings

1. Navigate to **Repository Settings** → **Rules** → **Rulesets**
2. Create **"Main Branch Protection"** ruleset
3. Set enforcement to **Active**
4. Configure required status checks (exact names above)

### 2. Status Check Names

Ensure these exact names are configured in rulesets:

```text
CI / CI Success
CodeQL Security Analysis / Analyze (python)
```

### 3. Troubleshooting

#### CodeQL Failures

- Check that autobuild can detect Python project structure
- Verify `.github/codeql/codeql-config.yml` is valid
- Ensure `src` directory contains Python files
- Check workflow permissions include `security-events: write`

#### CI Failures

- Verify Poetry and Python 3.11/3.12 compatibility
- Check PostgreSQL service availability for integration tests
- Ensure all required environment variables are set
- Review test markers and pytest configuration

## Integration with PromptCraft Patterns

This configuration follows successful patterns from [PromptCraft](https://github.com/williaby/PromptCraft):

### Similarities

- Simple CodeQL configuration without complex dependencies
- Required status checks for main branch protection
- Security-focused analysis with quality checks
- Weekly scheduled security scans

### Adaptations for Python

- Added Python-specific build detection
- Included Poetry dependency management awareness
- PostgreSQL integration testing requirements
- Multiple Python version matrix testing

## Maintenance

### Regular Updates

- Review and update required status check names if workflows change
- Monitor CodeQL query updates for new security rules
- Adjust branch protection settings as team grows
- Update documentation when adding new required checks

### Security Considerations

- CodeQL configuration focuses on security and quality
- All security scans are required before merge
- Dependency updates through Renovate are automatically merged when tests pass
- Security issues are reported through GitHub Security tab
