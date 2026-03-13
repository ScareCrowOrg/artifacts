"""
Unit tests for action_executor.py

Tests the action executor node which:
- Executes actions based on classified intentions
- Creates cells for CRIAR intention
- Executes cells for EXECUTAR intention
- Updates state with action results

Target coverage: 90%+
"""

import pytest
from unittest.mock import Mock, patch
from app.orchestrator.langgraph.action_executor import (
    executa_acao,
    _executar_criacao_celula,
    _executar_celula
)
from app.intention_classifier import IntentionType


class TestExecutarCriacaoCelula:
    """Test cell creation execution."""
    
    def test_create_cell_success(self, mock_cell_tools):
        """Test successful cell creation."""
        mock_cell_tools.criar_celula_impl.return_value = {
            "success": True,
            "celula_id": "cell123",
            "tipo_celula_id": "type456",
            "estado": "pendente"
        }
        
        resultado, celula_criada = _executar_criacao_celula("user123", "Create data analysis cell")
        
        assert resultado["success"] is True
        assert resultado["celula_id"] == "cell123"
        assert celula_criada is not None
        assert celula_criada["id"] == "cell123"
        assert celula_criada["tipo"] == "type456"  # Function returns "tipo" not "type"
        assert celula_criada["estado"] == "pendente"
        
        mock_cell_tools.criar_celula_impl.assert_called_once_with(
            responsavel_id="user123",
            tipo_celula_id=None,
            dados_iniciais={"instrucao": "Create data analysis cell"}
        )
    
    def test_create_cell_failure(self, mock_cell_tools):
        """Test cell creation failure."""
        mock_cell_tools.criar_celula_impl.return_value = {
            "success": False,
            "error": "Failed to create cell"
        }
        
        resultado, celula_criada = _executar_criacao_celula("user123", "Invalid request")
        
        assert resultado["success"] is False
        assert celula_criada is None
    
    def test_create_cell_with_complex_message(self, mock_cell_tools):
        """Test cell creation with complex message."""
        mock_cell_tools.criar_celula_impl.return_value = {
            "success": True,
            "celula_id": "cell789",
            "tipo_celula_id": "type123",
            "estado": "pendente"
        }
        
        complex_message = "Create a cell for analyzing user behavior patterns in the last 30 days"
        resultado, celula_criada = _executar_criacao_celula("user456", complex_message)
        
        assert resultado["success"] is True
        assert celula_criada["id"] == "cell789"
        call_args = mock_cell_tools.criar_celula_impl.call_args
        assert call_args[1]["dados_iniciais"]["instrucao"] == complex_message


class TestExecutarCelula:
    """Test cell execution."""
    
    def test_execute_cell_request(self):
        """Test cell execution request."""
        resultado = _executar_celula("Execute cell abc123")
        
        assert resultado is not None
        assert resultado["success"] is True
        assert "message" in resultado
        assert "ID" in resultado["message"]
    
    def test_execute_cell_various_messages(self):
        """Test execution with various message formats."""
        messages = [
            "Run cell xyz789",
            "Execute the analysis",
            "Start processing cell 123"
        ]
        
        for msg in messages:
            resultado = _executar_celula(msg)
            assert resultado["success"] is True


class TestExecutaAcao:
    """Test the main action executor node."""
    
    def test_executa_acao_criar(self, sample_state, mock_cell_tools):
        """Test action execution for CRIAR intention."""
        sample_state["intencao"] = IntentionType.CRIAR.value
        sample_state["mensagem"] = "Create a new analysis cell"
        sample_state["responsavel_id"] = "user123"
        
        mock_cell_tools.criar_celula_impl.return_value = {
            "success": True,
            "celula_id": "cell123",
            "tipo_celula_id": "type456",
            "estado": "pendente"
        }
        
        result = executa_acao(sample_state)
        
        assert result["acao_realizada"] is True
        assert result["resultado_acao"] is not None
        assert result["celula_criada"] is not None
        assert result["celula_criada"]["id"] == "cell123"
    
    def test_executa_acao_executar(self, sample_state):
        """Test action execution for EXECUTAR intention."""
        sample_state["intencao"] = IntentionType.EXECUTAR.value
        sample_state["mensagem"] = "Execute cell abc123"
        
        result = executa_acao(sample_state)
        
        assert result["acao_realizada"] is True
        assert result["resultado_acao"] is not None
        assert result["resultado_acao"]["success"] is True
        assert result["celula_criada"] is None
    
    def test_executa_acao_conversar(self, sample_state):
        """Test action execution for CONVERSAR intention (no action)."""
        sample_state["intencao"] = IntentionType.CONVERSAR.value
        sample_state["mensagem"] = "What is LangGraph?"
        
        result = executa_acao(sample_state)
        
        assert result["acao_realizada"] is False
        assert result["resultado_acao"] is None
        assert result["celula_criada"] is None
    
    def test_executa_acao_refletir(self, sample_state):
        """Test action execution for REFLETIR intention (no action)."""
        sample_state["intencao"] = IntentionType.REFLETIR.value
        sample_state["mensagem"] = "Analyze this code"
        
        result = executa_acao(sample_state)
        
        assert result["acao_realizada"] is False
        assert result["resultado_acao"] is None
    
    def test_executa_acao_depurar(self, sample_state):
        """Test action execution for DEPURAR intention (no action)."""
        sample_state["intencao"] = IntentionType.DEPURAR.value
        sample_state["mensagem"] = "Debug this error"
        
        result = executa_acao(sample_state)
        
        assert result["acao_realizada"] is False
        assert result["resultado_acao"] is None
    
    def test_executa_acao_default_intention(self, sample_state):
        """Test action execution with missing intention."""
        # Don't set intencao, test default behavior
        if "intencao" in sample_state:
            del sample_state["intencao"]
        
        result = executa_acao(sample_state)
        
        # Default should be CONVERSAR which doesn't execute action
        assert result["acao_realizada"] is False
        assert result["resultado_acao"] is None
    
    def test_executa_acao_preserves_state(self, sample_state, mock_cell_tools):
        """Test that action execution preserves other state fields."""
        sample_state["intencao"] = IntentionType.CRIAR.value
        sample_state["mensagem"] = "Create cell"
        sample_state["responsavel_id"] = "user123"
        sample_state["custom_field"] = "custom_value"
        
        mock_cell_tools.criar_celula_impl.return_value = {
            "success": True,
            "celula_id": "cell123",
            "tipo_celula_id": "type456",
            "estado": "pendente"
        }
        
        result = executa_acao(sample_state)
        
        # Original fields should be preserved
        assert result["mensagem"] == "Create cell"
        assert result["responsavel_id"] == "user123"
        assert result["custom_field"] == "custom_value"
        # New fields should be added
        assert "acao_realizada" in result
        assert "resultado_acao" in result
        assert "celula_criada" in result
    
    def test_executa_acao_failed_creation(self, sample_state, mock_cell_tools):
        """Test action execution when cell creation fails."""
        sample_state["intencao"] = IntentionType.CRIAR.value
        sample_state["mensagem"] = "Create cell"
        sample_state["responsavel_id"] = "user123"
        
        mock_cell_tools.criar_celula_impl.return_value = {
            "success": False,
            "error": "Failed to create"
        }
        
        result = executa_acao(sample_state)
        
        assert result["acao_realizada"] is True  # Action was attempted
        assert result["resultado_acao"]["success"] is False
        assert result["celula_criada"] is None
