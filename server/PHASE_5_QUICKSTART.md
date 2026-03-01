# Phase 5 Quick Start Guide

## Prerequisites

Ensure Phase 4 is working (server running, project indexed).

## Quick Test

### 1. Start the Server

```bash
cd server
python main.py
```

Server runs on `http://localhost:8765`

### 2. Test Command Execution

The `run_command` tool is now fully functional in the agent:

```bash
curl -X POST "http://localhost:8765/agent/query" \
  -G --data-urlencode "task=Run pytest on the tests directory and show me the results"
```

The agent will:
1. Use the `run_command` tool
2. Execute `pytest tests/` with safety checks
3. Return the test results

### 3. Test Terminal Sessions

**Create a terminal:**
```bash
curl -X POST "http://localhost:8765/terminal/create"
```

Response:
```json
{
  "session_id": "abc-123-def-456",
  "status": "active"
}
```

**Send a command:**
```bash
SESSION_ID="abc-123-def-456"
curl -X POST "http://localhost:8765/terminal/$SESSION_ID/command?command=ls%20-la"
```

Response:
```json
{
  "output": "total 48\ndrwxr-xr-x  12 user  staff   384 Jan 15 10:30 .\n...",
  "session_id": "abc-123-def-456"
}
```

**Read more output:**
```bash
curl "http://localhost:8765/terminal/$SESSION_ID/output?timeout=1.0"
```

**Close terminal:**
```bash
curl -X DELETE "http://localhost:8765/terminal/$SESSION_ID"
```

### 4. Test Session Persistence

**List sessions for current project:**
```bash
curl "http://localhost:8765/sessions"
```

Response:
```json
{
  "sessions": [
    {
      "session_id": "session-123",
      "task": "Run pytest on tests",
      "status": "complete",
      "created_at": "2024-01-15T10:30:00",
      "message_count": 5,
      "tool_call_count": 2
    }
  ],
  "count": 1
}
```

**Get session details:**
```bash
curl "http://localhost:8765/sessions/session-123"
```

**Clear all sessions:**
```bash
curl -X DELETE "http://localhost:8765/sessions"
```

### 5. Test Background Tasks

**Submit a background task:**
```bash
curl -X POST "http://localhost:8765/tasks/submit" \
  -G --data-urlencode "task=Find all TODO comments in the codebase" \
  --data-urlencode "max_iterations=5"
```

Response:
```json
{
  "task_id": "task-456",
  "session_id": "session-789",
  "status": "pending"
}
```

**Check task status:**
```bash
TASK_ID="task-456"
curl "http://localhost:8765/tasks/$TASK_ID"
```

Response:
```json
{
  "task_id": "task-456",
  "status": "running",
  "progress": 45,
  "current_step": "Searching codebase...",
  "created_at": "2024-01-15T10:35:00",
  "started_at": "2024-01-15T10:35:01"
}
```

**Poll until complete:**
```bash
while true; do
  STATUS=$(curl -s "http://localhost:8765/tasks/$TASK_ID" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
  echo "Status: $STATUS"
  [ "$STATUS" = "complete" ] && break
  sleep 2
done
```

**List all tasks:**
```bash
curl "http://localhost:8765/tasks"
```

**Cancel a running task:**
```bash
curl -X DELETE "http://localhost:8765/tasks/$TASK_ID"
```

## Python Examples

### Command Execution

```python
import httpx

# Agent will execute command
response = httpx.post(
    "http://localhost:8765/agent/query",
    params={
        "task": "Run black --check on all Python files and report any formatting issues"
    }
)

result = response.json()
print(f"Status: {result['status']}")
print(f"Response: {result['response']}")

# Check tool calls
for tool_call in result['tool_calls_made']:
    if tool_call['tool'] == 'run_command':
        print(f"Command executed: {tool_call['params']['command']}")
        print(f"Result: {tool_call['result'][:200]}...")
```

### Terminal Session

```python
import httpx
import time

client = httpx.Client(base_url="http://localhost:8765")

# Create terminal
response = client.post("/terminal/create")
session_id = response.json()["session_id"]
print(f"Terminal created: {session_id}")

# Start a dev server
client.post(
    f"/terminal/{session_id}/command",
    params={"command": "npm run dev"}
)

# Wait a bit
time.sleep(2)

# Read output
response = client.get(
    f"/terminal/{session_id}/output",
    params={"timeout": 1.0}
)
print(f"Output:\n{response.json()['output']}")

# Send Ctrl+C to stop
client.post(
    f"/terminal/{session_id}/command",
    params={"command": "\x03"}  # Ctrl+C
)

# Cleanup
client.delete(f"/terminal/{session_id}")
```

### Session Management

```python
import httpx

client = httpx.Client(base_url="http://localhost:8765")

# List all sessions for current project
response = client.get("/sessions")
sessions = response.json()["sessions"]

print(f"Found {len(sessions)} sessions:")
for session in sessions:
    print(f"  - {session['task'][:50]} ({session['status']})")

# Get latest session
if sessions:
    latest = sessions[0]  # Already sorted by updated_at
    session_id = latest["session_id"]

    # Get full details
    response = client.get(f"/sessions/{session_id}")
    session = response.json()

    print(f"\nLatest session: {session['task']}")
    print(f"Messages: {len(session['messages'])}")
    print(f"Tool calls: {len(session['tool_calls'])}")

    # Show conversation
    for msg in session["messages"]:
        print(f"{msg['role']}: {msg['content'][:100]}...")
```

### Background Tasks

```python
import httpx
import time

client = httpx.Client(base_url="http://localhost:8765")

# Submit task
response = client.post(
    "/tasks/submit",
    params={
        "task": "Analyze the codebase and create a summary of all API endpoints",
        "max_iterations": 10
    }
)

task_id = response.json()["task_id"]
session_id = response.json()["session_id"]

print(f"Task submitted: {task_id}")
print(f"Session: {session_id}")

# Poll for completion
while True:
    response = client.get(f"/tasks/{task_id}")
    task = response.json()

    print(f"Progress: {task['progress']}% - {task.get('current_step', 'Starting...')}")

    if task["status"] in ["complete", "error", "cancelled"]:
        break

    time.sleep(2)

# Show result
if task["status"] == "complete":
    print(f"\n✅ Task completed!")
    print(f"Response: {task['result']['response']}")

    # Get the full session
    response = client.get(f"/sessions/{session_id}")
    session = response.json()
    print(f"\nFull conversation history available in session {session_id}")

else:
    print(f"\n❌ Task {task['status']}: {task.get('error', 'Unknown error')}")
```

## Testing Features

### Test Command Safety

```python
from execution.command import is_command_safe

# Safe commands
safe, error = is_command_safe("pytest tests/")
assert safe

safe, error = is_command_safe("git status")
assert safe

# Dangerous commands
safe, error = is_command_safe("rm -rf /")
assert not safe
assert "rm -rf" in error

safe, error = is_command_safe("sudo apt-get install foo")
assert not safe
assert "sudo" in error
```

### Test Direct Command Execution

```python
from execution.command import execute_command
import tempfile

# Create temp directory
temp_dir = tempfile.mkdtemp()

# Execute command
result = execute_command(
    command="echo 'Hello, World!'",
    cwd=temp_dir,
    timeout=10
)

assert result["status"] == "success"
assert result["exit_code"] == 0
assert "Hello, World!" in result["stdout"]
```

### Test Session Persistence

```python
from execution.sessions import SessionManager
import tempfile

# Create temp sessions directory
sessions_dir = tempfile.mkdtemp()
manager = SessionManager(sessions_dir)

# Create session
session = manager.create_session("Test task", "/project")
session_id = session.session_id

# Add data
session.add_message("user", "Hello")
session.add_tool_call("search_codebase", {"query": "auth"}, "Found 5 functions")
manager.update_session(session)

# Create new manager (simulates restart)
manager2 = SessionManager(sessions_dir)

# Load session
loaded = manager2.get_session(session_id)
assert loaded is not None
assert loaded.task == "Test task"
assert len(loaded.messages) == 1
assert len(loaded.tool_calls) == 1
```

## Integration with Agent

The agent now has full command execution capabilities. Examples:

**Run tests:**
```
Task: "Run all pytest tests and report the results"
Agent will:
1. Use search_codebase to find test files
2. Use run_command to execute "pytest tests/ -v"
3. Parse output and report results
```

**Format code:**
```
Task: "Check if the code needs formatting with black"
Agent will:
1. Use run_command to execute "black --check ."
2. Report which files need formatting
```

**Git operations:**
```
Task: "Show me the git status and recent commits"
Agent will:
1. Use run_command to execute "git status"
2. Use run_command to execute "git log --oneline -n 10"
3. Summarize the results
```

**Build project:**
```
Task: "Build the project and report any errors"
Agent will:
1. Use run_command to execute "npm run build" or "make" or "cargo build"
2. Monitor output for errors
3. Report build status
```

## Running Tests

```bash
cd server

# Run all execution tests
pytest tests/test_execution.py -v

# Run specific test classes
pytest tests/test_execution.py::TestCommandExecutor -v
pytest tests/test_execution.py::TestTerminalSession -v
pytest tests/test_execution.py::TestSessionManager -v
pytest tests/test_execution.py::TestTaskManager -v

# Run with coverage
pytest tests/test_execution.py --cov=execution --cov-report=term-missing
```

Expected: **All tests passing** with >90% coverage

## Troubleshooting

### Command Execution Issues

**Issue: "Command not in whitelist"**

Add your command to `execution/command.py`:
```python
ALLOWED_COMMANDS = {
    "pytest", "python", "node", "npm", "yarn",
    "your-command",  # Add here
}
```

**Issue: "Command timed out"**

Increase timeout in agent task:
```python
params = {
    "command": "long-running-command",
    "timeout": 300  # 5 minutes
}
```

### Terminal Issues

**Issue: Terminal output incomplete**

Wait longer before reading:
```bash
curl "http://localhost:8765/terminal/$SESSION_ID/output?timeout=5.0"
```

**Issue: Terminal session died**

Check if the process crashed. Recreate the session.

### Session Issues

**Issue: Session not found after restart**

Sessions are persistent on disk. Check:
```bash
ls -la ~/.codenav/sessions/
```

**Issue: Too many old sessions**

Clean up:
```bash
curl -X DELETE "http://localhost:8765/sessions"
```

### Task Issues

**Issue: Task stuck in "running"**

Tasks are in-memory only. If server restarts, task state is lost. Cancel and resubmit:
```bash
curl -X DELETE "http://localhost:8765/tasks/$TASK_ID"
```

**Issue: Too many concurrent tasks**

Increase worker pool in `execution/tasks.py`:
```python
manager = TaskManager(max_concurrent=5)  # Default is 3
```

## What's Working

✅ Safe command execution with whitelist
✅ Blocked dangerous patterns (rm -rf, sudo, etc.)
✅ Timeout enforcement for all commands
✅ PTY-based terminal sessions
✅ Interactive terminal I/O
✅ Session persistence to disk
✅ Background task execution
✅ Task progress tracking
✅ Task cancellation
✅ Session management (list, get, delete)
✅ Full agent integration

## What's Next

Phase 6: VS Code Extension
- Extension activation
- Server lifecycle management
- HTTP client for API calls
- Settings and configuration

---

**Phase 5 is complete!** 🎉

All execution infrastructure is implemented, tested, and documented. The agent can now execute commands safely, manage terminals, persist sessions, and run tasks in the background.
