#!/usr/bin/env python3
"""
Unit Tests for Vue.js Intelligent Chunking Strategies

Tests for Vue SFC, composable, and Pinia store chunking strategies.
"""

import pytest
from pathlib import Path
from app.workflows.vue_chunking_strategies import (
    chunk_vue_code,
    chunk_vue_sfc as _chunk_vue_sfc,
    extract_vue_blocks as _extract_vue_blocks,
    chunk_javascript_file as _chunk_javascript_file,
    infer_js_chunk_type as _infer_js_chunk_type,
    extract_code_and_comments as _extract_code_and_comments,
    extract_function_body as _extract_function_body,
    find_preceding_jsdoc as _find_preceding_jsdoc
)


class TestVueSFCChunking:
    """
    Unit tests for Vue Single File Component chunking strategy.
    
    This test suite covers:
        - Block extraction: Ensures <template>, <script>, <style> blocks are correctly extracted.
        - Script language detection: Verifies detection of TypeScript vs JavaScript.
        - Empty component handling: Confirms graceful handling of incomplete or empty SFCs.
    """
    
    def test_chunk_vue_sfc_with_all_blocks(self):
        """Test Vue SFC chunking with template, script, and style blocks."""
        content = """<template>
  <div class="container mx-auto p-4">
    <h1 class="text-2xl font-bold">{{ title }}</h1>
  </div>
</template>

<script>
export default {
  name: 'TestComponent',
  data() {
    return {
      title: 'Hello Vue'
    }
  }
}
</script>

<style scoped>
.container {
  background-color: #f5f5f5;
}
</style>
"""
        file_path = Path("/test/TestComponent.vue")
        document_id = "test_vue_001"
        
        code_chunks, doc_chunks = _chunk_vue_sfc(content, file_path, document_id)
        
        # Should produce 3 code chunks (template, script, style)
        assert len(code_chunks) == 3
        
        # Check template chunk
        template_chunk = next((c for c in code_chunks if c["metadata"]["chunk_type"] == "vue_template"), None)
        assert template_chunk is not None
        assert "container mx-auto" in template_chunk["text"]
        assert template_chunk["metadata"]["embedding_model_id"] == "deepseek-coder"
        assert template_chunk["metadata"]["target_collection"] == "scareverse_code"
        
        # Check script chunk
        script_chunk = next((c for c in code_chunks if "vue_script" in c["metadata"]["chunk_type"]), None)
        assert script_chunk is not None
        assert "export default" in script_chunk["text"]
        
        # Check style chunk
        style_chunk = next((c for c in code_chunks if "vue_style" in c["metadata"]["chunk_type"]), None)
        assert style_chunk is not None
        assert "background-color" in style_chunk["text"]
    
    def test_extract_vue_blocks(self):
        """Test Vue block extraction from SFC."""
        content = """<template>
  <div>Template content</div>
</template>

<script lang="ts" setup>
const message = 'Hello'
</script>

<style lang="scss">
.test { color: red; }
</style>
"""
        blocks = _extract_vue_blocks(content)
        
        assert 'template' in blocks
        assert 'script' in blocks
        assert 'style' in blocks
        assert blocks['script_lang'] == 'ts'
        assert blocks['style_lang'] == 'scss'
        assert blocks['script_setup'] is True
    
    def test_chunk_vue_sfc_with_typescript(self):
        """Test Vue SFC with TypeScript script."""
        content = """<template>
  <div>{{ count }}</div>
</template>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'Counter',
  data() {
    return {
      count: 0 as number
    }
  }
})
</script>
"""
        file_path = Path("/test/Counter.vue")
        document_id = "test_vue_002"
        
        code_chunks, doc_chunks = _chunk_vue_sfc(content, file_path, document_id)
        
        # Find script chunk
        script_chunk = next((c for c in code_chunks if "vue_script_ts" in c["metadata"]["chunk_type"]), None)
        assert script_chunk is not None
        assert "defineComponent" in script_chunk["text"]
    
    def test_chunk_vue_sfc_empty(self):
        """Test Vue SFC chunking with minimal content."""
        content = "<template><div></div></template>"
        file_path = Path("/test/Empty.vue")
        document_id = "test_vue_003"
        
        code_chunks, doc_chunks = _chunk_vue_sfc(content, file_path, document_id)
        
        # Should still produce chunks
        assert len(code_chunks) >= 1
        assert all(c["metadata"]["document_id"] == document_id for c in code_chunks)


class TestJavaScriptChunking:
    """
    Unit tests for JavaScript/TypeScript file chunking strategy.
    
    This test suite covers:
        - Composable extraction: Ensures exported functions (useXxx) are extracted correctly.
        - Pinia store extraction: Verifies defineStore pattern detection.
        - JSDoc extraction: Confirms JSDoc blocks are extracted for documentation.
    """
    
    def test_chunk_composable_file(self):
        """Test chunking of a Vue composable file."""
        content = """/**
 * Composable for authentication
 * 
 * @returns {Object} Auth state and methods
 */
export function useAuth() {
  const isAuthenticated = ref(false)
  
  function login() {
    isAuthenticated.value = true
  }
  
  return {
    isAuthenticated,
    login
  }
}

/**
 * Another utility function
 */
export const useUtils = () => {
  return {
    formatDate: (date) => date.toISOString()
  }
}
"""
        file_path = Path("/test/cockpit-vue/src/composables/useAuth.js")
        document_id = "test_js_001"
        
        code_chunks, doc_chunks = _chunk_javascript_file(content, file_path, document_id, 'js')
        
        # Should extract both functions
        assert len(code_chunks) >= 2
        
        # Check that JSDoc is included in code chunks
        auth_chunk = next((c for c in code_chunks if c["metadata"].get("function_name") == "useAuth"), None)
        assert auth_chunk is not None
        assert "Composable for authentication" in auth_chunk["text"]
        
        # Check doc chunks extracted
        assert len(doc_chunks) >= 2
        jsdoc_chunk = next((c for c in doc_chunks if "authentication" in c["text"]), None)
        assert jsdoc_chunk is not None
        assert jsdoc_chunk["metadata"]["target_collection"] == "scareverse_docs"
    
    def test_chunk_pinia_store(self):
        """Test chunking of a Pinia store file."""
        content = """import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * Chat Store
 * 
 * Manages chat-related state and actions for the ChatIA component.
 * 
 * @module stores/chat
 */
export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  
  function addMessage(msg) {
    messages.value.push(msg)
  }
  
  return {
    messages,
    addMessage
  }
})
"""
        file_path = Path("/test/cockpit-vue/src/stores/chat.js")
        document_id = "test_js_002"
        
        code_chunks, doc_chunks = _chunk_javascript_file(content, file_path, document_id, 'js')
        
        # Should extract the store definition
        assert len(code_chunks) >= 1
        
        store_chunk = next((c for c in code_chunks if "pinia_store" in c["metadata"]["chunk_type"]), None)
        assert store_chunk is not None
        assert "defineStore" in store_chunk["text"]
        
        # Should extract JSDoc
        assert len(doc_chunks) >= 1
    
    def test_infer_js_chunk_type(self):
        """Test chunk type inference from file path."""
        composable_path = Path("/app/cockpit-vue/src/composables/useAuth.js")
        store_path = Path("/app/cockpit-vue/src/stores/chat.js")
        component_path = Path("/app/cockpit-vue/src/components/Header.js")
        other_path = Path("/app/utils/helpers.js")
        
        assert _infer_js_chunk_type(composable_path) == "vue_composable"
        assert _infer_js_chunk_type(store_path) == "vue_pinia_store"
        assert _infer_js_chunk_type(component_path) == "vue_component_script"
        assert _infer_js_chunk_type(other_path) == "vue_javascript"
    
    def test_extract_function_body(self):
        """Test function body extraction with brace matching."""
        content = """export function test() {
  const obj = { key: 'value' }
  if (true) {
    console.log('nested')
  }
  return obj
}

const next = 'code'
"""
        start_pos = 0
        func_body = _extract_function_body(content, start_pos)
        
        assert func_body is not None
        assert func_body.startswith("export function test()")
        assert func_body.endswith("}")
        assert "nested" in func_body
        assert "const next" not in func_body
    
    def test_extract_code_with_jsdoc(self):
        """Test extraction of code with JSDoc."""
        content = """/**
 * Test function
 * @param {string} name - User name
 */
export function greet(name) {
  return `Hello ${name}`
}
"""
        file_path = Path("/test/utils.js")
        document_id = "test_js_003"
        
        code_chunks, doc_chunks = _extract_code_and_comments(content, file_path, document_id, "vue_javascript")
        
        # Should have code chunk with JSDoc included
        assert len(code_chunks) == 1
        assert "Test function" in code_chunks[0]["text"]
        assert "export function greet" in code_chunks[0]["text"]
        
        # Should have separate doc chunk
        assert len(doc_chunks) == 1
        assert "Test function" in doc_chunks[0]["text"]
        assert doc_chunks[0]["metadata"]["target_collection"] == "scareverse_docs"


class TestVueChunkingIntegration:
    """
    Integration tests for the main chunk_vue_code function.
    """
    
    def test_chunk_vue_code_with_vue_file(self):
        """Test main entry point with .vue file."""
        content = """<template>
  <div>Test</div>
</template>

<script>
export default {
  name: 'Test'
}
</script>
"""
        file_path = Path("/test/Test.vue")
        document_id = "test_integration_001"
        
        code_chunks, doc_chunks = chunk_vue_code(content, file_path, document_id, 'vue')
        
        assert len(code_chunks) >= 2  # template + script
        assert all(c["metadata"]["embedding_model_id"] == "deepseek-coder" for c in code_chunks)
        assert all(c["metadata"]["target_collection"] == "scareverse_code" for c in code_chunks)
    
    def test_chunk_vue_code_with_js_file(self):
        """Test main entry point with .js file."""
        content = """export const useCounter = () => {
  const count = ref(0)
  return { count }
}
"""
        file_path = Path("/test/useCounter.js")
        document_id = "test_integration_002"
        
        code_chunks, doc_chunks = chunk_vue_code(content, file_path, document_id, 'js')
        
        assert len(code_chunks) >= 1
        assert code_chunks[0]["metadata"]["file_type"] == "javascript"


class TestMetadataConsistency:
    """
    Tests to ensure metadata fields are consistent across all Vue.js chunks.
    """
    
    def test_required_metadata_fields(self):
        """Test that all chunks have required metadata fields."""
        content = """<template><div>Test</div></template>
<script>export default { name: 'Test' }</script>"""
        
        file_path = Path("/test/Test.vue")
        document_id = "test_meta_001"
        
        code_chunks, doc_chunks = chunk_vue_code(content, file_path, document_id, 'vue')
        
        required_fields = [
            "document_id", "source", "file_type", "chunk_type",
            "embedding_model_id", "target_collection"
        ]
        
        for chunk in code_chunks + doc_chunks:
            assert "metadata" in chunk
            for field in required_fields:
                assert field in chunk["metadata"], f"Missing field: {field}"
    
    def test_code_chunks_target_code_collection(self):
        """Test that all code chunks target scareverse_code."""
        content = """export function test() { return true }"""
        file_path = Path("/test/test.js")
        document_id = "test_meta_002"
        
        code_chunks, doc_chunks = chunk_vue_code(content, file_path, document_id, 'js')
        
        for chunk in code_chunks:
            assert chunk["metadata"]["target_collection"] == "scareverse_code"
            assert chunk["metadata"]["embedding_model_id"] == "deepseek-coder"
    
    def test_doc_chunks_target_docs_collection(self):
        """Test that all doc chunks target scareverse_docs."""
        content = """/**
 * Test documentation
 */
export function test() { return true }
"""
        file_path = Path("/test/test.js")
        document_id = "test_meta_003"
        
        code_chunks, doc_chunks = chunk_vue_code(content, file_path, document_id, 'js')
        
        for chunk in doc_chunks:
            assert chunk["metadata"]["target_collection"] == "scareverse_docs"
            assert chunk["metadata"]["embedding_model_id"] == "mistral"
