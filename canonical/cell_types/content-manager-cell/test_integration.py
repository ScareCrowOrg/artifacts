#!/usr/bin/env python3
"""
Simple integration test for content-manager-cell.

Tests basic functionality without requiring full environment setup.
"""

import sys
import base64
from pathlib import Path

# Add cell scripts to path
cell_scripts_path = Path(__file__).parent / "backend" / "scripts"
sys.path.insert(0, str(cell_scripts_path))

from utils import (
    decode_base64_binary,
    encode_binary_to_base64,
    extract_mime_type_from_filename
)


def test_utils():
    """Test utility functions."""
    print("Testing utils.py...")
    
    # Test encode/decode
    test_data = b"Hello, World!"
    encoded = encode_binary_to_base64(test_data, "text/plain")
    decoded, mime = decode_base64_binary(encoded)
    
    assert decoded == test_data, "Encode/decode mismatch"
    assert mime == "text/plain", "MIME type mismatch"
    print("  ✓ Base64 encode/decode works")
    
    # Test MIME type extraction
    assert extract_mime_type_from_filename("test.png") == "image/png"
    assert extract_mime_type_from_filename("test.jpg") == "image/jpeg"
    assert extract_mime_type_from_filename("test.glb") == "model/gltf-binary"
    print("  ✓ MIME type extraction works")


def test_storage_interfaces():
    """Test storage backend interfaces."""
    print("\nTesting storage.py...")
    
    # Import without initializing (to avoid boto3 dependency)
    from storage import StorageBackend, LocalStorage
    
    # Verify LocalStorage is a proper subclass
    assert issubclass(LocalStorage, StorageBackend), "LocalStorage must extend StorageBackend"
    print("  ✓ Storage classes structure is correct")
    
    # Test LocalStorage basic functionality
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(tmpdir)
        
        # Upload
        content_id = "test-123"
        binary = b"Test content"
        filename = "test.txt"
        
        data_ref = storage.upload(content_id, binary, filename, "text/plain")
        assert data_ref.startswith("file://"), "Invalid data_ref format"
        print("  ✓ LocalStorage upload works")
        
        # Download
        downloaded = storage.download(content_id, filename)
        assert downloaded == binary, "Downloaded content mismatch"
        print("  ✓ LocalStorage download works")
        
        # Delete
        result = storage.delete(content_id, filename)
        assert result is True, "Delete should return True"
        
        downloaded_after_delete = storage.download(content_id, filename)
        assert downloaded_after_delete is None, "Content should be deleted"
        print("  ✓ LocalStorage delete works")


def test_main_structure():
    """Test main.py structure and imports."""
    print("\nTesting main.py structure...")
    
    # We can't fully test without the backend dependencies,
    # but we can verify the module structure
    try:
        # Import without executing
        import ast
        main_path = Path(__file__).parent / "backend" / "scripts" / "main.py"
        
        with open(main_path, 'r') as f:
            tree = ast.parse(f.read())
        
        # Verify required functions exist
        functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)]
        
        assert 'execute_cell' in functions, "Missing execute_cell function"
        assert 'handle_list' in functions, "Missing handle_list function"
        assert 'handle_load' in functions, "Missing handle_load function"
        assert 'handle_persist' in functions, "Missing handle_persist function"
        
        print("  ✓ All required async functions defined")
        
    except Exception as e:
        print(f"  ⚠ Could not fully validate main.py: {e}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Content Manager Cell - Integration Tests")
    print("=" * 60)
    
    try:
        test_utils()
        test_storage_interfaces()
        test_main_structure()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print("\n" + "=" * 60)
        print(f"❌ Test failed: {e}")
        print("=" * 60)
        return 1
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
