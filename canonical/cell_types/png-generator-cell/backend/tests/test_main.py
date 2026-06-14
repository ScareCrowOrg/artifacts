"""
Tests for png-generator-cell backend.
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock

# Add the cell scripts directory to Python path
cell_root = Path(__file__).parent.parent
sys.path.insert(0, str(cell_root / "scripts"))

import main


@pytest.fixture
def mock_queue_image_generation_job():
    """Fixture to mock queue_image_generation_job for tests."""
    async def _mock_generator(generate_return_value):
        """Create a mock for queue_image_generation_job async function."""
        print("[DIAP] mock_queue_image_generation_job called with return_value:", str(generate_return_value)[:100])
        async def mock_job(*args, **kwargs):
            print("[DIAP] mock_job executing with return_value:", str(generate_return_value)[:100])
            return generate_return_value
        return mock_job
    return _mock_generator


@pytest.mark.asyncio
class TestExecuteCell:
    """Tests for execute_cell function."""
    
    async def test_execute_cell_with_existing_png(self):
        """Test cell execution with already generated PNG."""
        cell_data = {
            "prompt": "A blue crystal",
            "generatedPng": "data:image/png;base64,iVBORw0KGgoAAAANS..."
        }
        
        result = await main.execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["message"] == "PNG already exists"
        assert result["has_png"] is True
        assert result["generatedPng"] == "data:image/png;base64,iVBORw0KGgoAAAANS..."
    
    async def test_execute_cell_empty_prompt(self):
        """Test cell execution with empty prompt."""
        cell_data = {
            "prompt": "",
            "generatedPng": None
        }
        
        result = await main.execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["prompt"] == ""
        assert result["has_png"] is False
        assert result["message"] == "No prompt provided"
    
    async def test_execute_cell_generates_png_success(self, mock_queue_image_generation_job):
        """Test cell execution that triggers PNG generation successfully."""
        cell_data = {
            "prompt": "A red dragon",
            "generatedPng": None
        }

        # Create mock using fixture
        mock_job = await mock_queue_image_generation_job({
            "success": True,
            "image_base64": "iVBORw0KGgoAAAANSbase64data...",
            "metadata": {
                "prompt": "A red dragon",
                "width": 512,
                "height": 512
            }
        })

        with patch('image_generation.queue_image_generation_job', mock_job):
            result = await main.execute_cell(cell_data)

        assert result["success"] is True
        assert result["message"] == "PNG generated successfully"
        assert result["has_png"] is True
        assert "generatedPng" in result
        assert result["generatedPng"].startswith("data:image/png;base64,")
        assert "fallback" not in result
    
    async def test_execute_cell_generates_png_failure(self, mock_queue_image_generation_job):
        """Test cell execution when image generation fails."""
        cell_data = {
            "prompt": "A mountain",
            "generatedPng": None
        }

        # Create mock using fixture
        mock_job = await mock_queue_image_generation_job({
            "success": False,
            "error": "Service timeout"
        })

        with patch('image_generation.queue_image_generation_job', mock_job):
            result = await main.execute_cell(cell_data)

        assert result["success"] is False
        assert "error" in result
        assert result["error"] == "Service timeout"


@pytest.mark.asyncio
class TestGeneratePngFromPrompt:
    """Tests for generate_png_from_prompt function."""
    
    async def test_generate_png_success(self, mock_queue_image_generation_job):
        """Test successful PNG generation."""
        mock_job = await mock_queue_image_generation_job({
            "success": True,
            "image_base64": "iVBORw0KGgoAAAANS...",
            "metadata": {
                "prompt": "A blue crystal",
                "width": 512,
                "height": 512,
                "steps": 20,
                "cfg_scale": 7.0,
                "seed": 12345
            }
        })

        with patch('image_generation.queue_image_generation_job', mock_job):
            result = await main.generate_png_from_prompt(
                prompt="A blue crystal",
                width=512,
                height=512,
                steps=20,
                cfg_scale=7.0,
                seed=-1
            )
        
        assert result["success"] is True
        assert "image_base64" in result
        assert result["prompt"] == "A blue crystal"
        assert "metadata" in result
    
    async def test_generate_png_with_negative_prompt(self, mock_queue_image_generation_job):
        """Test PNG generation with negative prompt."""
        mock_job = await mock_queue_image_generation_job({
            "success": True,
            "image_base64": "iVBORw0KGgoAAAANS...",
            "metadata": {
                "prompt": "A dragon",
                "negative_prompt": "blurry, low quality",
                "width": 512,
                "height": 512
            }
        })

        with patch('image_generation.queue_image_generation_job', mock_job):
            result = await main.generate_png_from_prompt(
                prompt="A dragon",
                negative_prompt="blurry, low quality"
            )
        
        assert result["success"] is True
        assert "image_base64" in result
    
    async def test_generate_png_with_3d_asset_mode_enabled(self, mock_queue_image_generation_job):
        """Test PNG generation with 3D Asset Mode enabled."""
        captured_calls = []

        async def capture_job(**kwargs):
            captured_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }

        with patch('image_generation.queue_image_generation_job', capture_job):
            result = await main.generate_png_from_prompt(
                prompt="A crystal warrior",
                asset_3d_mode=True
            )

        assert result["success"] is True
        assert len(captured_calls) == 1

        # Verify that 3D asset suffixes were added
        enhanced_prompt = captured_calls[0]["prompt"]
        assert "A crystal warrior" in enhanced_prompt
        # POSITIVE_SUFFIX_3D_ASSET provides flat lighting, orthographic view, etc.
        # Note: "full body" was removed from POSITIVE_SUFFIX_3D_ASSET in v5.0
        assert "flat lighting" in enhanced_prompt
        assert "orthographic view" in enhanced_prompt

        enhanced_negative = captured_calls[0]["negative_prompt"]
        assert "shadows" in enhanced_negative
        assert "dramatic lighting" in enhanced_negative
    
    async def test_generate_png_with_3d_asset_mode_and_custom_negative_prompt(self, mock_queue_image_generation_job):
        """Test PNG generation with 3D Asset Mode and custom negative prompt."""
        captured_calls = []

        async def capture_job(**kwargs):
            captured_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }

        with patch('image_generation.queue_image_generation_job', capture_job):
            result = await main.generate_png_from_prompt(
                prompt="A robot",
                negative_prompt="blurry, low quality",
                asset_3d_mode=True
            )

        assert result["success"] is True
        assert len(captured_calls) == 1

        # Verify that custom negative prompt is preserved and 3D suffix is appended
        enhanced_negative = captured_calls[0]["negative_prompt"]
        assert "blurry" in enhanced_negative
        assert "low quality" in enhanced_negative
        assert "shadows" in enhanced_negative
        assert "dramatic lighting" in enhanced_negative

        # Verify no keyword duplication
        keywords = [k.strip() for k in enhanced_negative.split(',')]
        assert len(keywords) == len(set(keywords)), "Should not have duplicate keywords"
    
    async def test_generate_png_3d_mode_deduplicates_keywords(self, mock_queue_image_generation_job):
        """Test that 3D Asset Mode properly deduplicates keywords in negative prompt."""
        captured_calls = []

        async def capture_job(**kwargs):
            captured_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }

        # User provides negative prompt with some keywords that overlap with 3D mode defaults
        with patch('image_generation.queue_image_generation_job', capture_job):
            result = await main.generate_png_from_prompt(
                prompt="A spaceship",
                negative_prompt="shadows, cluttered background, extra detail",
                asset_3d_mode=True
            )

        assert result["success"] is True
        assert len(captured_calls) == 1

        # Verify keywords appear only once
        enhanced_negative = captured_calls[0]["negative_prompt"]
        keywords = [k.strip() for k in enhanced_negative.split(',')]

        # Check no duplicates
        assert len(keywords) == len(set(keywords)), f"Found duplicate keywords: {keywords}"

        # Verify both user keywords and suffix keywords are present
        assert "shadows" in keywords
        assert "cluttered background" in keywords
        assert "extra detail" in keywords
        assert "dramatic lighting" in keywords
        assert "depth of field" in keywords
    
    async def test_generate_png_with_3d_asset_mode_disabled(self, mock_queue_image_generation_job):
        """Test PNG generation with 3D Asset Mode disabled (default)."""
        captured_calls = []

        async def capture_job(**kwargs):
            captured_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }

        with patch('image_generation.queue_image_generation_job', capture_job):
            result = await main.generate_png_from_prompt(
                prompt="A crystal warrior",
                asset_3d_mode=False
            )

        assert result["success"] is True
        assert len(captured_calls) == 1

        # Verify that prompts are NOT enhanced when 3D mode is disabled
        enhanced_prompt = captured_calls[0]["prompt"]
        assert enhanced_prompt == "A crystal warrior"
        assert "flat lighting" not in enhanced_prompt
    
    async def test_generate_png_service_failure(self, mock_queue_image_generation_job):
        """Test PNG generation when service returns failure."""
        mock_job = await mock_queue_image_generation_job({
            "success": False,
            "error": "Stable Diffusion API timeout"
        })

        with patch('image_generation.queue_image_generation_job', mock_job):
            result = await main.generate_png_from_prompt(
                prompt="A mountain"
            )

        assert result["success"] is False
        assert "error" in result
        assert "timeout" in result["error"].lower()
    
    async def test_generate_png_exception_handling(self, mock_queue_image_generation_job):
        """Test PNG generation exception handling."""
        async def mock_job_raise(*args, **kwargs):
            raise Exception("Connection error")

        with patch('image_generation.queue_image_generation_job', mock_job_raise):
            result = await main.generate_png_from_prompt(
                prompt="A forest"
            )

        assert result["success"] is False
        assert "error" in result
        assert "Connection error" in result["error"]


@pytest.mark.asyncio
class TestExecuteCellWith3DAssetMode:
    """Tests for execute_cell with 3D Asset Mode."""
    
    async def test_execute_cell_with_3d_asset_mode(self, mock_queue_image_generation_job):
        """Test cell execution with 3D Asset Mode enabled."""
        cell_data = {
            "prompt": "A space robot",
            "generatedPng": None,
            "asset3dMode": True,
            "negativePrompt": "cartoon style"
        }

        captured_calls = []

        async def capture_job(**kwargs):
            captured_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }

        # Mock Ollama to prevent real import (avoids chromadb/numpy conflict)
        mock_ollama_module = MagicMock()
        mock_ollama_module.verificar_ollama_disponivel = AsyncMock(return_value=False)
        mock_ollama_module.chamar_ollama = AsyncMock(return_value={"response": ""})

        with patch('image_generation.queue_image_generation_job', capture_job), \
             patch.dict('sys.modules', {'app.ollama_service': mock_ollama_module}):
            result = await main.execute_cell(cell_data)

        assert result["success"] is True
        assert result["has_png"] is True
        assert len(captured_calls) == 1

        # Verify 3D asset mode was applied (via static enhancement fallback)
        enhanced_prompt = captured_calls[0]["prompt"]
        assert "A space robot" in enhanced_prompt
        assert "flat lighting" in enhanced_prompt

        enhanced_negative = captured_calls[0]["negative_prompt"]
        assert "cartoon style" in enhanced_negative
        assert "shadows" in enhanced_negative


@pytest.mark.asyncio
class TestOllamaOrchestration:
    """Tests for Ollama orchestration in 3D Asset Mode."""
    
    async def test_ollama_orchestration_success(self, mock_queue_image_generation_job):
        """Test successful Ollama orchestration for prompt optimization."""
        # Mock Ollama service
        mock_ollama_module = MagicMock()
        mock_ollama_module.verificar_ollama_disponivel = AsyncMock(return_value=True)
        mock_ollama_module.chamar_ollama = AsyncMock(return_value={
            "response": "A detailed space robot, metallic surface, centered composition, front view orthographic, flat studio lighting, neutral gray background, high resolution, clear geometric shapes, technical precision"
        })

        # Capture calls to queue_image_generation_job
        captured_job_calls = []

        async def capture_job(**kwargs):
            captured_job_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }

        with patch.dict('sys.modules', {
            'app.ollama_service': mock_ollama_module,
        }), \
             patch('image_generation.queue_image_generation_job', capture_job):
            result = await main.generate_png_from_prompt(
                prompt="A space robot",
                asset_3d_mode=True
            )

        assert result["success"] is True

        # Verify Ollama was called
        mock_ollama_module.verificar_ollama_disponivel.assert_called_once()
        mock_ollama_module.chamar_ollama.assert_called_once()

        # Verify Ollama prompt contains system instructions
        ollama_call_args = mock_ollama_module.chamar_ollama.call_args[0][0]
        assert "ScareVerse Prompt Architect" in ollama_call_args
        assert "A space robot" in ollama_call_args
        # Note: "CRITICAL PROHIBITION" was removed from OLLAMA_SYSTEM_PROMPT_3D_ARCHITECT in v5.0
        # The constant now contains "flat lighting", "orthographic view", "4K" etc.

        # Verify SD was called with optimized prompt
        assert len(captured_job_calls) == 1
        sd_prompt = captured_job_calls[0]["prompt"]
        assert "metallic surface" in sd_prompt
        assert "flat studio lighting" in sd_prompt

        # Verify negative prompt uses base technical rendering guidelines
        # NEGATIVE_PROMPT_3D_ASSET_BASE was updated in v5.0 to exclude anti-biological keywords
        # (humans, hands, faces are now DESIRED for character assets)
        sd_negative = captured_job_calls[0]["negative_prompt"]
        assert "dramatic lighting" in sd_negative
        assert "artistic interpretation" in sd_negative
        assert "painting style" in sd_negative
    
    async def test_ollama_orchestration_ollama_unavailable(self, mock_queue_image_generation_job):
        """Test fallback to static enhancement when Ollama is unavailable."""
        # Mock Ollama service as unavailable
        mock_ollama_module = MagicMock()
        mock_ollama_module.verificar_ollama_disponivel = AsyncMock(return_value=False)

        # Capture calls to queue_image_generation_job
        captured_job_calls = []

        async def capture_job(**kwargs):
            captured_job_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }

        with patch.dict('sys.modules', {
            'app.ollama_service': mock_ollama_module,
        }), \
             patch('image_generation.queue_image_generation_job', capture_job):
            result = await main.generate_png_from_prompt(
                prompt="A magic sword",
                asset_3d_mode=True
            )

        assert result["success"] is True

        # Verify Ollama availability was checked
        mock_ollama_module.verificar_ollama_disponivel.assert_called_once()

        # Verify chamar_ollama was NOT called (Ollama unavailable)
        mock_ollama_module.chamar_ollama.assert_not_called()

        # Verify SD was called with static enhancement
        assert len(captured_job_calls) == 1
        sd_prompt = captured_job_calls[0]["prompt"]
        assert "A magic sword" in sd_prompt
        # POSITIVE_SUFFIX_3D_ASSET provides flat lighting, orthographic view, etc.
        # Note: "full body" was removed from POSITIVE_SUFFIX_3D_ASSET in v5.0
        assert "flat lighting" in sd_prompt
        assert "orthographic view" in sd_prompt
    
    async def test_ollama_orchestration_ollama_returns_empty(self, mock_queue_image_generation_job):
        """Test fallback to static enhancement when Ollama returns empty response."""
        # Mock Ollama service returning empty
        mock_ollama_module = MagicMock()
        mock_ollama_module.verificar_ollama_disponivel = AsyncMock(return_value=True)
        mock_ollama_module.chamar_ollama = AsyncMock(return_value={"response": ""})

        # Capture calls to queue_image_generation_job
        captured_job_calls = []

        async def capture_job(**kwargs):
            captured_job_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }

        with patch.dict('sys.modules', {
            'app.ollama_service': mock_ollama_module,
        }), \
             patch('image_generation.queue_image_generation_job', capture_job):
            result = await main.generate_png_from_prompt(
                prompt="A treasure chest",
                asset_3d_mode=True
            )

        assert result["success"] is True

        # Verify Ollama was called but returned empty
        mock_ollama_module.chamar_ollama.assert_called_once()

        # Verify SD was called with static enhancement (fallback)
        assert len(captured_job_calls) == 1
        sd_prompt = captured_job_calls[0]["prompt"]
        assert "A treasure chest" in sd_prompt
        # POSITIVE_SUFFIX_3D_ASSET provides static enhancement keywords
        # Note: "full body" was removed from POSITIVE_SUFFIX_3D_ASSET in v5.0
        assert "flat lighting" in sd_prompt
    
    async def test_ollama_orchestration_with_custom_negative_prompt(self, mock_queue_image_generation_job):
        """Test Ollama orchestration preserves user's negative prompt."""
        # Mock Ollama service
        mock_ollama_module = MagicMock()
        mock_ollama_module.verificar_ollama_disponivel = AsyncMock(return_value=True)
        # chamar_ollama is called twice: positive prompt first, negative prompt second
        # Use side_effect to return appropriate response for each call
        mock_ollama_module.chamar_ollama = AsyncMock(side_effect=[
            {"response": "A medieval shield with ornate details, centered view, flat lighting, gray background"},
            {"response": "rust, damage, scratches, artistic interpretation, painting style, dramatic lighting, shadows"},
        ])

        # Capture calls to queue_image_generation_job
        captured_job_calls = []

        async def capture_job(**kwargs):
            captured_job_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }

        with patch.dict('sys.modules', {
            'app.ollama_service': mock_ollama_module,
        }), \
             patch('image_generation.queue_image_generation_job', capture_job):
            result = await main.generate_png_from_prompt(
                prompt="A medieval shield",
                negative_prompt="rust, damage, scratches",
                asset_3d_mode=True
            )

        assert result["success"] is True

        # Verify SD negative prompt includes both user keywords and base negative
        assert len(captured_job_calls) == 1
        sd_negative = captured_job_calls[0]["negative_prompt"]

        # User keywords preserved
        assert "rust" in sd_negative
        assert "damage" in sd_negative
        assert "scratches" in sd_negative

        # Base negative keywords added (NEGATIVE_PROMPT_3D_ASSET_BASE excludes anti-biological
        # keywords in v5.0 - humans/hands/faces are now DESIRED for character assets)
        assert "dramatic lighting" in sd_negative
        assert "artistic interpretation" in sd_negative
    
    async def test_ollama_orchestration_exception_handling(self, mock_queue_image_generation_job):
        """Test fallback when Ollama raises exception."""
        # Mock Ollama service raising exception
        mock_ollama_module = MagicMock()
        mock_ollama_module.verificar_ollama_disponivel = AsyncMock(return_value=True)
        mock_ollama_module.chamar_ollama = AsyncMock(side_effect=Exception("Connection timeout"))

        # Capture calls to queue_image_generation_job
        captured_job_calls = []

        async def capture_job(**kwargs):
            captured_job_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }

        with patch.dict('sys.modules', {
            'app.ollama_service': mock_ollama_module,
        }), \
             patch('image_generation.queue_image_generation_job', capture_job):
            result = await main.generate_png_from_prompt(
                prompt="A magic staff",
                asset_3d_mode=True
            )

        assert result["success"] is True

        # Verify SD was called with static enhancement (fallback after exception)
        assert len(captured_job_calls) == 1
        sd_prompt = captured_job_calls[0]["prompt"]
        assert "A magic staff" in sd_prompt
        assert "flat lighting" in sd_prompt


def test_static_3d_enhancement():
    """Test the static 3D enhancement helper function."""
    prompt = "A wooden barrel"
    negative_prompt = None
    
    enhanced_prompt, enhanced_negative = main._apply_static_3d_enhancement(prompt, negative_prompt)
    
    # Check positive enhancement
    assert "A wooden barrel" in enhanced_prompt
    # POSITIVE_SUFFIX_3D_ASSET no longer contains "full body" (removed in v5.0)
    # It now provides: centered, front view, flat lighting, studio background,
    # neutral gray background, high resolution, orthographic view
    assert "flat lighting" in enhanced_prompt
    assert "orthographic view" in enhanced_prompt
    
    # Check negative enhancement
    assert "shadows" in enhanced_negative
    assert "dramatic lighting" in enhanced_negative
    assert "cluttered background" in enhanced_negative


def test_static_3d_enhancement_with_custom_negative():
    """Test static 3D enhancement with custom negative prompt."""
    prompt = "A steel helmet"
    negative_prompt = "rust, damage"
    
    enhanced_prompt, enhanced_negative = main._apply_static_3d_enhancement(prompt, negative_prompt)
    
    # Check positive enhancement
    assert "A steel helmet" in enhanced_prompt
    
    # Check negative enhancement preserves user keywords
    assert "rust" in enhanced_negative
    assert "damage" in enhanced_negative
    assert "shadows" in enhanced_negative
    
@pytest.mark.asyncio
class TestAutoPersist:
    """Tests for the auto-persist flow in handle_generate_png (v5.0)."""

    @pytest.fixture
    def mock_redis_magro_result(self, mock_queue_image_generation_job):
        """Fixture: queue_image_generation_job returns Redis Magro result with relative_url."""
        async def _setup():
            return await mock_queue_image_generation_job({
                "success": True,
                "relative_url": "/runtime/user/test-assignee/contents/job-uuid/job-uuid.png",
                "content_id": "job-uuid",
                "mime_type": "image/png",
                "metadata": {"width": 512, "height": 512},
            })
        return _setup

    @pytest.fixture
    def mock_auto_persist_modules(self):
        """
        Mock the modules needed for auto-persist:
        - app.services.content_manager (ContentManager, ContentTypeLoader)
        - app.models.content_types (CreateContentRequest)
        - storage (get_storage_backend)
        - app.database (db)
        """
        # Create the mock content
        mock_content = MagicMock()
        mock_content.id = "mongo-uuid-1234"

        # Create mock ContentManager
        mock_content_manager = MagicMock(spec=main.ContentManager if hasattr(main, 'ContentManager') else object)
        mock_content_manager.create_content = AsyncMock(return_value=mock_content)

        # Create mock ContentTypeLoader
        mock_content_type_loader = MagicMock()

        # Create mock content_manager module
        mock_cm_module = MagicMock()
        mock_cm_module.ContentManager = MagicMock(return_value=mock_content_manager)
        mock_cm_module.ContentTypeLoader = MagicMock(return_value=mock_content_type_loader)

        # Create mock content_types module
        mock_ct_module = MagicMock()
        mock_ct_module.CreateContentRequest = MagicMock()

        # Create mock storage module
        mock_storage = MagicMock()
        mock_storage.upload = MagicMock(return_value="local://runtime/user/test-assignee/contents/mongo-uuid-1234/file.png")
        mock_storage_module = MagicMock()
        mock_storage_module.get_storage_backend = MagicMock(return_value=mock_storage)

        # Create mock database module
        mock_db = MagicMock()
        mock_db.update = AsyncMock(return_value=None)
        mock_db_module = MagicMock()
        mock_db_module.db = mock_db

        return {
            'app.services.content_manager': mock_cm_module,
            'app.models.content_types': mock_ct_module,
            'storage': mock_storage_module,
            'app.database': mock_db_module,
        }

    @staticmethod
    def _make_mock_user(user_id="test-user-id"):
        """Create a simple mock user object with .id attribute."""
        user = MagicMock()
        user.id = user_id
        return user

    async def test_auto_persist_success(self, mock_redis_magro_result, mock_auto_persist_modules):
        """Auto-persist should create Content in MongoDB and return MongoDB _id as content_id."""
        print("[DIAP] test_auto_persist_success: START - should create Content, upload to storage, update data_ref")
        mock_job = await mock_redis_magro_result()
        mock_user = self._make_mock_user()

        cell_data = {
            "prompt": "A test image",
            "generatedPng": None,
            "generationParams": {"width": 512, "height": 512},
            "_current_user": mock_user,
        }

        with patch('image_generation.queue_image_generation_job', mock_job), \
             patch.dict('sys.modules', mock_auto_persist_modules), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', MagicMock()) as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = b"fake-png-binary-data"
            mock_open.return_value = mock_file

            result = await main.execute_cell(cell_data, user_id="test-user-id")

        # Verify overall success
        assert result["success"] is True
        assert result["has_png"] is True
        assert result["relative_url"] == "/runtime/user/test-assignee/contents/job-uuid/job-uuid.png"

        # Verify auto-persist set the MongoDB _id
        assert result["content_id"] is not None
        assert result["content_id"] != "job-uuid"  # Should be MongoDB _id, not job_id
        assert result["auto_persisted"] is True

        # Verify ContentManager was called
        cm_module = mock_auto_persist_modules['app.services.content_manager']
        content_manager_instance = cm_module.ContentManager.return_value
        assert content_manager_instance.create_content.called

        # Verify storage upload was called
        storage_module = mock_auto_persist_modules['storage']
        storage_instance = storage_module.get_storage_backend.return_value
        assert storage_instance.upload.called

        # Verify db.update was called
        db_module = mock_auto_persist_modules['app.database']
        assert db_module.db.update.called

    async def test_auto_persist_graceful_degradation(self, mock_redis_magro_result, mock_auto_persist_modules):
        """If auto-persist fails, should fall back to relative_url only (no MongoDB content_id)."""
        print("[DIAP] test_auto_persist_graceful_degradation: START - ContentManager.create_content will raise Exception")
        mock_job = await mock_redis_magro_result()
        mock_user = self._make_mock_user()

        # Make ContentManager.create_content raise an exception
        failing_cm_module = mock_auto_persist_modules['app.services.content_manager']
        failing_content_manager = MagicMock()
        failing_content_manager.create_content = AsyncMock(side_effect=Exception("MongoDB connection refused"))
        failing_cm_module.ContentManager = MagicMock(return_value=failing_content_manager)

        cell_data = {
            "prompt": "A test image",
            "generatedPng": None,
            "generationParams": {"width": 512, "height": 512},
            "_current_user": mock_user,
        }

        with patch('image_generation.queue_image_generation_job', mock_job), \
             patch.dict('sys.modules', mock_auto_persist_modules):
            result = await main.execute_cell(cell_data, user_id="test-user-id")

        # Verify generation still succeeds despite auto-persist failure
        assert result["success"] is True
        assert result["has_png"] is True
        assert result["relative_url"] == "/runtime/user/test-assignee/contents/job-uuid/job-uuid.png"

        # Verify auto-persist gracefully degraded
        assert result["auto_persisted"] is False

        # Verify fallback to job_id (original behavior preserved)
        assert result["content_id"] == "job-uuid"

    async def test_auto_persist_no_current_user(self, mock_redis_magro_result):
        """Without _current_user, auto-persist should be skipped, generation still works."""
        print("[DIAP] test_auto_persist_no_current_user: START - _current_user NOT provided, should skip auto-persist")
        mock_job = await mock_redis_magro_result()

        cell_data = {
            "prompt": "A test image",
            "generatedPng": None,
            "generationParams": {"width": 512, "height": 512},
            # NO _current_user
        }

        with patch('image_generation.queue_image_generation_job', mock_job):
            result = await main.execute_cell(cell_data, user_id=None)

        assert result["success"] is True
        assert result["has_png"] is True
        assert result["relative_url"] == "/runtime/user/test-assignee/contents/job-uuid/job-uuid.png"
        assert result["auto_persisted"] is False
        assert result["content_id"] == "job-uuid"

    async def test_auto_persist_file_not_found(self, mock_redis_magro_result, mock_auto_persist_modules):
        """If the PNG file is not found on disk, auto-persist should skip gracefully."""
        print("[DIAP] test_auto_persist_file_not_found: START - os.path.exists will return False, should skip")
        mock_job = await mock_redis_magro_result()
        mock_user = self._make_mock_user()

        # Mock os.path.exists to return False (file not found)
        cell_data = {
            "prompt": "A test image",
            "generatedPng": None,
            "generationParams": {"width": 512, "height": 512},
            "_current_user": mock_user,
        }

        with patch('image_generation.queue_image_generation_job', mock_job), \
             patch.dict('sys.modules', mock_auto_persist_modules), \
             patch('os.path.exists', return_value=False):
            result = await main.execute_cell(cell_data, user_id="test-user-id")

        assert result["success"] is True
        assert result["has_png"] is True
        assert result["relative_url"] == "/runtime/user/test-assignee/contents/job-uuid/job-uuid.png"
        assert result["auto_persisted"] is False
        assert result["content_id"] == "job-uuid"

        # Verify ContentManager was NOT called (file not found)
        cm_module = mock_auto_persist_modules['app.services.content_manager']
        content_manager_instance = cm_module.ContentManager.return_value
        assert not content_manager_instance.create_content.called
