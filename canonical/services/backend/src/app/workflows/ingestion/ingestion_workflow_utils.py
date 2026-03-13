#!/usr/bin/env python3
"""
Workflow Utility Functions for Document Ingestion

This module provides utility functions used by the ingestion workflow:
- URL detection and file downloading
- External script execution
- Common helper functions

These utilities are shared across different workflow nodes.
"""

import logging
import subprocess
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# URL and Download Utilities
# ============================================================================


def is_url(path: str) -> bool:
    """Check if a path is a URL."""
    return path.startswith(("http://", "https://"))


def download_from_url(url: str, output_dir: str = "/tmp") -> str:
    """
    Download a file from URL to local filesystem.

    Args:
        url: URL to download from
        output_dir: Directory to save the downloaded file

    Returns:
        Path to the downloaded file

    Raises:
        ValueError: If URL scheme is not allowed
        Exception: If download fails
    """
    # Security: Only allow http and https schemes to prevent file:/ or other unexpected schemes
    if not url.startswith(("http://", "https://")):
        raise ValueError(
            f"Invalid URL scheme. Only http:// and https:// are allowed. Got: {url}"
        )

    try:
        # Generate a unique filename
        filename = f"downloaded_{uuid.uuid4().hex}"
        output_path = Path(output_dir) / filename

        logger.info("Downloading from URL: %s", url)
        urllib.request.urlretrieve(url, str(output_path))  # nosec B310 - URL scheme validated above
        logger.info("Downloaded to: %s", output_path)

        return str(output_path)
    except Exception as e:
        logger.error("Failed to download from URL %s: %s", url, e)
        raise


# ============================================================================
# Script Execution Utilities
# ============================================================================


def run_script(script_path: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute an external Python script with provided inputs.

    Args:
        script_path: Relative path to the script from BASE_DIR
        inputs: Dictionary of input parameters for the script

    Returns:
        Dictionary containing:
        - success: Boolean indicating if execution succeeded
        - stdout: Standard output from the script
        - stderr: Standard error from the script
        - return_code: Process return code
    """
    try:
        # Get BASE_DIR from environment or use default
        from app.config import BASE_DIR

        full_script_path = BASE_DIR / script_path

        if not full_script_path.exists():
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Script not found: {full_script_path}",
                "return_code": 1,
            }

        # Build command line arguments from inputs
        cmd = ["python3", str(full_script_path)]

        for key, value in inputs.items():
            # Convert input keys to command-line flags (snake_case to kebab-case)
            flag = f"--{key.replace('_', '-')}"
            cmd.extend([flag, str(value)])

        logger.info("Executing script: %s", ' '.join(cmd))

        # Execute script
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        logger.info("Script completed with return code: %s", result.returncode)

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
        }

    except subprocess.TimeoutExpired:
        logger.error("Script execution timed out: %s", script_path)
        return {
            "success": False,
            "stdout": "",
            "stderr": "Script execution timed out after 5 minutes",
            "return_code": -1,
        }
    except Exception as e:
        logger.error("Error executing script %s: %s", script_path, e)
        return {"success": False, "stdout": "", "stderr": str(e), "return_code": -1}
