#!/usr/bin/env python3
"""
Integration Tests for Vue.js Intelligent Chunking in Preprocessing Pipeline

Tests the full preprocessing and chunking workflow for Vue.js files.
"""

import pytest
import tempfile
from pathlib import Path
from app.workflows.preprocess_and_chunk import (
    chunk_text_intelligent
)
from app.workflows.preprocess_and_chunk.chunker import _is_frontend_js_file


class TestVuePreprocessingIntegration:
    """
    Integration tests for Vue.js files through the preprocessing pipeline.
    
    Tests the complete flow:
    1. File type detection
    2. Dispatcher routing to Vue chunking strategy
    3. Chunk generation with correct metadata
    """
    
    def test_preprocess_vue_sfc(self):
        """Test preprocessing a complete Vue SFC file."""
        content = """<template>
  <div class="container mx-auto p-4 bg-gray-100">
    <h1 class="text-2xl font-bold text-primary">{{ title }}</h1>
    <button @click="handleClick" class="btn btn-primary">
      Click me
    </button>
  </div>
</template>

<script>
/**
 * TestComponent - A sample Vue component
 * 
 * This component demonstrates Tailwind CSS integration
 * and basic Vue.js patterns.
 */
export default {
  name: 'TestComponent',
  data() {
    return {
      title: 'Hello Vue.js'
    }
  },
  methods: {
    /**
     * Handle button click event
     */
    handleClick() {
      console.log('Button clicked!')
    }
  }
}
</script>

<style scoped>
.container {
  min-height: 100vh;
}
</style>
"""
        file_path = Path("/test/cockpit-vue/src/components/TestComponent.vue")
        document_id = "test_integration_vue_001"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            content, file_path, 'vue', document_id
        )
        
        # Should produce code chunks (template, script, style)
        assert len(code_chunks) >= 3
        
        # Should produce doc chunks from JSDoc
        assert len(doc_chunks) >= 1
        
        # Verify template chunk has Tailwind classes
        template_chunk = next(
            (c for c in code_chunks if c["metadata"]["chunk_type"] == "vue_template"),
            None
        )
        assert template_chunk is not None
        assert "mx-auto" in template_chunk["text"]
        assert "text-primary" in template_chunk["text"]
        
        # Verify script chunk
        script_chunk = next(
            (c for c in code_chunks if "vue_script" in c["metadata"]["chunk_type"]),
            None
        )
        assert script_chunk is not None
        assert "TestComponent" in script_chunk["text"]
        
        # Verify doc chunks contain JSDoc
        doc_chunk = next(
            (c for c in doc_chunks if "TestComponent" in c["text"]),
            None
        )
        assert doc_chunk is not None
        assert doc_chunk["metadata"]["target_collection"] == "scareverse_docs"
    
    def test_preprocess_composable(self):
        """Test preprocessing a Vue composable file."""
        content = """import { ref, computed } from 'vue'

/**
 * Composable for managing user authentication state
 * 
 * Provides reactive authentication state and methods for login/logout.
 * 
 * @returns {Object} Authentication state and methods
 * @property {Ref<boolean>} isAuthenticated - Whether user is authenticated
 * @property {Function} login - Function to log in user
 * @property {Function} logout - Function to log out user
 */
export function useAuth() {
  const isAuthenticated = ref(false)
  const user = ref(null)
  
  /**
   * Log in a user
   * @param {string} username - Username
   * @param {string} password - Password
   */
  function login(username, password) {
    // Authentication logic here
    isAuthenticated.value = true
    user.value = { username }
  }
  
  /**
   * Log out the current user
   */
  function logout() {
    isAuthenticated.value = false
    user.value = null
  }
  
  const userDisplayName = computed(() => {
    return user.value ? user.value.username : 'Guest'
  })
  
  return {
    isAuthenticated,
    user,
    userDisplayName,
    login,
    logout
  }
}
"""
        file_path = Path("/test/cockpit-vue/src/composables/useAuth.js")
        document_id = "test_integration_composable_001"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            content, file_path, 'js', document_id
        )
        
        # Should produce code chunks for the exported function
        assert len(code_chunks) >= 1
        
        # Should produce doc chunks from JSDoc
        assert len(doc_chunks) >= 1
        
        # Verify code chunk
        auth_chunk = next(
            (c for c in code_chunks if "useAuth" in c["text"]),
            None
        )
        assert auth_chunk is not None
        assert auth_chunk["metadata"]["chunk_type"] == "vue_composable_function"
        assert auth_chunk["metadata"]["target_collection"] == "scareverse_code"
        assert auth_chunk["metadata"]["embedding_model_id"] == "deepseek-coder"
        
        # Verify doc chunk
        doc_chunk = next(
            (c for c in doc_chunks if "authentication" in c["text"].lower()),
            None
        )
        assert doc_chunk is not None
        assert doc_chunk["metadata"]["target_collection"] == "scareverse_docs"
        assert doc_chunk["metadata"]["embedding_model_id"] == "mistral"
    
    def test_preprocess_pinia_store(self):
        """Test preprocessing a Pinia store file."""
        content = """import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * Chat Store
 * 
 * Manages chat-related state and actions for the ChatIA component.
 * Replaces global events: attach-to-prompt-ia, send-to-chat
 * 
 * @module stores/chat
 */
export const useChatStore = defineStore('chat', () => {
  // State
  const messages = ref([])
  const chatComponentRef = ref(null)
  
  /**
   * Register the ChatIA component instance
   * @param {Object} componentInstance - Vue component instance
   */
  function registerChatComponent(componentInstance) {
    chatComponentRef.value = componentInstance
  }
  
  /**
   * Add a message to the chat
   * @param {string} content - Message content
   * @param {string} role - Message role (user/assistant)
   */
  function addMessage(content, role = 'user') {
    messages.value.push({
      content,
      role,
      timestamp: Date.now()
    })
  }
  
  // Computed
  const messageCount = computed(() => messages.value.length)
  
  return {
    messages,
    messageCount,
    registerChatComponent,
    addMessage
  }
})
"""
        file_path = Path("/test/cockpit-vue/src/stores/chat.js")
        document_id = "test_integration_store_001"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            content, file_path, 'js', document_id
        )
        
        # Should produce code chunks for the store definition
        assert len(code_chunks) >= 1
        
        # Should produce doc chunks from JSDoc
        assert len(doc_chunks) >= 1
        
        # Verify store chunk
        store_chunk = next(
            (c for c in code_chunks if "defineStore" in c["text"]),
            None
        )
        assert store_chunk is not None
        assert store_chunk["metadata"]["chunk_type"] == "vue_pinia_store_pinia_store"
        assert "useChatStore" in store_chunk["text"]
        
        # Verify doc chunks
        module_doc = next(
            (c for c in doc_chunks if "Chat Store" in c["text"]),
            None
        )
        assert module_doc is not None
    
    def test_is_frontend_js_file_detection(self):
        """Test detection of frontend JavaScript files."""
        # Frontend files
        assert _is_frontend_js_file(
            Path("/app/cockpit-vue/src/composables/useAuth.js"), 'js'
        ) is True
        
        assert _is_frontend_js_file(
            Path("/app/cockpit-vue/src/stores/chat.js"), 'js'
        ) is True
        
        assert _is_frontend_js_file(
            Path("/app/cockpit-vue/src/components/Header.js"), 'js'
        ) is True
        
        # Backend files (should not be detected as frontend)
        assert _is_frontend_js_file(
            Path("/app/backend/utils/helpers.js"), 'js'
        ) is False
        
        assert _is_frontend_js_file(
            Path("/app/scripts/build.js"), 'js'
        ) is False
        
        # Non-JS files
        assert _is_frontend_js_file(
            Path("/app/cockpit-vue/src/composables/useAuth.py"), 'py'
        ) is False


class TestVueChunkingEdgeCases:
    """
    Test edge cases and error handling in Vue.js chunking.
    """
    
    def test_malformed_vue_sfc(self):
        """Test handling of malformed Vue SFC."""
        content = """<template>
  <div>Unclosed template
  
<script>
export default {
  // Missing closing brace
  name: 'Broken'
"""
        file_path = Path("/test/Broken.vue")
        document_id = "test_edge_001"
        
        # Should not raise exception, should fall back gracefully
        doc_chunks, code_chunks = chunk_text_intelligent(
            content, file_path, 'vue', document_id
        )
        
        # Should produce at least one chunk (full file fallback)
        assert len(code_chunks) >= 1
    
    def test_empty_vue_file(self):
        """Test handling of empty Vue file."""
        content = ""
        file_path = Path("/test/Empty.vue")
        document_id = "test_edge_002"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            content, file_path, 'vue', document_id
        )
        
        # Should produce at least one chunk (even if empty)
        assert isinstance(code_chunks, list)
    
    def test_vue_sfc_with_setup_script(self):
        """Test Vue SFC with <script setup> syntax."""
        content = """<template>
  <div>{{ count }}</div>
  <button @click="increment">+</button>
</template>

<script setup>
import { ref } from 'vue'

const count = ref(0)

function increment() {
  count.value++
}
</script>
"""
        file_path = Path("/test/Counter.vue")
        document_id = "test_edge_003"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            content, file_path, 'vue', document_id
        )
        
        # Should successfully parse and chunk
        assert len(code_chunks) >= 2  # template + script
        
        # Verify script chunk
        script_chunk = next(
            (c for c in code_chunks if "vue_script" in c["metadata"]["chunk_type"]),
            None
        )
        assert script_chunk is not None
        assert "const count = ref(0)" in script_chunk["text"]
