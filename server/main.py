"""
CodeNav FastAPI Server
Main entry point for the backend server.
"""
import os
import difflib
import threading
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
import logging
from state import app_state
from models import (
    ProjectOpenRequest, ProjectOpenResponse,
    FileNode, FileReadResponse,
    FileWriteRequest, FileWriteResponse,
    ApplyDiffRequest, ApplyDiffResponse
)
from utils import build_file_tree, detect_language
from middleware import (
    RequestLoggingMiddleware,
    global_exception_handler,
    setup_logging
)

# Load environment variables
load_dotenv()

# Set up logging
log_dir = os.path.join(os.path.expanduser("~"), ".codenav")
os.makedirs(log_dir, exist_ok=True)
setup_logging(os.path.join(log_dir, "server.log"))

# Create FastAPI app
app = FastAPI(
    title="CodeNav Server",
    description="Context-efficient AI coding assistant backend",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Will tighten this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Add global exception handler
app.add_exception_handler(Exception, global_exception_handler)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "CodeNav Server", "version": "0.1.0"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "0.1.0",
        "project_root": app_state.project_root,
        "index_status": app_state.index_status
    }


@app.post("/project/open", response_model=ProjectOpenResponse)
async def open_project(request: ProjectOpenRequest):
    """Open a project directory."""
    path = request.path

    # Validate path exists and is a directory
    if not os.path.exists(path):
        raise HTTPException(status_code=400, detail="Directory not found")

    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Path is not a directory")

    # Set project root in state
    app_state.project_root = os.path.abspath(path)
    app_state.index_status = "idle"

    return ProjectOpenResponse(
        success=True,
        path=app_state.project_root,
        name=os.path.basename(app_state.project_root)
    )


@app.get("/files/tree", response_model=List[FileNode])
async def get_file_tree():
    """Get the file tree for the current project."""
    if app_state.project_root is None:
        raise HTTPException(status_code=400, detail="No project opened")

    tree = build_file_tree(app_state.project_root)
    return tree


@app.get("/files/read", response_model=FileReadResponse)
async def read_file(path: str):
    """Read a file from the project."""
    if app_state.project_root is None:
        raise HTTPException(status_code=400, detail="No project opened")

    # Resolve the full path
    full_path = os.path.join(app_state.project_root, path)
    full_path = os.path.abspath(full_path)

    # Security: prevent path traversal
    if not full_path.startswith(app_state.project_root):
        raise HTTPException(status_code=400, detail="Invalid file path (path traversal attempt)")

    # Check file exists
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.isfile(full_path):
        raise HTTPException(status_code=400, detail="Path is not a file")

    # Check file size (refuse files over 500KB)
    file_size = os.path.getsize(full_path)
    if file_size > 500 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 500KB)")

    # Read file
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Binary file
        raise HTTPException(status_code=400, detail="Cannot read binary file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

    # Count lines
    line_count = content.count('\n') + 1 if content else 0

    # Detect language
    language = detect_language(full_path)

    return FileReadResponse(
        content=content,
        language=language,
        line_count=line_count,
        size_bytes=file_size
    )


@app.post("/files/write", response_model=FileWriteResponse)
async def write_file(request: FileWriteRequest):
    """Write content to a file."""
    if app_state.project_root is None:
        raise HTTPException(status_code=400, detail="No project opened")

    # Resolve the full path
    full_path = os.path.join(app_state.project_root, request.path)
    full_path = os.path.abspath(full_path)

    # Security: prevent path traversal
    if not full_path.startswith(app_state.project_root):
        raise HTTPException(status_code=400, detail="Invalid file path (path traversal attempt)")

    # Create parent directories if needed
    parent_dir = os.path.dirname(full_path)
    os.makedirs(parent_dir, exist_ok=True)

    # Atomic write: write to temp file first, then replace
    tmp_path = full_path + ".codenav_tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        os.replace(tmp_path, full_path)
    except Exception as e:
        # Clean up temp file if it exists
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"Error writing file: {str(e)}")

    # Count lines
    line_count = request.content.count('\n') + 1 if request.content else 0

    return FileWriteResponse(
        success=True,
        line_count=line_count
    )


@app.post("/files/apply_diff", response_model=ApplyDiffResponse)
async def apply_diff(request: ApplyDiffRequest):
    """Apply a diff to a file."""
    if app_state.project_root is None:
        raise HTTPException(status_code=400, detail="No project opened")

    # Resolve the full path
    full_path = os.path.join(app_state.project_root, request.path)
    full_path = os.path.abspath(full_path)

    # Security: prevent path traversal
    if not full_path.startswith(app_state.project_root):
        raise HTTPException(status_code=400, detail="Invalid file path (path traversal attempt)")

    # Read current file content
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            current_content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

    # Verify the original string exists in the current content
    if request.original not in current_content:
        raise HTTPException(status_code=409, detail="Diff is stale - original content not found in file")

    # Apply the replacement
    new_content = current_content.replace(request.original, request.modified, 1)

    # Generate unified diff
    diff_lines = list(difflib.unified_diff(
        current_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f'a/{request.path}',
        tofile=f'b/{request.path}',
        lineterm=''
    ))
    unified_diff = ''.join(diff_lines)

    # Write the modified content atomically
    tmp_path = full_path + ".codenav_tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        os.replace(tmp_path, full_path)
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"Error writing file: {str(e)}")

    return ApplyDiffResponse(
        success=True,
        diff=unified_diff
    )


# Global file watcher instance
file_watcher = None
logger = logging.getLogger(__name__)


def index_project_background():
    """Background task to index the project."""
    from core.call_tree import build_codemap, resolve_callees
    from core.serialization import save_codemap, update_codemap_for_file
    from core.watcher import FileWatcher
    from embeddings.index import build_index, save_index

    global file_watcher

    try:
        app_state.index_status = "indexing"
        app_state.index_progress = 0

        logger.info(f"Starting indexing for {app_state.project_root}")

        # Build codemap
        codemap = build_codemap(app_state.project_root)

        # Update progress
        app_state.index_progress = 40

        # Resolve callees
        codemap = resolve_callees(codemap)

        # Save codemap to disk
        save_codemap(codemap, app_state.project_root)

        # Update progress
        app_state.index_progress = 60

        # Build FAISS index
        logger.info("Building FAISS index...")
        index, metadata = build_index(codemap, app_state.project_root)

        # Save index to disk
        save_index(index, metadata, app_state.project_root)

        # Store in state
        app_state.faiss_index = index
        app_state.index_metadata = metadata

        # Update state
        app_state.codemap = codemap
        app_state.index_progress = 100
        app_state.index_status = "ready"

        logger.info(
            f"Indexing complete: {codemap['function_count']} functions "
            f"in {codemap['file_count']} files"
        )

        # Start file watcher
        def on_files_changed(changed_files):
            """Handle file changes."""
            if not app_state.codemap:
                return

            logger.info(f"Updating codemap for {len(changed_files)} changed files")

            for file_path in changed_files:
                try:
                    app_state.codemap = update_codemap_for_file(
                        app_state.codemap,
                        file_path,
                        app_state.project_root
                    )
                except Exception as e:
                    logger.error(f"Error updating {file_path}: {e}")

            # Re-resolve callees
            app_state.codemap = resolve_callees(app_state.codemap)

            # Save updated codemap
            save_codemap(app_state.codemap, app_state.project_root)

        # Stop existing watcher if any
        if file_watcher and file_watcher.is_running():
            file_watcher.stop()

        # Start new watcher
        file_watcher = FileWatcher(app_state.project_root, on_files_changed)
        file_watcher.start()

    except Exception as e:
        logger.error(f"Error during indexing: {e}", exc_info=True)
        app_state.index_status = "error"
        app_state.index_progress = 0


@app.post("/index/start")
async def start_indexing():
    """Start indexing the current project."""
    if app_state.project_root is None:
        raise HTTPException(status_code=400, detail="No project opened")

    if app_state.index_status == "indexing":
        raise HTTPException(status_code=400, detail="Indexing already in progress")

    # Start indexing in background thread
    thread = threading.Thread(target=index_project_background, daemon=True)
    thread.start()

    return {
        "status": "started",
        "message": "Indexing started in background"
    }


@app.get("/index/status")
async def get_index_status():
    """Get the current indexing status."""
    if app_state.project_root is None:
        return {
            "status": "no_project",
            "progress": 0,
            "function_count": 0,
            "file_count": 0,
        }

    return {
        "status": app_state.index_status,
        "progress": app_state.index_progress,
        "function_count": app_state.codemap.get("function_count", 0) if app_state.codemap else 0,
        "file_count": app_state.codemap.get("file_count", 0) if app_state.codemap else 0,
    }


@app.get("/search")
async def search_functions(query: str, top_k: int = 5):
    """
    Search for functions using semantic similarity.

    Args:
        query: Natural language search query
        top_k: Number of results to return

    Returns:
        List of matching functions with scores
    """
    if app_state.index_status != "ready":
        raise HTTPException(status_code=400, detail="Index not ready")

    # Load index if not in memory
    if app_state.faiss_index is None or app_state.index_metadata is None:
        from embeddings.index import load_index

        result = load_index(app_state.project_root)
        if result is None:
            raise HTTPException(status_code=500, detail="Could not load index")

        app_state.faiss_index, app_state.index_metadata = result

    # Search
    from embeddings.index import search

    results = search(
        query,
        app_state.faiss_index,
        app_state.index_metadata,
        top_k=top_k
    )

    return {"results": results, "count": len(results)}


@app.post("/context/retrieve")
async def retrieve_context(task: str, depth: int = 2, max_tokens: int = 2000):
    """
    Retrieve relevant context for a task using semantic search + graph traversal.

    Args:
        task: Natural language task description
        depth: Graph traversal depth
        max_tokens: Maximum tokens to include

    Returns:
        Context dict with functions, snippets, and metadata
    """
    if app_state.index_status != "ready":
        raise HTTPException(status_code=400, detail="Index not ready")

    if app_state.codemap is None:
        raise HTTPException(status_code=500, detail="Codemap not available")

    # Load index if not in memory
    if app_state.faiss_index is None or app_state.index_metadata is None:
        from embeddings.index import load_index

        result = load_index(app_state.project_root)
        if result is None:
            raise HTTPException(status_code=500, detail="Could not load index")

        app_state.faiss_index, app_state.index_metadata = result

    # Get context
    from core.retriever import get_context

    context = get_context(
        task=task,
        codemap=app_state.codemap,
        index=app_state.faiss_index,
        metadata=app_state.index_metadata,
        root_dir=app_state.project_root,
        depth=depth,
        max_tokens=max_tokens
    )

    return context


@app.post("/agent/query")
async def agent_query(task: str, max_iterations: int = 10, max_tokens: int = 2048):
    """
    Execute the agent for a task.

    Args:
        task: User's task description
        max_iterations: Maximum number of agent turns
        max_tokens: Maximum tokens per LLM call

    Returns:
        Result dict with status, response, tool_calls_made, tokens_used
    """
    if app_state.index_status != "ready":
        raise HTTPException(status_code=400, detail="Index not ready. Please wait for indexing to complete.")

    if app_state.codemap is None:
        raise HTTPException(status_code=500, detail="Codemap not available")

    # Load index if not in memory
    if app_state.faiss_index is None or app_state.index_metadata is None:
        from embeddings.index import load_index

        result = load_index(app_state.project_root)
        if result is None:
            raise HTTPException(status_code=500, detail="Could not load index")

        app_state.faiss_index, app_state.index_metadata = result

    # Run agent
    from agent.loop import run_agent

    try:
        result = run_agent(
            task=task,
            state=app_state,
            max_iterations=max_iterations,
            max_tokens=max_tokens
        )

        return result

    except Exception as e:
        logger.error(f"Error running agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.post("/agent/plan")
async def create_task_plan(task: str):
    """
    Create an execution plan by decomposing a user request into atomic tasks.
    Similar to how GitHub Copilot breaks down complex requests.

    Args:
        task: User's task description

    Returns:
        Execution plan with elaboration, tasks, and metadata
    """
    if app_state.codemap is None:
        raise HTTPException(status_code=400, detail="No project opened")

    # Get codemap summary
    context = {
        "function_count": len(app_state.codemap["functions"]),
        "file_count": len(app_state.codemap["files"])
    }

    # Create task planner
    from agent.task_planner import TaskPlanner
    from agent.llm_client import get_llm_client

    llm_client = get_llm_client()
    planner = TaskPlanner(llm_client)

    try:
        # Create execution plan
        plan = planner.create_execution_plan(task, context)
        return plan

    except Exception as e:
        logger.error(f"Error creating task plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Planning error: {str(e)}")


@app.websocket("/agent/stream")
async def agent_stream(websocket: WebSocket):
    """
    Stream agent responses via WebSocket.

    Client sends JSON: {"task": "...", "max_iterations": 10, "max_tokens": 2048}
    Server streams JSON messages: {"type": "...", "data": {...}}
    """
    await websocket.accept()

    try:
        # Receive task from client
        data = await websocket.receive_json()
        task = data.get("task")
        max_iterations = data.get("max_iterations", 10)
        max_tokens = data.get("max_tokens", 2048)

        if not task:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "No task provided"}
            })
            await websocket.close()
            return

        # Check index ready
        if app_state.index_status != "ready":
            await websocket.send_json({
                "type": "error",
                "data": {"message": "Index not ready"}
            })
            await websocket.close()
            return

        # Load index if needed
        if app_state.faiss_index is None or app_state.index_metadata is None:
            from embeddings.index import load_index

            result = load_index(app_state.project_root)
            if result is None:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Could not load index"}
                })
                await websocket.close()
                return

            app_state.faiss_index, app_state.index_metadata = result

        # Import agent components
        from agent.llm_client import get_client
        from agent.prompts import build_system_prompt
        from agent.tool_parser import parse_tool_call, extract_text_before_tool_call
        from agent.tool_executor import execute_tool, SENTINEL_ASK_USER, SENTINEL_FINISH
        from agent.history import HistoryManager

        # Initialize
        client = get_client()
        history = HistoryManager()
        tool_calls_made = []
        tokens_used_estimate = 0

        # Build system prompt
        codemap_summary = {
            "function_count": app_state.codemap.get("function_count", 0),
            "file_count": app_state.codemap.get("file_count", 0),
        }
        system_prompt = build_system_prompt(codemap_summary)

        # Add initial task
        history.add_user(task)

        # Send start event
        await websocket.send_json({
            "type": "start",
            "data": {"task": task, "max_iterations": max_iterations}
        })

        # Agent loop
        for iteration in range(max_iterations):
            # Send iteration event
            await websocket.send_json({
                "type": "iteration",
                "data": {"iteration": iteration + 1, "max_iterations": max_iterations}
            })

            # Trim history
            history.trim_to_budget(max_tokens // 2)

            # Get messages
            messages = history.get_messages()

            # Call LLM with streaming
            try:
                # Stream response chunks
                full_response = ""

                for chunk in client.invoke_stream(
                    system_prompt=system_prompt,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.2
                ):
                    full_response += chunk

                    # Send chunk to client
                    await websocket.send_json({
                        "type": "chunk",
                        "data": {"text": chunk}
                    })

                tokens_used_estimate += len(full_response) // 4

            except Exception as e:
                logger.error(f"Error calling LLM: {e}")
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": f"LLM error: {str(e)}"}
                })
                break

            # Add model response to history
            history.add_model(full_response)

            # Check for tool call
            tool_call = parse_tool_call(full_response)

            if tool_call:
                # Extract text before tool call
                text_before = extract_text_before_tool_call(full_response)
                if text_before:
                    await websocket.send_json({
                        "type": "thinking",
                        "data": {"text": text_before}
                    })

                tool_name = tool_call["name"]

                # Send tool call event
                await websocket.send_json({
                    "type": "tool_call",
                    "data": {
                        "tool": tool_name,
                        "params": tool_call.get("params", {})
                    }
                })

                # Execute tool
                try:
                    result = execute_tool(tool_call, app_state)

                    # Record tool call
                    tool_calls_made.append({
                        "tool": tool_name,
                        "params": tool_call.get("params", {}),
                        "result": result[:200] + "..." if len(result) > 200 else result
                    })

                    # Send tool result
                    await websocket.send_json({
                        "type": "tool_result",
                        "data": {
                            "tool": tool_name,
                            "result": result
                        }
                    })

                except Exception as e:
                    logger.error(f"Error executing tool {tool_name}: {e}")
                    result = f"Error executing tool: {str(e)}"

                    await websocket.send_json({
                        "type": "tool_error",
                        "data": {
                            "tool": tool_name,
                            "error": str(e)
                        }
                    })

                # Check for sentinels
                if result.startswith(SENTINEL_ASK_USER):
                    question = result[len(SENTINEL_ASK_USER):]
                    await websocket.send_json({
                        "type": "needs_input",
                        "data": {
                            "question": question,
                            "tool_calls_made": tool_calls_made,
                            "tokens_used": tokens_used_estimate
                        }
                    })
                    break

                if result.startswith(SENTINEL_FINISH):
                    final_response = result[len(SENTINEL_FINISH):]
                    await websocket.send_json({
                        "type": "complete",
                        "data": {
                            "response": final_response,
                            "tool_calls_made": tool_calls_made,
                            "tokens_used": tokens_used_estimate
                        }
                    })
                    break

                # Add tool result to history
                history.add_tool_result(tool_name, result)

            else:
                # No tool call - check if looks complete
                if any(phrase in full_response.lower() for phrase in [
                    "i've completed",
                    "task is complete",
                    "i've finished",
                    "done",
                    "successfully applied"
                ]):
                    await websocket.send_json({
                        "type": "complete",
                        "data": {
                            "response": full_response,
                            "tool_calls_made": tool_calls_made,
                            "tokens_used": tokens_used_estimate
                        }
                    })
                    break

        else:
            # Max iterations reached
            last_messages = history.get_last_n_messages(1)
            last_response = last_messages[0]["content"] if last_messages else "No response"

            await websocket.send_json({
                "type": "max_iterations",
                "data": {
                    "response": last_response,
                    "tool_calls_made": tool_calls_made,
                    "tokens_used": tokens_used_estimate
                }
            })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")

    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass

    finally:
        try:
            await websocket.close()
        except:
            pass


# ============================================================================
# TERMINAL ENDPOINTS
# ============================================================================

@app.post("/terminal/create")
async def create_terminal():
    """
    Create a new terminal session.

    Returns:
        Session ID and status
    """
    if app_state.project_root is None:
        raise HTTPException(status_code=400, detail="No project opened")

    from execution.terminal import get_terminal_manager

    terminal_manager = get_terminal_manager()

    try:
        session_id = terminal_manager.create_session(app_state.project_root)

        return {
            "session_id": session_id,
            "status": "active"
        }

    except Exception as e:
        logger.error(f"Error creating terminal session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create terminal: {str(e)}")


@app.post("/terminal/{session_id}/command")
async def send_terminal_command(session_id: str, command: str):
    """
    Send a command to a terminal session.

    Args:
        session_id: Terminal session ID
        command: Command to execute

    Returns:
        Output from the command
    """
    from execution.terminal import get_terminal_manager

    terminal_manager = get_terminal_manager()
    session = terminal_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Terminal session not found")

    try:
        # Send command
        session.send_command(command)

        # Wait for output (2 seconds)
        output = session.read_output(timeout=2.0)

        return {
            "output": output,
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"Error sending command: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/terminal/{session_id}/output")
async def get_terminal_output(session_id: str, timeout: float = 1.0):
    """
    Read output from a terminal session.

    Args:
        session_id: Terminal session ID
        timeout: How long to wait for output

    Returns:
        Terminal output
    """
    from execution.terminal import get_terminal_manager

    terminal_manager = get_terminal_manager()
    session = terminal_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Terminal session not found")

    try:
        output = session.read_output(timeout=timeout)

        return {
            "output": output,
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"Error reading output: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/terminal/{session_id}")
async def close_terminal(session_id: str):
    """
    Close a terminal session.

    Args:
        session_id: Terminal session ID

    Returns:
        Success status
    """
    from execution.terminal import get_terminal_manager

    terminal_manager = get_terminal_manager()
    session = terminal_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Terminal session not found")

    try:
        terminal_manager.close_session(session_id)

        return {
            "success": True,
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"Error closing terminal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SESSION ENDPOINTS
# ============================================================================

@app.get("/sessions")
async def list_sessions():
    """
    List all agent sessions for the current project.

    Returns:
        List of session summaries
    """
    if app_state.project_root is None:
        raise HTTPException(status_code=400, detail="No project opened")

    from execution.sessions import get_session_manager

    session_manager = get_session_manager()

    sessions = session_manager.list_sessions(project_root=app_state.project_root)

    return {"sessions": sessions, "count": len(sessions)}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Get details of a specific session.

    Args:
        session_id: Session ID

    Returns:
        Session details
    """
    from execution.sessions import get_session_manager

    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.to_dict()


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a session.

    Args:
        session_id: Session ID

    Returns:
        Success status
    """
    from execution.sessions import get_session_manager

    session_manager = get_session_manager()

    try:
        session_manager.delete_session(session_id)

        return {
            "success": True,
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"Error deleting session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions")
async def clear_sessions():
    """
    Clear all sessions for the current project.

    Returns:
        Number of sessions deleted
    """
    if app_state.project_root is None:
        raise HTTPException(status_code=400, detail="No project opened")

    from execution.sessions import get_session_manager

    session_manager = get_session_manager()

    # Get all sessions for this project
    sessions = session_manager.list_sessions(project_root=app_state.project_root)

    # Delete each one
    for session_info in sessions:
        session_manager.delete_session(session_info["session_id"])

    return {
        "success": True,
        "deleted_count": len(sessions)
    }


# ============================================================================
# TASK ENDPOINTS
# ============================================================================

@app.post("/tasks/submit")
async def submit_agent_task(task: str, max_iterations: int = 10, max_tokens: int = 2048):
    """
    Submit an agent task for background execution.

    Args:
        task: Task description
        max_iterations: Maximum agent iterations
        max_tokens: Maximum tokens per LLM call

    Returns:
        Task ID and status
    """
    if app_state.index_status != "ready":
        raise HTTPException(status_code=400, detail="Index not ready")

    if app_state.codemap is None:
        raise HTTPException(status_code=500, detail="Codemap not available")

    from execution.tasks import get_task_manager
    from execution.sessions import get_session_manager
    from agent.loop import run_agent

    task_manager = get_task_manager()
    session_manager = get_session_manager()

    # Create session
    session = session_manager.create_session(task, app_state.project_root)

    # Create task
    agent_task = task_manager.create_task(task, session.session_id)

    # Define execution function
    def execute_agent(agent_task):
        """Execute agent in background."""
        try:
            # Update progress
            agent_task.update_progress(10, "Starting agent")

            # Run agent
            result = run_agent(
                task=task,
                state=app_state,
                max_iterations=max_iterations,
                max_tokens=max_tokens
            )

            # Update session
            session.set_status(result["status"])
            session_manager.update_session(session)

            agent_task.update_progress(100, "Complete")

            return result

        except Exception as e:
            logger.error(f"Error in background agent: {e}", exc_info=True)
            raise

    # Submit task
    task_manager.submit_task(agent_task.task_id, execute_agent)

    return {
        "task_id": agent_task.task_id,
        "session_id": session.session_id,
        "status": agent_task.status
    }


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Get status of a background task.

    Args:
        task_id: Task ID

    Returns:
        Task status and details
    """
    from execution.tasks import get_task_manager

    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task.to_dict()


@app.get("/tasks")
async def list_tasks(status: Optional[str] = None, session_id: Optional[str] = None):
    """
    List background tasks.

    Args:
        status: Filter by status (optional)
        session_id: Filter by session ID (optional)

    Returns:
        List of tasks
    """
    from execution.tasks import get_task_manager

    task_manager = get_task_manager()
    tasks = task_manager.list_tasks(status=status, session_id=session_id)

    return {"tasks": tasks, "count": len(tasks)}


@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel a running task.

    Args:
        task_id: Task ID

    Returns:
        Success status
    """
    from execution.tasks import get_task_manager

    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        task_manager.cancel_task(task_id)

        return {
            "success": True,
            "task_id": task_id,
            "status": "cancelled"
        }

    except Exception as e:
        logger.error(f"Error cancelling task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("SERVER_PORT", "8765"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
