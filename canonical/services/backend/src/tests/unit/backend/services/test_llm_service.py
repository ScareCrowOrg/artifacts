"""
Tests for LLM Service (MVP 2).

Tests real OpenAI integration with mocking for:
1. Streaming code generation
2. Non-streaming generation
3. Message building
4. Error handling
5. API key validation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.llm_service import LLMService
from app.models import (
    EnrichedPrompt,
    ConversationMessage,
    RAGContext
)


@pytest.fixture
def llm_service():
    """Create LLM service with mock API key."""
    return LLMService(api_key="test-api-key")


@pytest.fixture
def enriched_prompt():
    """Create sample enriched prompt."""
    return EnrichedPrompt(
        user_prompt="Generate a bar chart",
        conversation_history=[
            ConversationMessage(
                role="user",
                content="Hello",
                timestamp=datetime.utcnow()
            ),
            ConversationMessage(
                role="assistant",
                content="Hi! How can I help?",
                timestamp=datetime.utcnow()
            )
        ],
        rag_context=RAGContext(
            relevant_docs=["Doc 1", "Doc 2"],
            metadata={}
        ),
        system_instructions="You are a code generation assistant.",
        constraints={"format": "svg", "model": "gpt-4"}
    )


class TestLLMService:
    """Test suite for LLM Service."""
    
    @pytest.mark.asyncio
    async def test_initialization_with_api_key(self):
        """Test LLM service initialization with API key."""
        service = LLMService(api_key="test-key")
        assert service.api_key == "test-key"
        assert service.client is not None
        assert service.max_retries == 3
        assert service.timeout == 60
    
    @pytest.mark.asyncio
    async def test_initialization_without_api_key(self):
        """Test LLM service initialization without API key."""
        with patch('app.config.OPENAI_API_KEY', None):
            service = LLMService()
            assert service.client is None
    
    @pytest.mark.asyncio
    async def test_build_messages(self, llm_service, enriched_prompt):
        """Test building OpenAI messages from enriched prompt."""
        messages = llm_service._build_messages(enriched_prompt)
        
        # Should have: system + rag + 2 history + user = 5 messages
        assert len(messages) == 5
        
        # First message should be system instructions
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == enriched_prompt.system_instructions
        
        # Second message should be RAG context
        assert messages[1]["role"] == "system"
        assert "Relevant context" in messages[1]["content"]
        
        # Last message should be user prompt
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == enriched_prompt.user_prompt
    
    @pytest.mark.asyncio
    async def test_build_messages_without_rag(self, llm_service):
        """Test building messages without RAG context."""
        prompt = EnrichedPrompt(
            user_prompt="Test prompt",
            conversation_history=[],
            rag_context=None,
            system_instructions="System",
            constraints={}
        )
        
        messages = llm_service._build_messages(prompt)
        
        # Should have: system + user = 2 messages
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
    
    @pytest.mark.asyncio
    async def test_generate_code_streaming_mock(self, llm_service, enriched_prompt):
        """Test streaming code generation with mocked OpenAI response."""
        # Mock OpenAI streaming response
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta = MagicMock()
        
        # Simulate streaming: narrative + code block + complete
        chunks_content = [
            "Generating code...\n",
            "```svg\n",
            '<svg width="100" height="100">',
            '<circle cx="50" cy="50" r="40"/>',
            '</svg>\n',
            "```\n",
            ""
        ]
        
        async def mock_stream():
            for content in chunks_content:
                mock_chunk.choices[0].delta.content = content
                yield mock_chunk
        
        # Use AsyncMock properly for async method
        mock_create = AsyncMock(return_value=mock_stream())
        with patch.object(llm_service.client.chat.completions, 'create', mock_create):
            chunks = []
            async for chunk in llm_service.generate_code_streaming(enriched_prompt):
                chunks.append(chunk)
            
            # Should have narrative, code, and complete chunks
            assert len(chunks) > 0
            
            # Check for completion chunk
            complete_chunks = [c for c in chunks if c["type"] == "complete"]
            assert len(complete_chunks) == 1
            assert "metadata" in complete_chunks[0]
    
    @pytest.mark.asyncio
    async def test_generate_code_streaming_without_api_key(self, enriched_prompt):
        """Test streaming generation fails without API key."""
        service = LLMService(api_key=None)
        
        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            async for _ in service.generate_code_streaming(enriched_prompt):
                pass
    
    @pytest.mark.asyncio
    async def test_generate_code_non_streaming(self, llm_service, enriched_prompt):
        """Test non-streaming code generation."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated code"
        
        # Use AsyncMock for async method
        mock_create = AsyncMock(return_value=mock_response)
        with patch.object(
            llm_service.client.chat.completions,
            'create',
            mock_create
        ):
            result = await llm_service.generate_code_non_streaming(enriched_prompt)
            assert result == "Generated code"
    
    @pytest.mark.asyncio
    async def test_validate_api_key_success(self, llm_service):
        """Test API key validation success."""
        mock_response = MagicMock()
        
        # Use AsyncMock for async method
        mock_create = AsyncMock(return_value=mock_response)
        with patch.object(
            llm_service.client.chat.completions,
            'create',
            mock_create
        ):
            is_valid = await llm_service.validate_api_key()
            assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_validate_api_key_failure(self, llm_service):
        """Test API key validation failure."""
        from openai import OpenAIError
        
        # Use AsyncMock that raises OpenAIError (not generic Exception)
        mock_create = AsyncMock(side_effect=OpenAIError("Invalid API key"))
        with patch.object(
            llm_service.client.chat.completions,
            'create',
            mock_create
        ):
            is_valid = await llm_service.validate_api_key()
            assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_get_supported_models(self, llm_service):
        """Test getting supported models."""
        models = llm_service.get_supported_models()
        
        assert len(models) > 0
        assert "gpt-4" in models
        assert "gpt-3.5-turbo" in models
    
    @pytest.mark.asyncio
    async def test_streaming_fence_block_detection(self, llm_service, enriched_prompt):
        """Test that streaming correctly detects fence blocks."""
        # Mock streaming with fence blocks
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta = MagicMock()
        
        chunks_content = [
            "Here's the code:\n",
            "```python\n",
            "def hello():\n",
            "    return 'world'\n",
            "```\n"
        ]
        
        async def mock_stream():
            for content in chunks_content:
                mock_chunk.choices[0].delta.content = content
                yield mock_chunk
        
        # Use AsyncMock for async method
        mock_create = AsyncMock(return_value=mock_stream())
        with patch.object(llm_service.client.chat.completions, 'create', mock_create):
            chunks = []
            async for chunk in llm_service.generate_code_streaming(enriched_prompt):
                chunks.append(chunk)
            
            # Should have code chunks with fence detected
            code_chunks = [c for c in chunks if c["type"] == "code"]
            assert len(code_chunks) > 0
            
            # Check fence language detected
            if code_chunks:
                assert code_chunks[0]["fence"] == "python"
    
    @pytest.mark.asyncio
    async def test_streaming_error_handling(self, llm_service, enriched_prompt):
        """Test error handling during streaming."""
        with patch.object(
            llm_service.client.chat.completions,
            'create',
            side_effect=Exception("API error")
        ):
            with pytest.raises(Exception, match="API error"):
                async for _ in llm_service.generate_code_streaming(enriched_prompt):
                    pass
