"""
Utility functions for content-manager-cell.
"""

import base64
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def decode_base64_binary(data_uri: str) -> Tuple[bytes, str]:
    """
    Decode Base64 data URI to binary.
    
    Args:
        data_uri: Data URI in format "data:mime/type;base64,..." or just base64 string
        
    Returns:
        Tuple of (binary_data, mime_type)
        
    Raises:
        ValueError: If data URI is invalid
    """
    if data_uri.startswith("data:"):
        # Parse data URI format: data:mime/type;base64,base64data
        try:
            header, data = data_uri.split(",", 1)
            mime_type = header.split(";")[0].replace("data:", "")
            binary = base64.b64decode(data)
            return binary, mime_type
        except Exception as e:
            raise ValueError(f"Invalid data URI format: {e}")
    else:
        # Assume plain base64 string
        try:
            binary = base64.b64decode(data_uri)
            return binary, "application/octet-stream"
        except Exception as e:
            raise ValueError(f"Invalid base64 data: {e}")


def encode_binary_to_base64(binary: bytes, mime_type: str) -> str:
    """
    Encode binary to Base64 data URI.
    
    Args:
        binary: Raw binary data
        mime_type: MIME type
        
    Returns:
        Data URI string
    """
    encoded = base64.b64encode(binary).decode('utf-8')
    return f"data:{mime_type};base64,{encoded}"


def extract_mime_type_from_filename(filename: str) -> str:
    """
    Extract MIME type from filename extension.
    
    Args:
        filename: Filename with extension
        
    Returns:
        MIME type string
    """
    extension = filename.lower().split('.')[-1]
    
    mime_types = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'svg': 'image/svg+xml',
        'webp': 'image/webp',
        'glb': 'model/gltf-binary',
        'gltf': 'model/gltf+json',
        'pdf': 'application/pdf',
        'json': 'application/json',
        'txt': 'text/plain',
    }
    
    return mime_types.get(extension, 'application/octet-stream')
