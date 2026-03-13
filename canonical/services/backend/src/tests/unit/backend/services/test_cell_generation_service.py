"""
Unit tests for Cell Generation Service.

Tests cover code generation, dynamic ref extraction, and event publishing.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.cell_generation_service import CellGenerationService
from app.models import (
    Cell,
    CellGenerationRequest,
    DynamicRef,
    GenerationMetadata,
    CellStatus,
    ConversationMessage,
    RAGContext,
    EnrichedPrompt
)


class TestCellGenerationService:
    """Unit tests for CellGenerationService."""
    
    @pytest.fixture
    def service(self):
        """Create a CellGenerationService instance for testing."""
        return CellGenerationService(redis_service=None)
    
    @pytest.fixture
    def sample_cell(self):
        """Create a sample cell for testing."""
        return Cell(
            assignee_id="user-123",
            notebook_item_type_id="unclassified-cell-type",
            title="Test Cell",
            content="Generate a blue circle SVG",
            initial_data={}
        )
    
    @pytest.fixture
    def generation_request(self, sample_cell):
        """Create a sample generation request."""
        return CellGenerationRequest(
            cell_id=sample_cell.id,
            content="Generate a blue circle SVG",
            format="svg",
            model="gpt-4"
        )
    
    @pytest.mark.asyncio
    async def test_generate_cell_code_success(self, service, sample_cell, generation_request):
        """Test successful code generation."""
        # Mock database update
        with patch('app.services.cell_generation_service.db') as mock_db:
            mock_db.update = AsyncMock()
            
            # Generate code
            result = await service.generate_cell_code(generation_request, sample_cell)
            
            # Verify result
            assert result["success"] is True
            assert result["refs_count"] == 1
            assert "metadata" in result
            
            # Verify database was updated
            mock_db.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_code_mock_svg(self, service):
        """Test mock SVG code generation."""
        code = await service._generate_code_mock("Generate a circle", "svg")
        
        assert code.startswith('<svg')
        assert code.endswith('</svg>')
        assert 'circle' in code
    
    @pytest.mark.asyncio
    async def test_generate_code_mock_vue(self, service):
        """Test mock Vue component generation."""
        code = await service._generate_code_mock("Generate a component", "vue")
        
        assert '<template>' in code
        assert '</template>' in code
        assert '<script>' in code
        assert 'export default' in code
    
    @pytest.mark.asyncio
    async def test_generate_code_mock_javascript(self, service):
        """Test mock JavaScript code generation."""
        code = await service._generate_code_mock("Generate a function", "js")
        
        assert 'function' in code
        assert 'greet' in code
        assert 'console.log' in code
    
    @pytest.mark.asyncio
    async def test_generate_code_mock_python(self, service):
        """Test mock Python code generation."""
        code = await service._generate_code_mock("Generate a function", "python")
        
        assert 'def greet' in code
        assert 'return' in code
        assert 'if __name__' in code
    
    @pytest.mark.asyncio
    async def test_extract_dynamic_refs_svg(self, service):
        """Test dynamic ref extraction for SVG."""
        code = '<svg><circle/></svg>'
        refs = await service._extract_dynamic_refs(code, "svg")
        
        assert len(refs) == 1
        ref = refs[0]
        assert ref.type == "visual"
        assert ref.lang == "svg"
        assert ref.path.startswith("sandbox/assets/visual_")
        assert ref.path.endswith(".svg")
        assert ref.size_bytes == len(code.encode('utf-8'))
        assert ref.validated is False
    
    @pytest.mark.asyncio
    async def test_extract_dynamic_refs_vue(self, service):
        """Test dynamic ref extraction for Vue."""
        code = '<template><div>Test</div></template>'
        refs = await service._extract_dynamic_refs(code, "vue")
        
        assert len(refs) == 1
        ref = refs[0]
        assert ref.type == "component"
        assert ref.lang == "vue"
        assert ref.path.endswith(".vue")
    
    @pytest.mark.asyncio
    async def test_extract_dynamic_refs_javascript(self, service):
        """Test dynamic ref extraction for JavaScript."""
        code = 'function test() {}'
        refs = await service._extract_dynamic_refs(code, "js")
        
        assert len(refs) == 1
        ref = refs[0]
        assert ref.type == "logic"
        assert ref.lang == "js"
        assert ref.path.endswith(".js")
    
    @pytest.mark.asyncio
    async def test_extract_dynamic_refs_python(self, service):
        """Test dynamic ref extraction for Python."""
        code = 'def test(): pass'
        refs = await service._extract_dynamic_refs(code, "python")
        
        assert len(refs) == 1
        ref = refs[0]
        assert ref.type == "logic"
        assert ref.lang == "python"
        assert ref.path.endswith(".python")
    
    @pytest.mark.asyncio
    async def test_update_cell_with_refs(self, service, sample_cell):
        """Test updating cell with dynamic refs and metadata."""
        refs = [
            DynamicRef(
                type="visual",
                lang="svg",
                path="sandbox/assets/visual_123.svg",
                filename="visual_123.svg",
                size_bytes=100
            )
        ]
        
        metadata = GenerationMetadata(
            prompt="Generate SVG",
            model="gpt-4",
            attempts=1
        )
        
        with patch('app.services.cell_generation_service.db') as mock_db:
            mock_db.update = AsyncMock()
            
            await service._update_cell_with_refs(sample_cell, refs, metadata)
            
            # Verify cell was updated
            assert "dynamic_refs" in sample_cell.initial_data
            assert len(sample_cell.initial_data["dynamic_refs"]) == 1
            assert "generation_metadata" in sample_cell.initial_data
            
            # Verify database update was called
            mock_db.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_event_without_redis(self, service):
        """Test event publishing without Redis service (should log warning)."""
        from app.models.event_bus import EventTopic
        
        # Should not raise an error
        await service._publish_event(
            EventTopic.CELL_GENERATE_REQUEST,
            {"cell_id": "123"}
        )
    
    @pytest.mark.asyncio
    async def test_generate_cell_code_error_handling(self, service, sample_cell, generation_request):
        """Test error handling in code generation."""
        with patch('app.services.cell_generation_service.db') as mock_db:
            # Simulate database error
            mock_db.update = AsyncMock(side_effect=Exception("Database error"))
            
            # Should raise ValueError with wrapped exception
            with pytest.raises(ValueError, match="Code generation failed"):
                await service.generate_cell_code(generation_request, sample_cell)
    
    @pytest.mark.asyncio
    async def test_generate_cell_code_updates_metadata(self, service, sample_cell, generation_request):
        """Test that generation updates cell with correct metadata."""
        with patch('app.services.cell_generation_service.db') as mock_db:
            mock_db.update = AsyncMock()
            
            result = await service.generate_cell_code(generation_request, sample_cell)
            
            # Verify metadata was set
            metadata = result["metadata"]
            assert metadata["prompt"] == generation_request.content
            assert metadata["model"] == generation_request.model
            assert metadata["attempts"] == 1
            assert "generated_at" in metadata
    
    @pytest.mark.asyncio
    async def test_retrieve_conversation_history_from_cell(self, service):
        """Test retrieving conversation history from cell's initial_data."""
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="unclassified-cell-type",
            title="Test Cell",
            content="Test content",
            initial_data={
                "history": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there"}
                ]
            }
        )
        
        history = await service._retrieve_conversation_history(cell)
        
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[0].content == "Hello"
        assert history[1].role == "assistant"
        assert history[1].content == "Hi there"
    
    @pytest.mark.asyncio
    async def test_retrieve_conversation_history_from_initial_data(self, service):
        """Test retrieving conversation history from cell's initial_data."""
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="unclassified-cell-type",
            title="Test Cell",
            content="Test content",
            initial_data={
                "history": [
                    {"role": "user", "content": "How are you?"},
                    {"role": "assistant", "content": "I'm good!"}
                ]
            }
        )
        
        history = await service._retrieve_conversation_history(cell)
        
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[0].content == "How are you?"
    
    @pytest.mark.asyncio
    async def test_retrieve_conversation_history_empty(self, service, sample_cell):
        """Test retrieving conversation history when none exists."""
        history = await service._retrieve_conversation_history(sample_cell)
        
        assert len(history) == 0
    
    @pytest.mark.asyncio
    async def test_enrich_with_rag(self, service):
        """Test RAG context enrichment."""
        rag_context = await service._enrich_with_rag("Generate a chart")
        
        assert isinstance(rag_context, RAGContext)
        assert len(rag_context.relevant_docs) > 0
        assert "metadata" in rag_context.model_dump()
        assert rag_context.metadata["retrieval_method"] == "mock"
    
    @pytest.mark.asyncio
    async def test_format_enriched_prompt(self, service):
        """Test formatting enriched prompt with all context."""
        history = [
            ConversationMessage(role="user", content="Hello"),
            ConversationMessage(role="assistant", content="Hi")
        ]
        
        rag_context = RAGContext(
            relevant_docs=["Doc 1", "Doc 2"],
            metadata={}
        )
        
        enriched = await service._format_enriched_prompt(
            user_prompt="Generate SVG",
            conversation_history=history,
            rag_context=rag_context,
            format_constraint="svg",
            model="gpt-4"
        )
        
        assert isinstance(enriched, EnrichedPrompt)
        assert enriched.user_prompt == "Generate SVG"
        assert len(enriched.conversation_history) == 2
        assert enriched.rag_context is not None
        assert enriched.system_instructions is not None
        assert enriched.constraints["format"] == "svg"
        assert enriched.constraints["model"] == "gpt-4"
    
    @pytest.mark.asyncio
    async def test_format_enriched_prompt_without_rag(self, service):
        """Test formatting enriched prompt without RAG context."""
        enriched = await service._format_enriched_prompt(
            user_prompt="Generate JS",
            conversation_history=[],
            rag_context=None,
            format_constraint="js",
            model="gpt-4"
        )
        
        assert enriched.rag_context is None
        assert enriched.system_instructions is not None
    
    def test_build_system_instructions_svg(self, service):
        """Test building system instructions for SVG format."""
        instructions = service._build_system_instructions("svg")
        
        assert "expert code generator" in instructions.lower()
        assert "svg" in instructions.lower()
        assert "valid" in instructions.lower()
    
    def test_build_system_instructions_vue(self, service):
        """Test building system instructions for Vue format."""
        instructions = service._build_system_instructions("vue")
        
        assert "vue" in instructions.lower()
        assert "component" in instructions.lower()
    
    def test_build_system_instructions_auto(self, service):
        """Test building system instructions for auto format."""
        instructions = service._build_system_instructions("auto")
        
        assert "analyze" in instructions.lower()
        assert "appropriate format" in instructions.lower()
    
    @pytest.mark.asyncio
    async def test_generate_cell_code_with_conversation_history(self, service, sample_cell):
        """Test code generation with conversation history."""
        # Add history to cell initial_data
        sample_cell.initial_data = {
            "history": [
                {"role": "user", "content": "I want to create a chart"},
                {"role": "assistant", "content": "What type of chart?"}
            ]
        }
        
        request = CellGenerationRequest(
            cell_id=sample_cell.id,
            content="A bar chart showing sales",
            format="svg",
            model="gpt-4",
            conversation_id="conv-123"
        )
        
        with patch('app.services.cell_generation_service.db') as mock_db:
            mock_db.update = AsyncMock()
            
            result = await service.generate_cell_code(request, sample_cell)
            
            assert result["success"] is True
            assert "request_id" in result
    
    @pytest.mark.asyncio
    async def test_generate_cell_code_with_rag(self, service, sample_cell):
        """Test code generation with RAG enrichment."""
        request = CellGenerationRequest(
            cell_id=sample_cell.id,
            content="Generate visualization",
            format="svg",
            model="gpt-4",
            use_rag=True
        )
        
        with patch('app.services.cell_generation_service.db') as mock_db:
            mock_db.update = AsyncMock()
            
            result = await service.generate_cell_code(request, sample_cell)
            
            assert result["success"] is True
            assert "request_id" in result
