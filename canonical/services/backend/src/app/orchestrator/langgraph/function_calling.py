"""
Function Calling Processor

Handles OpenAI function calling for document access and tool execution.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


async def process_with_function_calling(
    mensagem: str,
    historico: List[Dict[str, str]],
    modelo: str,
    enable_runtime_tools: bool = True,
) -> str:
    """
    Process message with OpenAI function calling for document access and runtime tools.

    This method enables the LLM to request document content on-demand
    and perform runtime file operations (grep, find, read).

    Args:
        mensagem: User's message
        historico: Conversation history
        modelo: Model to use (must be an OpenAI model)
        enable_runtime_tools: Enable runtime file operation tools (grep, find, read)

    Returns:
        LLM's final response after processing function calls
    """
    from ...document_tools import execute_tool_call, get_read_document_tool_definition
    from ...openai_service import (
        processar_com_function_calling as openai_function_calling,
    )

    logger.info("Processing with function calling enabled (runtime_tools=%s)", enable_runtime_tools)

    # Build messages for OpenAI
    messages = _build_messages(historico, mensagem, enable_runtime_tools)

    # Get tools - include runtime tools if enabled
    tools = [get_read_document_tool_definition()]

    if enable_runtime_tools:
        from ...langchain_runtime_tools import get_runtime_tool_definitions

        runtime_tool_defs = get_runtime_tool_definitions()
        tools.extend(runtime_tool_defs)
        logger.info("Runtime tools added: %s", [t['function']['name'] for t in runtime_tool_defs])

    try:
        # Process with function calling
        result = await openai_function_calling(
            messages=messages,
            tools=tools,
            tool_executor=execute_tool_call,
            model_id=modelo,
            temperature=0.7,
            max_tokens=4096,
            max_iterations=5,
        )

        # Log tool calls made
        if result.get("tool_calls_made"):
            logger.info("Tool calls executed: %s", len(result['tool_calls_made']))
            for tc in result["tool_calls_made"]:
                logger.info("  - %s(%s)", tc['tool'], tc['arguments'])

        return result["response"]

    except Exception as e:
        logger.error("Error in function calling: %s", e)
        return f"Desculpe, ocorreu um erro ao processar sua solicitação: {str(e)}"


def _build_messages(
    historico: List[Dict[str, str]], mensagem: str, enable_runtime_tools: bool = True
) -> List[Dict[str, str]]:
    """
    Build messages list for OpenAI API.

    Args:
        historico: Conversation history
        mensagem: Current user message
        enable_runtime_tools: Whether runtime tools are enabled

    Returns:
        List of formatted messages
    """
    messages = []

    # Add system prompt with runtime tools capabilities
    if enable_runtime_tools:
        system_prompt = (
            "Você é o AgenteLab, assistente avançado do ScareVerse especializado em análise e desenvolvimento. "
            "Você tem acesso a ferramentas poderosas para explorar o repositório:\n\n"
            "**Ferramentas Disponíveis:**\n"
            "- `grep`: Buscar padrões de texto em arquivos (como grep Unix)\n"
            "- `find`: Buscar arquivos por padrão de nome (glob)\n"
            "- `read_file`: Ler o conteúdo de um arquivo específico\n"
            "- `list_directory`: Listar conteúdo de diretórios\n"
            "- `read_local_document`: Ler documentos anexados\n\n"
            "**Como usar as ferramentas:**\n"
            "- Use `grep` quando precisar buscar código ou texto específico. Ex: buscar 'async def' em arquivos Python.\n"
            "- Use `find` para localizar arquivos. Ex: encontrar todos os arquivos de teste.\n"
            "- Use `read_file` para ver o conteúdo completo de um arquivo.\n"
            "- Use `list_directory` para explorar a estrutura de diretórios.\n\n"
            "**Importante:** Seja proativo! Use as ferramentas para buscar informações antes de responder. "
            "Não peça ao usuário para fornecer informações que você pode obter diretamente do repositório."
        )
    else:
        system_prompt = (
            "Você é o assistente ScareVerse, especializado em ajudar desenvolvedores. "
            "Você tem acesso a documentos do projeto via a ferramenta 'read_local_document'. "
            "Quando o usuário mencionar um arquivo ou documento, use essa ferramenta para ler o conteúdo "
            "antes de responder. Exemplos de caminhos: 'docs/README.md', 'backend/app/config.py'."
        )
    messages.append({"role": "system", "content": system_prompt})

    # Add conversation history
    for msg in historico:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})

    # Add current message
    messages.append({"role": "user", "content": mensagem})

    return messages
