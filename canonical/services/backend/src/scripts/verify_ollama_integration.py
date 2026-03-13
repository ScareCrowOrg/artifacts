#!/usr/bin/env python3
"""
Verification script for Ollama embeddings integration.

This script verifies that the Ollama embeddings are properly configured
and demonstrates the key features of the updated RAG pipeline.

Usage:
    python scripts/verify_ollama_integration.py

Requirements:
    - Ollama installed and running (ollama serve)
    - At least one model pulled (ollama pull mistral)
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import (
    OLLAMA_BASE_URL,
    OLLAMA_EMBEDDING_MODEL,
    VECTORSTORE_PATH,
    VECTORSTORE_COLLECTION,
    CHUNK_SIZE,
    CHUNK_OVERLAP
)


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def verify_configuration():
    """Verify that configuration is properly set up."""
    print_header("Configuration Verification")
    
    print("✓ Checking configuration variables...")
    print(f"  OLLAMA_BASE_URL: {OLLAMA_BASE_URL}")
    print(f"  OLLAMA_EMBEDDING_MODEL: {OLLAMA_EMBEDDING_MODEL}")
    print(f"  VECTORSTORE_PATH: {VECTORSTORE_PATH}")
    print(f"  VECTORSTORE_COLLECTION: {VECTORSTORE_COLLECTION}")
    print(f"  CHUNK_SIZE: {CHUNK_SIZE}")
    print(f"  CHUNK_OVERLAP: {CHUNK_OVERLAP}")
    
    # Verify Ollama URL is set
    if not OLLAMA_BASE_URL:
        print("\n❌ ERROR: OLLAMA_BASE_URL is not set!")
        return False
    
    # Verify embedding model is set
    if not OLLAMA_EMBEDDING_MODEL:
        print("\n❌ ERROR: OLLAMA_EMBEDDING_MODEL is not set!")
        return False
    
    print("\n✓ Configuration is valid!")
    return True


def check_ollama_connection():
    """Check if Ollama service is reachable."""
    print_header("Ollama Service Check")
    
    import requests
    
    try:
        print(f"Attempting to connect to {OLLAMA_BASE_URL}...")
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        
        if response.status_code == 200:
            models = response.json().get('models', [])
            print(f"✓ Ollama is running at {OLLAMA_BASE_URL}")
            print(f"✓ Found {len(models)} models:")
            for model in models:
                model_name = model.get('name', 'unknown')
                print(f"  - {model_name}")
            
            # Check if configured model is available
            model_names = [m.get('name', '') for m in models]
            if any(OLLAMA_EMBEDDING_MODEL in name for name in model_names):
                print(f"\n✓ Configured model '{OLLAMA_EMBEDDING_MODEL}' is available!")
                return True
            else:
                print(f"\n⚠ WARNING: Configured model '{OLLAMA_EMBEDDING_MODEL}' not found!")
                print(f"  Run: ollama pull {OLLAMA_EMBEDDING_MODEL}")
                return False
        else:
            print(f"❌ ERROR: Ollama returned status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ ERROR: Cannot connect to Ollama at {OLLAMA_BASE_URL}")
        print("  Make sure Ollama is installed and running:")
        print("    1. Install from https://ollama.ai/")
        print("    2. Run: ollama serve")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_embedding_creation():
    """Test creating embeddings instance."""
    print_header("Embedding Creation Test")
    
    try:
        from app.utils.document_ingestion import create_embeddings
        
        print(f"Creating embeddings with model '{OLLAMA_EMBEDDING_MODEL}'...")
        embeddings = create_embeddings()
        
        print(f"✓ Embeddings instance created successfully!")
        print(f"  Type: {type(embeddings).__name__}")
        print(f"  Model: {embeddings.model}")
        print(f"  Base URL: {embeddings.base_url}")
        
        return True
    except Exception as e:
        print(f"❌ ERROR creating embeddings: {e}")
        return False


def demonstrate_models():
    """Demonstrate support for multiple models."""
    print_header("Multi-Model Support")
    
    try:
        from app.utils.document_ingestion import create_embeddings
        
        models = ['mistral', 'phi', 'deepseek-coder']
        
        print("Testing embeddings creation with different models:\n")
        for model in models:
            try:
                embeddings = create_embeddings(model=model)
                print(f"  ✓ {model:15} - Created successfully")
            except Exception as e:
                print(f"  ✗ {model:15} - Error: {e}")
        
        return True
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def show_usage_examples():
    """Show usage examples."""
    print_header("Usage Examples")
    
    examples = """
# Basic usage with default model
from app.utils.document_ingestion import ingest_documents_to_vectorstore

vectorstore = ingest_documents_to_vectorstore()

# Use specific model
vectorstore = ingest_documents_to_vectorstore(embedding_model='phi')

# Force recreate vector store
vectorstore = ingest_documents_to_vectorstore(force_recreate=True)

# Get existing vector store or create empty
from app.utils.document_ingestion import get_or_create_vectorstore

vectorstore = get_or_create_vectorstore(auto_ingest=False)

# Auto-ingest if vector store doesn't exist
vectorstore = get_or_create_vectorstore(auto_ingest=True)
"""
    
    print(examples)


def main():
    """Run all verification checks."""
    print_header("Ollama Embeddings Integration Verification")
    print("This script verifies the Ollama embeddings integration.")
    
    all_passed = True
    
    # Check 1: Configuration
    if not verify_configuration():
        all_passed = False
    
    # Check 2: Ollama connection
    if not check_ollama_connection():
        all_passed = False
        print("\n⚠ Some checks require Ollama to be running.")
        print("  Install from: https://ollama.ai/")
        print(f"  Then run: ollama pull {OLLAMA_EMBEDDING_MODEL}")
    else:
        # Check 3: Embedding creation (requires Ollama)
        if not test_embedding_creation():
            all_passed = False
        
        # Check 4: Multiple models
        demonstrate_models()
    
    # Always show usage examples
    show_usage_examples()
    
    # Summary
    print_header("Summary")
    if all_passed:
        print("✅ All checks passed!")
        print("\nThe Ollama embeddings integration is working correctly.")
        print("You can now use the RAG pipeline with local embeddings.")
    else:
        print("⚠ Some checks failed.")
        print("\nPlease ensure:")
        print("  1. Ollama is installed (https://ollama.ai/)")
        print("  2. Ollama service is running (ollama serve)")
        print(f"  3. Model is pulled (ollama pull {OLLAMA_EMBEDDING_MODEL})")
        print("  4. Configuration is correct in .env file")
    
    print("\n" + "=" * 60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
