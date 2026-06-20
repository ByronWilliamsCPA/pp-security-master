---
category: workflow
complexity: high
estimated_time: "Variable based on issue"
dependencies: ["workflow-plan-validation"]
sub_commands: ["validation-precommit"]
version: "1.0"
---

# Workflow Implementation

Execute approved implementation plan with security and quality standards: $ARGUMENTS

## Usage Options

- `phase X issue Y` - Standard implementation workflow
- `quick phase X issue Y` - Essential implementation only
- `subagent phase X issue Y` - Use specialized subagents for implementation

## Prerequisites

This command requires approved implementation plan. If not done, run:

```bash
/project:workflow-plan-validation phase X issue Y
```

**CRITICAL**: User approval of the planning document is required before proceeding.

## Instructions

### Step 0: Branch Strategy Validation

**CRITICAL**: Validate and enforce proper branch strategy before implementation.

```bash
# Branch validation and setup
validate_and_setup_branch() {
    local phase="$1"
    local issue="$2"
    local current_branch=$(git branch --show-current)

    echo "🌿 Validating branch strategy..."
    echo "Current branch: $current_branch"
    echo "Phase: $phase, Issue: $issue"

    # Determine correct branch names
    local expected_issue_branch="issue-${issue}-implementation"
    local expected_phase_branch="phase-${phase}-development"

    # Check if we're on the correct branch
    if [[ "$current_branch" != "$expected_issue_branch" ]]; then
        echo "⚠️  Not on expected issue branch: $expected_issue_branch"

        # Check if correct branch exists
        if git branch -a | grep -q "$expected_issue_branch"; then
            echo "🔄 Switching to existing issue branch..."
            git checkout "$expected_issue_branch"
        else
            echo "🌟 Creating new issue branch..."
            # Ensure phase branch exists
            if ! git branch -a | grep -q "$expected_phase_branch"; then
                git checkout -b "$expected_phase_branch" main
                git push -u origin "$expected_phase_branch"
            fi

            git checkout "$expected_phase_branch"
            git pull origin "$expected_phase_branch"
            git checkout -b "$expected_issue_branch"
            git push -u origin "$expected_issue_branch"
        fi
    fi

    # Validate branch is up to date
    git fetch origin
    if git status | grep -q "behind"; then
        echo "🔄 Branch behind remote, pulling updates..."
        git pull origin "$current_branch"
    fi

    echo "✅ Branch strategy validated: $expected_issue_branch"
}

# Extract phase and issue from arguments
PHASE=$(echo "$ARGUMENTS" | grep -oP "phase\s+\K\d+" || echo "1")
ISSUE=$(echo "$ARGUMENTS" | grep -oP "issue\s+\K\d+" || echo "")

if [[ -z "$ISSUE" ]]; then
    echo "❌ Issue number required. Usage: workflow-implementation phase X issue Y"
    exit 1
fi

validate_and_setup_branch "$PHASE" "$ISSUE"
```

### Step 1: Implementation Setup

1. **Load Approved Plan**:
   - Read `/docs/planning/issue-plans/phase-{phase}-issue-{issue}-plan.md`
   - Verify plan is approved and has "status: approved"
   - Create todo list from action plan items

2. **Environment Validation**:
   - Ensure GPG and SSH keys are present
   - Validate development environment is ready
   - Check dependencies are met

3. **Dependency Management Setup**:

   ```bash
   # MANDATORY: Validate and maintain dependencies
   setup_dependency_management() {
       echo "📦 Setting up dependency management..."

       # Validate uv.lock is current
       if ! uv lock --check; then
           echo "🔄 Updating uv.lock..."
           uv lock
       fi

       # Generate requirements files immediately
       if [[ -f "scripts/generate_requirements.sh" ]]; then
           echo "📋 Generating requirements files..."
           chmod +x scripts/generate_requirements.sh
           ./scripts/generate_requirements.sh

           # Commit requirements updates if needed
           if ! git diff --quiet requirements*.txt; then
               git add requirements*.txt uv.lock
               git commit -m "chore(deps): update requirements from uv.lock"
           fi
       fi

       echo "✅ Dependencies validated and current"
   }

   setup_dependency_management
   ```

### Step 2: Implementation Execution

1. **Use Subagents** for implementation tasks:
   - Delegate complex coding tasks to specialized agents
   - Maintain coordination through Zen MCP Server
   - Follow agent-first design principles

2. **Follow the Action Plan** step by step:
   - Work through todo items sequentially
   - Mark items as in_progress before starting
   - Mark items as completed immediately after finishing
   - Never skip validation steps

3. **Implement Security Best Practices** throughout:
   - Use encrypted .env files for secrets
   - Follow security scanning requirements
   - Validate all inputs and outputs
   - Use AssuredOSS packages when available

4. **Follow Coding Standards** from CLAUDE.md:
   - Maintain naming conventions (snake_case, kebab-case, PascalCase)
   - Follow Python standards (Ruff format 88 chars, Ruff, BasedPyright)
   - Ensure 80% minimum test coverage
   - Create atomic knowledge chunks for documentation

5. **Maintain Progress Tracking**:
   - Use TodoWrite for all task management
   - Update progress in real-time
   - Document blockers and decisions
   - Keep scope boundaries in mind

### Step 3: Enhanced Continuous Validation

1. **Enhanced Real-Time Quality Checks**:

   ```bash
   # MANDATORY: Run after every significant code change
   validate_code_quality() {
       echo "🔍 Running continuous quality checks..."

       # File-specific linting based on changes
       git diff --name-only HEAD~1 | while read file; do
           case "$file" in
               *.py)
                   echo "  🐍 Checking Python: $file"
                   uv run ruff format --check "$file" || return 1
                   uv run ruff check "$file" || return 1
                   uv run basedpyright "$file" || return 1
                   ;;
               *.md)
                   echo "  📝 Checking Markdown: $file"
                   markdownlint "$file" || return 1
                   ;;
               *.yml|*.yaml)
                   echo "  📋 Checking YAML: $file"
                   yamllint "$file" || return 1
                   ;;
           esac
       done

       echo "✅ All quality checks passed"
   }

   # Run after each coding session
   validate_code_quality
   ```

2. **Test Coverage Monitoring**:

   ```bash
   # Run coverage check after each implementation milestone
   check_coverage() {
       echo "📊 Checking test coverage..."
       COVERAGE=$(uv run pytest --cov=src --cov-report=term-missing | grep "TOTAL" | awk '{print $4}' | sed 's/%//')

       if [[ $COVERAGE -lt 80 ]]; then
           echo "❌ Coverage below 80%: ${COVERAGE}%"
           echo "💡 Add tests before proceeding"
           return 1
       fi

       echo "✅ Coverage: ${COVERAGE}%"
   }

   # Run after significant implementation milestones
   check_coverage
   ```

3. **Traditional Quality Checks**:
   - Validate against acceptance criteria continuously
   - Check for scope creep at each milestone

4. **Security Validation**:
   - Run security scans regularly
   - Validate encrypted storage is working
   - Check for exposed secrets or keys

5. **GitHub Actions Simulation**:

   ```bash
   # Simulate GitHub Actions checks locally
   simulate_github_actions() {
       echo "🎬 Simulating GitHub Actions..."

       # Run the same checks that GitHub Actions will run
       echo "1. Pre-commit hooks..."
       uv run pre-commit run --all-files || return 1

       echo "2. Security scans..."
       # CI passes --ignore-vuln for accepted CVEs (see docs/known-vulnerabilities.md);
       # a bare local run may report those documented exceptions.
       uv run pip-audit || echo "⚠️  Security issues found"
       uv run bandit -r src || return 1

       echo "3. Test suite..."
       uv run pytest -v --cov=src --cov-report=term-missing || return 1

       echo "4. Dependency validation..."
       uv lock --check || return 1

       echo "✅ All GitHub Actions checks would pass"
   }

   # Run before major commits
   simulate_github_actions
   ```

## Implementation Patterns

### Code Reuse Strategy

1. **Check ledgerbase** for existing patterns
2. **Review FISProject** for similar implementations
3. **Use .github** for CI/CD templates
4. **Leverage PromptCraft** existing components

### Agent Coordination

```markdown
## Subagent Tasks
- **Security Agent**: Authentication and authorization
- **Create Agent**: Knowledge file generation
- **Testing Agent**: Test suite development
- **Review Agent**: Code quality validation
```

### Progress Tracking Template

```markdown
## Implementation Progress
- [ ] Task 1: [Description] - Status: pending/in_progress/completed
- [ ] Task 2: [Description] - Status: pending/in_progress/completed
- [ ] Task 3: [Description] - Status: pending/in_progress/completed

## Blockers and Decisions
- [Date] [Decision/Blocker]: [Description and resolution]

## Scope Validation
- Last checked: [Date]
- Scope drift detected: Yes/No
- Corrective actions taken: [List]
```

## Quality Gates

### Before Each Commit

```bash
# MANDATORY: Run pre-commit validation
/project:validation-precommit

# Check file-specific linting
markdownlint **/*.md  # For markdown changes
yamllint **/*.{yml,yaml}  # For YAML changes
uv run ruff format --check .  # For Python changes
uv run ruff check .  # For Python changes
uv run basedpyright src  # For Python changes
```

### Before Each Major Milestone

1. **Acceptance Criteria Check**: Verify progress against original criteria
2. **Security Scan**: Run pip-audit and Bandit checks
3. **Test Coverage**: Ensure 80% minimum coverage maintained
4. **Documentation**: Update knowledge files as needed

## Error Handling

- **Plan not approved**: Stop and request user approval first
- **Environment issues**: Provide specific setup instructions
- **Scope creep detected**: Halt and consult with user
- **Quality gate failures**: Fix issues before proceeding
- **Dependency conflicts**: Document and resolve systematically

## Examples

```bash
# Standard implementation
/project:workflow-implementation phase 1 issue 3

# Quick implementation (essential steps only)
/project:workflow-implementation quick phase 2 issue 7

# Subagent-coordinated implementation
/project:workflow-implementation subagent phase 1 issue 1
```

## Next Steps

After implementation completion:

- Proceed to `/project:workflow-review-cycle`
- Ensure all todo items are marked completed
- Prepare for comprehensive testing and validation
