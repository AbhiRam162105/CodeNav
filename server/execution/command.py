"""
Command execution with safety checks and output streaming.
"""
import os
import subprocess
import threading
import logging
from typing import Optional, Callable, List
from queue import Queue, Empty
import shlex

logger = logging.getLogger(__name__)


# Allowed commands - whitelist approach for security
ALLOWED_COMMANDS = {
    # Testing
    "pytest", "python", "node", "npm", "yarn",
    # Build tools
    "make", "cargo", "go",
    # Git
    "git",
    # Package managers
    "pip", "poetry", "pipenv",
    # Linters/formatters
    "black", "flake8", "pylint", "eslint", "prettier",
    # Others
    "ls", "cat", "echo", "grep", "find",
}

# Dangerous patterns to block
BLOCKED_PATTERNS = [
    "rm -rf",
    "sudo",
    "chmod +x",
    "> /dev/",
    "dd if=",
    "mkfs",
    "shutdown",
    "reboot",
]


def is_command_safe(command: str) -> tuple[bool, Optional[str]]:
    """
    Check if a command is safe to execute.

    Args:
        command: Command string to check

    Returns:
        Tuple of (is_safe, error_message)
    """
    # Check for blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if pattern in command.lower():
            return False, f"Blocked pattern detected: {pattern}"

    # Extract base command
    try:
        parts = shlex.split(command)
        if not parts:
            return False, "Empty command"

        base_command = os.path.basename(parts[0])

        # Check if command is in whitelist
        if base_command not in ALLOWED_COMMANDS:
            return False, f"Command not in whitelist: {base_command}"

        return True, None

    except ValueError as e:
        return False, f"Invalid command syntax: {str(e)}"


class CommandExecutor:
    """Executes commands with timeout and output streaming."""

    def __init__(self, cwd: str, timeout: int = 60):
        """
        Initialize command executor.

        Args:
            cwd: Working directory for commands
            timeout: Default timeout in seconds
        """
        self.cwd = cwd
        self.timeout = timeout
        self.process: Optional[subprocess.Popen] = None
        self._output_queue: Queue = Queue()
        self._stop_event = threading.Event()

    def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        on_output: Optional[Callable[[str], None]] = None
    ) -> dict:
        """
        Execute a command and return the result.

        Args:
            command: Command to execute
            timeout: Timeout in seconds (overrides default)
            on_output: Callback for output lines (for streaming)

        Returns:
            Dict with status, stdout, stderr, exit_code
        """
        # Safety check
        is_safe, error = is_command_safe(command)
        if not is_safe:
            logger.warning(f"Blocked unsafe command: {command} - {error}")
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"Command blocked: {error}",
                "exit_code": -1
            }

        timeout_val = timeout if timeout is not None else self.timeout

        logger.info(f"Executing command: {command} (timeout: {timeout_val}s)")

        try:
            # Start process
            self.process = subprocess.Popen(
                command,
                shell=True,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )

            # Collect output
            stdout_lines = []
            stderr_lines = []

            def read_stdout():
                """Read stdout in thread."""
                for line in iter(self.process.stdout.readline, ''):
                    if self._stop_event.is_set():
                        break
                    stdout_lines.append(line)
                    if on_output:
                        on_output(line)

            def read_stderr():
                """Read stderr in thread."""
                for line in iter(self.process.stderr.readline, ''):
                    if self._stop_event.is_set():
                        break
                    stderr_lines.append(line)

            # Start output readers
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)

            stdout_thread.start()
            stderr_thread.start()

            # Wait for completion
            try:
                exit_code = self.process.wait(timeout=timeout_val)
            except subprocess.TimeoutExpired:
                logger.warning(f"Command timed out after {timeout_val}s: {command}")
                self.kill()
                return {
                    "status": "timeout",
                    "stdout": ''.join(stdout_lines),
                    "stderr": ''.join(stderr_lines) + f"\n[Timeout after {timeout_val}s]",
                    "exit_code": -1
                }

            # Wait for threads to finish
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)

            # Determine status
            if exit_code == 0:
                status = "success"
            else:
                status = "error"

            return {
                "status": status,
                "stdout": ''.join(stdout_lines),
                "stderr": ''.join(stderr_lines),
                "exit_code": exit_code
            }

        except Exception as e:
            logger.error(f"Error executing command: {e}", exc_info=True)
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "exit_code": -1
            }

        finally:
            self.process = None
            self._stop_event.clear()

    def kill(self):
        """Kill the running process."""
        if self.process:
            self._stop_event.set()
            try:
                self.process.kill()
                self.process.wait(timeout=5)
            except Exception as e:
                logger.error(f"Error killing process: {e}")


def execute_command(command: str, cwd: str, timeout: int = 60) -> dict:
    """
    Execute a single command (convenience function).

    Args:
        command: Command to execute
        cwd: Working directory
        timeout: Timeout in seconds

    Returns:
        Result dict
    """
    executor = CommandExecutor(cwd, timeout)
    return executor.execute(command, timeout)
