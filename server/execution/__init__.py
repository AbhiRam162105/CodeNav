"""
Execution layer for CodeNav.
Handles command execution, terminals, sessions, and task management.
"""

from execution.command import (
    is_command_safe,
    CommandExecutor,
    execute_command,
    ALLOWED_COMMANDS,
    BLOCKED_PATTERNS
)

from execution.terminal import (
    TerminalSession,
    TerminalManager,
    get_terminal_manager
)

from execution.sessions import (
    AgentSession,
    SessionManager,
    get_session_manager
)

from execution.tasks import (
    AgentTask,
    TaskManager,
    get_task_manager
)

__all__ = [
    # Command execution
    "is_command_safe",
    "CommandExecutor",
    "execute_command",
    "ALLOWED_COMMANDS",
    "BLOCKED_PATTERNS",
    # Terminal sessions
    "TerminalSession",
    "TerminalManager",
    "get_terminal_manager",
    # Session persistence
    "AgentSession",
    "SessionManager",
    "get_session_manager",
    # Task management
    "AgentTask",
    "TaskManager",
    "get_task_manager",
]
