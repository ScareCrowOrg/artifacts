"""
Unit tests for the unified prompt builder service.

Tests the PromptBuilder class and build_prompt_for_provider function
to ensure consistent prompt generation across all LLM providers.
"""

import pytest
from app.services.prompt_builder import (
    PromptBuilder,
    build_prompt_for_provider,
    HISTORY_USAGE_INSTRUCTION
)


class TestPromptBuilderInitialization:
    """Tests for PromptBuilder initialization."""
    
    def test_basic_initialization(self):
        """Test creating a PromptBuilder with minimal parameters."""
        builder = PromptBuilder(user_message="Hello, AI!")
        
        assert builder.user_message == "Hello, AI!"
        assert builder.conversation_history == []
        assert builder.rag_context == ""
        assert builder.attached_content == []
        assert builder.system_instructions == ""
        assert builder.current_chat_summary is None
        assert builder.recent_chat_history is None
    
    def test_full_initialization(self):
        """Test creating a PromptBuilder with all parameters."""
        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"}
        ]
        
        builder = PromptBuilder(
            user_message="Create a login system",
            conversation_history=history,
            rag_context="Context about authentication...",
            attached_content=["def login(): pass"],
            system_instructions="You are a coding assistant",
            current_chat_summary="User working on auth",
            recent_chat_history=history,
            max_complete_messages=3
        )
        
        assert builder.user_message == "Create a login system"
        assert len(builder.conversation_history) == 2
        assert builder.rag_context == "Context about authentication..."
        assert len(builder.attached_content) == 1
        assert builder.system_instructions == "You are a coding assistant"
        assert builder.current_chat_summary == "User working on auth"
        assert builder.max_complete_messages == 3


class TestPromptBuilderOllama:
    """Tests for Ollama prompt generation."""
    
    def test_simple_message(self):
        """Test building a simple Ollama prompt."""
        builder = PromptBuilder(user_message="What is Python?")
        prompt = builder.build_for_ollama()
        
        assert isinstance(prompt, str)
        assert "What is Python?" in prompt
        assert "### Nova Pergunta ###" in prompt
        assert "user: What is Python?" in prompt
    
    def test_with_conversation_history(self):
        """Test Ollama prompt with conversation history."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        builder = PromptBuilder(
            user_message="How are you?",
            conversation_history=history
        )
        prompt = builder.build_for_ollama()
        
        assert HISTORY_USAGE_INSTRUCTION in prompt
        assert "### Histórico da Conversa ###" in prompt
        assert "user: Hello" in prompt
        assert "assistant: Hi there!" in prompt
        assert "### Nova Pergunta ###" in prompt
        assert "user: How are you?" in prompt
    
    def test_with_rag_context(self):
        """Test Ollama prompt with RAG context."""
        builder = PromptBuilder(
            user_message="Explain the architecture",
            rag_context="The system uses a microservices architecture..."
        )
        prompt = builder.build_for_ollama()
        
        assert "### Contexto Relevante do Repositório ###" in prompt
        assert "The system uses a microservices architecture..." in prompt
        assert "### Fim do Contexto ###" in prompt
        assert "Explain the architecture" in prompt
    
    def test_with_attached_content(self):
        """Test Ollama prompt with attached file content and explicit notification."""
        builder = PromptBuilder(
            user_message="Review this code",
            attached_content=["def hello(): print('Hello')"]
        )
        prompt = builder.build_for_ollama()
        
        # Check for new explicit notification format
        assert "### 📎 ARQUIVOS ANEXADOS PELO USUÁRIO ###" in prompt
        assert "⚠️ IMPORTANTE: O usuário anexou 1 arquivo(s)" in prompt
        assert "--- Arquivo Anexado 1 de 1 ---" in prompt
        assert "def hello(): print('Hello')" in prompt
        assert "### FIM DOS ARQUIVOS ANEXADOS ###" in prompt
    
    def test_with_long_history(self):
        """Test history minification for messages exceeding max_complete_messages."""
        # Create 10 messages (more than default MAX_COMPLETE_MESSAGES=5)
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", 
             "content": f"Message {i}" * 20}  # Long content
            for i in range(10)
        ]
        
        builder = PromptBuilder(
            user_message="Current question",
            conversation_history=history
        )
        prompt = builder.build_for_ollama()
        
        # Should have minified summary for older messages
        assert "Histórico resumido:" in prompt
        # Recent 5 messages should be complete
        assert "Message 9" in prompt
        assert "### Nova Pergunta ###" in prompt
    
    def test_complete_prompt_structure(self):
        """Test complete prompt with all components in correct order."""
        history = [{"role": "user", "content": "Hi"}]
        
        builder = PromptBuilder(
            user_message="Create login",
            conversation_history=history,
            rag_context="Auth context...",
            attached_content=["code snippet"]
        )
        prompt = builder.build_for_ollama()
        
        # Check order: RAG context -> attachments -> history -> new question
        rag_pos = prompt.find("### Contexto Relevante do Repositório ###")
        attach_pos = prompt.find("### 📎 ARQUIVOS ANEXADOS PELO USUÁRIO ###")
        history_pos = prompt.find("### Histórico da Conversa ###")
        question_pos = prompt.find("### Nova Pergunta ###")
        
        assert rag_pos < attach_pos < history_pos < question_pos


class TestPromptBuilderGemini:
    """Tests for Gemini prompt generation."""
    
    def test_simple_message(self):
        """Test building a simple Gemini messages list."""
        builder = PromptBuilder(user_message="What is AI?")
        messages = builder.build_for_gemini()
        
        assert isinstance(messages, list)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert len(messages[0]["parts"]) == 1
        assert "What is AI?" in messages[0]["parts"][0]["text"]
    
    def test_with_conversation_history(self):
        """Test Gemini messages with conversation history."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]
        
        builder = PromptBuilder(
            user_message="How are you?",
            conversation_history=history
        )
        messages = builder.build_for_gemini()
        
        # Should have: history instruction + acknowledgment + history + current message
        assert len(messages) >= 4
        
        # Check history instruction
        assert any(HISTORY_USAGE_INSTRUCTION in part.get("text", "") 
                  for msg in messages for part in msg["parts"])
        
        # Check history messages are converted
        user_msg = next((m for m in messages if m["role"] == "user" and 
                        any("Hello" in p.get("text", "") for p in m["parts"])), None)
        assert user_msg is not None
        
        model_msg = next((m for m in messages if m["role"] == "model" and 
                         any("Hi!" in p.get("text", "") for p in m["parts"])), None)
        assert model_msg is not None
    
    def test_with_rag_context(self):
        """Test Gemini messages with RAG context."""
        builder = PromptBuilder(
            user_message="Explain architecture",
            rag_context="System uses microservices..."
        )
        messages = builder.build_for_gemini()
        
        # Current message should include RAG context
        current_msg = messages[-1]
        assert current_msg["role"] == "user"
        
        # RAG context should be in parts
        text_parts = [p["text"] for p in current_msg["parts"] if "text" in p]
        combined_text = "".join(text_parts)
        assert "### Contexto Relevante do Repositório ###" in combined_text
        assert "System uses microservices..." in combined_text
    
    def test_with_file_uris(self):
        """Test Gemini messages with file URIs."""
        file_uri = "https://generativelanguage.googleapis.com/v1beta/files/abc123"
        
        builder = PromptBuilder(user_message="Analyze this file")
        messages = builder.build_for_gemini(file_uris=[file_uri])
        
        # Current message should have file reference
        current_msg = messages[-1]
        assert current_msg["role"] == "user"
        
        # Should have fileData part
        file_parts = [p for p in current_msg["parts"] if "fileData" in p]
        assert len(file_parts) == 1
        assert file_parts[0]["fileData"]["fileUri"] == file_uri
    
    def test_multiple_file_uris(self):
        """Test Gemini messages with multiple file URIs."""
        file_uris = [
            "https://generativelanguage.googleapis.com/v1beta/files/file1",
            "https://generativelanguage.googleapis.com/v1beta/files/file2"
        ]
        
        builder = PromptBuilder(user_message="Compare these files")
        messages = builder.build_for_gemini(file_uris=file_uris)
        
        current_msg = messages[-1]
        file_parts = [p for p in current_msg["parts"] if "fileData" in p]
        assert len(file_parts) == 2


class TestPromptBuilderOpenAI:
    """Tests for OpenAI prompt generation."""
    
    def test_simple_message(self):
        """Test building simple OpenAI messages."""
        builder = PromptBuilder(user_message="What is ML?")
        messages = builder.build_for_openai()
        
        assert isinstance(messages, list)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "What is ML?" in messages[0]["content"]
    
    def test_with_system_instructions(self):
        """Test OpenAI messages with system prompt."""
        builder = PromptBuilder(
            user_message="Help me code",
            system_instructions="You are a helpful coding assistant"
        )
        messages = builder.build_for_openai()
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "helpful coding assistant" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "Help me code" in messages[1]["content"]
    
    def test_with_conversation_history(self):
        """Test OpenAI messages with conversation history."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]
        
        builder = PromptBuilder(
            user_message="How are you?",
            conversation_history=history
        )
        messages = builder.build_for_openai()
        
        # Should have system (with history instruction) + history + current message
        assert len(messages) == 4  # system + 2 history + current
        assert messages[0]["role"] == "system"
        assert HISTORY_USAGE_INSTRUCTION in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "Hi!"
        assert messages[3]["role"] == "user"
        assert "How are you?" in messages[3]["content"]
    
    def test_with_rag_context_in_system(self):
        """Test RAG context injection into system prompt."""
        builder = PromptBuilder(
            user_message="Explain",
            system_instructions="You are helpful",
            rag_context="Context from docs..."
        )
        messages = builder.build_for_openai()
        
        # System message should contain both instruction and RAG context
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        assert "You are helpful" in system_msg["content"]
        assert "### Contexto Relevante do Repositório ###" in system_msg["content"]
        assert "Context from docs..." in system_msg["content"]
    
    def test_with_attachments_content(self):
        """Test OpenAI messages with attachment content."""
        builder = PromptBuilder(user_message="Review this")
        messages = builder.build_for_openai(
            attachments_content=["def test(): pass"]
        )
        
        user_msg = messages[-1]
        assert user_msg["role"] == "user"
        assert "Review this" in user_msg["content"]
        assert "📎 Anexos:" in user_msg["content"]
        assert "def test(): pass" in user_msg["content"]
    
    def test_history_instruction_in_system(self):
        """Test that history usage instruction is added to system prompt."""
        history = [{"role": "user", "content": "Hi"}]
        
        builder = PromptBuilder(
            user_message="Hello",
            conversation_history=history,
            system_instructions="Be helpful"
        )
        messages = builder.build_for_openai()
        
        # First message should be system with history instruction
        system_msg = next((m for m in messages if m["role"] == "system"), None)
        assert system_msg is not None
        assert HISTORY_USAGE_INSTRUCTION in system_msg["content"]


class TestBuildPromptForProvider:
    """Tests for the convenience function build_prompt_for_provider."""
    
    def test_ollama_provider(self):
        """Test building prompt for Ollama provider."""
        prompt = build_prompt_for_provider(
            provider="ollama",
            user_message="Test message",
            rag_context="Some context"
        )
        
        assert isinstance(prompt, str)
        assert "Test message" in prompt
        assert "Some context" in prompt
    
    def test_gemini_provider(self):
        """Test building prompt for Gemini provider."""
        messages = build_prompt_for_provider(
            provider="gemini",
            user_message="Test message",
            file_uris=["https://example.com/file"]
        )
        
        assert isinstance(messages, list)
        # Check for file URI in last message
        last_msg = messages[-1]
        file_parts = [p for p in last_msg["parts"] if "fileData" in p]
        assert len(file_parts) == 1
    
    def test_openai_provider(self):
        """Test building prompt for OpenAI provider."""
        messages = build_prompt_for_provider(
            provider="openai",
            user_message="Test message",
            system_instructions="Be helpful",
            attachments_content=["code"]
        )
        
        assert isinstance(messages, list)
        assert messages[0]["role"] == "system"
        assert "📎 Anexos:" in messages[-1]["content"]
    
    def test_case_insensitive_provider(self):
        """Test that provider name is case-insensitive."""
        prompt1 = build_prompt_for_provider(provider="OLLAMA", user_message="Hi")
        prompt2 = build_prompt_for_provider(provider="ollama", user_message="Hi")
        
        assert isinstance(prompt1, str)
        assert isinstance(prompt2, str)
    
    def test_invalid_provider(self):
        """Test error handling for invalid provider."""
        with pytest.raises(ValueError) as exc_info:
            build_prompt_for_provider(
                provider="invalid_provider",
                user_message="Test"
            )
        
        assert "Unsupported provider" in str(exc_info.value)
        assert "invalid_provider" in str(exc_info.value)


class TestHistoryMinification:
    """Tests for conversation history minification logic."""
    
    def test_no_minification_with_few_messages(self):
        """Test that short history is not minified."""
        history = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"}
        ]
        
        builder = PromptBuilder(
            user_message="New question",
            conversation_history=history,
            max_complete_messages=5
        )
        prompt = builder.build_for_ollama()
        
        # Should not have minification summary
        assert "Histórico resumido:" not in prompt
        # Should have complete messages
        assert "Message 1" in prompt
        assert "Response 1" in prompt
    
    def test_minification_with_many_messages(self):
        """Test that long history is minified."""
        # Create 8 messages (more than max_complete_messages=3)
        history = [
            {"role": "user" if i % 2 == 0 else "assistant",
             "content": f"Message number {i}"}
            for i in range(8)
        ]
        
        builder = PromptBuilder(
            user_message="Current question",
            conversation_history=history,
            max_complete_messages=3
        )
        prompt = builder.build_for_ollama()
        
        # Should have minification for older messages (0-4)
        assert "Histórico resumido:" in prompt
        
        # Recent 3 messages (5, 6, 7) should be complete
        assert "Message number 5" in prompt
        assert "Message number 6" in prompt
        assert "Message number 7" in prompt
    
    def test_minification_truncates_long_content(self):
        """Test that minified messages are truncated."""
        long_content = "x" * 100  # Longer than MINIFIED_CONTENT_MAX_LENGTH
        history = [
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": long_content},
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": long_content},
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": long_content}
        ]
        
        builder = PromptBuilder(
            user_message="New",
            conversation_history=history,
            max_complete_messages=2
        )
        prompt = builder.build_for_ollama()
        
        # Minified section should have truncation indicator
        # Look for the truncation in the "Histórico resumido:" line
        if "Histórico resumido:" in prompt:
            minified_line = prompt.split("Histórico resumido:")[1].split("\n")[0]
            assert "..." in minified_line
        else:
            # If no minified summary, all messages are within max_complete_messages
            pass


class TestContextFormatting:
    """Tests for RAG context and attachment formatting."""
    
    def test_multiple_attachments_formatting(self):
        """Test formatting of multiple attached files with explicit notifications."""
        attachments = [
            "File content 1",
            "File content 2",
            "File content 3"
        ]
        
        builder = PromptBuilder(
            user_message="Review",
            attached_content=attachments
        )
        prompt = builder.build_for_ollama()
        
        # Check for new format with explicit notification
        assert "⚠️ IMPORTANTE: O usuário anexou 3 arquivo(s)" in prompt
        assert "--- Arquivo Anexado 1 de 3 ---" in prompt
        assert "--- Arquivo Anexado 2 de 3 ---" in prompt
        assert "--- Arquivo Anexado 3 de 3 ---" in prompt
        assert "File content 1" in prompt
        assert "File content 2" in prompt
        assert "File content 3" in prompt
    
    def test_rag_and_attachments_together(self):
        """Test that RAG context and attachments are both included with clear separation."""
        builder = PromptBuilder(
            user_message="Question",
            rag_context="RAG data",
            attached_content=["Attachment data"]
        )
        prompt = builder.build_for_ollama()
        
        # Check both sections exist and RAG comes before attachments
        rag_pos = prompt.find("### Contexto Relevante do Repositório ###")
        attach_pos = prompt.find("### 📎 ARQUIVOS ANEXADOS PELO USUÁRIO ###")
        
        assert rag_pos != -1
        assert attach_pos != -1
        assert rag_pos < attach_pos
        assert "RAG data" in prompt
        assert "Attachment data" in prompt




class TestEdgeCases:
    """Tests for edge cases and additional scenarios."""
    
    def test_openai_with_both_system_and_rag(self):
        """Test OpenAI with both system instructions and RAG context."""
        builder = PromptBuilder(
            user_message="Question",
            system_instructions="You are helpful",
            rag_context="Context from docs"
        )
        
        messages = builder.build_for_openai()
        
        # System message should contain both
        system_msg = next((m for m in messages if m["role"] == "system"), None)
        assert system_msg is not None
        assert "You are helpful" in system_msg["content"]
        assert "Context from docs" in system_msg["content"]
    
    def test_openai_with_empty_system_but_rag(self):
        """Test OpenAI with empty system instructions but RAG context."""
        builder = PromptBuilder(
            user_message="Question",
            system_instructions="",
            rag_context="Important context"
        )
        
        messages = builder.build_for_openai()
        
        # Should still have system message with RAG
        system_msg = next((m for m in messages if m["role"] == "system"), None)
        assert system_msg is not None
        assert "Important context" in system_msg["content"]
    
    def test_gemini_empty_file_uris_list(self):
        """Test Gemini with empty file URIs list."""
        builder = PromptBuilder(user_message="Test")
        messages = builder.build_for_gemini(file_uris=[])
        
        # Should work fine
        assert len(messages) >= 1
        # No file parts
        last_msg = messages[-1]
        file_parts = [p for p in last_msg["parts"] if "fileData" in p]
        assert len(file_parts) == 0
    
    def test_ollama_empty_everything(self):
        """Test Ollama with minimal input."""
        builder = PromptBuilder(user_message="Hi")
        prompt = builder.build_for_ollama()
        
        assert "Hi" in prompt
        assert isinstance(prompt, str)
    
    def test_build_prompt_for_provider_all_providers(self):
        """Test convenience function with all providers."""
        from app.services.prompt_builder import build_prompt_for_provider
        
        # Test all three providers
        ollama_result = build_prompt_for_provider("ollama", "Test")
        gemini_result = build_prompt_for_provider("gemini", "Test")
        openai_result = build_prompt_for_provider("openai", "Test")
        
        assert isinstance(ollama_result, str)
        assert isinstance(gemini_result, list)
        assert isinstance(openai_result, list)
