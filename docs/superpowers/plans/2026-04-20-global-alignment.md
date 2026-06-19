# Global Standards Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `pp-security-master` into full alignment with the global Claude standards, org-level GitHub workflows, and Python toolchain rules across six dependency-ordered phases.

**Status as of 2026-04-29:** Phase 0 complete. Phase 1 complete (merged PR #9). Phase 2a, Phase 2b, and Phase 2c complete (merged PR #13). Phase 3 complete (PR open, pending merge). Phases 4-5 not started.

**Architecture:** Each phase builds on a stable base established by the previous phase. Phase 0 relocates the project to its correct directory. Phases 1-5 layer in files, tooling, CI, and documentation without revisiting completed work.

**Tech Stack:** Python 3.11+, Poetry, Ruff, BasedPyright, pip-audit, darglint, interrogate, qlty CLI, pre-commit, GitHub Actions (org reusable workflows), nox, Make.

**Spec:** `docs/superpowers/specs/2026-04-20-global-alignment-design.md`

---

> **Working directory note:** After Task 1 (Phase 0), all work happens from
> `/home/byron/dev/pp-security-master/`. Paths in Tasks 2-28 use that root.

---

## Phase 0: Relocate Project Root

---

### Task 1: Move project from nested path to correct root

The project lives at `.../pp-security-master/pp-security-master/` but should be at `.../pp-security-master/`. The outer directory contains only the inner one.

**Files:**

- Move: everything in `/home/byron/dev/pp-security-master/pp-security-master/` to `/home/byron/dev/pp-security-master/`

- [x] **Step 1: Verify the outer directory is clean**

```bash
ls -la /home/byron/dev/pp-security-master/
```

Expected: only one entry -- `pp-security-master/`. If any other files exist, stop and investigate before proceeding.

- [x] **Step 2: Move all content out of the inner directory**

Run from `/home/byron/dev/pp-security-master/`:

```bash
cd /home/byron/dev/pp-security-master

# Move hidden files and directories first
for item in pp-security-master/.[!.]* pp-security-master/..?*; do
    [ -e "$item" ] && mv "$item" .
done

# Move all non-hidden items
mv pp-security-master/* .
```

- [x] **Step 3: Remove the now-empty inner directory**

```bash
rmdir /home/byron/dev/pp-security-master/pp-security-master
```

If `rmdir` fails, the directory is not empty. Run `ls -la /home/byron/dev/pp-security-master/pp-security-master/` to see what remains, move those items, then retry.

- [x] **Step 4: Verify git works from the new root**

```bash
cd /home/byron/dev/pp-security-master
git status
git log --oneline -3
```

Expected: `git status` shows a clean working tree. `git log` shows the three most recent commits from the project history.

- [x] **Step 5: Check .vscode/settings.json for absolute paths**

```bash
grep -r "pp-security-master/pp-security-master" .vscode/ || echo "No old paths found"
```

Expected: `No old paths found`. If matches exist, open `.vscode/settings.json` and remove the extra `pp-security-master/` segment from any paths found.

- [x] **Step 6: Commit the relocation (no code changes, just the moved state)**

```bash
git add -A
git status
git commit -m "chore: relocate project to correct root directory

Moved all project files from pp-security-master/pp-security-master/
to pp-security-master/ to align with expected repository structure.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 1: Foundations

All subsequent paths are relative to `/home/byron/dev/pp-security-master/`.

---

### Task 2: Create SECURITY.md and CONTRIBUTING.md from org templates

The org-level files at `/home/byron/dev/.github/` are the canonical templates. Copy and adapt them for this project.

**Files:**

- Create: `SECURITY.md`
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Copy org SECURITY.md and adapt**

```bash
cp /home/byron/dev/.github/SECURITY.md SECURITY.md
```

Open `SECURITY.md` and replace any org-generic placeholders with project-specific values. At minimum, confirm the contact email is `byronawilliams@gmail.com` and the repo name is `pp-security-master`.

- [ ] **Step 2: Copy org CONTRIBUTING.md and adapt**

```bash
cp /home/byron/dev/.github/CONTRIBUTING.md CONTRIBUTING.md
```

Open `CONTRIBUTING.md` and update the repo URL, local setup commands (use `poetry install` not `pip install`), and any reference to test commands (use `nox -s unit`).

- [ ] **Step 3: Verify both files exist and are non-empty**

```bash
wc -l SECURITY.md CONTRIBUTING.md
```

Expected: both files show more than 5 lines.

- [ ] **Step 4: Commit**

```bash
git add SECURITY.md CONTRIBUTING.md
git commit -m "docs: add SECURITY.md and CONTRIBUTING.md from org templates

Required OpenSSF files. Adapted from ByronWilliamsCPA/.github org templates.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Create CHANGELOG.md and CODEOWNERS

**Files:**

- Create: `CHANGELOG.md`
- Create: `.github/CODEOWNERS`

- [ ] **Step 1: Create CHANGELOG.md**

Create `CHANGELOG.md` with this exact content:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
```

- [ ] **Step 2: Create .github/CODEOWNERS**

Create `.github/CODEOWNERS` with this content:

```text
# Default owner for all files
* @williaby
```

- [ ] **Step 3: Verify**

```bash
ls -la CHANGELOG.md .github/CODEOWNERS
head -3 CHANGELOG.md
```

Expected: both files exist; first line of CHANGELOG.md is `# Changelog`.

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md .github/CODEOWNERS
git commit -m "docs: add CHANGELOG.md and CODEOWNERS

CHANGELOG follows Keep a Changelog format. CODEOWNERS assigns @williaby
as default reviewer for all files.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Fix .gitignore, pyproject.toml metadata, and create known-vulnerabilities.md

**Files:**

- Modify: `.gitignore`
- Modify: `pyproject.toml` (lines 8, 24-25)
- Create: `docs/known-vulnerabilities.md`

- [ ] **Step 1: Add .worktrees/ to .gitignore**

Append to `.gitignore`:

```bash
echo "" >> .gitignore
echo "# Git worktrees (created by git worktree add)" >> .gitignore
echo ".worktrees/" >> .gitignore
```

Verify: `tail -3 .gitignore` shows the three new lines.

- [ ] **Step 2: Fix author email in pyproject.toml**

In `pyproject.toml` at line 8, change:

```toml
authors = [{name = "Byron", email = "byron@example.com"}]
```

to:

```toml
authors = [{name = "Byron Williams", email = "byronawilliams@gmail.com"}]
```

- [ ] **Step 3: Extend Python upper bound in pyproject.toml**

In `pyproject.toml`:

At line 24 (under `[project]`), change:

```toml
requires-python = ">=3.11,<3.13"
```

to:

```toml
requires-python = ">=3.11,<3.15"
```

At the Poetry dependencies section, change:

```toml
python = ">=3.11,<3.13"
```

to:

```toml
python = ">=3.11,<3.15"
```

- [ ] **Step 4: Verify pyproject.toml is valid**

```bash
poetry check
```

Expected: `All set!`

- [ ] **Step 5: Create docs/known-vulnerabilities.md**

```bash
mkdir -p docs
```

Create `docs/known-vulnerabilities.md` with this content:

```markdown
# Known Vulnerabilities

Unfixed CVEs are documented here per the global unfixed-CVE policy.
No entry may age past 60 days without reassessment. Review quarterly.

| CVE | Package | Severity | Introduced | Last Reviewed | Status | Notes |
|-----|---------|----------|------------|---------------|--------|-------|
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore pyproject.toml docs/known-vulnerabilities.md
git commit -m "chore: fix project metadata and add required policy files

- Add .worktrees/ to .gitignore per git workflow rule
- Correct author email and name in pyproject.toml
- Extend Python upper bound to <3.15 per global standard
- Add docs/known-vulnerabilities.md per unfixed-CVE policy

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Update CLAUDE.md with Phase 1 additions

**Files:**

- Modify: `CLAUDE.md`

- [ ] **Step 1: Add Package Overrides section to CLAUDE.md**

Append to the end of `CLAUDE.md`:

```markdown
## Package Overrides

- **Dependency manager**: Using `poetry` instead of `uv` -- this project
  predates the `uv` canonical standard. No migration required until a future
  major rework.

## Global Rule References

This project is governed by the following global rules in addition to this file:

- `~/.claude/.claude/rules/python.md` -- linting, type checking, function quality gates
- `~/.claude/.claude/rules/git-workflow.md` -- branch strategy, SHA pinning, pre-commit
- `~/.claude/.claude/rules/pre-commit.md` -- pre-commit hook requirements
- `~/.claude/.claude/rules/testing.md` -- coverage thresholds, test scope
- `~/.claude/.claude/rules/writing.md` -- em-dash ban, AI pattern blacklist
- `~/.claude/.claude/standards/packages.md` -- canonical package choices
```

- [ ] **Step 2: Verify no em-dashes were introduced**

```bash
grep $'\xe2\x80\x94' CLAUDE.md || echo "No em-dashes found"
```

Expected: `No em-dashes found`.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add package overrides and global rule references to CLAUDE.md

Documents the poetry grandfathering exception and cross-references all
global rule files that govern this project.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 2: Toolchain Replacements

---

### Task 6: Remove Black, configure Ruff format

Black is replaced by `ruff format`. Ruff is already in dev dependencies at `0.12.3`.

**Files:**

- Modify: `pyproject.toml` (remove black dep, add `[tool.ruff.format]`)
- Modify: `noxfile.py` (lines 190, 227)
- Modify: `Makefile` (lines 45, 52)

- [ ] **Step 1: Confirm current state by running black**

```bash
poetry run black --check . 2>&1 | head -5
```

Note: this should pass (clean formatting). If it fails, fix formatting with `poetry run black .` before proceeding so you have a clean baseline.

- [ ] **Step 2: Remove black from pyproject.toml dev dependencies**

In `pyproject.toml`, remove this line from `[tool.poetry.group.dev.dependencies]`:

```toml
black = "24.10.0"
```

- [ ] **Step 3: Add [tool.ruff.format] config to pyproject.toml**

Add after the `[tool.ruff]` block (after line 126):

```toml
[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"
```

- [ ] **Step 4: Update noxfile.py lint session (line 190)**

Change line 190 from:

```python
    session.run("black", "--check", *args)
```

to:

```python
    session.run("ruff", "format", "--check", *args)
```

- [ ] **Step 5: Update noxfile.py format_code session (line 227)**

Change line 227 from:

```python
    session.run("black", *args)
```

to:

```python
    session.run("ruff", "format", *args)
```

- [ ] **Step 6: Update Makefile lint target (line 45)**

Change line 45 from:

```makefile
 $(POETRY) run black --check .
```

to:

```makefile
 $(POETRY) run ruff format --check .
```

- [ ] **Step 7: Update Makefile format target (line 52)**

Change line 52 from:

```makefile
 $(POETRY) run black .
```

to:

```makefile
 $(POETRY) run ruff format .
```

- [ ] **Step 8: Reinstall deps and verify ruff format works**

```bash
poetry install --sync
poetry run ruff format --check .
```

Expected: exits 0 (all files already formatted correctly, since black and ruff format produce identical output for standard Python).

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml noxfile.py Makefile
git commit -m "refactor: replace Black with Ruff format

Ruff format replaces Black per global python.md standard. Output is
identical for standard Python files. Removes black dev dependency.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Remove MyPy, configure BasedPyright, fix type errors

BasedPyright runs in strict mode and will surface errors MyPy missed. Expect a wave of new findings. Fix each one -- do not add `# type: ignore`.

**Files:**

- Modify: `pyproject.toml` (remove mypy dep + stubs, remove `[tool.mypy]`, add `[tool.basedpyright]`)
- Modify: `noxfile.py` (line 204)
- Modify: `Makefile` (line 47)
- Fix: any `.py` files in `src/` that BasedPyright flags

- [ ] **Step 1: Record the current MyPy state as baseline**

```bash
poetry run mypy src 2>&1 | tail -5
```

Note: how many errors (likely 0). BasedPyright strict will find more.

- [ ] **Step 2: Remove MyPy and stubs from pyproject.toml**

Remove these lines from `[tool.poetry.group.dev.dependencies]`:

```toml
mypy = "1.13.0"
types-pyyaml = ">=6.0.12.12"
types-python-dateutil = ">=2.8.19.20240106"
```

- [ ] **Step 3: Remove [tool.mypy] section from pyproject.toml**

Delete the entire block from line 207 to line 234:

```toml
[tool.mypy]
python_version = "3.11"
...
[[tool.mypy.overrides]]
...
```

- [ ] **Step 4: Add basedpyright to dev dependencies**

In `[tool.poetry.group.dev.dependencies]`, add:

```toml
basedpyright = ">=1.1.400"
```

- [ ] **Step 5: Add [tool.basedpyright] config to pyproject.toml**

Add after the `[tool.ruff.lint.isort]` section:

```toml
[tool.basedpyright]
pythonVersion = "3.11"
pythonPlatform = "All"
typeCheckingMode = "strict"
strictListInference = true
strictDictionaryInference = true
strictSetInference = true
```

- [ ] **Step 6: Update noxfile.py type_check session (line 204)**

Change line 204 from:

```python
    session.run("mypy", "src")
```

to:

```python
    session.run("basedpyright")
```

- [ ] **Step 7: Update Makefile type-check invocation (line 47)**

Change line 47 from:

```makefile
 $(POETRY) run mypy src
```

to:

```makefile
 $(POETRY) run basedpyright
```

- [ ] **Step 8: Reinstall deps**

```bash
poetry install --sync
```

Expected: installs basedpyright, removes mypy and stubs.

- [ ] **Step 9: Run BasedPyright and fix all errors**

```bash
poetry run basedpyright 2>&1
```

For each error reported, fix the underlying type issue in the source file. Common patterns:

- Missing return type annotation: add `-> ReturnType` to the function signature
- `Unknown` type: add an explicit annotation or narrow the type with `isinstance`
- Optional not handled: add a None check before use
- Implicit `Any`: provide explicit typing

Run `poetry run basedpyright` after each fix to confirm progress. Do not proceed until it exits 0.

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml noxfile.py Makefile src/
git commit -m "refactor: replace MyPy with BasedPyright in strict mode

BasedPyright runs 3-5x faster than MyPy and enforces stricter type
checking. Fixed all type errors surfaced by strict mode.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 8: Remove safety (pip-audit already present)

`safety` is in dev dependencies and the nox security session. `pip-audit` already runs in the same session at line 219. Remove safety.

**Files:**

- Modify: `pyproject.toml` (remove safety dep)
- Modify: `noxfile.py` (line 213)
- Modify: `Makefile` (line 56)

- [ ] **Step 1: Verify pip-audit already runs in nox security session**

```bash
grep -n "pip-audit\|safety" noxfile.py
```

Expected output:

```text
213:    session.run("safety", "check", "--json")
219:    session.run("pip-audit")
```

Confirm both lines exist before removing safety.

- [ ] **Step 2: Remove safety from pyproject.toml**

Remove from `[tool.poetry.group.dev.dependencies]`:

```toml
safety = ">=3.0.1"
```

- [ ] **Step 3: Remove safety from noxfile.py security session**

Remove lines 212-213 from noxfile.py:

```python
    # Check for known vulnerabilities
    session.run("safety", "check", "--json")
```

The session should now go directly from `session.run("poetry", ...)` to `# Run bandit`.

- [ ] **Step 4: Update Makefile security target (line 56)**

Change line 56 from:

```makefile
 $(POETRY) run safety check
```

to:

```makefile
 $(POETRY) run pip-audit
```

- [ ] **Step 5: Reinstall and verify security session runs**

```bash
poetry install --sync
poetry run nox -s security
```

Expected: bandit and pip-audit run without error. Safety no longer appears.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml noxfile.py Makefile
git commit -m "refactor: replace safety with pip-audit in security checks

pip-audit was already running in the nox security session. Removes
safety as a redundant dependency.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 9: Add darglint and interrogate

darglint validates that docstring `Args`, `Returns`, and `Raises` sections match the actual function signature. interrogate enforces 85% docstring coverage in `scripts/`.

**Files:**

- Modify: `pyproject.toml` (add deps, add `[tool.interrogate]`, add `[tool.darglint]`)

- [ ] **Step 1: Add dev dependencies to pyproject.toml**

In `[tool.poetry.group.dev.dependencies]`, add:

```toml
darglint = ">=1.8.1"
interrogate = ">=1.7.0"
```

- [ ] **Step 2: Add [tool.interrogate] config to pyproject.toml**

```toml
[tool.interrogate]
ignore-init-method = true
ignore-init-module = false
ignore-magic = false
ignore-semiprivate = false
ignore-private = false
fail-under = 85
include = ["scripts/"]
verbose = 0
quiet = false
```

- [ ] **Step 3: Add [tool.darglint] config to pyproject.toml**

```toml
[tool.darglint]
strictness = long
ignore_regex = "^_"
```

Add per-path exclusions to the `[tool.ruff.lint.per-file-ignores]` section
for darglint compatibility. darglint is invoked via pre-commit in Phase 3,
not via ruff, so no ruff config change is needed here.

- [ ] **Step 4: Reinstall and run interrogate**

```bash
poetry install --sync
poetry run interrogate scripts/ --fail-under 85 --verbose
```

If interrogate reports coverage below 85% in `scripts/`, add Google-style
docstrings to the flagged functions. A minimal acceptable docstring:

```python
def my_function(arg: str) -> bool:
    """Check whether arg meets criteria.

    Args:
        arg: The string to evaluate.

    Returns:
        True if arg is non-empty, False otherwise.
    """
    return bool(arg)
```

- [ ] **Step 5: Run darglint on src/**

```bash
poetry run python -m darglint src/ 2>&1 | head -20
```

Fix any `DAR` errors by updating docstrings to match the actual function signatures. Do not add `# noqa: DAR` suppressions.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/ scripts/
git commit -m "feat: add darglint and interrogate for docstring quality

darglint validates Args/Returns/Raises sections match function signatures.
interrogate enforces 85% docstring coverage in scripts/.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 10: Create .qlty/qlty.toml

qlty is the unified quality runner per `~/.claude/.claude/standards/packages.md`. It is a standalone CLI, not a Python package.

**Files:**

- Create: `.qlty/qlty.toml`
- Modify: `README.md` (add qlty install step to dev setup)

- [ ] **Step 1: Install qlty CLI (if not already installed)**

```bash
qlty --version 2>/dev/null || curl https://qlty.sh | bash
```

- [ ] **Step 2: Create .qlty/qlty.toml**

```bash
mkdir -p .qlty
```

Create `.qlty/qlty.toml`:

```toml
[plugins]
enabled = ["ruff", "bandit"]

[ruff]
config = "pyproject.toml"

[bandit]
target = ["src"]
```

Note: basedpyright is not a qlty plugin; it is invoked via `poetry run basedpyright` in nox and pre-commit.

- [ ] **Step 3: Run qlty check to confirm it works**

```bash
qlty check
```

Expected: qlty reads `pyproject.toml` for ruff config and runs bandit against `src/`. Resolve any findings that are not already suppressed with a tracked justification.

- [ ] **Step 4: Add qlty install to README.md dev setup**

In `README.md`, find the development setup section. After `poetry install`, add:

```markdown
# Install qlty CLI (standalone, not a Python package)
curl https://qlty.sh | bash
# Then run quality checks
qlty check
```

- [ ] **Step 5: Commit**

```bash
git add .qlty/ README.md
git commit -m "feat: add qlty CLI configuration

qlty is the unified quality runner per global packages standard.
Configured with ruff and bandit plugins reading pyproject.toml.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 11: Align Ruff rule set with PyStrict standard

The current `[tool.ruff.lint]` select list is missing 12 PyStrict-aligned rule codes. The ignore list suppresses `BLE001` (blind exceptions) which conflicts with the global standard. The pylint max-branches setting is 18 (global standard is 12).

**Files:**

- Modify: `pyproject.toml` (lines 128-192)

- [ ] **Step 1: Record current lint state as baseline**

```bash
poetry run ruff check . 2>&1 | tail -5
```

Note the number of violations. After enabling new rules, violations will increase. Fix each one.

- [ ] **Step 2: Add missing rule codes to the select list**

In `pyproject.toml`, in the `[tool.ruff.lint]` `select` list, add these missing codes:

```toml
    "EM",   # flake8-errmsg: error message string literals
    "SLF",  # flake8-self: private member access
    "RSE",  # flake8-raise: raise statement best practices
    "FA",   # flake8-future-annotations
    "T10",  # flake8-debugger: no breakpoint() or pdb
    "TCH",  # flake8-type-checking: TYPE_CHECKING imports
    "FBT",  # flake8-boolean-trap
    "TRY",  # tryceratops: try/except structural patterns
    "FURB", # refurb: modernization
    "LOG",  # flake8-logging: logging best practices
    "ASYNC",# flake8-async: async/await best practices
    "C90",  # McCabe complexity (C901)
    "PERF", # perflint: performance anti-patterns
```

- [ ] **Step 3: Remove BLE001 from the ignore list**

In `pyproject.toml`, remove this line from `[tool.ruff.lint]` `ignore`:

```toml
    "BLE001",  # blind exception catching (needed for generic error handlers)
```

`BLE001` enforces catching specific exception types instead of bare `except Exception:`. This aligns with the global exception hierarchy rule. If any existing code catches `Exception` broadly, replace it with a specific exception type or the project's `AppError` base class.

- [ ] **Step 4: Fix pylint max-branches**

In `pyproject.toml`, change:

```toml
[tool.ruff.lint.pylint]
max-branches = 18      # Increased from default 12 for industry standards
max-statements = 75    # Increased from default 50 for industry standards
```

to:

```toml
[tool.ruff.lint.pylint]
max-branches = 12
max-statements = 75
```

- [ ] **Step 5: Update target-version**

In `pyproject.toml`, change:

```toml
target-version = "py311"
```

to:

```toml
target-version = "py312"
```

- [ ] **Step 6: Run ruff and fix all new violations**

```bash
poetry run ruff check . --fix
poetry run ruff check .
```

The `--fix` flag auto-fixes safe violations. For violations ruff cannot auto-fix:

- `EM101`/`EM102`: Move string literals out of `raise` statements:

  ```python
  # Before
  raise ValueError("message")
  # After
  msg = "message"
  raise ValueError(msg)
  ```

- `FBT001`/`FBT002`: Replace boolean positional args with keyword-only:

  ```python
  # Before
  def process(data, validate=True):
  # After
  def process(data, *, validate: bool = True):
  ```

- `TRY003`: Replace `raise Exception("message")` with typed exception:

  ```python
  # Before
  raise Exception("Something went wrong")
  # After (using project AppError base if defined, else specific type)
  raise RuntimeError("Something went wrong")
  ```

Run `poetry run ruff check .` after fixes. Repeat until 0 violations.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "fix: align Ruff rules with PyStrict global standard

Adds EM, SLF, RSE, FA, T10, TCH, FBT, TRY, FURB, LOG, ASYNC, C90, PERF.
Removes BLE001 from ignore list. Sets max-branches=12. Sets target=py312.
Fixes all violations surfaced by the new rules.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 3: Pre-commit

---

### Task 12: Create .pre-commit-config.yaml

The project has a `pre_commit` nox session (line 232) that calls `pre-commit run --all-files` but no config file for it to use. This task creates the config.

**Files:**

- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Confirm pre-commit is in dev dependencies**

```bash
grep "pre-commit" pyproject.toml
```

Expected: `pre-commit` appears in `[tool.poetry.group.dev.dependencies]`.

If it is absent, add it:

```toml
pre-commit = ">=3.6.0"
```

then run `poetry install --sync`.

- [ ] **Step 2: Create .pre-commit-config.yaml**

Create `.pre-commit-config.yaml`:

```yaml
repos:
  # Ruff: lint with autofix, then format check
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.12.3
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  # BasedPyright: strict type checking
  - repo: https://github.com/DetachHead/basedpyright
    rev: v1.1.400
    hooks:
      - id: basedpyright

  # Bandit: static security analysis
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.7
    hooks:
      - id: bandit
        args: [-r, src, -ll, -c, pyproject.toml]

  # detect-secrets: credential scanning
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: [--baseline, .secrets.baseline]
        exclude: poetry.lock

  # darglint: docstring argument validation
  - repo: https://github.com/terrencepreilly/darglint
    rev: v1.8.1
    hooks:
      - id: darglint

  # interrogate: docstring coverage in scripts/
  - repo: https://github.com/econchick/interrogate
    rev: 1.7.0
    hooks:
      - id: interrogate
        args: [--fail-under=85, scripts/]

  # commitizen: conventional commit message format
  - repo: https://github.com/commitizen-tools/commitizen
    rev: v4.4.1
    hooks:
      - id: commitizen
        stages: [commit-msg]

  # yamllint: YAML syntax and style
  - repo: https://github.com/adrienverge/yamllint
    rev: v1.35.1
    hooks:
      - id: yamllint
        args: [-c, .yamllint.yml]

  # markdownlint: Markdown formatting
  - repo: https://github.com/igorshubovych/markdownlint-cli
    rev: v0.43.0
    hooks:
      - id: markdownlint
        args: [--fix]

  # Em-dash guard: blocks the em-dash character (U+2014) in all text files
  - repo: local
    hooks:
      - id: no-em-dash
        name: No em-dashes
        language: pygrep
        entry: "\u2014"
        types: [text]
        description: "Blocks em-dash characters per global writing rule"
```

- [ ] **Step 3: Create the detect-secrets baseline**

```bash
poetry run detect-secrets scan > .secrets.baseline
```

Review `.secrets.baseline` to confirm it contains no real secrets. If it flags any, address those first.

- [ ] **Step 4: Install the hooks**

```bash
poetry run pre-commit install
poetry run pre-commit install --hook-type commit-msg
```

- [ ] **Step 5: Run pre-commit against all files**

```bash
poetry run pre-commit run --all-files
```

Fix any violations that are not auto-fixed. Common first-run findings:

- Trailing whitespace in markdown
- Missing newline at end of file
- yamllint indentation issues in `.github/workflows/`

Run again after fixes until it exits 0.

- [ ] **Step 6: Commit**

```bash
git add .pre-commit-config.yaml .secrets.baseline
git commit -m "feat: add pre-commit configuration

Wires ruff-format, ruff, basedpyright, bandit, detect-secrets, darglint,
interrogate, commitizen, yamllint, markdownlint, and an em-dash guard
into the pre-commit pipeline.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 13: Verify the nox pre_commit session works end-to-end

The nox session already exists at lines 232-235. Confirm it runs against the new config.

**Files:** none (verification only)

- [ ] **Step 1: Run the nox pre_commit session**

```bash
poetry run nox -s pre_commit
```

Expected: installs dev dependencies, runs `pre-commit run --all-files`, exits 0.

- [ ] **Step 2: Update CLAUDE.md Essential Commands**

In `CLAUDE.md`, find the Essential Commands section. Add under Code Quality:

```bash
# Run pre-commit on all files
poetry run pre-commit run --all-files
# Or via nox
poetry run nox -s pre_commit
```

- [ ] **Step 3: Commit the CLAUDE.md update**

```bash
git add CLAUDE.md
git commit -m "docs: add pre-commit commands to CLAUDE.md Essential Commands

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 4: CI Modernization

---

### Task 14: Look up action SHAs for all workflows

All GitHub Actions references use mutable version tags. This task resolves the commit SHA for each action version currently used so Tasks 15-18 can replace them.

**Files:** none (research task, results used in Tasks 15-18)

- [ ] **Step 1: Set up a helper function for SHA lookup**

```bash
get_action_sha() {
    local repo=$1  # e.g. "actions/checkout"
    local tag=$2   # e.g. "v4.2.2"
    local ref_response
    ref_response=$(gh api "repos/${repo}/git/ref/tags/${tag}" 2>/dev/null)
    local sha
    sha=$(echo "$ref_response" | jq -r '.object.sha')
    local type
    type=$(echo "$ref_response" | jq -r '.object.type')
    if [ "$type" = "tag" ]; then
        sha=$(gh api "repos/${repo}/git/tags/${sha}" --jq '.object.sha')
    fi
    echo "${sha}  # ${tag}"
}
```

- [ ] **Step 2: Get SHAs for all actions currently in use**

Run each lookup and record the output (40-char SHA + version comment):

```bash
# actions/checkout -- check GitHub releases for latest v4.x
get_action_sha actions/checkout v4.2.2

# actions/setup-python -- check GitHub releases for latest v5.x
get_action_sha actions/setup-python v5.3.0

# actions/cache
get_action_sha actions/cache v4.1.2

# actions/cache (restore subaction uses same repo)
# SHA is the same as actions/cache

# actions/upload-artifact
get_action_sha actions/upload-artifact v4.4.3

# github/codeql-action (all three subactions share the same repo)
get_action_sha github/codeql-action v3.27.0

# ossf/scorecard-action
get_action_sha ossf/scorecard-action v2.4.1

# step-security/harden-runner
get_action_sha step-security/harden-runner v2.12.0

# snok/install-poetry (used in renovate-auto-merge.yml)
get_action_sha snok/install-poetry v1.4.1

# fountainhead/action-wait-for-check (used in renovate-auto-merge.yml)
get_action_sha fountainhead/action-wait-for-check v1.2.0

# codecov/codecov-action -- only needed if keeping Codecov; will be removed in Task 18
get_action_sha codecov/codecov-action v4.5.0
```

Record all SHAs in a scratch file (do not commit it). They are used in Tasks 15-18.

- [ ] **Step 3: Verify SHAs are 40 characters**

```bash
# Each SHA should be exactly 40 hex characters
# If any are shorter, the lookup returned a tag object SHA, not a commit SHA
# Re-run the helper function to get the dereferenced commit SHA
```

---

### Task 15: Pin SHAs in codeql.yml and add harden-runner

**Files:**

- Modify: `.github/workflows/codeql.yml`

- [ ] **Step 1: Add harden-runner as the first step in the analyze job**

In `.github/workflows/codeql.yml`, in the `analyze` job, insert as the first step:

```yaml
    - name: Harden runner
      uses: step-security/harden-runner@<SHA-FROM-TASK-14>  # v2.12.0
      with:
        egress-policy: audit
```

- [ ] **Step 2: Pin actions/checkout (line 33)**

Change:

```yaml
    - name: Checkout repository
      uses: actions/checkout@v4
```

to:

```yaml
    - name: Checkout repository
      uses: actions/checkout@<SHA-FROM-TASK-14>  # v4.2.2
```

- [ ] **Step 3: Pin codeql-action/init (line 36)**

Change:

```yaml
      uses: github/codeql-action/init@v3
```

to:

```yaml
      uses: github/codeql-action/init@<SHA-FROM-TASK-14>  # v3.27.0
```

- [ ] **Step 4: Pin codeql-action/autobuild (line 42)**

Change:

```yaml
      uses: github/codeql-action/autobuild@v3
```

to:

```yaml
      uses: github/codeql-action/autobuild@<SHA-FROM-TASK-14>  # v3.27.0
```

Note: `init`, `autobuild`, and `analyze` all come from the same `codeql-action` repo at the same release, so they share the same commit SHA.

- [ ] **Step 5: Pin codeql-action/analyze (line 45)**

Change:

```yaml
      uses: github/codeql-action/analyze@v3
```

to:

```yaml
      uses: github/codeql-action/analyze@<SHA-FROM-TASK-14>  # v3.27.0
```

- [ ] **Step 6: Validate the YAML is well-formed**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/codeql.yml'))" && echo "Valid YAML"
```

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/codeql.yml
git commit -m "security: pin action SHAs in codeql.yml and add harden-runner

Replaces mutable version tags with immutable commit SHAs per git workflow
rule. Adds harden-runner egress auditing per org security standard.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 16: Pin SHAs in scorecard.yml

`scorecard.yml` already has `harden-runner`. Only SHA pinning is needed.

**Files:**

- Modify: `.github/workflows/scorecard.yml`

- [ ] **Step 1: Pin step-security/harden-runner (line 22)**

Change:

```yaml
        uses: step-security/harden-runner@v2.12
```

to:

```yaml
        uses: step-security/harden-runner@<SHA-FROM-TASK-14>  # v2.12.0
```

- [ ] **Step 2: Pin actions/checkout (line 27)**

Change `actions/checkout@v4` to `actions/checkout@<SHA>  # v4.2.2`

- [ ] **Step 3: Pin ossf/scorecard-action (line 32)**

Change `ossf/scorecard-action@v2.4` to `ossf/scorecard-action@<SHA>  # v2.4.1`

- [ ] **Step 4: Pin actions/upload-artifact (line 40)**

Change `actions/upload-artifact@v4` to `actions/upload-artifact@<SHA>  # v4.4.3`

- [ ] **Step 5: Pin github/codeql-action/upload-sarif (line 47)**

Change `github/codeql-action/upload-sarif@v3` to the codeql-action SHA with comment `# v3.27.0`

- [ ] **Step 6: Validate and commit**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/scorecard.yml'))" && echo "Valid YAML"
git add .github/workflows/scorecard.yml
git commit -m "security: pin action SHAs in scorecard.yml

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 17: Pin SHAs in renovate-auto-merge.yml

**Files:**

- Modify: `.github/workflows/renovate-auto-merge.yml`

- [ ] **Step 1: Pin all six actions**

Apply the same SHA pinning pattern to these actions found in the file:

| Line | Action | Tag |
|------|--------|-----|
| 22 | `step-security/harden-runner` | `v2.12` |
| 30 | `actions/checkout` | `v4` |
| 37 | `actions/setup-python` | `v5` |
| 42 | `snok/install-poetry` | `v1.4` |
| 49 | `actions/cache` | `v4` |
| 59 | `fountainhead/action-wait-for-check` | `v1.2` |

For each, replace the tag with the SHA from Task 14 and add the version as a comment.

- [ ] **Step 2: Validate and commit**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/renovate-auto-merge.yml'))" && echo "Valid YAML"
git add .github/workflows/renovate-auto-merge.yml
git commit -m "security: pin action SHAs in renovate-auto-merge.yml

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 18: Rewrite ci.yml as thin caller to org reusable workflow

The current `ci.yml` is 340 lines of duplicated setup. Replace with a thin caller that delegates to `ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@main`.

**Files:**

- Modify: `.github/workflows/ci.yml` (full rewrite)

- [ ] **Step 1: Read the current ci.yml to note what it does**

The current workflow runs: setup, unit-tests (matrix 3.11/3.12), integration-tests (matrix, PostgreSQL service), quality-checks (black, ruff, mypy, markdownlint, yamllint), security-scan (safety, bandit), ci-success gate.

The reusable workflow covers testing, linting, and type checking. Security scanning moves to a separate `security.yml` in Task 19.

- [ ] **Step 2: Replace ci.yml with the thin caller**

Overwrite `.github/workflows/ci.yml` with:

```yaml
name: CI

on:
  workflow_dispatch:
  pull_request:
    branches:
      - main
  push:
    branches:
      - main

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@main
    with:
      python-version: "3.11"
      python-versions-pr: '["3.11", "3.12"]'
      python-versions-comprehensive: '["3.11", "3.12"]'
      enable-matrix-testing: true
      coverage-threshold: 80
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

- [ ] **Step 3: Validate the YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "Valid YAML"
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: migrate to org reusable python-ci.yml workflow

Replaces 340-line inline CI with a thin caller. Reduces duplication,
inherits org-level hardening and matrix strategy from the reusable workflow.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 19: Add security.yml, sonarcloud.yml, and coverage.yml

These three new workflow files add capabilities that were missing or inline.

**Files:**

- Create: `.github/workflows/security.yml`
- Create: `.github/workflows/sonarcloud.yml`
- Create: `.github/workflows/coverage.yml`

- [ ] **Step 1: Read the org workflow signatures**

```bash
# See available inputs for each workflow
head -80 /home/byron/dev/.github/.github/workflows/python-security-analysis.yml
head -80 /home/byron/dev/.github/.github/workflows/python-sonarcloud.yml
head -80 /home/byron/dev/.github/.github/workflows/python-qlty-coverage.yml
```

Note the exact input names and required secrets before creating the callers.

- [ ] **Step 2: Create security.yml**

Create `.github/workflows/security.yml`:

```yaml
name: Security Analysis

on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main
  schedule:
    - cron: '0 8 * * 1'

jobs:
  security:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-security-analysis.yml@main
    with:
      source-directory: src
```

- [ ] **Step 3: Create sonarcloud.yml**

Create `.github/workflows/sonarcloud.yml`:

```yaml
name: SonarCloud

on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main

jobs:
  sonarcloud:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-sonarcloud.yml@main
    with:
      sonar-organization: ByronWilliamsCPA
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
```

- [ ] **Step 4: Create coverage.yml**

Create `.github/workflows/coverage.yml`:

```yaml
name: Coverage

on:
  push:
    branches:
      - main

jobs:
  coverage:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-qlty-coverage.yml@main
    with:
      coverage-artifact-name: coverage-report
    secrets:
      QLTY_COVERAGE_TOKEN: ${{ secrets.QLTY_COVERAGE_TOKEN }}
```

- [ ] **Step 5: Validate all three files**

```bash
for f in security.yml sonarcloud.yml coverage.yml; do
  python3 -c "import yaml; yaml.safe_load(open('.github/workflows/$f'))" && echo "$f: Valid"
done
```

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/security.yml .github/workflows/sonarcloud.yml .github/workflows/coverage.yml
git commit -m "ci: add security, SonarCloud, and Qlty coverage workflows

Security is now blocking (no continue-on-error). SonarCloud and Qlty
coverage were previously absent. All delegate to org reusable workflows.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 20: Create .github/copilot-instructions.md

This file scopes GitHub Copilot PR review to the categories that automated linters cannot catch.

**Files:**

- Create: `.github/copilot-instructions.md`

- [ ] **Step 1: Create the file**

Create `.github/copilot-instructions.md`:

```markdown
# GitHub Copilot PR Review Instructions

Review pull requests for the following categories. Do not comment on style,
formatting, or linting -- pre-commit and ruff handle those automatically.

## Focus Areas

**Business logic correctness**
Verify the implementation matches the intent described in the PR description.
Flag cases where the code does the wrong thing correctly.

**Error handling completeness**
Check that all external calls (database, API, file I/O) have error paths.
Flag broad `except Exception:` blocks that swallow failures silently.

**Edge cases**
Look for inputs that would cause unexpected behavior: empty collections,
None values, zero, negative numbers, empty strings, concurrent access.

**Concurrency and state**
Flag shared mutable state that could cause race conditions.
Check that database transactions are scoped correctly.

**Security logic**
Check for injection vulnerabilities in SQL or shell calls.
Verify secrets are not logged or returned in API responses.
Flag hardcoded credentials or tokens.

## Leave as advisory

All Copilot comments are advisory. Do not block merge based solely on
Copilot findings. Flag critical issues explicitly with "CRITICAL:" prefix.
```

- [ ] **Step 2: Commit**

```bash
git add .github/copilot-instructions.md
git commit -m "docs: add copilot-instructions.md for PR review scope

Scopes GitHub Copilot review to business logic, error handling, edge
cases, concurrency, and security -- areas linters cannot check.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 5: .claude/ and Docs Cleanup

---

### Task 21: Create project .claude/settings.json

**Files:**

- Create: `.claude/settings.json`

- [ ] **Step 1: Create the settings file**

Create `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(poetry run *)",
      "Bash(nox *)",
      "Bash(poetry run nox *)",
      "Bash(pre-commit *)",
      "Bash(poetry run pre-commit *)",
      "Bash(qlty *)",
      "Bash(poetry run pip-audit)",
      "Bash(git status)",
      "Bash(git log *)",
      "Bash(git diff *)",
      "Bash(git add *)",
      "Bash(git commit *)"
    ]
  }
}
```

- [ ] **Step 2: Verify the JSON is valid**

```bash
python3 -c "import json; json.load(open('.claude/settings.json'))" && echo "Valid JSON"
```

- [ ] **Step 3: Commit**

```bash
git add .claude/settings.json
git commit -m "chore: add project .claude/settings.json with tool permissions

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 22: Update CLAUDE.md with RAD markers, model selection, and corrected commands

**Files:**

- Modify: `CLAUDE.md`

- [ ] **Step 1: Add RAD section**

Append to `CLAUDE.md`:

```markdown
## Response-Aware Development (RAD)

Tag assumptions that could cause production failures using these markers in
code comments. Mandatory for: timing dependencies, external resources,
data integrity, concurrency, security, financial calculations.

- `#CRITICAL` -- assumption failure causes data loss or security breach
- `#ASSUME` -- assumption made without verification
- `#EDGE` -- edge case that needs explicit handling
- `#VERIFY` -- verification instruction paired with the above markers

Example:
```python
# #ASSUME: OpenFIGI rate limit is 10 req/s -- #VERIFY before production load
# #EDGE: empty ticker string returns None, not raises -- test this
```

- [ ] **Step 2: Add Model Selection section**

Append to `CLAUDE.md`:

```markdown
## Model Selection

| Task type | Model | When |
| --- | --- | --- |
| Architecture, planning, ADRs | Opus 4.7 | Multi-step decisions, deep code review |
| Standard development | Sonnet 4.6 | Most coding, editing, PR descriptions |
| Read-only exploration | Haiku 4.5 | File scanning, structure mapping, quick lookups |
```

- [ ] **Step 3: Fix Essential Commands section**

In the Code Quality subsection of Essential Commands, replace:

```bash
poetry run black .
...
poetry run mypy src
...
poetry run safety check
```

with:

```bash
poetry run ruff format .
poetry run ruff check --fix .
poetry run basedpyright
poetry run pip-audit
```

- [ ] **Step 4: Scan for em-dashes in CLAUDE.md**

```bash
grep -n $'\xe2\x80\x94' CLAUDE.md || echo "No em-dashes found"
```

If any are found, replace each em-dash with a comma, colon, semicolon, or restructured sentence.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add RAD markers, model selection, and fix Essential Commands

Updates CLAUDE.md with Response-Aware Development tagging guide, model
selection table, and corrects tool references removed in Phase 2.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 23: Em-dash scan across all project documentation

**Files:**

- Modify: any `.md` files in `docs/`, `.github/`, `schema_exports/`, and project root that contain em-dashes (U+2014)

- [ ] **Step 1: Find all em-dashes in the project**

```bash
grep -rn $'\xe2\x80\x94' docs/ .github/ schema_exports/ *.md 2>/dev/null
```

Record every file and line number.

- [ ] **Step 2: Fix each occurrence**

For each em-dash found, replace with the appropriate punctuation:

| Original pattern | Replacement |
|-----------------|-------------|
| `X (em-dash) which Y (em-dash) Z` | `X (which Y) Z` or `X, which Y, Z` |
| `X (em-dash) Y` (pause/aside) | `X: Y` or `X; Y` |
| `X (em-dash) Y` (contrast) | `X, but Y` or `X. Y` |

- [ ] **Step 3: Confirm clean**

```bash
grep -rn $'\xe2\x80\x94' docs/ .github/ schema_exports/ *.md 2>/dev/null || echo "No em-dashes remain"
```

Expected: `No em-dashes remain`.

- [ ] **Step 4: Commit**

```bash
git add docs/ .github/ schema_exports/ *.md
git commit -m "docs: remove all em-dashes from project documentation

Replaces em-dash characters with commas, colons, and semicolons per
global writing rule.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 24: Relocate AGENTS.md and GEMINI.md to project root

Agent runners expect `AGENTS.md` at the project root. Gemini CLI expects `GEMINI.md` at the project root. Both currently live at `docs/project/`.

**Files:**

- Move: `docs/project/AGENTS.md` → `AGENTS.md`
- Move: `docs/project/GEMINI.md` → `GEMINI.md`

- [ ] **Step 1: Move both files**

```bash
git mv docs/project/AGENTS.md AGENTS.md
git mv docs/project/GEMINI.md GEMINI.md
```

- [ ] **Step 2: Check for internal cross-references to the old paths**

```bash
grep -rn "docs/project/AGENTS.md\|docs/project/GEMINI.md" . --include="*.md" || echo "No broken references"
```

For any match found, update the link to point to the new root-level path.

- [ ] **Step 3: Verify both files are at the root**

```bash
ls -la AGENTS.md GEMINI.md
```

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md GEMINI.md
git commit -m "chore: relocate AGENTS.md and GEMINI.md to project root

Agent runners and Gemini CLI expect these files at the repository root,
not in docs/project/.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

### Spec Coverage Check

| Spec section | Covered by task |
|-------------|----------------|
| Phase 0: Relocate project root | Task 1 |
| SECURITY.md, CONTRIBUTING.md | Task 2 |
| CHANGELOG.md, CODEOWNERS | Task 3 |
| .gitignore, pyproject.toml metadata, known-vulnerabilities.md | Task 4 |
| CLAUDE.md Phase 1 additions | Task 5 |
| Remove Black, Ruff format | Task 6 |
| Remove MyPy, BasedPyright | Task 7 |
| Remove safety | Task 8 |
| darglint, interrogate | Task 9 |
| .qlty/qlty.toml | Task 10 |
| Ruff rule alignment | Task 11 |
| .pre-commit-config.yaml | Task 12 |
| nox pre_commit verification | Task 13 |
| Action SHA lookup | Task 14 |
| codeql.yml SHA pin + harden-runner | Task 15 |
| scorecard.yml SHA pin | Task 16 |
| renovate-auto-merge.yml SHA pin | Task 17 |
| ci.yml rewrite | Task 18 |
| security.yml, sonarcloud.yml, coverage.yml | Task 19 |
| .github/copilot-instructions.md | Task 20 |
| .claude/settings.json | Task 21 |
| CLAUDE.md RAD, model selection, fix commands | Task 22 |
| Em-dash scan | Task 23 |
| AGENTS.md, GEMINI.md relocation | Task 24 |

All 35 gaps from the spec are covered. No gaps found.

### Placeholder Check

The only placeholder-style text is in Tasks 15-17 (`<SHA-FROM-TASK-14>`), which are references to values computed by Task 14 using executable `gh api` commands. These are deliberate cross-task references, not forgotten content.

### Type Consistency Check

No new types or APIs are introduced. All tasks operate on existing files, config blocks, and shell commands. No cross-task type inconsistencies apply.
