"""
Unit tests for intention_classifier_node.py

Tests the intention classification node which:
- Classifies user intentions using IntentionClassifier
- Updates state with classified intention
- Logs classification explanations

Target coverage: 90%+
"""

import pytest
from unittest.mock import Mock
from app.orchestrator.langgraph.intention_classifier_node import classifica_intencao
from app.intention_classifier import IntentionType


class TestClassificaIntencao:
    """Test intention classification node."""
    
    def test_classify_conversar_intention(self, sample_state, mock_intention_classifier):
        """Test classifying CONVERSAR intention."""
        sample_state["mensagem"] = "What is LangGraph?"
        mock_intention_classifier.classify.return_value = IntentionType.CONVERSAR
        mock_intention_classifier.get_explanation.return_value = "User wants to have a conversation"
        
        result = classifica_intencao(sample_state, mock_intention_classifier)
        
        assert result["intencao"] == IntentionType.CONVERSAR.value
        mock_intention_classifier.classify.assert_called_once_with(
            sample_state["mensagem"],
            sample_state["historico"]
        )
        mock_intention_classifier.get_explanation.assert_called_once()
    
    def test_classify_criar_intention(self, sample_state, mock_intention_classifier):
        """Test classifying CRIAR intention."""
        sample_state["mensagem"] = "Create a new cell for data analysis"
        mock_intention_classifier.classify.return_value = IntentionType.CRIAR
        
        result = classifica_intencao(sample_state, mock_intention_classifier)
        
        assert result["intencao"] == IntentionType.CRIAR.value
    
    def test_classify_executar_intention(self, sample_state, mock_intention_classifier):
        """Test classifying EXECUTAR intention."""
        sample_state["mensagem"] = "Execute cell abc123"
        mock_intention_classifier.classify.return_value = IntentionType.EXECUTAR
        
        result = classifica_intencao(sample_state, mock_intention_classifier)
        
        assert result["intencao"] == IntentionType.EXECUTAR.value
    
    def test_classify_refletir_intention(self, sample_state, mock_intention_classifier):
        """Test classifying REFLETIR intention."""
        sample_state["mensagem"] = "Analyze this code for improvements"
        mock_intention_classifier.classify.return_value = IntentionType.REFLETIR
        
        result = classifica_intencao(sample_state, mock_intention_classifier)
        
        assert result["intencao"] == IntentionType.REFLETIR.value
    
    def test_classify_depurar_intention(self, sample_state, mock_intention_classifier):
        """Test classifying DEPURAR intention."""
        sample_state["mensagem"] = "Debug this error in the code"
        mock_intention_classifier.classify.return_value = IntentionType.DEPURAR
        
        result = classifica_intencao(sample_state, mock_intention_classifier)
        
        assert result["intencao"] == IntentionType.DEPURAR.value
    
    def test_classify_with_history(self, sample_state, mock_intention_classifier):
        """Test classification with conversation history."""
        sample_state["mensagem"] = "Tell me more about that"
        sample_state["historico"] = [
            {"role": "user", "content": "What is LangGraph?"},
            {"role": "assistant", "content": "LangGraph is a framework..."}
        ]
        mock_intention_classifier.classify.return_value = IntentionType.CONVERSAR
        
        result = classifica_intencao(sample_state, mock_intention_classifier)
        
        assert result["intencao"] == IntentionType.CONVERSAR.value
        # Verify classifier was called with history
        call_args = mock_intention_classifier.classify.call_args
        assert call_args[0][1] == sample_state["historico"]
    
    def test_classify_empty_history(self, sample_state, mock_intention_classifier):
        """Test classification with empty history."""
        sample_state["historico"] = []
        mock_intention_classifier.classify.return_value = IntentionType.CONVERSAR
        
        result = classifica_intencao(sample_state, mock_intention_classifier)
        
        assert result["intencao"] == IntentionType.CONVERSAR.value
        call_args = mock_intention_classifier.classify.call_args
        assert call_args[0][1] == []
    
    def test_state_preservation(self, sample_state, mock_intention_classifier):
        """Test that other state fields are preserved."""
        sample_state["mensagem"] = "Test message"
        sample_state["custom_field"] = "custom_value"
        mock_intention_classifier.classify.return_value = IntentionType.CONVERSAR
        
        result = classifica_intencao(sample_state, mock_intention_classifier)
        
        # Original fields should be preserved
        assert result["mensagem"] == "Test message"
        assert result["custom_field"] == "custom_value"
        # New field should be added
        assert "intencao" in result
