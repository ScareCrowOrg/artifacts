"""
Content Minimizer Module

Removes comments and docstrings from source code files to minimize token usage
while preserving functionality.

Supports:
- Python (.py): Remove docstrings and comments
- YAML (.yml, .yaml): Remove comment lines

Technical naming: All functions and variables in English.
"""

import ast
import logging
import re

logger = logging.getLogger(__name__)


def remove_python_comments_and_docstrings(
    code: str, preserve_structure: bool = True
) -> str:
    """
    Remove comments and docstrings from Python code to minimize token usage.

    Preserves code structure and functionality while removing non-essential documentation.
    Uses AST parsing for safe docstring removal and regex for comments.

    Args:
        code: Python source code
        preserve_structure: If True, keeps blank lines to maintain readability

    Returns:
        Python code with comments and docstrings removed

    Note:
        Falls back to original code if AST parsing fails (syntax errors).

    Example:
        >>> code = '''
        ... def hello():
        ...     \"\"\"Say hello\"\"\"
        ...     # This is a comment
        ...     print("hello")
        ... '''
        >>> cleaned = remove_python_comments_and_docstrings(code)
        >>> "Say hello" not in cleaned
        True
        >>> "print" in cleaned
        True
    """
    # First, remove single-line and inline comments
    lines = code.split("\n")
    cleaned_lines = []

    for line in lines:
        # Skip full comment lines
        stripped = line.lstrip()
        if stripped.startswith("#"):
            if preserve_structure:
                cleaned_lines.append("")
            continue

        # Remove inline comments (simplified approach)
        # Note: This doesn't handle # inside strings perfectly
        # For production, use tokenize module for robust handling
        if "#" in line:
            # Check if # is likely outside a string
            # Simple heuristic: count quotes before #
            before_hash = line.split("#")[0]
            single_quotes = before_hash.count("'")
            double_quotes = before_hash.count('"')

            # If even number of quotes, # is likely a comment
            if single_quotes % 2 == 0 and double_quotes % 2 == 0:
                line = before_hash.rstrip()

        cleaned_lines.append(line)

    code_without_comments = "\n".join(cleaned_lines)

    # Now remove docstrings using AST
    try:
        tree = ast.parse(code_without_comments)

        # Collect docstring nodes to remove
        docstring_lines = set()

        for node in ast.walk(tree):
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)
            ):
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, (ast.Str, ast.Constant))
                ):
                    # This is a docstring
                    docstring_node = node.body[0]
                    if hasattr(docstring_node, "lineno") and hasattr(
                        docstring_node, "end_lineno"
                    ):
                        # Mark these lines for removal
                        for line_no in range(
                            docstring_node.lineno, docstring_node.end_lineno + 1
                        ):
                            docstring_lines.add(line_no)

        # Remove docstring lines
        if docstring_lines:
            lines = code_without_comments.split("\n")
            result_lines = []
            for idx, line in enumerate(lines, start=1):
                if idx not in docstring_lines:
                    result_lines.append(line)
                elif preserve_structure:
                    result_lines.append("")

            code_without_comments = "\n".join(result_lines)

    except SyntaxError as e:
        logger.warning("Failed to parse Python code for docstring removal: %s", e)
        # Continue with comment-removed code

    # Remove excessive blank lines (more than 2 consecutive)
    result = re.sub(r"\n{3,}", "\n\n", code_without_comments)

    return result.strip()


def remove_yaml_comments(yaml_content: str) -> str:
    """
    Remove comments from YAML content to minimize token usage.

    Preserves YAML structure and values while removing comment lines.
    Handles both full-line comments and inline comments.

    Args:
        yaml_content: YAML source content

    Returns:
        YAML content with comments removed

    Note:
        Simple implementation - doesn't handle # inside quoted strings perfectly.
        For production use, consider PyYAML's parser for robust handling.

    Example:
        >>> yaml = '''
        ... # This is a comment
        ... key: value  # inline comment
        ... another: data
        ... '''
        >>> cleaned = remove_yaml_comments(yaml)
        >>> "This is a comment" not in cleaned
        True
        >>> "key: value" in cleaned
        True
    """
    lines = yaml_content.split("\n")
    cleaned_lines = []

    for line in lines:
        # Remove full comment lines
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue

        # Remove inline comments (after YAML value)
        if "#" in line:
            # Simple approach: if # appears, check if it's in a string
            # Count quotes before # to determine if inside string
            parts = line.split("#", 1)
            before_hash = parts[0]

            # Check for quotes
            single_quotes = before_hash.count("'")
            double_quotes = before_hash.count('"')

            # If even number of quotes, # is likely a comment
            if single_quotes % 2 == 0 and double_quotes % 2 == 0:
                line = before_hash.rstrip()

        # Only add non-empty lines
        if line.strip():
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def should_minimize_file(file_name: str) -> bool:
    """
    Determine if a file should have documentation minimized.

    Args:
        file_name: File name or path

    Returns:
        True if file should be minimized (is a source code file)

    Example:
        >>> should_minimize_file("test.py")
        True
        >>> should_minimize_file("README.md")
        False
    """
    file_name_lower = file_name.lower()

    # Source code files that should be minimized
    source_extensions = [
        ".py",
        ".yml",
        ".yaml",
        ".js",
        ".ts",
        ".java",
        ".cpp",
        ".c",
        ".go",
    ]

    # Documentation files that should NOT be minimized
    doc_extensions = [".md", ".rst", ".txt", ".pdf", ".html"]
    doc_names = ["readme", "changelog", "license", "contributing"]

    # Check if it's a documentation file
    for ext in doc_extensions:
        if file_name_lower.endswith(ext):
            return False

    for name in doc_names:
        if name in file_name_lower:
            return False

    # Check if it's a source code file
    for ext in source_extensions:
        if file_name_lower.endswith(ext):
            return True

    return False
