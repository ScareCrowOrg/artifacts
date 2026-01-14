"""
Main execution logic for threejs-scene-generator-cell.

This module provides Three.js scene generation functionality using LLM services.
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the Three.js scene generator cell.
    
    This function is called when the cell is executed from the backend.
    The actual scene generation is handled via the frontend calling
    the chat API with a specialized prompt.
    
    Args:
        cell_data: Cell instance data containing 'prompt' and optional 'generatedScript'
        
    Returns:
        Dict with execution results
        
    Example:
        >>> execute_cell({"prompt": "A rotating cube", "generatedScript": "..."})
        {
            "success": True,
            "message": "Three.js scene generator cell ready",
            "prompt": "A rotating cube"
        }
    """
    prompt = cell_data.get('prompt', '')
    generated_script = cell_data.get('generatedScript', None)
    
    logger.info(f"Three.js scene generator cell executed with prompt: {prompt[:50]}...")
    
    return {
        "success": True,
        "message": "Three.js scene generator cell ready",
        "prompt": prompt,
        "has_script": generated_script is not None
    }


async def generate_threejs_from_prompt(
    prompt: str, 
    model: str = "mistral"
) -> Dict[str, Any]:
    """
    Generate Three.js scene code from a text prompt using LLM.
    
    This function can be called by the chat router or other backend services
    to generate Three.js 3D scenes.
    
    Args:
        prompt: Text description of the desired 3D scene
        model: LLM model to use for generation
        
    Returns:
        Dict with generated script or error information
        
    Example:
        >>> await generate_threejs_from_prompt("A rotating cube")
        {
            "success": True,
            "script": "// Three.js code...",
            "prompt": "A rotating cube"
        }
    """
    try:
        # Import here to avoid circular dependencies
        from backend.app.services.llm_service import LLMService
        from backend.app.models.enriched_prompt import EnrichedPrompt
        
        # Create system instruction for Three.js generation
        system_instruction = """You are an expert Three.js developer. Generate clean, functional Three.js code based on user descriptions.

IMPORTANT RULES:
1. Return ONLY the JavaScript code, no explanations or markdown
2. Code should be complete and self-contained
3. Use THREE namespace (assume Three.js is already loaded globally)
4. Create scene, camera, and renderer
5. Add proper lighting (ambient + directional)
6. Include animation loop with requestAnimationFrame
7. Handle window resize events
8. Use semantic naming for objects
9. Add comments for clarity
10. Ensure code is production-ready and follows best practices

Required structure:
- Scene setup (scene, camera, renderer)
- Lighting setup
- Geometry and materials
- Animation loop
- Resize handler

Example minimal structure:
// Scene setup
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(container.clientWidth, container.clientHeight);
container.appendChild(renderer.domElement);

// Add your 3D objects here
// ...

// Animation loop
function animate() {
    requestAnimationFrame(animate);
    // Animation logic
    renderer.render(scene, camera);
}
animate();

// Handle resize
window.addEventListener('resize', () => {
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
});
"""
        
        # Build enriched prompt
        enriched_prompt = EnrichedPrompt(
            system_instructions=system_instruction,
            user_prompt=f"Generate a Three.js 3D scene for: {prompt}",
            conversation_history=[]
        )
        
        # Initialize LLM service
        llm_service = LLMService()
        
        # Generate code using streaming (collect all chunks)
        code_parts = []
        async for chunk in llm_service.generate_code_streaming(
            enriched_prompt=enriched_prompt,
            model=model,
            temperature=0.7,
            max_tokens=3000
        ):
            if chunk.get("type") == "code":
                code_parts.append(chunk.get("content", ""))
            elif chunk.get("type") == "narrative":
                # Skip narrative, we only want the code
                continue
        
        # Combine all code parts
        script_code = "\n".join(code_parts).strip()
        
        # Basic validation - check for key Three.js elements
        required_elements = ["THREE.", "scene", "camera", "renderer"]
        if not all(elem in script_code for elem in required_elements):
            logger.warning(
                f"Generated code missing required Three.js elements: {script_code[:100]}"
            )
            return {
                "success": False,
                "error": "Failed to generate valid Three.js code. Please try a different prompt.",
                "prompt": prompt
            }
        
        logger.info(f"Successfully generated Three.js scene from prompt: {prompt[:50]}...")
        
        return {
            "success": True,
            "script": script_code,
            "prompt": prompt
        }
        
    except Exception as e:
        logger.error(f"Error generating Three.js scene: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Error generating Three.js scene: {str(e)}",
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
            "prompt": "A rotating cube",
            "generatedScript": None
        }
    
    result = execute_cell(cell_data)
    print(json.dumps(result, indent=2))
