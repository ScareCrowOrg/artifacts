"""
Unit tests for configuration module.

Tests environment variable loading, default values,
and configuration constants.
"""

import pytest
import os
from pathlib import Path
from unittest.mock import patch

# Import config module
import app.config as config


class TestDatabaseConfiguration:
    """Tests for database-related configuration."""
    
    def test_mongodb_config_exists(self):
        """Test that MongoDB configuration is accessible."""
        assert hasattr(config, 'MONGODB_HOST')
        assert hasattr(config, 'MONGODB_PORT')
        assert hasattr(config, 'MONGODB_DATABASE')
        assert hasattr(config, 'MONGODB_ENABLED')
    
    def test_redis_config_exists(self):
        """Test that Redis L1/L2 configuration is accessible."""
        # Redis L1 configuration
        assert hasattr(config, 'REDIS_L1_HOST')
        assert hasattr(config, 'REDIS_L1_PORT')
        assert hasattr(config, 'REDIS_L1_DB')
        assert hasattr(config, 'REDIS_L1_ENABLED')
        
        # Redis L2 configuration
        assert hasattr(config, 'REDIS_L2_HOST')
        assert hasattr(config, 'REDIS_L2_PORT')
        assert hasattr(config, 'REDIS_L2_DB')
        assert hasattr(config, 'REDIS_L2_ENABLED')
    
        assert isinstance(config.MONGODB_DATABASE, str)
        assert isinstance(config.MONGODB_ENABLED, bool)
    
    def test_redis_config_types(self):
        """Test Redis L1/L2 config has correct types."""
        # Redis L1 types
        assert isinstance(config.REDIS_L1_HOST, str)
        assert isinstance(config.REDIS_L1_PORT, int)
        assert isinstance(config.REDIS_L1_DB, int)
        assert isinstance(config.REDIS_L1_ENABLED, bool)
        
        # Redis L2 types
        assert isinstance(config.REDIS_L2_HOST, str)
        assert isinstance(config.REDIS_L2_PORT, int)
        assert isinstance(config.REDIS_L2_DB, int)
        assert isinstance(config.REDIS_L2_ENABLED, bool)
    
    def test_get_mongodb_uri_function(self):
        """Test MongoDB URI generation function exists."""
        assert hasattr(config, 'get_mongodb_uri')
        assert callable(config.get_mongodb_uri)


class TestPathConfiguration:
    """Tests for path-related configuration."""
    
    def test_base_dir_exists(self):
        """Test that BASE_DIR is defined."""
        assert hasattr(config, 'BASE_DIR')
        assert config.BASE_DIR is not None
    
    def test_base_dir_is_path(self):
        """Test that BASE_DIR is a Path object."""
        assert isinstance(config.BASE_DIR, Path)
    
    def test_scarefera_lab_dir_equals_base_dir(self):
        """Test that SCAREFERA_LAB_DIR equals BASE_DIR."""
        assert config.SCAREFERA_LAB_DIR == config.BASE_DIR
    
    def test_artifacts_dir_exists(self):
        """Test that ARTIFACTS_DIR is defined."""
        assert hasattr(config, 'ARTIFACTS_DIR')
        assert isinstance(config.ARTIFACTS_DIR, Path)
    
    def test_canonical_dir_exists(self):
        """Test that CANONICAL_DIR is defined."""
        assert hasattr(config, 'CANONICAL_DIR')
        assert isinstance(config.CANONICAL_DIR, Path)
    
    def test_runtime_dir_exists(self):
        """Test that RUNTIME_DIR is defined."""
        assert hasattr(config, 'RUNTIME_DIR')
        assert isinstance(config.RUNTIME_DIR, Path)


class TestServerConfiguration:
    """Tests for server-related configuration."""
    
    def test_host_default(self):
        """Test HOST has correct default."""
        assert hasattr(config, 'HOST')
        assert isinstance(config.HOST, str)
    
    def test_port_default(self):
        """Test PORT has correct default."""
        assert hasattr(config, 'PORT')
        assert isinstance(config.PORT, int)
        assert config.PORT == 5051
    
    def test_debug_default(self):
        """Test DEBUG has correct type."""
        assert hasattr(config, 'DEBUG')
        assert isinstance(config.DEBUG, bool)
    
    @patch.dict(os.environ, {'API_HOST': 'testhost'})
    def test_host_from_env(self):
        """Test HOST can be set from environment."""
        # Re-import to pick up env changes
        import importlib
        importlib.reload(config)
        assert config.HOST == 'testhost'
    
    @patch.dict(os.environ, {'API_PORT': '8080'})
    def test_port_from_env(self):
        """Test PORT can be set from environment."""
        import importlib
        importlib.reload(config)
        assert config.PORT == 8080
    
    @patch.dict(os.environ, {'API_DEBUG': 'false'})
    def test_debug_from_env(self):
        """Test DEBUG can be set from environment."""
        import importlib
        importlib.reload(config)
        assert config.DEBUG is False


class TestCORSConfiguration:
    """Tests for CORS configuration."""
    
    def test_cors_origins_exists(self):
        """Test CORS_ORIGINS is defined."""
        assert hasattr(config, 'CORS_ORIGINS')
        assert isinstance(config.CORS_ORIGINS, list)
    
    def test_cors_origins_default(self):
        """Test CORS_ORIGINS default value."""
        # Default should be ["*"] if not set
        assert len(config.CORS_ORIGINS) > 0
    
    @patch.dict(os.environ, {'CORS_ORIGINS': 'http://localhost:3000,http://localhost:8080'})
    def test_cors_origins_from_env(self):
        """Test CORS_ORIGINS can be set from environment."""
        import importlib
        importlib.reload(config)
        assert 'http://localhost:3000' in config.CORS_ORIGINS
        assert 'http://localhost:8080' in config.CORS_ORIGINS


class TestAuthenticationConfiguration:
    """Tests for authentication configuration."""
    
    def test_auth_enabled_exists(self):
        """Test AUTH_ENABLED is defined."""
        assert hasattr(config, 'AUTH_ENABLED')
        assert isinstance(config.AUTH_ENABLED, bool)
    
    def test_auth_token_exists(self):
        """Test AUTH_TOKEN is defined."""
        assert hasattr(config, 'AUTH_TOKEN')
    
    def test_encryption_key_exists(self):
        """Test ENCRYPTION_KEY is defined."""
        assert hasattr(config, 'ENCRYPTION_KEY')
    
    def test_google_client_id_exists(self):
        """Test GOOGLE_CLIENT_ID is defined."""
        assert hasattr(config, 'GOOGLE_CLIENT_ID')
    
    def test_google_client_secret_exists(self):
        """Test GOOGLE_CLIENT_SECRET is defined."""
        assert hasattr(config, 'GOOGLE_CLIENT_SECRET')
    
    @patch.dict(os.environ, {'AUTH_ENABLED': 'true'})
    def test_auth_enabled_from_env(self):
        """Test AUTH_ENABLED can be enabled from environment."""
        import importlib
        importlib.reload(config)
        assert config.AUTH_ENABLED is True


class TestAPIConfiguration:
    """Tests for API configuration."""
    
    def test_api_prefix_exists(self):
        """Test API_PREFIX is defined."""
        assert hasattr(config, 'API_PREFIX')
        assert isinstance(config.API_PREFIX, str)
    
    def test_api_prefix_default(self):
        """Test API_PREFIX has correct default."""
        assert config.API_PREFIX == "/api"
    
    def test_api_version_exists(self):
        """Test API_VERSION is defined."""
        assert hasattr(config, 'API_VERSION')
        assert isinstance(config.API_VERSION, str)
    
    def test_api_version_default(self):
        """Test API_VERSION has correct default."""
        assert config.API_VERSION == "v1"
    
    @patch.dict(os.environ, {'API_PREFIX': '/v2/api'})
    def test_api_prefix_from_env(self):
        """Test API_PREFIX can be set from environment."""
        import importlib
        importlib.reload(config)
        assert config.API_PREFIX == '/v2/api'


class TestHTTPConfiguration:
    """Tests for HTTP client configuration."""
    
    def test_http_connection_timeout_exists(self):
        """Test HTTP_CONNECTION_TIMEOUT is defined."""
        assert hasattr(config, 'HTTP_CONNECTION_TIMEOUT')
        assert isinstance(config.HTTP_CONNECTION_TIMEOUT, float)
    
    def test_http_read_timeout_exists(self):
        """Test HTTP_READ_TIMEOUT is defined."""
        assert hasattr(config, 'HTTP_READ_TIMEOUT')
        assert isinstance(config.HTTP_READ_TIMEOUT, float)
    
    def test_http_timeout_defaults(self):
        """Test HTTP timeout defaults are reasonable."""
        assert config.HTTP_CONNECTION_TIMEOUT > 0
        assert config.HTTP_READ_TIMEOUT > 0
        assert config.HTTP_READ_TIMEOUT >= config.HTTP_CONNECTION_TIMEOUT
    
    @patch.dict(os.environ, {'HTTP_CONNECTION_TIMEOUT': '5.0'})
    def test_http_connection_timeout_from_env(self):
        """Test HTTP_CONNECTION_TIMEOUT can be set from environment."""
        import importlib
        importlib.reload(config)
        assert config.HTTP_CONNECTION_TIMEOUT == 5.0


class TestOllamaConfiguration:
    """Tests for Ollama LLM configuration."""
    
    def test_ollama_base_url_exists(self):
        """Test OLLAMA_BASE_URL is defined."""
        assert hasattr(config, 'OLLAMA_BASE_URL')
        assert isinstance(config.OLLAMA_BASE_URL, str)
    
    def test_ollama_model_exists(self):
        """Test OLLAMA_MODEL is defined."""
        assert hasattr(config, 'OLLAMA_MODEL')
        assert isinstance(config.OLLAMA_MODEL, str)
    
    def test_ollama_timeout_exists(self):
        """Test OLLAMA_TIMEOUT is defined."""
        assert hasattr(config, 'OLLAMA_TIMEOUT')
        assert isinstance(config.OLLAMA_TIMEOUT, int)
    
    def test_ollama_timeout_reasonable(self):
        """Test OLLAMA_TIMEOUT is reasonable."""
        assert config.OLLAMA_TIMEOUT > 0
    
    @patch.dict(os.environ, {'OLLAMA_BASE_URL': 'http://custom:11434'})
    def test_ollama_base_url_from_env(self):
        """Test OLLAMA_BASE_URL can be set from environment."""
        import importlib
        importlib.reload(config)
        assert config.OLLAMA_BASE_URL == 'http://custom:11434'


class TestRAGConfiguration:
    """Tests for RAG (Retrieval-Augmented Generation) configuration."""
    
    def test_ollama_embedding_model_exists(self):
        """Test OLLAMA_EMBEDDING_MODEL is defined."""
        assert hasattr(config, 'OLLAMA_EMBEDDING_MODEL')
        assert isinstance(config.OLLAMA_EMBEDDING_MODEL, str)
    
    def test_vectorstore_path_exists(self):
        """Test VECTORSTORE_PATH is defined."""
        assert hasattr(config, 'VECTORSTORE_PATH')
        assert isinstance(config.VECTORSTORE_PATH, str)
    
    def test_vectorstore_collection_exists(self):
        """Test VECTORSTORE_COLLECTION is defined."""
        assert hasattr(config, 'VECTORSTORE_COLLECTION')
        assert isinstance(config.VECTORSTORE_COLLECTION, str)
    
    def test_chunk_size_exists(self):
        """Test CHUNK_SIZE is defined."""
        assert hasattr(config, 'CHUNK_SIZE')
        assert isinstance(config.CHUNK_SIZE, int)
    
    def test_chunk_overlap_exists(self):
        """Test CHUNK_OVERLAP is defined."""
        assert hasattr(config, 'CHUNK_OVERLAP')
        assert isinstance(config.CHUNK_OVERLAP, int)
    
    def test_chunk_config_reasonable(self):
        """Test chunk configuration is reasonable."""
        assert config.CHUNK_SIZE > 0
        assert config.CHUNK_OVERLAP >= 0
        assert config.CHUNK_OVERLAP < config.CHUNK_SIZE
    
    def test_embedding_batch_size_exists(self):
        """Test EMBEDDING_BATCH_SIZE is defined."""
        assert hasattr(config, 'EMBEDDING_BATCH_SIZE')
        assert isinstance(config.EMBEDDING_BATCH_SIZE, int)
        assert config.EMBEDDING_BATCH_SIZE > 0
    
    def test_embedding_batch_delay_exists(self):
        """Test EMBEDDING_BATCH_DELAY is defined."""
        assert hasattr(config, 'EMBEDDING_BATCH_DELAY')
        assert isinstance(config.EMBEDDING_BATCH_DELAY, float)
        assert config.EMBEDDING_BATCH_DELAY >= 0
    
    def test_rag_postprocess_config_exists(self):
        """Test RAG post-processing configuration."""
        assert hasattr(config, 'RAG_POSTPROCESS_LLM_ENABLED')
        assert hasattr(config, 'RAG_POSTPROCESS_LLM_MODEL')
        assert hasattr(config, 'RAG_POSTPROCESS_LLM_PROMPT')
        assert isinstance(config.RAG_POSTPROCESS_LLM_ENABLED, bool)


class TestGeminiConfiguration:
    """Tests for Gemini API configuration."""
    
    def test_gemini_api_key_exists(self):
        """Test GEMINI_API_KEY is defined."""
        assert hasattr(config, 'GEMINI_API_KEY')
    
    def test_gemini_api_url_exists(self):
        """Test GEMINI_API_URL is defined."""
        assert hasattr(config, 'GEMINI_API_URL')
        assert isinstance(config.GEMINI_API_URL, str)
    
    def test_gemini_timeout_exists(self):
        """Test GEMINI_TIMEOUT is defined."""
        assert hasattr(config, 'GEMINI_TIMEOUT')
        assert isinstance(config.GEMINI_TIMEOUT, int)
    
    def test_gemini_default_model_exists(self):
        """Test GEMINI_DEFAULT_MODEL is defined."""
        assert hasattr(config, 'GEMINI_DEFAULT_MODEL')
        assert isinstance(config.GEMINI_DEFAULT_MODEL, str)
    
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'})
    def test_gemini_api_key_from_env(self):
        """Test GEMINI_API_KEY can be set from environment."""
        import importlib
        importlib.reload(config)
        assert config.GEMINI_API_KEY == 'test-key'


class TestOpenAIConfiguration:
    """Tests for OpenAI API configuration."""
    
    def test_openai_api_key_exists(self):
        """Test OPENAI_API_KEY is defined."""
        assert hasattr(config, 'OPENAI_API_KEY')
    
    def test_openai_api_url_exists(self):
        """Test OPENAI_API_URL is defined."""
        assert hasattr(config, 'OPENAI_API_URL')
        assert isinstance(config.OPENAI_API_URL, str)
    
    def test_openai_default_model_exists(self):
        """Test OPENAI_DEFAULT_MODEL is defined."""
        assert hasattr(config, 'OPENAI_DEFAULT_MODEL')
        assert isinstance(config.OPENAI_DEFAULT_MODEL, str)
    
    def test_openai_timeout_exists(self):
        """Test OPENAI_TIMEOUT is defined."""
        assert hasattr(config, 'OPENAI_TIMEOUT')
        assert isinstance(config.OPENAI_TIMEOUT, float)
    
    def test_openai_models_exists(self):
        """Test OPENAI_MODELS is defined."""
        assert hasattr(config, 'OPENAI_MODELS')
        assert isinstance(config.OPENAI_MODELS, list)
        assert len(config.OPENAI_MODELS) > 0


class TestModelConfiguration:
    """Tests for AI model configuration."""
    
    def test_ollama_models_exists(self):
        """Test OLLAMA_MODELS is defined."""
        assert hasattr(config, 'OLLAMA_MODELS')
        assert isinstance(config.OLLAMA_MODELS, list)
    
    def test_gemini_models_exists(self):
        """Test GEMINI_MODELS is defined."""
        assert hasattr(config, 'GEMINI_MODELS')
        assert isinstance(config.GEMINI_MODELS, list)
    
    @patch.dict(os.environ, {'OLLAMA_MODELS': 'mistral,llama2,phi'})
    def test_ollama_models_from_env(self):
        """Test OLLAMA_MODELS can be set from environment."""
        import importlib
        importlib.reload(config)
        assert 'mistral' in config.OLLAMA_MODELS
        assert 'llama2' in config.OLLAMA_MODELS


class TestMiscellaneousConfiguration:
    """Tests for miscellaneous configuration."""
    
    def test_tree_cache_ttl_exists(self):
        """Test TREE_CACHE_TTL is defined."""
        assert hasattr(config, 'TREE_CACHE_TTL')
        assert isinstance(config.TREE_CACHE_TTL, int)
    
    def test_log_level_exists(self):
        """Test LOG_LEVEL is defined."""
        assert hasattr(config, 'LOG_LEVEL')
        assert isinstance(config.LOG_LEVEL, str)
    
    def test_ngrok_api_url_exists(self):
        """Test NGROK_API_URL is defined."""
        assert hasattr(config, 'NGROK_API_URL')
        assert isinstance(config.NGROK_API_URL, str)
    
    def test_rag_vectorstore_path_exists(self):
        """Test RAG_VECTORSTORE_PATH is defined."""
        assert hasattr(config, 'RAG_VECTORSTORE_PATH')
        assert isinstance(config.RAG_VECTORSTORE_PATH, str)
    
    def test_conversation_tracing_exists(self):
        """Test ENABLE_CONVERSATION_TRACING is defined."""
        assert hasattr(config, 'ENABLE_CONVERSATION_TRACING')
        assert isinstance(config.ENABLE_CONVERSATION_TRACING, bool)
    
    def test_admin_email_exists(self):
        """Test ADMIN_EMAIL is defined."""
        assert hasattr(config, 'ADMIN_EMAIL')


class TestConfigurationConsistency:
    """Tests for configuration consistency and relationships."""
    
    def test_redis_cache_ttl_hierarchy(self):
        """Test Redis cache TTL values have logical hierarchy."""
        if hasattr(config, 'REDIS_CACHE_TTL'):
            assert config.REDIS_CACHE_TTL > 0
    
    def test_timeout_values_reasonable(self):
        """Test all timeout values are positive."""
        timeout_configs = [
            'OLLAMA_TIMEOUT',
            'GEMINI_TIMEOUT',
            'OPENAI_TIMEOUT',
            'HTTP_CONNECTION_TIMEOUT',
            'HTTP_READ_TIMEOUT'
        ]
        
        for timeout_config in timeout_configs:
            if hasattr(config, timeout_config):
                value = getattr(config, timeout_config)
                assert value > 0, f"{timeout_config} should be positive"
    
    def test_port_number_valid(self):
        """Test PORT is in valid range."""
        assert 1 <= config.PORT <= 65535
    
    def test_paths_are_absolute_or_relative(self):
        """Test path configurations are strings or Path objects."""
        path_configs = ['BASE_DIR', 'ARTIFACTS_DIR', 'CANONICAL_DIR', 'RUNTIME_DIR']
        
        for path_config in path_configs:
            if hasattr(config, path_config):
                value = getattr(config, path_config)
                assert isinstance(value, (str, Path)), f"{path_config} should be str or Path"
