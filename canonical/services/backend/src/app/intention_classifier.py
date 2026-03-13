"""
Intention Classifier Module

Classifies user intentions from chat messages into categories:
- conversar: free dialogue, no action
- criar: create a new cell
- executar: execute an existing cell
- refletir: review results or suggest improvements
- depurar: investigate errors or failures
"""

import logging
import re
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class IntentionType(str, Enum):
    """Types of user intentions."""

    CONVERSAR = "conversar"  # Free conversation, no action needed
    CRIAR = "criar"  # Create a new cell
    EXECUTAR = "executar"  # Execute an existing cell
    REFLETIR = "refletir"  # Review results or suggest improvements
    DEPURAR = "depurar"  # Debug errors or failures


class IntentionClassifier:
    """
    Classifies user intentions using keyword-based heuristics.

    This is a simple implementation that can be enhanced with LLM-based
    classification in the future.
    """

    # Keywords for each intention type
    KEYWORDS = {
        IntentionType.CRIAR: [
            "criar",
            "crie",
            "gerar",
            "gere",
            "novo",
            "nova",
            "adicionar",
            "adicione",
            "construir",
            "construa",
            "implementar",
            "implemente",
            "desenvolver",
            "desenvolva",
            "cell",
            "célula",
            "celula",
            "create",
            "generate",
            "add",
            "build",
            "implement",
            "develop",
        ],
        IntentionType.EXECUTAR: [
            "executar",
            "execute",
            "rodar",
            "rode",
            "correr",
            "corre",
            "processar",
            "processe",
            "iniciar",
            "inicie",
            "ativar",
            "ative",
            "run",
            "execute",
            "process",
            "start",
            "activate",
            "launch",
        ],
        IntentionType.REFLETIR: [
            "refletir",
            "reflita",
            "revisar",
            "revise",
            "analisar",
            "analise",
            "melhorar",
            "melhore",
            "otimizar",
            "otimize",
            "sugerir",
            "sugira",
            "review",
            "analyze",
            "improve",
            "optimize",
            "suggest",
            "reflect",
        ],
        IntentionType.DEPURAR: [
            "depurar",
            "depure",
            "debug",
            "debugar",
            "corrigir",
            "corrija",
            "investigar",
            "investigue",
            "erro",
            "bug",
            "falha",
            "problema",
            "fix",
            "investigate",
            "error",
            "bug",
            "failure",
            "problem",
        ],
    }

    # Phrases that strongly indicate creation intent
    CREATION_PHRASES = [
        r"pode\s+criar",
        r"cria\s+(uma|um)",
        r"gera\s+(uma|um)",
        r"fazer\s+(uma|um)\s+célula",
        r"fazer\s+(uma|um)\s+celula",
        r"nova\s+célula",
        r"nova\s+celula",
        r"novo\s+artefato",
        r"can\s+you\s+create",
        r"create\s+a\s+(new\s+)?cell",
    ]

    # Phrases that strongly indicate execution intent
    EXECUTION_PHRASES = [
        r"executar?\s+(a|o)?\s*célula",
        r"executar?\s+(a|o)?\s*celula",
        r"rodar?\s+(a|o)?\s*célula",
        r"rodar?\s+(a|o)?\s*celula",
        r"run\s+(the\s+)?cell",
        r"execute\s+(the\s+)?cell",
        r"rode\s+o\s+comando",
        r"execut(e|ar)\s+o\s+comando",
    ]

    def __init__(self):
        """Initialize the intention classifier."""

    def classify(
        self, message: str, _historico: Optional[List[Dict]] = None
    ) -> IntentionType:
        """
        Classify the intention of a user message.

        Args:
            message: The user's message
            historico: Optional conversation history for context

        Returns:
            The classified intention type
        """
        message_lower = message.lower().strip()

        # Check for strong creation phrases
        for pattern in self.CREATION_PHRASES:
            if re.search(pattern, message_lower):
                logger.info("Classified as CRIAR based on phrase pattern: %s", pattern)
                return IntentionType.CRIAR

        # Check for strong execution phrases
        for pattern in self.EXECUTION_PHRASES:
            if re.search(pattern, message_lower):
                logger.info("Classified as EXECUTAR based on phrase pattern: %s", pattern)
                return IntentionType.EXECUTAR

        # Count keyword matches for each intention type
        scores = {intention: 0 for intention in IntentionType}

        for intention, keywords in self.KEYWORDS.items():
            for keyword in keywords:
                if keyword in message_lower:
                    scores[intention] += 1

        # Find the intention with the highest score
        max_score = max(scores.values())

        # If no keywords found or scores are tied, default to CONVERSAR
        if max_score == 0:
            logger.info("No keywords found, classified as CONVERSAR")
            return IntentionType.CONVERSAR

        # Get intentions with the maximum score
        top_intentions = [
            intention for intention, score in scores.items() if score == max_score
        ]

        # If there's a tie, use priority order: CRIAR > EXECUTAR > DEPURAR > REFLETIR > CONVERSAR
        priority_order = [
            IntentionType.CRIAR,
            IntentionType.EXECUTAR,
            IntentionType.DEPURAR,
            IntentionType.REFLETIR,
            IntentionType.CONVERSAR,
        ]

        for intention in priority_order:
            if intention in top_intentions:
                logger.info("Classified as %s with score %s", intention.value, max_score)
                return intention

        # Fallback (should never reach here)
        logger.info("Fallback to CONVERSAR")
        return IntentionType.CONVERSAR

    def get_explanation(self, intention: IntentionType, _message: str) -> str:
        """
        Get a human-readable explanation of why a message was classified
        with a given intention.

        Args:
            intention: The classified intention
            message: The original message

        Returns:
            A string explaining the classification
        """
        explanations = {
            IntentionType.CONVERSAR: "Iniciar ou continuar uma conversa livre",
            IntentionType.CRIAR: "Criar uma nova célula ou artefato",
            IntentionType.EXECUTAR: "Executar uma célula ou comando existente",
            IntentionType.REFLETIR: "Revisar resultados ou sugerir melhorias",
            IntentionType.DEPURAR: "Investigar e corrigir erros ou problemas",
        }

        return explanations.get(intention, "Intenção desconhecida")
