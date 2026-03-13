"""
Unit tests for Query Expander Service.

Tests bilingual query expansion functionality for RAG vector search,
including successful expansion, error handling, and fallback scenarios.

Technical naming: All functions and variables in English.
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock
from app.services.query_expander_service import (
    generate_expanded_query,
    generate_expanded_query_with_context,
    DEFAULT_EXPANSION_MODEL,
    MAX_EXPANDED_TERMS,
    QUERY_EXPANSION_PROMPT_TEMPLATE
)


class TestGenerateExpandedQuery:
    """Tests for generate_expanded_query function."""
    
    @pytest.mark.asyncio
    async def test_successful_query_expansion(self):
        """Test successful query expansion with bilingual terms."""
        user_message = "Como criar uma célula?"
        expanded_response = (
            "célula, cell, criar, create, novo, new, item, notebook, "
            "estrutura, structure"
        )
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {"response": expanded_response}
            
            result = await generate_expanded_query(user_message)
            
            # Verify result
            assert result == expanded_response
            
            # Verify ollama was called correctly
            mock_ollama.assert_called_once()
            call_args = mock_ollama.call_args
            assert call_args.kwargs['model'] == DEFAULT_EXPANSION_MODEL
            assert call_args.kwargs['stream'] is False
            assert user_message in call_args.kwargs['prompt']
    
    @pytest.mark.asyncio
    async def test_expansion_with_custom_model(self):
        """Test query expansion with custom model."""
        user_message = "Explain architecture"
        custom_model = "llama2:latest"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {"response": "architecture, arquitetura, design"}
            
            result = await generate_expanded_query(user_message, model=custom_model)
            
            assert result is not None
            mock_ollama.assert_called_once()
            assert mock_ollama.call_args.kwargs['model'] == custom_model
    
    @pytest.mark.asyncio
    async def test_expansion_truncates_excessive_terms(self):
        """Test that expansion truncates when exceeding max_terms."""
        user_message = "Test query"
        # Create response with 15 terms (exceeds default MAX_EXPANDED_TERMS=10)
        excessive_terms = ", ".join([f"term{i}" for i in range(15)])
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {"response": excessive_terms}
            
            result = await generate_expanded_query(user_message, max_terms=10)
            
            # Should be truncated to 10 terms
            result_terms = [t.strip() for t in result.split(",")]
            assert len(result_terms) == 10
    
    @pytest.mark.asyncio
    async def test_expansion_with_custom_max_terms(self):
        """Test expansion with custom max_terms parameter."""
        user_message = "Custom test"
        terms = ", ".join([f"word{i}" for i in range(20)])
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {"response": terms}
            
            result = await generate_expanded_query(user_message, max_terms=5)
            
            result_terms = [t.strip() for t in result.split(",")]
            assert len(result_terms) == 5
    
    @pytest.mark.asyncio
    async def test_empty_response_returns_original_message(self):
        """Test that empty LLM response returns original message."""
        user_message = "Original query"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {"response": ""}
            
            result = await generate_expanded_query(user_message)
            
            assert result == user_message
    
    @pytest.mark.asyncio
    async def test_whitespace_only_response_returns_original(self):
        """Test that whitespace-only response returns original message."""
        user_message = "Query with spaces"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {"response": "   \n  \t  "}
            
            result = await generate_expanded_query(user_message)
            
            assert result == user_message
    
    @pytest.mark.asyncio
    async def test_ollama_error_returns_original_message(self):
        """Test fallback to original message when Ollama fails."""
        user_message = "Error test query"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.side_effect = Exception("Ollama connection failed")
            
            result = await generate_expanded_query(user_message)
            
            # Should fallback to original message
            assert result == user_message
    
    @pytest.mark.asyncio
    async def test_timeout_error_returns_original(self):
        """Test fallback when Ollama times out."""
        user_message = "Timeout test"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.side_effect = TimeoutError("Request timed out")
            
            result = await generate_expanded_query(user_message)
            
            assert result == user_message
    
    @pytest.mark.asyncio
    async def test_malformed_response_handling(self):
        """Test handling of malformed Ollama response."""
        user_message = "Malformed test"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            # Missing 'response' key
            mock_ollama.return_value = {"error": "malformed"}
            
            result = await generate_expanded_query(user_message)
            
            # Should handle missing key and return original
            assert result == user_message
    
    @pytest.mark.asyncio
    async def test_expansion_cleans_extra_whitespace(self):
        """Test that expansion cleans extra whitespace."""
        user_message = "Whitespace test"
        messy_response = "term1,  term2,   term3  ,term4,    term5"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {"response": messy_response}
            
            result = await generate_expanded_query(user_message)
            
            # Should clean whitespace
            assert "  " not in result
            assert result.strip() == result
    
    @pytest.mark.asyncio
    async def test_portuguese_input_expansion(self):
        """Test expansion with Portuguese input."""
        user_message = "Como funciona o sistema de autenticação?"
        expected_terms = (
            "autenticação, authentication, sistema, system, funcionar, work, "
            "login, segurança, security, OAuth"
        )
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {"response": expected_terms}
            
            result = await generate_expanded_query(user_message)
            
            assert result == expected_terms
            # Verify prompt contains the user message
            assert user_message in mock_ollama.call_args.kwargs['prompt']
    
    @pytest.mark.asyncio
    async def test_english_input_expansion(self):
        """Test expansion with English input."""
        user_message = "How does the RAG system work?"
        expected_terms = (
            "RAG, retrieval, vector, embedding, search, "
            "context, documento, relevante, ChromaDB"
        )
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {"response": expected_terms}
            
            result = await generate_expanded_query(user_message)
            
            assert result == expected_terms
    
    @pytest.mark.asyncio
    async def test_technical_terms_expansion(self):
        """Test expansion with technical programming terms."""
        user_message = "Explain FastAPI endpoints"
        expected_terms = (
            "FastAPI, endpoint, API, REST, router, "
            "route, path, HTTP, request, response"
        )
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {"response": expected_terms}
            
            result = await generate_expanded_query(user_message)
            
            assert "FastAPI" in result
            assert "endpoint" in result
    
    @pytest.mark.asyncio
    async def test_very_short_query(self):
        """Test expansion with very short query."""
        user_message = "RAG"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {
                "response": "RAG, retrieval, augmented, generation, LLM"
            }
            
            result = await generate_expanded_query(user_message)
            
            assert len(result) > len(user_message)
    
    @pytest.mark.asyncio
    async def test_very_long_query(self):
        """Test expansion with very long query."""
        user_message = (
            "Can you explain in detail how the RAG system integrates with "
            "the LLM providers and how the vector embeddings are generated "
            "and stored in ChromaDB for efficient retrieval?"
        )
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {
                "response": "RAG, LLM, embedding, vector, ChromaDB, retrieval"
            }
            
            result = await generate_expanded_query(user_message)
            
            # Expanded query should be more concise than original
            assert len(result) < len(user_message)
    
    @pytest.mark.asyncio
    async def test_single_term_result(self):
        """Test handling of single term expansion."""
        user_message = "Database"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {"response": "MongoDB"}
            
            result = await generate_expanded_query(user_message)
            
            assert result == "MongoDB"
    
    @pytest.mark.asyncio
    async def test_prompt_template_used(self):
        """Test that the prompt template is correctly used."""
        user_message = "Test message"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {"response": "test, message"}
            
            await generate_expanded_query(user_message)
            
            # Verify template components are in the prompt
            prompt_used = mock_ollama.call_args.kwargs['prompt']
            assert "bilingual" in prompt_used.lower()
            assert user_message in prompt_used


class TestGenerateExpandedQueryWithContext:
    """Tests for generate_expanded_query_with_context function."""
    
    @pytest.mark.asyncio
    async def test_context_aware_expansion_calls_basic(self):
        """Test that context-aware expansion currently delegates to basic."""
        user_message = "Context test"
        conversation_history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"}
        ]
        
        with patch('app.services.query_expander_service.generate_expanded_query', new_callable=AsyncMock) as mock_basic:
            mock_basic.return_value = "expanded, terms"
            
            result = await generate_expanded_query_with_context(
                user_message,
                conversation_history=conversation_history
            )
            
            # Should call basic expansion
            mock_basic.assert_called_once_with(user_message, model=DEFAULT_EXPANSION_MODEL)
            assert result == "expanded, terms"
    
    @pytest.mark.asyncio
    async def test_context_aware_with_custom_model(self):
        """Test context-aware expansion with custom model."""
        user_message = "Test"
        custom_model = "custom:latest"
        
        with patch('app.services.query_expander_service.generate_expanded_query', new_callable=AsyncMock) as mock_basic:
            mock_basic.return_value = "result"
            
            await generate_expanded_query_with_context(user_message, model=custom_model)
            
            mock_basic.assert_called_once_with(user_message, model=custom_model)
    
    @pytest.mark.asyncio
    async def test_context_aware_without_history(self):
        """Test context-aware expansion without conversation history."""
        user_message = "No context test"
        
        with patch('app.services.query_expander_service.generate_expanded_query', new_callable=AsyncMock) as mock_basic:
            mock_basic.return_value = "expanded"
            
            result = await generate_expanded_query_with_context(user_message)
            
            mock_basic.assert_called_once()
            assert result == "expanded"
    
    @pytest.mark.asyncio
    async def test_context_aware_with_empty_history(self):
        """Test context-aware expansion with empty history."""
        user_message = "Empty history test"
        
        with patch('app.services.query_expander_service.generate_expanded_query', new_callable=AsyncMock) as mock_basic:
            mock_basic.return_value = "expanded"
            
            result = await generate_expanded_query_with_context(
                user_message,
                conversation_history=[]
            )
            
            assert result == "expanded"


class TestQueryExpansionConstants:
    """Tests for module constants and configuration."""
    
    def test_default_expansion_model(self):
        """Test default expansion model is phi3."""
        assert DEFAULT_EXPANSION_MODEL == "phi3:latest"
    
    def test_max_expanded_terms(self):
        """Test max expanded terms constant."""
        assert MAX_EXPANDED_TERMS == 10
        assert isinstance(MAX_EXPANDED_TERMS, int)
        assert MAX_EXPANDED_TERMS > 0
    
    def test_prompt_template_structure(self):
        """Test prompt template has required placeholders."""
        assert "{user_message}" in QUERY_EXPANSION_PROMPT_TEMPLATE
        assert "bilingual" in QUERY_EXPANSION_PROMPT_TEMPLATE.lower()
        assert "Portuguese" in QUERY_EXPANSION_PROMPT_TEMPLATE
        assert "English" in QUERY_EXPANSION_PROMPT_TEMPLATE
    
    def test_prompt_template_format(self):
        """Test prompt template can be formatted."""
        user_msg = "Test message"
        formatted = QUERY_EXPANSION_PROMPT_TEMPLATE.format(user_message=user_msg)
        
        assert user_msg in formatted
        assert "{user_message}" not in formatted
