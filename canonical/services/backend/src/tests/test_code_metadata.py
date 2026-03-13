"""
Tests for Code Metadata Management Utility

Tests the reading, writing, and merging of metadata in code files
using JSDoc-style comments.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path to allow direct import
sys.path.insert(0, str(Path(__file__).parent.parent / 'app' / 'utils'))

from code_metadata import (
    CodeMetadataManager,
    mark_as_processed,
    get_unprocessed_files
)


class TestCodeMetadataManager:
    """Test suite for CodeMetadataManager."""
    
    def test_read_metadata_from_vue_file(self, tmp_path):
        """Test reading metadata from a Vue file."""
        vue_file = tmp_path / "Component.vue"
        vue_content = """/**
 * @metadata {
 *   "processed": true,
 *   "processed_date": "2025-12-10",
 *   "themes": ["frontend", "i18n"]
 * }
 */
<template>
  <div>Hello World</div>
</template>

<script setup>
import { ref } from 'vue'
const count = ref(0)
</script>
"""
        vue_file.write_text(vue_content)
        
        metadata = CodeMetadataManager.read_metadata(str(vue_file))
        
        assert metadata is not None
        assert metadata['processed'] is True
        assert metadata['processed_date'] == '2025-12-10'
        assert metadata['themes'] == ['frontend', 'i18n']
    
    def test_read_metadata_from_js_file(self, tmp_path):
        """Test reading metadata from a JavaScript file."""
        js_file = tmp_path / "module.js"
        js_content = """/**
 * @metadata {
 *   "processed": true,
 *   "modules": ["utils"]
 * }
 */
export function hello() {
  return 'Hello'
}
"""
        js_file.write_text(js_content)
        
        metadata = CodeMetadataManager.read_metadata(str(js_file))
        
        assert metadata is not None
        assert metadata['processed'] is True
        assert metadata['modules'] == ['utils']
    
    def test_read_metadata_from_ts_file(self, tmp_path):
        """Test reading metadata from a TypeScript file."""
        ts_file = tmp_path / "service.ts"
        ts_content = """/**
 * @metadata {
 *   "processed": true,
 *   "code_verified": true
 * }
 */
interface User {
  id: string
  name: string
}

export class UserService {
  getUser(id: string): User {
    return { id, name: 'Test' }
  }
}
"""
        ts_file.write_text(ts_content)
        
        metadata = CodeMetadataManager.read_metadata(str(ts_file))
        
        assert metadata is not None
        assert metadata['processed'] is True
        assert metadata['code_verified'] is True
    
    def test_read_metadata_no_metadata(self, tmp_path):
        """Test reading from file without metadata."""
        js_file = tmp_path / "clean.js"
        js_content = """export function test() {
  return true
}
"""
        js_file.write_text(js_content)
        
        metadata = CodeMetadataManager.read_metadata(str(js_file))
        
        assert metadata is None
    
    def test_write_metadata_new_file(self, tmp_path):
        """Test writing metadata to a file without existing metadata."""
        vue_file = tmp_path / "NewComponent.vue"
        vue_content = """<template>
  <div>Component</div>
</template>
"""
        vue_file.write_text(vue_content)
        
        new_metadata = {
            'processed': True,
            'processed_date': '2025-12-10',
            'themes': ['frontend']
        }
        
        success = CodeMetadataManager.write_metadata(
            str(vue_file), 
            new_metadata, 
            preserve_existing=False
        )
        
        assert success is True
        
        # Verify metadata was written
        content = vue_file.read_text()
        assert '@metadata' in content
        
        # Verify we can read it back
        read_metadata = CodeMetadataManager.read_metadata(str(vue_file))
        assert read_metadata == new_metadata
    
    def test_write_metadata_replace_existing(self, tmp_path):
        """Test replacing existing metadata."""
        js_file = tmp_path / "module.js"
        js_content = """/**
 * @metadata {
 *   "processed": false,
 *   "old_field": "value"
 * }
 */
export const data = 'test'
"""
        js_file.write_text(js_content)
        
        new_metadata = {
            'processed': True,
            'processed_date': '2025-12-10'
        }
        
        success = CodeMetadataManager.write_metadata(
            str(js_file), 
            new_metadata, 
            preserve_existing=False
        )
        
        assert success is True
        
        # Verify old metadata was replaced
        read_metadata = CodeMetadataManager.read_metadata(str(js_file))
        assert read_metadata == new_metadata
        assert 'old_field' not in read_metadata
    
    def test_merge_metadata_preserves_existing(self, tmp_path):
        """Test merging metadata preserves existing fields."""
        vue_file = tmp_path / "Component.vue"
        vue_content = """/**
 * @metadata {
 *   "processed": false,
 *   "themes": ["frontend"],
 *   "original_field": "preserved"
 * }
 */
<template><div>Test</div></template>
"""
        vue_file.write_text(vue_content)
        
        new_metadata = {
            'processed': True,
            'processed_date': '2025-12-10',
            'modules': ['cockpit-vue']
        }
        
        success = CodeMetadataManager.merge_metadata(str(vue_file), new_metadata)
        
        assert success is True
        
        # Verify merge
        read_metadata = CodeMetadataManager.read_metadata(str(vue_file))
        assert read_metadata['processed'] is True  # Updated
        assert read_metadata['processed_date'] == '2025-12-10'  # Added
        assert read_metadata['themes'] == ['frontend']  # Preserved
        assert read_metadata['original_field'] == 'preserved'  # Preserved
        assert read_metadata['modules'] == ['cockpit-vue']  # Added
    
    def test_has_metadata(self, tmp_path):
        """Test checking if file has metadata."""
        # File with metadata
        file_with = tmp_path / "with_metadata.js"
        file_with.write_text("""/**
 * @metadata { "processed": true }
 */
export const test = true
""")
        
        # File without metadata
        file_without = tmp_path / "without_metadata.js"
        file_without.write_text("export const test = true")
        
        assert CodeMetadataManager.has_metadata(str(file_with)) is True
        assert CodeMetadataManager.has_metadata(str(file_without)) is False
    
    def test_get_files_without_metadata(self, tmp_path):
        """Test finding files without metadata."""
        # Create test structure
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        
        # File with metadata
        (src_dir / "processed.vue").write_text("""/**
 * @metadata { "processed": true }
 */
<template><div>Test</div></template>
""")
        
        # Files without metadata
        (src_dir / "unprocessed1.vue").write_text("<template><div>A</div></template>")
        (src_dir / "unprocessed2.js").write_text("export const test = true")
        
        # Should be excluded (node_modules)
        node_modules = src_dir / "node_modules"
        node_modules.mkdir()
        (node_modules / "lib.js").write_text("export const lib = true")
        
        unprocessed = CodeMetadataManager.get_files_without_metadata(
            str(src_dir),
            extensions=['.vue', '.js']
        )
        
        # Convert to relative paths for easier assertion
        unprocessed_names = [Path(f).name for f in unprocessed]
        
        assert 'unprocessed1.vue' in unprocessed_names
        assert 'unprocessed2.js' in unprocessed_names
        assert 'processed.vue' not in unprocessed_names
        assert 'lib.js' not in unprocessed_names  # Excluded by pattern
    
    def test_mark_as_processed(self, tmp_path):
        """Test convenience function to mark file as processed."""
        vue_file = tmp_path / "Component.vue"
        vue_file.write_text("<template><div>Test</div></template>")
        
        success = mark_as_processed(
            str(vue_file),
            agent_name='i18n-localization-agent',
            themes=['frontend', 'i18n'],
            modules=['cockpit-vue'],
            additional_metadata={'i18n_coverage': 95}
        )
        
        assert success is True
        
        metadata = CodeMetadataManager.read_metadata(str(vue_file))
        assert metadata['processed'] is True
        assert metadata['processed_by'] == 'i18n-localization-agent'
        assert 'processed_date' in metadata
        assert metadata['themes'] == ['frontend', 'i18n']
        assert metadata['modules'] == ['cockpit-vue']
        assert metadata['i18n_coverage'] == 95
    
    def test_metadata_format_is_valid_jsdoc(self, tmp_path):
        """Test that generated metadata is valid JSDoc format."""
        js_file = tmp_path / "test.js"
        js_file.write_text("export const value = 42")
        
        metadata = {
            'processed': True,
            'nested': {
                'field': 'value'
            },
            'array': [1, 2, 3]
        }
        
        CodeMetadataManager.write_metadata(str(js_file), metadata, preserve_existing=False)
        
        content = js_file.read_text()
        
        # Check JSDoc structure
        assert content.startswith('/**')
        assert '@metadata' in content
        assert '*/' in content
        
        # Each line should have proper JSDoc formatting
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if i == 0:
                assert line.strip().startswith('/**')
            elif '@metadata' in line or '}' in line.strip()[-2:]:
                assert line.strip().startswith('*')
            elif line.strip() == '*/':
                assert True
            elif line.strip() and i < lines.index(' */'):
                assert line.strip().startswith('*'), f"Line {i} not properly formatted: {line}"
    
    def test_preserves_code_functionality(self, tmp_path):
        """Test that adding metadata doesn't break code functionality."""
        # This is a sanity check - the metadata comment shouldn't affect parsing
        vue_file = tmp_path / "Functional.vue"
        original_code = """<template>
  <div>{{ message }}</div>
</template>

<script setup>
import { ref } from 'vue'
const message = ref('Hello')
</script>

<style scoped>
div { color: blue; }
</style>
"""
        vue_file.write_text(original_code)
        
        mark_as_processed(str(vue_file), 'test-agent')
        
        new_content = vue_file.read_text()
        
        # Verify original code is still present and unchanged
        assert '<template>' in new_content
        assert "{{ message }}" in new_content
        assert '<script setup>' in new_content
        assert "const message = ref('Hello')" in new_content
        assert '<style scoped>' in new_content
        assert 'color: blue' in new_content
        
        # Verify metadata is at the top
        assert new_content.index('@metadata') < new_content.index('<template>')


class TestGetUnprocessedFiles:
    """Test suite for get_unprocessed_files convenience function."""
    
    def test_get_unprocessed_files(self, tmp_path):
        """Test getting unprocessed files."""
        src = tmp_path / "src"
        src.mkdir()
        
        # Create mix of processed and unprocessed
        (src / "processed.vue").write_text("""/**
 * @metadata { "processed": true }
 */
<template><div>A</div></template>
""")
        (src / "unprocessed.vue").write_text("<template><div>B</div></template>")
        (src / "unprocessed.js").write_text("export const test = 1")
        
        unprocessed = get_unprocessed_files(str(src))
        
        assert len(unprocessed) == 2
        names = [Path(f).name for f in unprocessed]
        assert 'unprocessed.vue' in names
        assert 'unprocessed.js' in names
        assert 'processed.vue' not in names


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
