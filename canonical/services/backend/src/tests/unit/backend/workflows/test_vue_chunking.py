#!/usr/bin/env python3
"""
Unit Tests for Vue.js Chunking Strategies

Tests for app/workflows/vue_chunking_strategies.py covering:
- Vue SFC (Single File Component) parsing
- JavaScript/TypeScript chunking
- JSDoc extraction
- Composables and Pinia stores
- Template, script, style block extraction

Target: 90%+ test coverage
"""

import pytest
from pathlib import Path

from app.workflows.vue_chunking_strategies import (
    chunk_vue_code,
    chunk_vue_sfc,
    extract_vue_blocks,
    chunk_javascript_file,
    infer_js_chunk_type,
    extract_code_and_comments,
    extract_function_body,
    find_preceding_jsdoc
)


class TestChunkVueCode:
    """Tests for the main chunk_vue_code function."""
    
    def testchunk_vue_sfc_file(self):
        """Test chunking a complete Vue SFC."""
        vue_content = '''<template>
  <div class="container">
    <h1>{{ title }}</h1>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const title = ref('Hello')
</script>

<style scoped>
.container {
  padding: 20px;
}
</style>
'''
        code_chunks, doc_chunks = chunk_vue_code(
            vue_content,
            Path('/app/components/Hello.vue'),
            'test_vue_001',
            'vue'
        )
        
        assert len(code_chunks) >= 2  # At least template and script
        chunk_types = [c['metadata']['chunk_type'] for c in code_chunks]
        assert 'vue_template' in chunk_types
        assert any('vue_script' in ct for ct in chunk_types)
    
    def test_chunk_vue_file_typescript(self):
        """Test chunking Vue file with TypeScript."""
        vue_content = '''<template>
  <div>TypeScript Component</div>
</template>

<script lang="ts" setup>
interface Props {
  name: string
}
const props = defineProps<Props>()
</script>
'''
        code_chunks, doc_chunks = chunk_vue_code(
            vue_content,
            Path('/app/components/TSComponent.vue'),
            'test_vue_002',
            'vue'
        )
        
        assert len(code_chunks) >= 1
        # Should detect TypeScript
        script_chunks = [c for c in code_chunks if 'script' in c['metadata']['chunk_type']]
        assert len(script_chunks) > 0
    
    def testchunk_javascript_file(self):
        """Test chunking JavaScript composable file."""
        js_content = '''/**
 * Authentication composable
 */
export function useAuth() {
    const isAuthenticated = ref(false)
    return { isAuthenticated }
}
'''
        code_chunks, doc_chunks = chunk_vue_code(
            js_content,
            Path('/app/composables/useAuth.js'),
            'test_js_001',
            'js'
        )
        
        assert len(code_chunks) >= 1
        assert len(doc_chunks) >= 0  # May extract JSDoc
    
    def test_chunk_unsupported_file_type(self):
        """Test chunking unsupported file type falls back to full file."""
        content = "Some random content"
        code_chunks, doc_chunks = chunk_vue_code(
            content,
            Path('/app/file.xyz'),
            'test_unsupported_001',
            'xyz'
        )
        
        # Should create a single full file chunk
        assert len(code_chunks) == 1
        assert code_chunks[0]['metadata']['chunk_type'] == 'full_file'


class TestExtractVueBlocks:
    """Tests for Vue SFC block extraction."""
    
    def test_extract_all_blocks(self):
        """Test extracting template, script, and style."""
        vue_content = '''<template>
  <div>Content</div>
</template>

<script>
export default { name: 'Test' }
</script>

<style>
div { color: red; }
</style>
'''
        blocks = extract_vue_blocks(vue_content)
        
        assert 'template' in blocks
        assert 'script' in blocks
        assert 'style' in blocks
        assert '<div>Content</div>' in blocks['template']
    
    def test_extract_script_setup(self):
        """Test detecting <script setup> attribute."""
        vue_content = '<script setup>\nconst x = 1\n</script>'
        blocks = extract_vue_blocks(vue_content)
        
        assert 'script' in blocks
        assert blocks.get('script_setup') is True
    
    def test_extract_script_lang_ts(self):
        """Test detecting TypeScript in script tag."""
        vue_content = '<script lang="ts">\nconst x: number = 1\n</script>'
        blocks = extract_vue_blocks(vue_content)
        
        assert blocks.get('script_lang') == 'ts'
    
    def test_extract_style_lang_scss(self):
        """Test detecting SCSS in style tag."""
        vue_content = '<style lang="scss">\n$color: red;\n</style>'
        blocks = extract_vue_blocks(vue_content)
        
        assert blocks.get('style_lang') == 'scss'
    
    def test_extract_no_blocks(self):
        """Test handling Vue file with no blocks."""
        vue_content = 'Just plain text'
        blocks = extract_vue_blocks(vue_content)
        
        assert 'template' not in blocks
        assert 'script' not in blocks
        assert 'style' not in blocks
    
    def test_extract_multiline_blocks(self):
        """Test extracting blocks with complex multiline content."""
        vue_content = '''<template>
  <div>
    <span>Line 1</span>
    <span>Line 2</span>
  </div>
</template>

<script>
export default {
  data() {
    return {
      items: []
    }
  }
}
</script>
'''
        blocks = extract_vue_blocks(vue_content)
        
        assert 'Line 1' in blocks['template']
        assert 'Line 2' in blocks['template']
        assert 'data()' in blocks['script']


class TestChunkJavaScriptFile:
    """Tests for JavaScript/TypeScript file chunking."""
    
    def test_chunk_composable_file(self):
        """Test chunking a composable function."""
        js_content = '''export function useCounter() {
    const count = ref(0)
    const increment = () => count.value++
    return { count, increment }
}
'''
        code_chunks, doc_chunks = chunk_javascript_file(
            js_content,
            Path('/app/composables/useCounter.js'),
            'test_comp_001',
            'js'
        )
        
        assert len(code_chunks) >= 1
        assert 'useCounter' in code_chunks[0]['text']
    
    def test_chunk_pinia_store(self):
        """Test chunking a Pinia store definition."""
        js_content = '''export const useAuthStore = defineStore('auth', {
    state: () => ({ user: null }),
    actions: {
        login() { /* login logic */ }
    }
})
'''
        code_chunks, doc_chunks = chunk_javascript_file(
            js_content,
            Path('/app/stores/auth.js'),
            'test_store_001',
            'js'
        )
        
        assert len(code_chunks) >= 1
        assert 'useAuthStore' in code_chunks[0]['text']


class TestInferJSChunkType:
    """Tests for JavaScript chunk type inference."""
    
    def test_infer_composable(self):
        """Test identifying composable files."""
        path = Path('/app/composables/useAuth.js')
        chunk_type = infer_js_chunk_type(path)
        assert chunk_type == 'vue_composable'
    
    def test_infer_store(self):
        """Test identifying store files."""
        path = Path('/app/stores/chat.js')
        chunk_type = infer_js_chunk_type(path)
        assert chunk_type == 'vue_pinia_store'
    
    def test_infer_component_script(self):
        """Test identifying component script files."""
        path = Path('/app/components/Header.js')
        chunk_type = infer_js_chunk_type(path)
        assert chunk_type == 'vue_component_script'
    
    def test_infer_generic_javascript(self):
        """Test identifying generic JavaScript files."""
        path = Path('/app/utils/helpers.js')
        chunk_type = infer_js_chunk_type(path)
        assert chunk_type == 'vue_javascript'


class TestExtractCodeAndComments:
    """Tests for code and JSDoc extraction."""
    
    def test_extract_function_with_jsdoc(self):
        """Test extracting function with associated JSDoc."""
        js_content = '''/**
 * Calculates sum
 * @param {number} a
 * @param {number} b
 */
export function sum(a, b) {
    return a + b
}
'''
        code_chunks, doc_chunks = extract_code_and_comments(
            js_content,
            Path('/app/utils.js'),
            'test_extract_001',
            'vue_javascript'
        )
        
        assert len(code_chunks) >= 1
        assert 'sum' in code_chunks[0]['metadata']['function_name']
        assert code_chunks[0]['metadata']['has_jsdoc'] is True
        assert len(doc_chunks) >= 1
    
    def test_extract_const_arrow_function(self):
        """Test extracting const arrow function."""
        js_content = '''export const multiply = (a, b) => {
    return a * b
}
'''
        code_chunks, doc_chunks = extract_code_and_comments(
            js_content,
            Path('/app/math.js'),
            'test_extract_002',
            'vue_javascript'
        )
        
        assert len(code_chunks) >= 1
        assert 'multiply' in code_chunks[0]['metadata']['function_name']
    
    def test_extract_defineStore(self):
        """Test extracting Pinia defineStore."""
        js_content = '''export const useStore = defineStore('main', {
    state: () => ({ count: 0 })
})
'''
        code_chunks, doc_chunks = extract_code_and_comments(
            js_content,
            Path('/app/store.js'),
            'test_extract_003',
            'vue_pinia_store'
        )
        
        assert len(code_chunks) >= 1
        assert 'useStore' in code_chunks[0]['metadata']['function_name']


class TestExtractFunctionBody:
    """Tests for function body extraction with brace matching."""
    
    def test_extract_simple_function(self):
        """Test extracting simple function body."""
        content = 'function test() { return 42; }'
        start_pos = 0
        body = extract_function_body(content, start_pos)
        
        assert body is not None
        assert 'return 42' in body
    
    def test_extract_nested_braces(self):
        """Test extracting function with nested braces."""
        content = 'function test() { if (true) { return 1; } return 0; }'
        start_pos = 0
        body = extract_function_body(content, start_pos)
        
        assert body is not None
        assert 'if (true)' in body
    
    def test_extract_with_strings(self):
        """Test extracting function with strings containing braces."""
        content = '''function test() { const msg = "Hello {world}"; return msg; }'''
        start_pos = 0
        body = extract_function_body(content, start_pos)
        
        assert body is not None
        assert 'Hello {world}' in body
    
    def test_extract_no_opening_brace(self):
        """Test handling code without opening brace."""
        content = 'const x = 5'
        start_pos = 0
        body = extract_function_body(content, start_pos)
        
        assert body is None
    
    def test_extract_unmatched_braces(self):
        """Test handling unmatched braces."""
        content = 'function test() { return 42;'
        start_pos = 0
        body = extract_function_body(content, start_pos)
        
        # Should return None if can't find matching brace
        assert body is None


class TestFindPrecedingJSDoc:
    """Tests for finding JSDoc before functions."""
    
    def test_find_jsdoc_before_function(self):
        """Test finding JSDoc immediately before function."""
        content = '''/**
 * Test function
 */
export function test() {}
'''
        import re
        jsdoc_pattern = r'/\*\*(.+?)\*/'
        jsdoc_matches = list(re.finditer(jsdoc_pattern, content, re.DOTALL))
        func_start = content.index('export function')
        
        jsdoc = find_preceding_jsdoc(content, func_start, jsdoc_matches)
        
        assert jsdoc is not None
        assert 'Test function' in jsdoc
    
    def test_no_jsdoc_before_function(self):
        """Test function without preceding JSDoc."""
        content = 'export function test() {}'
        import re
        jsdoc_pattern = r'/\*\*(.+?)\*/'
        jsdoc_matches = list(re.finditer(jsdoc_pattern, content, re.DOTALL))
        func_start = 0
        
        jsdoc = find_preceding_jsdoc(content, func_start, jsdoc_matches)
        
        assert jsdoc is None
    
    def test_jsdoc_too_far_before_function(self):
        """Test JSDoc that's too far before function."""
        # Create content with JSDoc more than 500 chars before function
        content = '/**\n * Some comment\n */\n' + (' ' * 600) + '\nexport function test() {}'
        import re
        jsdoc_pattern = r'/\*\*(.+?)\*/'
        jsdoc_matches = list(re.finditer(jsdoc_pattern, content, re.DOTALL))
        func_start = content.index('export function')
        
        jsdoc = find_preceding_jsdoc(content, func_start, jsdoc_matches)
        
        # Should not find JSDoc that's more than 500 chars away
        assert jsdoc is None


class TestVueChunkingIntegration:
    """Integration tests for Vue chunking."""
    
    def test_complete_vue_app_component(self):
        """Test chunking a complete Vue app component."""
        vue_content = '''<template>
  <div id="app" class="bg-gray-100 min-h-screen">
    <HeaderComponent />
    <main>
      <slot />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import HeaderComponent from './Header.vue'

const appReady = ref(false)

onMounted(() => {
  appReady.value = true
})
</script>

<style scoped>
#app {
  font-family: Avenir, sans-serif;
}
</style>
'''
        code_chunks, doc_chunks = chunk_vue_code(
            vue_content,
            Path('/app/App.vue'),
            'app_component',
            'vue'
        )
        
        # Should have template, script, and style chunks
        assert len(code_chunks) >= 3
        
        # Check all block types are present
        chunk_types = {c['metadata']['chunk_type'] for c in code_chunks}
        assert 'vue_template' in chunk_types
        assert any('vue_script' in ct for ct in chunk_types)
        assert any('vue_style' in ct for ct in chunk_types)
    
    def test_composable_with_full_documentation(self):
        """Test chunking composable with comprehensive JSDoc."""
        js_content = '''/**
 * User authentication composable
 * 
 * Provides user authentication state and methods
 * @returns {Object} Authentication state and methods
 */
export function useAuth() {
    const user = ref(null)
    
    /**
     * Login user
     * @param {string} email - User email
     * @param {string} password - User password
     */
    async function login(email, password) {
        // Login logic here
    }
    
    return { user, login }
}
'''
        code_chunks, doc_chunks = chunk_javascript_file(
            js_content,
            Path('/composables/useAuth.js'),
            'auth_composable',
            'js'
        )
        
        # Should extract the main function
        assert len(code_chunks) >= 1
        # Should extract JSDoc
        assert len(doc_chunks) >= 1
        
        # Check metadata
        main_chunk = code_chunks[0]
        assert main_chunk['metadata']['function_name'] == 'useAuth'
        assert main_chunk['metadata']['has_jsdoc'] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
