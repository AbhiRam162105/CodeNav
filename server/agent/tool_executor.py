"""
Tool executor for CodeNav agent.
"""
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Sentinel values for special returns
SENTINEL_ASK_USER = "__ASK_USER__:"
SENTINEL_FINISH = "__FINISH__:"


def execute_tool(tool_call: Dict, state) -> str:
    """
    Execute a tool call and return the result.

    Args:
        tool_call: Dict with 'name' and 'params' keys
        state: Application state (app_state)

    Returns:
        Result string (or sentinel value for special cases)
    """
    tool_name = tool_call["name"]
    params = tool_call.get("params", {})

    logger.info(f"Executing tool: {tool_name} with params: {params}")

    # Route to appropriate handler
    if tool_name == "read_lines":
        return execute_read_lines(params, state)
    elif tool_name == "search_codebase":
        return execute_search(params, state)
    elif tool_name == "retrieve_context":
        return execute_retrieve_context(params, state)
    elif tool_name == "apply_diff":
        return execute_apply_diff(params, state)
    elif tool_name == "create_file":
        return execute_create_file(params, state)
    elif tool_name == "delete_file":
        return execute_delete_file(params, state)
    elif tool_name == "move_file":
        return execute_move_file(params, state)
    elif tool_name == "list_directory":
        return execute_list_directory(params, state)
    elif tool_name == "write_file":
        return execute_write_file(params, state)
    elif tool_name == "run_command":
        return execute_run_command(params, state)
    elif tool_name == "ask_user":
        return execute_ask_user(params)
    elif tool_name == "finish":
        return execute_finish(params)
    else:
        return f"Error: Unknown tool '{tool_name}'"


def execute_read_lines(params: Dict, state) -> str:
    """Read specific lines from a file."""
    file_path = params.get("file")
    start_line = params.get("start", 1)
    end_line = params.get("end")

    if not file_path:
        return "Error: 'file' parameter required"

    if not state.project_root:
        return "Error: No project opened"

    # Construct full path
    full_path = os.path.join(state.project_root, file_path)

    # Security check
    if not full_path.startswith(state.project_root):
        return "Error: Invalid file path (path traversal attempt)"

    # Read file
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Extract requested lines (1-indexed)
        start_idx = max(0, start_line - 1)
        end_idx = end_line if end_line else len(lines)

        selected_lines = lines[start_idx:end_idx]
        content = ''.join(selected_lines)

        return f"Lines {start_line}-{end_idx} from {file_path}:\n\n{content}"

    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


def execute_search(params: Dict, state) -> str:
    """Search for functions in the codebase."""
    query = params.get("query")
    top_k = params.get("top_k", 5)

    if not query:
        return "Error: 'query' parameter required"

    if not state.faiss_index or not state.index_metadata:
        return "Error: Index not ready. Please wait for indexing to complete."

    # Perform search
    from embeddings.index import search

    results = search(
        query,
        state.faiss_index,
        state.index_metadata,
        top_k=top_k
    )

    if not results:
        return f"No results found for query: {query}"

    # Format results
    output = f"Search results for '{query}':\n\n"
    for i, result in enumerate(results, 1):
        output += f"{i}. {result['qualified_name']} ({result['file']}:{result['line_start']})\n"
        output += f"   Score: {result['score']:.2f}\n"

    return output


def execute_retrieve_context(params: Dict, state) -> str:
    """Retrieve relevant context for a task."""
    task = params.get("task")
    depth = params.get("depth", 2)
    max_tokens = params.get("max_tokens", 2000)

    if not task:
        return "Error: 'task' parameter required"

    if not state.codemap or not state.faiss_index:
        return "Error: Index not ready"

    # Retrieve context
    from core.retriever import get_context

    context_result = get_context(
        task=task,
        codemap=state.codemap,
        index=state.faiss_index,
        metadata=state.index_metadata,
        root_dir=state.project_root,
        depth=depth,
        max_tokens=max_tokens
    )

    if not context_result["functions"]:
        return f"No relevant code found for task: {task}"

    # Format result
    output = f"Retrieved context for '{task}':\n"
    output += f"Entry functions: {', '.join(context_result['entry_functions'])}\n"
    output += f"Total functions: {len(context_result['functions'])}\n"
    output += f"Token estimate: {context_result['token_estimate']}\n\n"
    output += "Code:\n"
    output += context_result["context_string"]

    return output


def execute_apply_diff(params: Dict, state) -> str:
    """Apply a diff to a file."""
    file_path = params.get("file")
    original = params.get("original")
    modified = params.get("modified")

    if not file_path or original is None or modified is None:
        return "Error: 'file', 'original', and 'modified' parameters required"

    if not state.project_root:
        return "Error: No project opened"

    # Construct full path
    full_path = os.path.join(state.project_root, file_path)

    # Security check
    if not full_path.startswith(state.project_root):
        return "Error: Invalid file path"

    # Read current content
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            current_content = f.read()
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

    # Check if original exists
    if original not in current_content:
        return f"Error: Original text not found in {file_path}. The diff may be stale."

    # Apply replacement
    new_content = current_content.replace(original, modified, 1)

    # Write atomically
    tmp_path = full_path + ".codenav_tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        os.replace(tmp_path, full_path)

        return f"Successfully applied diff to {file_path}"

    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return f"Error writing file: {str(e)}"


def execute_create_file(params: Dict, state) -> str:
    """Create a new file."""
    path = params.get("path")
    content = params.get("content", "")

    if not path:
        return "Error: 'path' parameter required"

    if not state.project_root:
        return "Error: No project opened"

    # Construct full path
    full_path = os.path.join(state.project_root, path)

    # Security check
    if not full_path.startswith(state.project_root):
        return "Error: Invalid file path"

    # Create parent directories
    parent_dir = os.path.dirname(full_path)
    os.makedirs(parent_dir, exist_ok=True)

    # Write file
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return f"Successfully created {path}"

    except Exception as e:
        return f"Error creating file: {str(e)}"


def execute_run_command(params: Dict, state) -> str:
    """Execute a shell command with safety checks."""
    command = params.get("command")
    description = params.get("description", "")
    timeout = params.get("timeout", 60)

    if not command:
        return "Error: 'command' parameter required"

    if not state.project_root:
        return "Error: No project opened"

    # Execute command
    from execution.command import execute_command

    logger.info(f"Executing command: {command}")

    result = execute_command(
        command=command,
        cwd=state.project_root,
        timeout=timeout
    )

    # Format output
    if result["status"] == "success":
        output = f"Command executed successfully (exit code: 0)\n\n"
        if result["stdout"]:
            output += f"Output:\n{result['stdout']}\n"
        if result["stderr"]:
            output += f"\nWarnings/Info:\n{result['stderr']}\n"
        return output

    elif result["status"] == "timeout":
        return f"Error: Command timed out after {timeout}s\n\nPartial output:\n{result['stdout']}"

    else:  # error
        output = f"Command failed (exit code: {result['exit_code']})\n\n"
        if result["stdout"]:
            output += f"Output:\n{result['stdout']}\n"
        if result["stderr"]:
            output += f"\nError:\n{result['stderr']}\n"
        return output


def execute_ask_user(params: Dict) -> str:
    """Ask the user a question (returns sentinel)."""
    question = params.get("question")

    if not question:
        return "Error: 'question' parameter required"

    # Return sentinel value
    return f"{SENTINEL_ASK_USER}{question}"


def execute_finish(params: Dict) -> str:
    """Finish the task (returns sentinel)."""
    response = params.get("response", "")

    # Return sentinel value
    return f"{SENTINEL_FINISH}{response}"


def execute_write_file(params: Dict, state) -> str:
    """Write content to a file (creates or overwrites)."""
    path = params.get("path")
    content = params.get("content", "")

    if not path:
        return "Error: 'path' parameter required"

    if not state.project_root:
        return "Error: No project opened"

    # Construct full path
    full_path = os.path.join(state.project_root, path)

    # Security check
    if not full_path.startswith(state.project_root):
        return "Error: Invalid file path"

    # Create parent directories
    parent_dir = os.path.dirname(full_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    # Write file
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        action = "Updated" if os.path.exists(full_path) else "Created"
        return f"{action} {path} ({len(content)} bytes)"

    except Exception as e:
        return f"Error writing file: {str(e)}"


def execute_delete_file(params: Dict, state) -> str:
    """Delete a file."""
    path = params.get("path")

    if not path:
        return "Error: 'path' parameter required"

    if not state.project_root:
        return "Error: No project opened"

    # Construct full path
    full_path = os.path.join(state.project_root, path)

    # Security check
    if not full_path.startswith(state.project_root):
        return "Error: Invalid file path"

    # Delete file
    try:
        if os.path.isfile(full_path):
            os.remove(full_path)
            return f"Deleted {path}"
        elif os.path.isdir(full_path):
            return f"Error: {path} is a directory. Use run_command with 'rm -rf' for directories."
        else:
            return f"Error: {path} does not exist"

    except Exception as e:
        return f"Error deleting file: {str(e)}"


def execute_move_file(params: Dict, state) -> str:
    """Move/rename a file."""
    source = params.get("source")
    destination = params.get("destination")

    if not source or not destination:
        return "Error: 'source' and 'destination' parameters required"

    if not state.project_root:
        return "Error: No project opened"

    # Construct full paths
    source_path = os.path.join(state.project_root, source)
    dest_path = os.path.join(state.project_root, destination)

    # Security checks
    if not source_path.startswith(state.project_root):
        return "Error: Invalid source path"
    if not dest_path.startswith(state.project_root):
        return "Error: Invalid destination path"

    # Move file
    try:
        if not os.path.exists(source_path):
            return f"Error: Source file {source} does not exist"

        # Create destination directory if needed
        dest_dir = os.path.dirname(dest_path)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)

        # Move file
        import shutil
        shutil.move(source_path, dest_path)

        return f"Moved {source} to {destination}"

    except Exception as e:
        return f"Error moving file: {str(e)}"


def execute_list_directory(params: Dict, state) -> str:
    """List files in a directory."""
    path = params.get("path", ".")
    include_hidden = params.get("include_hidden", False)

    if not state.project_root:
        return "Error: No project opened"

    # Construct full path
    full_path = os.path.join(state.project_root, path)

    # Security check
    if not full_path.startswith(state.project_root):
        return "Error: Invalid path"

    # List directory
    try:
        if not os.path.isdir(full_path):
            return f"Error: {path} is not a directory"

        entries = os.listdir(full_path)

        # Filter hidden files if requested
        if not include_hidden:
            entries = [e for e in entries if not e.startswith('.')]

        # Separate dirs and files
        dirs = []
        files = []

        for entry in sorted(entries):
            entry_path = os.path.join(full_path, entry)
            if os.path.isdir(entry_path):
                dirs.append(entry + "/")
            else:
                # Get file size
                size = os.path.getsize(entry_path)
                files.append(f"{entry} ({size} bytes)")

        # Format output
        output = f"Contents of {path}:\n\n"
        if dirs:
            output += "Directories:\n"
            for d in dirs:
                output += f"  {d}\n"
            output += "\n"

        if files:
            output += "Files:\n"
            for f in files:
                output += f"  {f}\n"

        if not dirs and not files:
            output += "(empty directory)\n"

        return output

    except Exception as e:
        return f"Error listing directory: {str(e)}"
