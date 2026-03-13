"""
Unit tests for Vector Lifecycle Management service.

Tests the vector store maintenance functions including:
- File hash calculation
- Vector cleanup for deleted files
- Vector updates for modified files
- Full maintenance workflow

Compliance: RULESET.md Rule 3.1 (90% coverage), Rule 3.2 (Unit tests)
"""

import pytest
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from tempfile import NamedTemporaryFile, TemporaryDirectory
from datetime import datetime

from app.services.vector_lifecycle import (
    calculate_file_hash,
    get_all_vectorstore_sources,
    remove_vectors_for_deleted_files,
    update_vectors_for_modified_files,
    perform_full_maintenance
)


class TestCalculateFileHash:
    """Tests for calculate_file_hash function."""
    
    def test_calculate_hash_success(self):
        """Test successful hash calculation."""
        with NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Test content for hashing")
            temp_file = Path(f.name)
        
        try:
            file_hash = calculate_file_hash(temp_file)
            
            # Verify it's a valid SHA256 hash (64 hex characters)
            assert len(file_hash) == 64
            assert all(c in '0123456789abcdef' for c in file_hash)
            
            # Verify hash is consistent
            hash2 = calculate_file_hash(temp_file)
            assert file_hash == hash2
        finally:
            temp_file.unlink()
    
    def test_calculate_hash_different_content(self):
        """Test that different content produces different hashes."""
        with NamedTemporaryFile(mode='w', delete=False) as f1:
            f1.write("Content A")
            temp_file1 = Path(f1.name)
        
        with NamedTemporaryFile(mode='w', delete=False) as f2:
            f2.write("Content B")
            temp_file2 = Path(f2.name)
        
        try:
            hash1 = calculate_file_hash(temp_file1)
            hash2 = calculate_file_hash(temp_file2)
            
            assert hash1 != hash2
        finally:
            temp_file1.unlink()
            temp_file2.unlink()
    
    def test_calculate_hash_nonexistent_file(self):
        """Test hash calculation for nonexistent file returns empty string."""
        import tempfile
        non_existent = Path(tempfile.gettempdir()) / "nonexistent_file_12345.txt"
        file_hash = calculate_file_hash(non_existent)
        
        assert file_hash == ""
    
    def test_calculate_hash_permission_error(self):
        """Test hash calculation handles permission errors."""
        with NamedTemporaryFile(delete=False) as f:
            temp_file = Path(f.name)
        
        try:
            # Mock open to raise permission error
            with patch('builtins.open', side_effect=PermissionError("Access denied")):
                file_hash = calculate_file_hash(temp_file)
                assert file_hash == ""
        finally:
            temp_file.unlink()


class TestGetAllVectorstoreSources:
    """Tests for get_all_vectorstore_sources function."""
    
    def test_get_sources_success(self):
        """Test successful retrieval of vector store sources."""
        mock_vectorstore = Mock()
        mock_vectorstore.get.return_value = {
            'metadatas': [
                {'source': 'file1.py'},
                {'source': 'file2.py'},
                {'source': 'file1.py'},  # Duplicate
                {'source': 'file3.py'}
            ]
        }
        
        sources = get_all_vectorstore_sources(mock_vectorstore)
        
        assert len(sources) == 3  # Duplicates removed
        assert 'file1.py' in sources
        assert 'file2.py' in sources
        assert 'file3.py' in sources
    
    def test_get_sources_empty_vectorstore(self):
        """Test retrieval from empty vector store."""
        mock_vectorstore = Mock()
        mock_vectorstore.get.return_value = {
            'metadatas': []
        }
        
        sources = get_all_vectorstore_sources(mock_vectorstore)
        
        assert len(sources) == 0
    
    def test_get_sources_missing_metadata(self):
        """Test handling of missing metadata."""
        mock_vectorstore = Mock()
        mock_vectorstore.get.return_value = {
            'metadatas': [
                {'source': 'file1.py'},
                None,  # Missing metadata
                {'other_field': 'value'},  # No 'source' field
                {'source': 'file2.py'}
            ]
        }
        
        sources = get_all_vectorstore_sources(mock_vectorstore)
        
        assert len(sources) == 2
        assert 'file1.py' in sources
        assert 'file2.py' in sources
    
    def test_get_sources_error_handling(self):
        """Test error handling when vectorstore.get() fails."""
        mock_vectorstore = Mock()
        mock_vectorstore.get.side_effect = Exception("Database error")
        
        sources = get_all_vectorstore_sources(mock_vectorstore)
        
        assert len(sources) == 0


class TestRemoveVectorsForDeletedFiles:
    """Tests for remove_vectors_for_deleted_files function."""
    
    def test_remove_no_deleted_files(self):
        """Test removal when no files are deleted."""
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            vectorstore_dir = base_dir / "chroma_db"
            vectorstore_dir.mkdir()
            
            # Create test file
            test_file = base_dir / "test.txt"
            test_file.write_text("content")
            
            mock_vectorstore = Mock()
            mock_collection = Mock()
            mock_vectorstore._collection = mock_collection
            mock_vectorstore.get.return_value = {
                'metadatas': [{'source': 'test.txt'}]
            }
            
            with patch('app.services.vector_lifecycle.create_embeddings') as mock_embeddings:
                with patch('app.services.vector_lifecycle.Chroma', return_value=mock_vectorstore):
                    with patch('app.services.vector_lifecycle.BASE_DIR', base_dir):
                        result = remove_vectors_for_deleted_files(
                            vectorstore_path="chroma_db",
                            embedding_model="test-model"
                        )
            
            assert result['files_checked'] == 1
            assert result['files_deleted'] == 0
            assert result['files_remaining'] == 1
            assert len(result['deleted_sources']) == 0
    
    def test_remove_deleted_files(self):
        """Test removal of vectors for deleted files."""
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            vectorstore_dir = base_dir / "chroma_db"
            vectorstore_dir.mkdir()
            
            mock_vectorstore = Mock()
            mock_collection = Mock()
            mock_vectorstore._collection = mock_collection
            # File doesn't exist
            mock_vectorstore.get.return_value = {
                'metadatas': [{'source': 'deleted_file.txt'}]
            }
            
            with patch('app.services.vector_lifecycle.create_embeddings') as mock_embeddings:
                with patch('app.services.vector_lifecycle.Chroma', return_value=mock_vectorstore):
                    with patch('app.services.vector_lifecycle.BASE_DIR', base_dir):
                        result = remove_vectors_for_deleted_files(
                            vectorstore_path="chroma_db",
                            embedding_model="test-model"
                        )
            
            assert result['files_checked'] == 1
            assert result['files_deleted'] == 1
            assert len(result['deleted_sources']) == 1
            assert 'deleted_file.txt' in result['deleted_sources']
            # Verify deletion was called
            assert mock_collection.delete.called
    
    def test_remove_dry_run(self):
        """Test dry run mode doesn't delete vectors."""
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            vectorstore_dir = base_dir / "chroma_db"
            vectorstore_dir.mkdir()
            
            mock_vectorstore = Mock()
            mock_collection = Mock()
            mock_vectorstore._collection = mock_collection
            mock_vectorstore.get.return_value = {
                'metadatas': [{'source': 'deleted_file.txt'}]
            }
            
            with patch('app.services.vector_lifecycle.create_embeddings') as mock_embeddings:
                with patch('app.services.vector_lifecycle.Chroma', return_value=mock_vectorstore):
                    with patch('app.services.vector_lifecycle.BASE_DIR', base_dir):
                        result = remove_vectors_for_deleted_files(
                            vectorstore_path="chroma_db",
                            embedding_model="test-model",
                            dry_run=True
                        )
            
            assert result['files_deleted'] == 0
            assert len(result['deleted_sources']) == 1
            # Verify deletion was NOT called
            assert not mock_collection.delete.called
    
    def test_remove_vectorstore_not_exists(self):
        """Test handling when vectorstore doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            non_existent = base_dir / "nonexistent_vectorstore"
            
            with patch('app.services.vector_lifecycle.create_embeddings') as mock_embeddings:
                with patch('app.services.vector_lifecycle.BASE_DIR', base_dir):
                    result = remove_vectors_for_deleted_files(
                        vectorstore_path=str(non_existent)
                    )
            
            assert result['files_checked'] == 0
            assert result['files_deleted'] == 0
    
    def test_remove_error_loading_vectorstore(self):
        """Test error handling when vectorstore fails to load."""
        with patch('app.services.vector_lifecycle.create_embeddings', side_effect=Exception("Load error")):
            result = remove_vectors_for_deleted_files()
        
        assert result['files_checked'] == 0
        assert result['files_deleted'] == 0


class TestUpdateVectorsForModifiedFiles:
    """Tests for update_vectors_for_modified_files function."""
    
    def test_update_no_modifications(self):
        """Test update when no files are modified."""
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            vectorstore_dir = base_dir / "chroma_db"
            vectorstore_dir.mkdir()
            
            test_file = base_dir / "test.txt"
            test_file.write_text("content")
            
            file_hash = hashlib.sha256(b"content").hexdigest()
            
            mock_vectorstore = Mock()
            mock_vectorstore.get.side_effect = [
                # First call: get_all_vectorstore_sources
                {'metadatas': [{'source': 'test.txt'}]},
                # Second call: checking hash for test.txt
                {'metadatas': [{'file_hash': file_hash}]}
            ]
            
            with patch('app.services.vector_lifecycle.create_embeddings') as mock_embeddings:
                with patch('app.services.vector_lifecycle.Chroma', return_value=mock_vectorstore):
                    with patch('app.services.vector_lifecycle.BASE_DIR', base_dir):
                        result = update_vectors_for_modified_files(
                            vectorstore_path="chroma_db",
                            embedding_model="test-model"
                        )
            
            assert result['files_checked'] == 1
            assert result['files_updated'] == 0
            assert result['files_unchanged'] == 1
    
    def test_update_modified_file(self):
        """Test update of modified file."""
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            vectorstore_dir = base_dir / "chroma_db"
            vectorstore_dir.mkdir()
            
            test_file = base_dir / "modified.txt"
            test_file.write_text("new content")
            
            old_hash = "oldhash123"
            
            mock_vectorstore = Mock()
            mock_collection = Mock()
            mock_vectorstore._collection = mock_collection
            mock_vectorstore.get.side_effect = [
                # get_all_vectorstore_sources
                {'metadatas': [{'source': 'modified.txt'}]},
                # checking hash
                {'metadatas': [{'file_hash': old_hash}]}
            ]
            mock_vectorstore.add_documents = Mock()
            
            with patch('app.services.vector_lifecycle.create_embeddings') as mock_embeddings:
                with patch('app.services.vector_lifecycle.Chroma', return_value=mock_vectorstore):
                    with patch('app.services.vector_lifecycle.load_document_content') as mock_load:
                        with patch('app.services.vector_lifecycle.BASE_DIR', base_dir):
                            # Mock document loading
                            from langchain_core.documents import Document
                            mock_load.return_value = [Document(page_content="new content", metadata={})]
                            
                            result = update_vectors_for_modified_files(
                                vectorstore_path="chroma_db",
                                embedding_model="test-model"
                            )
            
            assert result['files_checked'] == 1
            assert result['files_updated'] == 1
            assert 'modified.txt' in result['updated_sources']
            # Verify old vectors were deleted
            assert mock_collection.delete.called
            # Verify new vectors were added
            assert mock_vectorstore.add_documents.called
    
    def test_update_file_without_hash(self):
        """Test update of file that has no stored hash."""
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            vectorstore_dir = base_dir / "chroma_db"
            vectorstore_dir.mkdir()
            
            test_file = base_dir / "no_hash.txt"
            test_file.write_text("content")
            
            mock_vectorstore = Mock()
            mock_collection = Mock()
            mock_vectorstore._collection = mock_collection
            mock_vectorstore.get.side_effect = [
                # get_all_vectorstore_sources
                {'metadatas': [{'source': 'no_hash.txt'}]},
                # checking hash (no hash stored)
                {'metadatas': [{}]}
            ]
            mock_vectorstore.add_documents = Mock()
            
            with patch('app.services.vector_lifecycle.create_embeddings') as mock_embeddings:
                with patch('app.services.vector_lifecycle.Chroma', return_value=mock_vectorstore):
                    with patch('app.services.vector_lifecycle.load_document_content') as mock_load:
                        with patch('app.services.vector_lifecycle.BASE_DIR', base_dir):
                            from langchain_core.documents import Document
                            mock_load.return_value = [Document(page_content="content", metadata={})]
                            
                            result = update_vectors_for_modified_files(
                                vectorstore_path="chroma_db",
                                embedding_model="test-model"
                            )
            
            assert result['files_updated'] == 1
            assert 'no_hash.txt' in result['updated_sources']
    
    def test_update_dry_run(self):
        """Test dry run mode doesn't update vectors."""
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            vectorstore_dir = base_dir / "chroma_db"
            vectorstore_dir.mkdir()
            
            test_file = base_dir / "modified.txt"
            test_file.write_text("content")
            
            mock_vectorstore = Mock()
            mock_vectorstore.get.side_effect = [
                {'metadatas': [{'source': 'modified.txt'}]},
                {'metadatas': [{'file_hash': 'oldhash'}]}
            ]
            
            with patch('app.services.vector_lifecycle.create_embeddings') as mock_embeddings:
                with patch('app.services.vector_lifecycle.Chroma', return_value=mock_vectorstore):
                    with patch('app.services.vector_lifecycle.BASE_DIR', base_dir):
                        result = update_vectors_for_modified_files(
                            vectorstore_path="chroma_db",
                            embedding_model="test-model",
                            dry_run=True
                        )
            
            assert result['files_updated'] == 0
            assert 'modified.txt' in result['updated_sources']
            # Verify no actual updates were made
            assert not hasattr(mock_vectorstore, 'add_documents') or not mock_vectorstore.add_documents.called
    
    def test_update_vectorstore_not_exists(self):
        """Test handling when vectorstore doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            non_existent = base_dir / "nonexistent"
            
            with patch('app.services.vector_lifecycle.create_embeddings') as mock_embeddings:
                with patch('app.services.vector_lifecycle.BASE_DIR', base_dir):
                    result = update_vectors_for_modified_files(
                        vectorstore_path=str(non_existent)
                    )
            
            assert result['files_checked'] == 0
            assert result['files_updated'] == 0


class TestPerformFullMaintenance:
    """Tests for perform_full_maintenance function."""
    
    def test_full_maintenance_success(self):
        """Test successful full maintenance."""
        with patch('app.services.vector_lifecycle.remove_vectors_for_deleted_files') as mock_cleanup:
            with patch('app.services.vector_lifecycle.update_vectors_for_modified_files') as mock_update:
                mock_cleanup.return_value = {
                    'files_checked': 5,
                    'files_deleted': 1,
                    'files_remaining': 4,
                    'deleted_sources': ['deleted.txt']
                }
                mock_update.return_value = {
                    'files_checked': 4,
                    'files_updated': 2,
                    'files_unchanged': 2,
                    'updated_sources': ['file1.txt', 'file2.txt']
                }
                
                result = perform_full_maintenance()
        
        assert 'cleanup' in result
        assert 'update' in result
        assert 'timestamp' in result
        assert result['cleanup']['files_deleted'] == 1
        assert result['update']['files_updated'] == 2
        # Verify timestamp is ISO format
        datetime.fromisoformat(result['timestamp'])
    
    def test_full_maintenance_with_parameters(self):
        """Test full maintenance with custom parameters."""
        with patch('app.services.vector_lifecycle.remove_vectors_for_deleted_files') as mock_cleanup:
            with patch('app.services.vector_lifecycle.update_vectors_for_modified_files') as mock_update:
                mock_cleanup.return_value = {'files_checked': 0, 'files_deleted': 0, 'files_remaining': 0, 'deleted_sources': []}
                mock_update.return_value = {'files_checked': 0, 'files_updated': 0, 'files_unchanged': 0, 'updated_sources': []}
                
                result = perform_full_maintenance(
                    vectorstore_path="/custom/path",
                    collection_name="custom_collection",
                    embedding_model="custom-model",
                    dry_run=True
                )
        
        # Verify parameters were passed through
        mock_cleanup.assert_called_once_with(
            vectorstore_path="/custom/path",
            collection_name="custom_collection",
            embedding_model="custom-model",
            dry_run=True
        )
        mock_update.assert_called_once_with(
            vectorstore_path="/custom/path",
            collection_name="custom_collection",
            embedding_model="custom-model",
            dry_run=True
        )
    
    def test_full_maintenance_dry_run(self):
        """Test full maintenance in dry run mode."""
        with patch('app.services.vector_lifecycle.remove_vectors_for_deleted_files') as mock_cleanup:
            with patch('app.services.vector_lifecycle.update_vectors_for_modified_files') as mock_update:
                mock_cleanup.return_value = {'files_checked': 3, 'files_deleted': 0, 'files_remaining': 3, 'deleted_sources': ['file.txt']}
                mock_update.return_value = {'files_checked': 3, 'files_updated': 0, 'files_unchanged': 3, 'updated_sources': ['file.txt']}
                
                result = perform_full_maintenance(dry_run=True)
        
        # In dry run, files are identified but not actually deleted/updated
        assert result['cleanup']['files_deleted'] == 0
        assert result['update']['files_updated'] == 0
