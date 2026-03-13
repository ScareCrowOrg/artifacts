"""
Unit tests for app/database/operations.py

Tests CRUD operations (insert, find, update, delete) for JSONDatabase.
Covers canonical and runtime artifacts, field queries, and error handling.
"""

import pytest
import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional


class TestInsertOperations:
    """Test document insertion operations."""
    
    def test_insert_canonical_artifact(self, test_db, sample_document_class):
        """Test inserting a canonical artifact."""
        doc = sample_document_class(
            id="doc_1",
            name="Test Document",
            description="A test document",
            value=42
        )
        
        doc_id = test_db.insert("test_collection", doc, is_canonical=True)
        
        assert doc_id == "doc_1"
        
        # Verify file was created
        doc_path = test_db.canonical_path / "test_collection" / "doc_1.json"
        assert doc_path.exists()
        
        # Verify content
        with open(doc_path, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data['id'] == "doc_1"
        assert saved_data['name'] == "Test Document"
        assert saved_data['value'] == 42
    
    def test_insert_runtime_artifact_with_user_session(self, test_db, sample_celula_class):
        """Test inserting runtime artifact with user and session."""
        cell = sample_celula_class(
            id="cel_123",
            nome="Test Cell",
            tipo="code",
            conteudo="print('hello')",
            ordem=1
        )
        
        doc_id = test_db.insert(
            "cells",
            cell,
            user_id="user_1",
            session_id="session_1",
            is_canonical=False
        )
        
        assert doc_id == "cel_123"
        
        # Verify file location
        doc_path = (
            test_db.runtime_path / "cells" / "user_1" / "session_1" / "cel_123.json"
        )
        assert doc_path.exists()
    
    def test_insert_runtime_artifact_without_user_session(self, test_db, sample_document_class):
        """Test inserting runtime artifact without user/session scoping."""
        doc = sample_document_class(
            id="global_doc",
            name="Global Document"
        )
        
        doc_id = test_db.insert("global_collection", doc, is_canonical=False)
        
        assert doc_id == "global_doc"
        
        # Should be at collection root
        doc_path = test_db.runtime_path / "global_collection" / "global_doc.json"
        assert doc_path.exists()
    
    def test_insert_without_id_raises_error(self, test_db):
        """Test that inserting document without ID raises ValueError."""
        class DocWithoutId(BaseModel):
            name: str
        
        doc = DocWithoutId(name="No ID")
        
        with pytest.raises(ValueError, match="must have an 'id' field"):
            test_db.insert("test_collection", doc, is_canonical=True)
    
    def test_insert_with_list_fields(self, test_db, sample_document_class):
        """Test inserting document with list fields."""
        doc = sample_document_class(
            id="doc_with_tags",
            name="Tagged Document",
            tags=["tag1", "tag2", "tag3"]
        )
        
        doc_id = test_db.insert("test_collection", doc, is_canonical=True)
        
        # Verify tags were saved
        doc_path = test_db.canonical_path / "test_collection" / "doc_with_tags.json"
        with open(doc_path, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data['tags'] == ["tag1", "tag2", "tag3"]
    
    def test_insert_creates_parent_directories(self, test_db, sample_document_class):
        """Test that insert creates necessary parent directories."""
        doc = sample_document_class(id="doc_nested", name="Nested")
        
        # New collection and nested user/session
        doc_id = test_db.insert(
            "new_collection",
            doc,
            user_id="new_user",
            session_id="new_session"
        )
        
        # Path should exist
        doc_path = (
            test_db.runtime_path / "new_collection" / "new_user" / 
            "new_session" / "doc_nested.json"
        )
        assert doc_path.exists()


class TestFindOneOperations:
    """Test finding single documents by ID."""
    
    def test_find_one_canonical_artifact(self, test_db, sample_document_class):
        """Test finding a canonical artifact by ID."""
        # Insert document
        doc = sample_document_class(id="find_me", name="Find Me", value=100)
        test_db.insert("test_collection", doc, is_canonical=True)
        
        # Find it
        found = test_db.find_one(
            "test_collection",
            "find_me",
            sample_document_class,
            is_canonical=True
        )
        
        assert found is not None
        assert found.id == "find_me"
        assert found.name == "Find Me"
        assert found.value == 100
    
    def test_find_one_runtime_artifact(self, test_db, sample_celula_class):
        """Test finding runtime artifact with user/session scoping."""
        # Insert
        cell = sample_celula_class(
            id="cel_find", nome="Findable", tipo="text"
        )
        test_db.insert(
            "cells", cell,
            user_id="user_1", session_id="session_1"
        )
        
        # Find
        found = test_db.find_one(
            "cells", "cel_find", sample_celula_class,
            user_id="user_1", session_id="session_1"
        )
        
        assert found is not None
        assert found.id == "cel_find"
        assert found.nome == "Findable"
    
    def test_find_one_not_found_returns_none(self, test_db, sample_document_class):
        """Test finding non-existent document returns None."""
        found = test_db.find_one(
            "test_collection",
            "nonexistent",
            sample_document_class,
            is_canonical=True
        )
        
        assert found is None
    
    def test_find_one_wrong_user_returns_none(self, test_db, sample_celula_class):
        """Test finding document with wrong user/session returns None."""
        # Insert for user_1
        cell = sample_celula_class(id="cel_private", nome="Private", tipo="code")
        test_db.insert(
            "cells", cell,
            user_id="user_1", session_id="session_1"
        )
        
        # Try to find with user_2
        found = test_db.find_one(
            "cells", "cel_private", sample_celula_class,
            user_id="user_2", session_id="session_1"
        )
        
        assert found is None
    
    def test_find_one_deserializes_to_model(self, test_db, sample_document_class):
        """Test that find_one properly deserializes to Pydantic model."""
        doc = sample_document_class(
            id="typed_doc",
            name="Typed",
            value=999,
            tags=["a", "b"]
        )
        test_db.insert("test_collection", doc, is_canonical=True)
        
        found = test_db.find_one(
            "test_collection", "typed_doc",
            sample_document_class, is_canonical=True
        )
        
        assert isinstance(found, sample_document_class)
        assert isinstance(found.value, int)
        assert isinstance(found.tags, list)


class TestUpdateOperations:
    """Test document update operations."""
    
    def test_update_canonical_artifact(self, test_db, sample_document_class):
        """Test updating a canonical artifact."""
        # Insert
        doc = sample_document_class(id="update_me", name="Original", value=10)
        test_db.insert("test_collection", doc, is_canonical=True)
        
        # Update
        success = test_db.update(
            "test_collection",
            "update_me",
            {"name": "Updated", "value": 20},
            is_canonical=True
        )
        
        assert success is True
        
        # Verify update
        updated = test_db.find_one(
            "test_collection", "update_me",
            sample_document_class, is_canonical=True
        )
        
        assert updated.name == "Updated"
        assert updated.value == 20
    
    def test_update_runtime_artifact(self, test_db, sample_celula_class):
        """Test updating runtime artifact."""
        # Insert
        cell = sample_celula_class(
            id="cel_update", nome="Before", tipo="text"
        )
        test_db.insert(
            "cells", cell,
            user_id="user_1", session_id="session_1"
        )
        
        # Update
        success = test_db.update(
            "cells",
            "cel_update",
            {"nome": "After", "tipo": "code"},
            user_id="user_1",
            session_id="session_1"
        )
        
        assert success is True
        
        # Verify
        updated = test_db.find_one(
            "cells", "cel_update", sample_celula_class,
            user_id="user_1", session_id="session_1"
        )
        
        assert updated.nome == "After"
        assert updated.tipo == "code"
    
    def test_update_nonexistent_returns_false(self, test_db):
        """Test updating non-existent document returns False."""
        success = test_db.update(
            "test_collection",
            "nonexistent",
            {"name": "New"},
            is_canonical=True
        )
        
        assert success is False
    
    def test_update_adds_timestamp(self, test_db, sample_document_class):
        """Test that update adds dataAtualizacao timestamp."""
        # Insert
        doc = sample_document_class(id="timestamped", name="Test")
        test_db.insert("test_collection", doc, is_canonical=True)
        
        # Update
        test_db.update(
            "test_collection",
            "timestamped",
            {"name": "Updated"},
            is_canonical=True
        )
        
        # Check file for timestamp (app uses Portuguese field name)
        doc_path = test_db.canonical_path / "test_collection" / "timestamped.json"
        with open(doc_path, 'r') as f:
            data = json.load(f)
        
        assert "dataAtualizacao" in data
    
    def test_update_partial_fields(self, test_db, sample_document_class):
        """Test updating only some fields preserves others."""
        # Insert
        doc = sample_document_class(
            id="partial",
            name="Original Name",
            description="Original Description",
            value=100
        )
        test_db.insert("test_collection", doc, is_canonical=True)
        
        # Update only value
        test_db.update(
            "test_collection",
            "partial",
            {"value": 200},
            is_canonical=True
        )
        
        # Verify other fields preserved
        updated = test_db.find_one(
            "test_collection", "partial",
            sample_document_class, is_canonical=True
        )
        
        assert updated.name == "Original Name"
        assert updated.description == "Original Description"
        assert updated.value == 200


class TestDeleteOperations:
    """Test document deletion operations."""
    
    def test_delete_canonical_artifact(self, test_db, sample_document_class):
        """Test deleting a canonical artifact."""
        # Insert
        doc = sample_document_class(id="delete_me", name="To Delete")
        test_db.insert("test_collection", doc, is_canonical=True)
        
        # Verify exists
        doc_path = test_db.canonical_path / "test_collection" / "delete_me.json"
        assert doc_path.exists()
        
        # Delete
        success = test_db.delete("test_collection", "delete_me", is_canonical=True)
        
        assert success is True
        assert not doc_path.exists()
    
    def test_delete_runtime_artifact(self, test_db, sample_celula_class):
        """Test deleting runtime artifact."""
        # Insert
        cell = sample_celula_class(id="cel_delete", nome="Delete", tipo="text")
        test_db.insert(
            "cells", cell,
            user_id="user_1", session_id="session_1"
        )
        
        # Delete
        success = test_db.delete(
            "cells", "cel_delete",
            user_id="user_1", session_id="session_1"
        )
        
        assert success is True
        
        # Verify gone
        found = test_db.find_one(
            "cells", "cel_delete", sample_celula_class,
            user_id="user_1", session_id="session_1"
        )
        assert found is None
    
    def test_delete_nonexistent_returns_false(self, test_db):
        """Test deleting non-existent document returns False."""
        success = test_db.delete(
            "test_collection", "nonexistent", is_canonical=True
        )
        
        assert success is False


class TestFindManyOperations:
    """Test finding multiple documents with filters."""
    
    def test_find_many_canonical_artifacts(self, test_db, sample_document_class):
        """Test finding all canonical artifacts in a collection."""
        # Insert multiple
        for i in range(5):
            doc = sample_document_class(
                id=f"doc_{i}",
                name=f"Document {i}",
                value=i * 10
            )
            test_db.insert("test_collection", doc, is_canonical=True)
        
        # Find all
        docs = test_db.find_many("test_collection", sample_document_class, is_canonical=True)
        
        assert len(docs) == 5
        assert all(isinstance(doc, sample_document_class) for doc in docs)
    
    def test_find_many_runtime_by_user(self, test_db, sample_celula_class):
        """Test finding runtime artifacts filtered by user."""
        # Insert for user_1
        for i in range(3):
            cell = sample_celula_class(
                id=f"user1_cel_{i}",
                nome=f"User1 Cell {i}",
                tipo="text"
            )
            test_db.insert(
                "cells", cell,
                user_id="user_1", session_id="session_1"
            )
        
        # Insert for user_2
        for i in range(2):
            cell = sample_celula_class(
                id=f"user2_cel_{i}",
                nome=f"User2 Cell {i}",
                tipo="code"
            )
            test_db.insert(
                "cells", cell,
                user_id="user_2", session_id="session_1"
            )
        
        # Find only user_1's
        user1_docs = test_db.find_many(
            "cells", sample_celula_class,
            user_id="user_1"
        )
        
        assert len(user1_docs) == 3
        assert all("user1" in doc.id for doc in user1_docs)
    
    def test_find_many_with_limit(self, test_db, sample_document_class):
        """Test finding documents with limit."""
        # Insert 10 documents
        for i in range(10):
            doc = sample_document_class(id=f"limited_{i}", name=f"Doc {i}")
            test_db.insert("test_collection", doc, is_canonical=True)
        
        # Find with limit
        docs = test_db.find_many(
            "test_collection",
            sample_document_class,
            is_canonical=True,
            limit=5
        )
        
        assert len(docs) == 5
    
    def test_find_many_empty_collection(self, test_db, sample_document_class):
        """Test finding from empty collection returns empty list."""
        docs = test_db.find_many(
            "empty_collection",
            sample_document_class,
            is_canonical=True
        )
        
        assert docs == []


class TestFindByFieldOperations:
    """Test finding documents by specific field values."""
    
    def test_find_by_field_exact_match(self, test_db, sample_document_class):
        """Test finding document by exact field match."""
        # Insert documents
        doc1 = sample_document_class(id="doc1", name="Unique Name", value=100)
        doc2 = sample_document_class(id="doc2", name="Other Name", value=200)
        
        test_db.insert("test_collection", doc1, is_canonical=True)
        test_db.insert("test_collection", doc2, is_canonical=True)
        
        # Find by name
        found = test_db.find_by_field(
            "test_collection",
            "name",
            "Unique Name",
            sample_document_class,
            is_canonical=True
        )
        
        assert found is not None
        assert found.id == "doc1"
        assert found.name == "Unique Name"
    
    def test_find_by_field_not_found(self, test_db, sample_document_class):
        """Test finding by field with no match returns None."""
        doc = sample_document_class(id="doc1", name="Test")
        test_db.insert("test_collection", doc, is_canonical=True)
        
        found = test_db.find_by_field(
            "test_collection",
            "name",
            "Nonexistent",
            sample_document_class,
            is_canonical=True
        )
        
        assert found is None
    
    def test_find_by_field_returns_first_match(self, test_db, sample_document_class):
        """Test that find_by_field returns first matching document."""
        # Insert multiple with same field value
        for i in range(3):
            doc = sample_document_class(
                id=f"doc{i}",
                name="Same Name",
                value=i
            )
            test_db.insert("test_collection", doc, is_canonical=True)
        
        found = test_db.find_by_field(
            "test_collection",
            "name",
            "Same Name",
            sample_document_class,
            is_canonical=True
        )
        
        assert found is not None
        assert found.name == "Same Name"


class TestFindByFieldsOperations:
    """Test finding documents by multiple field values."""
    
    def test_find_by_fields_exact_match(self, test_db, sample_document_class):
        """Test finding by multiple fields with exact match."""
        # Insert documents
        doc1 = sample_document_class(
            id="doc1", name="Test", description="Desc1", value=100
        )
        doc2 = sample_document_class(
            id="doc2", name="Test", description="Desc2", value=200
        )
        
        test_db.insert("test_collection", doc1, is_canonical=True)
        test_db.insert("test_collection", doc2, is_canonical=True)
        
        # Find by name AND description
        found = test_db.find_by_fields(
            "test_collection",
            {"name": "Test", "description": "Desc2"},
            sample_document_class,
            is_canonical=True
        )
        
        assert found is not None
        assert found.id == "doc2"
    
    def test_find_by_fields_partial_match_fails(self, test_db, sample_document_class):
        """Test that partial field match returns None."""
        doc = sample_document_class(
            id="doc1", name="Test", value=100
        )
        test_db.insert("test_collection", doc, is_canonical=True)
        
        # Search with one matching, one non-matching field
        found = test_db.find_by_fields(
            "test_collection",
            {"name": "Test", "value": 999},  # value doesn't match
            sample_document_class,
            is_canonical=True
        )
        
        assert found is None
    
    def test_find_by_fields_empty_dict_returns_first(self, test_db, sample_document_class):
        """Test finding by empty fields dict returns first document."""
        doc = sample_document_class(id="doc1", name="Test")
        test_db.insert("test_collection", doc, is_canonical=True)
        
        found = test_db.find_by_fields(
            "test_collection",
            {},
            sample_document_class,
            is_canonical=True
        )
        
        # Should return first document since all match empty criteria
        assert found is not None


class TestErrorHandling:
    """Test error handling in CRUD operations."""
    
    def test_find_many_handles_corrupted_files(self, test_db, sample_document_class):
        """Test that find_many skips corrupted JSON files."""
        # Insert valid document
        valid_doc = sample_document_class(id="valid", name="Valid")
        test_db.insert("test_collection", valid_doc, is_canonical=True)
        
        # Create corrupted JSON file
        collection_path = test_db.canonical_path / "test_collection"
        corrupted_file = collection_path / "corrupted.json"
        with open(corrupted_file, 'w') as f:
            f.write("{ invalid json }")
        
        # Should skip corrupted file and return valid ones
        docs = test_db.find_many("test_collection", sample_document_class, is_canonical=True)
        
        # Should have the valid document but skip corrupted one
        assert len(docs) == 1
        assert docs[0].id == "valid"
    
    def test_find_many_all_runtime_without_user(self, test_db, sample_document_class):
        """Test finding all runtime artifacts across all users."""
        # Insert for different users
        for user_id in ["user1", "user2"]:
            for i in range(2):
                doc = sample_document_class(
                    id=f"{user_id}_doc{i}",
                    name=f"{user_id} Doc {i}"
                )
                test_db.insert(
                    "test_collection", doc,
                    user_id=user_id, session_id="session1"
                )
        
        # Find all runtime without specifying user
        all_docs = test_db.find_many(
            "test_collection",
            sample_document_class,
            is_canonical=False
        )
        
        # Should find all documents from all users
        assert len(all_docs) == 4
    
    def test_find_by_field_handles_missing_attribute(self, test_db, sample_document_class):
        """Test find_by_field when document doesn't have the searched field."""
        doc = sample_document_class(id="doc1", name="Test")
        test_db.insert("test_collection", doc, is_canonical=True)
        
        # Search for a field that doesn't exist on all documents
        found = test_db.find_by_field(
            "test_collection",
            "nonexistent_field",
            "some_value",
            sample_document_class,
            is_canonical=True
        )
        
        assert found is None
