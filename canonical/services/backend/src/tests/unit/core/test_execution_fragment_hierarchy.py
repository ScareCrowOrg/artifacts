"""
Tests for ExecutionFragment hierarchical tracing.

This test suite validates the two-fragment system:
- Fragment: Generic data container without execution semantics
- ExecutionFragment: Execution tracking with hierarchical tracing via executed_by
"""

import pytest
from datetime import datetime
from backend.app.core.models import Fragment, ExecutionFragment, PipelineItem, NotebookItem


class TestFragmentGeneric:
    """Fragment class must remain generic without executed_by field."""

    def test_fragment_is_generic(self):
        """Fragment is generic and has NO executed_by field."""
        fragment = Fragment(
            type="log",
            content="some log data",
        )
        # Fragment doesn't have executed_by - it's intentionally generic!
        assert not hasattr(fragment, "executed_by")

    def test_fragment_accepts_any_content(self):
        """Fragment can hold any type of content."""
        # Text content
        frag1 = Fragment(type="narrative", content="Long story here")
        assert frag1.content == "Long story here"

        # JSON/dict content
        frag2 = Fragment(type="memory", content={"key": "value", "nested": {"data": 123}})
        assert frag2.content["nested"]["data"] == 123

        # List content
        frag3 = Fragment(type="data", content=[1, 2, 3, "mixed"])
        assert len(frag3.content) == 4

    def test_fragment_with_metadata(self):
        """Fragment supports flexible metadata."""
        fragment = Fragment(
            type="execution",
            content="test",
            metadata={
                "source": "test-cell",
                "severity": "info",
                "custom_field": "any_value"
            }
        )
        assert fragment.metadata["severity"] == "info"
        assert "custom_field" in fragment.metadata


class TestExecutionFragment:
    """ExecutionFragment specifically supports hierarchical tracing."""

    def test_execution_fragment_has_executed_by(self):
        """ExecutionFragment has executed_by field for hierarchical tracing."""
        exec_frag = ExecutionFragment(
            timestamp="2026-02-10T12:00:00Z",
            step="discovery",
            status="success",
            executed_by="cell-123",  # ← This field ONLY on ExecutionFragment
        )
        assert exec_frag.executed_by == "cell-123"
        assert exec_frag.step == "discovery"

    def test_execution_fragment_tracking_fields(self):
        """ExecutionFragment has fields for detailed execution tracking."""
        exec_frag = ExecutionFragment(
            timestamp="2026-02-10T12:00:00Z",
            step="planning",
            status="running",
            input={"goal": "discover cells"},
            output={"cells_found": 3},
            executed_by="book-1",
            duration_ms=1500,
        )
        assert exec_frag.input == {"goal": "discover cells"}
        assert exec_frag.output["cells_found"] == 3
        assert exec_frag.duration_ms == 1500

    def test_execution_fragment_error_tracking(self):
        """ExecutionFragment can track errors."""
        exec_frag = ExecutionFragment(
            timestamp="2026-02-10T12:00:00Z",
            step="execute",
            status="failed",
            error="Cell execution timeout",
            executed_by="cell-456",
        )
        assert exec_frag.status == "failed"
        assert exec_frag.error == "Cell execution timeout"


class TestPipelineItemAddFragment:
    """PipelineItem.add_fragment() supports both Fragment and ExecutionFragment."""

    def test_add_generic_fragment(self):
        """add_fragment() creates generic Fragment by default."""
        notebook_item = NotebookItem(assignee_id="user-1")
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="test-cell",
            assignee_id="user-1",
        )

        # Add generic fragment
        result = pipeline.add_fragment(
            type="log",
            content="Test message",
            metadata={"source": "test"}
        )

        # Check fragment was added
        assert len(pipeline.fragments) == 1
        assert pipeline.fragments[0]["type"] == "log"
        assert pipeline.fragments[0]["content"] == "Test message"
        # Generic fragment should NOT have executed_by
        assert "executed_by" not in pipeline.fragments[0]

    def test_add_execution_fragment(self):
        """add_fragment() accepts ExecutionFragment for hierarchical tracing."""
        notebook_item = NotebookItem(assignee_id="user-1")
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="test-cell",
            assignee_id="user-1",
        )

        # Create and add ExecutionFragment
        exec_frag = ExecutionFragment(
            timestamp="2026-02-10T12:00:00Z",
            step="discovery",
            status="success",
            executed_by="cell-1",
        )
        result = pipeline.add_fragment(
            type="execution",
            content="Discovery completed",
            execution_fragment=exec_frag
        )

        # Check fragment was added with ExecutionFragment data
        assert len(pipeline.fragments) == 1
        assert pipeline.fragments[0]["step"] == "discovery"
        assert pipeline.fragments[0]["executed_by"] == "cell-1"

    def test_mixed_fragments_in_pipeline(self):
        """Pipeline can contain both generic and ExecutionFragments."""
        notebook_item = NotebookItem(assignee_id="user-1")
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="test-cell",
            assignee_id="user-1",
        )

        # Add generic fragment
        pipeline.add_fragment(type="log", content="Starting execution")

        # Add ExecutionFragment
        exec_frag = ExecutionFragment(
            timestamp="2026-02-10T12:00:00Z",
            step="execute",
            status="running",
            executed_by="cell-1",
        )
        pipeline.add_fragment(
            type="execution",
            content="Executing...",
            execution_fragment=exec_frag
        )

        # Add another generic fragment
        pipeline.add_fragment(type="log", content="Done")

        # Check all fragments are there
        assert len(pipeline.fragments) == 3
        # First is generic Fragment
        assert "type" in pipeline.fragments[0]
        assert pipeline.fragments[0]["type"] == "log"
        assert "executed_by" not in pipeline.fragments[0]
        # Second is ExecutionFragment
        assert pipeline.fragments[1]["step"] == "execute"
        assert pipeline.fragments[1]["executed_by"] == "cell-1"
        # Third is generic Fragment
        assert pipeline.fragments[2]["type"] == "log"
        assert "executed_by" not in pipeline.fragments[2]


class TestHierarchicalTracing:
    """Test hierarchical tracing via ExecutionFragment chain."""

    def test_execution_fragment_preserves_hierarchy(self):
        """ExecutionFragment preserves hierarchy through executed_by chain."""
        # Book executes Cell
        cell_exec_frag = ExecutionFragment(
            timestamp="2026-02-10T12:00:00Z",
            step="cell_step",
            status="success",
            executed_by="cell-1",
        )

        # Cell executed_by points to which cell ran it
        assert cell_exec_frag.executed_by == "cell-1"

    def test_hierarchical_chain_book_to_cell(self):
        """Verify executed_by forms proper parent→child chain."""
        # Root level (book has no executed_by)
        book_frag = ExecutionFragment(
            timestamp="2026-02-10T12:00:00Z",
            step="book_start",
            status="running",
            executed_by=None,  # Root has no parent
        )
        assert book_frag.executed_by is None

        # Child level (cell executed by book)
        cell_frag = ExecutionFragment(
            timestamp="2026-02-10T12:01:00Z",
            step="cell_execute",
            status="running",
            executed_by="book-1",  # Points to parent book
        )
        assert cell_frag.executed_by == "book-1"

        # Grand-child level (fragment created by cell)
        result_frag = ExecutionFragment(
            timestamp="2026-02-10T12:02:00Z",
            step="fragment_create",
            status="success",
            executed_by="cell-1",  # Points to parent cell
        )
        assert result_frag.executed_by == "cell-1"

        # Chain: book-1 → cell-1 → fragment visible through executed_by


class TestFragmentVsExecutionFragmentSeparation:
    """Verify Fragment and ExecutionFragment serve different purposes."""

    def test_fragment_ignores_execution_fields(self):
        """Fragment doesn't have execution-specific fields."""
        fragment = Fragment(
            type="metadata",
            content={"data": "value"},
            metadata={"custom": "metadata"}
        )
        # Fragment doesn't have these execution fields
        assert not hasattr(fragment, "step")
        assert not hasattr(fragment, "status")
        assert not hasattr(fragment, "executed_by")
        assert not hasattr(fragment, "input")
        assert not hasattr(fragment, "output")

    def test_execution_fragment_requires_execution_fields(self):
        """ExecutionFragment requires proper execution fields."""
        # All required fields
        exec_frag = ExecutionFragment(
            timestamp="2026-02-10T12:00:00Z",
            step="test_step",
            status="success",
        )
        assert exec_frag.timestamp == "2026-02-10T12:00:00Z"
        assert exec_frag.step == "test_step"
        assert exec_frag.status == "success"

    def test_pipeline_distinguishes_fragment_types(self):
        """Pipeline correctly handles both fragment types."""
        notebook_item = NotebookItem(assignee_id="user-1")
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="test-cell",
            assignee_id="user-1",
        )

        # Add Fragment
        frag = Fragment(type="log", content="test")
        pipeline.fragments.append(frag.model_dump())

        # Add ExecutionFragment
        exec_frag = ExecutionFragment(
            timestamp="2026-02-10T12:00:00Z",
            step="test",
            status="success",
            executed_by="cell-1",
        )
        pipeline.fragments.append(exec_frag.model_dump())

        # Check they're stored differently
        assert pipeline.fragments[0]["type"] == "log"
        assert "step" not in pipeline.fragments[0]

        assert pipeline.fragments[1]["step"] == "test"
        assert pipeline.fragments[1]["executed_by"] == "cell-1"
