"""
Main execution logic for svg-generator-cell.

This module provides SVG generation functionality using LLM services.
"""

from typing import Dict, Any, Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

# Minimal SVG fallback placeholder - red circle
MINIMAL_FALLBACK_SVG = '<svg viewBox="0 0 100 100" width="100" height="100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40" fill="red"/></svg>'


def _create_fallback_svg() -> str:
    """
    Create a simple red circle SVG as fallback placeholder.
    
    Returns:
        SVG code as string
    """
    return MINIMAL_FALLBACK_SVG


async def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the SVG generator cell.
    
    This function generates an SVG from a text prompt if one doesn't already exist.
    Falls back to a mock placeholder if the LLM service is unavailable.
    
    Args:
        cell_data: Cell instance data containing 'prompt' and optional 'generatedSvg'
        
    Returns:
        Dict with execution results including generated SVG
        
    Example:
        >>> await execute_cell({"prompt": "A simple circle", "generatedSvg": None})
        {
            "success": True,
            "message": "SVG generated successfully",
            "prompt": "A simple circle",
            "has_svg": True,
            "generatedSvg": "<svg>...</svg>"
        }
    """
    prompt = cell_data.get('prompt', '')
    generated_svg = cell_data.get('generatedSvg', None)
    
    logger.info(f"SVG generator cell executed with prompt: {prompt[:50]}...")
    
    # If SVG already exists, just return success
    if generated_svg:
        return {
            "success": True,
            "message": "SVG generator cell ready",
            "prompt": prompt,
            "has_svg": True,
            "generatedSvg": generated_svg
        }
    
    # If no prompt provided, return without generating
    if not prompt or not prompt.strip():
        logger.warning("No prompt provided for SVG generation")
        return {
            "success": True,
            "message": "No prompt provided",
            "prompt": prompt,
            "has_svg": False
        }
    
    # Generate SVG from prompt
    logger.info(f"Generating SVG for prompt: {prompt}")
    
    # Extract model preference if provided
    model = cell_data.get('selectedModel', 'mistral')
    
    try:
        # Call async generation function directly
        # This works because execute_cell is now async and can be called
        # from FastAPI's async context without creating a new event loop
        result = await generate_svg_from_prompt(
            prompt=prompt,
            model=model
        )
        
        if result.get("success"):
            svg_code = result.get("svg", "")
            
            logger.info("SVG generation successful")
            return {
                "success": True,
                "message": "SVG generated successfully",
                "prompt": prompt,
                "has_svg": True,
                "generatedSvg": svg_code
            }
        else:
            # Service failed, use fallback
            logger.warning(f"SVG generation failed, using fallback: {result.get('error')}")
            fallback_svg = _create_fallback_svg()
            
            return {
                "success": True,
                "message": "SVG generation failed, using fallback placeholder",
                "prompt": prompt,
                "has_svg": True,
                "generatedSvg": fallback_svg,
                "error": result.get("error"),
                "fallback": True
            }
    except Exception as e:
        # Unexpected error, use fallback
        logger.error(f"Unexpected error during SVG generation: {e}", exc_info=True)
        fallback_svg = _create_fallback_svg()
        
        return {
            "success": True,
            "message": "SVG generation error, using fallback placeholder",
            "prompt": prompt,
            "has_svg": True,
            "generatedSvg": fallback_svg,
            "error": str(e),
            "fallback": True
        }


async def generate_svg_from_prompt(prompt: str, model: str = "mistral") -> Dict[str, Any]:
    """
    Generate SVG code from a text prompt using LLM.
    
    Falls back to a placeholder if the LLM service is unavailable.
    
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
    # Try to import and use LLM service
    try:
        from app.services.llm_service import LLMService
        from app.models import EnrichedPrompt, ConversationMessage
        
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
    
    except ImportError as e:
        # Service not available in path
        logger.warning(f"LLM service not available: {e}")
        return {
            "success": False,
            "error": "LLM service not available (import failed)",
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
    
    result = asyncio.run(execute_cell(cell_data))
    print(json.dumps(result, indent=2))
