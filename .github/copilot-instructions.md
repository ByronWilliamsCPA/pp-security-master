# GitHub Copilot Code Review Instructions

This file tunes Copilot review behavior for the pp-security-master project.
Copilot is auto-requested by the `copilot_code_review` rule in the org ruleset;
this file does not trigger reviews, it configures them.

## Focus areas

- Business logic correctness in the security classification pipeline (fund, equity, bond)
- Error handling completeness in broker file parsers (extractor/) and OpenFIGI API calls
- Edge cases in taxonomy mapping (GICS, TRBC, CFI classification chains)
- SQL injection and input validation for user-supplied broker file data
- Concurrency issues in database writes and API rate-limit retry logic
- Security logic flaws in secrets handling and environment variable access

## Exclude from review

- Code style, formatting, and whitespace: enforced by pre-commit hooks and ruff
- Import ordering: enforced by ruff
- Type annotation style: enforced by basedpyright in strict mode
- Test file boilerplate: focus on assertion correctness, not structure
