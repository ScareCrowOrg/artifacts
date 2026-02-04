"""
Fallback utilities for PNG Generator Cell

This module provides fallback PNG generation when services are unavailable.
"""

import base64
import logging
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)

# Minimal 1x1 transparent PNG as ultra-fallback (67 bytes)
# Used when PIL is not available - smallest possible valid PNG
MINIMAL_FALLBACK_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="


def create_fallback_png() -> str:
    """
    Create a 1x1 red pixel PNG as fallback placeholder.
    
    Returns:
        Base64-encoded PNG with data URI prefix
    """
    try:
        from PIL import Image
        
        # Create 1x1 red pixel image
        img = Image.new('RGB', (1, 1), color='red')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Encode to base64 with proper prefix
        base64_data = base64.b64encode(buffer.read()).decode('utf-8')
        return f"data:image/png;base64,{base64_data}"
    except Exception as e:
        logger.error(f"Failed to create fallback PNG: {e}")
        # Ultra-minimal fallback - smallest possible PNG (1x1 transparent)
        return f"data:image/png;base64,{MINIMAL_FALLBACK_PNG}"
