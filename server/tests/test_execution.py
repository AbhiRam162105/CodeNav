"""
Tests for execution layer (commands, terminals, sessions, tasks).
"""
import pytest
import os
import tempfile
import shutil
import time
from execution.command import is_command_safe, CommandExecutor, execute_command
from execution.sessions import AgentSession, SessionManager
from execution.tasks import AgentTask, TaskManager


class TestCommandSafety:
    """Tests for command safety checks."""

    def test_safe_command(self):
        """Test that safe commands are allowed."""
        is_safe, error = is_command_safe("pytest tests/")
        assert is_safe
        assert error is None

    def test_blocked_pattern(self):
        """Test that dangerous patterns are blocked."""
        is_safe, error = is_command_safe("rm -rf /")
        assert not is_safe
        assert "rm -rf" in error

    def test_sudo_blocked(self):
        """Test that sudo is blocked."""
        is_safe, error = is_command_safe("sudo apt-get install foo")
        assert not is_safe
        assert "sudo" in error

    def test_unknown_command(self):
        """Test that unknown commands are blocked."""
        is_safe, error = is_command_safe("dangerous_tool --delete-all")
        assert not is_safe
        assert "not in whitelist" in error

    def test_empty_command(self):
        """Test that empty commands are rejected."""
        is_safe, error = is_command_safe("")
        assert not is_safe
        assert "Empty command" in error


class TestCommandExecutor:
    """Tests for command execution."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_execute_simple_command(self, temp_dir):
        """Test executing a simple command."""
        executor = CommandExecutor(temp_dir, timeout=10)

        result = executor.execute("echo 'Hello, World!'")

        assert result["status"] == "success"
        assert result["exit_code"] == 0
        assert "Hello, World!" in result["stdout"]

    def test_execute_command_with_error(self, temp_dir):
        """Test executing a command that fails."""
        executor = CommandExecutor(temp_dir, timeout=10)

        # Try to list non-existent file
        result = executor.execute("ls nonexistent_file_12345.txt")

        assert result["status"] == "error"
        assert result["exit_code"] != 0

    def test_execute_blocked_command(self, temp_dir):
        """Test executing a blocked command."""
        executor = CommandExecutor(temp_dir, timeout=10)

        result = executor.execute("rm -rf /")

        assert result["status"] == "error"
        assert "blocked" in result["stderr"].lower()

    def test_command_timeout(self, temp_dir):
        """Test command timeout."""
        executor = CommandExecutor(temp_dir, timeout=1)

        # Sleep for longer than timeout
        result = executor.execute("python -c 'import time; time.sleep(10)'", timeout=1)

        assert result["status"] == "timeout"
        assert "Timeout" in result["stderr"]

    def test_execute_in_cwd(self, temp_dir):
        """Test that command executes in correct working directory."""
        # Create a test file
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test content")

        executor = CommandExecutor(temp_dir, timeout=10)

        # List files in temp_dir
        result = executor.execute("ls test.txt")

        assert result["status"] == "success"
        assert "test.txt" in result["stdout"]


class TestAgentSession:
    """Tests for agent session."""

    def test_create_session(self):
        """Test creating a session."""
        session = AgentSession(
            session_id="test-123",
            task="Fix authentication bug",
            project_root="/path/to/project"
        )

        assert session.session_id == "test-123"
        assert session.task == "Fix authentication bug"
        assert session.status == "active"
        assert len(session.messages) == 0

    def test_add_message(self):
        """Test adding messages to session."""
        session = AgentSession("test-123", "Task", "/path")

        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")

        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "Hello"
        assert session.messages[1]["role"] == "assistant"

    def test_add_tool_call(self):
        """Test recording tool calls."""
        session = AgentSession("test-123", "Task", "/path")

        session.add_tool_call(
            "search_codebase",
            {"query": "auth functions"},
            "Found 5 functions..."
        )

        assert len(session.tool_calls) == 1
        assert session.tool_calls[0]["tool"] == "search_codebase"

    def test_set_status(self):
        """Test setting session status."""
        session = AgentSession("test-123", "Task", "/path")

        session.set_status("complete")

        assert session.status == "complete"

    def test_to_dict(self):
        """Test converting session to dict."""
        session = AgentSession("test-123", "Task", "/path")
        session.add_message("user", "Test")

        data = session.to_dict()

        assert data["session_id"] == "test-123"
        assert data["task"] == "Task"
        assert data["status"] == "active"
        assert len(data["messages"]) == 1

    def test_from_dict(self):
        """Test creating session from dict."""
        data = {
            "session_id": "test-123",
            "task": "Task",
            "project_root": "/path",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T01:00:00",
            "status": "complete",
            "messages": [{"role": "user", "content": "Hello"}],
            "tool_calls": [],
            "metadata": {"key": "value"}
        }

        session = AgentSession.from_dict(data)

        assert session.session_id == "test-123"
        assert session.status == "complete"
        assert len(session.messages) == 1
        assert session.metadata["key"] == "value"


class TestSessionManager:
    """Tests for session manager."""

    @pytest.fixture
    def temp_sessions_dir(self):
        """Create temporary sessions directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_create_session(self, temp_sessions_dir):
        """Test creating a session."""
        manager = SessionManager(temp_sessions_dir)

        session = manager.create_session("Fix bug", "/path/to/project")

        assert session.session_id is not None
        assert session.task == "Fix bug"
        assert session.project_root == "/path/to/project"

    def test_get_session(self, temp_sessions_dir):
        """Test retrieving a session."""
        manager = SessionManager(temp_sessions_dir)

        # Create session
        session = manager.create_session("Task", "/path")

        # Retrieve it
        retrieved = manager.get_session(session.session_id)

        assert retrieved is not None
        assert retrieved.session_id == session.session_id
        assert retrieved.task == "Task"

    def test_session_persistence(self, temp_sessions_dir):
        """Test that sessions are persisted to disk."""
        manager1 = SessionManager(temp_sessions_dir)

        # Create session
        session = manager1.create_session("Task", "/path")
        session_id = session.session_id

        # Create new manager (simulates restart)
        manager2 = SessionManager(temp_sessions_dir)

        # Should be able to load session
        loaded = manager2.get_session(session_id)

        assert loaded is not None
        assert loaded.session_id == session_id
        assert loaded.task == "Task"

    def test_delete_session(self, temp_sessions_dir):
        """Test deleting a session."""
        manager = SessionManager(temp_sessions_dir)

        # Create session
        session = manager.create_session("Task", "/path")
        session_id = session.session_id

        # Delete it
        manager.delete_session(session_id)

        # Should not be retrievable
        assert manager.get_session(session_id) is None

    def test_list_sessions(self, temp_sessions_dir):
        """Test listing sessions."""
        manager = SessionManager(temp_sessions_dir)

        # Create multiple sessions
        manager.create_session("Task 1", "/path1")
        manager.create_session("Task 2", "/path1")
        manager.create_session("Task 3", "/path2")

        # List all sessions
        all_sessions = manager.list_sessions()
        assert len(all_sessions) == 3

        # List sessions for specific project
        path1_sessions = manager.list_sessions(project_root="/path1")
        assert len(path1_sessions) == 2

    def test_get_latest_session(self, temp_sessions_dir):
        """Test getting the most recent session."""
        manager = SessionManager(temp_sessions_dir)

        # Create sessions
        session1 = manager.create_session("Task 1", "/path")
        time.sleep(0.01)  # Ensure different timestamps
        session2 = manager.create_session("Task 2", "/path")

        # Get latest
        latest = manager.get_latest_session("/path")

        assert latest is not None
        assert latest.session_id == session2.session_id


class TestAgentTask:
    """Tests for agent task."""

    def test_create_task(self):
        """Test creating a task."""
        task = AgentTask("task-123", "Fix authentication")

        assert task.task_id == "task-123"
        assert task.description == "Fix authentication"
        assert task.status == "pending"
        assert task.progress == 0

    def test_task_lifecycle(self):
        """Test task lifecycle (pending -> running -> complete)."""
        task = AgentTask("task-123", "Task")

        # Start task
        task.start()
        assert task.status == "running"
        assert task.started_at is not None

        # Update progress
        task.update_progress(50, "Processing...")
        assert task.progress == 50
        assert task.current_step == "Processing..."

        # Complete task
        result = {"status": "success", "output": "Done!"}
        task.complete(result)

        assert task.status == "complete"
        assert task.result == result
        assert task.progress == 100
        assert task.completed_at is not None

    def test_task_failure(self):
        """Test task failure."""
        task = AgentTask("task-123", "Task")

        task.start()
        task.fail("Something went wrong")

        assert task.status == "error"
        assert task.error == "Something went wrong"
        assert task.completed_at is not None

    def test_task_cancellation(self):
        """Test task cancellation."""
        task = AgentTask("task-123", "Task")

        task.start()
        task.cancel()

        assert task.status == "cancelled"
        assert task.is_cancelled()

    def test_to_dict(self):
        """Test converting task to dict."""
        task = AgentTask("task-123", "Task", "session-456")
        task.start()

        data = task.to_dict()

        assert data["task_id"] == "task-123"
        assert data["description"] == "Task"
        assert data["session_id"] == "session-456"
        assert data["status"] == "running"


class TestTaskManager:
    """Tests for task manager."""

    def test_create_task(self):
        """Test creating a task."""
        manager = TaskManager(max_concurrent=2)

        task = manager.create_task("Fix bug", "session-123")

        assert task.task_id is not None
        assert task.description == "Fix bug"
        assert task.session_id == "session-123"
        assert task.status == "pending"

    def test_get_task(self):
        """Test retrieving a task."""
        manager = TaskManager(max_concurrent=2)

        task = manager.create_task("Task")
        retrieved = manager.get_task(task.task_id)

        assert retrieved is not None
        assert retrieved.task_id == task.task_id

    def test_submit_and_execute_task(self):
        """Test submitting and executing a task."""
        manager = TaskManager(max_concurrent=2)

        task = manager.create_task("Test task")

        # Define simple execution function
        def execute_fn(task):
            task.update_progress(50)
            return {"result": "success"}

        # Submit task
        manager.submit_task(task.task_id, execute_fn)

        # Wait for completion (with timeout)
        timeout = time.time() + 5
        while task.status != "complete" and time.time() < timeout:
            time.sleep(0.1)

        assert task.status == "complete"
        assert task.result["result"] == "success"

    def test_cancel_task(self):
        """Test cancelling a task."""
        manager = TaskManager(max_concurrent=2)

        task = manager.create_task("Task")

        manager.cancel_task(task.task_id)

        assert task.status == "cancelled"

    def test_list_tasks(self):
        """Test listing tasks."""
        manager = TaskManager(max_concurrent=2)

        # Create tasks
        manager.create_task("Task 1", "session-1")
        manager.create_task("Task 2", "session-1")
        manager.create_task("Task 3", "session-2")

        # List all
        all_tasks = manager.list_tasks()
        assert len(all_tasks) == 3

        # Filter by session
        session1_tasks = manager.list_tasks(session_id="session-1")
        assert len(session1_tasks) == 2

    def test_cleanup_old_tasks(self):
        """Test cleaning up old tasks."""
        manager = TaskManager(max_concurrent=2)

        # Create and complete a task
        task = manager.create_task("Old task")
        task.complete({"result": "done"})

        # Cleanup (with 0 hour age to remove all completed)
        manager.cleanup_old_tasks(max_age_hours=0)

        # Task should be removed
        assert manager.get_task(task.task_id) is None
