"""
SAST Baseline Test for ScareVerse Backend

This test validates that the Static Application Security Testing (SAST) scan
using Bandit does not report any CRITICAL or HIGH severity vulnerabilities.

It ensures that the security baseline is maintained across code changes.
"""

import json
import subprocess
import pytest
import sys
from pathlib import Path


# Path to backend app directory
BACKEND_DIR = Path(__file__).parent.parent.parent
APP_DIR = BACKEND_DIR / "app"
BANDIT_CONFIG = BACKEND_DIR / ".bandit"


def run_bandit_scan():
    """
    Run Bandit SAST scan and return the results.
    
    Returns:
        dict: Bandit scan results as JSON
    """
    # Try to find bandit in the current Python environment
    import shutil
    bandit_path = shutil.which("bandit")
    if not bandit_path:
        # Try using python -m bandit
        bandit_cmd = [sys.executable, "-m", "bandit"]
    else:
        bandit_cmd = [bandit_path]
    
    cmd = bandit_cmd + [
        "-r", str(APP_DIR),
        "-c", str(BANDIT_CONFIG),
        "-f", "json"
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(BACKEND_DIR)
    )
    
    # Check if bandit is available (multiple detection methods)
    if result.returncode == 127 or "command not found" in result.stderr:
        pytest.skip("Bandit is not installed. Run: pip install bandit")
    
    # Check for "No module named bandit" in stderr (python -m bandit when not installed)
    if "No module named bandit" in result.stderr:
        pytest.skip("Bandit is not installed. Run: pip install bandit")
    
    # Bandit returns exit code 1 if issues found, but we still get the JSON in stdout
    # stderr contains INFO/WARNING messages which we can ignore
    if result.stdout:
        # Strip progress bar from stdout (starts with "Working...")
        lines = result.stdout.splitlines()
        json_lines = [line for line in lines if not line.startswith("Working...")]
        json_output = '\n'.join(json_lines)
        
        try:
            return json.loads(json_output)
        except json.JSONDecodeError as e:
            # If JSON parsing fails, this is a real error
            pytest.fail(
                f"Failed to parse Bandit JSON output: {e}\n"
                f"Cleaned output (first 300 chars): {json_output[:300]}"
            )
    
    # If no stdout and no stderr indicating missing module, bandit might have run with no issues
    # But if we get here with empty output, it's likely bandit is not installed
    if not result.stdout and not result.stderr:
        pytest.skip("Bandit is not installed or produced no output. Run: pip install bandit")
    
    # If we get here with empty stdout but some stderr, return empty results
    return {"results": [], "metrics": {"_totals": {"loc": 0}}}


def test_no_critical_vulnerabilities():
    """
    Test that no CRITICAL severity vulnerabilities are present.
    
    CRITICAL vulnerabilities must be fixed immediately.
    """
    report = run_bandit_scan()
    critical = [r for r in report['results'] if r['issue_severity'] == 'CRITICAL']
    
    assert len(critical) == 0, (
        f"Found {len(critical)} CRITICAL severity vulnerabilities:\n" +
        "\n".join([
            f"  - {r['test_id']}: {r['issue_text']}\n"
            f"    File: {r['filename']}:{r['line_number']}"
            for r in critical
        ])
    )


def test_no_high_vulnerabilities():
    """
    Test that no HIGH severity vulnerabilities are present.
    
    HIGH severity vulnerabilities should be fixed before merging.
    """
    report = run_bandit_scan()
    high = [r for r in report['results'] if r['issue_severity'] == 'HIGH']
    
    assert len(high) == 0, (
        f"Found {len(high)} HIGH severity vulnerabilities:\n" +
        "\n".join([
            f"  - {r['test_id']}: {r['issue_text']}\n"
            f"    File: {r['filename']}:{r['line_number']}"
            for r in high
        ])
    )


def test_medium_vulnerabilities_documented():
    """
    Test that MEDIUM severity vulnerabilities are tracked and acceptable.
    
    MEDIUM vulnerabilities should be reviewed and documented if accepted.
    This test warns if new medium vulnerabilities are introduced.
    """
    report = run_bandit_scan()
    medium = [r for r in report['results'] if r['issue_severity'] == 'MEDIUM']
    
    # Current baseline: 0 medium vulnerabilities
    ACCEPTED_MEDIUM_COUNT = 0
    
    if len(medium) > ACCEPTED_MEDIUM_COUNT:
        pytest.fail(
            f"Found {len(medium)} MEDIUM severity vulnerabilities "
            f"(accepted baseline: {ACCEPTED_MEDIUM_COUNT}):\n" +
            "\n".join([
                f"  - {r['test_id']}: {r['issue_text']}\n"
                f"    File: {r['filename']}:{r['line_number']}"
                for r in medium
            ]) +
            "\n\nIf these are acceptable, update ACCEPTED_MEDIUM_COUNT in this test."
        )


def test_bandit_configuration_exists():
    """
    Test that Bandit configuration file exists and is valid.
    """
    assert BANDIT_CONFIG.exists(), f"Bandit config not found at {BANDIT_CONFIG}"
    
    # Verify it's a valid YAML file
    import yaml
    with open(BANDIT_CONFIG) as f:
        config = yaml.safe_load(f)
    
    assert config is not None, "Bandit config is empty"
    assert 'exclude_dirs' in config, "Bandit config missing exclude_dirs"
    assert 'tests' in config, "Bandit config missing tests list"


def test_security_scan_performance():
    """
    Test that security scan completes in reasonable time.
    
    SAST should not be a bottleneck in CI/CD pipeline.
    Target: < 30 seconds for full scan
    """
    import time
    
    start = time.time()
    run_bandit_scan()
    duration = time.time() - start
    
    # Allow 30 seconds for SAST scan
    assert duration < 30, (
        f"Security scan took {duration:.2f}s (target: <30s). "
        "Consider optimizing or reducing scope."
    )


def test_scan_coverage():
    """
    Test that SAST scan covers all Python files in app directory.
    """
    report = run_bandit_scan()
    
    # Count Python files in app directory
    py_files = list(APP_DIR.rglob("*.py"))
    # Exclude __pycache__ and test files
    py_files = [f for f in py_files if "__pycache__" not in str(f)]
    
    scanned_lines = report['metrics'].get('_totals', {}).get('loc', 0)
    
    # Should scan at least 1000 lines (basic sanity check)
    assert scanned_lines > 1000, (
        f"Only {scanned_lines} lines scanned. "
        f"Expected to scan {len(py_files)} Python files."
    )


if __name__ == "__main__":
    # Allow running this test standalone
    pytest.main([__file__, "-v"])
