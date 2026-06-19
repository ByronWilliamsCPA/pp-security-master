# Development Roadmap: pp-security-master Global Standards Alignment

> **Status**: Active | **Updated**: 2026-04-21

## TL;DR

Bring pp-security-master into full alignment with global Claude standards across six
dependency-ordered phases, from project relocation (Phase 0) through documentation cleanup
(Phase 5), targeting completion within four weeks.

## Timeline Overview

```text
Phase 0: Relocate root       ████████████████ (complete)
Phase 1: Foundations         ████████████████ (complete)
Phase 2: Toolchain           ████░░░░░░░░░░░░ (in progress -- 3 branches)
Phase 3: Pre-commit          ░░░░░░░░░░░░░░░░ (not started)
Phase 4: CI modernization    ░░░░░░░░░░░░░░░░ (not started)
Phase 5: .claude/ and docs   ░░░░░░░░░░░░░░░░ (not started)
```

## Milestones

| Milestone | Target | Status | Depends on | Blocks |
| --------- | ------ | ------ | ---------- | ------ |
| M0: Project root relocated | 2026-04-20 | complete | None | M1 |
| M1: OpenSSF baseline files | 2026-04-21 | complete | M0 | M2 |
| M2: Toolchain replacements | 2026-04-28 | in progress | M1 | M3 |
| M3: Pre-commit pipeline | 2026-05-02 | planned | M2 | M4 |
| M4: CI workflows modernized | 2026-05-07 | planned | M3 | M5 |
| M5: Docs and .claude/ clean | 2026-05-09 | planned | M4 | none |

> Note: M3 extended to 2026-05-02 to buffer for BasedPyright error volume in Phase 2b.
> Existing `nox` sessions and unit/integration tests must remain green through every phase merge.

---

## Phase 0: Relocate Project Root (Complete)

### Objective

Move the project from the nested `pp-security-master/pp-security-master/` path to the correct
`pp-security-master/` root.

### Deliverables

- [x] All project files at correct root path
- [x] Git history preserved through the move
- [x] `.vscode/settings.json` paths corrected

### Success Criteria

- All tests pass from the new root
- `git log` shows uninterrupted history

---

## Phase 1: Foundations (Complete)

### Objective

Establish all OpenSSF baseline files and correct project metadata.

### Deliverables

- [x] `SECURITY.md` from org template
- [x] `CONTRIBUTING.md` from org template
- [x] `CHANGELOG.md` in Keep a Changelog format
- [x] `.github/CODEOWNERS` assigning `@williaby`
- [x] `.worktrees/` added to `.gitignore`
- [x] `pyproject.toml` author email and Python upper bound corrected
- [x] `docs/known-vulnerabilities.md` created
- [x] `CLAUDE.md` updated with package overrides and global rule references

### Success Criteria

- All five OpenSSF required files present: `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`,
  `CHANGELOG.md`, `README.md`
- `poetry check` exits `All set!`

---

## Phase 2: Toolchain Replacements (In Progress)

### Objective

Replace three legacy tools (Black, MyPy, safety) with global-standard equivalents and add
three new quality gates (darglint, interrogate, qlty).

### Deliverables

- [ ] `feature/phase-2a`: Black removed, `ruff format` wired, safety removed (Tasks 6, 8)
- [ ] `feature/phase-2b`: MyPy removed, BasedPyright strict wired, all type errors fixed (Task 7)
- [ ] `feature/phase-2c`: darglint + interrogate added, qlty configured, Ruff expanded to
  PyStrict rule set (Tasks 9, 10, 11)

### Success Criteria

- `poetry run ruff format --check .` exits 0
- `poetry run basedpyright` exits 0, 0 errors
- `poetry run nox -s security` runs bandit + pip-audit only
- `poetry run python -m darglint src/` exits 0
- `poetry run interrogate scripts/ --fail-under 85` exits 0
- `qlty check` exits 0
- `poetry run nox` all sessions green

### Branch Strategy

Branches are independent off `main`. Strict merge order applies:

1. `feature/phase-2a-toolchain-swaps` opens as PR, merges to main
2. `feature/phase-2b-basedpyright` PR opens only after 2a merges; rebases on updated main
3. `feature/phase-2c-new-gates` PR opens only after 2b merges; rebases on updated main

See [ADR-001](adr/adr-001-phase2-branch-strategy.md) for full rationale and escalation policy.

### Dependencies

- Requires: Phase 1 complete
- Blocks: Phase 3

---

## Phase 3: Pre-commit Pipeline

### Objective

Create `.pre-commit-config.yaml` and verify the existing nox `pre_commit` session uses it.

### Deliverables

- [ ] `.pre-commit-config.yaml` with all eleven hooks:
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
  11. `no-em-dash` (local pygrep hook blocking the em-dash character U+2014)
- [ ] `.secrets.baseline` generated and reviewed for false positives
- [ ] Pre-commit hooks installed (`pre-commit install` + `pre-commit install --hook-type commit-msg`)
- [ ] `poetry run pre-commit run --all-files` exits 0
- [ ] `poetry run nox -s pre_commit` exits 0
- [ ] `CLAUDE.md` updated with pre-commit commands

### Success Criteria

- `poetry run pre-commit run --all-files` exits 0 from a clean checkout
- `poetry run nox -s pre_commit` exits 0

### Dependencies

- Requires: Phase 2 complete (pre-commit hooks invoke the Phase 2 tools)
- Blocks: Phase 4

---

## Phase 4: CI Modernization

### Objective

Pin all GitHub Actions to commit SHAs, add `harden-runner`, replace the 340-line `ci.yml`
with a thin caller to the org reusable workflow, and add security/SonarCloud/coverage workflows.

### Deliverables

- [ ] Commit SHAs resolved for all actions in use (Task 14)
- [ ] `codeql.yml`: SHAs pinned, `harden-runner` added (Task 15)
- [ ] `scorecard.yml`: SHAs pinned (Task 16)
- [ ] `renovate-auto-merge.yml`: SHAs pinned (Task 17)
- [ ] `ci.yml`: replaced with thin caller to `ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@main` (Task 18)
- [ ] `.github/workflows/security.yml` created (Task 19)
- [ ] `.github/workflows/sonarcloud.yml` created (Task 19)
- [ ] `.github/workflows/coverage.yml` created (Task 19)
- [ ] `.github/copilot-instructions.md` created (Task 20)

### Success Criteria

- No mutable version tags in any `.github/workflows/*.yml` file
- `python3 -c "import yaml; yaml.safe_load(open(...))"` passes for all workflow files
- CI passes on push to main after the rewrite

### Dependencies

- Requires: Phase 3 complete
- Blocks: Phase 5

---

## Phase 5: .claude/ and Docs Cleanup

### Objective

Add project `.claude/settings.json`, update `CLAUDE.md` with RAD markers and corrected
commands, remove all em-dashes from documentation, and relocate `AGENTS.md` / `GEMINI.md`.

### Deliverables

- [ ] `.claude/settings.json` with tool permission allowlist (Task 21)
- [ ] `CLAUDE.md` updated with RAD markers, model selection table, corrected tool commands
  (Task 22)
- [ ] All em-dashes removed from `docs/`, `.github/`, `schema_exports/`, and root `*.md`
  files (Task 23)
- [ ] `AGENTS.md` moved from `docs/project/` to project root (Task 24)
- [ ] `GEMINI.md` moved from `docs/project/` to project root (Task 24)

### Success Criteria

- no-em-dash pre-commit hook passes with zero violations
- `ls -la AGENTS.md GEMINI.md` shows both files at root
- `python3 -c "import json; json.load(open('.claude/settings.json'))"` exits 0

### Dependencies

- Requires: Phase 4 complete
- Blocks: nothing (final phase)

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| BasedPyright surfaces 50+ type errors | Medium | High | Branch 2b isolated; work proceeds until 0 errors |
| Third-party stubs unavailable for BasedPyright | Low | Medium | Targeted suppression with issue tracking per ADR-001 |
| Org reusable workflow API mismatch in ci.yml | Low | High | Read workflow inputs before writing caller; validate YAML |
| SHA lookup returns wrong commit for codeql-action | Low | Medium | Verify 40-char SHA; dereference annotated tags |

## Definition of Done

A phase is complete when:

- [ ] All deliverables merged to main
- [ ] All success criteria pass from a clean checkout
- [ ] `/phase-gate` run and passes
- [ ] No suppressions added without tracked justification

## Related Documents

- [Phase 2 Design Spec](../superpowers/specs/2026-04-21-phase-2-toolchain-replacements-design.md)
- [Global Alignment Plan](../superpowers/plans/2026-04-20-global-alignment.md)
- [ADR-001: Branch Strategy](adr/adr-001-phase2-branch-strategy.md)
