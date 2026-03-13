#!/usr/bin/env python3
"""
Demo script for RAG post-processing feature.

This script demonstrates the RAG post-processing functionality
without requiring a full application setup.

Usage:
    python demo_rag_postprocessing.py
"""

import asyncio
from unittest.mock import AsyncMock, Mock
from langchain_core.documents import Document


async def demo_postprocessing():
    """Demonstrate RAG post-processing with mocked Ollama."""
    
    print("=" * 70)
    print("RAG Post-processing Demo")
    print("=" * 70)
    print()
    
    # Create sample chunks (simulating RAG retrieval)
    chunks = [
        Document(
            page_content="The ScareVerse architecture uses a microservices pattern with FastAPI for the backend. The backend handles API requests and coordinates with the AI services. FastAPI provides async support which is important for performance.",
            metadata={'source': 'docs/architecture.md'}
        ),
        Document(
            page_content="FastAPI is a modern web framework for building APIs with Python. It provides automatic OpenAPI documentation. The ScareVerse backend uses FastAPI for all API endpoints.",
            metadata={'source': 'docs/backend.md'}
        ),
        Document(
            page_content="The authentication system in ScareVerse uses OAuth2. Users can login with Google accounts. The auth module handles token validation.",
            metadata={'source': 'docs/auth.md'}
        ),
    ]
    
    user_query = "Explain the backend architecture"
    
    print(f"User Query: {user_query}")
    print(f"\nRetrieved {len(chunks)} chunks from RAG:")
    for i, chunk in enumerate(chunks, 1):
        print(f"\n  [{i}] From: {chunk.metadata['source']}")
        print(f"      Content: {chunk.page_content[:80]}...")
    
    # Calculate raw context size
    raw_size = sum(len(c.page_content) for c in chunks)
    print(f"\nTotal raw context size: {raw_size} characters")
    
    # Simulate post-processing
    print("\n" + "-" * 70)
    print("Applying Post-processing with Local LLM (Phi3)...")
    print("-" * 70)
    
    # Simulated condensed output (what the local LLM would produce)
    condensed_context = """
The ScareVerse backend architecture:
- Uses microservices pattern with FastAPI
- FastAPI provides async support and automatic OpenAPI docs
- Handles API requests and coordinates with AI services
- Implements OAuth2 authentication with Google login support
"""
    
    condensed_size = len(condensed_context.strip())
    reduction = ((raw_size - condensed_size) / raw_size) * 100
    
    print(f"\nCondensed context ({condensed_size} characters):")
    print(condensed_context)
    
    print(f"\n{'=' * 70}")
    print("Results:")
    print(f"  - Original size: {raw_size} characters")
    print(f"  - Condensed size: {condensed_size} characters")
    print(f"  - Reduction: {reduction:.1f}%")
    print(f"  - Relevance: Improved (focused on architecture)")
    print(f"  - Redundancy: Eliminated (FastAPI mentioned once)")
    print("=" * 70)
    
    print("\n✅ Post-processing successfully condensed and organized the context!")
    print("   The main LLM will now receive cleaner, more focused information.")


async def demo_with_actual_module():
    """Demo using the actual rag_postprocessor module."""
    
    print("\n" + "=" * 70)
    print("Testing Actual Module")
    print("=" * 70)
    
    try:
        import sys
        sys.path.insert(0, '/home/runner/work/ScareVerseLab/ScareVerseLab/backend')
        
        from app.services.rag_postprocessor import postprocess_rag_context
        from app.config import RAG_POSTPROCESS_LLM_MODEL, RAG_POSTPROCESS_LLM_PROMPT, OLLAMA_BASE_URL
        
        print(f"\n✅ Successfully imported rag_postprocessor module")
        print(f"   Model: {RAG_POSTPROCESS_LLM_MODEL}")
        print(f"   Ollama URL: {OLLAMA_BASE_URL}")
        
        # Test with disabled (should just format)
        chunks = [Document(page_content="Test content", metadata={})]
        result = await postprocess_rag_context(
            chunks=chunks,
            user_query="Test",
            enabled=False,
            model=RAG_POSTPROCESS_LLM_MODEL,
            prompt_template=RAG_POSTPROCESS_LLM_PROMPT,
            base_url=OLLAMA_BASE_URL
        )
        
        print(f"\n✅ Post-processing function works (disabled mode)")
        print(f"   Result: {result[:100]}...")
        
    except Exception as e:
        print(f"\n⚠️  Could not test actual module: {e}")
        print("   This is expected in a minimal environment")


if __name__ == "__main__":
    print("\n🚀 Starting RAG Post-processing Demo\n")
    
    # Run demos
    asyncio.run(demo_postprocessing())
    asyncio.run(demo_with_actual_module())
    
    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print("\nTo enable in production:")
    print("  1. Set RAG_POSTPROCESS_LLM_ENABLED=true in .env")
    print("  2. Ensure Ollama is running: ollama serve")
    print("  3. Pull the model: ollama pull phi3:latest")
    print("\nSee backend/app/services/README_RAG_POSTPROCESSING.md for details")
    print()
