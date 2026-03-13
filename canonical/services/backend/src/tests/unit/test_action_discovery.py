"""
Unit tests for Action Discovery Service

Tests the plug-and-play action discovery mechanism that scans and parses
action YAML files without manual registration.
"""

import pytest
from pathlib import Path
from app.services.action_discovery import (
    ActionDiscoveryService,
    ActionDefinition,
    ActionMetadata,
    ActionParameter
)


@pytest.fixture
def discovery_service():
    """Create a discovery service instance for testing"""
    return ActionDiscoveryService()


@pytest.fixture
def sample_actions_dir(tmp_path):
    """Create a temporary directory with sample action YAML files"""
    actions_dir = tmp_path / "actions"
    actions_dir.mkdir()
    
    # Create a sample grep action
    grep_yaml = actions_dir / "grep.yml"
    grep_yaml.write_text("""---
metadata:
  action_name: "grep"
  action_type: "JSON"
  version: "2.0.0"
  status: "active"
  labels:
    - search
    - runtime

description: |
  Search for patterns in file contents using regex.

syntax: |
  ```json
  {
    "action": "grep",
    "pattern": "search pattern",
    "path": "directory/to/search"
  }
  ```

required_fields:
  - name: "pattern"
    type: "string"
    description: "Search pattern or regex"

optional_fields:
  - name: "path"
    type: "string"
    default: "."
    description: "Directory to search"

examples:
  - name: "Find TODO comments"
    description: "Search for TODO or FIXME comments"

best_practices:
  - "Use specific patterns to reduce results"
  - "Use path wildcards for efficiency"

tips:
  - "Use anchors for line start/end"
""")
    
    # Create a sample create_cell action
    create_cell_yaml = actions_dir / "create_cell.yml"
    create_cell_yaml.write_text("""---
metadata:
  action_name: "create_cell"
  action_type: "JSON"
  version: "1.0.0"
  status: "active"
  labels:
    - notebook
    - ui

description: |
  Create a new cell in the notebook.

syntax: |
  ```json
  {
    "action": "create_cell",
    "type": "code",
    "title": "Cell Title"
  }
  ```

optional_fields:
  - name: "type"
    type: "string"
    default: "unclassified"
    description: "Cell type"
  - name: "title"
    type: "string"
    description: "Cell title"

examples:
  - name: "Create code cell"
    description: "Create a new code cell"
""")
    
    return actions_dir


class TestActionDiscoveryService:
    """Test cases for ActionDiscoveryService"""
    
    def test_init_with_default_path(self, discovery_service):
        """Test initialization with default actions directory"""
        assert discovery_service.actions_dir is not None
        assert "actions" in str(discovery_service.actions_dir)
    
    def test_init_with_custom_path(self, sample_actions_dir):
        """Test initialization with custom actions directory"""
        service = ActionDiscoveryService(sample_actions_dir)
        assert service.actions_dir == sample_actions_dir
    
    def test_load_actions(self, sample_actions_dir):
        """Test loading actions from YAML files"""
        service = ActionDiscoveryService(sample_actions_dir)
        actions = service._load_actions()
        
        assert len(actions) == 2
        assert "grep" in actions
        assert "create_cell" in actions
    
    def test_parse_action_file(self, sample_actions_dir):
        """Test parsing a single action YAML file"""
        service = ActionDiscoveryService(sample_actions_dir)
        grep_file = sample_actions_dir / "grep.yml"
        
        action_def = service._parse_action_file(grep_file)
        
        assert action_def is not None
        assert action_def.name == "grep"
        assert action_def.metadata.action_type == "JSON"
        assert action_def.metadata.version == "2.0.0"
        assert "search" in action_def.metadata.labels
        assert "runtime" in action_def.metadata.labels
        assert len(action_def.parameters) > 0
    
    def test_infer_labels(self, sample_actions_dir):
        """Test automatic label inference"""
        service = ActionDiscoveryService(sample_actions_dir)
        
        # Test search action inference
        labels = service._infer_labels("grep", {
            "description": "Search for patterns in files"
        })
        assert "search" in labels
        assert "runtime" in labels
        
        # Test file operation inference
        labels = service._infer_labels("read_file", {
            "description": "Read file contents"
        })
        assert "file-operations" in labels
        
        # Test notebook inference - need to have both name and description
        labels = service._infer_labels("create_cell", {
            "description": "Create a new cell in the notebook"
        })
        assert "notebook" in labels or "file-operations" in labels
    
    def test_build_labels_index(self, sample_actions_dir):
        """Test building labels to actions index"""
        service = ActionDiscoveryService(sample_actions_dir)
        labels_index = service._build_labels_index()
        
        assert "search" in labels_index
        assert "grep" in labels_index["search"]
        assert "notebook" in labels_index
        assert "create_cell" in labels_index["notebook"]
    
    def test_discover_all(self, sample_actions_dir):
        """Test discovering all labels and actions"""
        service = ActionDiscoveryService(sample_actions_dir)
        result = service.discover_all()
        
        assert isinstance(result, dict)
        assert "search" in result
        assert "notebook" in result
        assert "grep" in result["search"]
        assert "create_cell" in result["notebook"]
    
    def test_discover_by_label(self, sample_actions_dir):
        """Test discovering actions by label"""
        service = ActionDiscoveryService(sample_actions_dir)
        
        # Test search label
        actions = service.discover_by_label("search")
        assert len(actions) > 0
        assert any(a["name"] == "grep" for a in actions)
        
        # Test notebook label
        actions = service.discover_by_label("notebook")
        assert len(actions) > 0
        assert any(a["name"] == "create_cell" for a in actions)
        
        # Test non-existent label
        actions = service.discover_by_label("nonexistent")
        assert len(actions) == 0
    
    def test_discover_action(self, sample_actions_dir):
        """Test discovering specific action details"""
        service = ActionDiscoveryService(sample_actions_dir)
        
        # Test valid action
        action_details = service.discover_action("search", "grep")
        assert action_details is not None
        assert action_details["name"] == "grep"
        assert "description" in action_details
        assert "parameters" in action_details
        assert "metadata" in action_details
        assert len(action_details["parameters"]) > 0
        
        # Test action with wrong label
        action_details = service.discover_action("notebook", "grep")
        assert action_details is None
        
        # Test non-existent action
        action_details = service.discover_action("search", "nonexistent")
        assert action_details is None
    
    def test_refresh_cache(self, sample_actions_dir):
        """Test cache refresh functionality"""
        service = ActionDiscoveryService(sample_actions_dir)
        
        # Load actions to populate cache
        actions1 = service._load_actions()
        assert service._actions_cache is not None
        
        # Refresh cache
        service.refresh_cache()
        assert service._actions_cache is None
        assert service._labels_cache is None
        
        # Load again after refresh
        actions2 = service._load_actions()
        assert service._actions_cache is not None
    
    def test_action_with_parameters(self, sample_actions_dir):
        """Test that action parameters are correctly parsed"""
        service = ActionDiscoveryService(sample_actions_dir)
        actions = service.discover_by_label("search")
        
        grep_action = next(a for a in actions if a["name"] == "grep")
        
        # Check parameters structure
        assert "parameters" in grep_action
        params = grep_action["parameters"]
        assert len(params) > 0
        
        # Check required parameter
        pattern_param = next((p for p in params if p["name"] == "pattern"), None)
        assert pattern_param is not None
        assert pattern_param["required"] is True
        assert pattern_param["type"] == "string"
        
        # Check optional parameter
        path_param = next((p for p in params if p["name"] == "path"), None)
        assert path_param is not None
        assert path_param["required"] is False
        assert path_param["default"] == "."
    
    def test_empty_directory(self, tmp_path):
        """Test handling of empty actions directory"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        service = ActionDiscoveryService(empty_dir)
        actions = service._load_actions()
        
        assert len(actions) == 0
    
    def test_invalid_yaml_file(self, tmp_path):
        """Test handling of invalid YAML file"""
        actions_dir = tmp_path / "actions"
        actions_dir.mkdir()
        
        # Create invalid YAML
        invalid_yaml = actions_dir / "invalid.yml"
        invalid_yaml.write_text("{ invalid yaml content ][")
        
        service = ActionDiscoveryService(actions_dir)
        actions = service._load_actions()
        
        # Should skip invalid file without crashing
        assert "invalid" not in actions
    
    def test_real_actions_directory(self, discovery_service):
        """Test with real actions directory from the repository"""
        # This test uses the actual actions directory
        actions = discovery_service._load_actions()
        
        # Should find the actual action files
        assert len(actions) > 0
        
        # Check for known actions
        expected_actions = ["grep", "find", "read_file", "create_cell"]
        for action_name in expected_actions:
            if action_name in actions:
                action = actions[action_name]
                assert isinstance(action, ActionDefinition)
                assert action.name == action_name
                assert len(action.metadata.labels) > 0
