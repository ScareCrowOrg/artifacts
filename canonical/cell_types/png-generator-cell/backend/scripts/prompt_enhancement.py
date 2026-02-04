"""
Prompt enhancement utilities for PNG Generator Cell

This module provides prompt enhancement functions for 3D asset optimization,
including both static enhancement and Ollama-based orchestration.
"""

from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# System prompt for Ollama when acting as Prompt Architect
# This instructs Mistral to optimize prompts for 3D asset reconstruction (SF3D)
OLLAMA_SYSTEM_PROMPT_3D_ARCHITECT = """You are the ScareVerse Prompt Architect. Your mission is to transform simple descriptions into technical prompts for Stable Diffusion.

Objective: Generate prompts optimized for 3D asset reconstruction (Stable Fast 3D / SF3D).

Rules:
- Use flat lighting (no dramatic shadows or highlights)
- Neutral gray background (studio setup)
- Orthographic front view (centered, full object visible)
- Full body or complete object isolation
- High resolution and clear geometry
- No artistic interpretation - technical precision only

CRITICAL PROHIBITION: 
- If the user requests an OBJECT (weapon, tool, furniture, prop, item), DO NOT include humans, hands, faces, or any biological elements
- Objects must be standalone - no interaction, no context with living beings
- Focus solely on the geometric and material properties of the object itself

Output format: Return ONLY the optimized prompt string. Do not explain, do not add commentary. Just the prompt."""

# Base negative prompt keywords for 3D asset generation
# These prevent biological contamination and ensure technical precision
NEGATIVE_PROMPT_3D_ASSET_BASE = "humans, people, hands, fingers, faces, portraits, person, man, woman, child, body parts, biological elements, dramatic lighting, shadows, high contrast, depth of field, bokeh, cluttered background, side view, back view, artistic interpretation"

# Static enhancement suffixes for 3D asset mode (used in fallback)
POSITIVE_SUFFIX_3D_ASSET = ", full body, standing, centered, front view, flat lighting, studio background, neutral gray background, high resolution, orthographic view"
NEGATIVE_SUFFIX_3D_ASSET = ", shadows, dramatic lighting, high contrast, depth of field, bokeh, cluttered background, side view, back view"


def apply_static_3d_enhancement(prompt: str, negative_prompt: Optional[str] = None) -> Tuple[str, str]:
    """
    Apply static 3D asset prompt enhancements (fallback when Ollama is unavailable).
    
    This is the legacy enhancement method, used as a fallback when Ollama
    orchestration is not available.
    
    Args:
        prompt: Original user prompt
        negative_prompt: User's negative prompt (optional)
        
    Returns:
        Tuple of (enhanced_prompt, enhanced_negative_prompt)
    """
    # Use module-level constants for consistency
    enhanced_prompt = f"{prompt}{POSITIVE_SUFFIX_3D_ASSET}"
    
    # Merge negative prompts, avoiding duplicate keywords
    enhanced_negative = negative_prompt or ""
    if enhanced_negative:
        # Split both prompts into keywords, deduplicate, and rejoin
        user_keywords = [k.strip() for k in enhanced_negative.split(',')]
        suffix_keywords = [k.strip() for k in NEGATIVE_SUFFIX_3D_ASSET.lstrip(', ').split(',')]
        all_keywords = user_keywords + [k for k in suffix_keywords if k not in user_keywords]
        enhanced_negative = ', '.join(all_keywords)
    else:
        enhanced_negative = NEGATIVE_SUFFIX_3D_ASSET.lstrip(", ")
    
    return enhanced_prompt, enhanced_negative


async def enhance_prompt_with_ollama(prompt: str, negative_prompt: Optional[str] = None) -> Tuple[str, str]:
    """
    Enhance prompt using Ollama orchestration for 3D asset optimization.
    
    Falls back to static enhancement if Ollama is unavailable.
    
    Args:
        prompt: Original user prompt
        negative_prompt: User's negative prompt (optional)
        
    Returns:
        Tuple of (enhanced_prompt, enhanced_negative_prompt)
    """
    try:
        # Import Ollama service for prompt orchestration
        # NOTE: Import is conditional because this is an optional enhancement.
        # If import fails, we gracefully fall back to static enhancement.
        from app.ollama_service import chamar_ollama, verificar_ollama_disponivel
        
        # Check if Ollama is available
        ollama_available = await verificar_ollama_disponivel()
        
        if not ollama_available:
            logger.warning("Ollama not available, falling back to static 3D asset enhancement")
            return apply_static_3d_enhancement(prompt, negative_prompt)
        
        # Build the full prompt for Ollama using module-level constant
        ollama_prompt = f"""{OLLAMA_SYSTEM_PROMPT_3D_ARCHITECT}

User Description: {prompt}

Generate the optimized Stable Diffusion prompt:"""

        # Call Ollama with timeout handling
        logger.debug(f"Calling Ollama for prompt optimization - Original: {prompt[:50]}...")
        ollama_result = await chamar_ollama(ollama_prompt)
        
        # Extract the optimized prompt from Ollama response
        optimized_prompt = ollama_result.get("response", "").strip()
        
        if not optimized_prompt:
            logger.warning("Ollama returned empty response, falling back to static enhancement")
            return apply_static_3d_enhancement(prompt, negative_prompt)
        
        logger.info(f"Ollama optimization successful - Enhanced prompt length: {len(optimized_prompt)}")
        
        # Enhance negative prompt using module-level constant
        enhanced_negative = negative_prompt or ""
        if enhanced_negative:
            # Merge user negative prompt with base negative
            user_keywords = [k.strip() for k in enhanced_negative.split(',')]
            base_keywords = [k.strip() for k in NEGATIVE_PROMPT_3D_ASSET_BASE.split(',')]
            all_keywords = user_keywords + [k for k in base_keywords if k not in user_keywords]
            enhanced_negative = ', '.join(all_keywords)
        else:
            enhanced_negative = NEGATIVE_PROMPT_3D_ASSET_BASE
        
        logger.debug(f"Final enhanced negative prompt: {enhanced_negative[:100]}...")
        return optimized_prompt, enhanced_negative
        
    except Exception as e:
        logger.error(f"Error during Ollama orchestration: {e}", exc_info=True)
        logger.warning("Falling back to static 3D asset enhancement")
        return apply_static_3d_enhancement(prompt, negative_prompt)
