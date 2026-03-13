"""
Tests for Cell Factory models.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.cell_factory import (
    DynamicRef,
    GenerationMetadata,
    SandboxExecutionState,
    UnclassifiedCellData,
    CellPromotionRequest,
    CellPromotionResponse,
    CellGenerationRequest,
    CellGenerationResponse
)


class TestDynamicRef:
    """Tests for DynamicRef model."""
    
    def test_create_dynamic_ref(self):
        """Test creating a valid dynamic ref."""
        ref = DynamicRef(
            type='logic',
            lang='js',
            path='sandbox/assets/logic_123.js',
            filename='logic_123.js',
            size_bytes=1024
        )
        
        assert ref.id is not None
        assert ref.type == 'logic'
        assert ref.lang == 'js'
        assert ref.validated is False
        assert ref.validation_errors == []
        assert isinstance(ref.created_at, datetime)
    
    def test_dynamic_ref_types(self):
        """Test all valid ref types."""
        types = ['logic', 'style', 'data', 'component', 'visual']
        
        for ref_type in types:
            ref = DynamicRef(
                type=ref_type,
                lang='js',
                path=f'sandbox/assets/{ref_type}_123.js',
                filename=f'{ref_type}_123.js',
                size_bytes=100
            )
            assert ref.type == ref_type
    
    def test_dynamic_ref_languages(self):
        """Test all valid languages."""
        languages = ['js', 'css', 'json', 'vue', 'svg', 'python', 'html']
        
        for lang in languages:
            ref = DynamicRef(
                type='logic',
                lang=lang,
                path=f'sandbox/assets/file.{lang}',
                filename=f'file.{lang}',
                size_bytes=100
            )
            assert ref.lang == lang
    
    def test_dynamic_ref_validation(self):
        """Test ref with validation results."""
        ref = DynamicRef(
            type='logic',
            lang='js',
            path='sandbox/assets/logic.js',
            filename='logic.js',
            size_bytes=500,
            validated=True,
            validation_errors=[]
        )
        
        assert ref.validated is True
        assert len(ref.validation_errors) == 0
    
    def test_dynamic_ref_validation_errors(self):
        """Test ref with validation errors."""
        errors = ['Syntax error on line 5', 'Missing semicolon']
        ref = DynamicRef(
            type='logic',
            lang='js',
            path='sandbox/assets/logic.js',
            filename='logic.js',
            size_bytes=500,
            validated=False,
            validation_errors=errors
        )
        
        assert ref.validated is False
        assert ref.validation_errors == errors
    
    def test_dynamic_ref_negative_size(self):
        """Test that negative size is rejected."""
        with pytest.raises(ValidationError):
            DynamicRef(
                type='logic',
                lang='js',
                path='sandbox/assets/logic.js',
                filename='logic.js',
                size_bytes=-100
            )
    
    def test_dynamic_ref_json_serialization(self):
        """Test JSON serialization."""
        ref = DynamicRef(
            type='visual',
            lang='svg',
            path='sandbox/assets/chart.svg',
            filename='chart.svg',
            size_bytes=2048
        )
        
        data = ref.model_dump(mode='json')
        assert data['type'] == 'visual'
        assert data['lang'] == 'svg'
        assert isinstance(data['created_at'], str)


class TestGenerationMetadata:
    """Tests for GenerationMetadata model."""
    
    def test_create_generation_metadata(self):
        """Test creating valid generation metadata."""
        metadata = GenerationMetadata(
            prompt='Generate a bar chart',
            model='gpt-4'
        )
        
        assert metadata.prompt == 'Generate a bar chart'
        assert metadata.model == 'gpt-4'
        assert metadata.attempts == 1
        assert metadata.validation_errors == []
        assert metadata.auto_corrected is False
        assert metadata.promotion_ready is False
        assert isinstance(metadata.generated_at, datetime)
        assert metadata.completed_at is None
    
    def test_generation_metadata_with_attempts(self):
        """Test metadata with multiple attempts."""
        metadata = GenerationMetadata(
            prompt='Test prompt',
            model='gpt-4',
            attempts=3,
            auto_corrected=True
        )
        
        assert metadata.attempts == 3
        assert metadata.auto_corrected is True
    
    def test_generation_metadata_attempts_range(self):
        """Test attempts must be between 1 and 3."""
        with pytest.raises(ValidationError):
            GenerationMetadata(
                prompt='Test',
                model='gpt-4',
                attempts=0
            )
        
        with pytest.raises(ValidationError):
            GenerationMetadata(
                prompt='Test',
                model='gpt-4',
                attempts=4
            )
    
    def test_generation_metadata_promotion_ready(self):
        """Test promotion ready flag."""
        metadata = GenerationMetadata(
            prompt='Test prompt',
            model='gpt-4',
            promotion_ready=True,
            completed_at=datetime.utcnow()
        )
        
        assert metadata.promotion_ready is True
        assert isinstance(metadata.completed_at, datetime)
    
    def test_generation_metadata_with_errors(self):
        """Test metadata with validation errors."""
        errors = ['Syntax error', 'Security violation']
        metadata = GenerationMetadata(
            prompt='Test',
            model='gpt-4',
            attempts=2,
            validation_errors=errors
        )
        
        assert metadata.validation_errors == errors


class TestSandboxExecutionState:
    """Tests for SandboxExecutionState model."""
    
    def test_create_sandbox_state(self):
        """Test creating sandbox execution state."""
        state = SandboxExecutionState(
            cell_id='test-cell-123',
            status='booting'
        )
        
        assert state.cell_id == 'test-cell-123'
        assert state.status == 'booting'
        assert state.booted_at is None
        assert state.console_output == []
    
    def test_sandbox_state_all_statuses(self):
        """Test all valid statuses."""
        statuses = ['booting', 'running', 'completed', 'error', 'timeout', 'terminated']
        
        for status in statuses:
            state = SandboxExecutionState(
                cell_id='test-cell',
                status=status
            )
            assert state.status == status
    
    def test_sandbox_state_completed(self):
        """Test completed sandbox state."""
        booted = datetime.utcnow()
        completed = datetime.utcnow()
        
        state = SandboxExecutionState(
            cell_id='test-cell',
            status='completed',
            booted_at=booted,
            completed_at=completed,
            execution_duration_ms=250.5
        )
        
        assert state.status == 'completed'
        assert state.booted_at == booted
        assert state.completed_at == completed
        assert state.execution_duration_ms == 250.5
    
    def test_sandbox_state_with_error(self):
        """Test sandbox state with error."""
        state = SandboxExecutionState(
            cell_id='test-cell',
            status='error',
            error_message='Syntax error in code'
        )
        
        assert state.status == 'error'
        assert state.error_message == 'Syntax error in code'
    
    def test_sandbox_state_with_console_output(self):
        """Test sandbox state with console output."""
        output = ['Hello world', 'Error: undefined variable']
        state = SandboxExecutionState(
            cell_id='test-cell',
            status='running',
            console_output=output
        )
        
        assert state.console_output == output
    
    def test_sandbox_state_with_resource_usage(self):
        """Test sandbox state with resource usage."""
        resources = {
            'memory_mb': 45.5,
            'cpu_time_ms': 150
        }
        state = SandboxExecutionState(
            cell_id='test-cell',
            status='completed',
            resource_usage=resources
        )
        
        assert state.resource_usage == resources


class TestUnclassifiedCellData:
    """Tests for UnclassifiedCellData model."""
    
    def test_create_unclassified_cell_data(self):
        """Test creating unclassified cell data."""
        data = UnclassifiedCellData()
        
        assert data.title == "Nova Célula Sem Título"
        assert data.content == ""
        assert data.category == "persistida"
        assert data.icon == "📋"
        assert data.dynamic_refs == []
        assert data.generation_metadata is None
        assert data.sandbox_state is None
    
    def test_unclassified_cell_data_with_custom_values(self):
        """Test cell data with custom values."""
        data = UnclassifiedCellData(
            title="My Custom Cell",
            content="# Test content",
            category="ephemeral",
            icon="🎨"
        )
        
        assert data.title == "My Custom Cell"
        assert data.content == "# Test content"
        assert data.category == "ephemeral"
        assert data.icon == "🎨"
    
    def test_unclassified_cell_data_with_dynamic_refs(self):
        """Test cell data with dynamic refs."""
        ref1 = DynamicRef(
            type='logic',
            lang='js',
            path='sandbox/assets/logic.js',
            filename='logic.js',
            size_bytes=1024
        )
        ref2 = DynamicRef(
            type='visual',
            lang='svg',
            path='sandbox/assets/chart.svg',
            filename='chart.svg',
            size_bytes=2048
        )
        
        data = UnclassifiedCellData(
            dynamic_refs=[ref1, ref2]
        )
        
        assert len(data.dynamic_refs) == 2
        assert data.dynamic_refs[0].type == 'logic'
        assert data.dynamic_refs[1].type == 'visual'
    
    def test_unclassified_cell_data_with_generation_metadata(self):
        """Test cell data with generation metadata."""
        metadata = GenerationMetadata(
            prompt='Generate a chart',
            model='gpt-4',
            promotion_ready=True
        )
        
        data = UnclassifiedCellData(
            generation_metadata=metadata
        )
        
        assert data.generation_metadata is not None
        assert data.generation_metadata.prompt == 'Generate a chart'
        assert data.generation_metadata.promotion_ready is True
    
    def test_unclassified_cell_data_with_sandbox_state(self):
        """Test cell data with sandbox state."""
        state = SandboxExecutionState(
            cell_id='test-cell',
            status='completed'
        )
        
        data = UnclassifiedCellData(
            sandbox_state=state
        )
        
        assert data.sandbox_state is not None
        assert data.sandbox_state.status == 'completed'


class TestCellPromotionRequest:
    """Tests for CellPromotionRequest model."""
    
    def test_create_promotion_request(self):
        """Test creating promotion request."""
        request = CellPromotionRequest(
            cell_id='test-cell-123',
            new_type_name='custom-chart-cell'
        )
        
        assert request.cell_id == 'test-cell-123'
        assert request.new_type_name == 'custom-chart-cell'
        assert request.category == 'generated'
        assert request.new_type_description is None
    
    def test_promotion_request_with_description(self):
        """Test promotion request with description."""
        request = CellPromotionRequest(
            cell_id='test-cell',
            new_type_name='my-cell-type',
            new_type_description='A custom cell for charts',
            category='visualization'
        )
        
        assert request.new_type_description == 'A custom cell for charts'
        assert request.category == 'visualization'
    
    def test_promotion_request_name_length(self):
        """Test name length validation."""
        with pytest.raises(ValidationError):
            CellPromotionRequest(
                cell_id='test-cell',
                new_type_name='ab'  # Too short
            )
        
        with pytest.raises(ValidationError):
            CellPromotionRequest(
                cell_id='test-cell',
                new_type_name='a' * 101  # Too long
            )


class TestCellPromotionResponse:
    """Tests for CellPromotionResponse model."""
    
    def test_create_promotion_response(self):
        """Test creating promotion response."""
        response = CellPromotionResponse(
            success=True,
            new_cell_type_id='type-123',
            new_cell_id='cell-456',
            layout_book_synced=True,
            persisted_assets_count=3,
            message='Cell promoted successfully'
        )
        
        assert response.success is True
        assert response.new_cell_type_id == 'type-123'
        assert response.new_cell_id == 'cell-456'
        assert response.layout_book_synced is True
        assert response.persisted_assets_count == 3
        assert isinstance(response.promoted_at, datetime)


class TestCellGenerationRequest:
    """Tests for CellGenerationRequest model."""
    
    def test_create_generation_request(self):
        """Test creating generation request."""
        request = CellGenerationRequest(
            cell_id='test-cell-123',
            content='Generate a bar chart with data [10, 20, 30]'
        )
        
        assert request.cell_id == 'test-cell-123'
        assert request.content == 'Generate a bar chart with data [10, 20, 30]'
        assert request.format == 'auto'
        assert request.model == 'gpt-4'
    
    def test_generation_request_custom_format(self):
        """Test generation request with custom format."""
        formats = ['svg', 'vue', 'js', 'python', 'auto']
        
        for fmt in formats:
            request = CellGenerationRequest(
                cell_id='test-cell',
                content='Test content for generation',
                format=fmt
            )
            assert request.format == fmt
    
    def test_generation_request_content_min_length(self):
        """Test content minimum length validation."""
        with pytest.raises(ValidationError):
            CellGenerationRequest(
                cell_id='test-cell',
                content='short'  # Too short
            )


class TestCellGenerationResponse:
    """Tests for CellGenerationResponse model."""
    
    def test_create_generation_response(self):
        """Test creating generation response."""
        response = CellGenerationResponse(
            success=True,
            cell_id='test-cell-123',
            message='Generation initiated'
        )
        
        assert response.success is True
        assert response.cell_id == 'test-cell-123'
        assert response.stream_available is True
        assert response.message == 'Generation initiated'
    
    def test_generation_response_no_stream(self):
        """Test generation response without streaming."""
        response = CellGenerationResponse(
            success=False,
            cell_id='test-cell',
            stream_available=False,
            message='Generation failed'
        )
        
        assert response.success is False
        assert response.stream_available is False
