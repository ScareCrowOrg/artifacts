"""
File Operations Endpoint Handlers

Provides handler functions for all file operation endpoints.

⚠️ SECURITY WARNING - LOCAL DEVELOPMENT ONLY ⚠️
These handlers allow UNRESTRICTED file operations within BASE_DIR.
Designed for LOCAL DEVELOPMENT with version control (git).
DO NOT use in production or multi-user environments.
"""

from fastapi import Query
from fastapi.responses import JSONResponse
from pathlib import Path
import logging
import os
import shutil

from ...config import BASE_DIR
from ...file_utils import (
    validate_and_sanitize_path,
    validate_filename_extension,
    write_file_atomically,
    check_file_permissions,
    delete_file_or_directory,
)
from .file_ops_models import SaveFileRequest, MoverItemRequest, DeleteRequest, FileSnippetRequest

logger = logging.getLogger(__name__)


async def save_file(request: SaveFileRequest):
    """
    Save file content to the specified path.

    ⚠️ LOCAL DEVELOPMENT: Accepts ANY file extension.

    Args:
        request: Save request with folder, filename, and content

    Returns:
        Success message with file path

    Raises:
        HTTPException: If validation fails or write error occurs
    """
    try:
        folder = request.folder.strip()
        filename = request.filename.strip()
        content = request.content

        # Validate filename
        if not filename:
            logger.warning("Attempt to save without filename")
            return JSONResponse(
                status_code=400,
                content={"status": "error", "details": "Nome do arquivo é obrigatório"},
            )

        # Validate filename (only check for path traversal, no extension restriction)
        is_valid_ext, ext_error = validate_filename_extension(filename)
        if not is_valid_ext:
            logger.warning("Invalid filename: %s - %s", filename, ext_error)
            return JSONResponse(
                status_code=400,
                content={"status": "error", "details": f"Nome de arquivo inválido: {ext_error}"},
            )

        # Validate and sanitize path
        file_path = os.path.join(folder, filename) if folder else filename
        is_valid_path, sanitized_path, path_error = validate_and_sanitize_path(
            str(BASE_DIR), file_path
        )

        if not is_valid_path:
            logger.warning("Invalid path: folder=%s, filename=%s - %s", folder, filename, path_error)
            return JSONResponse(
                status_code=400,
                content={"status": "error", "details": "Caminho de arquivo inválido"},
            )

        # Check write permissions
        has_permission, perm_error = check_file_permissions(sanitized_path, check_write=True)
        if not has_permission:
            logger.warning("No write permission: %s - %s", sanitized_path, perm_error)
            return JSONResponse(
                status_code=403, content={"status": "error", "details": "Sem permissão de escrita"}
            )

        # Write file atomically
        success, write_error = write_file_atomically(sanitized_path, content)

        if not success:
            logger.error("Error writing file: %s - %s", sanitized_path, write_error)
            return JSONResponse(
                status_code=500, content={"status": "error", "details": "Failed to write file"}
            )

        logger.info("File saved successfully: %s", sanitized_path)
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "message": "Arquivo salvo com sucesso",
                "path": os.path.relpath(sanitized_path, BASE_DIR),
            },
        )

    except Exception as e:
        logger.error("Global error in save_file handler: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500, content={"status": "error", "details": "Erro interno do servidor"}
        )


async def list_files(folder: str = Query(default="", description="Folder to list")):
    """
    List files and directories in the specified directory.

    ⚠️ LOCAL DEVELOPMENT: Lists ALL files regardless of extension.

    Args:
        folder: Relative folder path (empty for root)

    Returns:
        List of all files and directories (with trailing /)

    Raises:
        HTTPException: If path is invalid
    """
    try:
        folder = folder.strip()

        # Validate and sanitize path
        # SECURITY: validate_and_sanitize_path() prevents path traversal attacks
        is_valid_path, sanitized_path, path_error = validate_and_sanitize_path(
            str(BASE_DIR), folder if folder else "."
        )

        if not is_valid_path:
            logger.warning("Invalid path: folder=%s - %s", folder, path_error)
            return JSONResponse(
                status_code=400, content={"status": "error", "details": "Caminho inválido"}
            )

        # List files and directories
        # CodeQL Alert py/path-injection: FALSE POSITIVE
        # The paths have been validated by validate_and_sanitize_path() above
        files = []
        if os.path.isdir(sanitized_path):
            for item in os.listdir(sanitized_path):
                item_path = os.path.join(sanitized_path, item)
                if os.path.isdir(item_path):
                    # Add directory with trailing slash
                    files.append(item + "/")
                elif os.path.isfile(item_path):
                    # Add ALL files (no extension filtering)
                    files.append(item)

        files.sort()
        logger.info("Listed %s items in %s", len(files), folder if folder else 'root')
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "files": files, "folder": folder if folder else ""},
        )

    except Exception as e:
        logger.error("Error listing files: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500, content={"status": "error", "details": "Erro ao listar arquivos"}
        )


async def load_file(
    path: str = Query(default="", description="Single file path"),
    folder: str = Query(default="", description="Folder path (deprecated - use path or paths)"),
    filename: str = Query(
        default="", description="Filename to load (deprecated - use path or paths)"
    ),
    paths: str = Query(default="", description="Comma-separated file paths"),
    line_numbers: bool = Query(default=False, description="Include line numbers in content"),
):
    """
    Load file content with optional line numbers and multi-file support.

    ⚠️ LOCAL DEVELOPMENT: Loads ANY file type.

    Args:
        path: Relative file path (single file)
        folder: Relative folder path (legacy, single file)
        filename: Filename to load (legacy, single file)
        paths: Comma-separated list of file paths (new, multi-file)
        line_numbers: Include line numbers in content

    Returns:
        File content (single file) or list of files (multiple files)

    Raises:
        HTTPException: If file not found or invalid
    """
    try:
        # Determine mode: multi-file or single file
        file_paths = []

        if path:
            # Single file mode using path parameter
            file_paths = [path.strip()]
            logger.info("[FILE-LOAD] Single file mode (path): %s", path)
        elif paths:
            # Multi-file mode: parse comma-separated paths
            file_paths = [p.strip() for p in paths.split(",") if p.strip()]
            logger.info("[FILE-LOAD] Multi-file mode: %s files requested", len(file_paths))
        elif filename:
            # Single file mode (legacy compatibility)
            folder = folder.strip()
            filename = filename.strip()
            file_path = os.path.join(folder, filename) if folder else filename
            file_paths = [file_path]
            logger.info("[FILE-LOAD] Single file mode (legacy): %s", file_path)
        else:
            logger.warning("[FILE-LOAD] No filename, path, or paths provided")
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "details": "Either 'path', 'filename', or 'paths' parameter is required",
                },
            )

        # Limit number of files
        MAX_FILES = 10
        if len(file_paths) > MAX_FILES:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "details": f"Too many files. Maximum: {MAX_FILES}"},
            )

        # Load all requested files
        results = []
        for file_path in file_paths:
            # Validate filename (only check for path traversal, no extension restriction)
            filename_only = os.path.basename(file_path)
            is_valid_ext, ext_error = validate_filename_extension(filename_only)
            if not is_valid_ext:
                logger.warning("[FILE-LOAD] Invalid filename: %s - %s", filename_only, ext_error)
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "details": f"Invalid filename: {ext_error}"},
                )

            # Validate and sanitize path
            is_valid_path, sanitized_path, path_error = validate_and_sanitize_path(
                str(BASE_DIR), file_path
            )

            if not is_valid_path:
                logger.warning("[FILE-LOAD] Invalid path: %s - %s", file_path, path_error)
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "details": f"Invalid path: {file_path}"},
                )

            # Check if file exists
            if not os.path.isfile(sanitized_path):
                logger.warning("[FILE-LOAD] File not found: %s", sanitized_path)
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "details": f"File not found: {file_path}"},
                )

            # Check read permissions
            has_permission, perm_error = check_file_permissions(sanitized_path, check_write=False)
            if not has_permission:
                logger.warning("No read permission: %s - %s", sanitized_path, perm_error)
                return JSONResponse(
                    status_code=403,
                    content={"status": "error", "details": f"No read permission: {file_path}"},
                )

            # Read file
            with open(sanitized_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Add line numbers if requested
            if line_numbers:
                lines = content.splitlines()
                numbered_lines = [f"{i+1}: {line}" for i, line in enumerate(lines)]
                content = "\n".join(numbered_lines)

            logger.info("[FILE-LOAD] File loaded: %s, content length: %s", sanitized_path, len(content))

            results.append(
                {
                    "path": os.path.relpath(sanitized_path, BASE_DIR),
                    "content": content,
                    "lines": len(content.splitlines()),
                    "line_numbers": line_numbers,
                }
            )

        # Return format depends on mode
        if len(results) == 1 and not paths:
            # Single file mode (legacy) - return directly for backward compatibility
            return JSONResponse(
                status_code=200,
                content={
                    "status": "ok",
                    "content": results[0]["content"],
                    "path": results[0]["path"],
                },
            )
        else:
            # Multi-file mode - return array
            return JSONResponse(
                status_code=200, content={"status": "ok", "files": results, "count": len(results)}
            )

    except UnicodeDecodeError:
        # Handle binary files
        logger.warning("Binary file detected: %s", sanitized_path)
        return JSONResponse(
            status_code=400,
            content={"status": "error", "details": "Binary file cannot be loaded as text"},
        )
    except Exception as e:
        logger.error("Error loading file: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500, content={"status": "error", "details": "Error loading file"}
        )


async def move_item(request: MoverItemRequest):
    """
    Move file or folder from source to destination.

    Args:
        request: Move request with source and destination paths

    Returns:
        Success message with paths

    Raises:
        HTTPException: If validation fails or move error occurs
    """
    try:
        source = request.source.strip()
        destination = request.destination.strip()

        if not source:
            logger.warning("Attempt to move without source path")
            return JSONResponse(
                status_code=400,
                content={"status": "error", "details": "Caminho de origem é obrigatório"},
            )

        if not destination:
            logger.warning("Attempt to move without destination path")
            return JSONResponse(
                status_code=400,
                content={"status": "error", "details": "Caminho de destino é obrigatório"},
            )

        # Validate and sanitize source path
        # SECURITY: validate_and_sanitize_path() prevents path traversal attacks
        is_valid_source, sanitized_source, source_error = validate_and_sanitize_path(
            str(BASE_DIR), source
        )

        if not is_valid_source:
            logger.warning("Invalid source path: %s - %s", source, source_error)
            return JSONResponse(
                status_code=400,
                content={"status": "error", "details": "Caminho de origem inválido"},
            )

        # Validate and sanitize destination path
        # SECURITY: validate_and_sanitize_path() prevents path traversal attacks
        is_valid_dest, sanitized_dest, dest_error = validate_and_sanitize_path(
            str(BASE_DIR), destination
        )

        if not is_valid_dest:
            logger.warning("Invalid destination path: %s - %s", destination, dest_error)
            return JSONResponse(
                status_code=400,
                content={"status": "error", "details": "Caminho de destino inválido"},
            )

        # Check if source exists
        # CodeQL Alert py/path-injection: FALSE POSITIVE
        # The paths have been validated by validate_and_sanitize_path() above
        source_path = Path(sanitized_source)
        if not source_path.exists():
            return JSONResponse(
                status_code=400,
                content={"status": "error", "details": "Caminho de origem não existe"},
            )

        # Check if destination already exists
        # CodeQL Alert py/path-injection: FALSE POSITIVE
        # The paths have been validated by validate_and_sanitize_path() above
        dest_path = Path(sanitized_dest)
        if dest_path.exists():
            return JSONResponse(
                status_code=400,
                content={"status": "error", "details": "Caminho de destino já existe"},
            )

        # Ensure destination parent directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Move the item
        # CodeQL Alert py/path-injection: FALSE POSITIVE
        # Both paths have been validated by validate_and_sanitize_path() above
        shutil.move(str(source_path), str(dest_path))

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "message": "Item movido com sucesso",
                "origem": os.path.relpath(sanitized_source, BASE_DIR),
                "destino": os.path.relpath(sanitized_dest, BASE_DIR),
            },
        )

    except Exception as e:
        logger.error("Global error in move_item handler: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500, content={"status": "error", "details": "Erro interno do servidor"}
        )


async def delete_item(request: DeleteRequest):
    """
    Delete a file or directory.

    ⚠️ LOCAL DEVELOPMENT: Deletes ANY file or directory within BASE_DIR.
    USE WITH CAUTION. Requires OS write permissions.

    Args:
        request: Delete request with path to remove

    Returns:
        Success message with deleted path

    Raises:
        HTTPException: If validation fails or deletion error occurs
    """
    try:
        path = request.path.strip()

        if not path:
            logger.warning("Attempt to delete without path")
            return JSONResponse(
                status_code=400, content={"status": "error", "details": "Caminho é obrigatório"}
            )

        # Validate and sanitize path
        # SECURITY: validate_and_sanitize_path() prevents path traversal attacks
        is_valid_path, sanitized_path, path_error = validate_and_sanitize_path(str(BASE_DIR), path)

        if not is_valid_path:
            logger.warning("Invalid path: %s - %s", path, path_error)
            return JSONResponse(
                status_code=400, content={"status": "error", "details": "Caminho inválido"}
            )

        # Delete file or directory
        success, delete_error = delete_file_or_directory(sanitized_path)

        if not success:
            logger.error("Error deleting: %s - %s", sanitized_path, delete_error)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "details": f"Failed to delete: {delete_error}"},
            )

        logger.info("Deleted successfully: %s", sanitized_path)
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "message": "Item deletado com sucesso",
                "path": os.path.relpath(sanitized_path, BASE_DIR),
            },
        )

    except Exception as e:
        logger.error("Global error in delete_item handler: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500, content={"status": "error", "details": "Erro interno do servidor"}
        )


async def load_file_snippet(request: FileSnippetRequest):
    """
    Load a snippet from a file by line range.

    **Changed to POST** to avoid URL length limitations and follow REST best practices.

    Args:
        request: FileSnippetRequest with path, line range, and context

    Returns:
        File snippet with metadata

    Raises:
        HTTPException: If file not found, invalid line range, etc.
    """
    try:
        path = request.path.strip()
        start_line = request.start_line
        end_line = request.end_line
        context_lines = request.context_lines

        # Enhanced logging: Request received
        logger.info(
            "[FILE-SNIPPET] Request received: path=%s, lines=%s-%s, context=%s",
            path, start_line, end_line, context_lines
        )

        # Enhanced logging: Line number validation
        logger.debug(
            "[FILE-SNIPPET] Validating line numbers: start_line=%s, end_line=%s, is_positive=%s, is_valid_range=%s",
            start_line, end_line, start_line >= 1 and end_line >= 1, start_line <= end_line
        )

        # Validate line numbers
        if start_line < 1 or end_line < 1:
            logger.warning(
                "[FILE-SNIPPET] Invalid line numbers (must be positive): start_line=%s, end_line=%s",
                start_line, end_line
            )
            return JSONResponse(
                status_code=400,
                content={"status": "error", "details": "Line numbers must be positive (1-indexed)"},
            )

        if start_line > end_line:
            logger.warning(
                "[FILE-SNIPPET] Invalid line range (start > end): start_line=%s, end_line=%s",
                start_line, end_line
            )
            return JSONResponse(
                status_code=400,
                content={"status": "error", "details": "start_line must be <= end_line"},
            )

        # Enhanced logging: Path validation start
        logger.debug(
            "[FILE-SNIPPET] Validating path: raw_path=%s, stripped_path=%s, base_dir=%s",
            path, path.strip(), str(BASE_DIR)
        )

        # Validate and sanitize path
        is_valid_path, sanitized_path, path_error = validate_and_sanitize_path(str(BASE_DIR), path)

        # Enhanced logging: Path validation result
        logger.debug(
            "[FILE-SNIPPET] Path validation result: is_valid=%s, sanitized_path=%s, error=%s",
            is_valid_path, sanitized_path if is_valid_path else None, path_error if not is_valid_path else None
        )

        if not is_valid_path:
            logger.warning(
                "[FILE-SNIPPET] Path validation failed: raw_path=%s, error=%s, base_dir=%s",
                path, path_error, str(BASE_DIR)
            )
            return JSONResponse(
                status_code=400, content={"status": "error", "details": "Invalid file path"}
            )

        # Enhanced logging: File existence check
        logger.debug("[FILE-SNIPPET] Checking file existence: sanitized_path=%s, exists=%s, is_file=%s", sanitized_path, os.path.exists(sanitized_path), os.path.isfile(sanitized_path) if os.path.exists(sanitized_path) else False)

        # Check if file exists
        if not os.path.isfile(sanitized_path):
            logger.warning(
                "[FILE-SNIPPET] File not found or not a file: sanitized_path=%s, exists=%s, is_file=%s",
                sanitized_path, os.path.exists(sanitized_path), os.path.isfile(sanitized_path)
            )
            return JSONResponse(
                status_code=404, content={"status": "error", "details": "File not found"}
            )

        # Enhanced logging: Permission check
        logger.debug("[FILE-SNIPPET] Checking file permissions: sanitized_path=%s, check_write=False", sanitized_path)

        # Check read permissions
        has_permission, perm_error = check_file_permissions(sanitized_path, check_write=False)

        logger.debug(
            "[FILE-SNIPPET] Permission check result: has_permission=%s, error=%s",
            has_permission, perm_error if not has_permission else None
        )

        if not has_permission:
            logger.warning("[FILE-SNIPPET] No read permission: sanitized_path=%s, error=%s", sanitized_path, perm_error)
            return JSONResponse(
                status_code=403, content={"status": "error", "details": "No read permission"}
            )

        # Enhanced logging: File reading
        logger.debug("[FILE-SNIPPET] Reading file: sanitized_path=%s, encoding=utf-8", sanitized_path)

        # Read file and split into lines
        with open(sanitized_path, "r", encoding="utf-8") as f:
            content = f.read()

        logger.debug(
            "[FILE-SNIPPET] File read successfully: content_length=%s, content_bytes=%s",
            len(content), len(content.encode('utf-8'))
        )

        lines = content.splitlines()
        total_lines = len(lines)

        logger.debug(
            "[FILE-SNIPPET] File parsed into lines: total_lines=%s, has_trailing_newline=%s",
            total_lines, content.endswith(chr(10))
        )

        # Enhanced logging: Line range validation
        logger.debug("[FILE-SNIPPET] Validating line range against file: start_line=%s, end_line=%s, total_lines=%s, start_valid=%s, end_valid=%s", start_line, end_line, total_lines, start_line <= total_lines, end_line <= total_lines)

        # Special case: Allow appending new lines (start_line == total_lines + 1)
        # This enables inserting content after the last line of the file
        if start_line == total_lines + 1 and end_line >= start_line:
            logger.info("[FILE-SNIPPET] Append mode detected: start_line=%s, total_lines=%s", start_line, total_lines)
            response_data = {
                "status": "ok",
                "path": os.path.relpath(sanitized_path, BASE_DIR),
                "start_line": start_line,
                "end_line": end_line,
                "actual_start": start_line,
                "actual_end": end_line,
                "content": "",
                "lines": 0,
                "total_file_lines": total_lines,
                "context_lines": context_lines,
                "append_mode": True,
            }

            logger.info(
                "[FILE-SNIPPET] Append mode response prepared: path=%s, start_line=%s, total_lines=%s",
                response_data['path'], start_line, total_lines
            )

            return JSONResponse(status_code=200, content=response_data)

        # Validate line range is within file bounds
        if start_line > total_lines:
            logger.warning(
                "[FILE-SNIPPET] start_line exceeds file length: start_line=%s, total_lines=%s",
                start_line, total_lines
            )
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "details": f"start_line ({start_line}) exceeds file length ({total_lines} lines)",
                },
            )

        if end_line > total_lines:
            logger.warning(
                "[FILE-SNIPPET] end_line exceeds file length: end_line=%s, total_lines=%s",
                end_line, total_lines
            )
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "details": f"end_line ({end_line}) exceeds file length ({total_lines} lines)",
                },
            )

        # Enhanced logging: Context calculation
        logger.debug("[FILE-SNIPPET] Calculating context range: requested_start=%s, requested_end=%s, context_lines=%s, total_lines=%s", start_line, end_line, context_lines, total_lines)

        # Calculate actual range with context
        actual_start = max(1, start_line - context_lines)
        actual_end = min(total_lines, end_line + context_lines)

        logger.debug("[FILE-SNIPPET] Context range calculated: actual_start=%s, actual_end=%s, context_before=%s, context_after=%s, total_lines_in_snippet=%s", actual_start, actual_end, start_line - actual_start, actual_end - end_line, actual_end - actual_start + 1)

        # Enhanced logging: Snippet extraction
        logger.debug(
            "[FILE-SNIPPET] Extracting snippet: slice_start=%s, slice_end=%s, array_indices=%s:%s",
            actual_start - 1, actual_end, actual_start - 1, actual_end
        )

        # Extract snippet (convert to 0-indexed for array slicing)
        snippet_lines = lines[actual_start - 1 : actual_end]
        snippet_content = "\n".join(snippet_lines)

        logger.debug("[FILE-SNIPPET] Snippet extracted: lines_extracted=%s, content_length=%s, first_line_preview=%s, last_line_preview=%s", len(snippet_lines), len(snippet_content), snippet_lines[0][:50] if snippet_lines else '', snippet_lines[-1][:50] if snippet_lines else '')

        # Enhanced logging: Response construction
        response_data = {
            "status": "ok",
            "path": os.path.relpath(sanitized_path, BASE_DIR),
            "start_line": start_line,
            "end_line": end_line,
            "actual_start": actual_start,
            "actual_end": actual_end,
            "content": snippet_content,
            "lines": len(snippet_lines),
            "total_file_lines": total_lines,
            "context_lines": context_lines,
        }

        logger.info("[FILE-SNIPPET] Snippet extraction successful: path=%s, requested_range=%s-%s, actual_range=%s-%s, lines_returned=%s, content_size=%s, success=True", response_data['path'], start_line, end_line, actual_start, actual_end, response_data['lines'], len(snippet_content))

        return JSONResponse(status_code=200, content=response_data)

    except UnicodeDecodeError:
        logger.warning("Binary file detected: %s", sanitized_path)
        return JSONResponse(
            status_code=400,
            content={"status": "error", "details": "Binary file cannot be loaded as text"},
        )
    except Exception as e:
        logger.error("Error loading file snippet: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500, content={"status": "error", "details": "Error loading file snippet"}
        )
