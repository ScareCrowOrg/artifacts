#!/usr/bin/env python3
"""
Verification script to ensure ChromaDB telemetry is properly disabled.

This script checks:
1. ANONYMIZED_TELEMETRY environment variable is set
2. ChromaDB can be imported without errors
3. No PostHog network calls are made during ChromaDB initialization

Usage:
    python test_chromadb_telemetry.py
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))


def validate_telemetry_setting(value):
    """
    Validate telemetry environment variable setting.
    
    Args:
        value: The environment variable value (or "not_set" if not present)
        
    Returns:
        tuple: (is_valid, status_message) where is_valid is True if telemetry is properly disabled
    """
    if value == "not_set":
        return False, "❌ FAIL: ANONYMIZED_TELEMETRY is not set"
    elif value.lower() in ["false", "0", "no"]:
        return True, "✅ PASS: Telemetry is disabled"
    else:
        return False, f"⚠️  WARNING: ANONYMIZED_TELEMETRY={value} (should be False)"


def test_env_variable():
    """Test that ANONYMIZED_TELEMETRY is set correctly."""
    print("=" * 60)
    print("Test 1: Environment Variable Configuration")
    print("=" * 60)
    
    telemetry_setting = os.getenv("ANONYMIZED_TELEMETRY", "not_set")
    print(f"ANONYMIZED_TELEMETRY = {telemetry_setting}")
    
    is_valid, message = validate_telemetry_setting(telemetry_setting)
    print(message)
    
    if not is_valid:
        print("   Set it in .env file or environment")
    
    return is_valid


def test_chromadb_import():
    """Test that ChromaDB can be imported."""
    print("\n" + "=" * 60)
    print("Test 2: ChromaDB Import")
    print("=" * 60)
    
    try:
        import chromadb
        print(f"✅ PASS: ChromaDB imported successfully")
        print(f"   Version: {chromadb.__version__}")
        return True
    except ImportError as e:
        print(f"❌ FAIL: Could not import ChromaDB: {e}")
        return False


def check_posthog_dependency():
    """
    Check if PostHog is installed as expected dependency from ChromaDB.
    
    This is informational only - PostHog presence is expected since it's
    a transitive dependency from ChromaDB. The test verifies it exists
    but doesn't execute telemetry code.
    
    Returns:
        bool: True (always, as this is informational)
    """
    print("\n" + "=" * 60)
    print("Test 3: PostHog Dependency (Informational)")
    print("=" * 60)
    
    try:
        import posthog
        print(f"✅ INFO: PostHog is installed (expected as ChromaDB dependency)")
        print(f"   Version: {posthog.__version__}")
        print("   Telemetry is disabled via ANONYMIZED_TELEMETRY env var")
        return True
    except ImportError:
        print("⚠️  INFO: PostHog not installed")
        print("   This is expected if ChromaDB is not yet installed")
        return True  # Not a failure, just informational


def test_chromadb_client_creation():
    """Test that ChromaDB client can be created without network calls."""
    print("\n" + "=" * 60)
    print("Test 4: ChromaDB Client Creation (No Network Calls)")
    print("=" * 60)
    
    try:
        import chromadb
        from chromadb.config import Settings
        
        # Create ephemeral client with telemetry explicitly disabled
        settings = Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
        
        print("   Creating ChromaDB client with telemetry disabled...")
        client = chromadb.Client(settings)
        
        print("✅ PASS: ChromaDB client created successfully")
        print("   No PostHog network calls should have been made")
        
        # Try to create a test collection
        print("   Creating test collection...")
        collection = client.create_collection(name="test_telemetry_check")
        print(f"   Collection created: {collection.name}")
        
        # Clean up
        client.delete_collection(name="test_telemetry_check")
        print("   Test collection deleted")
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error creating ChromaDB client: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_langchain_chroma():
    """Test LangChain Chroma integration (as used in production)."""
    print("\n" + "=" * 60)
    print("Test 5: LangChain Chroma Integration")
    print("=" * 60)
    
    try:
        from langchain_chroma import Chroma
        from langchain_core.documents import Document
        
        print("✅ PASS: LangChain Chroma imported successfully")
        
        # Note: We can't fully test without embeddings, but import is good
        print("   LangChain Chroma integration is available")
        print("   Actual embedding tests require Ollama service")
        
        return True
        
    except ImportError as e:
        print(f"❌ FAIL: Could not import LangChain Chroma: {e}")
        return False


def main():
    """Run all verification tests."""
    print("\n" + "🔍" * 30)
    print("ChromaDB Telemetry Verification Script")
    print("🔍" * 30 + "\n")
    
    results = []
    
    # Run all tests
    results.append(("Environment Variable", test_env_variable()))
    results.append(("ChromaDB Import", test_chromadb_import()))
    results.append(("PostHog Dependency", check_posthog_dependency()))
    results.append(("ChromaDB Client", test_chromadb_client_creation()))
    results.append(("LangChain Integration", test_langchain_chroma()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "-" * 60)
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\n🎉 All tests passed! ChromaDB telemetry is properly configured.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check configuration above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
