"""
Cell Validation Service for code quality and security checks.

This service implements the validation pipeline for generated code:
1. Syntax validation (JS, Python, Vue, SVG)
2. Security pattern scanning (XSS, injection)
3. Discovery System rule validation (mock for MVP 1)
4. Hypnosis Loop auto-correction (iterative feedback)
"""

import ast
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..database import db
from ..models import Cell, DynamicRef
from ..models.event_bus import EventTopic, MessageEnvelope
from ..services.redis_pubsub_service import RedisPubSubService

logger = logging.getLogger(__name__)

# Database constants for cell retrieval
# These are used when retrieving cells for validation across all users
DEFAULT_USER_ID = None  # None means all users (admin/system access)
DEFAULT_SESSION_ID = "default"  # Default session for system operations


class ValidationError:
    """Represents a validation error found in code."""

    def __init__(
        self,
        error_type: str,
        message: str,
        file: str,
        line: Optional[int] = None,
        suggestion: Optional[str] = None,
    ):
        self.error_type = error_type
        self.message = message
        self.file = file
        self.line = line
        self.suggestion = suggestion

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.error_type,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "suggestion": self.suggestion,
        }


class CellValidationService:
    """
    Service for validating generated cell code.

    Implements syntax checks, security scanning, and auto-correction
    through the Hypnosis Loop pattern.
    """

    MAX_HYPNOSIS_ATTEMPTS = 3

    # Security patterns to detect
    SECURITY_PATTERNS = {
        "eval": re.compile(r"\beval\s*\("),
        "exec": re.compile(r"\bexec\s*\("),
        "function_constructor": re.compile(r"\bFunction\s*\("),
        "script_injection": re.compile(r"<script[^>]*>"),
        "on_event": re.compile(r"\bon\w+\s*="),
    }

    def __init__(self, redis_service: Optional[RedisPubSubService] = None):
        """
        Initialize Cell Validation Service.

        Args:
            redis_service: Redis pub/sub service for event publishing
        """
        self.redis_service = redis_service
        self.logger = logger
        self._revalidation_subscription_started = False

    async def start_revalidation_listener(self) -> None:
        """
        Start listening for cell/generate/complete events for re-validation.

        Subscribes to generation complete topic and automatically re-validates
        cells that were auto-corrected through the Hypnosis Loop.

        Should be called once during service initialization (e.g., in main.py startup).
        """
        if self._revalidation_subscription_started:
            self.logger.info("Re-validation listener already started")
            return

        if not self.redis_service:
            self.logger.warning(
                "Redis service not configured, cannot start re-validation listener"
            )
            return

        try:
            self.logger.info(
                "Starting re-validation listener for cell/generate/complete"
            )

            # Subscribe to generation complete topic
            await self.redis_service.subscribe(
                EventTopic.CELL_GENERATE_COMPLETE.value,
                self._handle_generation_complete,
            )

            self._revalidation_subscription_started = True
            self.logger.info("✅ Re-validation listener started successfully")

        except Exception as e:
            self.logger.error("Failed to start re-validation listener: %s", e)
            raise

    async def validate_cell(
        self, cell: Cell, auto_correct: bool = True
    ) -> Tuple[bool, List[ValidationError]]:
        """
        Validate all dynamic refs in a cell.

        Args:
            cell: Cell to validate
            auto_correct: Whether to attempt auto-correction via Hypnosis Loop

        Returns:
            Tuple of (is_valid, errors_list)
        """
        self.logger.info("Starting validation for cell %s", cell.id)

        # Get dynamic refs from cell
        cell_data = cell.initial_data or {}
        dynamic_refs_data = cell_data.get("dynamic_refs", [])

        if not dynamic_refs_data:
            self.logger.warning("Cell %s has no dynamic refs to validate", cell.id)
            return True, []

        # Publish validation start event
        await self._publish_event(
            EventTopic.CELL_VALIDATE_STARTED,
            {"cell_id": cell.id, "refs_count": len(dynamic_refs_data), "attempt": 1},
        )

        # Validate each ref
        all_errors = []
        for ref_data in dynamic_refs_data:
            ref = DynamicRef(**ref_data)
            errors = await self._validate_ref(ref)
            all_errors.extend(errors)

        # Check if validation passed
        is_valid = len(all_errors) == 0

        if is_valid:
            # Mark all refs as validated
            await self._mark_refs_validated(cell, dynamic_refs_data)

            # Publish validation success
            await self._publish_event(
                EventTopic.CELL_VALIDATE_COMPLETE,
                {"cell_id": cell.id, "valid": True, "requires_human": False},
            )

            self.logger.info("Validation passed for cell %s", cell.id)

        else:
            # Publish validation errors
            await self._publish_event(
                EventTopic.CELL_VALIDATE_ERRORS,
                {"cell_id": cell.id, "errors": [err.to_dict() for err in all_errors]},
            )

            self.logger.warning("Validation failed for cell %s with %s errors", cell.id, len(all_errors))

            # If auto-correction enabled, initiate Hypnosis Loop
            if auto_correct:
                is_valid = await self._hypnosis_loop(cell, all_errors)

        return is_valid, all_errors

    async def _validate_ref(self, ref: DynamicRef) -> List[ValidationError]:
        """
        Validate a single dynamic ref.

        Args:
            ref: Dynamic ref to validate

        Returns:
            List of validation errors found
        """
        errors = []

        # Mock code content (in production, would read from OPFS/storage)
        code_content = self._get_mock_code_content(ref)

        # Syntax validation based on language
        if ref.lang == "python":
            errors.extend(self._validate_python_syntax(code_content, ref.filename))
        elif ref.lang in ["js", "vue"]:
            errors.extend(self._validate_javascript_syntax(code_content, ref.filename))
        elif ref.lang == "svg":
            errors.extend(self._validate_svg_syntax(code_content, ref.filename))

        # Security validation for all languages
        errors.extend(self._validate_security_patterns(code_content, ref.filename))

        return errors

    def _validate_python_syntax(
        self, code: str, filename: str
    ) -> List[ValidationError]:
        """Validate Python syntax using AST parsing."""
        errors = []

        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(
                ValidationError(
                    error_type="syntax_error",
                    message=f"Python syntax error: {e.msg}",
                    file=filename,
                    line=e.lineno,
                    suggestion="Fix syntax according to Python grammar",
                )
            )

        return errors

    def _validate_javascript_syntax(
        self, code: str, filename: str
    ) -> List[ValidationError]:
        """
        Validate JavaScript syntax.

        Basic validation - in production would use a JS parser like esprima.
        """
        errors = []

        # Basic checks for common syntax errors
        if code.count("{") != code.count("}"):
            errors.append(
                ValidationError(
                    error_type="syntax_error",
                    message="Mismatched braces in JavaScript code",
                    file=filename,
                    suggestion="Ensure all braces are properly closed",
                )
            )

        if code.count("(") != code.count(")"):
            errors.append(
                ValidationError(
                    error_type="syntax_error",
                    message="Mismatched parentheses in JavaScript code",
                    file=filename,
                    suggestion="Ensure all parentheses are properly closed",
                )
            )

        return errors

    def _validate_svg_syntax(self, code: str, filename: str) -> List[ValidationError]:
        """
        Validate SVG syntax.

        Basic validation - checks for valid XML structure.
        """
        errors = []

        if not code.strip().startswith("<svg"):
            errors.append(
                ValidationError(
                    error_type="syntax_error",
                    message="SVG must start with <svg> tag",
                    file=filename,
                    suggestion="Ensure SVG has proper opening tag",
                )
            )

        if not code.strip().endswith("</svg>"):
            errors.append(
                ValidationError(
                    error_type="syntax_error",
                    message="SVG must end with </svg> tag",
                    file=filename,
                    suggestion="Ensure SVG has proper closing tag",
                )
            )

        return errors

    def _validate_security_patterns(
        self, code: str, filename: str
    ) -> List[ValidationError]:
        """Scan code for security vulnerabilities."""
        errors = []

        for pattern_name, pattern in self.SECURITY_PATTERNS.items():
            if pattern.search(code):
                errors.append(
                    ValidationError(
                        error_type="security_violation",
                        message=f"Potentially unsafe pattern detected: {pattern_name}",
                        file=filename,
                        suggestion=f"Remove or sanitize {pattern_name} usage",
                    )
                )

        return errors

    async def _hypnosis_loop(self, cell: Cell, errors: List[ValidationError]) -> bool:
        """
        Execute Hypnosis Loop for auto-correction.

        Attempts to auto-correct errors through iterative feedback with LLM.
        Maximum 3 attempts before escalating to human validation.

        Args:
            cell: Cell to correct
            errors: List of validation errors

        Returns:
            True if corrected successfully, False otherwise
        """
        self.logger.info("Starting Hypnosis Loop for cell %s", cell.id)

        metadata = self._get_generation_metadata(cell)
        current_attempt = metadata.get("attempts", 1) if metadata else 1

        while current_attempt < self.MAX_HYPNOSIS_ATTEMPTS:
            current_attempt += 1

            self.logger.info(
                "Hypnosis Loop attempt %s/%s for cell %s",
                current_attempt, self.MAX_HYPNOSIS_ATTEMPTS, cell.id
            )

            # Format error context for LLM
            error_context = self._format_error_context(errors)

            # Publish auto-correction request to Event Bus
            await self._publish_event(
                EventTopic.CELL_VALIDATE_AUTO_CORRECT,
                {
                    "cell_id": cell.id,
                    "error_context": error_context,
                    "attempt": current_attempt,
                    "errors": [err.to_dict() for err in errors],
                },
            )

            # In MVP 2, trigger re-generation with error context through Event Bus
            # The Cell Generation Service will subscribe to this event and:
            # 1. Retrieve original enriched prompt from cell metadata
            # 2. Append error context to system instructions
            # 3. Call LLM to regenerate corrected code
            # 4. Publish cell/generate/complete when done

            # For MVP 2 implementation, we would await the corrected generation here
            # by subscribing to cell/generate/complete and checking if errors are fixed

            # Update metadata with attempt count
            await self._update_generation_attempts(cell, current_attempt)

            # MVP 2 Full Integration Complete:
            # The Hypnosis Loop now operates asynchronously through Event Bus:
            # 1. We publish validation/auto_correct event above
            # 2. Cell Generation Service subscribes and re-generates with error context
            # 3. Cell Generation Service publishes cell/generate/complete when done
            # 4. We subscribe to cell/generate/complete and automatically re-validate
            # 5. If valid, publish cell/validate/complete with success
            # 6. If still errors and attempts < max, trigger another cycle
            # 7. If max attempts reached, escalate to human

            # Since the loop is now event-driven and asynchronous, we return here
            # and let the event handlers continue the flow
            self.logger.info("Hypnosis Loop cycle %s initiated for cell %s. Auto-correction will continue asynchronously via Event Bus.", current_attempt, cell.id)

            # Return False to indicate the loop is in progress (not complete yet)
            # The actual result will be determined by the event handlers
            return False

    def _format_error_context(self, errors: List[ValidationError]) -> str:
        """Format errors as context for LLM correction."""
        context_lines = ["## Code Validation Errors Detected\n"]
        context_lines.append(
            "The generated code has the following issues. Please fix them:\n"
        )

        for i, error in enumerate(errors, 1):
            context_lines.append(
                f"{i}. **{error.error_type}**: {error.message}\n   File: {error.file}\n"
            )
            if error.line:
                context_lines.append(f"   Line: {error.line}\n")
            if error.suggestion:
                context_lines.append(f"   Fix suggestion: {error.suggestion}\n")
            context_lines.append("\n")

        context_lines.append("Please regenerate the corrected code blocks.")

        return "".join(context_lines)

    def _get_mock_code_content(self, ref: DynamicRef) -> str:
        """Get mock code content for validation. In production, reads from OPFS."""
        # Mock valid code for testing
        mock_code = {
            "python": "def hello():\n    return 'Hello, World!'",
            "js": "function hello() { return 'Hello, World!'; }",
            "svg": '<svg width="100" height="100"><circle cx="50" cy="50" r="40"/></svg>',
            "vue": "<template><div>Hello</div></template>",
        }
        return mock_code.get(ref.lang, "")

    def _get_generation_metadata(self, cell: Cell) -> Optional[Dict[str, Any]]:
        """Get generation metadata from cell."""
        cell_data = cell.initial_data or {}
        return cell_data.get("generation_metadata")

    async def _update_generation_attempts(self, cell: Cell, attempts: int) -> None:
        """Update generation metadata with new attempt count."""
        cell_data = cell.initial_data or {}
        metadata = cell_data.get("generation_metadata", {})
        metadata["attempts"] = attempts
        metadata["auto_corrected"] = True
        cell_data["generation_metadata"] = metadata
        cell.initial_data = cell_data

        db.update(
            "cells",
            cell.id,
            cell,
            user_id=cell.assignee_id,
            session_id="default",
            is_canonical=False,
        )

    async def _mark_refs_validated(
        self, cell: Cell, refs_data: List[Dict[str, Any]]
    ) -> None:
        """Mark all refs as validated and update promotion_ready flag."""
        for ref_data in refs_data:
            ref_data["validated"] = True

        cell_data = cell.initial_data or {}
        cell_data["dynamic_refs"] = refs_data

        # Mark generation as promotion ready
        metadata = cell_data.get("generation_metadata", {})
        metadata["promotion_ready"] = True
        cell_data["generation_metadata"] = metadata

        cell.initial_data = cell_data

        db.update(
            "cells",
            cell.id,
            cell,
            user_id=cell.assignee_id,
            session_id="default",
            is_canonical=False,
        )

    async def _publish_event(self, topic: EventTopic, payload: Dict[str, Any]) -> None:
        """Publish event to Event Bus."""
        if not self.redis_service:
            self.logger.warning("Redis service not configured, skipping event publish for %s", topic)
            return

        try:
            envelope = MessageEnvelope(
                topic=topic.value,  # Use string value for topic
                payload=payload,
                timestamp=datetime.utcnow(),
            )

            # Publish envelope to Redis
            # Note: RedisPubSubService.publish() expects MessageEnvelope and handles serialization internally
            await self.redis_service.publish(envelope)

            self.logger.debug("Published event %s", topic.value)

        except Exception as e:
            self.logger.error("Error publishing event %s: %s", topic.value, e)

    async def _handle_generation_complete(self, message: MessageEnvelope) -> None:
        """
        Handle cell/generate/complete event for auto-corrected cells.

        When a cell is re-generated through the Hypnosis Loop, this method
        automatically re-validates the new code to check if errors were fixed.

        Args:
            message: Event Bus message containing cell_id and auto_corrected flag
        """
        payload = message.payload
        cell_id = payload.get("cell_id")
        auto_corrected = payload.get("auto_corrected", False)
        attempt = payload.get("attempt", 1)

        # Only re-validate if this was an auto-correction
        if not auto_corrected:
            self.logger.debug("Skipping re-validation for cell %s (not auto-corrected)", cell_id)
            return

        self.logger.info("Re-validating auto-corrected cell %s, attempt %s", cell_id, attempt)

        try:
            # Retrieve updated cell from database
            cell = await db.get(
                "cells",
                cell_id,
                user_id=DEFAULT_USER_ID,
                session_id=DEFAULT_SESSION_ID,
                is_canonical=False,
            )

            if not cell:
                self.logger.error("Cell %s not found for re-validation", cell_id)
                return

            # Re-validate the cell (without triggering auto-correct again to avoid infinite loop)
            is_valid, errors = await self.validate_cell(cell, auto_correct=False)

            if is_valid:
                self.logger.info("✅ Auto-correction successful for cell %s on attempt %s", cell_id, attempt)

                # Publish validation complete with success
                await self._publish_event(
                    EventTopic.CELL_VALIDATE_COMPLETE,
                    {
                        "cell_id": cell_id,
                        "valid": True,
                        "requires_human": False,
                        "attempts": attempt,
                    },
                )
            else:
                # Errors still present
                if attempt < self.MAX_HYPNOSIS_ATTEMPTS:
                    # Trigger another auto-correction attempt
                    self.logger.info(
                        "Auto-correction attempt %s failed for cell %s. Triggering retry (%s/%s)",
                        attempt, cell_id, attempt + 1, self.MAX_HYPNOSIS_ATTEMPTS
                    )

                    error_context = self._format_error_context(errors)

                    await self._publish_event(
                        EventTopic.CELL_VALIDATE_AUTO_CORRECT,
                        {
                            "cell_id": cell_id,
                            "error_context": error_context,
                            "attempt": attempt + 1,
                            "errors": [err.to_dict() for err in errors],
                        },
                    )
                else:
                    # Max attempts reached, escalate to human
                    self.logger.warning(
                        "Max auto-correction attempts (%s) reached for cell %s. Escalating to human validation.",
                        self.MAX_HYPNOSIS_ATTEMPTS, cell_id
                    )

                    await self._publish_event(
                        EventTopic.CELL_VALIDATE_COMPLETE,
                        {
                            "cell_id": cell_id,
                            "valid": False,
                            "requires_human": True,
                            "attempts": attempt,
                        },
                    )

        except Exception as e:
            self.logger.error("Error re-validating cell %s: %s", cell_id, e)
