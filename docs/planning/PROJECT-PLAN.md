# Project Plan: pp-security-master Global Standards Alignment

> **Status**: Active
> **Version**: 1.0.0
> **Date**: 2026-04-21
> **Current Phase**: Phase 2 (In Progress)

---

## Executive Summary

pp-security-master is a centralized asset classification and taxonomy management service for
Portfolio Performance (PP). It extracts securities from broker files (PP XML, IBKR Flex,
Wells CSV, AltoIRA PDF), classifies them against OpenFIGI and pp-portfolio-classifier,
stores results in PostgreSQL 17, and syncs classifications back to Portfolio Performance via
XML/JSON feeds.

This project plan governs a parallel workstream: bringing the repository into full alignment
with global Claude development standards. That alignment work runs across six dependency-ordered
phases (Phase 0 through Phase 5), targeting completion within four weeks of Phase 2 start.
Phases 0 and 1 are complete. Phase 2 is the active phase.

The alignment work does not alter the service's production functionality. It replaces tooling,
adds quality gates, and establishes the CI/CD and documentation baseline from which all future
feature work will be launched.

---

## Scope

### In Scope

- Toolchain replacement: Black to Ruff format, MyPy to BasedPyright strict, safety to pip-audit
- New quality gates: darglint, interrogate (85% docstring coverage in `scripts/`), qlty CLI
- Pre-commit pipeline with eleven hooks including em-dash detection
- GitHub Actions modernization: SHA-pinned actions, harden-runner, org reusable workflow caller
- `.claude/settings.json`, `CLAUDE.md` corrections, and RAD markers
- Relocation of `AGENTS.md` and `GEMINI.md` to project root
- Em-dash removal across all documentation

### Out of Scope

- Production feature development (classification engine enhancements, new broker parsers)
- Database schema migrations
- OpenFIGI API integration changes
- Infrastructure changes to the PostgreSQL 17 deployment

---

## Architecture Overview

The following architectural decisions govern this alignment workstream.

### ADR-001: Phase 2 Toolchain Replacement Branch Strategy (Accepted)

**Decision**: Phase 2 splits toolchain replacements across three sequential feature branches
rather than a single branch.

**Rationale**: Tasks differ significantly in risk profile. Black-to-Ruff format and
safety-to-pip-audit are near-zero-risk swaps (identical output). MyPy-to-BasedPyright strict is
high-uncertainty because the current MyPy config uses `ignore_errors = true` on several override
sections, masking an unknown number of type errors. Bundling high-uncertainty work with zero-risk
work would allow BasedPyright error volume to block unrelated merges.

**Branch topology**: All three Phase 2 branches target `main` as their base. Merge order is
enforced, not creation order: `feature/phase-2a-toolchain-swaps` merges before
`feature/phase-2b-basedpyright` is opened as a PR; `feature/phase-2b-basedpyright` merges
before `feature/phase-2c-new-gates` is opened as a PR.

**Suppression policy**: No `# type: ignore` suppressions. Targeted `# pyright: ignore[<code>]`
with a GitHub issue reference is acceptable only when a third-party library has no stubs and the
error cannot be resolved by any other means.

See `/home/byron/dev/pp-security-master/docs/planning/adr/adr-001-phase2-branch-strategy.md`
for full options analysis and consequences.

---

## Technology Stack

| Layer | Tool | Version |
|-------|------|---------|
| Language | Python | 3.11+ (target-version py312 after Phase 2) |
| Dependency manager | Poetry | Current (no uv migration until future major rework) |
| Formatter | Ruff format | Replaces Black in Phase 2a |
| Linter | Ruff check | PyStrict rule set complete after Phase 2c |
| Type checker | BasedPyright strict | Replaces MyPy in Phase 2b |
| Security scanner | pip-audit + bandit | Replaces safety in Phase 2a |
| Docstring validator | darglint | Added in Phase 2c |
| Docstring coverage | interrogate | 85% threshold in `scripts/`, added in Phase 2c |
| Quality runner | qlty CLI | Standalone binary, added in Phase 2c |
| Test runner | pytest via nox | Existing; must stay green through every phase |
| Pre-commit | pre-commit | Configured in Phase 3 |
| CI | GitHub Actions | SHA-pinned, modernized in Phase 4 |
| Database | PostgreSQL 17 | Unraid-hosted; not modified by this workstream |

---

## Phased Development

### Phase 0: Relocate Project Root

**Status**: Complete
**Branch**: `chore/phase-0-relocate-root` (merged)
**Milestone target**: 2026-04-20 (met)

**Goal**: Move the project from `pp-security-master/pp-security-master/` to the correct
`pp-security-master/` root, preserving full git history.

**Deliverables**:

- All project files at the correct root path
- Git history preserved through the move
- `.vscode/settings.json` paths corrected

**Acceptance criteria**:

- All tests pass from the new root
- `git log` shows uninterrupted history

**Quality gates**:

- `poetry run pytest` exits 0
- `git log --oneline` confirms history continuity

**Dependencies**: None (first phase)

---

### Phase 1: Foundations

**Status**: Complete
**Branch**: `feature/phase-1-foundations` (merged, PR #9, 2026-04-21)
**Milestone target**: 2026-04-21 (met)

**Goal**: Establish all OpenSSF baseline files and correct project metadata so the repository
meets the global standard for any public or reviewed project.

**Deliverables**:

- `SECURITY.md` from org template
- `CONTRIBUTING.md` from org template
- `CHANGELOG.md` in Keep a Changelog format
- `.github/CODEOWNERS` assigning `@williaby`
- `.worktrees/` added to `.gitignore`
- `pyproject.toml` author email and Python upper bound corrected
- `docs/known-vulnerabilities.md` created
- `CLAUDE.md` updated with package overrides and global rule references

**Acceptance criteria**:

- All five OpenSSF required files present: `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`,
  `CHANGELOG.md`, `README.md`
- `poetry check` exits `All set!`

**Quality gates**:

- `poetry run pytest` exits 0
- `poetry check` passes
- OpenSSF file checklist verified

**Dependencies**: Phase 0 complete

---

### Phase 2: Toolchain Replacements

**Status**: In Progress
**Milestone target**: 2026-04-28

**Goal**: Replace three legacy tools (Black, MyPy, safety) with global-standard equivalents
and add three new quality gates (darglint, interrogate, qlty). All work is scoped to
`pyproject.toml`, `noxfile.py`, `Makefile`, and source files requiring type fixes.

**Branch strategy** (ADR-001, risk-tiered split):

| Branch | Tasks | Contents |
|--------|-------|----------|
| `feature/phase-2a-toolchain-swaps` | 6, 8 | Black removed, `ruff format` wired; safety removed |
| `feature/phase-2b-basedpyright` | 7 | MyPy removed, BasedPyright strict wired, all type errors fixed |
| `feature/phase-2c-new-gates` | 9, 10, 11 | darglint + interrogate added; qlty configured; Ruff expanded to PyStrict rule set |

Merge order is strictly enforced: 2a merges before 2b PR opens; 2b merges before 2c PR opens.
Each branch rebases on updated `main` before its PR is raised.

**Deliverables**:

- `feature/phase-2a`: Black removed, `ruff format` configured in `pyproject.toml`, `noxfile.py`,
  and `Makefile`; safety removed from the same files
- `feature/phase-2b`: MyPy and stubs removed; `[tool.basedpyright]` strict config added;
  all `src/**/*.py` type errors resolved with zero suppressions (or targeted suppressions paired
  with issue references per ADR-001 escalation policy)
- `feature/phase-2c`: darglint and interrogate added to dev deps with config blocks; qlty CLI
  configured in `.qlty/qlty.toml`; Ruff select list expanded to PyStrict set; `BLE001` removed
  from ignore list; `max-branches` lowered to 12; `target-version` updated to `py312`

**Acceptance criteria**:

| Check | Command | Expected |
|-------|---------|----------|
| Format | `poetry run ruff format --check .` | exit 0 |
| Lint | `poetry run ruff check .` | exit 0, 0 violations |
| Type check | `poetry run basedpyright` | exit 0, 0 errors |
| Security | `poetry run nox -s security` | bandit + pip-audit pass; safety absent |
| Docstring accuracy | `poetry run python -m darglint src/` | exit 0 |
| Docstring coverage | `poetry run interrogate scripts/ --fail-under 85` | exit 0 |
| Quality runner | `qlty check` | exit 0 |
| Full suite | `poetry run nox` | all sessions green |

Tools that must not appear after Phase 2: black, mypy, safety (in any invocation).
Tools that must appear after Phase 2: basedpyright, ruff format, pip-audit, darglint,
interrogate, qlty.

**Quality gates** (per branch, evaluated before PR is raised):

- Branch 2a: `poetry run ruff format --check .` and `poetry run nox -s security` both green
- Branch 2b: `poetry run basedpyright` exits 0; existing test suite green; no type suppressions
  except under the ADR-001 escalation policy
- Branch 2c: `poetry run ruff check .`, `poetry run python -m darglint src/`,
  `poetry run interrogate scripts/ --fail-under 85`, and `qlty check` all green
- All branches: 80% line coverage / 70% branch coverage maintained (no regression)
- Phase gate: `/phase-gate` run and passes before Phase 3 opens

**Dependencies**: Phase 1 complete

---

### Phase 3: Pre-commit Pipeline

**Status**: Not started
**Branch**: `chore/phase-3-pre-commit` (to be created)
**Milestone target**: 2026-05-02

**Goal**: Create `.pre-commit-config.yaml` with all eleven hooks and verify the existing nox
`pre_commit` session executes it correctly. The `.pre-commit-config.yaml` does not exist until
this phase begins; Phase 2 does not create it.

**Deliverables**:

- `.pre-commit-config.yaml` with eleven hooks:
  1. `ruff` (lint with autofix, exit-non-zero-on-fix)
  2. `ruff-format` (format check)
  3. `basedpyright` (strict type checking)
  4. `bandit` (static security analysis, targets `src/`)
  5. `detect-secrets` (credential scanning, uses `.secrets.baseline`)
  6. `darglint` (docstring Args/Returns/Raises validation)
  7. `interrogate` (85% docstring coverage in `scripts/`)
  8. `commitizen` (conventional commit message format, `commit-msg` stage)
  9. `yamllint` (YAML syntax and style, uses `.yamllint.yml`)
  10. `markdownlint` (Markdown formatting with autofix)
  11. `no-em-dash` (local pygrep hook blocking the em-dash character)
- `.secrets.baseline` generated and reviewed for false positives
- Pre-commit hooks installed (`pre-commit install` + `pre-commit install --hook-type commit-msg`)
- `CLAUDE.md` updated with pre-commit commands

**Acceptance criteria**:

- `poetry run pre-commit run --all-files` exits 0 from a clean checkout
- `poetry run nox -s pre_commit` exits 0

**Quality gates**:

- All eleven hooks pass on `--all-files` run
- No secrets detected in `.secrets.baseline` false-positive review
- 80% line / 70% branch coverage maintained
- `/phase-gate` run and passes before Phase 4 opens

**Dependencies**: Phase 2 complete (all three branches merged; pre-commit hooks invoke Phase 2
tools and cannot be configured before those tools exist)

---

### Phase 4: CI Modernization

**Status**: Not started
**Branch**: `chore/phase-4-ci-modernization` (to be created)
**Milestone target**: 2026-05-07

**Goal**: Pin all GitHub Actions to commit SHAs, add `harden-runner` for supply-chain
hardening, replace the 340-line `ci.yml` with a thin caller to the org reusable workflow, and
add security, SonarCloud, and coverage workflows.

**Deliverables**:

- Commit SHAs resolved for all actions in use
- `codeql.yml`: SHAs pinned, `harden-runner` added
- `scorecard.yml`: SHAs pinned
- `renovate-auto-merge.yml`: SHAs pinned
- `ci.yml`: replaced with thin caller to
  `ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@main`
- `.github/workflows/security.yml` created
- `.github/workflows/sonarcloud.yml` created
- `.github/workflows/coverage.yml` created
- `.github/copilot-instructions.md` created

**Acceptance criteria**:

- No mutable version tags in any `.github/workflows/*.yml` file
- `python3 -c "import yaml; yaml.safe_load(open(...))"` passes for all workflow files
- CI passes on push to main after the rewrite

**Quality gates**:

- SHA pinning verified for every action reference (no `@v3`, `@main`, etc.)
- `harden-runner` present in all modified workflow files
- All workflow YAML is syntactically valid
- CI green on push after rewrite
- 80% line / 70% branch coverage maintained
- `/phase-gate` run and passes before Phase 5 opens

**Dependencies**: Phase 3 complete (pre-commit hooks must be in place before CI configuration
is finalized, to ensure CI and local gates are consistent)

---

### Phase 5: .claude/ and Docs Cleanup

**Status**: Not started
**Branch**: `chore/phase-5-claude-docs-cleanup` (to be created)
**Milestone target**: 2026-05-09

**Goal**: Add project `.claude/settings.json`, update `CLAUDE.md` with RAD markers and
corrected tool commands, remove all em-dashes from documentation, and relocate `AGENTS.md`
and `GEMINI.md` to the project root.

**Deliverables**:

- `.claude/settings.json` with tool permission allowlist
- `CLAUDE.md` updated with RAD markers, model selection table, corrected tool commands
- All em-dashes removed from `docs/`, `.github/`, `schema_exports/`, and root `*.md` files
- `AGENTS.md` moved from `docs/project/` to project root
- `GEMINI.md` moved from `docs/project/` to project root

**Acceptance criteria**:

- no-em-dash pre-commit hook passes with zero violations
- `ls -la AGENTS.md GEMINI.md` shows both files at root
- `python3 -c "import json; json.load(open('.claude/settings.json'))"` exits 0

**Quality gates**:

- Em-dash scan returns zero matches
- `.claude/settings.json` parses as valid JSON
- `CLAUDE.md` contains RAD markers and updated tool references
- 80% line / 70% branch coverage maintained
- `poetry run pre-commit run --all-files` exits 0 (validates no-em-dash hook passes)
- `/phase-gate` run and passes (final phase; gates overall alignment completion)

**Dependencies**: Phase 4 complete

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| BasedPyright surfaces 50+ type errors in Phase 2b | Medium | High | Branch 2b isolated per ADR-001; work proceeds sub-commit by module until `basedpyright` exits 0; does not block 2a or 2c |
| Third-party stubs unavailable for BasedPyright | Low | Medium | Targeted `# pyright: ignore[<code>]` with GitHub issue reference per ADR-001 escalation policy; no blanket suppressions |
| Org reusable workflow API mismatch in Phase 4 ci.yml | Low | High | Read workflow inputs before writing caller; validate YAML with Python yaml parser before commit |
| SHA lookup returns wrong commit for codeql-action | Low | Medium | Verify 40-char SHA; dereference annotated tags; confirm with `gh release view` |
| pre-commit hook version drift between Phase 3 and Phase 4 | Low | Low | Pin hook versions with SHA or explicit version tag in `.pre-commit-config.yaml` |
| BasedPyright strict rejects SQLAlchemy ORM patterns | Medium | Medium | Use `cast()` or `isinstance` narrowing; consult SQLAlchemy typed extension patterns before writing suppressions |

---

## Success Metrics

The alignment workstream is complete when all of the following hold simultaneously from a clean
checkout of `main`:

- `poetry run ruff format --check .` exits 0
- `poetry run ruff check .` exits 0, 0 violations
- `poetry run basedpyright` exits 0, 0 errors
- `poetry run nox -s security` runs bandit + pip-audit only (safety absent)
- `poetry run python -m darglint src/` exits 0
- `poetry run interrogate scripts/ --fail-under 85` exits 0
- `qlty check` exits 0
- `poetry run pre-commit run --all-files` exits 0
- No mutable version tags in `.github/workflows/*.yml`
- no-em-dash pre-commit hook passes with zero violations
- `poetry run nox` all sessions green (coverage at 80% line / 70% branch minimum)

---

## Phase 0 Checklist (Complete -- For Reference)

The following tasks were executed to complete Phase 0:

- [x] Identify nested path `pp-security-master/pp-security-master/`
- [x] Move all files to correct root
- [x] Verify `git log` shows uninterrupted history
- [x] Correct `.vscode/settings.json` paths
- [x] Run `poetry run pytest` from new root and confirm green

---

## Immediate Next Actions (Phase 2 Active)

The following tasks are ready for execution now, in order:

1. Create `feature/phase-2a-toolchain-swaps` branch off current `main`
2. Remove `black` and `safety` from `pyproject.toml`; remove `[tool.black]`; add
   `[tool.ruff.format]` config block; keep isort profile as `"black"` (the `"ruff"` value is not a valid isort profile)
3. Update `noxfile.py` to replace `black` invocations with `ruff format` and remove `safety`
   invocations
4. Update `Makefile` to replace `black` invocations with `ruff format` and replace `safety`
   with `pip-audit`
5. Verify: `poetry install --sync`, `poetry run ruff format --check .` exits 0,
   `poetry run nox -s security` passes without safety
6. Commit (two commits: Task 6 then Task 8), open PR, merge to main
7. Create `feature/phase-2b-basedpyright` off updated main; rebase if 2a has not yet merged
8. Remove mypy, stubs; add basedpyright; run `poetry run basedpyright`; fix all errors
9. Commit, open PR, merge to main
10. Create `feature/phase-2c-new-gates` off updated main; add darglint, interrogate, qlty;
    expand Ruff select; fix all violations
11. Commit, open PR, merge to main
12. Run `/phase-gate` to confirm Phase 2 complete before opening Phase 3

---

## Related Documents

- Phase 2 design spec:
  `/home/byron/dev/pp-security-master/docs/superpowers/specs/2026-04-21-phase-2-toolchain-replacements-design.md`
- ADR-001 branch strategy:
  `/home/byron/dev/pp-security-master/docs/planning/adr/adr-001-phase2-branch-strategy.md`
- Full roadmap:
  `/home/byron/dev/pp-security-master/docs/planning/roadmap.md`
- Global alignment plan:
  `/home/byron/dev/pp-security-master/docs/superpowers/plans/2026-04-20-global-alignment.md`
- Known vulnerabilities:
  `/home/byron/dev/pp-security-master/docs/known-vulnerabilities.md`
