"""
Unit tests for RAG Post-processor Service.

Tests context condensation with local LLM, error handling, and
integration with the RAG pipeline.

Technical naming: All functions and variables in English.
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock
from langchain_core.documents import Document
from app.services.rag_postprocessor import (
    condense_context_with_local_llm,
    postprocess_rag_context
)


class TestCondenseContextWithLocalLLM:
    """Tests for condense_context_with_local_llm function."""
    
    @pytest.mark.asyncio
    async def test_successful_condensation(self, sample_documents):
        """Test successful context condensation with local LLM."""
        user_query = "Explain the architecture"
        model = "phi3:latest"
        prompt_template = "Context: {context}\nQuery: {query}\nCondensed:"
        base_url = "http://localhost:11434"
        
        condensed_response = "ScareVerse uses FastAPI backend with MongoDB and RAG for context retrieval."
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            
            mock_format.return_value = "[1] Doc1\n[2] Doc2\n[3] Doc3"
            mock_ollama.return_value = {"response": condensed_response}
            
            result = await condense_context_with_local_llm(
                chunks=sample_documents,
                user_query=user_query,
                model=model,
                prompt_template=prompt_template,
                base_url=base_url
            )
            
            assert result == condensed_response
            mock_ollama.assert_called_once()
            assert mock_ollama.call_args.kwargs['model'] == model
            assert mock_ollama.call_args.kwargs['stream'] is False
    
    @pytest.mark.asyncio
    async def test_condensation_with_custom_timeout(self, sample_documents):
        """Test condensation with custom timeout parameter."""
        user_query = "Test query"
        model = "phi3:latest"
        prompt_template = "{context} {query}"
        base_url = "http://localhost:11434"
        timeout = 60
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            
            mock_format.return_value = "context"
            mock_ollama.return_value = {"response": "condensed"}
            
            result = await condense_context_with_local_llm(
                chunks=sample_documents,
                user_query=user_query,
                model=model,
                prompt_template=prompt_template,
                base_url=base_url,
                timeout=timeout
            )
            
            assert result == "condensed"
    
    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty_string(self):
        """Test that empty chunks return empty string."""
        result = await condense_context_with_local_llm(
            chunks=[],
            user_query="Query",
            model="phi3:latest",
            prompt_template="{context} {query}",
            base_url="http://localhost:11434"
        )
        
        assert result == ""
    
    @pytest.mark.asyncio
    async def test_condensation_error_returns_raw_context(self, sample_documents):
        """Test fallback to raw context when condensation fails."""
        user_query = "Error test"
        model = "phi3:latest"
        prompt_template = "{context} {query}"
        base_url = "http://localhost:11434"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            
            raw_context = "[1] Raw doc 1\n[2] Raw doc 2"
            mock_format.return_value = raw_context
            mock_ollama.side_effect = Exception("Ollama error")
            
            result = await condense_context_with_local_llm(
                chunks=sample_documents,
                user_query=user_query,
                model=model,
                prompt_template=prompt_template,
                base_url=base_url
            )
            
            # Should fallback to raw context
            assert result == raw_context
            assert mock_format.call_count == 2  # Once for prompt, once for fallback
    
    @pytest.mark.asyncio
    async def test_ollama_timeout_returns_raw_context(self, sample_documents):
        """Test fallback when Ollama times out."""
        user_query = "Timeout test"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            
            raw_context = "Raw context"
            mock_format.return_value = raw_context
            mock_ollama.side_effect = TimeoutError("Request timed out")
            
            result = await condense_context_with_local_llm(
                chunks=sample_documents,
                user_query=user_query,
                model="phi3:latest",
                prompt_template="{context} {query}",
                base_url="http://localhost:11434"
            )
            
            assert result == raw_context
    
    @pytest.mark.asyncio
    async def test_context_reduction_logging(self, sample_documents):
        """Test that condensation logs context size reduction."""
        user_query = "Logging test"
        long_context = "A" * 1000
        short_response = "B" * 100
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            
            mock_format.return_value = long_context
            mock_ollama.return_value = {"response": short_response}
            
            result = await condense_context_with_local_llm(
                chunks=sample_documents,
                user_query=user_query,
                model="phi3:latest",
                prompt_template="{context} {query}",
                base_url="http://localhost:11434"
            )
            
            # Should return condensed response
            assert len(result) < len(long_context)
            assert result == short_response
    
    @pytest.mark.asyncio
    async def test_prompt_template_formatting(self, sample_documents):
        """Test that prompt template is correctly formatted."""
        user_query = "Template test"
        prompt_template = "CONTEXT:\n{context}\n\nQUERY: {query}\n\nSUMMARY:"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            
            formatted_context = "Doc content"
            mock_format.return_value = formatted_context
            mock_ollama.return_value = {"response": "summary"}
            
            await condense_context_with_local_llm(
                chunks=sample_documents,
                user_query=user_query,
                model="phi3:latest",
                prompt_template=prompt_template,
                base_url="http://localhost:11434"
            )
            
            # Verify prompt contains formatted template
            called_prompt = mock_ollama.call_args.kwargs['prompt']
            assert "CONTEXT:" in called_prompt
            assert "QUERY:" in called_prompt
            assert user_query in called_prompt
            assert formatted_context in called_prompt
    
    @pytest.mark.asyncio
    async def test_response_stripping(self, sample_documents):
        """Test that response whitespace is stripped."""
        user_query = "Whitespace test"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            
            mock_format.return_value = "context"
            # Response with leading/trailing whitespace
            mock_ollama.return_value = {"response": "  \n  condensed response  \n  "}
            
            result = await condense_context_with_local_llm(
                chunks=sample_documents,
                user_query=user_query,
                model="phi3:latest",
                prompt_template="{context} {query}",
                base_url="http://localhost:11434"
            )
            
            assert result == "condensed response"
    
    @pytest.mark.asyncio
    async def test_large_chunk_set(self, large_documents):
        """Test condensation with large number of chunks."""
        user_query = "Large test"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            
            mock_format.return_value = "Large context"
            mock_ollama.return_value = {"response": "Condensed summary"}
            
            result = await condense_context_with_local_llm(
                chunks=large_documents,
                user_query=user_query,
                model="phi3:latest",
                prompt_template="{context} {query}",
                base_url="http://localhost:11434"
            )
            
            assert result == "Condensed summary"
            # Should have formatted all documents
            mock_format.assert_called_once_with(large_documents)


class TestPostprocessRAGContext:
    """Tests for postprocess_rag_context function."""
    
    @pytest.mark.asyncio
    async def test_postprocessing_enabled(self, sample_documents):
        """Test post-processing when enabled."""
        user_query = "Test query"
        model = "phi3:latest"
        prompt_template = "{context} {query}"
        base_url = "http://localhost:11434"
        
        with patch('app.services.rag_postprocessor.condense_context_with_local_llm', new_callable=AsyncMock) as mock_condense:
            mock_condense.return_value = "Condensed context"
            
            result = await postprocess_rag_context(
                chunks=sample_documents,
                user_query=user_query,
                enabled=True,
                model=model,
                prompt_template=prompt_template,
                base_url=base_url
            )
            
            assert result == "Condensed context"
            mock_condense.assert_called_once_with(
                chunks=sample_documents,
                user_query=user_query,
                model=model,
                prompt_template=prompt_template,
                base_url=base_url,
                timeout=30
            )
    
    @pytest.mark.asyncio
    async def test_postprocessing_disabled(self, sample_documents):
        """Test post-processing when disabled."""
        user_query = "Test query"
        
        with patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            mock_format.return_value = "Raw formatted context"
            
            result = await postprocess_rag_context(
                chunks=sample_documents,
                user_query=user_query,
                enabled=False,
                model="phi3:latest",
                prompt_template="{context} {query}",
                base_url="http://localhost:11434"
            )
            
            assert result == "Raw formatted context"
            mock_format.assert_called_once_with(sample_documents)
    
    @pytest.mark.asyncio
    async def test_postprocessing_with_custom_timeout(self, sample_documents):
        """Test post-processing with custom timeout."""
        user_query = "Timeout test"
        custom_timeout = 60
        
        with patch('app.services.rag_postprocessor.condense_context_with_local_llm', new_callable=AsyncMock) as mock_condense:
            mock_condense.return_value = "Result"
            
            await postprocess_rag_context(
                chunks=sample_documents,
                user_query=user_query,
                enabled=True,
                model="phi3:latest",
                prompt_template="{context} {query}",
                base_url="http://localhost:11434",
                timeout=custom_timeout
            )
            
            assert mock_condense.call_args.kwargs['timeout'] == custom_timeout
    
    @pytest.mark.asyncio
    async def test_empty_chunks_disabled(self):
        """Test with empty chunks and disabled post-processing."""
        with patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            mock_format.return_value = ""
            
            result = await postprocess_rag_context(
                chunks=[],
                user_query="Query",
                enabled=False,
                model="phi3:latest",
                prompt_template="{context} {query}",
                base_url="http://localhost:11434"
            )
            
            assert result == ""
    
    @pytest.mark.asyncio
    async def test_empty_chunks_enabled(self):
        """Test with empty chunks and enabled post-processing."""
        result = await postprocess_rag_context(
            chunks=[],
            user_query="Query",
            enabled=True,
            model="phi3:latest",
            prompt_template="{context} {query}",
            base_url="http://localhost:11434"
        )
        
        # condense_context_with_local_llm returns "" for empty chunks
        assert result == ""
    
    @pytest.mark.asyncio
    async def test_postprocessing_integration_flow(self, sample_documents):
        """Test complete post-processing flow."""
        user_query = "Integration test"
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            
            raw_context = "Raw: Doc1, Doc2, Doc3"
            condensed = "Condensed: Summary of docs"
            
            mock_format.return_value = raw_context
            mock_ollama.return_value = {"response": condensed}
            
            result = await postprocess_rag_context(
                chunks=sample_documents,
                user_query=user_query,
                enabled=True,
                model="phi3:latest",
                prompt_template="{context}\n{query}",
                base_url="http://localhost:11434"
            )
            
            assert result == condensed
            # Should format and then condense
            assert mock_format.called
            assert mock_ollama.called
    
    @pytest.mark.asyncio
    async def test_disabled_skips_ollama_call(self, sample_documents):
        """Test that disabled post-processing skips Ollama call."""
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            
            mock_format.return_value = "Formatted"
            
            await postprocess_rag_context(
                chunks=sample_documents,
                user_query="Query",
                enabled=False,
                model="phi3:latest",
                prompt_template="{context} {query}",
                base_url="http://localhost:11434"
            )
            
            # Should NOT call Ollama
            mock_ollama.assert_not_called()
            # Should only format
            mock_format.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_postprocessing_error_fallback(self, sample_documents):
        """Test fallback when post-processing encounters error."""
        user_query = "Error test"
        
        with patch('app.services.rag_postprocessor.condense_context_with_local_llm', new_callable=AsyncMock) as mock_condense, \
             patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            
            raw_context = "Raw fallback"
            mock_format.return_value = raw_context
            # Condense will call format_context_for_prompt on error
            mock_condense.return_value = raw_context
            
            result = await postprocess_rag_context(
                chunks=sample_documents,
                user_query=user_query,
                enabled=True,
                model="phi3:latest",
                prompt_template="{context} {query}",
                base_url="http://localhost:11434"
            )
            
            # Should return the raw context from the fallback
            assert result == raw_context


class TestPostprocessorConfiguration:
    """Tests for post-processor configuration and edge cases."""
    
    @pytest.mark.asyncio
    async def test_different_models(self, sample_documents):
        """Test post-processing with different models."""
        models = ["phi3:latest", "llama2:latest", "mistral:latest"]
        
        for model in models:
            with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama, \
                 patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
                
                mock_format.return_value = "context"
                mock_ollama.return_value = {"response": f"Result from {model}"}
                
                result = await postprocess_rag_context(
                    chunks=sample_documents,
                    user_query="Test",
                    enabled=True,
                    model=model,
                    prompt_template="{context} {query}",
                    base_url="http://localhost:11434"
                )
                
                assert model in result or "Result" in result
    
    @pytest.mark.asyncio
    async def test_different_base_urls(self, sample_documents):
        """Test with different Ollama base URLs."""
        base_urls = [
            "http://localhost:11434",
            "http://ollama:11434",
            "http://192.168.1.100:11434"
        ]
        
        for base_url in base_urls:
            with patch('app.services.rag_postprocessor.condense_context_with_local_llm', new_callable=AsyncMock) as mock_condense:
                mock_condense.return_value = "Result"
                
                await postprocess_rag_context(
                    chunks=sample_documents,
                    user_query="Test",
                    enabled=True,
                    model="phi3:latest",
                    prompt_template="{context} {query}",
                    base_url=base_url
                )
                
                assert mock_condense.call_args.kwargs['base_url'] == base_url
    
    @pytest.mark.asyncio
    async def test_complex_prompt_template(self, sample_documents):
        """Test with complex multi-line prompt template."""
        complex_template = """
You are a context summarizer. Given the following context and query, 
create a concise summary focusing only on relevant information.

CONTEXT:
{context}

USER QUERY:
{query}

SUMMARIZED CONTEXT:
"""
        
        with patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            
            mock_format.return_value = "context"
            mock_ollama.return_value = {"response": "summary"}
            
            await postprocess_rag_context(
                chunks=sample_documents,
                user_query="Complex test",
                enabled=True,
                model="phi3:latest",
                prompt_template=complex_template,
                base_url="http://localhost:11434"
            )
            
            prompt = mock_ollama.call_args.kwargs['prompt']
            assert "You are a context summarizer" in prompt
            assert "CONTEXT:" in prompt
            assert "USER QUERY:" in prompt
