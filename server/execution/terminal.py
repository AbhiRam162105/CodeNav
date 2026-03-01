"""
Terminal session management for persistent command execution.
"""
import os
import pty
import subprocess
import select
import threading
import logging
from typing import Optional, Callable
from queue import Queue
import uuid

logger = logging.getLogger(__name__)


class TerminalSession:
    """Manages a persistent terminal session."""

    def __init__(self, session_id: str, cwd: str, shell: str = "/bin/bash"):
        """
        Initialize terminal session.

        Args:
            session_id: Unique session ID
            cwd: Working directory
            shell: Shell to use (default: /bin/bash)
        """
        self.session_id = session_id
        self.cwd = cwd
        self.shell = shell
        self.master_fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.output_queue: Queue = Queue()
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.is_active = False

    def start(self):
        """Start the terminal session."""
        if self.is_active:
            raise RuntimeError("Session already active")

        logger.info(f"Starting terminal session {self.session_id}")

        try:
            # Fork a PTY
            self.pid, self.master_fd = pty.fork()

            if self.pid == 0:
                # Child process - execute shell
                os.chdir(self.cwd)
                os.execv(self.shell, [self.shell])
            else:
                # Parent process - start output reader
                self.is_active = True
                self._reader_thread = threading.Thread(
                    target=self._read_output,
                    daemon=True
                )
                self._reader_thread.start()

                logger.info(f"Terminal session {self.session_id} started (PID: {self.pid})")

        except Exception as e:
            logger.error(f"Failed to start terminal session: {e}", exc_info=True)
            self.cleanup()
            raise

    def _read_output(self):
        """Read output from PTY in background thread."""
        try:
            while not self._stop_event.is_set():
                # Use select to check for available data
                ready, _, _ = select.select([self.master_fd], [], [], 0.1)

                if ready:
                    try:
                        data = os.read(self.master_fd, 1024)
                        if not data:
                            # EOF reached
                            break

                        # Decode and queue output
                        text = data.decode('utf-8', errors='replace')
                        self.output_queue.put(text)

                    except OSError:
                        # PTY closed
                        break

        except Exception as e:
            logger.error(f"Error reading terminal output: {e}", exc_info=True)

        finally:
            self.is_active = False
            logger.info(f"Terminal session {self.session_id} output reader stopped")

    def send_command(self, command: str):
        """
        Send a command to the terminal.

        Args:
            command: Command to execute
        """
        if not self.is_active:
            raise RuntimeError("Session not active")

        # Add newline if not present
        if not command.endswith('\n'):
            command += '\n'

        try:
            os.write(self.master_fd, command.encode('utf-8'))
            logger.debug(f"Sent command to session {self.session_id}: {command.strip()}")

        except Exception as e:
            logger.error(f"Error sending command: {e}", exc_info=True)
            raise

    def read_output(self, timeout: float = 1.0) -> str:
        """
        Read accumulated output from the terminal.

        Args:
            timeout: How long to wait for output (seconds)

        Returns:
            Output string
        """
        import time

        output_parts = []
        end_time = time.time() + timeout

        while time.time() < end_time:
            try:
                # Try to get output without blocking
                text = self.output_queue.get(timeout=0.1)
                output_parts.append(text)
            except:
                # No more output available
                break

        return ''.join(output_parts)

    def cleanup(self):
        """Clean up the terminal session."""
        logger.info(f"Cleaning up terminal session {self.session_id}")

        self._stop_event.set()

        # Close PTY
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except:
                pass
            self.master_fd = None

        # Kill process
        if self.pid is not None:
            try:
                os.kill(self.pid, 9)
                os.waitpid(self.pid, 0)
            except:
                pass
            self.pid = None

        # Wait for reader thread
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2)

        self.is_active = False

    def __del__(self):
        """Cleanup on deletion."""
        self.cleanup()


class TerminalManager:
    """Manages multiple terminal sessions."""

    def __init__(self):
        """Initialize terminal manager."""
        self.sessions: dict[str, TerminalSession] = {}

    def create_session(self, cwd: str, shell: str = "/bin/bash") -> str:
        """
        Create a new terminal session.

        Args:
            cwd: Working directory
            shell: Shell to use

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())

        session = TerminalSession(session_id, cwd, shell)
        session.start()

        self.sessions[session_id] = session

        logger.info(f"Created terminal session {session_id}")

        return session_id

    def get_session(self, session_id: str) -> Optional[TerminalSession]:
        """
        Get a terminal session by ID.

        Args:
            session_id: Session ID

        Returns:
            TerminalSession or None
        """
        return self.sessions.get(session_id)

    def close_session(self, session_id: str):
        """
        Close a terminal session.

        Args:
            session_id: Session ID
        """
        session = self.sessions.pop(session_id, None)

        if session:
            session.cleanup()
            logger.info(f"Closed terminal session {session_id}")

    def close_all(self):
        """Close all terminal sessions."""
        logger.info(f"Closing all {len(self.sessions)} terminal sessions")

        for session_id in list(self.sessions.keys()):
            self.close_session(session_id)

    def __del__(self):
        """Cleanup on deletion."""
        self.close_all()


# Global terminal manager instance
_terminal_manager: Optional[TerminalManager] = None


def get_terminal_manager() -> TerminalManager:
    """Get the global terminal manager instance."""
    global _terminal_manager

    if _terminal_manager is None:
        _terminal_manager = TerminalManager()

    return _terminal_manager
