"""
AgenteLab Runtime Interaction Tool

CLI tool that enables AgenteLab to interact with the ScareVerse repository
through structured commands for file operations (grep, find, read).

Usage:
    python -m app.agentlab_runtime --command '{"type": "grep", "pattern": "import", "path": "backend/app"}'
    python -m app.agentlab_runtime --file commands.json
"""

import argparse
import asyncio
import json
import sys
from typing import Any, Dict, List

# Import existing MCP tools
from app.mcp.tools import file_tools, repo_tools


async def execute_grep(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute grep command to search content in files.

    Args:
        params: {
            "pattern": str - Search pattern
            "path": str - Directory to search (default: ".")
            "file_pattern": str - File pattern filter (e.g., "*.py")
            "case_sensitive": bool - Case sensitive search (default: False)
            "max_results": int - Max results (default: 100)
        }

    Returns:
        Search results with matches
    """
    query = params.get("pattern")
    if not query:
        raise ValueError("Missing required parameter: 'pattern'")

    search_params = {
        "query": query,
        "path": params.get("path", "."),
        "file_pattern": params.get("file_pattern"),
        "case_sensitive": params.get("case_sensitive", False),
        "max_results": params.get("max_results", 100),
    }

    result = await repo_tools.search_code(search_params)

    return {"command": "grep", "status": "success", "data": result}


async def execute_find(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute find command to search for files by pattern.

    Args:
        params: {
            "pattern": str - File pattern (glob, e.g., "*.py")
            "path": str - Starting directory (default: ".")
            "recursive": bool - Recursive search (default: True)
        }

    Returns:
        List of matching files
    """
    pattern = params.get("pattern")
    if not pattern:
        raise ValueError("Missing required parameter: 'pattern'")

    search_params = {
        "pattern": pattern,
        "path": params.get("path", "."),
        "recursive": params.get("recursive", True),
    }

    result = await file_tools.search_files(search_params)

    return {"command": "find", "status": "success", "data": result}


async def execute_read(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute read command to get file contents.

    Args:
        params: {
            "path": str - File path (required)
            "encoding": str - File encoding (default: "utf-8")
            "max_size_mb": int - Max file size in MB (default: 10)
        }

    Returns:
        File contents and metadata
    """
    path = params.get("path")
    if not path:
        raise ValueError("Missing required parameter: 'path'")

    read_params = {
        "path": path,
        "encoding": params.get("encoding", "utf-8"),
        "max_size_mb": params.get("max_size_mb", 10),
    }

    result = await file_tools.read_file(read_params)

    return {"command": "read", "status": "success", "data": result}


async def execute_command(command: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a single AgenteLab command.

    Args:
        command: {
            "type": str - Command type ("grep", "find", "read")
            "params": Dict - Command parameters
        }

    Returns:
        Command execution result
    """
    cmd_type = command.get("type", "").lower()
    params = command.get("params", {})

    # Allow params at root level for convenience
    if not params:
        params = {k: v for k, v in command.items() if k != "type"}

    try:
        if cmd_type == "grep":
            return await execute_grep(params)
        elif cmd_type == "find":
            return await execute_find(params)
        elif cmd_type == "read":
            return await execute_read(params)
        else:
            return {
                "command": cmd_type,
                "status": "error",
                "error": f"Unknown command type: {cmd_type}. "
                f"Supported: grep, find, read",
            }
    except Exception as e:
        return {"command": cmd_type, "status": "error", "error": str(e)}


async def execute_batch(commands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Execute multiple commands in batch.

    Args:
        commands: List of command dictionaries

    Returns:
        List of execution results
    """
    results = []
    for cmd in commands:
        result = await execute_command(cmd)
        results.append(result)

    return results


def format_output(result: Any, format_type: str = "json") -> str:
    """
    Format command result for output.

    Args:
        result: Command result
        format_type: Output format ("json" or "markdown")

    Returns:
        Formatted string
    """
    if format_type == "markdown":
        return format_markdown(result)
    else:
        return json.dumps(result, indent=2, ensure_ascii=False)


def format_markdown(result: Dict[str, Any]) -> str:
    """
    Format result as Markdown for AgenteLab consumption.

    Args:
        result: Command result

    Returns:
        Markdown formatted string
    """
    lines = []
    lines.append("```json")
    lines.append(json.dumps(result, indent=2, ensure_ascii=False))
    lines.append("```")

    # Add human-readable summary
    if result.get("status") == "success":
        data = result.get("data", {})
        cmd = result.get("command")

        if cmd == "grep":
            count = data.get("count", 0)
            lines.append(f"\n**Found {count} matches**")
            if count > 0:
                lines.append("\nSample matches:")
                for match in data.get("matches", [])[:5]:
                    file_path = match.get("file")
                    line_no = match.get("line")
                    content = match.get("content", "")[:80]
                    lines.append(f"- `{file_path}:{line_no}` - {content}")

        elif cmd == "find":
            count = data.get("count", 0)
            lines.append(f"\n**Found {count} files**")
            if count > 0:
                lines.append("\nMatching files:")
                for match in data.get("matches", [])[:10]:
                    path = match.get("path")
                    size = match.get("size")
                    lines.append(f"- `{path}` ({size} bytes)")

        elif cmd == "read":
            path = data.get("path")
            lines_count = data.get("lines", 0)
            size = data.get("size", 0)
            lines.append(f"\n**File**: `{path}`")
            lines.append(f"**Lines**: {lines_count}")
            lines.append(f"**Size**: {size} bytes")

    return "\n".join(lines)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AgenteLab Runtime Interaction Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Grep for pattern
  python -m app.agentlab_runtime --command '{"type": "grep", "pattern": "import"}'

  # Find Python files
  python -m app.agentlab_runtime --command '{"type": "find", "pattern": "*.py"}'

  # Read a file
  python -m app.agentlab_runtime --command '{"type": "read", "path": "README.md"}'

  # Execute batch from file
  python -m app.agentlab_runtime --file commands.json
        """,
    )

    parser.add_argument("--command", "-c", type=str, help="JSON command string")

    parser.add_argument("--file", "-f", type=str, help="JSON file with command(s)")

    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)",
    )

    parser.add_argument(
        "--output", "-o", type=str, help="Output file (default: stdout)"
    )

    args = parser.parse_args()

    # Validate input
    if not args.command and not args.file:
        parser.print_help()
        sys.exit(1)

    # Parse input
    try:
        if args.command:
            command_data = json.loads(args.command)
            # Single command
            if isinstance(command_data, dict):
                commands = [command_data]
            else:
                commands = command_data
        else:
            with open(args.file, "r", encoding="utf-8") as f:
                command_data = json.load(f)
                if isinstance(command_data, dict):
                    commands = [command_data]
                else:
                    commands = command_data
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    # Execute commands
    try:
        if len(commands) == 1:
            result = asyncio.run(execute_command(commands[0]))
        else:
            result = asyncio.run(execute_batch(commands))
    except Exception as e:
        print(f"Error executing command: {e}", file=sys.stderr)
        sys.exit(1)

    # Format output
    output = format_output(result, args.format)

    # Write output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Output written to: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
