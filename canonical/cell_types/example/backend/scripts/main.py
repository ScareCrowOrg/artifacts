"""
Main execution logic for example cell type.

This module demonstrates a simple cell execution pattern.
"""

from typing import Dict, Any


def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the example cell.
    
    Args:
        cell_data: Cell instance data containing 'message' and 'counter'
        
    Returns:
        Dict with execution results
        
    Example:
        >>> execute_cell({"message": "Hello", "counter": 5})
        {
            "success": True,
            "output": "Hello (Count: 5)",
            "new_counter": 6
        }
    """
    message = cell_data.get('message', 'Hello from Example Cell')
    counter = cell_data.get('counter', 0)
    
    # Simple execution logic
    output = f"{message} (Count: {counter})"
    new_counter = counter + 1
    
    return {
        "success": True,
        "output": output,
        "new_counter": new_counter
    }


if __name__ == "__main__":
    # Allow standalone execution for testing
    import json
    import sys
    
    if len(sys.argv) > 1:
        cell_data = json.loads(sys.argv[1])
    else:
        cell_data = {"message": "Hello from Example Cell", "counter": 0}
    
    result = execute_cell(cell_data)
    print(json.dumps(result, indent=2))
