"""
GitHub Pull Request Router

Provides endpoints for querying Pull Request information from GitHub.

Endpoints:
- GET /github/pr/report - Get PR report with metadata
- GET /github/pr/changes - List all changed files in PR
- GET /github/pr/file-diff - Get diff for specific file
- GET /github/pr/new-file-content - Get content of newly added file
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.services.github_pr_service import get_github_pr_service

from ..auth import get_current_user_required
from ..models.users import User

logger = logging.getLogger(__name__)

github_pr_router = APIRouter(prefix="/github/pr", tags=["github"])


class PRReportResponse(BaseModel):
    """Response model for PR report"""

    number: int
    title: str
    body: str
    state: str
    merged: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    closed_at: Optional[str] = None
    merged_at: Optional[str] = None
    user: Optional[str] = None
    base_branch: str
    head_branch: str
    commits_count: int
    additions: int
    deletions: int
    changed_files: int
    url: str


class FileChangeInfo(BaseModel):
    """Model for file change information"""

    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = None
    previous_filename: Optional[str] = None


class FileDiffResponse(BaseModel):
    """Response model for file diff"""

    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = None
    previous_filename: Optional[str] = None


class NewFileContentResponse(BaseModel):
    """Response model for new file content"""

    filename: str
    content: Optional[str] = None
    encoding: str
    size: Optional[int] = None
    error: Optional[str] = None


@github_pr_router.get("/report", response_model=PRReportResponse)
async def get_pr_report(
    owner: str = Query(..., description="Repository owner (username or organization)"),
    repo: str = Query(..., description="Repository name"),
    pr_number: int = Query(..., description="Pull Request number", ge=1),
    _current_user: User = Depends(get_current_user_required),
):
    """
    Get Pull Request report with metadata

    Required: authenticated user

    Returns detailed information about a PR including:
    - Title, body, and state
    - Author and timestamps
    - Branch information
    - Statistics (commits, additions, deletions)
    - URL to the PR
    """
    try:
        service = get_github_pr_service()
        report = service.get_pr_report(owner, repo, pr_number)
        logger.info("[GITHUB_PR_ROUTER] Successfully retrieved PR report for %s/%s#%s", owner, repo, pr_number)
        return report
    except Exception as e:
        logger.error("[GITHUB_PR_ROUTER] Error getting PR report for %s/%s#%s: %s", owner, repo, pr_number, e)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve PR report: {str(e)}"
        )


@github_pr_router.get("/changes")
async def get_pr_changes(
    owner: str = Query(..., description="Repository owner"),
    repo: str = Query(..., description="Repository name"),
    pr_number: int = Query(..., description="Pull Request number", ge=1),
    _current_user: User = Depends(get_current_user_required),
):
    """
    Get list of all changed files in a Pull Request

    Returns information about each file changed in the PR:
    - Filename and status (added/modified/removed/renamed)
    - Number of additions, deletions, and total changes
    - Patch/diff (if available)
    - Previous filename (for renamed files)
    """
    try:
        service = get_github_pr_service()
        changes = service.get_pr_changes(owner, repo, pr_number)
        logger.info(
            "[GITHUB_PR_ROUTER] Successfully retrieved %s changes for %s/%s#%s",
            len(changes), owner, repo, pr_number
        )
        return {"changes": changes, "total": len(changes)}
    except Exception as e:
        logger.error("[GITHUB_PR_ROUTER] Error getting PR changes for %s/%s#%s: %s", owner, repo, pr_number, e)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve PR changes: {str(e)}"
        )


@github_pr_router.get("/file-diff")
async def get_pr_file_diff(
    owner: str = Query(..., description="Repository owner"),
    repo: str = Query(..., description="Repository name"),
    pr_number: int = Query(..., description="Pull Request number", ge=1),
    file_path: str = Query(..., description="Path to the file"),
    _current_user: User = Depends(get_current_user_required),
):
    """
    Get diff for a specific file in a Pull Request

    Required: authenticated user

    Returns diff information for the specified file:
    - Filename and status
    - Statistics (additions, deletions, changes)
    - Patch/diff content
    - Previous filename (if renamed)
    """
    try:
        service = get_github_pr_service()
        diff = service.get_pr_file_diff(owner, repo, pr_number, file_path)

        if diff is None:
            raise HTTPException(
                status_code=404,
                detail=f"File '{file_path}' not found in PR #{pr_number}",
            )

        logger.info(
            "[GITHUB_PR_ROUTER] Successfully retrieved file diff for %s in %s/%s#%s",
            file_path, owner, repo, pr_number
        )
        return diff
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[GITHUB_PR_ROUTER] Error getting file diff for %s in %s/%s#%s: %s",
            file_path, owner, repo, pr_number, e
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve file diff: {str(e)}"
        )


@github_pr_router.get("/new-file-content")
async def get_pr_new_file_content(
    owner: str = Query(..., description="Repository owner"),
    repo: str = Query(..., description="Repository name"),
    pr_number: int = Query(..., description="Pull Request number", ge=1),
    file_path: str = Query(..., description="Path to the newly added file"),
    _current_user: User = Depends(get_current_user_required),
):
    """
    Get content of a newly added file in a Pull Request

    Required: authenticated user

    Returns the full content of a file that was added in the PR.
    Only works for files with status "added" (not modified or renamed).

    Returns:
    - Filename
    - File content (text)
    - Encoding
    - Size
    """
    try:
        service = get_github_pr_service()
        content = service.get_pr_new_file_content(owner, repo, pr_number, file_path)

        if content is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"File '{file_path}' was not added in PR #{pr_number}. "
                    "This endpoint only works for newly added files."
                ),
            )

        logger.info(
            "[GITHUB_PR_ROUTER] Successfully retrieved new file content for %s in %s/%s#%s",
            file_path, owner, repo, pr_number
        )
        return content
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[GITHUB_PR_ROUTER] Error getting new file content for %s in %s/%s#%s: %s",
            file_path, owner, repo, pr_number, e
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve new file content: {str(e)}"
        )
