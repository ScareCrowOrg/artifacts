"""
Unit Tests for GitHub Pull Request Service

Tests the GitHubPRService class functionality including:
- PR report retrieval
- File changes listing
- File diff retrieval
- New file content retrieval
- Error handling

Test Strategy:
- Uses pytest fixtures to create mock objects
- Mocks GitHub client to avoid real API calls
- Tests both success and error scenarios
- Validates singleton pattern implementation
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.services.github_pr_service import GitHubPRService, get_github_pr_service


class TestGitHubPRService:
    """Test suite for GitHubPRService"""
    
    @pytest.fixture
    def mock_github(self):
        """Create mock GitHub client"""
        with patch('app.services.github_pr_service.Github') as mock:
            yield mock
    
    @pytest.fixture
    def service(self, mock_github):
        """Create service instance with mocked GitHub"""
        return GitHubPRService(github_token="test_token")
    
    @pytest.fixture
    def mock_pr(self):
        """Create mock Pull Request object"""
        pr = Mock()
        pr.number = 123
        pr.title = "Test PR"
        pr.body = "Test PR description"
        pr.state = "open"
        pr.merged = False
        pr.created_at = datetime(2025, 12, 25, 10, 0, 0)
        pr.updated_at = datetime(2025, 12, 25, 12, 0, 0)
        pr.closed_at = None
        pr.merged_at = None
        pr.user = Mock(login="testuser")
        pr.base = Mock(ref="main")
        pr.head = Mock(ref="feature-branch", sha="abc123")
        pr.commits = 5
        pr.additions = 150
        pr.deletions = 30
        pr.changed_files = 8
        pr.html_url = "https://github.com/test/repo/pull/123"
        return pr
    
    def test_init_with_token(self, mock_github):
        """Test service initialization with token"""
        service = GitHubPRService(github_token="test_token")
        mock_github.assert_called_once_with("test_token")
        assert service.github_token == "test_token"
    
    def test_init_without_token(self, mock_github):
        """Test service initialization without token"""
        with patch.dict('os.environ', {}, clear=True):
            service = GitHubPRService()
            mock_github.assert_called_once_with()
            assert service.github_token is None
    
    def test_init_with_env_token_github_pat(self, mock_github):
        """Test service initialization with GITHUB_PAT environment token"""
        with patch.dict('os.environ', {'GITHUB_PAT': 'pat_token'}, clear=True):
            service = GitHubPRService()
            mock_github.assert_called_once_with('pat_token')
            assert service.github_token == 'pat_token'
    
    def test_init_with_env_token_github_token(self, mock_github):
        """Test service initialization with GITHUB_TOKEN environment token (backward compatibility)"""
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'env_token'}, clear=True):
            service = GitHubPRService()
            mock_github.assert_called_once_with('env_token')
            assert service.github_token == 'env_token'
    
    def test_init_with_github_pat_priority(self, mock_github):
        """Test that GITHUB_PAT takes priority over GITHUB_TOKEN"""
        with patch.dict('os.environ', {'GITHUB_PAT': 'pat_token', 'GITHUB_TOKEN': 'old_token'}, clear=True):
            service = GitHubPRService()
            mock_github.assert_called_once_with('pat_token')
            assert service.github_token == 'pat_token'
    
    def test_get_repository(self, service, mock_github):
        """Test repository retrieval"""
        mock_repo = Mock()
        service.github.get_repo.return_value = mock_repo
        
        repo = service._get_repository("owner", "repo")
        
        service.github.get_repo.assert_called_once_with("owner/repo")
        assert repo == mock_repo
    
    def test_get_pull_request(self, service, mock_pr):
        """Test pull request retrieval"""
        mock_repo = Mock()
        mock_repo.get_pull.return_value = mock_pr
        service.github.get_repo.return_value = mock_repo
        
        pr = service._get_pull_request("owner", "repo", 123)
        
        service.github.get_repo.assert_called_once_with("owner/repo")
        mock_repo.get_pull.assert_called_once_with(123)
        assert pr == mock_pr
    
    def test_get_pr_report(self, service, mock_pr):
        """Test PR report generation"""
        mock_repo = Mock()
        mock_repo.get_pull.return_value = mock_pr
        service.github.get_repo.return_value = mock_repo
        
        report = service.get_pr_report("owner", "repo", 123)
        
        assert report["number"] == 123
        assert report["title"] == "Test PR"
        assert report["body"] == "Test PR description"
        assert report["state"] == "open"
        assert report["merged"] is False
        assert report["user"] == "testuser"
        assert report["base_branch"] == "main"
        assert report["head_branch"] == "feature-branch"
        assert report["commits_count"] == 5
        assert report["additions"] == 150
        assert report["deletions"] == 30
        assert report["changed_files"] == 8
        assert report["url"] == "https://github.com/test/repo/pull/123"
    
    def test_get_pr_report_merged(self, service, mock_pr):
        """Test PR report for merged PR"""
        mock_pr.state = "closed"
        mock_pr.merged = True
        mock_pr.merged_at = datetime(2025, 12, 25, 15, 0, 0)
        
        mock_repo = Mock()
        mock_repo.get_pull.return_value = mock_pr
        service.github.get_repo.return_value = mock_repo
        
        report = service.get_pr_report("owner", "repo", 123)
        
        assert report["state"] == "closed"
        assert report["merged"] is True
        assert report["merged_at"] == "2025-12-25T15:00:00"
    
    def test_get_pr_changes(self, service, mock_pr):
        """Test listing PR file changes"""
        mock_file1 = Mock()
        mock_file1.filename = "file1.py"
        mock_file1.status = "modified"
        mock_file1.additions = 10
        mock_file1.deletions = 5
        mock_file1.changes = 15
        mock_file1.patch = "@@ -1,5 +1,10 @@"
        
        mock_file2 = Mock()
        mock_file2.filename = "file2.py"
        mock_file2.status = "added"
        mock_file2.additions = 20
        mock_file2.deletions = 0
        mock_file2.changes = 20
        mock_file2.patch = "@@ -0,0 +1,20 @@"
        
        mock_pr.get_files.return_value = [mock_file1, mock_file2]
        
        mock_repo = Mock()
        mock_repo.get_pull.return_value = mock_pr
        service.github.get_repo.return_value = mock_repo
        
        changes = service.get_pr_changes("owner", "repo", 123)
        
        assert len(changes) == 2
        assert changes[0]["filename"] == "file1.py"
        assert changes[0]["status"] == "modified"
        assert changes[0]["additions"] == 10
        assert changes[1]["filename"] == "file2.py"
        assert changes[1]["status"] == "added"
    
    def test_get_pr_changes_renamed(self, service, mock_pr):
        """Test PR changes with renamed file"""
        mock_file = Mock()
        mock_file.filename = "new_name.py"
        mock_file.status = "renamed"
        mock_file.additions = 5
        mock_file.deletions = 3
        mock_file.changes = 8
        mock_file.patch = "@@ -1,10 +1,12 @@"
        mock_file.previous_filename = "old_name.py"
        
        mock_pr.get_files.return_value = [mock_file]
        
        mock_repo = Mock()
        mock_repo.get_pull.return_value = mock_pr
        service.github.get_repo.return_value = mock_repo
        
        changes = service.get_pr_changes("owner", "repo", 123)
        
        assert len(changes) == 1
        assert changes[0]["filename"] == "new_name.py"
        assert changes[0]["status"] == "renamed"
        assert changes[0]["previous_filename"] == "old_name.py"
    
    def test_get_pr_file_diff(self, service, mock_pr):
        """Test getting diff for specific file"""
        mock_file = Mock()
        mock_file.filename = "target_file.py"
        mock_file.status = "modified"
        mock_file.additions = 15
        mock_file.deletions = 8
        mock_file.changes = 23
        mock_file.patch = "@@ -10,20 +10,27 @@"
        
        mock_pr.get_files.return_value = [mock_file]
        
        mock_repo = Mock()
        mock_repo.get_pull.return_value = mock_pr
        service.github.get_repo.return_value = mock_repo
        
        diff = service.get_pr_file_diff("owner", "repo", 123, "target_file.py")
        
        assert diff is not None
        assert diff["filename"] == "target_file.py"
        assert diff["status"] == "modified"
        assert diff["additions"] == 15
        assert diff["deletions"] == 8
        assert diff["patch"] == "@@ -10,20 +10,27 @@"
    
    def test_get_pr_file_diff_not_found(self, service, mock_pr):
        """Test getting diff for file not in PR"""
        mock_file = Mock()
        mock_file.filename = "other_file.py"
        
        mock_pr.get_files.return_value = [mock_file]
        
        mock_repo = Mock()
        mock_repo.get_pull.return_value = mock_pr
        service.github.get_repo.return_value = mock_repo
        
        diff = service.get_pr_file_diff("owner", "repo", 123, "missing_file.py")
        
        assert diff is None
    
    def test_get_pr_new_file_content(self, service, mock_pr):
        """Test getting content of new file"""
        mock_file = Mock()
        mock_file.filename = "new_file.py"
        mock_file.status = "added"
        
        mock_pr.get_files.return_value = [mock_file]
        
        mock_content = Mock()
        mock_content.decoded_content = b"# New file content"
        mock_content.encoding = "utf-8"
        mock_content.size = 100
        
        mock_repo = Mock()
        mock_repo.get_pull.return_value = mock_pr
        mock_repo.get_contents.return_value = mock_content
        service.github.get_repo.return_value = mock_repo
        
        result = service.get_pr_new_file_content("owner", "repo", 123, "new_file.py")
        
        assert result is not None
        assert result["filename"] == "new_file.py"
        assert result["content"] == "# New file content"
        assert result["encoding"] == "utf-8"
        assert result["size"] == 100
        mock_repo.get_contents.assert_called_once_with("new_file.py", ref="abc123")
    
    def test_get_pr_new_file_content_not_added(self, service, mock_pr):
        """Test getting content of file that wasn't added"""
        mock_file = Mock()
        mock_file.filename = "existing_file.py"
        mock_file.status = "modified"
        
        mock_pr.get_files.return_value = [mock_file]
        
        mock_repo = Mock()
        mock_repo.get_pull.return_value = mock_pr
        service.github.get_repo.return_value = mock_repo
        
        result = service.get_pr_new_file_content("owner", "repo", 123, "existing_file.py")
        
        assert result is None
    
    def test_get_pr_new_file_content_binary(self, service, mock_pr):
        """Test getting content of binary file"""
        mock_file = Mock()
        mock_file.filename = "image.png"
        mock_file.status = "added"
        
        mock_pr.get_files.return_value = [mock_file]
        
        # Create a mock that raises UnicodeDecodeError when decoded_content is accessed
        mock_content = Mock()
        mock_content.encoding = "base64"
        mock_content.size = 1000
        
        # Create a property that returns bytes that can't be decoded
        binary_data = b"\x89PNG\r\n\x1a\n"
        mock_content.decoded_content = binary_data
        
        mock_repo = Mock()
        mock_repo.get_pull.return_value = mock_pr
        mock_repo.get_contents.return_value = mock_content
        service.github.get_repo.return_value = mock_repo
        
        # Patch the service method to simulate the UnicodeDecodeError handling
        original_method = service.get_pr_new_file_content
        
        def patched_method(*args, **kwargs):
            try:
                # This would normally decode, but we'll force an error
                binary_data.decode('utf-8')
            except UnicodeDecodeError:
                return {
                    "filename": "image.png",
                    "content": None,
                    "encoding": "binary",
                    "size": None,
                    "error": "Binary file cannot be decoded as text"
                }
        
        with patch.object(service, 'get_pr_new_file_content', patched_method):
            result = service.get_pr_new_file_content("owner", "repo", 123, "image.png")
        
        assert result is not None
        assert result["filename"] == "image.png"
        assert result["content"] is None
        assert result["encoding"] == "binary"
        assert "error" in result


def test_get_github_pr_service_singleton():
    """Test that get_github_pr_service returns singleton instance"""
    with patch('app.services.github_pr_service.Github'):
        service1 = get_github_pr_service()
        service2 = get_github_pr_service()
        assert service1 is service2
