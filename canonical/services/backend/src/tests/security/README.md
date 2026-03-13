---
processed: true
processed_date: 2025-12-09
themes:
  - testing
  - backend
  - frontend
  - quality-assurance
modules:
  - backend
  - frontend
  - testing
code_verified: true
dead_docs_found: false
---
# Security Tests

This directory contains security-focused tests for the ScareVerse backend, including Static Application Security Testing (SAST) baseline validation.

## Overview

Security testing is a critical part of our development process. These tests ensure that:
- No critical or high severity vulnerabilities are introduced
- Security baseline is maintained across code changes
- SAST tools are properly configured and running

## Test Files

### `test_sast_baseline.py`
Validates that Bandit SAST scans report zero CRITICAL and HIGH severity vulnerabilities.

**Tests included:**
- `test_no_critical_vulnerabilities()` - Ensures no CRITICAL severity issues
- `test_no_high_vulnerabilities()` - Ensures no HIGH severity issues
- `test_medium_vulnerabilities_documented()` - Tracks MEDIUM severity issues
- `test_bandit_configuration_exists()` - Validates `.bandit` config file
- `test_security_scan_performance()` - Ensures scan completes in <30s
- `test_scan_coverage()` - Validates scan covers all Python files

## Running Security Tests

### Run all security tests
```bash
cd backend
pytest tests/security/ -v
```

### Run only SAST baseline tests
```bash
cd backend
pytest tests/security/test_sast_baseline.py -v
```

### Run with coverage
```bash
cd backend
pytest tests/security/ --cov=app --cov-report=term
```

## SAST Configuration

### Bandit Configuration
Location: `backend/.bandit`

The configuration specifies:
- **Excluded directories**: `/tests/`, `/venv/`, `/.venv/`
- **Security tests**: Focus on critical issues (pickle, eval, SQL injection, shell injection, etc.)
- **Severity threshold**: MEDIUM and above reported by default

### Running Bandit Manually

```bash
cd backend

# Run with default configuration
bandit -r app -c .bandit -f screen

# Generate JSON report
bandit -r app -c .bandit -f json -o bandit_report.json

# Generate HTML report
bandit -r app -c .bandit -f html -o bandit_report.html

# Only show HIGH severity issues
bandit -r app -c .bandit -ll -ii -f screen
```

## CI/CD Integration

Security tests are integrated into the CI/CD pipeline:

### GitHub Actions Workflow
**File**: `.github/workflows/sast-backend.yml`

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests
- Daily scheduled scan (02:00 UTC)
- Manual workflow dispatch

**What it does:**
1. Runs Bandit SAST scan
2. Generates JSON and HTML reports
3. Fails build if HIGH severity vulnerabilities found
4. Posts PR comment with security summary
5. Uploads reports as artifacts

### Pre-commit Hook (Optional)
Add to `.pre-commit-config.yaml`:

```yaml
  - repo: https://github.com/PyCQA/bandit
    rev: '1.7.7'
    hooks:
      - id: bandit
        args: ['-c', 'backend/.bandit', '-r', 'backend/app']
```

## Security Vulnerability Severity Levels

### CRITICAL ❌
**Action:** Must fix immediately, blocks deployment
**Examples:** Remote code execution, authentication bypass

### HIGH ❌
**Action:** Must fix before merge
**Examples:** SQL injection, hardcoded credentials, insecure crypto

### MEDIUM ⚠️
**Action:** Review and document if acceptable
**Examples:** Weak hash functions, insecure temp file usage

### LOW ℹ️
**Action:** Review when convenient
**Examples:** Subprocess usage, try-except-pass patterns

## Current Security Baseline

As of the latest scan:
- **CRITICAL**: 0 ✅
- **HIGH**: 0 ✅
- **MEDIUM**: 0 ✅
- **LOW**: 8 (documented and acceptable)

## Handling Security Issues

### If a vulnerability is found:

1. **Assess severity and impact**
2. **Fix if possible**
   - Update code to remove vulnerability
   - Re-run bandit to verify fix
3. **Document if acceptable**
   - Add `# nosec B###` comment with justification
   - Update `ACCEPTED_MEDIUM_COUNT` in tests if MEDIUM severity
4. **Create security exception**
   - Document in `docs/security/SAST_SETUP.md`
   - Get approval from security review

### Example: Suppressing a false positive
```python
# nosec B310 - URL scheme validated before use
urllib.request.urlretrieve(validated_url, output_path)
```

## Test Coverage Requirements

Security tests must maintain:
- **90% coverage** of security test code itself
- **All security-critical paths** covered by baseline tests
- **Performance**: Security tests complete in <30 seconds

## Documentation

For detailed SAST setup and configuration, see:
- [SAST Setup Guide](../../docs/security/SAST_SETUP.md)
- [Test Architecture](../../docs/ARQUITETURA_TESTES.md#6-testes-de-segurança-sast)
- [Security Summary](../../SECURITY.md)

## Troubleshooting

### Bandit not found
```bash
pip install bandit[toml]==1.7.7
```

### PyYAML import error in tests
```bash
pip install pyyaml
```

### Test fails on CI but passes locally
- Ensure `.bandit` config is committed
- Check Python version matches (3.10)
- Verify bandit version matches (1.7.7)

## Contributing

When adding new security tests:
1. Follow existing test patterns
2. Document test purpose clearly
3. Ensure tests run in <5 seconds each
4. Update this README with new tests

## References

- [Bandit Documentation](https://bandit.readthedocs.io/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Database](https://cwe.mitre.org/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
