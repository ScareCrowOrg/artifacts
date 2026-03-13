"""
GitHub Pull Request Service

Provides functionality to query Pull Request information from GitHub API.
Supports retrieving PR reports, file changes, diffs, and new file content.

Features:
- Get PR report (description, title, metadata)
- List all changed files in a PR
- Get file diff for specific files
- Retrieve content of newly added files
- Proper error handling and validation
- Support for authentication via GitHub token
"""

import logging
import os
from typing import Any, Dict, List, Optional

from github import Github, GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository

logger = logging.getLogger(__name__)


class GitHubPRService:
    """
    Service for interacting with GitHub Pull Requests API

    Provides methods to query PR information including reports,
    file changes, diffs, and new file content.
    """

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize GitHub PR Service

        Args:
            github_token: GitHub personal access token (defaults to GITHUB_PAT env var,
                         falls back to GITHUB_TOKEN for backward compatibility)
        """
        # Priority: explicit token > GITHUB_PAT > GITHUB_TOKEN (backward compatibility)
        self.github_token = (
            github_token
            or os.environ.get("GITHUB_PAT")
            or os.environ.get("GITHUB_TOKEN")
        )
        if not self.github_token:
            logger.warning(
                "[GITHUB_PR_SERVICE] No GitHub token provided. "
                "API rate limits will be severely restricted. "
                "Set GITHUB_PAT environment variable for authentication."
            )

        try:
            self.github = Github(self.github_token) if self.github_token else Github()
            logger.info("[GITHUB_PR_SERVICE] GitHub client initialized")
        except Exception as e:
            logger.error("[GITHUB_PR_SERVICE] Failed to initialize GitHub client: %s", e)
            raise

    def _get_repository(self, owner: str, repo: str) -> Repository:
        """
        Get GitHub repository object

        Args:
            owner: Repository owner (username or organization)
            repo: Repository name

        Returns:
            Repository object

        Raises:
            GithubException: If repository not found or access denied
        """
        try:
            repository = self.github.get_repo(f"{owner}/{repo}")
            logger.info("[GITHUB_PR_SERVICE] Retrieved repository: %s/%s", owner, repo)
            return repository
        except GithubException as e:
            logger.error("[GITHUB_PR_SERVICE] Failed to get repository %s/%s: %s", owner, repo, e)
            raise

    def _get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequest:
        """
        Get Pull Request object

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull Request number

        Returns:
            PullRequest object

        Raises:
            GithubException: If PR not found or access denied
        """
        try:
            repository = self._get_repository(owner, repo)
            pull_request = repository.get_pull(pr_number)
            logger.info("[GITHUB_PR_SERVICE] Retrieved PR #%s", pr_number)
            return pull_request
        except GithubException as e:
            logger.error("[GITHUB_PR_SERVICE] Failed to get PR #%s from %s/%s: %s", pr_number, owner, repo, e)
            raise

    def get_pr_report(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """
        Get Pull Request report with metadata

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull Request number

        Returns:
            Dictionary containing PR information:
            {
                "number": int,
                "title": str,
                "body": str,
                "state": str,
                "merged": bool,
                "created_at": str,
                "updated_at": str,
                "closed_at": str (optional),
                "merged_at": str (optional),
                "user": str,
                "base_branch": str,
                "head_branch": str,
                "commits_count": int,
                "additions": int,
                "deletions": int,
                "changed_files": int,
                "url": str
            }
        """
        try:
            pr = self._get_pull_request(owner, repo, pr_number)

            report = {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body or "",
                "state": pr.state,
                "merged": pr.merged,
                "created_at": pr.created_at.isoformat() if pr.created_at else None,
                "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
                "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
                "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                "user": pr.user.login if pr.user else None,
                "base_branch": pr.base.ref,
                "head_branch": pr.head.ref,
                "commits_count": pr.commits,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "changed_files": pr.changed_files,
                "url": pr.html_url,
            }

            logger.info("[GITHUB_PR_SERVICE] Generated report for PR #%s", pr_number)
            return report

        except GithubException as e:
            logger.error("[GITHUB_PR_SERVICE] Error getting PR report: %s", e)
            raise

    def get_pr_changes(
        self, owner: str, repo: str, pr_number: int
    ) -> List[Dict[str, Any]]:
        """
        Get list of all changed files in a Pull Request

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull Request number

        Returns:
            List of dictionaries with file change information:
            [
                {
                    "filename": str,
                    "status": str (added|modified|removed|renamed),
                    "additions": int,
                    "deletions": int,
                    "changes": int,
                    "patch": str (optional),
                    "previous_filename": str (optional, for renamed files)
                }
            ]
        """
        try:
            pr = self._get_pull_request(owner, repo, pr_number)
            files = pr.get_files()

            changes = []
            for file in files:
                file_info = {
                    "filename": file.filename,
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                }

                # Include patch if available (not available for binary files)
                if hasattr(file, "patch") and file.patch:
                    file_info["patch"] = file.patch

                # Include previous filename for renamed files
                if file.status == "renamed" and hasattr(file, "previous_filename"):
                    file_info["previous_filename"] = file.previous_filename

                changes.append(file_info)

            logger.info("[GITHUB_PR_SERVICE] Retrieved %s changed files for PR #%s", len(changes), pr_number)
            return changes

        except GithubException as e:
            logger.error("[GITHUB_PR_SERVICE] Error getting PR changes: %s", e)
            raise

    def get_pr_file_diff(
        self, owner: str, repo: str, pr_number: int, file_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get diff for a specific file in a Pull Request

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull Request number
            file_path: Path to the file

        Returns:
            Dictionary with file diff information or None if file not found:
            {
                "filename": str,
                "status": str,
                "additions": int,
                "deletions": int,
                "changes": int,
                "patch": str,
                "previous_filename": str (optional)
            }
        """
        try:
            pr = self._get_pull_request(owner, repo, pr_number)
            files = pr.get_files()

            for file in files:
                if file.filename == file_path:
                    diff_info = {
                        "filename": file.filename,
                        "status": file.status,
                        "additions": file.additions,
                        "deletions": file.deletions,
                        "changes": file.changes,
                        "patch": file.patch
                        if hasattr(file, "patch") and file.patch
                        else None,
                    }

                    if file.status == "renamed" and hasattr(file, "previous_filename"):
                        diff_info["previous_filename"] = file.previous_filename

                    logger.info("[GITHUB_PR_SERVICE] Retrieved diff for file '%s' in PR #%s", file_path, pr_number)
                    return diff_info

            logger.warning("[GITHUB_PR_SERVICE] File '%s' not found in PR #%s", file_path, pr_number)
            return None

        except GithubException as e:
            logger.error("[GITHUB_PR_SERVICE] Error getting file diff: %s", e)
            raise

    def get_pr_new_file_content(
        self, owner: str, repo: str, pr_number: int, file_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get content of a newly added file in a Pull Request

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull Request number
            file_path: Path to the newly added file

        Returns:
            Dictionary with file content or None if file not found or not new:
            {
                "filename": str,
                "content": str,
                "encoding": str,
                "size": int
            }
        """
        try:
            pr = self._get_pull_request(owner, repo, pr_number)
            files = pr.get_files()

            # Check if file was added in this PR using any()
            file_added = any(
                file.filename == file_path and file.status == "added" for file in files
            )

            if not file_added:
                logger.warning(
                    "[GITHUB_PR_SERVICE] File '%s' was not added in PR #%s (may be modified or not exist)",
                    file_path, pr_number
                )
                return None

            # Get file content from the PR's head branch
            repository = self._get_repository(owner, repo)
            file_content = repository.get_contents(file_path, ref=pr.head.sha)

            result = {
                "filename": file_path,
                "content": file_content.decoded_content.decode("utf-8"),
                "encoding": file_content.encoding,
                "size": file_content.size,
            }

            logger.info("[GITHUB_PR_SERVICE] Retrieved content for new file '%s' in PR #%s", file_path, pr_number)
            return result

        except GithubException as e:
            logger.error("[GITHUB_PR_SERVICE] Error getting new file content: %s", e)
            raise
        except UnicodeDecodeError:
            logger.error("[GITHUB_PR_SERVICE] Cannot decode file '%s' (may be binary)", file_path)
            return {
                "filename": file_path,
                "content": None,
                "encoding": "binary",
                "size": None,
                "error": "Binary file cannot be decoded as text",
            }


# Global service instance
_github_pr_service: Optional[GitHubPRService] = None


def get_github_pr_service() -> GitHubPRService:
    """
    Get or create the global GitHub PR service instance

    Returns:
        GitHubPRService instance
    """
    global _github_pr_service
    if _github_pr_service is None:
        _github_pr_service = GitHubPRService()
    return _github_pr_service
