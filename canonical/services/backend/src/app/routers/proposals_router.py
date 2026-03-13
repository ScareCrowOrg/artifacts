"""
File Proposal Router

Handles file modification and creation proposals from AgenteLab.
Allows users to accept/reject proposals which trigger PR creation via Coding Agent.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional
import logging
import hashlib
import time
from pathlib import Path

from ..config import BASE_DIR
from ..models.users import User
from ..permissions import has_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


class FileProposal(BaseModel):
    """File proposal data model"""

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["update", "create"] = Field(..., description="Type of proposal")
    filePath: str = Field(..., alias="filePath", description="Path to the file")
    content: str = Field(..., description="New/updated file content or snippet")
    originalContent: Optional[str] = Field(
        None, alias="originalContent", description="Original content (for updates)"
    )
    description: str = Field("", description="Description of the change")
    # Snippet-specific fields
    startLine: Optional[int] = Field(
        None, alias="startLine", description="Starting line number for snippet updates (1-indexed)"
    )
    endLine: Optional[int] = Field(
        None, alias="endLine", description="Ending line number for snippet updates (1-indexed)"
    )
    isSnippet: bool = Field(
        False, alias="isSnippet", description="Whether this is a snippet-based update"
    )


class ProposalResponse(BaseModel):
    """Response model for proposal operations"""

    status: str
    message: str
    proposal_id: Optional[str] = None


@router.post("/accept", response_model=ProposalResponse)
async def accept_proposal(
    request: Request,
    proposal: FileProposal,
    _current_user: User = Depends(has_permission(["proposals.accept"])),
):
    """
    Accept a file proposal and persist the file to disk.

    Required permission: proposals.accept

    For snippet-based updates (isSnippet=True):
    - Reads the entire file
    - Replaces only the specified line range (startLine to endLine)
    - Writes the complete modified file back

    For full-file updates (isSnippet=False):
    - Replaces the entire file with proposal.content

    Args:
        request: FastAPI request object (for raw body inspection)
        proposal: FileProposal data

    Returns:
        ProposalResponse with status and message
    """
    try:
        logger.info("[ProposalsRouter] accept_proposal endpoint invoked.")

        # Log raw request body for debugging
        try:
            body = await request.body()
            import json

            raw_data = json.loads(body.decode("utf-8"))
            logger.debug("[ProposalsRouter] Raw request body: %s", json.dumps(raw_data, indent=2))
            logger.info(
                "[ProposalsRouter] Raw isSnippet value: %s (type: %s)",
                raw_data.get('isSnippet'), type(raw_data.get('isSnippet')).__name__
            )
        except Exception as e:
            logger.warning("[ProposalsRouter] Could not parse raw request body: %s", e)

        logger.info(
            "[ProposalsRouter] Received proposal: type=%s, filePath=%s, isSnippet=%s",
            proposal.type, proposal.filePath, proposal.isSnippet
        )
        logger.debug("[ProposalsRouter] Deserialized proposal object: %s", proposal.model_dump())

        # Validate proposal data
        if not proposal.filePath:
            raise HTTPException(status_code=400, detail="File path is required")

        # Allow empty content for snippet deletions (isSnippet=True + empty content = delete lines)
        # For all other cases, content is required
        is_snippet_deletion = proposal.isSnippet and proposal.content == ""
        if not proposal.content and not is_snippet_deletion:
            raise HTTPException(status_code=400, detail="Content is required")

        # Validate based on mode
        if proposal.type == "update" and not proposal.isSnippet and not proposal.originalContent:
            raise HTTPException(
                status_code=400, detail="Original content is required for full-file updates"
            )

        # Validate snippet-specific fields
        if proposal.isSnippet:
            logger.info(
                "[ProposalsRouter] Snippet mode detected: startLine=%s, endLine=%s",
                proposal.startLine, proposal.endLine
            )

            if proposal.startLine is None or proposal.endLine is None:
                raise HTTPException(
                    status_code=400, detail="startLine and endLine are required for snippet updates"
                )

            if proposal.startLine < 1 or proposal.endLine < 1:
                raise HTTPException(
                    status_code=400, detail="Line numbers must be positive (1-indexed)"
                )

            if proposal.startLine > proposal.endLine:
                raise HTTPException(status_code=400, detail="startLine must be <= endLine")

        # Construct full file path using BASE_DIR
        # Remove leading slash if present to avoid absolute path issues
        file_path_str = proposal.filePath.lstrip("/")
        full_path = BASE_DIR / file_path_str

        logger.info("[ProposalsRouter] Full file path: %s", full_path)

        # Security check: ensure the path is within BASE_DIR (prevent directory traversal)
        try:
            full_path.resolve().relative_to(BASE_DIR.resolve())
        except ValueError:
            logger.error("[ProposalsRouter] Security violation: path %s is outside BASE_DIR %s", full_path, BASE_DIR)
            raise HTTPException(
                status_code=400, detail="Invalid file path: path must be within repository"
            )

        # For update operations, verify the file exists
        if proposal.type == "update" and not full_path.exists():
            logger.error("[ProposalsRouter] File not found for update: %s", full_path)
            raise HTTPException(status_code=404, detail=f"File not found: {proposal.filePath}")

        # Create parent directories if they don't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("[ProposalsRouter] Created parent directories for: %s", full_path)

        # Write the file content based on update mode
        try:
            if proposal.isSnippet and proposal.type == "update":
                # SNIPPET MODE: Replace only specified lines (or delete if content is empty)
                operation = "deleting" if proposal.content == "" else "replacing"
                logger.info(
                    "[ProposalsRouter] Snippet mode: %s lines %s-%s",
                    operation, proposal.startLine, proposal.endLine
                )

                # Read current file content
                current_content = full_path.read_text(encoding="utf-8")
                current_lines = current_content.splitlines()
                total_lines = len(current_lines)

                # ENHANCED LOGGING: File state
                logger.info("[ProposalsRouter] Current file: %s lines, %s chars", total_lines, len(current_content))
                logger.debug(
                    "[ProposalsRouter] Current file content (first 200 chars, repr): %s",
                    repr(current_content[:200])
                )
                logger.debug(
                    "[ProposalsRouter] Current lines (first 5): %s",
                    current_lines[:5] if len(current_lines) >= 5 else current_lines
                )
                logger.debug(
                    "[ProposalsRouter] Current lines (last 5): %s",
                    current_lines[-5:] if len(current_lines) >= 5 else current_lines
                )

                # Defensive validation: Ensure file is not empty
                if not current_content:
                    logger.error("[ProposalsRouter] File is empty: %s", full_path)
                    raise HTTPException(
                        status_code=400, detail="File is empty - cannot perform snippet update"
                    )

                if not current_lines:
                    logger.error("[ProposalsRouter] File has no lines after splitlines(): %s", full_path)
                    raise HTTPException(
                        status_code=400, detail="File has no lines - cannot perform snippet update"
                    )

                # ENHANCED LOGGING: Received content
                is_deletion = proposal.content == ""
                logger.info(
                    "[ProposalsRouter] Received content: %s chars (deletion: %s)",
                    len(proposal.content), is_deletion
                )
                logger.debug("[ProposalsRouter] Received content (repr): %s", repr(proposal.content))
                if not is_deletion:
                    logger.debug("[ProposalsRouter] Received content (full): %s", proposal.content)

                # Validate line indices
                if proposal.startLine < 1:
                    logger.error("[ProposalsRouter] startLine must be >= 1 (1-indexed), got: %s", proposal.startLine)
                    raise HTTPException(
                        status_code=400,
                        detail=f"startLine must be >= 1 (1-indexed), got: {proposal.startLine}",
                    )

                if proposal.endLine < 1:
                    logger.error("[ProposalsRouter] endLine must be >= 1 (1-indexed), got: %s", proposal.endLine)
                    raise HTTPException(
                        status_code=400,
                        detail=f"endLine must be >= 1 (1-indexed), got: {proposal.endLine}",
                    )

                # Validate line range
                # Special case: Allow appending new lines (startLine == total_lines + 1)
                # This enables inserting content after the last line of the file
                if proposal.startLine == total_lines + 1 and proposal.endLine >= proposal.startLine:
                    logger.info(
                        "[ProposalsRouter] Append mode detected: startLine=%s, total_lines=%s",
                        proposal.startLine, total_lines
                    )
                    # For append mode, we'll insert after all existing lines
                    # The validation passes, and the slicing logic below will handle it correctly
                elif proposal.startLine > total_lines:
                    logger.error(
                        "[ProposalsRouter] startLine (%s) exceeds file length (%s lines)",
                        proposal.startLine, total_lines
                    )
                    raise HTTPException(
                        status_code=400,
                        detail=f"startLine ({proposal.startLine}) exceeds file length ({total_lines} lines)",
                    )

                if proposal.endLine > total_lines and not (proposal.startLine == total_lines + 1):
                    logger.error(
                        "[ProposalsRouter] endLine (%s) exceeds file length (%s lines)",
                        proposal.endLine, total_lines
                    )
                    raise HTTPException(
                        status_code=400,
                        detail=f"endLine ({proposal.endLine}) exceeds file length ({total_lines} lines)",
                    )

                # Split new content into lines
                new_lines = proposal.content.splitlines()

                # ENHANCED LOGGING: New content lines
                logger.info("[ProposalsRouter] New lines count: %s (deletion: %s)", len(new_lines), is_deletion)
                logger.debug("[ProposalsRouter] New lines (repr): %s", repr(new_lines))
                if not is_deletion:
                    logger.debug("[ProposalsRouter] New lines (full): %s", new_lines)

                num_original_lines = proposal.endLine - proposal.startLine + 1
                logger.info(
                    "[ProposalsRouter] %s %s original lines with %s new lines",
                    'Deleting' if is_deletion else 'Replacing', num_original_lines, len(new_lines)
                )

                # Calculate slice indices (with explicit logging)
                before_end_index = proposal.startLine - 1  # Convert 1-indexed to 0-indexed
                after_start_index = proposal.endLine  # Correct for Python slicing (exclusive end)

                logger.debug("[ProposalsRouter] Slicing plan:")
                logger.debug(
                    "  - Before: current_lines[:%s] = indices 0 to %s = %s lines",
                    before_end_index, before_end_index-1, before_end_index
                )
                logger.debug("  - Replacement: %s lines", len(new_lines))
                logger.debug(
                    "  - After: current_lines[%s:] = indices %s to %s = %s lines",
                    after_start_index, after_start_index, total_lines-1, total_lines - after_start_index
                )

                # Perform slicing
                lines_before = current_lines[:before_end_index]
                lines_after = current_lines[after_start_index:]

                # ENHANCED LOGGING: Actual slicing results
                logger.debug("[ProposalsRouter] Actual slicing results:")
                logger.debug("  - Before: %s lines", len(lines_before))
                if lines_before:
                    logger.debug("    First 3: %s", repr(lines_before[:3]))
                    logger.debug("    Last 3: %s", repr(lines_before[-3:]))
                else:
                    logger.debug("    (empty)")

                logger.debug("  - New: %s lines: %s", len(new_lines), repr(new_lines))

                logger.debug("  - After: %s lines", len(lines_after))
                if lines_after:
                    logger.debug("    First 3: %s", repr(lines_after[:3]))
                    logger.debug("    Last 3: %s", repr(lines_after[-3:]))
                else:
                    logger.debug("    (empty)")

                # Construct updated file
                updated_lines = lines_before + new_lines + lines_after

                # ENHANCED LOGGING: Updated file
                logger.info(
                    "[ProposalsRouter] Updated file will have: %s lines (was %s lines)",
                    len(updated_lines), total_lines
                )
                logger.debug(
                    "[ProposalsRouter] Updated lines (first 5): %s",
                    updated_lines[:5] if len(updated_lines) >= 5 else updated_lines
                )
                logger.debug(
                    "[ProposalsRouter] Updated lines (last 5): %s",
                    updated_lines[-5:] if len(updated_lines) >= 5 else updated_lines
                )

                # Sanity check
                expected_line_count = len(lines_before) + len(new_lines) + len(lines_after)
                if len(updated_lines) != expected_line_count:
                    logger.error(
                        "[ProposalsRouter] Line count mismatch! Expected %s, got %s",
                        expected_line_count, len(updated_lines)
                    )
                    raise HTTPException(
                        status_code=500,
                        detail="Internal error: line count mismatch during snippet update",
                    )

                # Join back into complete file
                final_content = "\n".join(updated_lines)

                # Preserve trailing newline if original file had one
                had_trailing_newline = current_content.endswith("\n")
                if had_trailing_newline:
                    final_content += "\n"
                    logger.debug("[ProposalsRouter] Added trailing newline (original file had one)")
                else:
                    logger.debug("[ProposalsRouter] No trailing newline added (original file had none)")

                # ENHANCED LOGGING: Final content
                logger.info(
                    "[ProposalsRouter] Final content: %s chars, %s lines",
                    len(final_content), len(final_content.splitlines())
                )
                logger.debug("[ProposalsRouter] Final content (first 200 chars, repr): %s", repr(final_content[:200]))
                logger.debug(
                    "[ProposalsRouter] Final content (last 200 chars, repr): %s",
                    repr(final_content[-200:]) if len(final_content) >= 200 else repr(final_content)
                )

                # Sanity check: Verify we're not about to write just the snippet
                final_line_count = len(final_content.splitlines())
                if final_line_count == len(new_lines) and total_lines > len(new_lines):
                    logger.error("[ProposalsRouter] CRITICAL BUG DETECTED: About to replace %s lines with just %s lines (snippet only)!", total_lines, final_line_count)
                    logger.error("[ProposalsRouter] This would cause data loss. Aborting write.")
                    logger.error("[ProposalsRouter] Debug info:")
                    logger.error("  - lines_before: %s lines", len(lines_before))
                    logger.error("  - new_lines: %s lines", len(new_lines))
                    logger.error("  - lines_after: %s lines", len(lines_after))
                    logger.error("  - updated_lines: %s lines", len(updated_lines))
                    logger.error("  - final_content lines: %s", final_line_count)
                    raise HTTPException(
                        status_code=500,
                        detail="Internal error: snippet update would cause data loss (bug detected)",
                    )

                # Write the complete updated file
                full_path.write_text(final_content, encoding="utf-8")
                logger.info("[ProposalsRouter] Successfully wrote snippet update to: %s", full_path)

                # Verify the write
                verify_content = full_path.read_text(encoding="utf-8")
                verify_line_count = len(verify_content.splitlines())
                logger.info(
                    "[ProposalsRouter] Verification: File now has %s lines, %s chars",
                    verify_line_count, len(verify_content)
                )

                if verify_line_count != len(updated_lines):
                    logger.error(
                        "[ProposalsRouter] Verification FAILED: Expected %s lines, file has %s lines",
                        len(updated_lines), verify_line_count
                    )
                else:
                    logger.info("[ProposalsRouter] Verification PASSED: File has correct number of lines")

            else:
                # FULL-FILE MODE: Replace entire file
                logger.info("[ProposalsRouter] Full-file mode: replacing entire file")
                full_path.write_text(proposal.content, encoding="utf-8")
                logger.info("[ProposalsRouter] Successfully wrote full file to: %s", full_path)

        except (IOError, OSError) as e:
            logger.error("[ProposalsRouter] Failed to write file %s: %s", full_path, e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error writing file: {str(e)}") from e

        # Generate deterministic proposal ID using SHA256
        proposal_data = f"{proposal.type}:{proposal.filePath}:{int(time.time())}"
        proposal_id = hashlib.sha256(proposal_data.encode()).hexdigest()[:12]

        action_word = "created" if proposal.type == "create" else "updated"
        if proposal.isSnippet and proposal.content == "":
            action_word = "updated (lines deleted)"
        mode_info = "(snippet)" if proposal.isSnippet else "(full-file)"
        logger.info("[ProposalsRouter] Proposal %s completed: file %s %s", proposal_id, action_word, mode_info)

        return ProposalResponse(
            status="ok",
            message=f"File {action_word} successfully: {proposal.filePath}",
            proposal_id=proposal_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[ProposalsRouter] Error accepting proposal: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e


@router.post("/reject", response_model=ProposalResponse)
async def reject_proposal(
    proposal: FileProposal, _current_user: User = Depends(has_permission(["proposals.reject"]))
):
    """
    Reject a file proposal.

    Required permission: proposals.reject

    Args:
        proposal: FileProposal data

    Returns:
        ProposalResponse with status and message
    """
    try:
        logger.info("Proposal rejected: %s - %s", proposal.type, proposal.filePath)

        return ProposalResponse(status="ok", message=f"Proposal rejected for {proposal.filePath}")

    except Exception as e:
        logger.error("Error rejecting proposal: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e
