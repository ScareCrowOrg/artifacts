"""
Test to verify that Pylint with pylint-pydantic plugin can detect invalid field access in Pydantic models.

This test file intentionally contains an error to validate that the Pylint configuration
correctly catches attempts to access non-existent fields in Pydantic models.

Expected Pylint behavior:
- Should report W0201 (attribute-defined-outside-init) or E1101 (no-member)
- Should NOT give a 10/10 score due to the intentional error

Expected pytest behavior (Pydantic v2):
- Should raise ValueError when trying to set non-existent field
"""

import sys
import os
import pytest

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.models import Cell  # pylint: disable=wrong-import-position

def test_invalid_field_access():
    """
    Test that Pydantic v2 correctly raises ValueError for invalid field access.
    
    This function intentionally tries to access 'fragmentos' (Portuguese) field
    which does not exist in the Cell model. The correct field name is 'fragments' (English).
    
    Expected: 
    - Pylint should detect this as an error (static analysis)
    - Pydantic v2 should raise ValueError at runtime
    """
    # Create a Cell instance
    cell = Cell(
        assignee_id="test-user-id",
        notebook_item_type_id="test-type-id"
    )
    
    # INTENTIONAL ERROR: Try to set 'fragmentos' which doesn't exist
    # The correct field name is 'fragments'
    # In Pydantic v2, this raises ValueError at runtime
    with pytest.raises(ValueError, match='object has no field "fragmentos"'):
        cell.fragmentos = ["test fragment 1", "test fragment 2"]  # This should trigger Pylint error

if __name__ == "__main__":
    test_invalid_field_access()
