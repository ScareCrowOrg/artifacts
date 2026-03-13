"""
Pytest configuration and fixtures for backend tests.

This conftest.py file is located at backend/tests/ and provides:
- Python path configuration to enable 'app' module imports
- Shared fixtures for all backend tests

The main purpose is to ensure tests can import from the 'app' module
by adding the backend directory to sys.path.
"""

import os
import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock

# CRITICAL: Set environment variables BEFORE any app imports
# This ensures config.py reads these values during module initialization
os.environ.setdefault('ENCRYPTION_KEY', 'test-secret-key-for-testing-minimum-32-characters-long')
os.environ.setdefault('MONGODB_ENABLED', 'false')
os.environ.setdefault('REDIS_L1_ENABLED', 'false')

# Mock PyGithub if not installed (for test environments)
try:
    import github
except ImportError:
    # Create comprehensive mock github module with all submodules
    github_mock = MagicMock()
    github_mock.Github = MagicMock()
    github_mock.GithubException = Exception
    
    # Mock submodules
    pullrequest_mock = MagicMock()
    pullrequest_mock.PullRequest = MagicMock()
    
    repository_mock = MagicMock()
    repository_mock.Repository = MagicMock()
    
    sys.modules['github'] = github_mock
    sys.modules['github.Github'] = github_mock
    sys.modules['github.GithubException'] = MagicMock()
    sys.modules['github.PullRequest'] = pullrequest_mock
    sys.modules['github.Repository'] = repository_mock

# Add backend directory to Python path so we can import app modules
# This conftest is at backend/tests/, so parent is backend/
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Verify the path was added correctly
if str(backend_dir) not in sys.path:
    raise RuntimeError(f"Failed to add backend directory to sys.path: {backend_dir}")

# Now imports from 'app' module should work
# Example: from app.file_utils import validate_and_sanitize_path


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Set up test environment variables for all tests.
    This fixture runs once per session and ensures critical
    environment variables are set before any tests run.
    """
    # Ensure ENCRYPTION_KEY is set for JWT operations
    if not os.environ.get('ENCRYPTION_KEY'):
        os.environ['ENCRYPTION_KEY'] = 'test-secret-key-for-testing-minimum-32-characters-long'
    
    yield
    
    # Cleanup is not necessary as tests run in isolated environment
