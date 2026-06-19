# Pull Request

## Type of Change
<!-- Mark the appropriate box with an "x" -->
- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📚 Documentation update
- [ ] 🔧 Maintenance (dependency updates, refactoring, etc.)
- [ ] 🔒 Security update
- [ ] 📊 Database schema change

## Description
<!-- Provide a brief description of the changes -->

## Security Impact
<!-- For security-master service, describe any security implications -->
- [ ] No security-sensitive changes
- [ ] Changes to classification logic
- [ ] Database schema changes
- [ ] External API integration changes
- [ ] File processing changes

## Testing
<!-- Describe the tests that you ran to verify your changes -->
- [ ] Tests pass locally with `uv run pytest`
- [ ] Code follows the style guidelines (`uv run ruff format .` and `uv run ruff check .`)
- [ ] Type checking passes (`uv run basedpyright`)
- [ ] Security scans pass (`uv run pip-audit` and `uv run bandit -r src`)
- [ ] Database migrations tested (if applicable)
- [ ] Classification accuracy validated (if applicable)

## Database Changes (if applicable)
<!-- For database schema changes -->
- [ ] Migration scripts created
- [ ] Backup/rollback plan documented
- [ ] Test data validated
- [ ] Performance impact assessed

## Classification Changes (if applicable)
<!-- For changes affecting security classification -->
- [ ] Classification accuracy tested
- [ ] OpenFIGI API integration validated
- [ ] pp-portfolio-classifier compatibility verified
- [ ] Fallback scenarios tested

## Checklist
<!-- Ensure all items are checked before requesting review -->
- [ ] Code follows project style guidelines
- [ ] Self-review of the code has been performed
- [ ] Code is properly commented, particularly in hard-to-understand areas
- [ ] Corresponding changes to documentation have been made
- [ ] Changes generate no new warnings
- [ ] Tests have been added that prove the fix is effective or that the feature works
- [ ] New and existing unit tests pass locally
- [ ] Any dependent changes have been merged and published

## Additional Context
<!-- Add any other context, screenshots, or relevant information -->

---

## For Reviewers

### Security Review

- [ ] No sensitive data exposure
- [ ] API keys/credentials properly handled
- [ ] Input validation adequate
- [ ] Dependencies reviewed for vulnerabilities

### Portfolio Performance Integration

- [ ] XML/JSON output format validated
- [ ] Backward compatibility maintained
- [ ] Import/export functionality verified
