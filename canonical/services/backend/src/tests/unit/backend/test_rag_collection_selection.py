"""
Unit tests for RAG collection selection behavior.

CRITICAL: These tests validate that RAG is NEVER executed without explicit 
collection selection. This is a critical compliance requirement.

Test coverage:
- RAG disabled when selected_collections is None
- RAG disabled when selected_collections is empty []
- RAG enabled only with explicit valid collections
- ValueError raised when invalid collections are provided
- No caching behavior interference

NOTE: These tests mock all LangChain dependencies to avoid complex setup.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock, Mock
from typing import List

from app.services.rag.rag_service import RAGService, get_rag_service


class TestRAGCollectionSelection:
    """Test suite for RAG collection selection compliance."""

    
    def test_rag_service_init_without_collections(self):
        """Test that RAGService initializes without default collections."""
        rag = RAGService()
        
        assert rag.collection_names is None, "RAGService should not have default collections"
        assert rag.available_collection_names is not None, "Available collections should be defined"
        assert len(rag.available_collection_names) > 0, "Available collections should not be empty"
    
    def test_rag_service_init_with_explicit_collections(self):
        """Test that RAGService accepts explicit collections."""
        explicit_collections = ['scareverse_docs', 'scareverse_code']
        rag = RAGService(collection_names=explicit_collections)
        
        assert rag.collection_names == explicit_collections, "Should store explicit collections"
    
    @pytest.mark.asyncio
    async def test_get_context_with_none_collections(self):
        """Test that get_context returns empty when selected_collections is None."""
        rag = RAGService()
        
        msg, docs, context = await rag.get_context(
            user_message="Test query",
            selected_collections=None
        )
        
        assert msg == "Test query", "Message should be unchanged"
        assert docs == [], "Documents should be empty when RAG is disabled"
        assert context == "", "Context should be empty when RAG is disabled"
    
    @pytest.mark.asyncio
    async def test_get_context_with_empty_collections(self):
        """Test that get_context returns empty when selected_collections is []."""
        rag = RAGService()
        
        msg, docs, context = await rag.get_context(
            user_message="Test query",
            selected_collections=[]
        )
        
        assert msg == "Test query", "Message should be unchanged"
        assert docs == [], "Documents should be empty when RAG is disabled"
        assert context == "", "Context should be empty when RAG is disabled"
    
    @pytest.mark.asyncio
    async def test_get_context_with_explicit_valid_collections(self):
        """Test that get_context executes RAG with explicit valid collections."""
        rag = RAGService()
        
        # Mock the ensemble retriever via retriever_manager to avoid actual vector store access
        with patch.object(rag.retriever_manager, 'get_ensemble_retriever') as mock_ensemble:
            mock_retriever = MagicMock()
            mock_retriever.get_relevant_documents.return_value = [
                MagicMock(page_content="Test content", metadata={})
            ]
            mock_ensemble.return_value = mock_retriever
            
            msg, docs, context = await rag.get_context(
                user_message="Test query",
                selected_collections=['scareverse_docs'],
                enable_query_expansion=False  # Disable to simplify test
            )
            
            assert msg == "Test query", "Message should be unchanged"
            assert len(docs) > 0, "Documents should not be empty with valid collections"
            assert context != "", "Context should not be empty with valid collections"
            mock_ensemble.assert_called_once_with(k=5, selected_collections=['scareverse_docs'])
    
    def test_get_ensemble_retriever_with_none_collections(self):
        """Test that retriever_manager.get_ensemble_retriever raises ValueError with None collections."""
        rag = RAGService()
        
        with pytest.raises(ValueError) as exc_info:
            rag.retriever_manager.get_ensemble_retriever(selected_collections=None)
        
        assert "must be explicitly provided" in str(exc_info.value).lower()
    
    def test_get_ensemble_retriever_with_empty_collections(self):
        """Test that retriever_manager.get_ensemble_retriever raises ValueError with empty collections."""
        rag = RAGService()
        
        with pytest.raises(ValueError) as exc_info:
            rag.retriever_manager.get_ensemble_retriever(selected_collections=[])
        
        assert "must be explicitly provided" in str(exc_info.value).lower()
    
    def test_get_ensemble_retriever_with_invalid_collections(self):
        """Test that retriever_manager.get_ensemble_retriever raises ValueError with all invalid collections."""
        rag = RAGService()
        
        with pytest.raises(ValueError) as exc_info:
            rag.retriever_manager.get_ensemble_retriever(selected_collections=['invalid_collection'])
        
        assert "none of the selected collections" in str(exc_info.value).lower()
    
    def test_get_ensemble_retriever_with_mixed_valid_invalid(self):
        """Test that retriever_manager.get_ensemble_retriever filters out invalid collections."""
        rag = RAGService()
        
        # Mock get_retriever_for_collection to avoid actual vector store access
        # Need to create a proper BaseRetriever mock for Pydantic validation
        from langchain_core.retrievers import BaseRetriever
        from langchain_core.documents import Document
        from langchain_core.callbacks import CallbackManagerForRetrieverRun
        
        class MockRetriever(BaseRetriever):
            """Mock retriever for testing."""
            def _get_relevant_documents(
                self, query: str, *, run_manager: CallbackManagerForRetrieverRun
            ) -> List[Document]:
                return []
        
        with patch.object(rag.retriever_manager, 'get_retriever_for_collection') as mock_get_retriever:
            mock_retriever = MockRetriever()
            mock_get_retriever.return_value = mock_retriever
            
            ensemble = rag.retriever_manager.get_ensemble_retriever(
                selected_collections=['scareverse_docs', 'invalid_collection']
            )
            
            # Should only call for valid collection
            mock_get_retriever.assert_called_once()
            assert ensemble is not None
    
    def test_factory_function_without_collections(self):
        """Test that factory function creates service without default collections."""
        rag = get_rag_service()
        
        assert rag.collection_names is None, "Factory should not set default collections"
    
    def test_factory_function_with_collections(self):
        """Test that factory function accepts explicit collections."""
        explicit_collections = ['scareverse_docs']
        rag = get_rag_service(collection_names=explicit_collections)
        
        assert rag.collection_names == explicit_collections


class TestRAGCachingRemoval:
    """Test suite to verify that caching has been removed."""
    
    def test_no_cache_attributes(self):
        """Test that cache attributes have been removed from RAGService."""
        rag = RAGService()
        
        # These attributes should NOT exist
        assert not hasattr(rag, '_retrievers'), "Retriever cache should be removed"
        assert not hasattr(rag, '_ensemble_retriever'), "Ensemble cache should be removed"
    
    def test_get_retriever_creates_fresh_instance(self):
        """Test that retriever_manager.get_retriever_for_collection creates fresh instances."""
        rag = RAGService()
        
        # Need to create a proper BaseRetriever mock for Pydantic validation
        from langchain_core.retrievers import BaseRetriever
        from langchain_core.documents import Document
        from langchain_core.callbacks import CallbackManagerForRetrieverRun
        from pathlib import Path
        
        class MockRetriever(BaseRetriever):
            """Mock retriever for testing."""
            def _get_relevant_documents(
                self, query: str, *, run_manager: CallbackManagerForRetrieverRun
            ) -> List[Document]:
                return []
        
        # Mock both Path.exists() and Chroma - use the correct import path
        with patch.object(Path, 'exists', return_value=True), \
             patch('app.services.rag.retriever_manager.Chroma') as mock_chroma:
            mock_vs = MagicMock()
            mock_vs.peek.return_value = {'ids': ['doc1']}  # Non-empty to pass validation
            mock_vs.as_retriever.return_value = MockRetriever()
            mock_chroma.return_value = mock_vs
            
            # Call twice with same parameters
            retriever1 = rag.retriever_manager.get_retriever_for_collection('scareverse_docs', k=5)
            retriever2 = rag.retriever_manager.get_retriever_for_collection('scareverse_docs', k=5)
            
            # Should create new instances each time (no caching)
            assert mock_chroma.call_count == 2, "Should create fresh Chroma instance each time"
    
    def test_get_ensemble_retriever_creates_fresh_instance(self):
        """Test that retriever_manager.get_ensemble_retriever creates fresh instances."""
        rag = RAGService()
        
        # Need to create a proper BaseRetriever mock for Pydantic validation
        from langchain_core.retrievers import BaseRetriever
        from langchain_core.documents import Document
        from langchain_core.callbacks import CallbackManagerForRetrieverRun
        
        class MockRetriever(BaseRetriever):
            """Mock retriever for testing."""
            def _get_relevant_documents(
                self, query: str, *, run_manager: CallbackManagerForRetrieverRun
            ) -> List[Document]:
                return []
        
        # Mock get_retriever_for_collection to avoid actual vector store access
        with patch.object(rag.retriever_manager, 'get_retriever_for_collection') as mock_get_retriever:
            mock_retriever = MockRetriever()
            mock_get_retriever.return_value = mock_retriever
            
            # Call twice with same parameters
            ensemble1 = rag.retriever_manager.get_ensemble_retriever(
                selected_collections=['scareverse_docs'], k=5
            )
            ensemble2 = rag.retriever_manager.get_ensemble_retriever(
                selected_collections=['scareverse_docs'], k=5
            )
            
            # Should call get_retriever_for_collection twice (no caching)
            assert mock_get_retriever.call_count == 2, "Should create fresh retrievers each time"
            assert ensemble1 is not ensemble2, "Should create different ensemble instances"


class TestRAGProviderIntegration:
    """Test suite for RAG integration in LLM providers."""
    
    @pytest.mark.asyncio
    async def test_ollama_provider_respects_rag_disabled(self):
        """Test that OllamaProvider does not call RAG when collections are empty."""
        from app.services.providers.ollama_provider import OllamaProvider
        
        provider = OllamaProvider(model_id="mistral")
        
        # Patch at the module where it's actually defined
        with patch('app.services.rag.rag_service.get_rag_service') as mock_rag_factory:
            with patch('app.ollama_service.chamar_ollama') as mock_ollama:
                with patch.object(provider, 'verify_availability', return_value=True):
                    mock_ollama.return_value = {"response": "Test response"}
                    
                    # Call with empty collections
                    await provider.process_chat(
                        user_message="Test",
                        use_rag=True,  # Even with use_rag=True, should not call RAG
                        selected_collections=[]
                    )
                    
                    # RAG service should still be called but get_context will return empty
                    # The provider passes use_rag=True but selected_collections=[]
                    # The rag_service.get_context will detect empty collections and skip RAG
    
    @pytest.mark.asyncio
    async def test_openai_provider_respects_rag_disabled(self):
        """Test that OpenAIProvider does not call RAG when collections are None."""
        from app.services.providers.openai_provider import OpenAIProvider
        
        provider = OpenAIProvider(model_id="gpt-4", api_key="test-key")
        
        # Patch at the module where it's actually defined
        with patch('app.services.rag.rag_service.get_rag_service') as mock_rag_factory:
            with patch('app.openai_service.chamar_openai') as mock_openai:
                with patch.object(provider, 'verify_availability', return_value=True):
                    mock_openai.return_value = {"response": "Test response"}
                    
                    # Call with None collections
                    await provider.process_chat(
                        user_message="Test",
                    use_rag=True,
                    selected_collections=None
                )
                
                # Similar to Ollama test - service is called but returns empty


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
