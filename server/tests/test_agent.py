"""
Tests for the agent system.
"""
import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from agent.llm_client import GeminiClient, get_client
from agent.prompts import build_system_prompt, get_tool_definitions
from agent.tool_parser import parse_tool_call, extract_text_before_tool_call
from agent.tool_executor import (
    execute_tool,
    execute_read_lines,
    execute_search,
    execute_retrieve_context,
    execute_apply_diff,
    execute_create_file,
    execute_ask_user,
    execute_finish,
    SENTINEL_ASK_USER,
    SENTINEL_FINISH
)
from agent.history import HistoryManager
from agent.loop import run_agent
from state import AppState


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    temp_dir = tempfile.mkdtemp()

    # Create test files
    os.makedirs(os.path.join(temp_dir, "src"), exist_ok=True)

    with open(os.path.join(temp_dir, "src", "main.py"), "w") as f:
        f.write("""def hello():
    return "Hello, World!"

def add(a, b):
    return a + b
""")

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_state(temp_project):
    """Create a mock AppState."""
    state = AppState()
    state.project_root = temp_project
    state.codemap = {
        "function_count": 2,
        "file_count": 1,
        "files": {
            "src/main.py": {
                "functions": {
                    "src/main.py::hello": {
                        "name": "hello",
                        "qualified_name": "src/main.py::hello",
                        "file": "src/main.py",
                        "line_start": 1,
                        "line_end": 2,
                        "calls": []
                    },
                    "src/main.py::add": {
                        "name": "add",
                        "qualified_name": "src/main.py::add",
                        "file": "src/main.py",
                        "line_start": 4,
                        "line_end": 5,
                        "calls": []
                    }
                }
            }
        }
    }
    return state


class TestToolParser:
    """Tests for tool_parser module."""

    def test_parse_tool_call_valid(self):
        """Test parsing a valid tool call."""
        text = """Let me read the file.
<tool_call>{"name": "read_lines", "params": {"file": "src/main.py", "start": 1, "end": 5}}</tool_call>"""

        result = parse_tool_call(text)

        assert result is not None
        assert result["name"] == "read_lines"
        assert result["params"]["file"] == "src/main.py"
        assert result["params"]["start"] == 1
        assert result["params"]["end"] == 5

    def test_parse_tool_call_no_tool(self):
        """Test parsing text without a tool call."""
        text = "Just some regular text without a tool call."

        result = parse_tool_call(text)

        assert result is None

    def test_parse_tool_call_invalid_json(self):
        """Test parsing tool call with invalid JSON."""
        text = '<tool_call>{invalid json}</tool_call>'

        result = parse_tool_call(text)

        assert result is None

    def test_extract_text_before_tool_call(self):
        """Test extracting text before tool call."""
        text = """Let me read the file for you.
<tool_call>{"name": "read_lines", "params": {}}</tool_call>"""

        result = extract_text_before_tool_call(text)

        assert result == "Let me read the file for you."

    def test_extract_text_before_no_tool_call(self):
        """Test extracting text when no tool call present."""
        text = "Just some text."

        result = extract_text_before_tool_call(text)

        assert result == "Just some text."


class TestToolExecutor:
    """Tests for tool_executor module."""

    def test_execute_read_lines(self, mock_state):
        """Test reading lines from a file."""
        params = {
            "file": "src/main.py",
            "start": 1,
            "end": 2
        }

        result = execute_read_lines(params, mock_state)

        assert "Lines 1-2 from src/main.py" in result
        assert "def hello():" in result
        assert 'return "Hello, World!"' in result

    def test_execute_read_lines_no_file(self, mock_state):
        """Test reading with no file parameter."""
        params = {}

        result = execute_read_lines(params, mock_state)

        assert "Error" in result
        assert "'file' parameter required" in result

    def test_execute_read_lines_file_not_found(self, mock_state):
        """Test reading a file that doesn't exist."""
        params = {
            "file": "nonexistent.py",
            "start": 1
        }

        result = execute_read_lines(params, mock_state)

        assert "Error" in result
        assert "not found" in result

    def test_execute_apply_diff(self, mock_state):
        """Test applying a diff to a file."""
        params = {
            "file": "src/main.py",
            "original": 'return "Hello, World!"',
            "modified": 'return "Hello, CodeNav!"'
        }

        result = execute_apply_diff(params, mock_state)

        assert "Successfully applied diff" in result

        # Verify the change was applied
        with open(os.path.join(mock_state.project_root, "src/main.py"), "r") as f:
            content = f.read()
            assert "Hello, CodeNav!" in content

    def test_execute_apply_diff_stale(self, mock_state):
        """Test applying a diff with stale original text."""
        params = {
            "file": "src/main.py",
            "original": "def nonexistent():",
            "modified": "def new():"
        }

        result = execute_apply_diff(params, mock_state)

        assert "Error" in result
        assert "not found" in result

    def test_execute_create_file(self, mock_state):
        """Test creating a new file."""
        params = {
            "path": "src/new_module.py",
            "content": "def new_function():\n    pass\n"
        }

        result = execute_create_file(params, mock_state)

        assert "Successfully created" in result

        # Verify file exists
        new_file_path = os.path.join(mock_state.project_root, "src/new_module.py")
        assert os.path.exists(new_file_path)

        with open(new_file_path, "r") as f:
            content = f.read()
            assert "def new_function():" in content

    def test_execute_ask_user(self):
        """Test ask_user tool."""
        params = {"question": "Should I proceed?"}

        result = execute_ask_user(params)

        assert result.startswith(SENTINEL_ASK_USER)
        assert "Should I proceed?" in result

    def test_execute_finish(self):
        """Test finish tool."""
        params = {"response": "Task completed successfully"}

        result = execute_finish(params)

        assert result.startswith(SENTINEL_FINISH)
        assert "Task completed successfully" in result


class TestHistoryManager:
    """Tests for HistoryManager."""

    def test_add_messages(self):
        """Test adding messages to history."""
        history = HistoryManager()

        history.add_user("Hello")
        history.add_model("Hi there!")
        history.add_tool_result("read_lines", "File contents...")

        messages = history.get_messages()

        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        assert "[Tool: read_lines]" in messages[2]["content"]

    def test_trim_to_budget(self):
        """Test trimming history to token budget."""
        history = HistoryManager()

        # Add several messages
        history.add_user("Task: " + "x" * 1000)
        for i in range(10):
            history.add_model(f"Response {i}: " + "y" * 500)
            history.add_user(f"Follow-up {i}: " + "z" * 500)

        # Should have 21 messages (1 initial + 10 * 2)
        assert len(history) == 21

        # Trim to small budget
        history.trim_to_budget(100)  # Very small budget

        messages = history.get_messages()

        # Should keep first message and some recent ones
        assert len(messages) < 21
        assert messages[0]["content"].startswith("Task:")

    def test_get_last_n_messages(self):
        """Test getting last N messages."""
        history = HistoryManager()

        history.add_user("Message 1")
        history.add_model("Response 1")
        history.add_user("Message 2")
        history.add_model("Response 2")

        last_2 = history.get_last_n_messages(2)

        assert len(last_2) == 2
        assert last_2[0]["content"] == "Message 2"
        assert last_2[1]["content"] == "Response 2"

    def test_clear(self):
        """Test clearing history."""
        history = HistoryManager()

        history.add_user("Test")
        history.add_model("Response")

        assert len(history) == 2

        history.clear()

        assert len(history) == 0
        assert history.original_task == ""


class TestPrompts:
    """Tests for prompts module."""

    def test_build_system_prompt(self):
        """Test building system prompt."""
        codemap_summary = {
            "function_count": 42,
            "file_count": 10
        }

        prompt = build_system_prompt(codemap_summary)

        assert "CodeNav" in prompt
        assert "42 functions" in prompt
        assert "10 files" in prompt
        assert "read_lines" in prompt
        assert "search_codebase" in prompt
        assert "apply_diff" in prompt

    def test_get_tool_definitions(self):
        """Test getting tool definitions."""
        definitions = get_tool_definitions()

        # Should include all tools
        assert "read_lines" in definitions
        assert "search_codebase" in definitions
        assert "retrieve_context" in definitions
        assert "apply_diff" in definitions
        assert "create_file" in definitions
        assert "run_command" in definitions
        assert "ask_user" in definitions
        assert "finish" in definitions


class TestAgentLoop:
    """Tests for agent loop."""

    @patch('agent.loop.get_client')
    def test_run_agent_finish(self, mock_get_client, mock_state):
        """Test agent loop with finish tool."""
        # Mock LLM client
        mock_client = Mock()
        mock_client.invoke.return_value = '<tool_call>{"name": "finish", "params": {"response": "Done!"}}</tool_call>'
        mock_get_client.return_value = mock_client

        result = run_agent("Simple task", mock_state, max_iterations=5)

        assert result["status"] == "complete"
        assert result["response"] == "Done!"
        assert len(result["tool_calls_made"]) == 1
        assert result["tool_calls_made"][0]["tool"] == "finish"

    @patch('agent.loop.get_client')
    def test_run_agent_ask_user(self, mock_get_client, mock_state):
        """Test agent loop with ask_user tool."""
        # Mock LLM client
        mock_client = Mock()
        mock_client.invoke.return_value = '<tool_call>{"name": "ask_user", "params": {"question": "Proceed?"}}</tool_call>'
        mock_get_client.return_value = mock_client

        result = run_agent("Task needing input", mock_state, max_iterations=5)

        assert result["status"] == "needs_input"
        assert result["question"] == "Proceed?"

    @patch('agent.loop.get_client')
    def test_run_agent_max_iterations(self, mock_get_client, mock_state):
        """Test agent loop reaching max iterations."""
        # Mock LLM client - returns response without tool call
        mock_client = Mock()
        mock_client.invoke.return_value = "Thinking about the task..."
        mock_get_client.return_value = mock_client

        result = run_agent("Complex task", mock_state, max_iterations=3)

        assert result["status"] == "max_iterations"

    @patch('agent.loop.get_client')
    def test_run_agent_llm_error(self, mock_get_client, mock_state):
        """Test agent loop with LLM error."""
        # Mock LLM client to raise exception
        mock_client = Mock()
        mock_client.invoke.side_effect = Exception("API error")
        mock_get_client.return_value = mock_client

        result = run_agent("Task", mock_state, max_iterations=5)

        assert result["status"] == "error"
        assert "API error" in result["response"]


class TestLLMClient:
    """Tests for LLM client."""

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    @patch('agent.llm_client.genai')
    def test_gemini_client_init(self, mock_genai):
        """Test GeminiClient initialization."""
        client = GeminiClient()

        # Should configure with API key
        mock_genai.configure.assert_called_once()
        assert mock_genai.configure.call_args[1]["api_key"] == "test-key"

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    @patch('agent.llm_client.genai')
    def test_gemini_client_invoke(self, mock_genai):
        """Test GeminiClient invoke method."""
        # Mock the model and response
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        client = GeminiClient()

        response = client.invoke(
            system_prompt="You are a helpful assistant",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=100
        )

        assert response == "Test response"
        mock_model.generate_content.assert_called_once()

    def test_get_client_singleton(self):
        """Test that get_client returns the same instance."""
        client1 = get_client()
        client2 = get_client()

        assert client1 is client2
