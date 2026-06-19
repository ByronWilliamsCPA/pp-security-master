# Design: Global Standards Alignment

**Date**: 2026-04-20
**Status**: Approved
**Author**: Byron Williams

---

## Background

The `pp-security-master` project was initialized before several global standards in
`~/.claude/CLAUDE.md` and `~/.claude/.claude/rules/` solidified. This document
catalogues the ~35 gaps found in an April 2026 audit and specifies exactly what to
change in each of six dependency-ordered phases.

The audit compared the project against:

- Global `~/.claude/CLAUDE.md` (v1.4.0, 2026-04-19)
- `~/.claude/.claude/rules/python.md` (toolchain, type checking, linting)
- `~/.claude/.claude/rules/git-workflow.md` (SHA pinning, pre-commit, branch rules)
- `~/.claude/.claude/rules/writing.md` (em-dash ban, AI pattern blacklist)
- `~/.claude/.claude/standards/packages.md` (canonical packages, qlty)
- `/home/byron/dev/.github/README.md` (org-level reusable workflows)

---

## Approach

Six dependency-ordered phases. Each phase produces a working, committable state
before the next phase starts. The ordering ensures no phase calls a tool or file
that does not yet exist.

| Phase | Name | Scope |
|-------|------|-------|
| 0 | Project Root Relocation | Move project from nested path to correct location |
| 1 | Foundations | Missing files, metadata fixes |
| 2 | Toolchain Replacements | Black/MyPy/safety out; Ruff format/BasedPyright/pip-audit in |
| 3 | Pre-commit | Wire Phase 2 tools into `.pre-commit-config.yaml` |
| 4 | CI Modernization | Migrate to org reusable workflows, pin SHAs, add hardening |
| 5 | `.claude/` and Docs Cleanup | Settings, CLAUDE.md updates, em-dash scan |

---

## Phase 0: Project Root Relocation

The project is nested one directory too deep. All files live at
`/home/byron/dev/pp-security-master/pp-security-master/` when the correct root
is `/home/byron/dev/pp-security-master/`. The outer directory contains only the
inner one (confirmed at audit time), so no content conflicts exist.

This phase must run before any other phase because subsequent phases create files
at paths relative to the project root. Doing that work before the relocation would
require redoing path references afterward.

### Steps

1. Open a terminal at `/home/byron/dev/pp-security-master/` (the outer directory).

2. Move all contents (including hidden files and directories) out of the inner
   directory and into the outer:

   ```bash
   # From /home/byron/dev/pp-security-master/
   mv pp-security-master/{.,}* . 2>/dev/null || true
   ```

   If the glob approach causes issues with dotfiles, move explicitly:

   ```bash
   mv pp-security-master/.git .
   mv pp-security-master/.github .
   mv pp-security-master/.claude .
   mv pp-security-master/.gitignore .
   mv pp-security-master/.editorconfig .
   mv pp-security-master/.dockerignore .
   mv pp-security-master/.env.example .
   mv pp-security-master/.gemini.json .
   mv pp-security-master/.vscode .
   mv pp-security-master/.yamllint.yml .
   # Then move all non-hidden items
   mv pp-security-master/* .
   ```

3. Remove the now-empty inner directory:

   ```bash
   rmdir pp-security-master
   ```

4. Update the VSCode workspace path if `.vscode/` contains any absolute paths
   referencing the old nested location.

5. Verify git still works from the new root:

   ```bash
   git status
   git log --oneline -3
   ```

6. Close and reopen any IDE windows pointing to the old path, then re-open from
   `/home/byron/dev/pp-security-master/`.

### Verification

- `git status` exits cleanly from `/home/byron/dev/pp-security-master/`
- `ls CLAUDE.md README.md pyproject.toml` returns all three files
- The inner `pp-security-master/` directory no longer exists
- No absolute paths in `.vscode/`, `pyproject.toml`, or `Makefile` reference
  the old nested path

---

## Phase 1: Foundations

### OpenSSF Required Files (project root)

The global standard requires `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`,
`CHANGELOG.md`, and `README.md` in every project. The project has `LICENSE` and
`README.md`. Three are missing.

| File | Action | Source |
|------|--------|--------|
| `SECURITY.md` | Create from org template at `/home/byron/dev/.github/SECURITY.md` | Copy and adapt |
| `CONTRIBUTING.md` | Create from org template at `/home/byron/dev/.github/CONTRIBUTING.md` | Copy and adapt |
| `CHANGELOG.md` | Create with Keep a Changelog v1.0.0 header, `## [Unreleased]` section | New file |
| `CODEOWNERS` | Create at `.github/CODEOWNERS`, assign `@williaby` as default owner | New file |

### `.gitignore` Additions

The git workflow rule requires `.worktrees/` in `.gitignore`. It is absent.

```text
.worktrees/
```

### `pyproject.toml` Metadata Fixes

| Field | Current | Target |
|-------|---------|--------|
| `authors[0].email` | `byron@example.com` | `byronawilliams@gmail.com` |
| `requires-python` | `>=3.11,<3.13` | `>=3.11,<3.15` |
| `python` (Poetry dep) | `>=3.11,<3.13` | `>=3.11,<3.15` |

The 3.11 minimum stays (the project uses 3.11 features). The upper bound
extends to `<3.15` to align with the global standard's 3.10-3.14 support range.

### New Project Docs

| File | Contents |
|------|----------|
| `docs/known-vulnerabilities.md` | Create with a header and empty table: columns `CVE`, `Package`, `Severity`, `Introduced`, `Last Reviewed`, `Status`, `Notes` |
| `docs/superpowers/` | Already created when this spec was written -- no further action needed |

### `CLAUDE.md` Phase 1 Additions

- `## Package Overrides` section noting `poetry` is grandfathered (project predates
  the `uv` standard; no migration required until a future major rework)
- Cross-reference pointers to the global rule files that govern this project:
  `~/.claude/.claude/rules/python.md`, `git-workflow.md`, `pre-commit.md`,
  `testing.md`, `writing.md`

---

## Phase 2: Toolchain Replacements

### Black out, Ruff format in

`black = "24.10.0"` is removed from `[tool.poetry.group.dev.dependencies]`.
Ruff's formatter replaces it. Ruff is already present at `0.12.3`.

Changes required:

- Add `[tool.ruff.format]` block to `pyproject.toml`
- Replace every `black` invocation in `noxfile.py` and `Makefile` with `ruff format`
- Update `CLAUDE.md` Essential Commands to reference `ruff format .`

### MyPy out, BasedPyright in

`mypy = "1.13.0"` and its type stubs (`types-pyyaml`, `types-python-dateutil`)
are removed. BasedPyright replaces MyPy (3-5x faster, strict mode).

Changes required:

- Add `basedpyright` to dev dependencies
- Add `[tool.basedpyright]` block to `pyproject.toml`:

```toml
[tool.basedpyright]
pythonVersion = "3.11"
pythonPlatform = "All"
typeCheckingMode = "strict"
strictListInference = true
strictDictionaryInference = true
strictSetInference = true
```

- Replace `mypy src` with `basedpyright` in `noxfile.py` type-check session
- Remove `mypy` from `Makefile` and `CLAUDE.md` Essential Commands
- Resolve any new type errors BasedPyright flags that MyPy missed (expected in strict mode)

### safety out, pip-audit in

`safety` is removed. `pip-audit` replaces it per global security standard.

Changes required:

- Remove `safety` from dev dependencies
- Add `pip-audit` to dev dependencies
- Replace `poetry run safety check` in `noxfile.py` security session and `Makefile`
  with `poetry run pip-audit`
- Update `CLAUDE.md` Essential Commands

### Add darglint and interrogate

Both are required by `python.md` but absent from the project.

- Add `darglint` to dev dependencies (docstring arg/return/raises validation)
- Add `interrogate` to dev dependencies (85% docstring coverage gate in `scripts/`)
- Configure both in `pyproject.toml`:

```toml
[tool.interrogate]
ignore-init-method = true
ignore-init-module = false
ignore-magic = false
ignore-semiprivate = false
ignore-private = false
fail-under = 85
include = ["scripts/"]

[tool.darglint]
strictness = long
ignore = ["tests/", "scripts/", "benchmarks/", "noxfile.py"]
```

### qlty CLI configuration

`qlty` is the unified quality runner per `packages.md`. It is a standalone CLI,
not a Python package. The project needs a `.qlty/qlty.toml` config file.

```toml
# .qlty/qlty.toml
[plugins]
enabled = ["ruff", "basedpyright", "bandit"]
```

Add a note to `README.md` dev-setup section: install qlty with
`curl https://qlty.sh | bash` before running `qlty check`.

### Ruff rule alignment

The current `[tool.ruff.lint]` `select` list is incomplete relative to the
PyStrict-aligned rules mandated in `python.md`. Add the following rule codes that
are currently missing:

`BLE`, `EM`, `SLF`, `INP`, `ISC`, `PGH`, `RSE`, `TID`, `YTT`, `FA`, `T10`,
`G`, `ANN`, `TCH`, `FBT`, `TRY`, `ERA`, `FURB`, `LOG`, `ASYNC`

Also set:

```toml
[tool.ruff]
target-version = "py312"
```

Expect a wave of new lint violations after enabling these rules. Fix each one;
do not suppress with `# noqa` unless a vendored-code exception applies.

---

## Phase 3: Pre-commit

The project has no `.pre-commit-config.yaml`. Create it with hooks in this order:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: <pinned SHA>
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/DetachHead/basedpyright
    rev: <pinned SHA>
    hooks:
      - id: basedpyright

  - repo: https://github.com/PyCQA/bandit
    rev: <pinned SHA>
    hooks:
      - id: bandit
        args: [-r, src, -ll]

  - repo: https://github.com/Yelp/detect-secrets
    rev: <pinned SHA>
    hooks:
      - id: detect-secrets

  - repo: https://github.com/terrencepreilly/darglint
    rev: <pinned SHA>
    hooks:
      - id: darglint

  - repo: https://github.com/econchick/interrogate
    rev: <pinned SHA>
    hooks:
      - id: interrogate
        args: [--fail-under=85, scripts/]

  - repo: https://github.com/commitizen-tools/commitizen
    rev: <pinned SHA>
    hooks:
      - id: commitizen
        stages: [commit-msg]

  - repo: https://github.com/adrienverge/yamllint
    rev: <pinned SHA>
    hooks:
      - id: yamllint

  - repo: https://github.com/igorshubovych/markdownlint-cli
    rev: <pinned SHA>
    hooks:
      - id: markdownlint

  - repo: local
    hooks:
      - id: no-em-dash
        name: No em-dashes
        language: pygrep
        entry: \u2014
        types: [text]
        description: Blocks em-dashes (global writing rule)
```

All `rev` fields show `<pinned SHA>` as a placeholder. During implementation,
resolve each SHA from the tool's releases page on GitHub and replace the placeholder
with the full 40-character hash plus a version comment. Do not commit with
placeholder text in place.

Additional wiring:

- Add `pre-commit` to dev dependencies in `pyproject.toml`
- Add `nox -s pre_commit` session: `session.run("pre-commit", "run", "--all-files")`
- Add `make pre-commit` target in `Makefile`
- Update `CLAUDE.md` Essential Commands: `poetry run pre-commit run --all-files`

---

## Phase 4: CI Modernization

### Migrate to org-level reusable workflows

The current `ci.yml` is 340 lines of inline setup duplicated across every job.
Replace with thin caller workflows that delegate to `ByronWilliamsCPA/.github`:

**`.github/workflows/ci.yml`** -- replaces the current inline file:

```yaml
jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@main
    with:
      python-versions: '["3.11", "3.12"]'
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

**`.github/workflows/security.yml`** -- new file, replaces `security-scan` job:

```yaml
jobs:
  security:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-security-analysis.yml@main
```

Note: this workflow is now blocking (no `continue-on-error`).

**`.github/workflows/sonarcloud.yml`** -- new file, adds SonarCloud integration:

```yaml
jobs:
  sonarcloud:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-sonarcloud.yml@main
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
```

**`.github/workflows/coverage.yml`** -- new file, replaces Codecov uploads with Qlty:

```yaml
jobs:
  coverage:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-qlty-coverage.yml@main
    secrets:
      QLTY_COVERAGE_TOKEN: ${{ secrets.QLTY_COVERAGE_TOKEN }}
```

The existing `codeql.yml`, `scorecard.yml`, and `renovate-auto-merge.yml` remain
but get SHA-pinned (see below).

### Pin all action SHAs

Every `uses:` reference currently uses a mutable tag. All must be replaced with
40-character commit SHAs. Affected files and actions:

| File | Actions to pin |
|------|---------------|
| `ci.yml` (post-migration caller) | Inherited from reusable workflow |
| `codeql.yml` | `actions/checkout@v4`, `github/codeql-action/init@v3`, `github/codeql-action/autobuild@v3`, `github/codeql-action/analyze@v3` |
| `scorecard.yml` | `step-security/harden-runner@v2.12`, `actions/checkout@v4`, `ossf/scorecard-action@v2.4`, `actions/upload-artifact@v4`, `github/codeql-action/upload-sarif@v3` |
| `renovate-auto-merge.yml` | `step-security/harden-runner@v2.12`, `actions/checkout@v4`, `actions/setup-python@v5`, and others |

Resolve each SHA by visiting the action's releases page on GitHub and copying the
full commit hash for the tagged version. Add the version as a comment on the same line.

Dependabot is already configured for `package-ecosystem: github-actions` in the
org-level `dependabot.yml`, which will keep these SHAs current.

### Add harden-runner to CI and CodeQL jobs

`scorecard.yml` and `renovate-auto-merge.yml` already include
`step-security/harden-runner`. The `codeql.yml` job and any remaining inline jobs
do not. Add as the first step in every job:

```yaml
- name: Harden runner
  uses: step-security/harden-runner@<SHA>  # v2.x.x
  with:
    egress-policy: audit
```

### Add `.github/copilot-instructions.md`

The git workflow rule references this file as the Copilot PR review configuration.
Create it with scope instructions: focus on business logic correctness, error
handling completeness, edge cases, concurrency issues, and security logic flaws.
Explicitly exclude style and formatting from Copilot's scope (pre-commit and
ruff handle those).

---

## Phase 5: `.claude/` and Docs Cleanup

### Project `.claude/settings.json`

Create `.claude/settings.json` with project-specific tool permissions:

```json
{
  "permissions": {
    "allow": [
      "Bash(poetry run *)",
      "Bash(nox *)",
      "Bash(pre-commit *)",
      "Bash(qlty *)",
      "Bash(pip-audit *)"
    ]
  }
}
```

Adjust the allow list based on actual tool usage patterns in this project.

### `CLAUDE.md` remaining updates

Beyond the Phase 1 additions, the project `CLAUDE.md` needs:

- `## Response-Aware Development (RAD)` section with `#CRITICAL`, `#ASSUME`,
  `#EDGE`, `#VERIFY` marker guidance (copy structure from global CLAUDE.md)
- `## Model Selection` table:

  | Task type | Model | When |
  | --- | --- | --- |
  | Architecture, planning, ADRs | Opus 4.7 | Multi-step decisions |
  | Standard development | Sonnet 4.6 | Most coding and editing |
  | Read-only exploration | Haiku 4.5 | File scanning, quick lookups |

- Fix Essential Commands: replace `black`, `mypy`, `safety check` with `ruff format`,
  `basedpyright`, `pip-audit`
- Remove any em-dashes found in the file

### Em-dash and AI pattern scan

Scan all `.md` files in `docs/`, `schema_exports/`, `.github/`, and the project
root for em-dash characters (U+2014) and replace with commas, colons, semicolons,
or restructured sentences.

In the same pass, scan formal documents for AI pattern blacklist terms from
`writing.md`: `leverage`, `seamless`, `robust`, `comprehensive`, `holistic`,
`crucial`, `pivotal`, `vital`, and related terms. Replace with specific,
measurable language.

### AGENTS.md and GEMINI.md relocation

Both files currently live at `docs/project/AGENTS.md` and `docs/project/GEMINI.md`.
Agent runners and Gemini CLI expect them at the project root. Relocate both files
to the root and remove the originals. Update any internal cross-references.

---

## Gap Summary

| # | Gap | Phase |
|---|-----|-------|
| 1 | Missing `SECURITY.md` | 1 |
| 2 | Missing `CONTRIBUTING.md` | 1 |
| 3 | Missing `CHANGELOG.md` | 1 |
| 4 | Missing `CODEOWNERS` | 1 |
| 5 | `.worktrees/` absent from `.gitignore` | 1 |
| 6 | Author email placeholder in `pyproject.toml` | 1 |
| 7 | Python upper bound `<3.13` (should be `<3.15`) | 1 |
| 8 | Missing `docs/known-vulnerabilities.md` | 1 |
| 9 | No `docs/superpowers/` directory | 1 (resolved by spec creation) |
| 10 | `CLAUDE.md` missing Package Overrides section | 1 |
| 11 | `CLAUDE.md` missing global rule cross-references | 1 |
| 12 | Black in use (replaced by Ruff format) | 2 |
| 13 | MyPy in use (replaced by BasedPyright) | 2 |
| 14 | safety in use (replaced by pip-audit) | 2 |
| 15 | darglint absent from dev dependencies | 2 |
| 16 | interrogate absent from dev dependencies | 2 |
| 17 | No `.qlty/qlty.toml` configuration | 2 |
| 18 | Ruff rule set incomplete (missing 20 PyStrict codes) | 2 |
| 19 | `target-version` not set to `py312` | 2 |
| 20 | No `.pre-commit-config.yaml` | 3 |
| 21 | No conventional commit enforcement | 3 |
| 22 | No em-dash pre-commit gate | 3 |
| 23 | CI uses inline jobs instead of org reusable workflows | 4 |
| 24 | No SonarCloud integration | 4 |
| 25 | No Qlty Cloud coverage reporting (uses Codecov) | 4 |
| 26 | Action SHAs not pinned (using mutable tags) | 4 |
| 27 | harden-runner missing from CI and CodeQL jobs | 4 |
| 28 | Security scan is non-blocking (`continue-on-error: true`) | 4 |
| 29 | No `.github/copilot-instructions.md` | 4 |
| 30 | No project `.claude/settings.json` | 5 |
| 31 | `CLAUDE.md` missing RAD and model-selection sections | 5 |
| 32 | `CLAUDE.md` Essential Commands reference removed tools | 5 |
| 33 | Em-dashes present in project documentation | 5 |
| 34 | `AGENTS.md` and `GEMINI.md` in wrong directory | 5 |
| 35 | Project nested one level too deep (`pp-security-master/pp-security-master/`) | 0 |

---

## Testing Strategy

Each phase ends with a verification step before the next phase begins:

- **Phase 0**: `git status` exits cleanly from `/home/byron/dev/pp-security-master/`;
  `ls CLAUDE.md README.md pyproject.toml` returns all three; no inner
  `pp-security-master/` directory exists
- **Phase 1**: `git status` confirms all new files present; `poetry check` passes
- **Phase 2**: `poetry run basedpyright` exits 0; `poetry run ruff format --check .`
  exits 0; `poetry run pip-audit` runs without error; `qlty check` passes
- **Phase 3**: `poetry run pre-commit run --all-files` exits 0 on a clean checkout
- **Phase 4**: CI passes on a test PR; all jobs green; no `continue-on-error` silencing failures
- **Phase 5**: `grep -r "\u2014" docs/ README.md CLAUDE.md` returns no matches;
  `AGENTS.md` and `GEMINI.md` present at project root

## Error Handling

BasedPyright strict mode will flag type errors that MyPy missed. These are real
errors, not false positives. Fix each one in Phase 2 before proceeding to Phase 3.
Do not add `# type: ignore` suppressions.

The full Ruff rule set will surface existing violations. Fix them in Phase 2.
Do not add `# noqa` suppressions except for genuinely vendored code with a
tracking reference.
