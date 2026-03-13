"""
Unit tests for RAG Service.

Tests the main RAG service including ensemble retrieval, query expansion,
post-processing integration, and collection filtering.

Technical naming: All functions and variables in English.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from langchain_core.documents import Document
from app.services.rag.rag_service import RAGService
from app.services.rag.config import DEFAULT_RAG_K, AVAILABLE_COLLECTION_NAMES


class TestRAGServiceInitialization:
    """Tests for RAGService initialization."""
    
    def test_init_with_collections(self):
        """Test initialization with specific collections."""
        collections = ["scareverse_docs", "scareverse_code"]
        
        with patch('app.services.rag.rag_service.RetrieverManager'):
            rag = RAGService(collection_names=collections)
            
            assert rag.collection_names == collections
            assert rag.available_collection_names == AVAILABLE_COLLECTION_NAMES
    
    def test_init_without_collections(self):
        """Test initialization without collections (RAG disabled by default)."""
        with patch('app.services.rag.rag_service.RetrieverManager'):
            rag = RAGService()
            
            assert rag.collection_names is None
            assert rag.ensemble_weights is None
    
    def test_init_with_custom_vectorstore_path(self):
        """Test initialization with custom vectorstore path."""
        custom_path = "/custom/path/chroma_db"
        
        with patch('app.services.rag.rag_service.RetrieverManager'):
            rag = RAGService(vectorstore_path=custom_path)
            
            assert rag.vectorstore_path == custom_path
    
    def test_init_with_equal_weights(self):
        """Test that equal weights are assigned when not specified."""
        collections = ["col1", "col2", "col3"]
        
        with patch('app.services.rag.rag_service.RetrieverManager'):
            rag = RAGService(collection_names=collections)
            
            assert len(rag.ensemble_weights) == 3
            assert all(w == pytest.approx(1.0/3.0) for w in rag.ensemble_weights)
    
    def test_init_with_custom_weights(self):
        """Test initialization with custom ensemble weights."""
        collections = ["col1", "col2"]
        weights = [0.7, 0.3]
        
        with patch('app.services.rag.rag_service.RetrieverManager'):
            rag = RAGService(collection_names=collections, ensemble_weights=weights)
            
            assert rag.ensemble_weights == weights
    
    def test_init_with_api_key(self):
        """Test initialization with API key for OpenAI embeddings."""
        api_key = "sk-test-key"
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm:
            rag = RAGService(api_key=api_key)
            
            assert rag.api_key == api_key
            # Verify RetrieverManager was initialized with api_key
            mock_rm.assert_called_once()
            assert mock_rm.call_args.kwargs['api_key'] == api_key


class TestGetContext:
    """Tests for get_context method."""
    
    @pytest.mark.asyncio
    async def test_rag_disabled_when_no_collections(self, sample_documents):
        """Test RAG returns empty context when no collections selected."""
        with patch('app.services.rag.rag_service.RetrieverManager'):
            rag = RAGService()
            
            msg, docs, context = await rag.get_context(
                user_message="Test query",
                selected_collections=None
            )
            
            assert msg == "Test query"
            assert docs == []
            assert context == ""
    
    @pytest.mark.asyncio
    async def test_rag_disabled_when_empty_collections(self):
        """Test RAG returns empty context when empty collection list."""
        with patch('app.services.rag.rag_service.RetrieverManager'):
            rag = RAGService()
            
            msg, docs, context = await rag.get_context(
                user_message="Test query",
                selected_collections=[]
            )
            
            assert msg == "Test query"
            assert docs == []
            assert context == ""
    
    @pytest.mark.asyncio
    async def test_rag_enabled_with_collections(self, sample_documents, mock_ensemble_retriever):
        """Test RAG retrieves context with selected collections."""
        collections = ["scareverse_docs"]
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm, \
             patch('app.services.rag.rag_service.format_context_for_prompt') as mock_format:
            
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.return_value = mock_ensemble_retriever
            mock_rm.return_value = mock_manager
            mock_format.return_value = "Formatted context"
            
            rag = RAGService()
            
            msg, docs, context = await rag.get_context(
                user_message="Test query",
                selected_collections=collections,
                enable_query_expansion=False,
                enable_postprocessing=False
            )
            
            assert msg == "Test query"
            assert len(docs) == len(sample_documents)
            assert context == "Formatted context"
            mock_ensemble_retriever.get_relevant_documents.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_query_expansion_enabled(self, sample_documents, mock_ensemble_retriever):
        """Test query expansion when enabled."""
        collections = ["scareverse_docs"]
        expanded_query = "expanded, terms, bilingual"
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm, \
             patch('app.services.rag.rag_service.format_context_for_prompt') as mock_format, \
             patch('app.services.query_expander_service.generate_expanded_query', new_callable=AsyncMock) as mock_expand:
            
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.return_value = mock_ensemble_retriever
            mock_rm.return_value = mock_manager
            mock_format.return_value = "Context"
            mock_expand.return_value = expanded_query
            
            rag = RAGService()
            
            await rag.get_context(
                user_message="Original query",
                selected_collections=collections,
                enable_query_expansion=True,
                enable_postprocessing=False
            )
            
            # Should call expansion
            mock_expand.assert_called_once_with("Original query")
            # Should use expanded query for retrieval
            mock_ensemble_retriever.get_relevant_documents.assert_called_once_with(expanded_query)
    
    @pytest.mark.asyncio
    async def test_query_expansion_disabled(self, sample_documents, mock_ensemble_retriever):
        """Test that query expansion is skipped when disabled."""
        collections = ["scareverse_docs"]
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm, \
             patch('app.services.rag.rag_service.format_context_for_prompt') as mock_format, \
             patch('app.services.query_expander_service.generate_expanded_query', new_callable=AsyncMock) as mock_expand:
            
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.return_value = mock_ensemble_retriever
            mock_rm.return_value = mock_manager
            mock_format.return_value = "Context"
            
            rag = RAGService()
            
            await rag.get_context(
                user_message="Original query",
                selected_collections=collections,
                enable_query_expansion=False,
                enable_postprocessing=False
            )
            
            # Should NOT call expansion
            mock_expand.assert_not_called()
            # Should use original query
            mock_ensemble_retriever.get_relevant_documents.assert_called_once_with("Original query")
    
    @pytest.mark.asyncio
    async def test_query_expansion_error_fallback(self, sample_documents, mock_ensemble_retriever):
        """Test fallback to original query when expansion fails."""
        collections = ["scareverse_docs"]
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm, \
             patch('app.services.rag.rag_service.format_context_for_prompt') as mock_format, \
             patch('app.services.query_expander_service.generate_expanded_query', new_callable=AsyncMock) as mock_expand:
            
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.return_value = mock_ensemble_retriever
            mock_rm.return_value = mock_manager
            mock_format.return_value = "Context"
            mock_expand.side_effect = Exception("Expansion failed")
            
            rag = RAGService()
            
            await rag.get_context(
                user_message="Original query",
                selected_collections=collections,
                enable_query_expansion=True,
                enable_postprocessing=False
            )
            
            # Should fallback to original query
            mock_ensemble_retriever.get_relevant_documents.assert_called_once_with("Original query")
    
    @pytest.mark.asyncio
    async def test_postprocessing_enabled(self, sample_documents, mock_ensemble_retriever):
        """Test post-processing when enabled."""
        collections = ["scareverse_docs"]
        condensed_context = "Condensed summary"
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm, \
             patch('app.services.rag_postprocessor.postprocess_rag_context', new_callable=AsyncMock) as mock_postprocess:
            
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.return_value = mock_ensemble_retriever
            mock_rm.return_value = mock_manager
            mock_postprocess.return_value = condensed_context
            
            rag = RAGService()
            
            msg, docs, context = await rag.get_context(
                user_message="Test query",
                selected_collections=collections,
                enable_query_expansion=False,
                enable_postprocessing=True
            )
            
            assert context == condensed_context
            mock_postprocess.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_postprocessing_disabled(self, sample_documents, mock_ensemble_retriever):
        """Test raw context when post-processing disabled."""
        collections = ["scareverse_docs"]
        raw_context = "Raw formatted context"
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm, \
             patch('app.services.rag.rag_service.format_context_for_prompt') as mock_format, \
             patch('app.services.rag_postprocessor.postprocess_rag_context', new_callable=AsyncMock) as mock_postprocess:
            
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.return_value = mock_ensemble_retriever
            mock_rm.return_value = mock_manager
            mock_format.return_value = raw_context
            
            rag = RAGService()
            
            msg, docs, context = await rag.get_context(
                user_message="Test query",
                selected_collections=collections,
                enable_query_expansion=False,
                enable_postprocessing=False
            )
            
            assert context == raw_context
            # Should NOT call post-processor
            mock_postprocess.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_custom_k_parameter(self, sample_documents, mock_ensemble_retriever):
        """Test retrieval with custom k parameter."""
        collections = ["scareverse_docs"]
        custom_k = 10
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm, \
             patch('app.services.rag.rag_service.format_context_for_prompt') as mock_format:
            
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.return_value = mock_ensemble_retriever
            mock_rm.return_value = mock_manager
            mock_format.return_value = "Context"
            
            rag = RAGService()
            
            await rag.get_context(
                user_message="Test",
                selected_collections=collections,
                k=custom_k,
                enable_query_expansion=False,
                enable_postprocessing=False
            )
            
            # Verify k was passed to ensemble retriever
            mock_manager.get_ensemble_retriever.assert_called_once_with(
                k=custom_k,
                selected_collections=collections
            )
    
    @pytest.mark.asyncio
    async def test_error_returns_empty_context(self, mock_ensemble_retriever):
        """Test that errors return empty context instead of failing."""
        collections = ["scareverse_docs"]
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm:
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.side_effect = Exception("Retrieval error")
            mock_rm.return_value = mock_manager
            
            rag = RAGService()
            
            msg, docs, context = await rag.get_context(
                user_message="Test",
                selected_collections=collections,
                enable_query_expansion=False
            )
            
            # Should return empty context on error
            assert msg == "Test"
            assert docs == []
            assert context == ""
    
    @pytest.mark.asyncio
    async def test_multiple_collections(self, sample_documents, mock_ensemble_retriever):
        """Test retrieval across multiple collections."""
        collections = ["scareverse_docs", "scareverse_code", "scareverse_markdown"]
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm, \
             patch('app.services.rag.rag_service.format_context_for_prompt') as mock_format:
            
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.return_value = mock_ensemble_retriever
            mock_rm.return_value = mock_manager
            mock_format.return_value = "Multi-collection context"
            
            rag = RAGService()
            
            msg, docs, context = await rag.get_context(
                user_message="Test",
                selected_collections=collections,
                enable_query_expansion=False,
                enable_postprocessing=False
            )
            
            # Verify all collections were passed
            mock_manager.get_ensemble_retriever.assert_called_once_with(
                k=DEFAULT_RAG_K,
                selected_collections=collections
            )
    
    @pytest.mark.asyncio
    async def test_session_id_logging(self, sample_documents, mock_ensemble_retriever):
        """Test that session_id is used for logging."""
        collections = ["scareverse_docs"]
        session_id = "test_session_123"
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm, \
             patch('app.services.rag.rag_service.format_context_for_prompt') as mock_format:
            
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.return_value = mock_ensemble_retriever
            mock_rm.return_value = mock_manager
            mock_format.return_value = "Context"
            
            rag = RAGService()
            
            # Session ID is for logging/tracking only
            msg, docs, context = await rag.get_context(
                user_message="Test",
                session_id=session_id,
                selected_collections=collections,
                enable_query_expansion=False,
                enable_postprocessing=False
            )
            
            # Should execute successfully
            assert msg == "Test"
            assert len(docs) > 0


class TestSearchSimilar:
    """Tests for search_similar method."""
    
    def test_search_in_specific_collection(self, sample_documents):
        """Test similarity search in specific collection."""
        collection_name = "scareverse_docs"
        query = "test query"
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm:
            mock_manager = Mock()
            mock_retriever = Mock()
            mock_retriever.get_relevant_documents.return_value = sample_documents
            mock_manager.get_retriever_for_collection.return_value = mock_retriever
            mock_rm.return_value = mock_manager
            
            rag = RAGService()
            
            result = rag.search_similar(query, k=5, collection_name=collection_name)
            
            assert len(result) == len(sample_documents)
            mock_manager.get_retriever_for_collection.assert_called_once_with(collection_name, k=5)
            mock_retriever.get_relevant_documents.assert_called_once_with(query)
    
    def test_search_across_all_collections(self, sample_documents, mock_ensemble_retriever):
        """Test similarity search across all collections."""
        query = "test query"
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm:
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.return_value = mock_ensemble_retriever
            mock_rm.return_value = mock_manager
            
            rag = RAGService()
            
            result = rag.search_similar(query, k=5, collection_name=None)
            
            assert len(result) == len(sample_documents)
            mock_ensemble_retriever.get_relevant_documents.assert_called_once_with(query)
    
    def test_search_with_custom_k(self, sample_documents):
        """Test search with custom k parameter."""
        query = "test"
        custom_k = 10
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm:
            mock_manager = Mock()
            mock_retriever = Mock()
            mock_retriever.get_relevant_documents.return_value = sample_documents[:custom_k]
            mock_manager.get_retriever_for_collection.return_value = mock_retriever
            mock_rm.return_value = mock_manager
            
            rag = RAGService()
            
            result = rag.search_similar(query, k=custom_k, collection_name="test_col")
            
            # Result limited by k
            assert len(result) <= custom_k
    
    def test_search_error_returns_empty(self):
        """Test that search errors return empty list."""
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm:
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.side_effect = Exception("Search error")
            mock_rm.return_value = mock_manager
            
            rag = RAGService()
            
            result = rag.search_similar("query", k=5)
            
            # Should return empty on error
            assert result == []


class TestRAGServiceIntegration:
    """Integration tests for complete RAG workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_rag_workflow_with_all_features(self, sample_documents, mock_ensemble_retriever):
        """Test complete RAG workflow with query expansion and post-processing."""
        collections = ["scareverse_docs"]
        original_query = "Como funciona o RAG?"
        expanded_query = "RAG, retrieval, augmented, generation, busca, contexto"
        condensed_context = "RAG retrieves relevant context for LLM prompts."
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm, \
             patch('app.services.query_expander_service.generate_expanded_query', new_callable=AsyncMock) as mock_expand, \
             patch('app.services.rag_postprocessor.postprocess_rag_context', new_callable=AsyncMock) as mock_postprocess:
            
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.return_value = mock_ensemble_retriever
            mock_rm.return_value = mock_manager
            mock_expand.return_value = expanded_query
            mock_postprocess.return_value = condensed_context
            
            rag = RAGService()
            
            msg, docs, context = await rag.get_context(
                user_message=original_query,
                selected_collections=collections,
                enable_query_expansion=True,
                enable_postprocessing=True
            )
            
            # Verify complete flow
            assert msg == original_query
            assert len(docs) > 0
            assert context == condensed_context
            
            # Verify expansion was called
            mock_expand.assert_called_once_with(original_query)
            # Verify retrieval used expanded query
            mock_ensemble_retriever.get_relevant_documents.assert_called_once_with(expanded_query)
            # Verify post-processing was called
            mock_postprocess.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_minimal_rag_workflow(self, sample_documents, mock_ensemble_retriever):
        """Test minimal RAG workflow without expansion or post-processing."""
        collections = ["scareverse_code"]
        query = "Show me the authentication code"
        raw_context = "[1] Auth code here\n[2] More auth code"
        
        with patch('app.services.rag.rag_service.RetrieverManager') as mock_rm, \
             patch('app.services.rag.rag_service.format_context_for_prompt') as mock_format:
            
            mock_manager = Mock()
            mock_manager.get_ensemble_retriever.return_value = mock_ensemble_retriever
            mock_rm.return_value = mock_manager
            mock_format.return_value = raw_context
            
            rag = RAGService()
            
            msg, docs, context = await rag.get_context(
                user_message=query,
                selected_collections=collections,
                enable_query_expansion=False,
                enable_postprocessing=False
            )
            
            assert msg == query
            assert len(docs) > 0
            assert context == raw_context
