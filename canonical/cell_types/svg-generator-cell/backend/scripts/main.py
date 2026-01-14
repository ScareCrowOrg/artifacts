"""
Main execution logic for svg-generator-cell.

This module provides SVG generation functionality using LLM services.
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the SVG generator cell.
    
    This function is called when the cell is executed from the backend.
    For the MVP, the actual SVG generation is handled via the frontend
    calling the chat API with a specialized prompt.
    
    Args:
        cell_data: Cell instance data containing 'prompt' and optional 'generatedSvg'
        
    Returns:
        Dict with execution results
        
    Example:
        >>> execute_cell({"prompt": "A simple circle", "generatedSvg": "<svg>...</svg>"})
        {
            "success": True,
            "message": "SVG generator cell ready",
            "prompt": "A simple circle"
        }
    """
    prompt = cell_data.get('prompt', '')
    generated_svg = cell_data.get('generatedSvg', None)
    
    logger.info(f"SVG generator cell executed with prompt: {prompt[:50]}...")
    
    return {
        "success": True,
        "message": "SVG generator cell ready",
        "prompt": prompt,
        "has_svg": generated_svg is not None
    }


async def generate_svg_from_prompt(prompt: str, model: str = "mistral") -> Dict[str, Any]:
    """
    Generate SVG code from a text prompt using LLM.
    
    This function can be called by the chat router or other backend services
    to generate SVG visualizations.
    
    Args:
        prompt: Text description of the desired SVG
        model: LLM model to use for generation
        
    Returns:
        Dict with generated SVG or error information
        
    Example:
        >>> await generate_svg_from_prompt("A blue circle with radius 50")
        {
            "success": True,
            "svg": "<svg>...</svg>",
            "prompt": "A blue circle with radius 50"
        }
    """
    try:
        # Import here to avoid circular dependencies
        from ...services.llm_service import LLMService
        from ...models import EnrichedPrompt, ConversationMessage
        
        # Create system instruction for SVG generation
        system_instruction = """You are an expert SVG generator. Generate clean, valid SVG code based on user descriptions.
        
IMPORTANT RULES:
1. Return ONLY the SVG code, no explanations or markdown
2. Start with <svg> tag and end with </svg>
3. Include proper viewBox and dimensions
4. Use semantic naming for elements
5. Keep the SVG simple and readable
6. Use appropriate colors and styling
7. Ensure the SVG is self-contained and valid

Example output format:
<svg viewBox="0 0 200 200" width="200" height="200" xmlns="http://www.w3.org/2000/svg">
  <circle cx="100" cy="100" r="50" fill="blue"/>
</svg>
"""
        
        # Build enriched prompt
        enriched_prompt = EnrichedPrompt(
            system_instructions=system_instruction,
            user_prompt=f"Generate an SVG visualization for: {prompt}",
            conversation_history=[]
        )
        
        # Initialize LLM service
        llm_service = LLMService()
        
        # Generate SVG using streaming (we'll collect all chunks)
        svg_parts = []
        async for chunk in llm_service.generate_code_streaming(
            enriched_prompt=enriched_prompt,
            model=model,
            temperature=0.7,
            max_tokens=2000
        ):
            if chunk.get("type") == "code":
                svg_parts.append(chunk.get("content", ""))
            elif chunk.get("type") == "narrative":
                # Skip narrative, we only want the SVG code
                continue
        
        # Combine all SVG parts
        svg_code = "\n".join(svg_parts).strip()
        
        # Validate that we got SVG
        if not svg_code or not svg_code.startswith("<svg"):
            logger.warning(f"Generated content doesn't look like SVG: {svg_code[:100]}")
            return {
                "success": False,
                "error": "Failed to generate valid SVG. Please try a different prompt.",
                "prompt": prompt
            }
        
        logger.info(f"Successfully generated SVG from prompt: {prompt[:50]}...")
        
        return {
            "success": True,
            "svg": svg_code,
            "prompt": prompt
        }
        
    except Exception as e:
        logger.error(f"Error generating SVG: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Error generating SVG: {str(e)}",
            "prompt": prompt
        }


if __name__ == "__main__":
    # Allow standalone execution for testing
    import json
    import sys
    
    if len(sys.argv) > 1:
        cell_data = json.loads(sys.argv[1])
    else:
        cell_data = {
            "prompt": "A simple circle",
            "generatedSvg": None
        }
    
    result = execute_cell(cell_data)
    print(json.dumps(result, indent=2))
