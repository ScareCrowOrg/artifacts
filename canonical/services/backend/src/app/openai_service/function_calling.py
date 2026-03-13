"""
Function Calling Module

This module handles OpenAI function calling (tool execution loop).
It manages the iterative process of LLM → tool execution → LLM.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.config import OPENAI_API_KEY, OPENAI_DEFAULT_MODEL

from .api_client import TOOL_RESULT_MAX_LOG_LENGTH, chamar_openai

logger = logging.getLogger(__name__)


async def processar_com_function_calling(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    tool_executor: callable,
    api_key: Optional[str] = None,
    model_id: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    max_iterations: int = 10,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Process chat with OpenAI using function calling (tool execution loop).

    This function implements the OpenAI function calling pattern:
    1. Send messages with tools to OpenAI
    2. If OpenAI requests tool execution, execute the tools
    3. Send tool results back to OpenAI
    4. Repeat until OpenAI returns a final response (or max iterations reached)

    Args:
        messages: List of conversation messages (role, content format)
        tools: List of tool definitions in OpenAI format
        tool_executor: Callable that executes tools (receives tool_name, arguments)
        api_key: API Key específica (prioritária sobre config global)
        model_id: ID do modelo OpenAI (default: OPENAI_DEFAULT_MODEL)
        temperature: Temperatura para geração (0.0 a 2.0)
        max_tokens: Número máximo de tokens na resposta
        max_iterations: Maximum number of LLM calls to prevent infinite loops
        base_url: URL base da API (prioritária sobre config global)
        timeout: Timeout em segundos (prioritário sobre config global)

    Returns:
        Dict with:
            - response: Final text response from assistant
            - tool_calls_made: List of tool calls executed
            - messages: Complete message history including tool calls

    Raises:
        ValueError: Se a API key não estiver configurada
        RuntimeError: Para outros erros durante o processamento

    Example:
        >>> def my_tool_executor(tool_name, arguments):
        ...     if tool_name == "get_weather":
        ...         return "Sunny, 72°F"
        ...     return "Unknown tool"

        >>> messages = [{"role": "user", "content": "What's the weather?"}]
        >>> tools = [{
        ...     "type": "function",
        ...     "function": {
        ...         "name": "get_weather",
        ...         "description": "Get current weather",
        ...         "parameters": {"type": "object", "properties": {}}
        ...     }
        ... }]
        >>> result = await processar_com_function_calling(
        ...     messages=messages,
        ...     tools=tools,
        ...     tool_executor=my_tool_executor,
        ...     api_key="sk-..."
        ... )
        >>> print(result["response"])  # "The weather is sunny and 72°F"
        >>> print(result["tool_calls_made"])  # [{"tool": "get_weather", ...}]
    """
    # Validate API key
    effective_api_key = api_key if api_key else OPENAI_API_KEY
    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    model = model_id or OPENAI_DEFAULT_MODEL
    conversation_messages = list(messages)  # Copy to avoid mutating input
    tool_calls_made = []

    logger.info(
        "Starting function calling with OpenAI - Model: %s, Tools: %s, Max iterations: %s",
        model, len(tools), max_iterations
    )

    for iteration in range(max_iterations):
        logger.info("Function calling iteration %s/%s", iteration + 1, max_iterations)

        # Build payload with tools
        payload = {
            "model": model,
            "messages": conversation_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools,
        }

        try:
            # Call OpenAI
            response_data = await chamar_openai(
                payload=payload,
                api_key=effective_api_key,
                base_url=base_url,
                timeout=timeout,
            )

            # Check if we got a valid response
            if not response_data or not response_data.get("choices"):
                logger.warning("Empty response from OpenAI")
                return {
                    "response": "Não foi possível obter uma resposta da OpenAI.",
                    "tool_calls_made": tool_calls_made,
                    "messages": conversation_messages,
                }

            assistant_message = response_data["choices"][0]["message"]

            # Check if assistant wants to call tools
            if assistant_message.get("tool_calls"):
                logger.info("Assistant requested %s tool call(s)", len(assistant_message['tool_calls']))

                # Add assistant message with tool calls to conversation
                conversation_messages.append(assistant_message)

                # Execute each tool call
                for tool_call in assistant_message["tool_calls"]:
                    tool_id = tool_call["id"]
                    tool_name = tool_call["function"]["name"]

                    # Parse arguments
                    try:
                        arguments_str = tool_call["function"]["arguments"]
                        arguments = json.loads(arguments_str) if arguments_str else {}
                    except json.JSONDecodeError:
                        logger.error("Failed to parse tool arguments: %s", arguments_str)
                        arguments = {}

                    logger.info("Executing tool: %s with args: %s", tool_name, arguments)

                    # Execute the tool
                    try:
                        tool_result = tool_executor(tool_name, arguments)
                        tool_result_str = str(tool_result)

                        # Log result (truncated for readability)
                        log_result = tool_result_str[:TOOL_RESULT_MAX_LOG_LENGTH]
                        if len(tool_result_str) > TOOL_RESULT_MAX_LOG_LENGTH:
                            log_result += "..."
                        logger.info("Tool %s result: %s", tool_name, log_result)

                    except Exception as e:
                        logger.error("Tool execution failed for %s: %s", tool_name, e)
                        tool_result_str = f"Error executing tool: {str(e)}"

                    # Record tool call
                    tool_calls_made.append(
                        {
                            "tool": tool_name,
                            "arguments": arguments,
                            "result": tool_result_str,
                        }
                    )

                    # Add tool response to conversation
                    conversation_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "content": tool_result_str,
                        }
                    )

                # Continue loop to get next response from assistant
                continue

            # No tool calls - assistant provided final response
            final_response = assistant_message.get("content", "")
            if not final_response:
                final_response = "Não foi possível obter uma resposta da OpenAI."

            logger.info("Function calling completed after %s iteration(s)", iteration + 1)

            # Add final assistant message to conversation
            if assistant_message not in conversation_messages:
                conversation_messages.append(assistant_message)

            return {
                "response": final_response,
                "tool_calls_made": tool_calls_made,
                "messages": conversation_messages,
            }

        except Exception as e:
            logger.error("Error during function calling iteration %s: %s", iteration + 1, e)
            raise RuntimeError(f"Erro ao processar function calling: {e}") from e

    # Max iterations reached
    logger.warning("Function calling stopped: reached maximum iterations (%s)", max_iterations)
    return {
        "response": f"Atingido o número máximo de iterações ({max_iterations}). "
        f"A resposta pode estar incompleta.",
        "tool_calls_made": tool_calls_made,
        "messages": conversation_messages,
    }
